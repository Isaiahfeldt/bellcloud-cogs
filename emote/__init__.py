#  Copyright (c) 2023, Isaiah Feldt
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU General Public License (GPL) as published by
#     - the Free Software Foundation, either version 3 of this License,
#     - or (at your option) any later version.
#  ͏
#     - This program is distributed in the hope that it will be useful,
#     - but without any warranty, without even the implied warranty of
#     - merchantability or fitness for a particular purpose.
#     - See the GNU General Public License for more details.
#  ͏
#     - You should have received a copy of the GNU GPL along with this program.
#     - If not, please see <https://www.gnu.org/licenses/#GPL>.

from redbot.core.bot import Red

from .cog import Emotes


async def setup(bot: Red) -> None:
    cog = Emotes(bot)
    await bot.add_cog(cog)
