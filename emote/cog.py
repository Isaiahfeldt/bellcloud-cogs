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

from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from emote.hybrid_commands import HybridCommands
from emote.slash_commands import SlashCommands
from emote.user_commands import UserCommands

_ = Translator("Emote", __file__)


@cog_i18n(_)
class Emotes(
    UserCommands,
    HybridCommands,
    SlashCommands,
    # ContextMenus,
):
    """
    Discord emotes slash commands.
    Sorta like an emoji, but bigger.
    """

    __version__ = "0.0.1"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=4150111391)
        self.config = Config.get_conf(
            self,
            identifier=4150111391,
            force_registration=True,
        )

        # self.add_as_emote = discord.app_commands.ContextMenu(
        #     name=_("Add as emote"),
        #     callback=self.add_as_emote,
        #     type=AppCommandType.message,
        #     extras={"red_force_enable": True},
        # )
        # self.bot.tree.add_command(self.add_as_emote)

    # async def cog_unload(self) -> None:
    #     self.bot.tree.remove_command(self.add_as_emote, type=AppCommandType.message)
