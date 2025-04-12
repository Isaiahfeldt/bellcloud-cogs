# --- START OF FILE user_commands.py ---

import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


@cog_i18n(_)
class UserCommands(commands.Cog):

    @app_commands.user_install()  # Enable for user installs
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)  # Restrict to DMs/Groups
    async def handle_apply_effect(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to apply effects to images in a message."""
        await interaction.response.send_message("This command is working!.")
