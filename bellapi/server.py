from aiohttp import web


def build_app(cog) -> web.Application:
    """
    Build the aiohttp application and attach all routes.
    `cog` is the BellApi cog instance — routes access bot/config through it.
    """
    from bellapi.routes import setup_routes, json_error_middleware
    app = web.Application(middlewares=[json_error_middleware])
    app["cog"] = cog
    setup_routes(app)
    return app


async def start_server(cog, port: int):
    """Start the aiohttp server and return the AppRunner."""
    app = build_app(cog)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    return runner


async def stop_server(runner):
    """Gracefully stop the aiohttp server."""
    if runner is not None:
        await runner.cleanup()
