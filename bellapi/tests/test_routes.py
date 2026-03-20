"""Tests for bellapi route handlers using aiohttp TestClient."""
import asyncio
import time
import jwt
import pytest
from aiohttp.test_utils import TestClient, TestServer
from unittest.mock import MagicMock

from bellapi.server import build_app
from bellapi.manifest import OWNER_ONLY_COGS

SECRET = "test_secret_routes_abc123_padding_for_length"

OWNER_ID = 111111111
GUILD_USER_ID = 222222222


def make_token(sub: int, secret: str = SECRET, guild_id: int | None = None) -> str:
    return jwt.encode(
        {
            "iss": "bellbot.xyz",
            "sub": str(sub),
            "guild_id": str(guild_id) if guild_id is not None else None,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        },
        secret,
        algorithm="HS256",
    )


def make_mock_cog(owner_ids: set) -> MagicMock:
    """Build a minimal cog mock sufficient for the manifest_schema handler."""
    cog = MagicMock()
    cog._secret = SECRET
    cog.bot.owner_ids = owner_ids
    return cog


def run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


async def _get_manifest(app, token: str | None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/manifest", headers=headers)
        status = resp.status
        try:
            data = await resp.json()
        except Exception:
            data = {}
    return status, data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_manifest_schema_owner_sees_all_keys():
    """Owner receives all manifest keys, including owner-access ones like demo_channels."""
    cog = make_mock_cog(owner_ids={OWNER_ID})
    app = build_app(cog)
    token = make_token(sub=OWNER_ID)

    status, data = run(_get_manifest(app, token))

    assert status == 200
    assert "cogs" in data
    gen3 = data["cogs"].get("Gen3Cog", {})
    assert "active_rule" in gen3, "guild-access key should be visible to owner"
    assert "demo_channels" in gen3, "owner-access key should be visible to owner"


def test_manifest_schema_guild_sees_only_guild_keys():
    """Non-owner guild manager only sees keys with access='guild'; owner-access keys filtered out."""
    cog = make_mock_cog(owner_ids={OWNER_ID})
    app = build_app(cog)
    token = make_token(sub=GUILD_USER_ID)

    status, data = run(_get_manifest(app, token))

    assert status == 200
    assert "cogs" in data

    gen3 = data["cogs"].get("Gen3Cog", {})
    assert "active_rule" in gen3, "guild-access key should be visible to guild user"
    assert "demo_channels" not in gen3, "owner-access key should be hidden from guild user"

    # Admin.announce_channel is owner-access — should be hidden
    admin = data["cogs"].get("Admin", {})
    assert "announce_channel" not in admin, "owner-access key should be hidden from guild user"
    # Admin.selfroles is guild-access — should be visible
    assert "selfroles" in admin, "guild-access key should be visible to guild user"

    assert "Cleanup" not in data["cogs"], "owner-only cog should be hidden from guild user"


def test_manifest_schema_owner_only_cogs_list():
    """owner_only_cogs is always present in the response and matches OWNER_ONLY_COGS."""
    cog = make_mock_cog(owner_ids={OWNER_ID})
    app = build_app(cog)
    token = make_token(sub=OWNER_ID)

    status, data = run(_get_manifest(app, token))

    assert status == 200
    assert "owner_only_cogs" in data
    assert data["owner_only_cogs"] == sorted(OWNER_ONLY_COGS)


def test_manifest_schema_requires_auth():
    """Request without a Bearer token returns 403."""
    cog = make_mock_cog(owner_ids={OWNER_ID})
    app = build_app(cog)

    status, _ = run(_get_manifest(app, token=None))

    assert status == 403


# ---------------------------------------------------------------------------
# Guild info tests (Task 1)
# ---------------------------------------------------------------------------

def test_guild_info_returns_member_count():
    async def _run():
        cog = make_mock_cog(owner_ids=set())
        mock_guild = MagicMock()
        mock_guild.id = 111
        mock_guild.name = "Test Guild"
        mock_guild.icon = None
        mock_guild.member_count = 500
        cog.bot.get_guild.return_value = mock_guild
        app = build_app(cog)
        async with TestClient(TestServer(app)) as client:
            token = make_token(sub=GUILD_USER_ID, guild_id=111)
            resp = await client.get("/guilds/111/info",
                                    headers={"Authorization": f"Bearer {token}"})
            assert resp.status == 200
            data = await resp.json()
            assert data["id"] == "111"
            assert data["member_count"] == 500
            assert "name" in data

    asyncio.run(_run())


def test_guild_info_404_unknown_guild():
    async def _run():
        cog = make_mock_cog(owner_ids=set())
        cog.bot.get_guild.return_value = None  # guild not found
        app = build_app(cog)
        async with TestClient(TestServer(app)) as client:
            token = make_token(sub=GUILD_USER_ID, guild_id=999)
            resp = await client.get("/guilds/999/info",
                                    headers={"Authorization": f"Bearer {token}"})
            assert resp.status == 404

    asyncio.run(_run())


def test_guild_info_requires_auth():
    async def _run():
        cog = make_mock_cog(owner_ids=set())
        app = build_app(cog)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/guilds/111/info")
            assert resp.status == 403

    asyncio.run(_run())
