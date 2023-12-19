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

from typing import TYPE_CHECKING, Any, TypeVar, Union

import discord
from discord import app_commands
from discord.ext.commands import AutoShardedBot, Cog, CommandError

# Define TypeVars upfront to avoid Referenced before assignment issues
DISCORD_BOT_TYPE = TypeVar("DISCORD_BOT_TYPE", bound=AutoShardedBot, covariant=True)
DISCORD_COG_TYPE = TypeVar("DISCORD_COG_TYPE", bound=Cog, covariant=True)
DISCORD_CONTEXT_TYPE = TypeVar("DISCORD_CONTEXT_TYPE", bound="Context", covariant=True)

if TYPE_CHECKING:
    from discord.ext.commands import Context

    try:
        from redbot.core.bot import Red
        from redbot.core.bot import Red as BotClient
        from redbot.core.commands import Cog as RedCog
        from redbot.core.commands import Context as ClientContext
    except ImportError:
        BotClient = Red = AutoShardedBot
        RedCog = Cog
        ClientContext = Context
else:
    from discord.ext.commands import Context

    try:
        from redbot.core.bot import Red as BotClient
        from redbot.core.commands import Cog as RedCog
    except ImportError:
        BotClient = AutoShardedBot
        RedCog = Cog


class BotClientType(BotClient):
    async def get_context(
            self, message: discord.Message | DISCORD_COG_TYPE | ClientContext, *,
            cls: type[Context] = None) -> Context[Any]:
        ...


class DISCORD_INTERACTION_TYPE_BASE(discord.Interaction):
    client: BotClientType
    response: discord.InteractionResponse
    followup: discord.Webhook


class DISCORD_COG_TYPE_MIXIN(RedCog):
    __version__: str
    bot: DISCORD_BOT_TYPE


DISCORD_INTERACTION_TYPE = TypeVar(
    "DISCORD_INTERACTION_TYPE", bound=DISCORD_INTERACTION_TYPE_BASE | discord.Interaction, covariant=True
)
DISCORD_COMMAND_ERROR_TYPE = TypeVar(
    "DISCORD_COMMAND_ERROR_TYPE", bound=Union[CommandError, app_commands.errors.AppCommandError], covariant=True
)
