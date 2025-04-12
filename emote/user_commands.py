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
        message = interaction.message

        image_attachment = None
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4')):
                image_attachment = attachment
                break

        await message.reply(content=f"This is a test! {message.content}", mention_author=False)
