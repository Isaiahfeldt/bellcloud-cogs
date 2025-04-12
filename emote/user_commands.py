# --- START OF FILE user_commands.py ---

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


@cog_i18n(_)
class UserCommands(commands.Cog):

    async def handle_apply_effect(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to apply effects to images in a message."""
        await interaction.response.send_message("This command is working!")
