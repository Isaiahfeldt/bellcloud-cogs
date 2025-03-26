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
import time

import discord
from discord import app_commands
from fuzzywuzzy import fuzz, process
from redbot.core import commands
# from discord.app_commands import Choice, commands
# from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from .utils.chat import send_help_embed, send_error_embed, send_embed_followup, send_error_followup, send_emote, \
    generate_token
from .utils.database import Database
from .utils.effects import latency, flip, debug, train
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


async def get_emote_and_verify(emote_name_str: str, channel):
    emote = await db.get_emote(emote_name_str, channel.guild.id, True)
    if emote is None:
        # await channel.send(f"Emote '{emote_name_str}' not found.")
        await channel.send(f"Checkpoint 1")
        await channel.send(f"{channel}")
        await channel.send(f"{channel.guild}")
        await channel.send(f"{channel.guild.id}")
        valid_names = await db.get_emote_names(channel.guild.id)

        matches = process.extractBests(
            emote_name_str,
            valid_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=70
        )
        await channel.send(f"Checkpoint 2 - {matches}")

        if matches:
            best_match = matches[0][0]
            await channel.send(f"{matches[0]}")
            await channel.send(f"{matches[0][0]}")
            await channel.send(f"Emote '{emote_name}' not found. Did you mean '{best_match}'?",
                               delete_after=10)
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
        "latency": {'func': latency, 'perm': 'mod'},
        "flip": {'func': flip, 'perm': 'everyone'},
        "debug": {'func': debug, 'perm': 'everyone'},
        "train": {'func': train, 'perm': 'everyone'},
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

        emote_list = "\n".join(emote_names)
        await interaction.response.send_message(emote_list)

    @emote.command(name="website", description="Get a secure link to view the server's emotes")
    async def emote_website(self, interaction: discord.Interaction):
        token = generate_token(interaction)

        url = f"https://bellbot.xyz/emote/{server_id}?token={token}"
        secure_url = f"[bellbot.xyz/emote/{server_id}]({url})"

        await interaction.response.send_message(f"Here is your secure link: {secure_url}")

    @emote.command(name="show_cache", description="Show current cache state")
    @commands.is_owner()
    async def emote_show_cache(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        cache_info = get_cache_info()
        await interaction.response.send_message(cache_info)

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
            colour=EmbedColor.RED.value
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not is_enclosed_in_colon(message):
            return

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
