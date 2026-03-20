import pytest
from bellapi.manifest import MANIFEST, KNOWN_COGS, validate_value


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


def test_known_cogs_matches_manifest():
    assert set(KNOWN_COGS) == set(MANIFEST.keys())


def test_all_entries_have_required_fields():
    for cog_name, cog_keys in MANIFEST.items():
        for key, meta in cog_keys.items():
            assert "scope" in meta, f"{cog_name}.{key} missing 'scope'"
            assert "type" in meta, f"{cog_name}.{key} missing 'type'"
            assert "display" in meta, f"{cog_name}.{key} missing 'display'"
            assert meta["scope"] in ("GUILD", "GLOBAL"), f"{cog_name}.{key} invalid scope"


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
