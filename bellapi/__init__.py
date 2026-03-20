from redbot.core.bot import Red

from .cog import BellApi


async def setup(bot: Red) -> None:
    await bot.add_cog(BellApi(bot))
