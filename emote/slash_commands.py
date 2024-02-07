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
from redbot.core import commands
# from discord.app_commands import Choice, commands
# from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from .utils.chat import send_help_embed, send_error_embed, send_embed_followup, send_error_followup, send_emote
from .utils.database import Database
from .utils.effects import latency, flip
from .utils.enums import EmoteAddError
from .utils.format import extract_emote_details, is_enclosed_in_colon
from .utils.pipeline import create_pipeline, execute_pipeline
from .utils.url import is_url_reachable, blacklisted_url, is_media_format_valid, is_media_size_valid, alphanumeric_name

_ = Translator("Emote", __file__)

valid_formats = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
db = Database()


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
        "latency2": {'func': latency, 'perm': 'mod'},
        "flip": {'func': flip, 'perm': 'everyone'},
    }

    latency_enabled = False
    was_cached = False

    def generate_extra_args(self, time_elapsed, emote_name):
        if SlashCommands.latency_enabled:
            extra_args = [f"Your request was processed in `{time_elapsed}` seconds!"]
            if SlashCommands.was_cached:
                extra_args.append(f"The emote `{emote_name}` was found in cache")
            return extra_args
        return []

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

        if await db.check_emote_exists(name):
            await send_error_followup(interaction, EmoteAddError.DUPLICATE_EMOTE_NAME)
            return

        await send_embed_followup(
            interaction, "Success!", f"Added **{name}** as an emote."
        )

        # Does Emote name already exist in db?
        # Upload to bucket

    @emote.command(name="remove", description="Remove an emote from the server")
    @app_commands.describe(name="The name of the emote to remove")
    async def emote_remove(self, interaction: discord.Interaction, name: str):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        await send_help_embed(
            interaction, "Adding emote...",
            "Please wait while the emote is being added to the server."
        )

    @emote.command(name="show_cache", description="Show current cache state")
    @commands.is_owner()
    async def emote_show_cache(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        cache_state = str(db.cache)
        emote_usage_collection = str(db.emote_usage_collection)
        await interaction.response.send_message(f"{cache_state}\n{emote_usage_collection}")

    @emote.command(name="clear_cache", description="Manually clear the cache")
    @commands.is_owner()
    async def emote_clear_cache(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        db.cache.clear()
        await interaction.response.send_message("Cache cleared successfully.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # await send_reload(self, message)
        if message.author.bot or not is_enclosed_in_colon(message):
            return
        await message.channel.typing()

        start_time = time.perf_counter()  # Start performance timer

        emote_name, queued_effects = extract_emote_details(message)
        emote = await db.get_emote(emote_name)

        if not emote:
            return await message.channel.send(f"Emote '{emote_name}' not found.")

        pipeline, issues = await create_pipeline(self, message, emote, queued_effects)
        emote = await execute_pipeline(pipeline)

        # End performance timer
        end_time = time.perf_counter()
        time_elapsed = round(end_time - start_time, 2)

        extra_args = self.generate_extra_args(time_elapsed, emote_name)

        await send_emote(message, emote, *extra_args)

        SlashCommands.latency_enabled = False
        SlashCommands.was_cached = False
