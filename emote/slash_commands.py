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

from type_hints.bot import DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE
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
    """
    This class defines the SlashCommands cog, which contains command functionalities related to emotes.

    Attributes:
    - emote: Group command to perform actions related to emotes.

    Methods:
    - emote_add: Add an emote to the server.

    """
    emote = app_commands.Group(name="emote", description="Sorta like emojis, but cooler")

    async def _send_embed_message(self, interaction, title, description, color: EmbedColor):
        """Send embed message to user."""
        embed = discord.Embed(title=title,
                              description=description,
                              colour=color.value)
        embed.set_author(name="Emote Help Menu",
                         icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @emote.command(name="add", description="Add an emote to the server")
    @app_commands.describe(
        name="The name of the new emote",
        url="The URL of a supported file type to add as an emote"
    )
    async def emote_add(self, interaction: DISCORD_INTERACTION_TYPE, name: str, url: str):
        """
        Add an emote to the server.

        Parameters:
        - interaction (DISCORD_INTERACTION_TYPE): The Discord interaction object.
        - name (str): The name of the new emote.
        - url (str): The URL of a supported file type to add as an emote.

        Returns:
        None

        Throws:
        None

        Example usage:
        emote_add("emote_name", "https://example.com/emote.png")
        """

        if not interaction.user.guild_permissions.manage_messages:
            await self._send_embed_message(interaction,
                                           "Hmm, something went wrong",
                                           "You do not have the required permissions to use this command.",
                                           EmbedColor.ORANGE)
            return

        is_reachable = URLUtils.is_url_reachable(url)
        format_whitelist = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
        is_allowed, file_ext = URLUtils.is_url_allowed_format(url, format_whitelist)

        await self._send_embed_message(interaction,
                                       "Adding emote...",
                                       "Please wait while the emote is being added to the server.",
                                       EmbedColor.GREEN)
