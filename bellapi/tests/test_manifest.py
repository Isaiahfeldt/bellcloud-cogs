import pytest
from bellapi.manifest import MANIFEST, validate_value


def test_manifest_has_gen3_keys():
    assert "Gen3Cog" in MANIFEST
    assert "active_rule" in MANIFEST["Gen3Cog"]
    assert "enabled_channels" in MANIFEST["Gen3Cog"]
    assert "demo_channels" in MANIFEST["Gen3Cog"]


def test_manifest_has_emotes_keys():
    assert "Emotes" in MANIFEST
    assert "blacklisted_channels" in MANIFEST["Emotes"]
    assert "emoji_blacklisted_channels" in MANIFEST["Emotes"]


def test_no_guild_enabled_in_manifest():
    # guild_enabled is managed by Red's native COG_DISABLE_SETTINGS, not MANIFEST
    for cog_name, keys in MANIFEST.items():
        assert "guild_enabled" not in keys, f"{cog_name} should not have guild_enabled in MANIFEST"


def test_all_entries_have_required_fields():
    for cog_name, cog_keys in MANIFEST.items():
        for key, meta in cog_keys.items():
            for field in ("scope", "type", "display", "access"):
                assert field in meta, f"{cog_name}.{key} missing '{field}'"
            assert meta["scope"] in ("GUILD", "GLOBAL"), f"{cog_name}.{key} invalid scope"
            assert meta["access"] in ("guild", "owner"), f"{cog_name}.{key} invalid access"


def test_validate_enum_valid():
    assert validate_value("Gen3Cog", "active_rule", "three_word") is True


def test_validate_enum_invalid():
    assert validate_value("Gen3Cog", "active_rule", "bad_value") is False


def test_validate_channel_list_valid():
    assert validate_value("Gen3Cog", "enabled_channels", [123456789, 987654321]) is True
    assert validate_value("Gen3Cog", "enabled_channels", []) is True


def test_validate_channel_list_invalid():
    assert validate_value("Gen3Cog", "enabled_channels", "not_a_list") is False
    assert validate_value("Gen3Cog", "enabled_channels", ["not_an_int"]) is False


def test_validate_unknown_cog():
    assert validate_value("NonexistentCog", "some_key", "value") is False


def test_validate_unknown_key():
    assert validate_value("Gen3Cog", "nonexistent_key", "value") is False


def test_demo_channels_is_owner_only():
    assert MANIFEST["Gen3Cog"]["demo_channels"]["access"] == "owner"


def test_validate_bool_valid():
    assert validate_value("Mod", "respect_hierarchy", True) is True
    assert validate_value("Mod", "respect_hierarchy", False) is True


def test_validate_bool_invalid():
    assert validate_value("Mod", "respect_hierarchy", "yes") is False


def test_validate_int_valid():
    assert validate_value("Mod", "delete_delay", -1) is True
    assert validate_value("Mod", "delete_delay", 60) is True


def test_validate_int_out_of_range():
    assert validate_value("Mod", "delete_delay", 9999) is False
    assert validate_value("Mod", "default_days", -1) is False


def test_validate_string_valid():
    assert validate_value("Mod", "ban_extra_embed_title", "Hello") is True


def test_validate_string_invalid():
    assert validate_value("Mod", "ban_extra_embed_title", 123) is False


def test_validate_channel_valid():
    assert validate_value("Admin", "announce_channel", 123456789) is True
    assert validate_value("Admin", "announce_channel", None) is True


def test_validate_channel_invalid():
    assert validate_value("Admin", "announce_channel", "not-an-int") is False


def test_validate_role_list_valid():
    assert validate_value("Admin", "selfroles", []) is True
    assert validate_value("Admin", "selfroles", [123456789]) is True


def test_validate_role_list_invalid():
    assert validate_value("Admin", "selfroles", "not-a-list") is False


def test_key_access_guild_key():
    from bellapi.manifest import key_access
    assert key_access("Gen3Cog", "active_rule") == "guild"


def test_key_access_owner_key():
    from bellapi.manifest import key_access
    assert key_access("Gen3Cog", "demo_channels") == "owner"


def test_key_access_unknown_cog_or_key_returns_owner():
    from bellapi.manifest import key_access
    assert key_access("Gen3Cog", "nonexistent_key") == "owner"
    assert key_access("NonexistentCog", "any_key") == "owner"
