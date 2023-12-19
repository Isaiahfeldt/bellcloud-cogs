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

from emote.utils.enums import EmbedColor

a


async def send_help_embed(interaction, title, description):
    """
    @param interaction: The interaction object representing the user's interaction with the bot.
    @param title: The title of the embed message.
    @param description: The description of the embed message.
    @return: None

    Sends an embed message for the help menu using the provided parameters. The embed message includes a title, description, color, and author information.

    Example Usage:
        await _send_help_embed_message(interaction, "Command Help", "This is a help message.", Color.BLUE.Value)
    """
    embed = discord.Embed(title=title,
                          description=description,
                          colour=EmbedColor.GREEN.value)
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def send_error_embed(self, interaction, error_message):
    """
    @param self: The current instance of the class.
    @param interaction: The interaction object representing the user command to respond to.
    @param error_message: The error message to display in the error embed.

    Sends an error embed to the user in response to a command with the provided error message.

    @return: None
    """
    # Make sure error_message has a value attribute
    if not hasattr(error_message, 'value'):
        raise ValueError("Invalid error message object, must have a value attribute")

    embed = discord.Embed(title="Hmm, something went wrong",
                          description=error_message.value,
                          colour=EmbedColor.RED.value)  # Changed usage of Enum
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)