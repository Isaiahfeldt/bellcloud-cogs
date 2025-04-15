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
    # (Your existing helper function - no changes needed)
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

    # No need for original_message_id here anymore if using followup
    def __init__(self, options: list[discord.SelectOption], image_buffer: bytes, file_type: str):
        self.image_buffer = image_buffer
        self.file_type = file_type
        display_options = options[:25]
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(display_options),
            options=display_options,
            custom_id="effect_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handles the user's selection of effects using followup."""

        # --- CHANGE 1: Acknowledge by EDITING the original (non-ephemeral) message ---
        # This removes the select menu and shows processing.
        try:
            await interaction.response.edit_message(content="Processing selected effect(s)...", view=None)
        except discord.NotFound:
            # If the original message was deleted before selection, we can't proceed easily.
            # Send an ephemeral message to the user.
            try:
                await interaction.followup.send("The original selection message seems to be gone.", ephemeral=True)
            except discord.HTTPException:
                pass  # Ignore if followup fails too
            return
        except discord.HTTPException as e:
            # Log error, inform user ephemerally
            # logger.error(f"Failed to edit interaction message: {e}")
            try:
                await interaction.followup.send(f"An error occurred acknowledging selection: {e}", ephemeral=True)
            except discord.HTTPException:
                pass
            return

        selected_effects = self.values

        # --- Effect processing logic (using self.image_buffer) ---
        queued_effects = []
        for effect_name in selected_effects:
            parsed_args = []  # Placeholder
            queued_effects.append((effect_name, parsed_args))

        emote_instance = Emote(
            id=0,
            file_path=f"virtual/emote.{self.file_type}",
            author_id=interaction.user.id,
            timestamp=discord.utils.utcnow(),
            original_url=f"Interaction based",  # Placeholder as original msg object isn't needed here
            name=f"effect_{'_'.join(selected_effects)}.{self.file_type}",
            guild_id=interaction.guild_id or 0,
            usage_count=0,
            errors={}, issues={}, notes={}, followup={}, effect_chain={},
            img_data=self.image_buffer,
        )

        try:
            # Adapt pipeline call if needed (pass interaction?)
            pipeline = await create_pipeline(interaction, None, emote_instance, queued_effects)
            emote = await execute_pipeline(pipeline)
        except Exception as e:
            # logger.exception("Error during effect pipeline execution:")
            # Use followup to report error since original message was edited
            await interaction.followup.send(f"An error occurred while applying effects: {e}", ephemeral=True)
            return

        if emote.img_data:
            image_buffer_out = io.BytesIO(emote.img_data)
            filename = emote.file_path.split("/")[-1] if emote.file_path else f"effected_image.{self.file_type}"
            file = discord.File(fp=image_buffer_out, filename=filename)

            # --- CHANGE 2: Use interaction.followup.send ---
            # This uses the interaction token for permission and replies to the interaction
            # (which is now associated with the non-ephemeral edited message)
            try:
                # Send the final image non-ephemerally
                await interaction.followup.send(
                    content="",  # Optional content
                    file=file,
                    ephemeral=False  # Ensure final result is visible
                )
            except discord.Forbidden:
                # This *shouldn't* happen now with followup, but handle defensively
                await interaction.followup.send("Error: I lack permission to send the final message (followup failed).",
                                                ephemeral=True)
            except discord.HTTPException as e:
                await interaction.followup.send(f"Error sending the final image: {e}", ephemeral=True)
            except Exception as e:
                # logger.exception("Unexpected error sending final image followup:")
                await interaction.followup.send(f"An unexpected error occurred sending the result: {e}", ephemeral=True)

        else:
            # Use followup for the error message
            await interaction.followup.send("Effect processing completed, but no image data was generated.",
                                            ephemeral=True)


class EffectView(View):
    """A view containing the EffectSelect."""

    # No need for original_message_id or ephemeral_interaction_message here anymore
    def __init__(self, available_options: list[discord.SelectOption], image_buffer: bytes, file_type: str, *,
                 timeout=180):
        super().__init__(timeout=timeout)
        # Store the message this view is attached to (which will be non-ephemeral)
        self.message: discord.Message | None = None
        if available_options:
            self.add_item(EffectSelect(
                options=available_options,
                image_buffer=image_buffer,
                file_type=file_type,
                # Removed original_message_id
            ))

    async def on_timeout(self):
        """Disables items and edits the non-ephemeral message on timeout."""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass  # Ignore if message is gone or editing fails
        self.clear_items()  # Stop listening


@cog_i18n(_)
class UserCommands(commands.Cog):
    # Assuming self.bot and SlashCommands.EFFECTS_LIST are available

    async def handle_apply_effect(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command callback."""

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
            # logger.exception("Error reading image attachment:")
            await interaction.response.send_message("Error reading image.", ephemeral=True)
            return

        # --- Get available effects (same as before) ---
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
            allowed = (perm == "everyone") or (perm == "owner" and is_owner)  # Simplified
            if allowed:
                description = _parse_docstring_for_description(func)
                available_options.append(
                    discord.SelectOption(label=name.capitalize(), value=name, description=description))

        if not available_options:
            await interaction.response.send_message("No effects available for you.", ephemeral=True)
            return

        # --- Create View (removed original_message_id) ---
        view = EffectView(
            available_options=available_options,
            image_buffer=image_buffer,
            file_type=image_attachment.content_type.split("/")[-1],
            timeout=180
        )

        # --- CHANGE 3: Send initial response NON-ephemerally ---
        await interaction.response.send_message(
            "Select effect(s) to apply:",
            view=view,
            ephemeral=False  # Make this message visible
        )
        # Store the sent message object in the view for timeout handling
        view.message = await interaction.original_response()

# --- END OF FILE user_commands.py ---
