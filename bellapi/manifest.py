MANIFEST: dict[str, dict[str, dict]] = {
    "Gen3Cog": {
        "active_rule": {
            "scope": "GUILD",
            "type": "enum",
            "display": "Active Rule",
            "options": ["apple_orange", "word_chain", "three_word"],
            "access": "guild",
        },
        "enabled_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Enabled Channels",
            "access": "guild",
        },
        "demo_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Demo Channels",
            "access": "owner",
        },
    },
    "Emotes": {
        "blacklisted_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Blacklisted Channels",
            "access": "guild",
        },
        "emoji_blacklisted_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Emoji Blacklisted Channels",
            "access": "guild",
        },
    },
    "Admin": {
        "announce_channel": {
            "scope": "GUILD",
            "type": "channel",
            "display": "Announcement Channel",
            "access": "owner",
        },
        "selfroles": {
            "scope": "GUILD",
            "type": "role_list",
            "display": "Self-Assignable Roles",
            "access": "guild",
        },
    },
    "Mod": {
        "delete_repeats": {
            "scope": "GUILD",
            "type": "int",
            "display": "Delete Repeated Messages (max count, -1 to disable)",
            "min": -1,
            "access": "guild",
        },
        "respect_hierarchy": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Respect Role Hierarchy",
            "access": "guild",
        },
        "delete_delay": {
            "scope": "GUILD",
            "type": "int",
            "display": "Delete Delay (seconds, -1 to disable)",
            "min": -1,
            "max": 600,
            "access": "guild",
        },
        "reinvite_on_unban": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Reinvite on Unban",
            "access": "guild",
        },
        "dm_on_kickban": {
            "scope": "GUILD",
            "type": "bool",
            "display": "DM User on Kick/Ban",
            "access": "guild",
        },
        "require_reason": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Require Reason for Mod Actions",
            "access": "guild",
        },
        "default_days": {
            "scope": "GUILD",
            "type": "int",
            "display": "Default Ban Message Delete Days",
            "min": 0,
            "max": 7,
            "access": "guild",
        },
        "default_tempban_duration": {
            "scope": "GUILD",
            "type": "int",
            "display": "Default Tempban Duration (seconds)",
            "min": 60,
            "access": "guild",
        },
        "track_nicknames": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Track Nickname Changes",
            "access": "guild",
        },
        "ban_show_extra": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Show Extra Info in Ban Messages",
            "access": "guild",
        },
        "ban_extra_embed_title": {
            "scope": "GUILD",
            "type": "string",
            "display": "Ban Extra Embed Title",
            "access": "guild",
        },
        "ban_extra_embed_contents": {
            "scope": "GUILD",
            "type": "string",
            "display": "Ban Extra Embed Contents",
            "access": "guild",
        },
    },
    "Cleanup": {
        "notify": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Notify Users of Cleanup",
            "access": "guild",
        },
    },
}

# Cog enable/disable is handled entirely via Red's built-in COG_DISABLE_SETTINGS mechanism
# (bot._disabled_cog_cache). No guild_enabled key is needed in MANIFEST.
# Red automatically suppresses commands when a cog is disabled; event listeners
# (e.g. on_message in Gen3Cog) must check bot.cog_disabled_in_guild_raw() themselves.

# OWNER_ONLY_COGS: entire cogs hidden from guild managers in the dashboard.
# Per-key access is controlled by the 'access' field in MANIFEST above.
OWNER_ONLY_COGS: frozenset[str] = frozenset({
    "BellApi",
    "Cleanup",
    "CycleStatus",
    "CustomHelp",
    "Downloader",
    "Say",
})


def validate_value(cog_name: str, key: str, value) -> bool:
    """Return True if value is valid for the given cog/key per the manifest."""
    cog_keys = MANIFEST.get(cog_name)
    if cog_keys is None:
        return False
    meta = cog_keys.get(key)
    if meta is None:
        return False

    t = meta["type"]
    if t == "bool":
        return isinstance(value, bool)
    if t == "enum":
        return value in meta.get("options", [])
    if t == "channel_list":
        return isinstance(value, list) and all(isinstance(v, int) for v in value)
    if t == "role_list":
        return isinstance(value, list) and all(isinstance(v, int) for v in value)
    if t == "string_list":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if t == "string":
        return isinstance(value, str)
    if t == "channel":
        return value is None or isinstance(value, int)
    if t == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if "min" in meta and value < meta["min"]:
            return False
        if "max" in meta and value > meta["max"]:
            return False
        return True
    return False


def key_access(cog_name: str, key: str) -> str:
    """
    Return 'guild' or 'owner' for the given cog/key.
    Returns 'owner' for any unknown cog or key (fail closed).
    All keys in MANIFEST are required to have an explicit 'access' field.
    """
    meta = MANIFEST.get(cog_name, {}).get(key)
    if meta is None:
        return "owner"
    return meta["access"]
