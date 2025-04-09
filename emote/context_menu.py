import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import valid_formats
from .utils.chat import send_error_embed
from .utils.enums import EmoteAddError
from .utils.modals import EmoteNameModal

_ = Translator("Emote", __file__)


@cog_i18n(_)
class ContextMenu(commands.Cog):
    def __init__(self):
        self.temp_attachments = {}

    async def handle_add_emote(self, interaction: discord.Interaction, message: discord.Message):
        # Check permissions
        if not interaction.user.guild_permissions.manage_messages:
            await send_error_embed(interaction, EmoteAddError.INVALID_PERMISSION)
            return

        # Get first valid attachment
        attachment = next(
            (att for att in message.attachments
             if any(att.filename.lower().endswith(ext) for ext in valid_formats)),
            None
        )

        if not attachment:
            await send_error_embed(interaction, EmoteAddError.INVALID_FILE_FORMAT)
            return

        # Store attachment URL temporarily
        self.temp_attachments[interaction.user.id] = attachment.url

        # Show name modal
        modal = EmoteNameModal(self.modal_callback)
        await interaction.response.send_modal(modal)

    async def modal_callback(self, interaction: discord.Interaction, name: str):
        url = self.temp_attachments.pop(interaction.user.id, None)
        if not url:
            await send_error_embed(interaction, EmoteAddError.UNREACHABLE_URL)
            return

        # Reuse existing add logic
        await self.emote_add(interaction, name=name, url=url)
