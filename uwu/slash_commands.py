#  Copyright (c) 2024-2025, Isaiah Feldt
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

import json
import os
import random

import discord
from discord import app_commands
from openai import OpenAI
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

# Reuse the Database class from emote
from emote.utils.database import Database

_ = Translator("Uwu", __file__)

# Initialize database
db = Database()


async def analyze_uwu(content=None, image_url=None, current_strikes: int = 0):
    """Analyzes text/image for UwU-style content using OpenAI"""
    client = OpenAI(
        api_key=os.getenv('OPENAI_KEY'),
    )

    messages = [{
        "role": "system",
        "content":
            "You are a discord bot that analyzes messages for UwU-style content in the general-3 channel. "
            "Analyze for *any* ( UwU-style elements (cute text, emoticons, playful misspellings). "
            "Messages don't necessarily have to be 'happy', they can be angry, mean, etc as long as they follow the other rules. "
            "Examples: 'i fwucking hate dis server', 'wat da hell...'. "
            f"Keep in mind that the user is currently on warning {current_strikes + 1}/3; each message that lacks these creative touches "
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


@cog_i18n(_)
class SlashCommands(commands.Cog):
    """
    Slash commands for the UwU cog.
    """
    uwu = app_commands.Group(name="uwu", description="UwU voice analyzer commands")

    def __init__(self):
        super().__init__()

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Check if message is in the 'general-3-uwu' channel
        if message.channel.name.lower() == "general-3-uwu" or message.channel.name.lower() == "general-3":
            if not (message.author.id == 138148168360656896 and message.content.startswith("!")):  # Ignore owner
                # Check if the message is not an emote (you might need to import this function)
                # if not is_enclosed_in_colon(message):
                await self.handle_april_fools(message)

    @uwu.command(name="remove_a_strike", description="Remove a single strike from a user")
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

    @uwu.command(name="forgive", description="Forgive all strikes for a user")
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

    @uwu.command(name="view_strikes", description="View current strikes for a user")
    @app_commands.describe(user="User to check strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def view_strikes(self, interaction: discord.Interaction, user: discord.Member):
        strikes = await db.get_strikes(user.id, interaction.guild_id)
        await interaction.response.send_message(
            f"{user.mention}-chan has {strikes}/3 stwikes, nya~! Pwease be cawefuw! ⚠️",
            ephemeral=False
        )

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

        strikes = await db.get_strikes(user_id, guild_id)
        analysis = await analyze_uwu(content, image_url, strikes)

        if analysis.get("isUwU", False):
            # UwU approved - no action needed
            pass
        else:
            await message.channel.typing()
            # Increment strike count
            current_strikes = await db.increment_strike(user_id, guild_id)

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
                    f"Stwike {current_strikes}/3 - "
                    f"You have {strikes_left} {'twies' if strikes_left > 1 else 'twie'} wemaining! ⚠️\n\n",
                    mention_author=True
                )
                await message.add_reaction("❌")  # Non-UwU reaction