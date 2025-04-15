import io
from datetime import datetime

import discord
from discord.ui import View
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import SlashCommands
from emote.utils.effects import Emote
from emote.utils.pipeline import create_pipeline, execute_pipeline

_ = Translator("Emote", __file__)


def _parse_docstring_for_description(func) -> str:
    """Extracts the user description from the function's docstring."""

    doc = getattr(func, "__doc__", None) or ""
    lines = doc.strip().splitlines()
    try:
        user_line_index = -1
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("user:"):
                user_line_index = i
                break

        if user_line_index != -1 and user_line_index + 1 < len(lines):
            for next_line in lines[user_line_index + 1:]:
                stripped_next_line = next_line.strip()
                if stripped_next_line:
                    desc = stripped_next_line.split('.')[0].strip()
                    return desc[:100]
    except Exception:
        pass
    return "No description available."[:100]


class EffectSelect(discord.ui.Select):
    """A select menu for choosing effects to apply to a message."""

    def __init__(self, options: list[discord.SelectOption], image_buffer: bytes, file_type: str, ):
        """
        Initializes the EffectSelect menu.

        Args:
            options (list[discord.SelectOption]): A list of effect options.
            image_buffer (bytes): The image buffer to apply effects to.
            file_type (str): The file type of the image (e.g., "png", "jpg", "gif")..
        """
        self.image_buffer = image_buffer
        self.file_type = file_type
        display_options = options[:25]  # Discord limit
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(display_options),
            options=display_options,
            custom_id="effect_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handles the user's selection of effects."""

        await interaction.response.defer(ephemeral=False, thinking=True)
        selected_effects = self.values

        queued_effects = []
        for effect_name in selected_effects:
            parsed_args = []
            queued_effects.append((effect_name, parsed_args))

        emote_instance = Emote(
            id=0,  # Use a dummy id since this is a virtual Emote
            file_path=f"virtual/emote.{self.file_type}",  # Use real file name and type
            author_id=000000000,
            timestamp=datetime.now(),
            original_url="www.example.com",
            name=f"emote.{self.file_type}",
            guild_id=0,
            usage_count=0,
            errors={},
            issues={},
            notes={},
            followup={},
            effect_chain={},
            img_data=self.image_buffer,
        )

        pipeline = await create_pipeline(self, interaction.message, emote_instance, queued_effects)
        emote = await execute_pipeline(pipeline)

        if emote.img_data:
            image_buffer = io.BytesIO(emote.img_data)
            filename = emote.file_path.split("/")[-1] if emote.file_path else "emote.png"
            file = discord.File(fp=image_buffer, filename=filename)
            await interaction.response.send_message(content="", file=file, ephemeral=False)


class EffectView(View):
    """A view that allows users to select and apply effects to a Discord message."""

    def __init__(self, available_options: list[discord.SelectOption], image_buffer: bytes, file_type: str, *,
                 timeout=180):
        """
        Initializes the EffectView.

        Args:
            available_options (list[discord.SelectOption]): A list of available effect options.
            image_buffer (bytes): The image buffer to apply effects to.
            file_type (str): The file type of the image (e.g., "png", "jpg", "gif").
            timeout (int, optional): The timeout for the view in seconds. Defaults to 180.
        """
        super().__init__(timeout=timeout)
        self.attached_message: discord.Message | None = None
        if available_options:
            self.add_item(EffectSelect(
                options=available_options,
                image_buffer=image_buffer,
                file_type=file_type,
            ))

    async def on_timeout(self):
        """Called when the view times out. Disables all items in the view and updates the attached message."""

        if self.attached_message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.attached_message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden):
                pass


@cog_i18n(_)
class UserCommands(commands.Cog):

    async def handle_apply_effect(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to apply effects to images in a message."""

        has_image = message.attachments and any(
            att.content_type and att.content_type.startswith("image/") for att in message.attachments)

        if not has_image:
            await interaction.response.send_message(
                "I couldn't find a direct image attachment in that message to apply effects to.",
                ephemeral=True
            )
            return

        image_attachment = next((att for att in message.attachments if att.content_type.startswith("image/")), None)
        image_buffer = await image_attachment.read()

        # TODO: image compression / resize to be smaller

        effects_list_data = SlashCommands.EFFECTS_LIST
        available_options = []
        is_owner = await self.bot.is_owner(interaction.user)

        for name, data in effects_list_data.items():
            perm = data.get("perm", "everyone").lower()
            func = data.get("func")
            if not func: continue

            allowed = False
            if perm == "owner":
                allowed = is_owner
            elif perm == "everyone":
                allowed = True

            if allowed:
                # Use the helper from UserCommands mixin
                description = _parse_docstring_for_description(func)
                available_options.append(
                    discord.SelectOption(label=name.capitalize(), value=name, description=description)
                )

        if not available_options:
            await interaction.response.send_message(
                "You don't have permission for any effects, or none are configured for DM use.",
                ephemeral=True
            )
            return

        view = EffectView(
            available_options=available_options,
            image_buffer=image_buffer,
            file_type=image_attachment.content_type.split("/")[-1],
            timeout=180
        )

        await interaction.response.send_message(
            f"Select effect(s) to apply this message:",
            view=view,
            ephemeral=True
        )
        view.attached_message = await interaction.original_response()
