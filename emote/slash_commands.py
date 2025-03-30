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
import json
import os
import random
import time
from textwrap import wrap

import discord
from anyio import sleep
from discord import app_commands
from fuzzywuzzy import fuzz, process
from openai import OpenAI
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


async def analyze_uwu(content=None, image_url=None):
    """Analyzes text/image for UwU-style content using OpenAI"""
    client = OpenAI(
        api_key=os.getenv('OPENAI_KEY'),
    )

    messages = [{
        "role": "system",
        "content": "Analyze for *any* ( UwU-style elements (cute text, emoticons, playful misspellings). "
                   "Messages don't necessarily have to be 'happy', they can be angry, mean, etc as long as they follow the other rules. "
                   "Examples: 'i fwucking hate dis server', 'wat da hell...'. "
                   "Write your reason in uWu speak in 1-2 sentences. "
                   "Try to avoid reiterating the rules verbatim. Do not say 'uwu-style' or anything similar. "
                   "Respond with JSON: {\"isUwU\": bool, \"reason\": str}"
    }]

    if content:
        messages.append({
            "role": "user",
            "content": f"Message: {content}\nIs this UwU-style? Respond with JSON."
        })

    if image_url:
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Analyze this image for UwU-style text/content"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "auto"
                    },
                }
            ]
        })

    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=messages,
        max_tokens=300
    )

    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"isUwU": False, "reason": "Invalid response from API"}


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
        "latency": {'func': effect.latency, 'perm': 'mod', 'single_use': True},
        "flip": {'func': effect.flip, 'perm': 'everyone'},
        "debug": {'func': effect.debug, 'perm': 'everyone', 'single_use': True},
        "train": {'func': effect.train, 'perm': 'everyone', 'single_use': True},
        "reverse": {'func': effect.reverse, 'perm': 'everyone', 'single_use': True},
        "invert": {'func': effect.invert, 'perm': 'everyone'},
        "speed": {'func': effect.speed, 'perm': 'everyone', 'single_use': True},
        "fast": {'func': effect.fast, 'perm': 'everyone', 'single_use': True},
        "slow": {'func': effect.slow, 'perm': 'everyone', 'single_use': True},
    }

    latency_enabled = False
    was_cached = False
    debug_enabled = False
    train_count = 1

    @emote.command(name="add", description="Add an emote to the server")
    @app_commands.describe(
        name="The name of the new emote",
        url="The URL of a supported file type to add as an emote"
    )
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
            (lambda: alphanumeric_name, EmoteAddError.INVALID_NAME_CHAR),
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

        await interaction.response.send_message(f"Here is your secure link: {masked_url}")

    # Deprecated
    # @emote.command(name="show_cache", description="Show current cache state")
    # @commands.is_owner()
    # async def emote_show_cache(self, interaction: discord.Interaction):
    #     if not interaction.user.guild_permissions.manage_messages:
    #         await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
    #         return
    #
    #     cache_info = get_cache_info()
    #     await interaction.response.send_message(cache_info)

    @emote.command(name="clear_cache", description="Manually clear the cache")
    @commands.is_owner()
    async def emote_clear_cache(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        db.cache.clear()
        await interaction.response.send_message("Cache cleared successfully.")

    @emote.command(name="effect", description="Learn more about an effect")
    @app_commands.describe(effect_name="Name of the effect to get details about")
    async def effect(self, interaction: discord.Interaction, effect_name: str):
        # Retrieve effect information from EFFECTS_LIST
        effect_info = self.EFFECTS_LIST.get(effect_name.lower())
        if not effect_info:
            await interaction.response.send_message(
                f"Effect '{effect_name}' not found.",
                ephemeral=True
            )
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

                display_name = f"{name} - {user_doc}" if user_doc else name
                suggestions.append(app_commands.Choice(name=display_name, value=name))
        return suggestions

    @emote.command(name="remove_a_strike", description="Remove a single strike from a user")
    @app_commands.describe(user="User to remove a strike from")
    @commands.guild_only()
    @commands.is_owner()
    async def remove_a_strike(self, interaction: discord.Interaction, user: discord.Member):
        new_count = await db.decrease_strike(user.id, interaction.guild_id)

        if new_count < 3:
            channel_names = ["general-3-uwu", "general-3"]
            channel = next(
                (discord.utils.get(interaction.guild.channels, name=name) for name in channel_names if
                 discord.utils.get(interaction.guild.channels, name=name)),
                None
            )

            if channel:
                await channel.set_permissions(user, overwrite=None, reason="Strike count below maximum strikes")

        await interaction.response.send_message(
            f"Aww, {user.mention}-chan had a stwike wemoved! ✨ UwU~ They now have {new_count}/3 stwikes. 🐾",
            ephemeral=False
        )

    @emote.command(name="forgive", description="Forgive all strikes for a user")
    @app_commands.describe(user="User to forgive strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def forgive_user(self, interaction: discord.Interaction, user: discord.Member):
        await db.reset_strikes(user.id, interaction.guild_id)

        channel_names = ["general-3-uwu", "general-3"]

        # Find the first matching channel
        channel = next(
            (discord.utils.get(interaction.guild.channels, name=name) for name in channel_names if
             discord.utils.get(interaction.guild.channels, name=name)),
            None
        )

        if channel:
            # Reset user permissions for the channel
            await channel.set_permissions(user, overwrite=None, reason="Strikes forgiven")

        await interaction.response.send_message(
            f"All of {user.mention}-chan's stwikes have been fuwgiven, nya~! ✨ UwU~",
            ephemeral=False
        )

    @emote.command(name="view_strikes", description="View current strikes for a user")
    @app_commands.describe(user="User to check strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def view_strikes(self, interaction: discord.Interaction, user: discord.Member):
        strikes = await db.get_strikes(user.id, interaction.guild_id)
        await interaction.response.send_message(
            f"{user.mention}-chan has {strikes}/3 stwikes, nya~! Pwease be cawefuw! ⚠️",
            ephemeral=False
        )

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Check if message is in the 'general-3-uwu' channel
        if message.channel.name.lower() == "general-3-uwu" or message.channel.name.lower() == "general-3":
            if not (message.author.id == 138148168360656896 and message.content.startswith("!")):  # Ignore owner
                if not is_enclosed_in_colon(message):  # Ignore :emotes:
                    await message.channel.typing()
                    await self.handle_april_fools(message)

        elif is_enclosed_in_colon(message):
            await message.channel.typing()
            await self.process_emote_pipeline(message)
            reset_flags()

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

    async def handle_april_fools(self, message: discord.Message):
        content = message.clean_content
        image_data = None
        guild_id = message.guild.id
        user_id = message.author.id

        image_url = None
        valid_formats = ["png", "webm", "jpg", "jpeg", "gif"]
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in valid_formats):
                image_url = attachment.url
                break

        # try:
        analysis = await analyze_uwu(content, image_url)

        if analysis.get("isUwU", False):
            await message.add_reaction("✅")  # UwU approved
            await sleep(1)
            await message.remove_reaction("✅", message.guild.me)
            pass
        else:
            # Increment strike count
            current_strikes = await db.increment_strike(user_id, guild_id)
            # current_strikes = 0

            if current_strikes >= 3:
                # Revoke posting privileges
                channel_names = ["general-3-uwu", "general-3"]

                channel = next(
                    (discord.utils.get(message.guild.channels, name=name) for name in channel_names if
                     discord.utils.get(message.guild.channels, name=name)),
                    None
                )

                await channel.set_permissions(
                    message.author,
                    send_messages=False,
                    reason="3 strikes reached"
                )
                await db.reset_strikes(user_id, guild_id)
                await message.add_reaction("❌")
                first_lines = [
                    "**Oopsie!**",
                    "**ZOMG!!**",
                    "**UwU, nuuu!**",
                    "**Oh noes!**",
                    "**Sowwy!**",
                    "**Nyaa!**",
                    "**Hewwo?**",
                    "**Eep!**"
                ]
                first_line = random.choice(first_lines)
                await message.reply(
                    f"{first_line} 🚨🚨🚨\n"
                    f"{message.author.mention}-chan, you've hit 3 stwikes! No mowe posting fow you... 🚫 (✿◕︿◕)\n"
                    f"B-bettew wuck next time, nya~! ✨"
                )
            else:
                alert_lines = [
                    "**Non-UwU Alert!**",
                    "**Oops, no UwU!**",
                    "**Aw-aw missing!**",
                    "**Nyoo! Not UwU!**",
                    "**Alert! No UwU!**"
                ]
                alert_line = random.choice(alert_lines)
                strikes_left = 3 - current_strikes
                await message.reply(
                    f"{alert_line} 🚨\n"
                    f"{analysis['reason']}\n\n"
                    f"Strike {current_strikes}/3 - "
                    f"You have {strikes_left} {'tries' if strikes_left > 1 else 'try'} remaining! ⚠️\n\n",
                    mention_author=True
                )
                await message.add_reaction("❌")  # Non-UwU reaction

        # except Exception as e:
        #     print(f"Error processing April Fools message: {e}")
        #     await message.reply(f"Error processing April Fools message. Please try again later. \n {(str(e))}")
        #     await message.add_reaction("⚠️")


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
