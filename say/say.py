#  Copyright (c) 2024, Isaiah Feldt
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

from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Say", __file__)


@cog_i18n(_)
class Say(commands.Cog):
    """Talk As Bell"""

    default_guild_settings = {
    }

    default_channel_settings = {
    }

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.settings = Config.get_conf(self, identifier=6849044639, force_registration=True)

        self.settings.register_guild(**self.default_guild_settings)
        self.settings.register_channel(**self.default_channel_settings)

    @commands.command(aliases=["s"])
    @commands.guild_only()
    async def say(self, ctx, *, text):
        """Talk as Bell"""
        user = ctx.message.author
        message = ctx.message
        if hasattr(user, 'bot') and user.bot is True:
            return
        try:
            if "__" in text:
                raise ValueError
            evald = eval(text, {}, {'message': ctx.message,
                                    'channel': ctx.message.channel,
                                    'server': ctx.message.server})
        except:
            evald = text

        if len(str(evald)) > 2000:
            evald = str(evald)[-1990:] + "blank"

        await ctx.send(evald)
        await message.delete()
