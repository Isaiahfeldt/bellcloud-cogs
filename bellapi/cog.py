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
            allowed_ips=[],
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

    @bellapi.command(name="allowip")
    async def bellapi_allowip(self, ctx, ip: str):
        """Add an IP address to the allowlist."""
        allowed = await self.config.allowed_ips()
        if ip in allowed:
            return await ctx.send(f"`{ip}` is already in the allowlist.")
        allowed.append(ip)
        await self.config.allowed_ips.set(allowed)
        await ctx.send(f"Added `{ip}` to the allowlist.")

    @bellapi.command(name="removeip")
    async def bellapi_removeip(self, ctx, ip: str):
        """Remove an IP address from the allowlist."""
        allowed = await self.config.allowed_ips()
        if ip not in allowed:
            return await ctx.send(f"`{ip}` is not in the allowlist.")
        allowed.remove(ip)
        await self.config.allowed_ips.set(allowed)
        await ctx.send(f"Removed `{ip}` from the allowlist.")

    @bellapi.command(name="listips")
    async def bellapi_listips(self, ctx):
        """Show the current IP allowlist."""
        allowed = await self.config.allowed_ips()
        if not allowed:
            return await ctx.send("The allowlist is empty — all requests are blocked.")
        await ctx.send("Allowed IPs:\n" + "\n".join(f"• `{ip}`" for ip in allowed))

    @bellapi.command(name="port")
    async def bellapi_port(self, ctx):
        """Show the current server port."""
        port = await self.config.port()
        await ctx.send(f"BellApi is running on port `{port}`.")
