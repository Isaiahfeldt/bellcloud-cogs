import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


@cog_i18n(_)
class UserCommands(commands.Cog):

    @app_commands.command(name="effect", description="Adds effects to images")
    @app_commands.user_install()
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def effect(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message('I am installed in users by default!')
