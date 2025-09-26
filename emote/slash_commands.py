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
import base64
import os
import re
import time
from textwrap import wrap

import cv2
import discord
from discord import app_commands
from fuzzywuzzy import fuzz, process
from redbot.core import commands
# from discord.app_commands import Choice, commands
# from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from .utils import effects as effect
from .utils.chat import send_help_embed, send_error_embed, send_embed_followup, send_error_followup, send_emote, \
    generate_token
from .utils.database import Database
from .utils.enums import EmoteAddError, EmoteRemoveError, EmoteError, EmbedColor
from .utils.format import is_enclosed_in_colon, extract_emote_details
from .utils.pipeline import create_pipeline, execute_pipeline
from .utils.url import is_url_reachable, blacklisted_url, is_media_format_valid, is_media_size_valid, alphanumeric_name

# Channel constants
PISSCORD_CHANNEL_ID = 1412970503475429477  # gen-free channel
DEBUG_CHANNEL_ID = 1355981630484774932  # debug output channel
CREATOR_NOVEMBER_USER_ID = "138148168360656896"
BITTER_USER_ID = "401924420471619584"  # bitter - check for code image matches


def get_violation_message(channel_id: int, violation_type: str, user_mention: str) -> str:
    """Generate the appropriate violation message based on channel and violation type."""
    if channel_id == PISSCORD_CHANNEL_ID:
        if violation_type == "images":
            return f"No images allowed in gen-free, {user_mention}!!!"
        elif violation_type == "emojis":
            return f"No emojis allowed in gen-free, {user_mention}!!!"
        elif violation_type == "reactions":
            return f"No reactions allowed in gen-free, {user_mention}!!!"
    else:
        if violation_type == "images":
            return f"Images are not allowed in this channel, {user_mention} 🚫"
        elif violation_type == "emojis":
            return f"Emojis are not allowed in this channel, {user_mention}!"
        elif violation_type == "reactions":
            return f"Reactions are not allowed in this channel, {user_mention}!"

    return f"Content not allowed in this channel, {user_mention}!"


async def debug_output(message: discord.Message, debug_text: str):
    """
    Send debug output to debug channel if message is in DEBUG_CHANNEL_ID, otherwise print to console.
    """
    if message.channel.id == DEBUG_CHANNEL_ID:
        try:
            await message.channel.send(f"🐛 **DEBUG:** {debug_text}")
        except Exception as e:
            # Fallback to console if sending to channel fails
            print(f"Failed to send debug to channel: {e}")
            print(debug_text)
    else:
        print(debug_text)


def check_filename_contains_cash_app(filename: str) -> bool:
    """
    Check if the filename contains "Cash_App" (case-insensitive).
    Returns True if "Cash_App" is found in the filename, False otherwise.
    """
    return "cash_app" in filename.lower()


async def send_bitter_match_info(bot, match_count: int, threshold: int, attachment: discord.Attachment,
                                 user_mention: str, filename_check: bool = False):
    """Send bitter match information and original image to the debug channel."""
    try:
        # Get the debug channel
        debug_channel = bot.get_channel(DEBUG_CHANNEL_ID)
        if debug_channel is None:
            print(f"Debug channel {DEBUG_CHANNEL_ID} not found")
            return

        # Create the match info message
        if match_count > threshold or filename_check:
            status = "DELETED"
            emoji = "🚨"
        else:
            status = "ALLOWED"
            emoji = "✅"

        info_text = f"{emoji} **Bitter Image Check Result**\n"
        info_text += f"User: {user_mention}\n"
        info_text += f"Filename contains 'Cash_App': {filename_check}\n"
        info_text += f"Image matches: {match_count}\n"
        info_text += f"Image threshold: {threshold}\n"
        info_text += f"Status: {status}\n"
        info_text += f"Original filename: {attachment.filename}"

        # Send the info message
        await debug_channel.send(info_text)

        # Send the original image
        try:
            # Re-read the attachment to send it
            image_bytes = await attachment.read()
            import io
            image_buffer = io.BytesIO(image_bytes)
            file = discord.File(fp=image_buffer, filename=f"bitter_check_{attachment.filename}")
            await debug_channel.send(file=file)
        except Exception as e:
            await debug_channel.send(f"⚠️ Could not attach original image: {e}")

    except Exception as e:
        print(f"Failed to send bitter match info to debug channel: {e}")


async def check_image_matches_code(attachment_bytes: bytes) -> int:
    """
    Check if an image attachment matches the code.png template using ORB feature matching.
    Converts all images to PNG format before comparison to eliminate file type matching errors.
    Returns the number of matches found, or 0 if no match or error.
    """
    import tempfile
    import uuid
    import numpy as np

    temp_candidate_path = None
    try:
        # Path to template image - use absolute path based on current file location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, 'res', 'code.png')

        if not os.path.exists(template_path):
            print(f"Template image not found: {template_path}")
            return 0

        # Load template image
        template_img = cv2.imread(template_path, 0)
        if template_img is None:
            print("Could not load template image")
            return 0

        # Convert attachment bytes to OpenCV image format
        print("Converting attachment bytes to image format...")
        np_array = np.frombuffer(attachment_bytes, np.uint8)
        candidate_img_color = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        
        if candidate_img_color is None:
            print("Could not decode candidate image from bytes")
            return 0
            
        print(f"Successfully decoded image with shape: {candidate_img_color.shape}")
        
        # Convert to PNG format and save to temporary file for consistent processing
        temp_dir = tempfile.gettempdir()
        temp_candidate_path = os.path.join(temp_dir, f"candidate_{uuid.uuid4().hex}.png")
        
        # Encode as PNG and save to ensure consistent format
        success, png_encoded = cv2.imencode('.png', candidate_img_color)
        if not success:
            print("Could not encode candidate image to PNG format")
            return 0
            
        print("Successfully converted image to PNG format")
        
        with open(temp_candidate_path, 'wb') as temp_file:
            temp_file.write(png_encoded.tobytes())

        # Load candidate image from PNG file in grayscale for matching
        candidate_img = cv2.imread(temp_candidate_path, cv2.IMREAD_GRAYSCALE)
        if candidate_img is None:
            print("Could not load converted PNG candidate image from temporary file")
            return 0

        # ORB detector
        orb = cv2.ORB_create(1000)

        # Find keypoints and descriptors
        k1, d1 = orb.detectAndCompute(template_img, None)
        k2, d2 = orb.detectAndCompute(candidate_img, None)

        if d1 is None or d2 is None or len(k1) == 0 or len(k2) == 0:
            print("No features detected in one or both images")
            return 0

        # Brute Force Matcher
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(d1, d2)
        matches = sorted(matches, key=lambda x: x.distance)

        match_count = len(matches)
        print(f"Image matching result: {match_count} matches found")

        return match_count

    except Exception as e:
        print(f"Error in check_image_matches_code: {e}")
        return 0
    finally:
        # Clean up temporary file
        if temp_candidate_path and os.path.exists(temp_candidate_path):
            try:
                os.remove(temp_candidate_path)
                print(f"Cleaned up temporary file: {temp_candidate_path}")
            except Exception as cleanup_error:
                print(f"Warning: Could not clean up temporary file {temp_candidate_path}: {cleanup_error}")


def contains_emoji(text: str) -> bool:
    """Check if the text contains any emojis (Unicode emojis, Discord custom emojis, or emoji shortcodes)."""
    # Unicode emoji pattern - covers most standard emojis
    unicode_emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F7E0-\U0001F7EB"  # geometric shapes
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
        "]+",
        flags=re.UNICODE
    )

    # Discord custom emoji pattern <:name:id> or <a:name:id> for animated
    discord_emoji_pattern = re.compile(r'<a?:\w+:\d+>')

    # Emoji shortcode pattern :name: (like :green_circle:, :thinking:, etc.)
    emoji_shortcode_pattern = re.compile(r':[a-zA-Z0-9_+-]+:')

    return bool(unicode_emoji_pattern.search(text)) or bool(discord_emoji_pattern.search(text)) or bool(
        emoji_shortcode_pattern.search(text))


_ = Translator("Emote", __file__)

valid_formats = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
db = Database()


def calculate_extra_args(time_elapsed, emote) -> list:
    extra_args = []
    if SlashCommands.latency_enabled:
        extra_args.append(f"Your request was processed in `{time_elapsed}` seconds!")
    # if SlashCommands.debug_enabled:
    #     if SlashCommands.was_cached:
    #         extra_args.append(f"The emote `{emote.name}` was found in cache.")
    #     else:
    #         extra_args.append(f"The emote `{emote.name}` was not found in cache.")
    # Append emote.notes if it exists (i.e. not None)
    # if emote.notes:
    #     extra_args.append(emote.notes)
    return extra_args


def encode_image(image_data):
    """Encodes image bytes as base64 string"""
    return base64.b64encode(image_data).decode('utf-8')


async def get_emote_and_verify(emote_name_str: str, channel):
    emote = await db.get_emote(emote_name_str, channel.guild.id, True)
    if emote is None:
        valid_names = await db.get_emote_names(channel.guild.id)

        matches = process.extractBests(
            emote_name_str,
            valid_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=70
        )

        if matches:
            best_match = matches[0][0]
            await channel.send(f"Emote '{emote_name_str}' not found. Did you mean '{best_match}'?")
        else:
            await channel.send(f"Emote '{emote_name_str}' not found.")

    return emote


def get_cache_info(return_as_boolean=False):
    """
    Returns cache information based on the specified argument.

    If `return_as_boolean` is True, returns a boolean indicating whether the cache contains any items.
    Otherwise, returns the current cache state and emote usage collection as a formatted string.
    """
    cache_state = db.cache
    emote_usage_collection = db.emote_usage_collection

    # If return_as_boolean is True, return a boolean based on whether the cache has any items
    if return_as_boolean:
        return bool(cache_state)  # True if cache contains items, False otherwise

    # Otherwise, format cache information as a string
    return f"{str(cache_state)}\n{str(emote_usage_collection)}"


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
        "shake": {'func': effect.shake, 'perm': 'everyone', 'single_use': True, 'blocking': True},
        "explode": {'func': effect.explode, 'perm': 'everyone', 'single_use': True, 'blocking': True},
        "rainbow": {'func': effect.rainbow, 'perm': 'everyone', 'single_use': True, 'blocking': True},
        "spin": {'func': effect.spin, 'perm': 'everyone', 'single_use': True, 'blocking': True}
    }
    reaction_effects = {
        "🔄": effect.reverse,
        "⏩": effect.fast,
        "🐢": effect.slow,
        "⚡": effect.speed,
        "🔀": effect.invert,
        "🫨": effect.shake,
        "🔃": effect.flip,
        "🌈": effect.rainbow,
        "💣": effect.explode,
    }

    latency_enabled = False
    was_cached = False
    debug_enabled = False
    train_count = 1

    @emote.command(name="add", description="Add an emote to the server")
    @app_commands.describe(name="The name of the new emote", url="The URL of a supported file type to add as an emote")
    async def emote_add(self, interaction: discord.Interaction, name: str, url: str):
        # Can only be used by users with the "Manage Messages" permission
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        await send_help_embed(
            interaction, "Adding emote...",
            "Please wait while the emote is being added to the server."
        )

        rules = [
            (lambda: alphanumeric_name(name), EmoteAddError.INVALID_NAME_CHAR),
            (lambda: len(name) <= 32, EmoteAddError.EXCEED_NAME_LEN),
            (lambda: is_url_reachable(url), EmoteAddError.UNREACHABLE_URL),
            (lambda: not blacklisted_url(url), EmoteAddError.BLACKLISTED_URL),
            (lambda: is_media_format_valid(url, valid_formats), EmoteAddError.INVALID_FILE_FORMAT),
            (lambda: is_media_size_valid(url, 52428800), EmoteAddError.EXCEED_FILE_SIZE),
        ]

        for condition, error in rules:
            if not condition():
                await send_error_followup(interaction, error)
                return

        # TODO: move this function to @SlashCommands and make seperate function that we can call
        if await db.check_emote_exists(name, interaction.guild_id):
            await send_error_followup(interaction, EmoteAddError.DUPLICATE_EMOTE_NAME)
            return

        # Upload to bucket
        file_type = str(is_media_format_valid(url, valid_formats)[1])
        success, error = await db.add_emote_to_database(interaction, name, url, file_type)

        if not success:
            await send_error_followup(interaction, error)
            return

        await send_embed_followup(
            interaction, "Success!", f"Added **{name}** as an emote."
        )

    @emote.command(name="remove", description="Remove an emote from the server")
    @app_commands.describe(name="The name of the emote to remove")
    async def emote_remove(self, interaction: discord.Interaction, name: str):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        await send_help_embed(
            interaction, "Removing emote...",
            "Please wait while the emote is being removed from the server."
        )

        if not await db.check_emote_exists(name, interaction.guild_id):
            await send_error_followup(interaction, EmoteRemoveError.NOTFOUND_EMOTE_NAME)
            return

        # Remove emote from db
        success, error = await db.remove_emote_from_database(interaction, name)

        if not success:
            await send_error_followup(interaction, error)
            return

        await send_embed_followup(
            interaction, "Success!", f"Removed **{name}** as an emote."
        )

    @emote.command(name="list", description="List all emotes in the server")
    async def emote_list(self, interaction: discord.Interaction):
        emote_names = await db.get_emote_names(interaction.guild_id)
        if not emote_names:
            await send_error_embed(interaction, EmoteError.EMPTY_SERVER)
            return

        embeds = []
        max_characters = 1000 - len("Emotes: ")
        embed = discord.Embed(color=EmbedColor.DEFAULT.value)

        field_count = 0
        emote_list_str = ", ".join(emote_names)
        chunks = wrap(emote_list_str, width=max_characters, break_long_words=False, break_on_hyphens=False)

        for i, chunk in enumerate(chunks):
            embed.add_field(name="Emotes:" if i == 0 else "\u200b", value=chunk, inline=False)
            field_count += 1

        embed.set_author(name=f"{interaction.guild.name}", icon_url=interaction.guild.icon.url)
        embeds.append(embed)

        token = await generate_token(interaction)
        server_id = interaction.guild_id

        url = f"https://bellbot.xyz/emote/{server_id}?token={token}"
        url_button = discord.ui.Button(style=discord.ButtonStyle.link, label="Visit emote gallery",
                                       url=f"{url}")

        view = discord.ui.View()
        view.add_item(url_button)

        for i, embed in enumerate(embeds):
            ephemeral = False if field_count <= 3 else True
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral, view=view)

    @emote.command(name="website", description="Get a secure link to view the server's emotes")
    async def emote_website(self, interaction: discord.Interaction):
        token = await generate_token(interaction)
        server_id = interaction.guild_id

        url = f"https://bellbot.xyz/emote/{server_id}?token={token}"
        masked_url = f"[bellbot.xyz/emote/{server_id}]({url})"

        embed = discord.Embed(
            title=f"Emote Gallery - {interaction.guild.name}",
            description=f"Here is your link:\n{masked_url}",
            color=EmbedColor.DEFAULT.value
        )
        embed.set_footer(text="For privacy purposes, this link is only valid for 24 hours.")

        await interaction.response.send_message(embed=embed)

    @emote.command(name="clear_cache", description="Manually clear the cache")
    @commands.is_owner()
    async def emote_clear_cache(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        db.cache.clear()
        await interaction.response.send_message("Cache cleared successfully.")

    @emote.command(name="toggle",
                   description="Enable or disable emotes for a specific channel, optionally also configure emojis")
    @app_commands.describe(channel="The channel to configure emotes for",
                           enabled="True to enable emotes, False to disable emotes",
                           enable_emojis="True to enable emojis, False to disable emojis, None to leave unchanged")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def emote_toggle(self, interaction: discord.Interaction, channel: discord.TextChannel,
                           enabled: bool, enable_emojis: bool = None):
        """Enable or disable emotes for a specific channel"""
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        emotes_cog = self.bot.get_cog("Emotes")

        # Handle emote blacklisting based on enabled parameter
        async with emotes_cog.config.guild(interaction.guild).blacklisted_channels() as blacklisted_channels:
            if enabled:
                # Enable emotes - remove from blacklist if present
                if channel.id in blacklisted_channels:
                    blacklisted_channels.remove(channel.id)
            else:
                # Disable emotes - add to blacklist if not present
                if channel.id not in blacklisted_channels:
                    blacklisted_channels.append(channel.id)

        # Handle emoji blacklisting if requested
        async with emotes_cog.config.guild(
                interaction.guild).emoji_blacklisted_channels() as emoji_blacklisted_channels:
            if enable_emojis is not None:
                if enable_emojis:
                    # Enable emojis - remove from blacklist if present
                    if channel.id in emoji_blacklisted_channels:
                        emoji_blacklisted_channels.remove(channel.id)
                    if enabled:
                        await interaction.response.send_message(
                            f"Emotes and emojis have been enabled in {channel.mention}!", ephemeral=False)
                    else:
                        await interaction.response.send_message(
                            f"Emotes have been disabled but emojis have been enabled in {channel.mention}!",
                            ephemeral=False)
                else:
                    # Disable emojis - add to blacklist if not present
                    if channel.id not in emoji_blacklisted_channels:
                        emoji_blacklisted_channels.append(channel.id)
                    if not enabled:
                        await interaction.response.send_message(
                            f"Emotes and emojis have been disabled in {channel.mention}!", ephemeral=False)
                    else:
                        await interaction.response.send_message(
                            f"Emotes have been enabled but emojis have been disabled in {channel.mention}!",
                            ephemeral=False)
            else:
                # Only handle emotes, but remove emoji blacklist entry when enabling emotes
                if enabled:
                    # Also remove from emoji blacklist when enabling emotes to keep lists synchronized
                    if channel.id in emoji_blacklisted_channels:
                        emoji_blacklisted_channels.remove(channel.id)
                    await interaction.response.send_message(f"Emotes have been enabled in {channel.mention} ✅",
                                                            ephemeral=False)
                else:
                    await interaction.response.send_message(f"Emotes have been disabled in {channel.mention} 🚫",
                                                            ephemeral=False)

    @emote.command(name="effect", description="Learn more about an effect")
    @app_commands.describe(effect_name="Name of the effect to get details about")
    async def effect(self, interaction: discord.Interaction, effect_name: str):
        # Retrieve effect information from EFFECTS_LIST
        effect_info = self.EFFECTS_LIST.get(effect_name.lower())
        if not effect_info:
            await interaction.response.send_message(f"Effect '{effect_name}' not found.", ephemeral=True)
            return

        # Check user's permission for the effect
        perm = effect_info.get("perm", "everyone")
        allowed = False
        if perm == "owner":
            allowed = await self.bot.is_owner(interaction.user)
        elif perm == "mod":
            allowed = interaction.user.guild_permissions.manage_messages
        elif perm == "everyone":
            allowed = True

        if not allowed:
            await interaction.response.send_message(
                "You do not have permission to view details for this effect.",
                ephemeral=True
            )
            return

        # Retrieve and filter the docstring from the effect function
        effect_func = effect_info.get("func")
        raw_doc = effect_func.__doc__ or "No description available."
        doc_lines = raw_doc.splitlines()

        # Extract only the user documentation section
        user_doc = []
        capture = False
        for line in doc_lines:
            if line.strip().startswith("User:"):
                capture = True
                continue
            elif capture and (line.strip().startswith("Parameters:") or
                              line.strip().startswith("Returns:") or
                              line.strip().startswith("Raises:")):
                break
            elif capture:
                user_doc.append(line)

        description = "\n".join(user_doc).strip() or "No user documentation available."

        embed = discord.Embed(
            title=f"Effect: {effect_name.capitalize()}",
            description=description,
            colour=EmbedColor.DEFAULT.value
        )
        embed.set_author(
            name="Emote Effects",
            icon_url=interaction.client.user.display_avatar.url
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @effect.autocomplete("effect_name")
    async def effect_autocomplete(self, interaction: discord.Interaction, current: str):
        suggestions = []
        for name, data in self.EFFECTS_LIST.items():
            perm = data.get("perm", "everyone")
            allowed = False
            if perm == "owner":
                allowed = await self.bot.is_owner(interaction.user)
            elif perm == "mod":
                allowed = interaction.user.guild_permissions.manage_messages
            elif perm == "everyone":
                allowed = True

            if allowed and current.lower() in name.lower():
                # Extract first sentence of user documentation
                doc = data['func'].__doc__ or ""
                doc_lines = doc.splitlines()
                user_doc = ""
                for line in doc_lines:
                    if line.strip().startswith("User:"):
                        next_line = doc_lines[doc_lines.index(line) + 1].strip()
                        user_doc = next_line.split('.')[0]
                        break

                emoji = ""
                for emote, func in self.reaction_effects.items():
                    if func == data['func']:
                        emoji = emote
                        break

                if emoji:
                    display_name = f"{name} - {emoji} - {user_doc}" if user_doc else f"{name} - {emoji}"
                else:
                    display_name = f"{name} - {user_doc}" if user_doc else name

                suggestions.append(app_commands.Choice(name=display_name, value=name))
        return suggestions

    @emote.command(name="info", description="Display detailed information about an emote")
    @app_commands.describe(name="The name of the emote to get information about")
    async def emote_info(self, interaction: discord.Interaction, name: str):
        emote = await db.get_emote(name, interaction.guild_id, False)

        if emote is None:
            await send_error_embed(interaction, EmoteRemoveError.NOTFOUND_EMOTE_NAME)
            return

        # Format timestamp
        timestamp_formatted = emote.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Get author information
        try:
            author = await self.bot.fetch_user(emote.author_id)
            author_name = f"{author.display_name} ({author.name})"
        except:
            author_name = f"Unknown User (ID: {emote.author_id})"

        embed = discord.Embed(
            title=f"Emote Info: {emote.name}",
            color=EmbedColor.DEFAULT.value
        )

        # Add emote image if available
        emote_url = f"https://media.bellbot.xyz/emote/{emote.file_path}"
        embed.set_thumbnail(url=emote_url)

        embed.add_field(name="Author", value=author_name, inline=True)
        embed.add_field(name="Created", value=timestamp_formatted, inline=True)
        embed.add_field(name="Usage Count", value=str(emote.usage_count), inline=True)
        embed.add_field(name="File Path", value=emote.file_path, inline=False)
        embed.add_field(name="Original URL", value=emote.original_url if emote.original_url else "N/A", inline=False)

        if emote.errors:
            error_text = "\n".join([f"**{k}**: {v}" for k, v in emote.errors.items()])
            embed.add_field(name="Errors", value=error_text, inline=False)

        if emote.notes:
            notes_text = "\n".join([f"**{k}**: {v}" for k, v in emote.notes.items()])
            embed.add_field(name="Notes", value=notes_text, inline=False)

        embed.set_footer(text=f"Guild ID: {emote.guild_id} | Emote ID: {emote.id}")

        await interaction.response.send_message(embed=embed)

    @emote.command(name="top", description="Display the most used emotes in this server")
    @app_commands.describe(limit="Number of top emotes to display (default: 10, max: 25)")
    async def emote_top(self, interaction: discord.Interaction, limit: int = 10):
        # Validate limit
        if limit < 1:
            limit = 10
        elif limit > 25:
            limit = 25

        top_emotes = await db.get_top_emotes_by_usage(interaction.guild_id, limit)

        if not top_emotes:
            await send_error_embed(interaction, EmoteError.EMPTY_SERVER)
            return

        embed = discord.Embed(
            title=f"🏆 Top {len(top_emotes)} Most Used Emotes",
            color=EmbedColor.DEFAULT.value
        )
        embed.set_author(name=f"{interaction.guild.name}",
                         icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        description_lines = []
        medals = ["🥇", "🥈", "🥉"]

        for i, (emote_name, usage_count, author_id) in enumerate(top_emotes, 1):
            # Get medal or number
            if i <= 3:
                position = medals[i - 1]
            else:
                position = f"**{i}.**"

            # Try to get author name
            try:
                author = await self.bot.fetch_user(author_id)
                author_display = author.display_name
            except:
                author_display = f"Unknown User"

            # Format the line
            usage_text = "use" if usage_count == 1 else "uses"
            line = f"{position} **{emote_name}** - {usage_count} {usage_text} (by {author_display})"
            description_lines.append(line)

        embed.description = "\n".join(description_lines)
        embed.set_footer(text=f"Showing top {len(top_emotes)} emotes out of all server emotes")

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Skip processing if channel is blacklisted
        if message.guild:
            emotes_cog = self.bot.get_cog("Emotes")
            blacklisted_channels = await emotes_cog.config.guild(message.guild).blacklisted_channels()
            emoji_blacklisted_channels = await emotes_cog.config.guild(message.guild).emoji_blacklisted_channels()

            await debug_output(message, f"Is blacklisted: {message.channel.id in blacklisted_channels}")
            await debug_output(message, f"Is emoji blacklisted: {message.channel.id in emoji_blacklisted_channels}")

            # Check for emote blacklisting
            if message.channel.id in blacklisted_channels and is_enclosed_in_colon(message):
                violation_msg = get_violation_message(message.channel.id, "images", message.author.mention)
                await message.channel.send(violation_msg)

                await debug_output(message, "Contained emote")
                return

            # Check for emoji blacklisting
            if message.channel.id in emoji_blacklisted_channels:
                # Special check for Creator November user with attachments
                if str(message.author.id) == CREATOR_NOVEMBER_USER_ID and message.attachments:
                    await message.delete()
                    violation_msg = get_violation_message(message.channel.id, "images", message.author.mention)
                    await message.channel.send(violation_msg)

                    await debug_output(message, "Contained November image attachments")
                    return

            # Special check for bitter user with image attachments (check filename and code.png matches)
            if (str(message.author.id) == BITTER_USER_ID or str(
                    message.author.id) == CREATOR_NOVEMBER_USER_ID) and message.attachments:
                for attachment in message.attachments:
                    # Check if attachment is an image
                    if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        try:
                            # First check if filename contains "Cash_App" (faster check)
                            filename_has_cash_app = check_filename_contains_cash_app(attachment.filename)
                            
                            if filename_has_cash_app:
                                # Send debug info with filename check result
                                await send_bitter_match_info(self.bot, 0, 240, attachment,
                                                             message.author.mention, filename_check=True)
                                
                                # Delete the message and send reply immediately
                                await message.delete()
                                reply_msg = f"No bitter cashapp codes allowed, {message.author.mention}!!!"
                                await message.channel.send(reply_msg)
                                return
                            
                            # If filename check passes, do the more expensive image matching
                            # Read attachment bytes
                            image_bytes = await attachment.read()

                            # Check for image matches
                            match_count = await check_image_matches_code(image_bytes)
                            threshold = 240

                            # Always send match info to debug channel
                            await send_bitter_match_info(self.bot, match_count, threshold, attachment,
                                                         message.author.mention, filename_check=filename_has_cash_app)

                            if match_count > threshold:
                                # Delete the message and send reply
                                await message.delete()
                                reply_msg = f"No bitter cashapp codes allowed, {message.author.mention}!!!"
                                await message.channel.send(reply_msg)
                                return

                        except Exception as e:
                            # Send error info to debug channel as well
                            try:
                                debug_channel = self.bot.get_channel(DEBUG_CHANNEL_ID)
                                if debug_channel:
                                    await debug_channel.send(
                                        f"⚠️ **Error processing bitter's attachment:** {e}\nUser: {message.author.mention}\nFilename: {attachment.filename}")
                            except:
                                pass
                            await debug_output(message, f"Error processing bitter's attachment: {e}")
                        break  # Only check first image attachment

            # Check for emoji blacklisting
            if message.channel.id in emoji_blacklisted_channels:
                if contains_emoji(message.content):
                    await message.delete()
                    violation_msg = get_violation_message(message.channel.id, "emojis", message.author.mention)
                    await message.channel.send(violation_msg)

                    await debug_output(message, "Contained emoji")
                    return

                await debug_output(message, f"Message content: {message.content}")
                await debug_output(message, "Did nothing")

        if is_enclosed_in_colon(message):
            async with message.channel.typing():
                await self.process_emote_pipeline(message)

            reset_flags()

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_reaction_add(self, reaction: discord.Reaction, user):
        if reaction.me:
            return

        if user.bot:
            return

        # Check for emoji blacklisting in reactions
        message = reaction.message
        if message.guild:
            emotes_cog = self.bot.get_cog("Emotes")
            emoji_blacklisted_channels = await emotes_cog.config.guild(message.guild).emoji_blacklisted_channels()

            if message.channel.id in emoji_blacklisted_channels:
                await reaction.remove(user)
                violation_msg = get_violation_message(message.channel.id, "reactions", user.mention)
                await message.channel.send(violation_msg)
                return
        image_attachment = None
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4')):
                image_attachment = attachment
                break

        if image_attachment is None:
            return

        effect_func = self.reaction_effects.get(str(reaction.emoji))
        if not effect_func:
            return

        import io
        from emote.utils.effects import Emote
        from datetime import datetime

        try:
            image_bytes = await image_attachment.read()
        except Exception as e:
            await debug_output(message, f"Error reading image data: {e}")
            return

        await message.channel.typing()

        emote_instance = Emote(
            id=0,  # Use a dummy id since this is a virtual Emote
            file_path=f"virtual/{image_attachment.filename}",  # Use real file name and type
            author_id=user.id,
            timestamp=datetime.now(),
            original_url=image_attachment.url,
            name=image_attachment.filename,
            guild_id=message.guild.id if message.guild else 0,
            usage_count=0,
            errors={},
            issues={},
            notes={},
            followup={},
            effect_chain={},
            img_data=image_bytes,
        )

        emote = effect_func(emote_instance)

        if emote.img_data:
            image_buffer = io.BytesIO(emote.img_data)
            filename = emote.file_path.split("/")[-1] if emote.file_path else "emote.png"
            file = discord.File(fp=image_buffer, filename=filename)
            # await message.channel.send(content="", file=file)
            await message.reply(content="", file=file, mention_author=False)

    async def process_emote_pipeline(self, message):
        timer = PerformanceTimer()
        async with timer:
            emote_name, queued_effects = extract_emote_details(message)
            emote = await get_emote_and_verify(emote_name, message.channel)

            if emote is None:
                return

            pipeline = await create_pipeline(self, message, emote, queued_effects)
            emote = await execute_pipeline(pipeline)

        # Get elapsed time after timer has stopped
        extra_args = calculate_extra_args(timer.elapsedTime, emote)
        await send_emote(message, emote, *extra_args)


def reset_flags():
    SlashCommands.latency_enabled = False
    SlashCommands.was_cached = False
    SlashCommands.debug_enabled = False
    SlashCommands.train_count = 1


class PerformanceTimer:
    def __init__(self):
        self.startTime = None
        self.endTime = None

    async def __aenter__(self):
        self.startTime = time.perf_counter()

    async def __aexit__(self, exec_type, exec_val, exec_tb):
        self.endTime = time.perf_counter()

    @property
    def elapsedTime(self):
        return round(self.endTime - self.startTime, 2) if self.endTime else None
