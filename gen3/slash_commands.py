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
import random
import re

import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from gen3.rules.apple_orange import apple_orange_rule
# Import the 3-word rule from scratch file for flexible rules
from gen3.rules.three_word import three_word_rule
# Use the dedicated Gen3Database class
from gen3.utils.database import Gen3Database

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

# Channels where strikes don't count (hard-coded exemptions)
STRIKE_EXEMPT_CHANNEL_IDS = {900659338069295125}

_ = Translator("Gen3", __file__)


def contains_emoji(text: str) -> bool:
    """Check if the text contains any emojis (Unicode emojis, Discord custom emojis, or emoji shortcodes)."""
    # Unicode emoji pattern - covers most standard emojis
    unicode_emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F7E0-\U0001F7EB"  # geometric shapes
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
        "]+",
        flags=re.UNICODE
    )

    # Discord custom emoji pattern <:name:id> or <a:name:id> for animated
    discord_emoji_pattern = re.compile(r'<a?:\w+:\d+>')

    # Emoji shortcode pattern :name: (like :green_circle:, :thinking:, etc.)
    emoji_shortcode_pattern = re.compile(r':[a-zA-Z0-9_+-]+:')

    return bool(unicode_emoji_pattern.search(text)) or bool(discord_emoji_pattern.search(text)) or bool(
        emoji_shortcode_pattern.search(text))


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
                "reason": f"Message accepted! Next person must include the word '{selected_word}'",
                "selected_word": selected_word,
                "word_position": word_position
            }
        else:
            return {
                "passes": True,
                "reason": "No meaningful words found to select. Message accepted!",
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
                "reason": f"Great! Your message contained '{current_required_word}'. Next person must include '{selected_word}'",
                "selected_word": selected_word,
                "word_position": word_position
            }
        else:
            # Keep the same required word since no new words to select
            return {
                "passes": True,
                "reason": f"Message accepted! Next person still needs to include '{current_required_word}'",
                "selected_word": None,
                "word_position": None
            }
    else:
        # Message fails - doesn't contain required word
        return {
            "passes": False,
            "reason": f"Oops! Your message must contain the word '{current_required_word}' to continue the chain!"
        }


async def check_gen3_rules(content: str, current_strikes: int = 0, active_rule: str | None = None) -> dict:
    """
    Flexible rule checker for gen3 events. Dispatches to the active rule.
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has
        active_rule: Optional explicit rule selector (overrides global when provided)
    
    Returns:
        dict: {"passes": bool, "reason": str, "selected_word": str|None, "word_position": int|None}
    """
    # Use provided rule if available; otherwise fallback to global (keeps tests/backcompat)
    rule = (active_rule or ACTIVE_RULE) if isinstance(active_rule or ACTIVE_RULE, str) else "apple_orange"

    if rule == "word_chain":
        return await word_chain_rule(content, current_strikes)
    elif rule == "three_word":
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

        # Persist the selected rule per guild so it survives reloads
        try:
            await self.config.guild(interaction.guild).active_rule.set(ACTIVE_RULE)
        except Exception:
            # If config isn't available for any reason, continue with in-memory value only
            pass

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
        # Read persisted rule for this guild, fallback to in-memory global
        try:
            saved_rule = await self.config.guild(interaction.guild).active_rule()
        except Exception:
            saved_rule = None
        rule_key = saved_rule or ACTIVE_RULE
        await interaction.response.send_message(
            f"Current active Gen3 rule: {names.get(rule_key, rule_key)}",
            ephemeral=True,
        )

    @gen3.command(name="standings", description="View Gen3 standings: lowest strikes first, then message count")
    @app_commands.describe(user="Optionally show only this user's standing")
    @commands.guild_only()
    async def standings(self, interaction: discord.Interaction, user: discord.Member | None = None):
        guild = interaction.guild
        try:
            active_rows = await db.fetch_standings(guild.id)
            struck_rows = await db.fetch_struck_out(guild.id)
        except Exception:
            await interaction.response.send_message("Could not fetch standings due to a database error.",
                                                    ephemeral=True)
            return

        def to_tuple(r):
            try:
                uid = int(r["user_id"])  # asyncpg.Record supports key access
                strikes = int(r["strikes"])
                msg_count = int(r["msg_count"])
            except Exception:
                uid = int(r[0])
                strikes = int(r[1])
                msg_count = int(r[2])
            return uid, strikes, msg_count

        def format_rows(rows, start_pos: int = 1):
            lines = []
            pos = start_pos
            for r in rows:
                uid, strikes, msg_count = to_tuple(r)
                member = guild.get_member(uid)
                name = member.mention if member else f"<@{uid}>"
                lines.append(f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs")
                pos += 1
            return lines

        def find_user_position(rows, target_id: int):
            pos = 1
            for r in rows:
                uid, strikes, msg_count = to_tuple(r)
                if uid == target_id:
                    return pos, strikes, msg_count
                pos += 1
            return None

        if user:
            # Show only this user's standing
            found = find_user_position(active_rows, user.id)
            # Use member from cache if available; otherwise fall back to provided user
            member = guild.get_member(user.id) or user
            display_name = getattr(member, "display_name", getattr(user, "display_name", str(user)))
            embed_title = f"{display_name}'s Gen3 Standing"
            embed = discord.Embed(title=embed_title, color=discord.Color.blurple())
            # Set the user's avatar as the embed thumbnail for a more personal look
            avatar_url = None
            try:
                avatar_url = member.display_avatar.url  # Preferred in discord.py 2.x
            except Exception:
                try:
                    avatar_url = member.avatar.url  # Legacy attribute fallback
                except Exception:
                    try:
                        avatar_url = member.default_avatar.url
                    except Exception:
                        avatar_url = None
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            if found:
                pos, strikes, msg_count = found
                name = member.mention if isinstance(member, discord.Member) else f"<@{user.id}>"
                line = f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs"
                embed.add_field(name="Active Players", value=line, inline=False)
            else:
                found = find_user_position(struck_rows, user.id)
                if found:
                    pos, strikes, msg_count = found
                    name = member.mention if isinstance(member, discord.Member) else f"<@{user.id}>"
                    line = f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs"
                    embed.add_field(name="Striked Out :(", value=line, inline=False)
                else:
                    embed.description = f"{user.mention} has no recorded activity yet."
            await interaction.response.send_message(embed=embed)
            return

        # Default: show top 10 active and top 10 struck-out
        top_active = list(active_rows[:10]) if hasattr(active_rows, "__getitem__") else active_rows
        top_struck = list(struck_rows[:10]) if hasattr(struck_rows, "__getitem__") else struck_rows

        active_lines = format_rows(top_active, start_pos=1)
        struck_lines = format_rows(top_struck, start_pos=1)

        embed = discord.Embed(title="Gen3 Standings!", color=discord.Color.blurple())
        embed.description = "Sorted by lowest strikes first, then by message count to break ties"
        if active_lines:
            active_text = "\n".join(active_lines)
            # Append summary if more beyond top 10
            extra = max(len(active_rows) - 10, 0)
            if extra > 0:
                active_text += f"\n+{extra} more outside top 10 standings"
        else:
            active_text = "No active participants yet."
        embed.add_field(name="Active Players", value=active_text[:1024], inline=False)

        if struck_lines:
            struck_text = "\n".join(struck_lines)
        else:
            struck_text = "None"
        embed.add_field(name="Striked Out :(", value=struck_text[:1024], inline=False)

        await interaction.response.send_message(embed=embed)

    @gen3.command(name="toggle", description="Enable or disable Gen3 in a specific channel")
    @app_commands.describe(channel="The channel to configure Gen3 for")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def gen3_toggle(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Enable or disable Gen3 processing for a specific channel (per guild)."""
        # Double-check permissions similar to Emote cog style
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        # Toggle channel in the enabled_channels list for this guild
        async with self.config.guild(interaction.guild).enabled_channels() as enabled_channels:
            if channel.id in enabled_channels:
                enabled_channels.remove(channel.id)
                await interaction.response.send_message(
                    f"Gen3 has been disabled in {channel.mention} 🚫",
                    ephemeral=False,
                )
            else:
                enabled_channels.append(channel.id)
                await interaction.response.send_message(
                    f"Gen3 has been enabled in {channel.mention} ✅",
                    ephemeral=False,
                )

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Determine whether this channel is enabled for Gen3
        channel_is_enabled = False
        if message.guild:
            try:
                enabled_channels = await self.config.guild(message.guild).enabled_channels()
                if enabled_channels:
                    channel_is_enabled = message.channel.id in enabled_channels
                else:
                    # Backward-compat: if no channels configured yet, fall back to name-based defaults
                    monitored_channels = ["private-bot-commands", "general-3"]
                    channel_is_enabled = message.channel.name.lower() in monitored_channels
            except Exception:
                # If config isn’t available for some reason, fall back to original behavior
                monitored_channels = ["private-bot-commands", "general-3"]
                channel_is_enabled = message.channel.name.lower() in monitored_channels

        if channel_is_enabled:
            # Track participation: increment message count, except in exempt channels
            try:
                ch_id = getattr(message.channel, "id", None)
            except Exception:
                ch_id = None
            try:
                if message.guild and ch_id not in STRIKE_EXEMPT_CHANNEL_IDS:
                    await db.increment_msg_count(message.author.id, message.guild.id)
            except Exception:
                pass

            # Punish: strike for image attachments and/or emojis; do NOT delete the message
            violation_reasons = []

            # Check for image attachments
            if message.attachments:
                for attachment in message.attachments:
                    ct = getattr(attachment, "content_type", None) or ""
                    filename = attachment.filename.lower() if attachment.filename else ""
                    if ct.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                        violation_reasons.append("Images are not allowed in your message!")
                        break

            # Check for emojis in the content
            try:
                text_to_check = message.content or ""
            except Exception:
                text_to_check = ""
            if text_to_check and contains_emoji(text_to_check):
                violation_reasons.append("Emojis/emotes are not allowed in your message!")

            if violation_reasons:
                # Apply a single strike with combined reasons and stop further processing
                reason_text = "\n".join(violation_reasons)
                await self.apply_strike_to_message(message, reason_text=reason_text, show_typing=False)
                return

            # Ignore owner’s test bang commands in these channels
            if not (message.author.id == 138148168360656896 and message.content.startswith("!")):
                await self.handle_gen3_event(message)

    @gen3.command(name="remove_a_strike", description="Remove a single strike from a user")
    @app_commands.describe(user="User to remove a strike from")
    @commands.guild_only()
    @commands.is_owner()
    async def remove_a_strike(self, interaction: discord.Interaction, user: discord.Member):
        new_count = await db.decrease_strike(user.id, interaction.guild_id)

        if new_count < 3:
            # Unblock user in any enabled Gen3 channels (or default fallbacks)
            try:
                enabled_ids = await self.config.guild(interaction.guild).enabled_channels()
            except Exception:
                enabled_ids = []

            cleared_any = False
            if enabled_ids:
                for ch_id in enabled_ids:
                    ch = interaction.guild.get_channel(ch_id)
                    if isinstance(ch, discord.TextChannel):
                        try:
                            await ch.set_permissions(user, overwrite=None, reason="Strike count below maximum strikes")
                            cleared_any = True
                        except Exception:
                            pass

            # Fallback to name-based defaults if no enabled channels configured or none cleared
            if not cleared_any:
                for name in ["private-bot-commands", "general-3"]:
                    ch = discord.utils.get(interaction.guild.channels, name=name)
                    if ch:
                        try:
                            await ch.set_permissions(user, overwrite=None, reason="Strike count below maximum strikes")
                            cleared_any = True
                        except Exception:
                            pass

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

    @gen3.command(name="edit_msg", description="Edit a previous bot message in this channel")
    @app_commands.describe(
        message_id="The message ID of the bot message to edit (must be in this channel)"
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_messages=True)
    async def edit_msg(self, interaction: discord.Interaction, message_id: str):
        """Edit a prior message authored by this bot in the current channel.
        Uses a modal to collect the new message content.
        """
        # Parse the message ID
        try:
            target_id = int(str(message_id).strip())
        except Exception:
            await interaction.response.send_message(
                "Invalid message ID. Please provide the numeric ID of the message.",
                ephemeral=True,
            )
            return

        channel = interaction.channel

        # Determine this bot's user id
        bot_user_id = None
        try:
            bot_user_id = self.bot.user.id  # Red's bot
        except Exception:
            try:
                bot_user_id = interaction.client.user.id  # discord.Client
            except Exception:
                bot_user_id = None

        # Try fetching the message directly by ID first
        target_msg: discord.Message | None = None
        try:
            target_msg = await channel.fetch_message(target_id)
        except discord.NotFound:
            # Fallback: scan recent history just in case
            try:
                async for m in channel.history(limit=2000, oldest_first=True):
                    if m.id == target_id:
                        target_msg = m
                        break
            except Exception:
                pass
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to view messages in this channel.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            # As a fallback, try a manual history scan
            try:
                async for m in channel.history(limit=2000, oldest_first=True):
                    if m.id == target_id:
                        target_msg = m
                        break
            except Exception:
                pass

        if target_msg is None:
            await interaction.response.send_message(
                "I couldn't find a message with that ID in this channel.",
                ephemeral=True,
            )
            return

        # Ensure the message was authored by this bot
        author_id = getattr(getattr(target_msg, "author", None), "id", None)
        if bot_user_id is None or author_id != bot_user_id:
            await interaction.response.send_message(
                "That message was not sent by me, so I can't edit it.",
                ephemeral=True,
            )
            return

        # Build and show a modal to collect the new content
        class EditMessageModal(discord.ui.Modal):
            def __init__(self, target: discord.Message):
                super().__init__(title="Edit Bot Message")
                self.target = target
                # Prefill with current content up to 2000 characters
                try:
                    current = (target.content or "")[:2000]
                except Exception:
                    current = ""
                self.new_content = discord.ui.TextInput(
                    label="New content",
                    style=discord.TextStyle.paragraph,
                    required=True,
                    max_length=2000,
                    placeholder="Enter the new message content...",
                    default=current,
                )
                self.add_item(self.new_content)

            async def on_submit(self, modal_interaction: discord.Interaction):
                content = (self.new_content.value or "").strip()
                if not content:
                    await modal_interaction.response.send_message(
                        "Content cannot be empty.", ephemeral=True
                    )
                    return
                try:
                    await self.target.edit(content=content)
                except discord.Forbidden:
                    await modal_interaction.response.send_message(
                        "I wasn't able to edit that message due to missing permissions.",
                        ephemeral=True,
                    )
                    return
                except discord.HTTPException as e:
                    await modal_interaction.response.send_message(
                        f"Failed to edit the message: {e}",
                        ephemeral=True,
                    )
                    return

                await modal_interaction.response.send_message(
                    "Message updated successfully. ✅", ephemeral=True
                )

            async def on_error(self, modal_interaction: discord.Interaction, error: Exception) -> None:
                try:
                    if modal_interaction.response.is_done():
                        await modal_interaction.followup.send(
                            "An unexpected error occurred while processing the modal.",
                            ephemeral=True,
                        )
                    else:
                        await modal_interaction.response.send_message(
                            "An unexpected error occurred while processing the modal.",
                            ephemeral=True,
                        )
                except Exception:
                    pass

        await interaction.response.send_modal(EditMessageModal(target_msg))

    async def handle_gen3_event(self, message: discord.Message):
        content = message.clean_content
        channel = message.channel
        guild_id = message.guild.id
        user_id = message.author.id

        strikes = await db.get_strikes(user_id, guild_id)
        # Use the persisted active rule for this guild (fallback handled in checker)
        try:
            saved_rule = await self.config.guild(message.guild).active_rule()
        except Exception:
            saved_rule = None

        analysis = await check_gen3_rules(content, strikes, active_rule=saved_rule)
        if analysis.get("passes", False):
            # Rule check passed - add emoji reaction if word was selected
            if analysis.get("selected_word") and analysis.get("word_position"):
                word_position = analysis.get("word_position")
                # Generate emoji for any position dynamically
                emoji = get_position_emoji(word_position)
                await message.add_reaction(emoji)
        else:
            await self.apply_strike_to_message(message, analysis.get('reason'), show_typing=True)

    async def apply_strike_to_message(self, message: discord.Message, reason_text: str | None = None,
                                      show_typing: bool = False):
        """
        Shared strike application logic used by rule violations and manual strikes.
        - Increments strike
        - Handles 3-strike lockout and reset
        - Adds ❌ reaction
        - Sends appropriate reply
        """
        try:
            if show_typing:
                try:
                    await message.channel.typing()
                except Exception:
                    pass

            if message is None or message.guild is None or message.author is None:
                return

            guild_id = message.guild.id
            user = message.author
            channel = message.channel

            # Determine if channel is strike-exempt (strikes paused here)
            try:
                ch_id = getattr(channel, "id", None)
            except Exception:
                ch_id = None
            exempt_channel = ch_id in STRIKE_EXEMPT_CHANNEL_IDS

            # Compute strike count (increment only when not exempt)
            if exempt_channel:
                current_strikes = await db.get_strikes(user.id, guild_id)
            else:
                current_strikes = await db.increment_strike(user.id, guild_id)

            if exempt_channel:
                # In strike-exempt channels: warn only, do not add a strike or lock out
                alert_lines = [
                    "**Rule Violation Alert!**",
                    "**Gen3 Rule Alert!**",
                    "**Strike Warning!**",
                    "**Rule Check Failed!**",
                    "**Alert! Rule Violation!**"
                ]
                alert_line = random.choice(alert_lines)
                reason_section = f"{reason_text}\n\n" if reason_text else ""
                try:
                    await message.reply(
                        f"{alert_line} 🚨\n"
                        f"{reason_section}"
                        f"Strikes are paused in this channel. No strike has been added. This is just a warning. ⚠️",
                        mention_author=True
                    )
                except Exception:
                    pass
                try:
                    await message.add_reaction("❌")
                except Exception:
                    pass
                return

            if current_strikes >= 3:
                # Revoke posting privileges
                try:
                    await channel.set_permissions(
                        user,
                        send_messages=False,
                        reason="3 strikes reached"
                    )
                except Exception:
                    pass

                # React and notify
                try:
                    await message.add_reaction("❌")
                except Exception:
                    pass

                first_lines = [
                    "**Strike Out!**",
                    "**Game Over!**",
                    "**Maximum Strikes!**",
                    "**Three Strikes!**",
                    "**Oops!**",
                    "**Alert!**"
                ]
                first_line = random.choice(first_lines)
                try:
                    await message.reply(
                        f"{first_line} 🚨🚨🚨\n"
                        f"{user.mention}, you've reached 3 strikes! No more posting for you... 🚫\n"
                        f"Better luck next time! ✨"
                    )
                except Exception:
                    pass
            else:
                # Warn the user
                alert_lines = [
                    "**Rule Violation Alert!**",
                    "**Gen3 Rule Alert!**",
                    "**Strike Warning!**",
                    "**Rule Check Failed!**",
                    "**Alert! Rule Violation!**"
                ]
                alert_line = random.choice(alert_lines)
                strikes_left = 3 - current_strikes

                reason_section = f"{reason_text}\n\n" if reason_text else ""

                try:
                    await message.reply(
                        f"{alert_line} 🚨\n"
                        f"{reason_section}"
                        f"Strike {current_strikes}/3 - "
                        f"You have {strikes_left} {'tries' if strikes_left > 1 else 'try'} remaining! ⚠️\n\n",
                        mention_author=True
                    )
                except Exception:
                    pass

                try:
                    await message.add_reaction("❌")
                except Exception:
                    pass
        except Exception:
            # Never raise from shared handler
            pass

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_reaction_add(self, reaction: discord.Reaction, user):
        """Gen3 reaction handlers:
        - Owner ❌ on a user's message in enabled channels -> apply a strike
        - Mod ❓/❔ on a message in enabled channels -> show analysis for that message
        """
        try:
            # ignore bots
            if getattr(user, "bot", False):
                return

            message: discord.Message = reaction.message
            if message is None or message.guild is None:
                return

            # Respect Gen3 enabled channels setting (with fallback to defaults)
            channel_is_enabled = False
            try:
                enabled_channels = await self.config.guild(message.guild).enabled_channels()
                if enabled_channels:
                    channel_is_enabled = message.channel.id in enabled_channels
                else:
                    monitored_channels = ["private-bot-commands", "general-3"]
                    channel_is_enabled = message.channel.name.lower() in monitored_channels
            except Exception:
                monitored_channels = ["private-bot-commands", "general-3"]
                channel_is_enabled = message.channel.name.lower() in monitored_channels

            if not channel_is_enabled:
                return

            # Determine emoji (only process unicode)
            emoji = reaction.emoji
            emoji_str = emoji if isinstance(emoji, str) else None

            # Owner manual strike via ❌
            if emoji_str == "❌" and user.id == 138148168360656896:
                # Don't strike bot messages
                if message.author and not getattr(message.author, "bot", False):
                    await self.apply_strike_to_message(message, reason_text=None, show_typing=False)
                return

            # Mod analysis via question mark emoji
            if emoji_str in {"❓", "❔"}:
                # permissions: mods only (or owner)
                is_owner = False
                try:
                    is_owner = await self.bot.is_owner(user)
                except Exception:
                    pass
                perms = getattr(user, "guild_permissions", None)
                is_mod = False
                if perms:
                    is_mod = (
                            perms.administrator
                            or perms.manage_guild
                            or getattr(perms, "moderate_members", False)
                            or perms.manage_messages
                    )
                if not (is_owner or is_mod):
                    return

                # Compute analysis for the target message
                try:
                    content = message.clean_content
                    guild_id = message.guild.id
                    author_id = message.author.id if message.author else None
                    current_strikes = await db.get_strikes(author_id, guild_id) if author_id else 0
                    try:
                        saved_rule = await self.config.guild(message.guild).active_rule()
                    except Exception:
                        saved_rule = None

                    analysis = await check_gen3_rules(content, current_strikes, active_rule=saved_rule)
                    pretty = json.dumps(analysis, indent=2, ensure_ascii=False)
                    await message.channel.send(f"```json\n{pretty}\n```")
                except Exception:
                    pass
                return
        except Exception:
            # Listener should never raise
            pass
