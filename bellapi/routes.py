import json
from aiohttp import web
from bellapi.auth import verify_jwt, AuthError
from bellapi.rate_limit import RateLimiter

# Rate limiters
_health_limiter = RateLimiter(max_calls=10, period=60)
_write_limiter = RateLimiter(max_calls=30, period=60)


# ---------------------------------------------------------------------------
# Middleware + helpers
# ---------------------------------------------------------------------------

@web.middleware
async def json_error_middleware(request: web.Request, handler):
    """Convert all HTTPException responses to consistent {"error": "..."} JSON."""
    try:
        return await handler(request)
    except web.HTTPException as ex:
        return web.Response(
            status=ex.status,
            content_type="application/json",
            text=json.dumps({"error": ex.reason}),
        )


def _err(status: int, message: str) -> web.Response:
    return web.Response(
        status=status,
        content_type="application/json",
        text=json.dumps({"error": message}),
    )


def _json(data) -> web.Response:
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )


async def _check_auth(request: web.Request, required_guild_id: str | None = "FROM_PATH") -> dict:
    """
    Validates JWT. Returns JWT payload.
    required_guild_id="FROM_PATH" means extract guild_id from the URL match_info.
    required_guild_id=None means skip guild_id scope check (list endpoints).
    Raises web.HTTPForbidden on failure.
    """
    cog = request.app["cog"]

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPForbidden(reason="Missing Bearer token")
    token = auth_header[len("Bearer "):]

    if required_guild_id == "FROM_PATH":
        required_guild_id = request.match_info.get("guild_id")

    try:
        payload = verify_jwt(token, cog._secret, required_guild_id)
    except AuthError as e:
        raise web.HTTPForbidden(reason=e.message)

    return payload


# ---------------------------------------------------------------------------
# Health (Task 6)
# ---------------------------------------------------------------------------

async def health(request: web.Request) -> web.Response:
    remote_ip = request.remote
    if not _health_limiter.is_allowed(remote_ip):
        return _err(429, "Rate limit exceeded")
    cog = request.app["cog"]
    latency_ms = round(cog.bot.latency * 1000, 1)
    return _json({"status": "online", "latency_ms": latency_ms})


# ---------------------------------------------------------------------------
# Guilds list (Task 6)
# ---------------------------------------------------------------------------

async def guilds(request: web.Request) -> web.Response:
    await _check_auth(request, required_guild_id=None)
    cog = request.app["cog"]
    result = [
        {"id": str(g.id), "name": g.name, "icon": str(g.icon) if g.icon else None}
        for g in cog.bot.guilds
    ]
    return _json(result)


# ---------------------------------------------------------------------------
# Guild info (Task 1 — dashboard)
# ---------------------------------------------------------------------------

async def guild_info(request: web.Request) -> web.Response:
    await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")
    return _json({
        "id": str(guild.id),
        "name": guild.name,
        "icon": guild.icon.key if guild.icon else None,
        "member_count": guild.member_count,
    })


# ---------------------------------------------------------------------------
# Cog enable/disable (Task 7)
# Uses Red's native bot._disabled_cog_cache — no guild_enabled Config key needed.
# ---------------------------------------------------------------------------

async def guild_cogs(request: web.Request) -> web.Response:
    payload = await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")

    from bellapi.manifest import OWNER_ONLY_COGS
    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids

    result = []
    for cog_name in sorted(cog.bot.cogs.keys()):
        if cog_name in OWNER_ONLY_COGS and not is_owner:
            continue
        enabled = not await cog.bot.cog_disabled_in_guild_raw(cog_name, guild_id)
        result.append({
            "name": cog_name,
            "enabled_in_guild": enabled,
            "owner_only": cog_name in OWNER_ONLY_COGS,
        })
    return _json(result)


async def set_guild_cog(request: web.Request) -> web.Response:
    payload = await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    cog_name = request.match_info["cog_name"]

    from bellapi.manifest import OWNER_ONLY_COGS
    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids

    if cog_name in OWNER_ONLY_COGS and not is_owner:
        return _err(403, f"Cog '{cog_name}' can only be managed by the bot owner")

    if cog.bot.get_cog(cog_name) is None:
        return _err(404, f"Cog '{cog_name}' is not loaded")

    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")

    try:
        body = await request.json()
        enabled = body["enabled"]
        if not isinstance(enabled, bool):
            return _err(400, "'enabled' must be a boolean")
    except Exception:
        return _err(400, "Invalid request body — expected {'enabled': bool}")

    cache = cog.bot._disabled_cog_cache
    if enabled:
        await cache.enable_cog_in_guild(cog_name, guild_id)
    else:
        await cache.disable_cog_in_guild(cog_name, guild_id)

    return _json({"cog_name": cog_name, "enabled": enabled})


# ---------------------------------------------------------------------------
# Manifest schema (Task 4)
# ---------------------------------------------------------------------------

async def manifest_schema(request: web.Request) -> web.Response:
    payload = await _check_auth(request, required_guild_id=None)
    cog = request.app["cog"]

    from bellapi.manifest import MANIFEST, OWNER_ONLY_COGS
    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids

    filtered: dict[str, dict] = {}
    for cog_name, keys in MANIFEST.items():
        if cog_name in OWNER_ONLY_COGS and not is_owner:
            continue
        visible_keys = {
            k: v for k, v in keys.items()
            if is_owner or v["access"] == "guild"
        }
        if visible_keys:
            filtered[cog_name] = visible_keys

    return _json({
        "cogs": filtered,
        "owner_only_cogs": sorted(OWNER_ONLY_COGS),
    })


# ---------------------------------------------------------------------------
# Config read helpers (Task 8)
# ---------------------------------------------------------------------------

async def _read_cog_config(bot, guild, cog_name: str, is_owner: bool = False) -> dict | None:
    """
    Read all GUILD-scope manifest keys for cog_name from Red's Config.
    Filters out 'owner'-access keys when is_owner is False.
    Returns None if the cog is not loaded.
    """
    from bellapi.manifest import MANIFEST
    target_cog = bot.get_cog(cog_name)
    if target_cog is None:
        return None
    cog_keys = MANIFEST.get(cog_name, {})
    result = {}
    for key, meta in cog_keys.items():
        if meta["scope"] == "GUILD":
            if not is_owner and meta.get("access", "guild") == "owner":
                continue
            result[key] = await target_cog.config.guild(guild).get_attr(key)()
    return result


# ---------------------------------------------------------------------------
# Config read routes (Task 8)
# ---------------------------------------------------------------------------

async def config_all(request: web.Request) -> web.Response:
    payload = await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")

    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids

    from bellapi.manifest import MANIFEST
    result = {}
    for cog_name in MANIFEST:
        data = await _read_cog_config(cog.bot, guild, cog_name, is_owner=is_owner)
        if data is not None:
            result[cog_name] = data
    return _json(result)


async def config_cog(request: web.Request) -> web.Response:
    payload = await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    cog_name = request.match_info["cog_name"]

    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")

    from bellapi.manifest import MANIFEST
    if cog_name not in MANIFEST:
        return _err(404, f"Cog '{cog_name}' is not in the manifest")

    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids
    data = await _read_cog_config(cog.bot, guild, cog_name, is_owner=is_owner)
    if data is None:
        return _err(404, f"Cog '{cog_name}' is not loaded")
    return _json(data)


async def config_key(request: web.Request) -> web.Response:
    payload = await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    cog_name = request.match_info["cog_name"]
    key = request.match_info["key"]

    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")

    from bellapi.manifest import MANIFEST, key_access
    cog_keys = MANIFEST.get(cog_name)
    if cog_keys is None:
        return _err(404, f"Cog '{cog_name}' is not in the manifest")
    if key not in cog_keys:
        return _err(404, f"Key '{key}' is not in the manifest for '{cog_name}'")

    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids
    if key_access(cog_name, key) == "owner" and not is_owner:
        return _err(403, f"Key '{key}' can only be read by the bot owner")

    target_cog = cog.bot.get_cog(cog_name)
    if target_cog is None:
        return _err(404, f"Cog '{cog_name}' is not loaded")

    value = await target_cog.config.guild(guild).get_attr(key)()
    return _json({"key": key, "value": value})


# ---------------------------------------------------------------------------
# Config write route (Task 9)
# ---------------------------------------------------------------------------

async def config_set_key(request: web.Request) -> web.Response:
    payload = await _check_auth(request)
    cog = request.app["cog"]
    guild_id = int(request.match_info["guild_id"])
    cog_name = request.match_info["cog_name"]
    key = request.match_info["key"]
    user_id = str(payload.get("sub", "unknown"))

    if not _write_limiter.is_allowed(user_id):
        return _err(429, "Write rate limit exceeded")

    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return _err(404, "Guild not found")

    from bellapi.manifest import MANIFEST, validate_value, key_access
    cog_keys = MANIFEST.get(cog_name)
    if cog_keys is None:
        return _err(404, f"Cog '{cog_name}' is not in the manifest")
    if key not in cog_keys:
        return _err(400, f"Key '{key}' is not in the manifest for '{cog_name}'")

    # Per-key access check (fail fast before reading request body)
    caller_id = int(payload.get("sub", 0))
    is_owner = caller_id in cog.bot.owner_ids
    if key_access(cog_name, key) == "owner" and not is_owner:
        return _err(403, f"Key '{key}' can only be set by the bot owner")

    try:
        body = await request.json()
        value = body["value"]
    except Exception:
        return _err(400, "Invalid request body — expected {'value': ...}")

    if not validate_value(cog_name, key, value):
        return _err(400, f"Invalid value for '{key}'")

    target_cog = cog.bot.get_cog(cog_name)
    if target_cog is None:
        return _err(404, f"Cog '{cog_name}' is not loaded")

    try:
        await target_cog.config.guild(guild).get_attr(key).set(value)
    except Exception as e:
        return _err(503, f"Failed to set config: {e}")

    return _json({"key": key, "value": value, "cog_name": cog_name})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def setup_routes(app: web.Application):
    app.router.add_get("/health", health)
    app.router.add_get("/manifest", manifest_schema)
    app.router.add_get("/guilds", guilds)
    app.router.add_get("/guilds/{guild_id}/info", guild_info)
    app.router.add_get("/guilds/{guild_id}/cogs", guild_cogs)
    app.router.add_put("/guilds/{guild_id}/cogs/{cog_name}", set_guild_cog)
    app.router.add_get("/config/{guild_id}", config_all)
    app.router.add_get("/config/{guild_id}/{cog_name}", config_cog)
    app.router.add_get("/config/{guild_id}/{cog_name}/{key}", config_key)
    app.router.add_put("/config/{guild_id}/{cog_name}/{key}", config_set_key)
