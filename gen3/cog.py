#  Copyright (c) 2024-2025, Isaiah Feldt
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

from gen3.slash_commands import SlashCommands

_ = Translator("Gen3", __file__)


@cog_i18n(_)
class Gen3Cog(SlashCommands):
    """
    Gen3 event manager for Discord channels.
    A flexible cog for managing gen3 events with various content requirements.
    """

    __version__ = "0.1.0"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=4150111392,  # Different identifier than Emotes
            force_registration=True,
        )

        # Default configuration for Gen3 (per guild)
        default_guild = {
            "enabled_channels": [],
            "active_rule": "apple_orange"
        }
        self.config.register_guild(**default_guild)

    async def cog_load(self):
        from gen3.slash_commands import db
        # init_schema will initialize the pool if needed and perform migrations
        await db.init_schema()
        print("Gen3 schema initialized")

    async def cog_unload(self):
        from gen3.slash_commands import db
        await db.close_pool()
        print("Pool closed")
