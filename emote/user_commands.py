# --- START OF FILE user_commands.py ---

import io

import discord
from discord.ui import View
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

# Assume these imports work and classes/functions exist
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
    """A select menu for choosing effects."""

    def __init__(self, options: list[discord.SelectOption], image_buffer: bytes, file_type: str):
        """
        Initializes the EffectSelect menu.

        Args:
            options (list[discord.SelectOption]): A list of effect options.
            image_buffer (bytes): The image buffer to apply effects to.
            file_type (str): The file type of the image (e.g., "png", "jpg", "gif").
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
        """Handles the user's selection of effects using followup."""

        try:
            await interaction.response.edit_message(content="Processing selected effect(s)...", view=None)
        except discord.NotFound:
            try:
                await interaction.followup.send("The original selection message seems to be gone.", ephemeral=True)
            except discord.HTTPException:
                pass
            return
        except discord.HTTPException as e:
            try:
                await interaction.followup.send(f"An error occurred acknowledging selection: {e}", ephemeral=True)
            except discord.HTTPException:
                pass
            return

        selected_effects = self.values

        queued_effects = []
        for effect_name in selected_effects:
            parsed_args = []
            queued_effects.append((effect_name, parsed_args))

        emote_instance = Emote(
            id=0,  # Use a dummy id since this is a virtual Emote
            file_path=f"virtual/emote.{self.file_type}",  # Use real file name and type
            author_id=interaction.user.id,
            timestamp=discord.utils.utcnow(),
            original_url="Interaction based",  # Placeholder
            name=f"effect_{'_'.join(selected_effects)}.{self.file_type}",
            guild_id=interaction.guild_id or 0,
            usage_count=0,
            errors={}, issues={}, notes={}, followup={}, effect_chain={},
            img_data=self.image_buffer,
        )

        try:
            pipeline = await create_pipeline(interaction, interaction.message, emote_instance, queued_effects)
            emote = await execute_pipeline(pipeline)
        except Exception as e:
            await interaction.followup.send(f"An error occurred while applying effects: {e}", ephemeral=True)
            return

        if emote.img_data:
            image_buffer_out = io.BytesIO(emote.img_data)
            filename = emote.file_path.split("/")[-1] if emote.file_path else f"effected_image.{self.file_type}"
            file = discord.File(fp=image_buffer_out, filename=filename)

            try:
                await interaction.followup.send(
                    content="",
                    file=file,
                    ephemeral=False
                )
            except discord.Forbidden:
                await interaction.followup.send("Error: I lack permission to send the final message (followup failed).",
                                                ephemeral=True)
            except discord.HTTPException as e:
                await interaction.followup.send(f"Error sending the final image: {e}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"An unexpected error occurred sending the result: {e}", ephemeral=True)

        else:
            await interaction.followup.send("Effect processing completed, but no image data was generated.",
                                            ephemeral=True)


class EffectView(View):
    """A view containing the EffectSelect."""

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
        self.message: discord.Message | None = None
        if available_options:
            self.add_item(EffectSelect(
                options=available_options,
                image_buffer=image_buffer,
                file_type=file_type,
            ))

    async def on_timeout(self):
        """Called when the view times out. Disables all items in the view and updates the attached message."""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        self.clear_items()


@cog_i18n(_)
class UserCommands(commands.Cog):

    async def handle_apply_effect(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command callback to apply effects to images in a message."""

        image_attachment = None
        if message.attachments:
            for att in message.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    image_attachment = att
                    break

        if not image_attachment:
            await interaction.response.send_message("No direct image attachment found.", ephemeral=True)
            return

        try:
            image_buffer = await image_attachment.read()
        except (discord.HTTPException, discord.NotFound) as e:
            await interaction.response.send_message(f"Failed to download image: {e}", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message("Error reading image.", ephemeral=True)
            return

        # TODO: image compression / resize to be smaller

        try:
            effects_list_data = SlashCommands.EFFECTS_LIST
        except AttributeError:
            await interaction.response.send_message("Effect configuration missing.", ephemeral=True)
            return

        available_options = []
        is_owner = await self.bot.is_owner(interaction.user)
        for name, data in effects_list_data.items():
            perm = data.get("perm", "everyone").lower()
            func = data.get("func")
            if not func: continue
            allowed = (perm == "everyone") or (perm == "owner" and is_owner)
            if allowed:
                description = _parse_docstring_for_description(func)
                available_options.append(
                    discord.SelectOption(label=name.capitalize(), value=name, description=description))

        if not available_options:
            await interaction.response.send_message("No effects available for you.", ephemeral=True)
            return

        view = EffectView(
            available_options=available_options,
            image_buffer=image_buffer,
            file_type=image_attachment.content_type.split("/")[-1],
            timeout=180
        )

        await interaction.response.send_message(
            "Select effect(s) to apply:",
            view=view,
            ephemeral=False
        )
        view.message = await interaction.original_response()
