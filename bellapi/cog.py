import logging
import os

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

    async def cog_load(self):
        self._secret = os.environ.get("BELL_API_SECRET")
        if not self._secret:
            raise RuntimeError("BELL_API_SECRET environment variable is not set")
        from bellapi.server import start_server
        port = await self.config.port()
        self._runner = await start_server(self, port)
        log.info(f"BellApi HTTP server started on port {port}")

    async def cog_unload(self):
        from bellapi.server import stop_server
        await stop_server(self._runner)
        self._runner = None
        log.info("BellApi HTTP server stopped")

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
