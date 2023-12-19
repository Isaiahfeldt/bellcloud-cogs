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

import os
from enum import Enum

import discord
from discord import app_commands
# from discord.app_commands import Choice, commands
# from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from .type_hints.bot import DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE
from .utils.url import URLUtils

_ = Translator("Emote", __file__)

# Database connection parameters
host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
database = os.getenv('DB_DATABASE')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')


# def is_url_reachable(url_string):
#     """
#     Check if a URL is reachable by sending a HEAD request and checking the status code.
#     Parameters:
#     - url_string (str): The URL to check.
#     Returns:
#     - (bool): True if the URL is reachable, False otherwise.
#     """
#     try:
#         response = requests.head(url_string)
#         return response.status_code == 200
#     except requests.ConnectionError:
#         return False


class EmbedColor(Enum):
    GREEN = 0x00ff00
    ORANGE = 0xd58907
    RED = 0xff0000


@cog_i18n(_)
@app_commands.guild_only()
class SlashCommands(DISCORD_COG_TYPE_MIXIN):
    """This class defines the SlashCommands cog"""

    COLOR_GREEN = EmbedColor.GREEN
    COLOR_ORANGE = EmbedColor.ORANGE
    COLOR_RED = EmbedColor.RED

    emote = app_commands.Group(name="emote", description="Sorta like emojis, but cooler")

    async def _send_help_embed_message(self, interaction, title, description, color):
        """Send help embed message to user."""
        embed = discord.Embed(title=title,
                              description=description,
                              colour=color.value)
        embed.set_author(name="Emote Help Menu",
                         icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _has_manage_messages_permission(self, interaction):
        return interaction.user.guild_permissions.manage_messages

    def _is_valid_emote_format(self, url):
        format_whitelist = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
        is_allowed, file_ext = URLUtils.is_url_allowed_format(url, format_whitelist)
        return is_allowed

    @emote.command(name="add", description="Add an emote to the server")
    @app_commands.describe(
        name="The name of the new emote",
        url="The URL of a supported file type to add as an emote"
    )
    async def emote_add(self, interaction: DISCORD_INTERACTION_TYPE, name: str, url: str):
        """Add an emote to the server."""
        if not self._has_manage_messages_permission(interaction):
            await self._send_help_embed_message(
                interaction,
                "Hmm, something went wrong",
                "You do not have the required permissions to use this command.",
                self.COLOR_ORANGE
            )
            return

        if not URLUtils.is_url_reachable(url) or not self._is_valid_emote_format(url):
            return  # handle accordingly

        await self._send_help_embed_message(
            interaction,
            "Adding emote...",
            "Please wait while the emote is being added to the server.",
            self.COLOR_GREEN
        )
