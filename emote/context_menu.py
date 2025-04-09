import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import valid_formats
from .utils.chat import send_error_embed, send_error_followup, send_embed_followup
from .utils.database import Database
from .utils.enums import EmoteAddError
from .utils.modals import EmoteNameModal
from .utils.url import is_url_reachable, blacklisted_url, is_media_format_valid, is_media_size_valid, alphanumeric_name

_ = Translator("Emote", __file__)
db = Database()


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

        rules = [
            (lambda: alphanumeric_name, EmoteAddError.INVALID_NAME_CHAR),
            (lambda: len(name) <= 32, EmoteAddError.EXCEED_NAME_LEN),
            (lambda: is_url_reachable(url), EmoteAddError.UNREACHABLE_URL),
            (lambda: not blacklisted_url(url), EmoteAddError.BLACKLISTED_URL),
            (lambda: is_media_format_valid(url, valid_formats), EmoteAddError.INVALID_FILE_FORMAT),
            (lambda: is_media_size_valid(url, 52428800), EmoteAddError.EXCEED_FILE_SIZE),
        ]

        for condition, error in rules:
            if not condition():
                await send_error_followup(interaction, error)
                return

        if await db.check_emote_exists(name, interaction.guild_id):
            await send_error_followup(interaction, EmoteAddError.DUPLICATE_EMOTE_NAME)
            return

        # Upload to bucket
        file_type = str(is_media_format_valid(url, valid_formats)[1])
        success, error = await db.add_emote_to_database(interaction, name, url, file_type)

        if not success:
            await send_error_followup(interaction, error)
            return

        await send_embed_followup(
            interaction, "Success!", f"Added **{name}** as an emote."
        )
