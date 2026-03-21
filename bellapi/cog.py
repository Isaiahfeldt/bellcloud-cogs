import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from redbot.core import Config, commands
from redbot.core.bot import Red

log = logging.getLogger("red.bellapi")


class BellApi(commands.Cog):
    """HTTP API bridge for the bellbot.xyz dashboard."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7291038456, force_registration=True)
        self.config.register_global(
            port=8765,
        )
        self._runner = None
        self._secret: str | None = None
        self._redis = None
        self._status_task: asyncio.Task | None = None

    async def cog_load(self):
        self._secret = os.environ.get("BELL_API_SECRET")
        if not self._secret:
            raise RuntimeError("BELL_API_SECRET environment variable is not set")

        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            log.info(f"Connected to Redis at {redis_url}")
            self._status_task = asyncio.create_task(self._publish_status_loop())
        except Exception as e:
            log.warning(f"Redis unavailable, status publishing disabled: {e}")
            self._redis = None

        from bellapi.server import start_server
        port = await self.config.port()
        self._runner = await start_server(self, port)
        log.info(f"BellApi HTTP server started on port {port}")

    async def cog_unload(self):
        if self._status_task:
            self._status_task.cancel()
            self._status_task = None

        if self._redis:
            await self._redis.aclose()
            self._redis = None

        from bellapi.server import stop_server
        await stop_server(self._runner)
        self._runner = None
        log.info("BellApi HTTP server stopped")

    async def _publish_status_loop(self):
        """Write Bell's status to Redis every 30 seconds."""
        while True:
            try:
                status = {
                    "latency_ms": round(self.bot.latency * 1000, 2),
                    "guild_count": len(self.bot.guilds),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await self._redis.set("bell:status", json.dumps(status), ex=90)
            except Exception as e:
                log.warning(f"Redis publish error: {e}")
            await asyncio.sleep(30)

    @commands.group()
    @commands.is_owner()
    async def bellapi(self, ctx):
        """BellApi configuration commands."""
        pass

    @bellapi.command(name="port")
    async def bellapi_port(self, ctx):
        """Show the current server port."""
        port = await self.config.port()
        await ctx.send(f"BellApi is running on port `{port}`.")
