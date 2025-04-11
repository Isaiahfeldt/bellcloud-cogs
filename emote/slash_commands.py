#  Copyright (c) 2023-2024, Isaiah Feldt
#  ͏
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU Affero General Public License (AGPL) as published by
#     - the Free Software Foundation, either version 3 of this License,
#     - or (at your option) any later version.
#  ͏
#     - This program is distributed in the hope that it will be useful,
#     - but without any warranty, without even the implied warranty of
#     - merchantability or fitness for a particular purpose.
#     - See the GNU Affero General Public License for more details.
#  ͏
#     - You should have received a copy of the GNU Affero General Public License
#     - If not, please see <https://www.gnu.org/licenses/#GPL>.
import asyncio
import base64
import hashlib
import io
import json
import os
import random
import time
from textwrap import wrap
from typing import List, Tuple, Optional

import aiohttp
import discord
from discord import app_commands
from fuzzywuzzy import fuzz, process
from openai import OpenAI
from redbot.core import commands
# from discord.app_commands import Choice, commands # Original comments kept
# from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from .utils import effects as effect  # Import effects module
from .utils.chat import send_error_embed, send_embed_followup, send_error_followup, send_emote, \
    generate_token
from .utils.database import Database
from .utils.effects import Emote  # Import Emote dataclass
from .utils.enums import EmoteAddError, EmoteRemoveError, EmoteError, EmbedColor
from .utils.format import is_enclosed_in_colon, extract_emote_details
from .utils.pipeline import create_pipeline, execute_pipeline
from .utils.url import is_url_reachable, blacklisted_url, is_media_format_valid, is_media_size_valid, alphanumeric_name

_ = Translator("Emote", __file__)

valid_formats = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
db = Database()  # Instantiate Database


def generate_effects_signature(queued_effects: List[Tuple[str, list]]) -> str:
    """Generates a canonical string signature for a list of effects and their args."""
    parts = []
    for effect_name, effect_args in queued_effects:
        args_str = ""
        if effect_args:
            args_str = f"({','.join(map(str, effect_args))})"
        parts.append(f"{effect_name}{args_str}")
    return "_".join(parts)


def generate_variant_filename(original_emote_id: int, signature: str, file_type: str) -> str:
    """Generates a unique filename for a variant based on emote ID and signature hash."""
    hasher = hashlib.sha256(signature.encode())
    hash_prefix = hasher.hexdigest()[:16]  # Use first 16 hex characters of the hash
    return f"{original_emote_id}_{hash_prefix}.{file_type.lower()}"


def get_file_type_from_path(file_path: str) -> str:
    """Extracts the file extension from a path."""
    return file_path.split('.')[-1].lower() if '.' in file_path else 'png'  # Default?


def calculate_extra_args(time_elapsed: Optional[float], emote: Emote, was_cached: bool = False) -> list:
    """Calculates extra arguments for the send_emote function."""
    extra_args = []
    if SlashCommands.latency_enabled and time_elapsed is not None:
        processing_time_str = f"Processed in `{time_elapsed:.3f}` seconds!"
        if was_cached:
            processing_time_str += " (Cached ✨)"
        extra_args.append(processing_time_str)

    if SlashCommands.debug_enabled:
        debug_lines = []
        debug_lines.append(f"Variant Cache: {'Hit ⚡' if was_cached else 'Miss 🐌'}")
        # Add other notes stored during processing
        if emote.notes:
            for key, value in emote.notes.items():
                debug_lines.append(f"{key.replace('_', ' ').title()}: {value}")
        if debug_lines:
            extra_args.append("\n".join(debug_lines))

    # Append emote.followup if it exists
    if emote.followup:
        followup_lines = ["**Notes:**"]
        for key, value in emote.followup.items():
            followup_lines.append(f"- **{key}:** {value}")
        if len(followup_lines) > 1:
            extra_args.append("\n".join(followup_lines))

    return extra_args


def encode_image(image_data):
    """Encodes image bytes as base64 string"""
    return base64.b64encode(image_data).decode('utf-8')


async def analyze_uwu(content=None, image_url=None, current_strikes: int = 0):
    """Analyzes text/image for UwU-style content using OpenAI"""
    api_key = os.getenv('OPENAI_KEY')
    if not api_key:
        print("Warning: OPENAI_KEY environment variable not set. April Fools features disabled.")
        return {"isUwU": True, "reason": "OpenAI key not configured."}  # Bypass if no key

    client = OpenAI(api_key=api_key)

    messages = [{
        "role": "system",
        "content":
            "You are a discord bot that analyzes messages for UwU-style content in the general-3 channel. "
            "Analyze for *any* UwU-style elements (cute text, emoticons, playful misspellings). "
            "Messages don't necessarily have to be 'happy', they can be angry, mean, etc as long as they follow the other rules. "
            "Examples: 'i fwucking hate dis server', 'wat da hell...'. "
            f"Keep in mind that the user is currently on warning {current_strikes + 1}/3; each message that lacks these creative touches "
            "Write your reason in uWu speak in 1-2 sentences. "
            "Try to avoid reiterating the rules verbatim. Do not say 'uwu-style' or anything similar. "
            "Respond with JSON: {\"isUwU\": bool, \"reason\": str}"
    }]

    user_content = []
    if content:
        user_content.append({"type": "text", "text": f"Message: {content}\nIs this UwU-style? Respond with JSON."})

    if image_url:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": image_url, "detail": "auto"},  # Let OpenAI decide detail level
        })
        user_content.insert(0, {"type": "text",
                                "text": "Analyze this message content and image (if present) for UwU-style elements. Respond with JSON."})

    if user_content:
        messages.append({"role": "user", "content": user_content})
    else:
        return {"isUwU": True, "reason": "No content to analyze."}

    try:
        response = await client.chat.completions.create(  # Use async client if available, otherwise sync
            model="gpt-4o-mini-2024-07-18",  # Or your preferred model
            messages=messages,
            max_tokens=150,  # Reduced tokens
            response_format={"type": "json_object"}  # Request JSON output directly
        )
        response_content = response.choices[0].message.content
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        print(f"OpenAI JSON Decode Error: {e}, Response: {response_content}")
        return {"isUwU": False, "reason": "Sorwy, couwdn't undewstand the API wesponse! >_<"}
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return {"isUwU": False,
                "reason": f"Oopsie! My bwain had a fritz connecting to the AI! (Error: {type(e).__name__})"}


async def get_emote_and_verify(emote_name_str: str, channel):
    """Fetches the base emote data, handling not found cases."""
    emote = await db.get_emote(emote_name_str, channel.guild.id, inc_count=False)
    if emote is None:
        valid_names = await db.get_emote_names(channel.guild.id)

        matches = process.extractBests(
            emote_name_str,
            valid_names,
            scorer=fuzz.token_sort_ratio,  # Good for matching out-of-order words
            score_cutoff=70
        )

        if matches:
            best_match = matches[0][0]
            await channel.send(f"Emote `:{emote_name_str}:` not found. Did you mean `:{best_match}:`?")
        else:
            await channel.send(f"Emote `:{emote_name_str}:` not found.")
        return None  # Explicitly return None

    return emote


def get_cache_info(return_as_boolean=False):
    """
    Returns cache information based on the specified argument.
    (Note: db.cache now holds DB query results, not generated emotes)
    """
    cache_state = db.cache
    if return_as_boolean:
        return bool(cache_state)
    cache_details = [f"DB Query Cache Size: {cache_state.currsize}/{cache_state.maxsize}"]
    return "\n".join(cache_details)


@cog_i18n(_)
@app_commands.guild_only()
class SlashCommands(commands.Cog):
    """This class defines the SlashCommands cog"""
    emote = app_commands.Group(name="emote", description="Sorta like emojis, but cooler")

    PERMISSION_LIST = {
        "owner": lambda message, self: self.bot.is_owner(message.author),
        "mod": lambda message, _: message.author.guild_permissions.manage_messages,
        "everyone": lambda _, __: True,
    }

    EFFECTS_LIST = {
        # Non-blocking (or very fast) effects
        "latency": {'func': effect.latency, 'perm': 'mod', 'single_use': True, 'blocking': False},
        "debug": {'func': effect.debug, 'perm': 'everyone', 'single_use': True, 'blocking': False},
        "train": {'func': effect.train, 'perm': 'everyone', 'single_use': True, 'blocking': False},  # Just sets a flag

        # Potentially blocking effects (PIL/Numpy/Moviepy)
        "flip": {'func': effect.flip, 'perm': 'everyone', 'blocking': True},
        "reverse": {'func': effect.reverse, 'perm': 'everyone', 'single_use': True, 'blocking': True},
        "invert": {'func': effect.invert, 'perm': 'everyone', 'blocking': True},
        "speed": {'func': effect.speed, 'perm': 'everyone', 'single_use': True, 'blocking': True},
        "fast": {'func': effect.fast, 'perm': 'everyone', 'single_use': True, 'blocking': True},  # Alias for speed
        "slow": {'func': effect.slow, 'perm': 'everyone', 'single_use': True, 'blocking': True},  # Alias for speed
        "shake": {'func': effect.shake, 'perm': 'everyone', 'single_use': False, 'blocking': True},
        # Allow multiple shakes? Revisit if needed
        "rainbow": {'func': effect.rainbow, 'perm': 'everyone', 'single_use': True, 'blocking': True},
        "spin": {'func': effect.spin, 'perm': 'everyone', 'single_use': True, 'blocking': True}
    }
    reaction_effects = {
        "🔄": effect.reverse,
        "⏩": effect.fast,
        "🐢": effect.slow,
        "🔀": effect.invert,
        "🤸": effect.flip,
        "↕️": effect.flip,  # Note: This needs special handling for direction 'v'
        "🌈": effect.rainbow,
        "😵": effect.spin,
        "💥": effect.shake,
    }

    # Cog state flags
    latency_enabled = False
    debug_enabled = False
    train_count = 1

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(db.init_pool())

    async def cog_unload(self):
        await db.close_pool()

    @emote.command(name="add", description="Add an emote to the server")
    @app_commands.describe(
        name="The name of the new emote",
        url="The URL of a supported file type to add as an emote"
    )
    @commands.has_permissions(manage_messages=True)  # Use Red's permission check
    async def emote_add(self, interaction: discord.Interaction, name: str, url: str):
        await interaction.response.defer(ephemeral=True)  # Acknowledge interaction quickly

        if not alphanumeric_name(name):  # Check if the name is valid first
            await send_error_followup(interaction, EmoteAddError.INVALID_NAME_CHAR)
            return

        rules = [
            (lambda: len(name) <= 32, EmoteAddError.EXCEED_NAME_LEN),
            (lambda: is_url_reachable(url), EmoteAddError.UNREACHABLE_URL),
            (lambda: not blacklisted_url(url), EmoteAddError.BLACKLISTED_URL),
            (lambda: is_media_format_valid(url, valid_formats), EmoteAddError.INVALID_FILE_FORMAT),
            (lambda: is_media_size_valid(url, 52428800), EmoteAddError.EXCEED_FILE_SIZE),  # 50MB limit
        ]

        for condition, error in rules:
            is_valid = False
            # Need to await if condition is async
            if asyncio.iscoroutinefunction(condition):
                is_valid = await condition()
            else:
                is_valid = condition()
            if not is_valid:
                await send_error_followup(interaction, error)
                return

        if await db.check_emote_exists(name, interaction.guild_id):
            await send_error_followup(interaction, EmoteAddError.DUPLICATE_EMOTE_NAME)
            return

        valid_check_result = is_media_format_valid(url, valid_formats)
        if not valid_check_result[0]:
            await send_error_followup(interaction, EmoteAddError.INVALID_FILE_FORMAT)
            return
        file_type = str(valid_check_result[1])

        success, db_error = await db.add_emote_to_database(interaction, name, url, file_type)

        if not success:
            if db_error == EmoteError.S3_UPLOAD_FAILED:
                add_error = EmoteAddError.S3_UPLOAD_FAILED
            elif db_error == EmoteError.DUPLICATE_EMOTE_NAME:
                add_error = EmoteAddError.DUPLICATE_EMOTE_NAME
            else:  # Generic DB or other error
                add_error = EmoteAddError.DATABASE_ERROR
            await send_error_followup(interaction, add_error)
            return

        await send_embed_followup(
            interaction, "Success! ✨", f"Added `:{name}:` as an emote."
        )

    @emote.command(name="remove", description="Remove an emote (and its variants) from the server")
    @app_commands.describe(name="The name of the emote to remove")
    @commands.has_permissions(manage_messages=True)
    async def emote_remove(self, interaction: discord.Interaction, name: str):
        success, error_enum = await db.remove_emote_from_database(interaction.guild_id, name)

        if not success:
            if error_enum == EmoteError.NOTFOUND_EMOTE_NAME:
                remove_error = EmoteRemoveError.NOTFOUND_EMOTE_NAME
            else:
                remove_error = EmoteRemoveError.DATABASE_ERROR  # Use a generic one for now
            await send_error_followup(interaction, remove_error)
            return

        await send_embed_followup(
            interaction, "Success! 🗑️", f"Removed `:{name}:` and all its cached variants."
        )

    @emote.command(name="list", description="List all emotes in the server")
    async def emote_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)  # List can be public

        emote_names = await db.get_emote_names(interaction.guild_id)
        if not emote_names:
            await send_error_followup(interaction, EmoteError.EMPTY_SERVER)
            return

        embeds = []
        max_characters_per_field = 1000
        prefix = "Emotes: "
        emote_list_str = ", ".join([f"`:{name}:`" for name in emote_names])  # Format names
        chunks = wrap(emote_list_str, width=max_characters_per_field,
                      break_long_words=False, break_on_hyphens=False, placeholder="...")

        current_embed = discord.Embed(color=EmbedColor.DEFAULT.value)
        current_embed.set_author(name=f"{interaction.guild.name} Emotes",
                                 icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        field_count = 0
        char_count = 0

        for i, chunk in enumerate(chunks):
            field_name = prefix if i == 0 else "\u200b"  # Use invisible char for subsequent field names
            field_value = chunk

            if field_count >= 25 or char_count + len(field_name) + len(field_value) > 5800:  # Leave headroom
                embeds.append(current_embed)
                current_embed = discord.Embed(color=EmbedColor.DEFAULT.value)
                field_count = 0
                char_count = 0

            current_embed.add_field(name=field_name, value=field_value, inline=False)
            field_count += 1
            char_count += len(field_name) + len(field_value)

        embeds.append(current_embed)  # Add the last embed

        token = await generate_token(interaction)
        server_id = interaction.guild_id
        url = f"https://bellbot.xyz/emote/{server_id}?token={token}"
        url_button = discord.ui.Button(style=discord.ButtonStyle.link, label="Visit Emote Gallery", url=url)
        view = discord.ui.View()
        view.add_item(url_button)

        await interaction.followup.send(embed=embeds[0], view=view)  # Send first embed with button
        if len(embeds) > 1:
            for embed in embeds[1:]:
                await interaction.channel.send(embed=embed)

    @emote.command(name="website", description="Get a secure link to view the server's emotes")
    async def emote_website(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # Link is user-specific
        token = await generate_token(interaction)
        server_id = interaction.guild_id
        url = f"https://bellbot.xyz/emote/{server_id}?token={token}"
        masked_url = f"[View Emote Gallery]({url})"  # Markdown link
        await interaction.followup.send(
            f"Here is your secure, temporary link to the gallery:\n{masked_url}",
            ephemeral=True
        )

    @emote.command(name="clear_cache", description="Manually clear the internal DB query cache")
    @commands.is_owner()
    async def emote_clear_cache(self, interaction: discord.Interaction):
        db.cache.clear()
        await interaction.followup.send("Internal database query cache cleared successfully.", ephemeral=True)

    @emote.command(name="clear_variants", description="Clear ALL cached variants for a specific emote")
    @app_commands.describe(name="The name of the original emote whose variants should be cleared")
    @commands.has_permissions(manage_messages=True)
    async def emote_clear_variants(self, interaction: discord.Interaction, name: str):
        original_emote = await db.get_emote(name, interaction.guild_id)
        if not original_emote:
            await send_error_followup(interaction, EmoteRemoveError.NOTFOUND_EMOTE_NAME)
            return

        variant_paths = await db.remove_variants_for_emote(original_emote.id)
        if not variant_paths:
            await interaction.followup.send(f"No cached variants found for `:{name}:`.", ephemeral=True)
            return

        failed_s3_deletions = 0
        for path in variant_paths:
            success, error = await db.remove_variant_from_bucket(path)
            if not success:
                failed_s3_deletions += 1
                print(f"Failed to delete variant '{path}' from S3 during clear: {error}")

        message = f"Successfully cleared {len(variant_paths)} cached variant(s) for `:{name}:`."
        if failed_s3_deletions > 0:
            message += f"\n⚠️ Failed to delete {failed_s3_deletions} file(s) from storage. Please check logs."
        await interaction.followup.send(message, ephemeral=True)

    @emote.command(name="clear_server_variants", description="Clear ALL cached variants for this entire server")
    @commands.has_permissions(manage_messages=True)
    async def emote_clear_server_variants(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        variant_paths = await db.remove_variants_for_guild(guild_id)

        if not variant_paths:
            await interaction.followup.send("No cached variants found for this server.", ephemeral=True)
            return

        failed_s3_deletions = 0
        total_variants = len(variant_paths)
        await interaction.followup.send(f"Found {total_variants} variants. Starting cleanup...", ephemeral=True)

        for i, path in enumerate(variant_paths):
            success, error = await db.remove_variant_from_bucket(path)
            if not success:
                failed_s3_deletions += 1
                print(f"Failed to delete variant '{path}' from S3 during server clear: {error}")

        message = f"Successfully cleared {total_variants - failed_s3_deletions}/{total_variants} cached variant(s) for this server."
        if failed_s3_deletions > 0:
            message += f"\n⚠️ Failed to delete {failed_s3_deletions} file(s) from storage. Please check logs."
        await interaction.edit_original_response(content=message)

    @emote.command(name="effect", description="Learn more about an effect")
    @app_commands.describe(effect_name="Name of the effect to get details about")
    async def effect_info(self, interaction: discord.Interaction, effect_name: str):
        effect_name_lower = effect_name.lower()
        effect_info = self.EFFECTS_LIST.get(effect_name_lower)

        if not effect_info:
            all_effect_names = list(self.EFFECTS_LIST.keys())
            matches = process.extractBests(
                effect_name_lower, all_effect_names,
                scorer=fuzz.ratio, score_cutoff=60, limit=3
            )
            suggestion = ""
            if matches:
                suggestions = [f"`{m[0]}`" for m in matches]
                suggestion = f" Did you mean: {', '.join(suggestions)}?"
            await interaction.followup.send(
                f"Effect '{effect_name}' not found.{suggestion}",
                ephemeral=True
            )
            return

        perm_key = effect_info.get("perm", "everyone")
        perm_func = self.PERMISSION_LIST.get(perm_key)
        allowed = False
        mock_message = interaction
        if perm_func:
            if perm_key == "owner":
                allowed = await self.bot.is_owner(interaction.user)
            else:
                try:
                    allowed = perm_func(mock_message, self)
                except Exception as e:
                    print(f"Permission check failed for {effect_name}: {e}. Defaulting to not allowed.")
                    allowed = False
        else:
            print(f"Warning: Unknown permission key '{perm_key}' for effect '{effect_name}'")
            allowed = False

        if not allowed:
            await interaction.followup.send(
                "You do not have permission to view details for this effect.",
                ephemeral=True
            )
            return

        effect_func = effect_info.get("func")
        raw_doc = effect_func.__doc__ or "No description available."
        doc_lines = raw_doc.strip().splitlines()

        user_doc = []
        capture = False
        indent = 0  # Keep track of indentation for clean output
        for line in doc_lines:
            line_strip = line.strip()
            if line_strip.startswith("User:"):
                capture = True
                continue
            elif capture and (line_strip.startswith("Parameters:") or
                              line_strip.startswith("Returns:") or
                              line_strip.startswith("Raises:") or
                              not line_strip):  # Stop on standard sections or empty line
                break
            elif capture:
                if not user_doc:  # First line determines base indentation
                    indent = len(line) - len(line.lstrip())
                    user_doc.append(line.lstrip())
                else:
                    user_doc.append(line[min(indent, len(line)):])  # Remove common indent

        description = "\n".join(user_doc).strip() or "No user documentation available for this effect."

        embed = discord.Embed(
            title=f"Effect: `{effect_name.lower()}`",
            description=description,
            colour=EmbedColor.DEFAULT.value
        )
        embed.set_author(
            name="Emote Effect Details",
            icon_url=interaction.client.user.display_avatar.url  # Bot's avatar
        )
        embed.add_field(name="Permission Required", value=perm_key.capitalize(), inline=True)
        embed.add_field(name="Can be used multiple times?", value=str(not effect_info.get("single_use", False)),
                        inline=True)
        embed.add_field(name="Requires Significant Processing?", value=str(effect_info.get("blocking", False)),
                        inline=True)
        await interaction.followup.send(embed=embed, ephemeral=False)  # Show publicly

    @effect_info.autocomplete("effect_name")
    async def effect_autocomplete(self, interaction: discord.Interaction, current: str):
        suggestions = []
        current_lower = current.lower()

        for name, data in self.EFFECTS_LIST.items():
            perm = data.get("perm", "everyone")
            allowed = False
            if perm == "owner":
                allowed = await self.bot.is_owner(interaction.user)
            elif perm == "mod":
                allowed = interaction.user.guild_permissions.manage_messages
            elif perm == "everyone":
                allowed = True

            if allowed and current_lower in name.lower():
                doc = data['func'].__doc__ or ""
                user_doc_first_sentence = ""
                in_user_section = False
                for line in doc.strip().splitlines():
                    line_strip = line.strip()
                    if line_strip.startswith("User:"):
                        in_user_section = True
                        continue
                    if in_user_section and line_strip:
                        sentence_end = -1
                        for end_char in ['.', '!', '?']:
                            found_pos = line_strip.find(end_char)
                            if found_pos != -1:
                                if sentence_end == -1 or found_pos < sentence_end:
                                    sentence_end = found_pos
                        if sentence_end != -1:
                            user_doc_first_sentence = line_strip[:sentence_end + 1]
                        else:
                            user_doc_first_sentence = line_strip
                        break  # Stop after finding the first line/sentence
                    elif in_user_section and not line_strip:  # Stop if empty line encountered
                        break

                emoji = ""
                for reaction_emoji, func in self.reaction_effects.items():
                    if func == data['func']:
                        emoji = f"{reaction_emoji} "  # Add space after emoji
                        break

                display_name = f"`{name}`"
                if emoji:
                    display_name += f" - {emoji}"
                if user_doc_first_sentence:
                    display_name += f" - {user_doc_first_sentence}"
                if len(display_name) > 100:  # Limit display name length
                    display_name = display_name[:97] + "..."
                suggestions.append(app_commands.Choice(name=display_name, value=name))
                if len(suggestions) >= 25:  # Autocomplete limit
                    break
        return suggestions

    # === April Fools Commands & Listener ===

    @emote.command(name="remove_a_strike", description="Remove a single strike from a user")
    @app_commands.describe(user="User to remove a strike from")
    @commands.guild_only()
    @commands.is_owner()
    async def remove_a_strike(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=False)
        new_count = await db.decrease_strike(user.id, interaction.guild.id)
        max_strikes = 3
        if new_count < max_strikes:
            channel_names = ["general-3-uwu", "general-3"]
            channel = discord.utils.find(lambda c: c.name in channel_names, interaction.guild.text_channels)
            if channel:
                try:
                    current_overwrite = channel.overwrites_for(user)
                    if not current_overwrite.is_empty() and current_overwrite.send_messages is False:
                        await channel.set_permissions(user, send_messages=None, reason="Strike removed, below maximum.")
                        print(f"Reset send_messages permission for {user.display_name} in {channel.name}")
                except discord.Forbidden:
                    print(f"Bot lacks permission to modify permissions for {user.display_name} in {channel.name}")
                    await interaction.followup.send("Note: I couldn't reset channel permissions (missing permissions).",
                                                    ephemeral=True)
                except Exception as e:
                    print(f"Error resetting permissions for {user.display_name} in {channel.name}: {e}")

        await interaction.followup.send(
            f"Aww, {user.mention}-chan had a stwike wemoved! ✨ UwU~ They now have {new_count}/{max_strikes} stwikes. 🐾",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @emote.command(name="forgive", description="Forgive all strikes for a user")
    @app_commands.describe(user="User to forgive strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def forgive_user(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=False)
        await db.reset_strikes(user.id, interaction.guild.id)
        channel_names = ["general-3-uwu", "general-3"]
        channel = discord.utils.find(lambda c: c.name in channel_names, interaction.guild.text_channels)
        if channel:
            try:
                current_overwrite = channel.overwrites_for(user)
                if not current_overwrite.is_empty():
                    await channel.set_permissions(user, overwrite=None, reason="Strikes forgiven by owner.")
                    print(f"Reset all permissions for {user.display_name} in {channel.name}")
            except discord.Forbidden:
                print(f"Bot lacks permission to modify permissions for {user.display_name} in {channel.name}")
                await interaction.followup.send("Note: I couldn't reset channel permissions (missing permissions).",
                                                ephemeral=True)
            except Exception as e:
                print(f"Error resetting permissions for {user.display_name} in {channel.name}: {e}")

        await interaction.followup.send(
            f"All of {user.mention}-chan's stwikes have been fuwgiven, nya~! ✨ UwU~",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @emote.command(name="view_strikes", description="View current strikes for a user")
    @app_commands.describe(user="User to check strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def view_strikes(self, interaction: discord.Interaction, user: discord.Member):
        strikes = await db.get_strikes(user.id, interaction.guild.id)
        max_strikes = 3
        await interaction.followup.send(
            f"{user.mention}-chan has {strikes}/{max_strikes} stwikes, nya~! Pwease be cawefuw! ⚠️",
            ephemeral=True
        )

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        # Ignore bots or DMs
        if message.author.bot or not message.guild:
            return

        # --- April Fools Logic ---
        april_fools_channels = ["general-3-uwu", "general-3"]
        if message.channel.name.lower() in april_fools_channels:
            is_owner_command = False
            if await self.bot.is_owner(message.author) and message.content.startswith(
                    tuple(await self.bot.get_prefix(message))):
                is_owner_command = True
            # Ignore owner commands and emote invocations
            if not is_owner_command and not is_enclosed_in_colon(message):
                await self.handle_april_fools(message)

        # --- Emote Pipeline Logic ---
        elif is_enclosed_in_colon(message):
            # Check permissions
            if not message.channel.permissions_for(message.guild.me).send_messages:
                print(f"Missing send_messages permission in {message.channel.name}")
                return
            if not message.channel.permissions_for(message.guild.me).attach_files:
                print(f"Missing attach_files permission in {message.channel.name}")
                try:
                    await message.channel.send("I need permission to attach files to send emotes! 😿")
                except discord.Forbidden:
                    pass
                return

            # Process
            typing_task = asyncio.create_task(message.channel.typing())
            try:
                await self.process_emote_pipeline(message)
            finally:
                typing_task.cancel()
            reset_flags()  # Reset cog state flags

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        # Ignore bot reactions or DMs
        if user.bot or not reaction.message.guild:
            return

        message = reaction.message
        image_attachment = None
        # Check message attachments for valid images/videos
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(f".{ext}") for ext in valid_formats):
                if attachment.size <= 52428800:  # Basic size check
                    image_attachment = attachment
                    break
        if image_attachment is None:
            return

        # Find matching effect based on emoji
        effect_func = None
        effect_name_for_sig = None
        effect_args_for_sig = []

        if str(reaction.emoji) == "↕️":  # Special case for vertical flip
            effect_func = effect.flip
            effect_name_for_sig = "flip"
            effect_args_for_sig = ["v"]
        else:
            effect_func = self.reaction_effects.get(str(reaction.emoji))
            if effect_func:
                # Find the effect name
                for name, data in self.EFFECTS_LIST.items():
                    if data['func'] == effect_func:
                        effect_name_for_sig = name
                        # Set default args for aliases if needed
                        if name == 'fast':
                            effect_args_for_sig = [2]
                        elif name == 'slow':
                            effect_args_for_sig = [0.5]
                        break

        if not effect_func or not effect_name_for_sig:
            return  # Emoji doesn't match a known effect

        # Process the reaction effect
        typing_task = asyncio.create_task(message.channel.typing())
        timer = PerformanceTimer()
        processed_emote = None

        try:
            async with timer:
                # Download attachment
                try:
                    image_bytes = await image_attachment.read()
                except Exception as e:
                    print(f"Error reading attachment data for reaction effect: {e}")
                    await message.channel.send(
                        f"Sorry {user.mention}, I couldn't read the attachment for that reaction.", delete_after=10)
                    return

                # Create temporary Emote object
                virtual_emote_id = 0
                base_filename = image_attachment.filename
                base_name_no_ext = base_filename.rsplit('.', 1)[0]
                original_file_type = get_file_type_from_path(base_filename)

                queued_effects = [(effect_name_for_sig, effect_args_for_sig)]
                effects_signature = generate_effects_signature(queued_effects)

                initial_emote = Emote(
                    id=virtual_emote_id,
                    file_path=f"reaction/{base_filename}",
                    author_id=user.id,  # User who reacted
                    timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                    original_url=image_attachment.url,
                    name=f"{base_name_no_ext}_{effects_signature}",
                    guild_id=message.guild.id,
                    usage_count=0,  # Not a tracked emote
                    img_data=image_bytes  # Start with downloaded data
                )

                # Execute pipeline for the single effect
                pipeline = await create_pipeline(self, message, initial_emote, queued_effects)
                processed_emote = await execute_pipeline(pipeline)

            # Send result or error
            if processed_emote and processed_emote.img_data and not processed_emote.errors:
                extra_args = calculate_extra_args(timer.elapsedTime, processed_emote, was_cached=False)
                final_file_type = get_file_type_from_path(processed_emote.file_path)
                final_filename = f"{base_name_no_ext}_{effects_signature}.{final_file_type}"

                file = discord.File(fp=io.BytesIO(processed_emote.img_data), filename=final_filename)
                content = f"{user.mention} applied `{effect_name_for_sig}` effect:"
                if extra_args:
                    content += "\n" + "\n".join(extra_args)
                await message.channel.send(content=content, file=file,
                                           allowed_mentions=discord.AllowedMentions(users=[user]))  # Mention reactor

            elif processed_emote and processed_emote.errors:
                error_msg = f"Sorry {user.mention}, couldn't apply the `{effect_name_for_sig}` effect. 😿"
                print(
                    f"Reaction effect error for {user.display_name} on {image_attachment.url}: {processed_emote.errors}")
                first_error_key = next(iter(processed_emote.errors))
                error_reason = processed_emote.errors[first_error_key].split('\n')[0]
                error_msg += f"\nReason: {error_reason}"[:150]
                await message.channel.send(error_msg, delete_after=15)
            else:
                await message.channel.send(f"Sorry {user.mention}, something went wrong applying the effect.",
                                           delete_after=10)

        finally:
            typing_task.cancel()
            reset_flags()  # Reset any global flags

    async def process_emote_pipeline(self, message: discord.Message):
        """Handles fetching, caching, processing, and sending emotes with effects."""
        timer = PerformanceTimer()
        processed_emote: Optional[Emote] = None
        was_cached = False
        final_emote_to_send: Optional[Emote] = None

        async with timer:
            emote_name, queued_effects = extract_emote_details(message)
            effects_signature = generate_effects_signature(queued_effects)

            # Get Base Emote Data
            original_emote = await get_emote_and_verify(emote_name, message.channel)
            if original_emote is None:
                return  # Error handled in verify function

            # --- Cache Check ---
            if effects_signature:  # Only check cache if effects were requested
                variant_info = await db.get_variant(original_emote.id, effects_signature)
                if variant_info:
                    # Cache Hit!
                    was_cached = True
                    variant_file_path = variant_info['file_path']
                    variant_file_type = variant_info['file_type']
                    variant_url = f"https://media.bellbot.xyz/emote/{variant_file_path}"  # Construct URL

                    try:
                        # Download the cached variant data
                        async with aiohttp.ClientSession() as session:
                            async with session.get(variant_url) as response:
                                response.raise_for_status()
                                variant_img_data = await response.read()

                        # Create an Emote object representing the cached variant
                        cached_emote_state = Emote(
                            id=original_emote.id,
                            file_path=variant_file_path,  # Path of the *variant*
                            author_id=original_emote.author_id,
                            timestamp=original_emote.timestamp,  # Or maybe variant creation time?
                            original_url=original_emote.original_url,
                            name=original_emote.name,
                            guild_id=original_emote.guild_id,
                            usage_count=original_emote.usage_count,  # Usage count is on original
                            img_data=variant_img_data,
                            effect_chain={ef[0]: True for ef in queued_effects}
                        )
                        cached_emote_state.notes["cached_variant"] = "True"
                        final_emote_to_send = cached_emote_state

                        # Set flags based on effects signature if needed
                        if "latency" in effects_signature: SlashCommands.latency_enabled = True
                        if "debug" in effects_signature: SlashCommands.debug_enabled = True
                        if "train" in effects_signature:
                            for ef_name, ef_args in queued_effects:
                                if ef_name == "train":
                                    try:
                                        amount = int(ef_args[0]) if ef_args else 3
                                        amount = min(max(amount, 1), 6)  # Clamp
                                        SlashCommands.train_count = amount
                                    except (ValueError, IndexError, TypeError):
                                        SlashCommands.train_count = 3
                                    break

                    except aiohttp.ClientError as e:
                        print(f"Cache Hit: Failed to download variant {variant_url}: {e}")
                        was_cached = False  # Treat as cache miss
                    except Exception as e:
                        print(f"Cache Hit: Unexpected error processing variant {variant_url}: {e}")
                        was_cached = False

            # --- Processing (Cache Miss or No Effects) ---
            if not final_emote_to_send:  # If not a cache hit (or no effects)
                was_cached = False
                # Initialize pipeline (fetches data in initialize step)
                pipeline = await create_pipeline(self, message, original_emote, queued_effects)
                processed_emote = await execute_pipeline(pipeline)
                final_emote_to_send = processed_emote

                # --- Save to Cache ---
                if effects_signature and final_emote_to_send and final_emote_to_send.img_data and not any(
                        err_key in final_emote_to_send.errors for err_key in
                        ["timeout", "pipeline_execution", "initialize"]):
                    # Check no critical errors occurred
                    is_critical_error = any(final_emote_to_send.errors.get(key) for key in final_emote_to_send.errors if
                                            key.endswith(('_executor', '_execution')))
                    if not is_critical_error:
                        variant_file_type = get_file_type_from_path(final_emote_to_send.file_path)
                        variant_filename = generate_variant_filename(original_emote.id, effects_signature,
                                                                     variant_file_type)
                        variant_s3_path = f"{original_emote.guild_id}/variants/{variant_filename}"

                        # Upload generated data
                        upload_success, upload_error = await db.upload_variant_to_bucket(
                            original_emote.guild_id,
                            variant_filename,
                            final_emote_to_send.img_data,
                            variant_file_type
                        )

                        if upload_success:
                            # Add record to DB
                            add_success = await db.add_variant(
                                original_emote.id,
                                original_emote.guild_id,
                                effects_signature,
                                variant_s3_path,  # Store the full S3 key
                                variant_file_type
                            )
                            if not add_success:
                                print(f"Failed to add variant record to DB for {variant_s3_path}")
                        else:
                            print(
                                f"Failed to upload variant to S3 for {original_emote.name} ({effects_signature}): {upload_error}")
                    else:
                        print(
                            f"Skipping variant cache save due to critical pipeline errors for {original_emote.name} ({effects_signature})")

            # Increment Usage Count (once per valid request)
            await db.increment_emote_usage(original_emote.id)

        # --- Send Emote ---
        if final_emote_to_send:
            if final_emote_to_send.img_data:
                extra_args = calculate_extra_args(timer.elapsedTime, final_emote_to_send, was_cached)
                await send_emote(message, final_emote_to_send, *extra_args)
            else:
                # Handle failure state where img_data is missing
                print(f"Error: Final emote state for {original_emote.name} has no image data.")
                init_error = final_emote_to_send.errors.get("initialize")
                if init_error:
                    error_msg = f"Failed to fetch original emote data: {init_error}"
                else:
                    error_msg = "Failed to process emote: No final image data."
                    if final_emote_to_send.errors:
                        first_err = next(iter(final_emote_to_send.errors.values()))
                        error_msg += f"\nDetails: {first_err.splitlines()[0]}"[:200]
                await send_error_embed(message, error_msg)
        else:
            print(f"Critical error: No final emote state available for {emote_name}")
            await send_error_embed(message, "A critical error occurred while processing the emote.")

    async def handle_april_fools(self, message: discord.Message):
        """Processes messages in designated channels for April Fools UwU rules."""
        content = message.clean_content
        guild_id = message.guild.id
        user_id = message.author.id
        max_strikes = 3

        image_url = None
        img_formats = ["png", "jpg", "jpeg", "gif", "webp"]
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in img_formats):
                if attachment.size < 20 * 1024 * 1024:  # Check size limit
                    image_url = attachment.url
                    break

        if not content and not image_url:
            return  # Skip messages with no content

        try:
            current_strikes = await db.get_strikes(user_id, guild_id)
            thinking_reaction_task = asyncio.create_task(message.add_reaction("🤔"))
            analysis = await analyze_uwu(content, image_url, current_strikes)

            try:
                await thinking_reaction_task
                await message.remove_reaction("🤔", message.guild.me)
            except (asyncio.CancelledError, discord.NotFound, discord.Forbidden):
                pass  # Ignore errors removing reaction

            if analysis.get("isUwU", False):
                await message.add_reaction("✅")
            else:
                await message.add_reaction("❌")
                await message.channel.typing()
                new_strike_count = await db.increment_strike(user_id, guild_id)
                reason = analysis.get("reason", "No weason pwovided... T_T")

                if new_strike_count >= max_strikes:
                    channel_names = ["general-3-uwu", "general-3"]
                    channel = discord.utils.find(lambda c: c.name in channel_names, message.guild.text_channels)
                    if channel:
                        try:
                            await channel.set_permissions(
                                message.author, send_messages=False,
                                reason=f"April Fools: Reached {max_strikes} strikes."
                            )
                        except discord.Forbidden:
                            print(
                                f"Bot lacks permission to revoke send_messages for {message.author.display_name} in {channel.name}")
                            await message.channel.send(
                                "⚠️ **Ewwooor:** I need permissions to manage channel access! Pwease fix! 🙏")
                        except Exception as e:
                            print(f"Error setting permissions for {message.author.display_name} in {channel.name}: {e}")

                    # await db.reset_strikes(user_id, guild_id) # Maybe don't reset immediately

                    first_lines = ["**Oopsie!**", "**ZOMG!!**", "**UwU, nuuu!**", "**Oh noes!**", "**Sowwy!**",
                                   "**Nyaa!**", "**Hewwo?**", "**Eep!**"]
                    first_line = random.choice(first_lines)
                    await message.reply(
                        f"{first_line} 🚨🚨🚨\n"
                        f"{message.author.mention}-chan, you've hit {new_strike_count}/{max_strikes} stwikes! No mowe posting fow you... 🚫 (✿◕︿◕)\n"
                        f"({reason})\n"  # Include reason for final strike
                        f"B-bettew wuck next time, nya~! ✨",
                        allowed_mentions=discord.AllowedMentions.none()  # Don't ping
                    )
                else:
                    alert_lines = ["**Non-UwU Alert!**", "**Oops, no UwU!**", "**Aw-aw missing!**",
                                   "**Nyoo! Not UwU!**", "**Alert! No UwU!**"]
                    alert_line = random.choice(alert_lines)
                    strikes_left = max_strikes - new_strike_count
                    await message.reply(
                        f"{alert_line} 🚨\n"
                        f"{reason}\n\n"
                        f"Stwike {new_strike_count}/{max_strikes} - "
                        f"You have {strikes_left} {'twies' if strikes_left > 1 else 'twie'} wemaining! ⚠️",
                        mention_author=True  # Ping user on warnings
                    )

        except Exception as e:
            print(f"Error processing April Fools message for {message.author.id}: {e}")
            try:
                await message.remove_reaction("🤔", message.guild.me)
            except:
                pass
            try:
                await message.add_reaction("⚠️")
            except:
                pass
            await message.reply(
                f"Ahhh! Sowwy {message.author.mention}-chan, I had an error checking your message! >_<\nPlease tell my owner! (Error: {type(e).__name__})")


def reset_flags():
    """Resets cog-level state flags after processing a message."""
    SlashCommands.latency_enabled = False
    SlashCommands.debug_enabled = False
    SlashCommands.train_count = 1


class PerformanceTimer:
    """Async context manager for timing operations."""

    def __init__(self):
        self.startTime = None
        self.endTime = None

    async def __aenter__(self):
        self.startTime = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.endTime = time.perf_counter()

    @property
    def elapsedTime(self) -> Optional[float]:
        """Returns the elapsed time in seconds, rounded."""
        if self.startTime and self.endTime:
            return round(self.endTime - self.startTime, 3)  # Use 3 decimal places for ms precision
        return None
