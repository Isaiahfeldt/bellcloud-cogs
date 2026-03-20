MANIFEST: dict[str, dict[str, dict]] = {
    "Gen3Cog": {
        "active_rule": {
            "scope": "GUILD",
            "type": "enum",
            "display": "Active Rule",
            # Values verified against gen3/slash_commands.py app_commands.choices
            "options": ["apple_orange", "word_chain", "three_word"],
        },
        "enabled_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Enabled Channels",
        },
        "demo_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Demo Channels",
        },
    },
    "Emotes": {
        "blacklisted_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Blacklisted Channels",
        },
        "emoji_blacklisted_channels": {
            "scope": "GUILD",
            "type": "channel_list",
            "display": "Emoji Blacklisted Channels",
        },
    },
}

# Cog enable/disable is handled entirely via Red's built-in COG_DISABLE_SETTINGS mechanism
# (bot._disabled_cog_cache). No guild_enabled key is needed in MANIFEST.
# Red automatically suppresses commands when a cog is disabled; event listeners
# (e.g. on_message in Gen3Cog) must check bot.cog_disabled_in_guild_raw() themselves.
KNOWN_COGS: list[str] = ["Gen3Cog", "Emotes"]


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
    if t == "string_list":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if t == "string":
        return isinstance(value, str)
    return False
