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
import re

import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

# Use the dedicated Gen3Database class
from gen3.utils.database import Gen3Database

# Import the 3-word rule from scratch file for flexible rules
from three_word_rule_scratch import three_word_rule

# Create a global database instance
db = Gen3Database()

# Word chain tracking - global state for current required word
current_required_word = None

# Active rule selector (global for simplicity/minimal changes)
# Possible values: "apple_orange", "word_chain", "three_word"
ACTIVE_RULE = "apple_orange"

# Common words to exclude from selection
EXCLUDED_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he", "in", "is", "it", 
    "its", "of", "on", "that", "the", "to", "was", "will", "with", "you", "your", "i", "me", "my",
    "we", "us", "our", "they", "them", "their", "this", "these", "those", "than", "then", "there",
    "here", "where", "when", "how", "what", "who", "why", "can", "could", "should", "would", "have",
    "had", "do", "does", "did", "get", "got", "just", "now", "so", "very", "much", "more", "most",
    "some", "any", "no", "not", "up", "out", "if", "about", "into", "over", "after"
}

# Base digit emojis for dynamic number generation
DIGIT_EMOJIS = {
    '0': "0️⃣", '1': "1️⃣", '2': "2️⃣", '3': "3️⃣", '4': "4️⃣",
    '5': "5️⃣", '6': "6️⃣", '7': "7️⃣", '8': "8️⃣", '9': "9️⃣"
}

def get_position_emoji(position: int) -> str:
    """
    Generate emoji representation for any position number dynamically.
    
    Args:
        position: The position number to convert to emoji
        
    Returns:
        str: Emoji representation of the position number
    """
    if position == 10:
        return "🔟"  # Special case for 10
    
    # Convert position to string and map each digit to its emoji
    position_str = str(position)
    emoji_parts = [DIGIT_EMOJIS[digit] for digit in position_str]
    
    return ''.join(emoji_parts)

# Provide a legacy/static mapping for tests and convenience (1..20)
POSITION_EMOJIS = {i: get_position_emoji(i) for i in range(1, 21)}

_ = Translator("Gen3", __file__)


def extract_words(text: str) -> list[str]:
    """
    Extract meaningful words from text, excluding articles, prepositions, and common words.
    
    Args:
        text: The input text to extract words from
        
    Returns:
        list: List of meaningful words in lowercase
    """
    # Remove punctuation and split into words
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    # Filter out excluded words and words shorter than 3 characters
    meaningful_words = [word for word in words if word not in EXCLUDED_WORDS and len(word) >= 3]
    
    return meaningful_words


async def apple_orange_rule(content: str, current_strikes: int = 0) -> dict:
    """
    Demo rule: pass if message contains 'apple' (case-insensitive),
    fail if it contains 'orange'. If both appear, 'orange' takes precedence and it fails.
    """
    text = content.lower() if content else ""
    contains_orange = "orange" in text
    contains_apple = "apple" in text

    if contains_orange:
        return {
            "passes": False,
            "reason": "Contains forbidden word 'orange'. 🍊❌"
        }
    if contains_apple:
        return {
            "passes": True,
            "reason": "Contains required word 'apple'. 🍎✅"
        }
    return {
        "passes": False,
        "reason": "Message must include 'apple'. 🍎❌"
    }


async def word_chain_rule(content: str, current_strikes: int = 0) -> dict:
    """
    Word chain rule function for gen3 events.
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has
    
    Returns:
        dict: {"passes": bool, "reason": str, "selected_word": str|None, "word_position": int|None}
    """
    global current_required_word
    
    # If no required word is set, this message passes and we select a new word
    if current_required_word is None:
        meaningful_words = extract_words(content)
        
        if meaningful_words:
            # Select a random word from the meaningful words
            selected_word = random.choice(meaningful_words)
            
            # Find the position of this word in the original text
            content_words = re.findall(r'\b[a-zA-Z]+\b', content.lower())
            word_position = content_words.index(selected_word) + 1  # 1-indexed
            
            current_required_word = selected_word
            
            return {
                "passes": True,
                "reason": f"Message accepted! Next person must include the word '{selected_word}' 🎯",
                "selected_word": selected_word,
                "word_position": word_position
            }
        else:
            return {
                "passes": True,
                "reason": "No meaningful words found to select. Message accepted! 🎯",
                "selected_word": None,
                "word_position": None
            }
    
    # Check if the message contains the required word
    content_lower = content.lower()
    if current_required_word in content_lower:
        # Message passes, now select a new word from this message
        meaningful_words = extract_words(content)
        
        if meaningful_words:
            selected_word = random.choice(meaningful_words)
            content_words = re.findall(r'\b[a-zA-Z]+\b', content.lower())
            word_position = content_words.index(selected_word) + 1  # 1-indexed
            
            current_required_word = selected_word
            
            return {
                "passes": True,
                "reason": f"Great! Your message contained '{current_required_word}'. Next person must include '{selected_word}' 🎯",
                "selected_word": selected_word,
                "word_position": word_position
            }
        else:
            # Keep the same required word since no new words to select
            return {
                "passes": True,
                "reason": f"Message accepted! Next person still needs to include '{current_required_word}' 🎯",
                "selected_word": None,
                "word_position": None
            }
    else:
        # Message fails - doesn't contain required word
        return {
            "passes": False,
            "reason": f"Oops! Your message must contain the word '{current_required_word}' to continue the chain! 🔗❌"
        }


async def check_gen3_rules(content: str, current_strikes: int = 0) -> dict:
    """
    Flexible rule checker for gen3 events. Dispatches to the active rule.
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has
    
    Returns:
        dict: {"passes": bool, "reason": str, "selected_word": str|None, "word_position": int|None}
    """
    # Minimal global toggle (not persisted). Defaults to apple_orange for backward-compat tests.
    if ACTIVE_RULE == "word_chain":
        return await word_chain_rule(content, current_strikes)
    elif ACTIVE_RULE == "three_word":
        return await three_word_rule(content, current_strikes)
    else:
        # Default / fallback demo rule
        return await apple_orange_rule(content, current_strikes)


@cog_i18n(_)
class SlashCommands(commands.Cog):
    """
    Slash commands for the Gen3 cog.
    """
    gen3 = app_commands.Group(name="gen3", description="Gen3 event management commands")

    def __init__(self):
        super().__init__()

    @gen3.command(name="set_rule", description="Set the active Gen3 rule")
    @app_commands.describe(rule="Choose which rule to enforce")
    @app_commands.choices(
        rule=[
            app_commands.Choice(name="Apple/Orange (demo)", value="apple_orange"),
            app_commands.Choice(name="Word Chain", value="word_chain"),
            app_commands.Choice(name="Three Word (exactly 3 words)", value="three_word"),
        ]
    )
    @commands.guild_only()
    @commands.is_owner()
    async def set_rule(self, interaction: discord.Interaction, rule: app_commands.Choice[str]):
        global ACTIVE_RULE
        ACTIVE_RULE = rule.value

        # Reset the word-chain state if switching away from/into it (to avoid confusing carryover)
        global current_required_word
        if ACTIVE_RULE != "word_chain":
            current_required_word = None

        # Friendly confirmation
        names = {
            "apple_orange": "Apple/Orange (demo)",
            "word_chain": "Word Chain",
            "three_word": "Three Word",
        }
        await interaction.response.send_message(
            f"Active Gen3 rule set to: {names.get(ACTIVE_RULE, ACTIVE_RULE)}",
            ephemeral=False,
        )

    @gen3.command(name="get_rule", description="Show the currently active Gen3 rule")
    @commands.guild_only()
    async def get_rule(self, interaction: discord.Interaction):
        names = {
            "apple_orange": "Apple/Orange (demo)",
            "word_chain": "Word Chain",
            "three_word": "Three Word",
        }
        await interaction.response.send_message(
            f"Current active Gen3 rule: {names.get(ACTIVE_RULE, ACTIVE_RULE)}",
            ephemeral=True,
        )

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Check if message is in monitored channels (gen3 channels + testing channel)
        monitored_channels = ["private-bot-commands", "general-3"]

        if (message.channel.name.lower() in monitored_channels):
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
            channel_names = ["general-3"]
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
        channel = message.channel
        guild_id = message.guild.id
        user_id = message.author.id

        strikes = await db.get_strikes(user_id, guild_id)
        analysis = await check_gen3_rules(content, strikes)

        if analysis.get("passes", False):
            # Rule check passed - add emoji reaction if word was selected
            if analysis.get("selected_word") and analysis.get("word_position"):
                word_position = analysis.get("word_position")
                # Generate emoji for any position dynamically
                emoji = get_position_emoji(word_position)
                await message.add_reaction(emoji)
        else:
            await message.channel.typing()
            # Increment strike count
            current_strikes = await db.increment_strike(user_id, guild_id)

            if current_strikes >= 3:
                # Revoke posting privileges
                await channel.send(f"Channel: {channel}")

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
