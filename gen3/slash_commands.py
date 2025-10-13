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

import random

import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

# Use the dedicated Gen3Database class
from gen3.utils.database import Gen3Database

# Create a global database instance
db = Gen3Database()

_ = Translator("Gen3", __file__)


async def apple_orange_rule(content: str, current_strikes: int = 0) -> dict:
    """
    Demo rule function for gen3 events - checks for apple (pass) vs orange (strike).
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has
    
    Returns:
        dict: {"passes": bool, "reason": str}
    """
    content_lower = content.lower()

    # Check for "orange" first (strike condition takes precedence)
    if "orange" in content_lower:
        return {
            "passes": False,
            "reason": f"Oops! Your message contains 'orange' which is not allowed in this gen3 event. Try using 'apple' instead! 🚫🍊"
        }
    elif "apple" in content_lower:
        return {
            "passes": True,
            "reason": f"Great! Your message contains 'apple' and follows the gen3 rules! 🍎"
        }
    else:
        return {
            "passes": False,
            "reason": f"Your message doesn't contain the required word 'apple' for this gen3 event! 🍎"
        }


async def check_gen3_rules(content: str, current_strikes: int = 0) -> dict:
    """
    Flexible rule checker for gen3 events. 
    This function can be easily modified to use different rule functions for different events.
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has
    
    Returns:
        dict: {"passes": bool, "reason": str}
    """
    # For now, use the apple/orange rule - this can be easily swapped out for different events
    return await apple_orange_rule(content, current_strikes)


@cog_i18n(_)
class SlashCommands(commands.Cog):
    """
    Slash commands for the Gen3 cog.
    """
    gen3 = app_commands.Group(name="gen3", description="Gen3 event management commands")

    def __init__(self):
        super().__init__()

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Check if message is in monitored channels (gen3 channels + testing channel)
        monitored_channels = ["private-bot-commands", "general-3"]
        testing_channel_id = 900659338069295125  # private-bot-commands

        if (message.channel.name.lower() in monitored_channels or
                message.channel.id == testing_channel_id):
            if not (message.author.id == 138148168360656896 and message.content.startswith("!")):  # Ignore owner
                # Check if the message is not an emote (you might need to import this function)
                # if not is_enclosed_in_colon(message):
                await self.handle_gen3_event(message)

    @gen3.command(name="remove_a_strike", description="Remove a single strike from a user")
    @app_commands.describe(user="User to remove a strike from")
    @commands.guild_only()
    @commands.is_owner()
    async def remove_a_strike(self, interaction: discord.Interaction, user: discord.Member):
        new_count = await db.decrease_strike(user.id, interaction.guild_id)

        if new_count < 3:
            channel_names = ["private-bot-commands", "general-3"]
            channel = next(
                (discord.utils.get(interaction.guild.channels, name=name) for name in channel_names if
                 discord.utils.get(interaction.guild.channels, name=name)),
                None
            )

            if channel:
                await channel.set_permissions(user, overwrite=None, reason="Strike count below maximum strikes")

        await interaction.response.send_message(
            f"Strike removed for {user.mention}! ✨ They now have {new_count}/3 strikes.",
            ephemeral=False
        )

    @gen3.command(name="forgive", description="Forgive all strikes for a user")
    @app_commands.describe(user="User to forgive strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def forgive_user(self, interaction: discord.Interaction, user: discord.Member):
        await db.reset_strikes(user.id, interaction.guild_id)

        channel_names = ["private-bot-commands", "general-3"]

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
            f"All strikes for {user.mention} have been forgiven! ✨",
            ephemeral=False
        )

    @gen3.command(name="view_strikes", description="View current strikes for a user")
    @app_commands.describe(user="User to check strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def view_strikes(self, interaction: discord.Interaction, user: discord.Member):
        strikes = await db.get_strikes(user.id, interaction.guild_id)
        await interaction.response.send_message(
            f"{user.mention} has {strikes}/3 strikes. Please be careful! ⚠️",
            ephemeral=False
        )

    async def handle_gen3_event(self, message: discord.Message):
        content = message.clean_content
        guild_id = message.guild.id
        user_id = message.author.id

        strikes = await db.get_strikes(user_id, guild_id)
        analysis = await check_gen3_rules(content, strikes)

        if analysis.get("passes", False):
            # Rule check passed - no action needed
            pass
        else:
            await message.channel.typing()
            # Increment strike count
            current_strikes = await db.increment_strike(user_id, guild_id)

            if current_strikes >= 3:
                # Revoke posting privileges
                channel_names = ["private-bot-commands", "general-3"]

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
                    "**Strike Out!**",
                    "**Game Over!**",
                    "**Maximum Strikes!**",
                    "**Three Strikes!**",
                    "**Oops!**",
                    "**Alert!**",
                    "**Notice!**",
                    "**Warning!**"
                ]
                first_line = random.choice(first_lines)
                await message.reply(
                    f"{first_line} 🚨🚨🚨\n"
                    f"{message.author.mention}, you've reached 3 strikes! No more posting for you... 🚫\n"
                    f"Better luck next time! ✨"
                )
            else:
                alert_lines = [
                    "**Rule Violation Alert!**",
                    "**Gen3 Rule Alert!**",
                    "**Strike Warning!**",
                    "**Rule Check Failed!**",
                    "**Alert! Rule Violation!**"
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
                await message.add_reaction("❌")  # Rule violation reaction
