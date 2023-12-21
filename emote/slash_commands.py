#  Copyright (c) 2023, Isaiah Feldt
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

import discord
from discord import app_commands
from redbot.core import commands
# from discord.app_commands import Choice, commands
# from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from .utils.chat import send_help_embed, send_error_embed, send_embed_followup, send_error_followup
from .utils.database import Database
from .utils.enums import EmoteAddError
from .utils.url import is_url_reachable, blacklisted_url, is_media_format_valid, is_media_size_valid, alphanumeric_name

_ = Translator("Emote", __file__)

valid_formats = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
db = Database()


@cog_i18n(_)
@app_commands.guild_only()
class SlashCommands(commands.Cog):
    """This class defines the SlashCommands cog"""
    emote = app_commands.Group(name="emote", description="Sorta like emojis, but cooler")

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

        # Send pre-emptive response embed
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

        if await db.emote_exists_in_database(name):
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

        # Send pre-emptive response embed
        await send_help_embed(
            interaction, "Adding emote...",
            "Please wait while the emote is being added to the server."
        )
