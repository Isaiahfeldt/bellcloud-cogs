MANIFEST: dict[str, dict[str, dict]] = {
    "Gen3Cog": {
        "guild_enabled": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Cog Enabled",
        },
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
        "guild_enabled": {
            "scope": "GUILD",
            "type": "bool",
            "display": "Cog Enabled",
        },
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

# Which cogs use "native_flag" vs "command_disable" for per-guild enable/disable.
# Custom cogs (in bellcloud-cogs) use "native_flag". Native Red cogs use "command_disable".
DISABLE_MECHANISM: dict[str, str] = {
    "Gen3Cog": "native_flag",
    "Emotes": "native_flag",
}


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
