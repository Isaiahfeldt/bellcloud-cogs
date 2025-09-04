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

import io
from datetime import datetime, timedelta, timezone

import discord
import jwt

from emote.utils.effects import Emote
from emote.utils.enums import EmbedColor


async def send_help_embed(interaction, title, description):
    """
    @param interaction: The interaction object representing the user's interaction with the bot.
    @param title: The title of the embed message.
    @param description: The description of the embed message.
    @return: None

    Sends an embed message for the help menu using the provided parameters. The embed message includes a title,
    description, color, and author information.

    Example Usage:
        await _send_help_embed_message(interaction, "Command Help", "This is a help message.", Color.BLUE.Value)
    """
    embed = discord.Embed(title=title,
                          description=description,
                          colour=EmbedColor.GREEN.value)
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def send_embed_followup(interaction, title, description):
    """
    :param interaction: The interaction object representing the user's interaction with a command in Discord.
    :param title: The title of the embedded message.
    :param description: The description of the embedded message.
    :return: None

    This method is used to send an embedded follow-up message in response to a user's interaction with a command in Discord. The method takes three parameters: `interaction`, `title`, and
    * `description`.
    """
    embed = discord.Embed(title=title,
                          description=description,
                          colour=EmbedColor.GREEN.value)
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    try:
        await interaction.delete_original_response()
    except (discord.NotFound, discord.HTTPException):
        pass

    await interaction.followup.send(embed=embed, ephemeral=True)


async def send_error_embed(interaction, error_message):
    """
    @param interaction: The interaction object representing the user command to respond to.
    @param error_message: The error message to display in the error embed.

    Sends an error embed to the user in response to a command with the provided error message.

    @return: None
    """
    # Make sure error_message has a value attribute
    if not hasattr(error_message, 'value'):
        raise ValueError("Invalid error message object, must have a value attribute.")

    embed = discord.Embed(title="Hmm, something went wrong.",
                          description=error_message.value,
                          colour=EmbedColor.RED.value)  # Changed usage of Enum
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def send_error_followup(interaction, error_message, emote=None):
    """
    @param interaction: The interaction object representing the user command to respond to.
    @param error_message: The error message to display in the error embed.

    Sends an error embed to the user in response to a command with the provided error message.

    @return: None
    """
    # Make sure error_message has a value attribute
    if not hasattr(error_message, 'value'):
        raise ValueError("Invalid error message object, must have a value attribute.")

    embed = discord.Embed(title="Hmm, something went wrong.",
                          description=error_message.value,
                          colour=EmbedColor.RED.value)  # Changed usage of Enum
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    try:
        await interaction.delete_original_response()
    except (discord.NotFound, discord.HTTPException):
        pass

    await interaction.followup.send(embed=embed, ephemeral=True)


async def send_embed_followup_modal(interaction, title, description):
    """
    ... (docstring) ...
    """
    embed = discord.Embed(title=title,
                          description=description,
                          colour=EmbedColor.GREEN.value)
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)
    # Correctly uses followup.send without deleting
    await interaction.followup.send(embed=embed, ephemeral=True)


# ADD THIS NEW FUNCTION
async def send_error_followup_modal(interaction, error_message):
    """Sends an error embed as a followup for a modal interaction."""
    if not hasattr(error_message, 'value'):
        raise ValueError("Invalid error message object, must have a value attribute.")

    embed = discord.Embed(title="Hmm, something went wrong.",
                          description=error_message.value,
                          colour=EmbedColor.RED.value)
    embed.set_author(name="Emote Help Menu",
                     icon_url=interaction.client.user.display_avatar.url)

    # Check if a response has already been sent (e.g., defer())
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        # If not, send the initial response
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def send_debug_embed(message, emote):
    debug_embed = discord.Embed(
        title="Debug Information",
        color=0xFF5733  # Choose your preferred color.
    )

    # Iterate over the dictionary items: key is the note name, and value is the note content.
    for note_name, note_content in emote.notes.items():
        debug_embed.add_field(name=note_name, value=note_content, inline=True)

    # Add fields for each error present.
    for error_key, error_value in emote.errors.items():
        debug_embed.add_field(name=f"Error: {error_key}", value=error_value, inline=False)

    for issue_key, issue_value in emote.issues.items():
        debug_embed.add_field(name=f"Issues: {issue_key}", value=issue_value, inline=False)

    await message.channel.send(embed=debug_embed)


async def send_followup_embed(message: discord.Message, emote):
    """
    Sends a followup embed using messages in emote.followup.

    :param message: The discord.Message object where the embed will be sent.
    :param emote: The Emote object containing followup messages.
    """
    if not emote.followup:
        return

    embed = discord.Embed(title="Umm, just a follow up...", colour=EmbedColor.GREY.value)
    for key, followup_msg in emote.followup.items():
        embed.add_field(name=f"{key}", value=followup_msg, inline=False)
    embed.set_footer(text="This embed will delete automatically.")
    await message.channel.send(embed=embed, delete_after=20)


async def generate_token(interaction: discord.Interaction):
    expiration = datetime.now(timezone.utc) + timedelta(days=1)
    server_id = interaction.guild_id

    # Create a simple JWT payload.
    payload = {
        "server_id": str(server_id),
        "iat": datetime.now(timezone.utc),
        "exp": expiration,
    }

    JWT_SECRET = "yammychocolatecake"
    # Generate the JWT. (HS256 is a symmetric algorithm that keeps the token compact.)
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token


async def send_reload(self, message: discord.Message):
    if message.content == "!cog update True emote":
        ctx = await self.bot.get_context(message)
        await ctx.invoke(ctx.bot.get_command('cog update'), 'True emote')
        await message.channel.send(f"<@138148168360656896>")


async def send_emote(message: discord.Message, emote: Emote, *args):
    """
    Sends the emote image to the discord channel.
    If emote.img_data exists, the image is sent as a file using an in-memory buffer.
    Otherwise, it falls back to sending the file path text.
    Additional arguments are sent as part of the text.

    :param message: The discord.Message object where the emote should be sent.
    :param emote: The Emote object containing image data and other details.
    :param args: Any additional text arguments.
    """
    from emote.slash_commands import SlashCommands

    content = ""
    if args:
        content = "\n".join(args)

    if emote.img_data:
        for _ in range(SlashCommands.train_count):
            # Create an in-memory binary stream for the image data.
            image_buffer = io.BytesIO(emote.img_data)
            # You can extract a filename from emote.file_path or use a default.
            filename = emote.file_path.split("/")[-1] if emote.file_path else "emote.png"
            file = discord.File(fp=image_buffer, filename=filename)
            await message.channel.send(content=content, file=file)
    else:
        file_url = emote.file_path
        # Fall back to sending the URL text if no image data available.
        text = f"{file_url}\n{content}" if content else file_url
        await message.channel.send(text)

    if emote.notes and SlashCommands.debug_enabled:
        await send_debug_embed(message, emote)

    if emote.followup:
        await send_followup_embed(message, emote)

    # TODO update @send_embed_followup to allow for
