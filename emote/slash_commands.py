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

from .utils.chat import send_help_embed, send_error_embed, send_embed_followup, send_error_followup
from .utils.database import Database
from .utils.enums import EmoteAddError
from .utils.format import extract_emote_effects
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

        # Send pre-emptive response embed
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
        await interaction.response.send_message(cache_state)

    @emote.command(name="clear_cache", description="Manually clear the cache")
    @commands.is_owner()
    async def emote_clear_cache(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        db.cache.clear()
        await interaction.response.send_message("Cache cleared successfully.")

    # @commands.Cog.listener()
    # async def on_message(self, message: discord.Message):
    #     if message.author.bot or not (message.content.startswith(":") and message.content.endswith(":")):
    #         return
    #
    #     emote_name = convert_emote_name(message.content)
    #
    #     result = await db.get_emote(emote_name, False)
    #     if result is not None:
    #         # file_path = result[0]  # Extract the file_path from the database result
    #         file_url = f"https://media.bellbot.xyz/emote/{result}"  # Construct the final URL
    #         # embed = discord.Embed()
    #         # embed.set_image(url=file_url)
    #         await message.channel.send(f"{file_url}")
    #     else:
    #         await message.channel.send(f"Emote '{emote_name}' not found.")


@commands.Cog.listener()
async def on_message(self, message: discord.Message):
    if message.author.bot or not message.content.startswith(":") and message.content.endswith(":"):
        return

    effects_list = {
        "latency": {'func': latency, 'perm': 'everyone'},
        "flip": {'func': flip, 'perm': 'everyone'},
    }

    permissions = {
        "owner": lambda: self.bot.is_owner(message.author),
        "mod": lambda: message.author.guild_permissions.manage_messages,
        "everyone": lambda: True,
    }

    pipeline = [self.get_emote]
    emote_name, emote_effect = extract_emote_effects(message.content)

    for command_name in emote_effect:
        if command_name in effects_list:
            command = effects_list[command_name]
            if permissions[command['perm']]():
                await message.channel.send(command['func'])
                # pipeline.append(command['func'])
            else:
                await message.channel.send(f"You are not authorized to use the {command_name} command.")


async def latency(message, emote_name):
    start_time = time.time()
    result = await db.get_emote(emote_name, False)
    end_time = time.time()
    elapsed_time = round(end_time - start_time, 2)

    # if result is not None:
    #     file_url = f"https://media.bellbot.xyz/emote/{result}"
    #     await message.channel.send(f"{file_url}\n\nTime taken: {elapsed_time}s")
    # else:
    #     await message.channel.send(f"Emote '{emote_name}' not found.\n\nTime taken: {elapsed_time}s")


async def send_emote(message, emote_name):
    result = await db.get_emote(emote_name, False)
    if result is not None:
        file_url = f"https://media.bellbot.xyz/emote/{result}"
        await message.channel.send(f"{file_url}")
    else:
        await message.channel.send(f"Emote '{emote_name}' not found.")
