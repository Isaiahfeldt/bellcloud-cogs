# from glob import glob
# import ast
# import os
# import os.path
# import re
# import io
# import urllib.request
# import httplib2
# import requests
# import datetime

import discord
from discord import AppCommandType
from redbot.core import checks, Config, commands, app_commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from .user_commands import UserCommands
from .hybrid_commands import HybridCommands
from .slash_commands import SlashCommands
from .context_menus import ContextMenus

_ = Translator("Emote", __file__)

@cog_i18n(_)
class Emotes(
    UserCommands,
    HybridCommands,
    SlashCommands,
    ContextMenus,
):
    """
    Sorta like an emoji, but bigger
    """

    __version__ = "0.0.1"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=4150561391)
        self.config = Config.get_conf(
            self,
            identifier=4150561391,
            force_registration=True,
        )

        self.add_as_emote = discord.app_commands.ContextMenu(
            name=_("Add as emote"),
            callback=self.add_as_emote,
            type=AppCommandType.message,
            extras={"red_force_enable": True},
        )
        self.bot.tree.add_command(self.add_as_emote)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.add_as_emote, type=AppCommandType.message)
        

#     @commands.hybrid_group(name="emote", aliases=["e"])
#     @commands.guild_only()
#     async def emote(self, ctx: commands.Context):
#         """
#         Sorta like emojis, but bigger
#         """
#         passa
#
#     @emote.command(name="add", aliases=["a"])
#     async def add(self, ctx):
#         """
#         Adds an Emote to the server
#         """
#         await ctx.send("Aemote test", ephemeral=True)
#
#
#     # Important: we're building the commands outside of our cog class.
# @app_commands.context_menu(name="Add as emote")
# async def add_as_emote(interaction: discord.Interaction, message: discord.Message):
#     pass