import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


@cog_i18n(_)
class UserCommands(commands.Cog):

    @app_commands.command()
    @app_commands.user_install()
    async def effect(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message('I am installed in users by default!')
