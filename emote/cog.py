#  Copyright (c) 2023, Isaiah Feldt
#  ͏
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU Affero General Public License (AGPL) as published by
#     - the Free Software Foundation, either version 3 of this License,
#     - or (at your option) any later version.
#  ͏
#     - This program is distributed in the hope that it will be useful,
#     - but without any warranty, without even the implied warranty of
#     - merchantability or fitness for a particular purpose.
#     - See the GNU Affero General Public License for more details.
#  ͏
#     - You should have received a copy of the GNU Affero General Public License
#     - If not, please see <https://www.gnu.org/licenses/#GPL>.

from typing import Any

from discord import AppCommandType
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import SlashCommands

_ = Translator("Emote", __file__)


@cog_i18n(_)
class Emotes(
    # UserCommands,
    # HybridCommands,
    SlashCommands,
    # ContextMenus,
):
    """
    Discord emotes slash commands.
    Sorta like an emoji, but bigger.
    """

    __version__ = "0.0.1"

    def __init__(self, bot: Red, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.bot = bot

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.add_as_emote, type=AppCommandType.message)
