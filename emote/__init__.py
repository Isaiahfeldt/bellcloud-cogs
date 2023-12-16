from redbot.core.bot import Red
from .cog import Emotes

async def setup(bot: Red) -> None:
      cog = Emotes(bot)
      await bot.add_cog(cog)