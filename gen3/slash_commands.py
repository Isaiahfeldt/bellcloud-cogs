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
from datetime import datetime

import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from gen3.rules.apple_orange import apple_orange_rule
# Import the 3-word rule from scratch file for flexible rules
from gen3.rules.three_word import three_word_rule
from gen3.rules.word_chain import get_position_emoji, reset_word_chain_state, word_chain_rule
# Use the dedicated Gen3Database class
from gen3.utils.database import Gen3Database

# Create a global database instance
db = Gen3Database()

# Active rule selector (global for simplicity/minimal changes)
# Possible values: "apple_orange", "word_chain", "three_word"
ACTIVE_RULE = "apple_orange"

# Toggle to preserve legacy numbered standings formatting (disabled for alphabetical view)
USE_LEGACY_STANDINGS_LAYOUT = False

# Channels where strikes don't count (hard-coded exemptions)
STRIKE_EXEMPT_CHANNEL_IDS = {}

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


def format_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    try:
        return dt.strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        return str(dt)


def format_short_date(dt: datetime | None) -> str:
    if not dt:
        return "On going"
    try:
        return dt.strftime("%m/%d/%y")
    except Exception:
        return str(dt)


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
    season = app_commands.Group(name="season", description="Manage Gen3 seasons", parent=gen3)

    def __init__(self):
        super().__init__()

    async def _get_enabled_channel_ids(self, guild: discord.Guild | None) -> list[int]:
        if guild is None:
            return []

        try:
            enabled_ids = await self.config.guild(guild).enabled_channels()
        except Exception:
            return []

        return enabled_ids or []

    async def _get_enabled_text_channels(self, guild: discord.Guild | None) -> list[discord.TextChannel]:
        enabled_channels: list[discord.TextChannel] = []
        channel_ids = await self._get_enabled_channel_ids(guild)

        if guild is None:
            return enabled_channels

        for ch_id in channel_ids:
            channel = guild.get_channel(ch_id)
            if isinstance(channel, discord.TextChannel):
                enabled_channels.append(channel)

        return enabled_channels

    async def _channel_is_enabled(self, channel: discord.abc.GuildChannel | None) -> bool:
        if channel is None:
            return False

        channel_ids = await self._get_enabled_channel_ids(getattr(channel, "guild", None))
        if not channel_ids:
            return False

        return getattr(channel, "id", None) in channel_ids

    async def _channel_is_demo(self, channel: discord.abc.GuildChannel | None) -> bool:
        if channel is None:
            return False

        try:
            demo_channels = await self.config.guild(channel.guild).demo_channels()
            print(f"demo channels: {demo_channels}")
        except Exception:
            return False

        demo_channels = demo_channels or []
        return getattr(channel, "id", None) in demo_channels

    async def _get_guild_rule(self, guild: discord.Guild | None) -> str | None:
        if guild is None:
            return None
        try:
            return await self.config.guild(guild).active_rule()
        except Exception:
            return None

    async def _get_channel_rule_override(
        self, guild: discord.Guild | None, channel: discord.abc.GuildChannel | None
    ) -> str | None:
        if guild is None or channel is None:
            return None

        try:
            overrides = await self.config.guild(guild).channel_rule_overrides()
        except Exception:
            return None

        if not overrides:
            return None

        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return None

        return overrides.get(str(channel_id)) or overrides.get(channel_id)

    async def _get_effective_rule(
        self, guild: discord.Guild | None, channel: discord.abc.GuildChannel | None
    ) -> str:
        override_rule = await self._get_channel_rule_override(guild, channel)
        if override_rule:
            return override_rule

        saved_rule = await self._get_guild_rule(guild)
        if saved_rule:
            return saved_rule

        return ACTIVE_RULE

    # Owner-only commands near the top
    @gen3.command(name="set_rule", description="Set the active Gen3 rule")
    @app_commands.describe(
        rule="Choose which rule to enforce",
        channel="Optionally override the rule for a single channel",
    )
    @app_commands.choices(
        rule=[
            app_commands.Choice(name="Apple/Orange (demo)", value="apple_orange"),
            app_commands.Choice(name="Word Chain", value="word_chain"),
            app_commands.Choice(name="Three Word (exactly 3 words)", value="three_word"),
        ]
    )
    @commands.guild_only()
    @commands.is_owner()
    async def set_rule(
        self,
        interaction: discord.Interaction,
        rule: app_commands.Choice[str],
        channel: discord.TextChannel | None = None,
    ):
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        rule_value = rule.value
        # Friendly confirmation
        names = {
            "apple_orange": "Apple/Orange (demo)",
            "word_chain": "Word Chain",
            "three_word": "Three Word",
        }

        if channel:
            try:
                async with self.config.guild(interaction.guild).channel_rule_overrides() as overrides:
                    overrides[str(channel.id)] = rule_value
            except Exception:
                pass

            await interaction.response.send_message(
                f"Active Gen3 rule for {channel.mention} set to: {names.get(rule_value, rule_value)} (channel override)",
                ephemeral=False,
            )
        else:
            global ACTIVE_RULE
            ACTIVE_RULE = rule_value

            # Persist the selected rule per guild so it survives reloads
            try:
                await self.config.guild(interaction.guild).active_rule.set(ACTIVE_RULE)
            except Exception:
                # If config isn't available for any reason, continue with in-memory value only
                pass

            await interaction.response.send_message(
                f"Active Gen3 rule set to: {names.get(ACTIVE_RULE, ACTIVE_RULE)}",
                ephemeral=False,
            )

        # Reset the word-chain state (fresh start when rules change)
        reset_word_chain_state()

    @season.command(name="new", description="End the current Gen3 season and start a new one")
    @app_commands.describe(label="Optional label for the new season")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def season_new(self, interaction: discord.Interaction, label: str | None = None):
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        old_season, new_season = await db.start_new_season(interaction.guild_id, label=label)

        cleared_users: set[int] = set()
        if old_season:
            try:
                struck_rows = await db.fetch_struck_out_for_season(
                    interaction.guild_id, int(old_season["id"])
                )
            except Exception:
                struck_rows = []

            if struck_rows:
                target_channels = await self._get_enabled_text_channels(interaction.guild)

                def extract_user_id(row) -> int:
                    try:
                        return int(row["user_id"])
                    except Exception:
                        return int(row[0])

                for row in struck_rows:
                    uid = extract_user_id(row)
                    member = interaction.guild.get_member(uid)
                    if not member:
                        continue
                    for ch in target_channels:
                        try:
                            await ch.set_permissions(member, overwrite=None, reason="Gen3 season reset")
                            cleared_users.add(uid)
                        except Exception:
                            continue

        embed = discord.Embed(title="New Gen3 Season Started!", color=discord.Color.green())
        if old_season:
            embed.add_field(
                name="Previous Season",
                value=(
                    f"ID: {old_season['id']}\n"
                    f"Label: {old_season.get('label') or '—'}\n"
                    f"Duration: {format_dt(old_season.get('started_at'))} → {format_dt(old_season.get('ended_at'))}"
                ),
                inline=False,
            )

        embed.add_field(
            name="Active Season",
            value=(
                f"ID: {new_season['id']}\n"
                f"Label: {new_season.get('label') or '—'}\n"
                f"Started: {format_dt(new_season.get('started_at'))}"
            ),
            inline=False,
        )

        if cleared_users:
            embed.set_footer(text=f"Cleared channel overrides for {len(cleared_users)} users from the previous season.")

        await interaction.response.send_message(embed=embed)

    @season.command(name="list", description="List all Gen3 seasons for this guild")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def season_list(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        seasons = await db.list_seasons(interaction.guild_id)
        active = await db.get_active_season(interaction.guild_id)
        active_id = int(active["id"]) if active else None

        embed = discord.Embed(title="Gen3 Seasons", color=discord.Color.blurple())
        if not seasons:
            embed.description = "No seasons recorded for this guild yet."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        multiple_seasons = len(seasons) > 1

        async def get_winner_mention(season_id: int) -> str | None:
            standings = await db.fetch_standings_for_season(interaction.guild_id, season_id)
            if standings:
                try:
                    uid = int(standings[0]["user_id"])
                except Exception:
                    uid = int(standings[0][0])
                return f"<@{uid}>"
            struck = await db.fetch_struck_out_for_season(interaction.guild_id, season_id)
            if struck:
                try:
                    uid = int(struck[0]["user_id"])
                except Exception:
                    uid = int(struck[0][0])
                return f"<@{uid}>"
            return None

        lines = []
        winners: dict[int, str | None] = {}
        if multiple_seasons:
            for season in seasons:
                season_id = int(season["id"])
                if season_id == active_id and season.get("is_active"):
                    continue
                winners[season_id] = await get_winner_mention(season_id)

        for idx, season in enumerate(seasons, start=1):
            season_id = int(season["id"])
            start_fmt = format_short_date(season.get("started_at"))
            end_fmt = format_short_date(season.get("ended_at")) if season.get("ended_at") else "On going"
            line = f"{idx}. {season.get('label') or '—'}: {start_fmt} - {end_fmt}"
            if season_id == active_id and season.get("is_active"):
                line += " 🟢"
            elif multiple_seasons:
                winner = winners.get(season_id)
                if winner:
                    line += f" - {winner}"
            lines.append(line)

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @season.command(name="standings", description="View standings for a specific season")
    @app_commands.describe(season_id="Season ID to view")
    @commands.guild_only()
    async def season_standings(self, interaction: discord.Interaction, season_id: int):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        seasons = await db.list_seasons(interaction.guild_id)
        target = next((s for s in seasons if int(s["id"]) == season_id), None)
        if not target:
            await interaction.response.send_message("Season not found for this guild.", ephemeral=True)
            return

        active_rows = await db.fetch_standings_for_season(interaction.guild_id, season_id)
        struck_rows = await db.fetch_struck_out_for_season(interaction.guild_id, season_id)

        def to_tuple(r):
            try:
                uid = int(r["user_id"])
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
                member = interaction.guild.get_member(uid)
                name = member.mention if member else f"<@{uid}>"
                lines.append(f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs")
                pos += 1
            return lines

        start_fmt = format_short_date(target.get("started_at"))
        end_fmt = format_short_date(target.get("ended_at")) if target.get("ended_at") else "On going"
        label_text = target.get("label") or "—"
        active_marker = " 🟢" if target.get("is_active") else ""

        embed = discord.Embed(
            title=f"Gen3 Standings - {label_text}!",
            description=f"{start_fmt} - {end_fmt}{active_marker}",
            color=discord.Color.blurple(),
        )

        active_lines = format_rows(active_rows)
        struck_lines = format_rows(struck_rows)

        embed.add_field(name="Active Players", value="\n".join(active_lines) or "None", inline=False)
        embed.add_field(name="Struck Out :(", value="\n".join(struck_lines) or "None", inline=False)

        await interaction.response.send_message(embed=embed)

    @season_standings.autocomplete("season_id")
    async def season_standings_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        if interaction.guild is None:
            return []

        seasons = await db.list_seasons(interaction.guild_id)
        if not seasons:
            return []

        active_id = next((int(s["id"]) for s in seasons if s.get("is_active")), None)

        choices: list[app_commands.Choice[int]] = []
        for idx, season in enumerate(seasons, start=1):
            season_id = int(season["id"])
            start_fmt = format_short_date(season.get("started_at"))
            end_fmt = format_short_date(season.get("ended_at")) if season.get("ended_at") else "On going"
            name = f"{idx}. {season.get('label') or '—'}: {start_fmt} - {end_fmt}"
            if season_id == active_id and season.get("is_active"):
                name += " 🟢"
            choices.append(app_commands.Choice(name=name, value=season_id))

        if current:
            lowered = current.lower()
            choices = [choice for choice in choices if lowered in choice.name.lower()]

        return choices[:25]

    @gen3.command(name="remove_strike", description="Remove one or more strikes from a user")
    @app_commands.describe(user="User to remove strikes from", value="Number of strikes to remove (1-3)")
    @commands.guild_only()
    @commands.is_owner()
    async def remove_strikes(self, interaction: discord.Interaction, user: discord.Member, value: app_commands.Range[int, 1, 3] = 1):
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        # Remove the specified number of strikes, capping at 0
        new_count = None
        for _ in range(int(value)):
            new_count = await db.decrease_strike(user.id, interaction.guild_id)
        if new_count is None:
            new_count = await db.get_strikes(user.id, interaction.guild_id)

        if new_count < 3:
            # Unblock user in any enabled Gen3 channels
            cleared_any = False
            for channel in await self._get_enabled_text_channels(interaction.guild):
                try:
                    await channel.set_permissions(
                        user,
                        overwrite=None,
                        reason="Strike count below maximum strikes",
                    )
                    cleared_any = True
                except Exception:
                    pass

        removed = int(value)
        plural = "strike" if removed == 1 else "strikes"
        await interaction.response.send_message(
            f"Removed {removed} {plural} from {user.mention}! ✨ They now have {new_count}/3 strikes.",
            ephemeral=False
        )

    @gen3.command(name="forgive", description="Forgive all strikes for a user")
    @app_commands.describe(user="User to forgive strikes for")
    @commands.guild_only()
    @commands.is_owner()
    async def forgive_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        await db.reset_strikes(user.id, interaction.guild_id)

        channel = next(iter(await self._get_enabled_text_channels(interaction.guild)), None)

        if channel:
            # Reset user permissions for the channel
            await channel.set_permissions(user, overwrite=None, reason="Strikes forgiven")

        await interaction.response.send_message(
            f"All strikes for {user.mention} have been forgiven! ✨",
            ephemeral=False
        )

    # General/admin commands
    @gen3.command(name="get_rule", description="Show the currently active Gen3 rule")
    @app_commands.describe(channel="Optionally view the rule for a specific channel")
    @commands.guild_only()
    async def get_rule(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        names = {
            "apple_orange": "Apple/Orange (demo)",
            "word_chain": "Word Chain",
            "three_word": "Three Word",
        }
        effective_rule = await self._get_effective_rule(interaction.guild, channel)
        override_rule = await self._get_channel_rule_override(interaction.guild, channel) if channel else None

        if channel:
            detail = "(channel override)" if override_rule else "(guild default)"
            await interaction.response.send_message(
                f"Current Gen3 rule for {channel.mention}: {names.get(effective_rule, effective_rule)} {detail}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"Current active Gen3 rule: {names.get(effective_rule, effective_rule)}",
                ephemeral=True,
            )

    @gen3.command(name="view_strikes", description="View current strikes for a user")
    @app_commands.describe(user="User to check strikes for")
    @commands.guild_only()
    async def view_strikes(self, interaction: discord.Interaction, user: discord.Member):
        strikes = await db.get_strikes(user.id, interaction.guild_id)
        await interaction.response.send_message(
            f"{user.mention} has {strikes}/3 strikes. Please be careful! ⚠️",
            ephemeral=False
        )

    @gen3.command(name="standings", description="View Gen3 standings alphabetically")
    @app_commands.describe(user="Optionally show only this user's standing")
    @commands.guild_only()
    async def standings(self, interaction: discord.Interaction, user: discord.Member | None = None):
        guild = interaction.guild
        active_season = await db.get_active_season(guild.id)
        season_label = None
        if active_season:
            try:
                season_label = active_season.get("label")
            except Exception:
                try:
                    season_label = active_season["label"]
                except Exception:
                    season_label = None
        embed_title = f"Gen3 Standings - {season_label}!" if season_label else "Gen3 Standings!"
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

        def format_rows_legacy(rows, start_pos: int = 1):
            lines = []
            pos = start_pos
            for r in rows:
                uid, strikes, msg_count = to_tuple(r)
                member = guild.get_member(uid)
                name = member.mention if member else f"<@{uid}>"
                lines.append(f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs")
                pos += 1
            return lines

        def format_rows_alpha(rows):
            entries = []
            for r in rows:
                uid, strikes, msg_count = to_tuple(r)
                member = guild.get_member(uid)
                mention = member.mention if member else f"<@{uid}>"
                display_name = getattr(member, "display_name", None) or str(uid)
                entries.append((display_name.casefold(), f"{mention} — {strikes}/3 strikes"))
            entries.sort(key=lambda item: item[0])
            return [entry for _, entry in entries]

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
            embed_title = f"{display_name}'s Gen3 Standing!"
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
                if USE_LEGACY_STANDINGS_LAYOUT:
                    line = f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs"
                else:
                    line = f"{name} — {strikes}/3 strikes"
                embed.add_field(name="Active Player", value=line, inline=False)
            else:
                found = find_user_position(struck_rows, user.id)
                if found:
                    pos, strikes, msg_count = found
                    name = member.mention if isinstance(member, discord.Member) else f"<@{user.id}>"
                    if USE_LEGACY_STANDINGS_LAYOUT:
                        line = f"{pos}. {name} — {strikes}/3 strikes • {msg_count} msgs"
                    else:
                        line = f"{name} — {strikes}/3 strikes"
                    embed.add_field(name="Struck Out :(", value=line, inline=False)
                else:
                    embed.description = f"{user.mention} has no recorded activity yet."
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(title=embed_title, color=discord.Color.blurple())

        if USE_LEGACY_STANDINGS_LAYOUT:
            # Default: show top 10 active and top 10 struck-out
            top_active = list(active_rows[:10]) if hasattr(active_rows, "__getitem__") else active_rows
            top_struck = list(struck_rows[:10]) if hasattr(struck_rows, "__getitem__") else struck_rows

            active_lines = format_rows_legacy(top_active, start_pos=1)
            struck_lines = format_rows_legacy(top_struck, start_pos=1)

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
        else:
            active_lines = format_rows_alpha(active_rows)
            struck_lines = format_rows_alpha(struck_rows)

            embed.description = "Sorted alphabetically by display name"
            if active_lines:
                visible_active = active_lines[:10]
                active_text = "\n".join(visible_active)
                extra = max(len(active_lines) - len(visible_active), 0)
                if extra > 0:
                    active_text += f"\n+{extra} more outside top 10 standings"
            else:
                active_text = "No active participants yet."
            embed.add_field(name="Active Players", value=active_text[:1024], inline=False)

            if struck_lines:
                visible_struck = struck_lines[:10]
                struck_text = "\n".join(visible_struck)
                extra_struck = max(len(struck_lines) - len(visible_struck), 0)
                if extra_struck > 0:
                    struck_text += f"\n+{extra_struck} more outside top 10 standings"
            else:
                struck_text = "None"
        embed.add_field(name="Struck Out :(", value=struck_text[:1024], inline=False)

        await interaction.response.send_message(embed=embed)

    @gen3.command(name="toggle", description="Enable or disable Gen3 in a specific channel")
    @app_commands.describe(
        channel="The channel to configure Gen3 for",
        demo="Enable demo mode (no strikes) instead of the normal mode",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def gen3_toggle(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        demo: bool | None = None,
    ):
        """Enable or disable Gen3 processing for a specific channel (per guild)."""
        # Double-check permissions similar to Emote cog style
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        # Toggle channel in the enabled_channels list for this guild
        async with self.config.guild(interaction.guild).enabled_channels() as enabled_channels:
            if channel.id in enabled_channels:
                if demo is not None:
                    try:
                        async with self.config.guild(interaction.guild).demo_channels() as demo_channels:
                            demo_channels = demo_channels or []
                            if demo:
                                if channel.id not in demo_channels:
                                    demo_channels.append(channel.id)
                            else:
                                if channel.id in demo_channels:
                                    demo_channels.remove(channel.id)
                    except Exception:
                        pass

                    mode_text = "demo" if demo else "normal"
                    await interaction.response.send_message(
                        f"Updated Gen3 mode for {channel.mention} to {mode_text}.", ephemeral=False
                    )
                    return

                enabled_channels.remove(channel.id)
                try:
                    async with self.config.guild(interaction.guild).demo_channels() as demo_channels:
                        demo_channels = demo_channels or []
                        if channel.id in demo_channels:
                            demo_channels.remove(channel.id)
                except Exception:
                    pass

                try:
                    async with self.config.guild(interaction.guild).channel_rule_overrides() as overrides:
                        overrides.pop(str(channel.id), None)
                        overrides.pop(channel.id, None)
                except Exception:
                    pass

                await interaction.response.send_message(
                    f"Gen3 has been disabled in {channel.mention} 🚫",
                    ephemeral=False,
                )
            else:
                enabled_channels.append(channel.id)
                try:
                    async with self.config.guild(interaction.guild).demo_channels() as demo_channels:
                        demo_channels = demo_channels or []
                        if demo:
                            if channel.id not in demo_channels:
                                demo_channels.append(channel.id)
                        elif channel.id in demo_channels:
                            demo_channels.remove(channel.id)
                except Exception:
                    pass

                if demo:
                    message_text = f"Gen3 has been enabled in {channel.mention} ✅ (demo mode, no strikes will be recorded)"
                else:
                    message_text = f"Gen3 has been enabled in {channel.mention} ✅"
                await interaction.response.send_message(
                    message_text,
                    ephemeral=False,
                )

    @gen3.command(name="edit_msg", description="Edit a previous bot message in this channel")
    @app_commands.describe(
        message_id="The message ID of the bot message to edit (must be in this channel)"
    )
    @commands.guild_only()
    @commands.is_owner()
    async def edit_msg(self, interaction: discord.Interaction, message_id: str):
        """Edit a prior message authored by this bot in the current channel.
        Uses a modal to collect the new message content.
        """
        if not interaction.user.guild_permissions.manage_guild and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
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

    # Listener placed before message-processing group
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
            channel_is_enabled = await self._channel_is_enabled(message.channel)

            if not channel_is_enabled:
                return

            # Determine emoji (only process unicode)
            emoji = reaction.emoji
            emoji_str = emoji if isinstance(emoji, str) else None

            # Owner manual strike via ❌
            if emoji_str == "❌" and user.id == 138148168360656896:
                # Don't strike bot messages
                if message.author and not getattr(message.author, "bot", False):
                    await self.apply_strike_to_message(
                        message,
                        reason_text=None,
                        show_typing=False,
                        demo_mode=await self._channel_is_demo(message.channel),
                    )
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
                    demo_mode = await self._channel_is_demo(message.channel)
                    current_strikes = 0
                    if author_id and not demo_mode:
                        current_strikes = await db.get_strikes(author_id, guild_id)
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

            # Mod strike removal via sparkle emoji
            if emoji_str == "✨":
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

                # Remove a single strike from the message author
                target_user = message.author
                if target_user is None or getattr(target_user, "bot", False):
                    return

                try:
                    new_count = await db.decrease_strike(target_user.id, message.guild.id)

                    if new_count < 3:
                        for channel in await self._get_enabled_text_channels(message.guild):
                            try:
                                await channel.set_permissions(
                                    target_user,
                                    overwrite=None,
                                    reason="Strike count below maximum strikes",
                                )
                            except Exception:
                                pass

                    removed = 1
                    plural = "strike" if removed == 1 else "strikes"
                    await message.channel.send(
                        f"Removed {removed} {plural} from {target_user.mention}! ✨ They now have {new_count}/3 strikes.",
                    )
                except Exception:
                    pass
                return
        except Exception:
            # Listener should never raise
            pass

    # on_message and supporting functions placed at the end
    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Determine whether this channel is enabled for Gen3
        channel_is_enabled = await self._channel_is_enabled(message.channel)
        demo_mode = await self._channel_is_demo(message.channel)

        print(f"demo mode: {demo_mode}")

        if channel_is_enabled:
            # Track participation: increment message count, except in exempt channels
            try:
                ch_id = getattr(message.channel, "id", None)
            except Exception:
                ch_id = None
            try:
                if message.guild and ch_id not in STRIKE_EXEMPT_CHANNEL_IDS and not demo_mode:
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
                if demo_mode:
                    await self._send_demo_warning(message, reason_text=reason_text)
                else:
                    await self.apply_strike_to_message(
                        message, reason_text=reason_text, show_typing=False, demo_mode=demo_mode
                    )
                return

            # Ignore owner’s test bang commands in these channels
            if not (message.author.id == 138148168360656896 and message.content.startswith("!")):
                await self.handle_gen3_event(message, demo_mode=demo_mode)

    async def _send_demo_warning(self, message: discord.Message, reason_text: str | None = None):
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
                f"{alert_line} 🚨 (demo mode)\n"
                f"{reason_section}"
                f"No strikes have been recorded because this channel is in demo mode.",
                mention_author=True,
            )
        except Exception:
            pass
        try:
            await message.add_reaction("❌")
        except Exception:
            pass

    async def handle_gen3_event(self, message: discord.Message, demo_mode: bool = False):
        content = message.clean_content
        channel = message.channel
        guild_id = message.guild.id
        user_id = message.author.id

        if demo_mode:
            strikes = 0
        else:
            strikes = await db.get_strikes(user_id, guild_id)
        rule_key = await self._get_effective_rule(message.guild, channel)

        analysis = await check_gen3_rules(content, strikes, active_rule=rule_key)
        if analysis.get("passes", False):
            # Rule check passed - add emoji reaction if word was selected
            if analysis.get("selected_word") and analysis.get("word_position"):
                word_position = analysis.get("word_position")
                # Generate emoji for any position dynamically
                emoji = get_position_emoji(word_position)
                await message.add_reaction(emoji)
        else:
            if demo_mode:
                await self._send_demo_warning(message, analysis.get('reason'))
            else:
                await self.apply_strike_to_message(
                    message,
                    analysis.get('reason'),
                    show_typing=True,
                    demo_mode=demo_mode,
                )

    async def apply_strike_to_message(
        self,
        message: discord.Message,
        reason_text: str | None = None,
        show_typing: bool = False,
        demo_mode: bool | None = None,
    ):
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

            if demo_mode is None:
                try:
                    demo_mode = await self._channel_is_demo(channel)
                except Exception:
                    demo_mode = False

            if demo_mode:
                await self._send_demo_warning(message, reason_text=reason_text or "Rule violation detected.")
                return

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
