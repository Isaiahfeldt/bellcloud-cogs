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
    # (Your existing code for this helper function - no changes needed)
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

    # Added original_message_id
    def __init__(self, options: list[discord.SelectOption], image_buffer: bytes, file_type: str,
                 original_message_id: int):
        """
        Initializes the EffectSelect menu.

        Args:
            options (list[discord.SelectOption]): A list of effect options.
            image_buffer (bytes): The image buffer to apply effects to.
            file_type (str): The file type of the image (e.g., "png", "jpg", "gif").
            original_message_id (int): The ID of the message the effect is applied to.
        """
        self.image_buffer = image_buffer
        self.file_type = file_type
        self.original_message_id = original_message_id  # Store the ID
        display_options = options[:25]  # Discord limit
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(display_options),
            options=display_options,
            custom_id="effect_select"  # custom_id can be static if state is in instance vars
        )

    async def callback(self, interaction: discord.Interaction):
        """Handles the user's selection of effects."""

        # --- CHANGE 1: Acknowledge ephemerally ---
        # Edit the ephemeral message to show processing.
        await interaction.response.edit_message(content="Processing selected effect(s)...", view=None)
        # If processing is long, could also use: await interaction.response.defer(ephemeral=True)

        selected_effects = self.values

        # --- Fetch the original message ---
        try:
            # interaction.channel is the channel where the command was invoked.
            original_message = await interaction.channel.fetch_message(self.original_message_id)
        except discord.NotFound:
            await interaction.edit_original_response(content="Error: Could not find the original message to reply to.")
            return
        except discord.Forbidden:
            await interaction.edit_original_response(content="Error: I lack permissions to fetch the original message.")
            return
        except discord.HTTPException as e:
            await interaction.edit_original_response(content=f"Error fetching original message: {e}")
            return

        # --- Effect processing logic (no changes needed here) ---
        queued_effects = []
        for effect_name in selected_effects:
            parsed_args = []  # Placeholder
            queued_effects.append((effect_name, parsed_args))

        emote_instance = Emote(
            id=0,
            file_path=f"virtual/emote.{self.file_type}",
            author_id=interaction.user.id,  # Use invoking user's ID
            timestamp=discord.utils.utcnow(),  # Use timezone-aware UTC time
            original_url=original_message.jump_url,  # Link to the source message
            name=f"effect_{'_'.join(selected_effects)}.{self.file_type}",
            guild_id=interaction.guild_id or 0,
            usage_count=0,
            errors={}, issues={}, notes={}, followup={}, effect_chain={},
            img_data=self.image_buffer,
        )

        try:
            pipeline = await create_pipeline(interaction, original_message, emote_instance, queued_effects)
            emote = await execute_pipeline(pipeline)
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred while applying effects: {e}")
            return

        if emote.img_data:
            image_buffer = io.BytesIO(emote.img_data)
            filename = emote.file_path.split("/")[-1] if emote.file_path else f"effected_image.{self.file_type}"
            file = discord.File(fp=image_buffer, filename=filename)

            try:
                await interaction.channel.send(
                    content="",
                    file=file,
                    reference=original_message.to_reference(fail_if_not_exists=False)  # Reply!
                )
                await interaction.edit_original_response(content="Effect applied successfully!")

            except discord.Forbidden:
                await interaction.edit_original_response(
                    content="Error: I don't have permission to send messages or reply in this channel.")
            except discord.HTTPException as e:
                await interaction.edit_original_response(content=f"Error sending the final image: {e}")
            except Exception as e:
                await interaction.edit_original_response(
                    content=f"An unexpected error occurred while sending the result: {e}")
        else:
            await interaction.edit_original_response(
                content="Effect processing completed, but no image data was generated.")


class EffectView(View):
    """A view that allows users to select and apply effects to a Discord message."""

    # Added original_message_id
    def __init__(self, available_options: list[discord.SelectOption], image_buffer: bytes, file_type: str,
                 original_message_id: int, *, timeout=180):
        """
        Initializes the EffectView.

        Args:
            available_options (list[discord.SelectOption]): A list of available effect options.
            image_buffer (bytes): The image buffer to apply effects to.
            file_type (str): The file type of the image (e.g., "png", "jpg", "gif").
            original_message_id (int): The ID of the message the effect is applied to.
            timeout (int, optional): The timeout for the view in seconds. Defaults to 180.
        """
        super().__init__(timeout=timeout)
        # Store the message object for the ephemeral message this view is attached to
        self.ephemeral_interaction_message: discord.WebhookMessage | None = None
        if available_options:
            self.add_item(EffectSelect(
                options=available_options,
                image_buffer=image_buffer,
                file_type=file_type,
                original_message_id=original_message_id  # Pass the ID down
            ))

    async def on_timeout(self):
        """Called when the view times out. Disables all items in the view and updates the ephemeral message."""
        if self.ephemeral_interaction_message:
            try:
                for item in self.children:
                    item.disabled = True
                # Edit the ephemeral message
                await self.ephemeral_interaction_message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                # Ignore errors if the message is gone or editing fails
                pass
        self.clear_items()


@cog_i18n(_)
class UserCommands(commands.Cog):
    # Assuming self.bot and SlashCommands.EFFECTS_LIST are available via __init__ or class attributes

    # This method is assumed to be the callback for a discord.app_commands.ContextMenu
    async def handle_apply_effect(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command callback to apply effects to images in a message."""

        image_attachment = None
        if message.attachments:
            for att in message.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    image_attachment = att
                    break

        if not image_attachment:
            await interaction.response.send_message(
                "This message does not have a direct image attachment.",
                ephemeral=True
            )
            return

        # Download the image safely
        try:
            # Consider adding a size check here before reading if large files are a concern
            # if image_attachment.size > MAX_ALLOWED_SIZE: ...
            image_buffer = await image_attachment.read()
        except (discord.HTTPException, discord.NotFound) as e:
            await interaction.response.send_message(f"Failed to download the image: {e}", ephemeral=True)
            return
        except Exception as e:  # Catch potential other read errors
            # logger.exception("Error reading image attachment:")
            await interaction.response.send_message(f"An unexpected error occurred reading the image.", ephemeral=True)
            return

        # TODO: image compression / resize to be smaller (if needed)

        # Access effects list (ensure it's loaded, e.g., self.EFFECTS_LIST)
        try:
            # Assuming SlashCommands is accessible, potentially via self.slash_commands
            # Or if EFFECTS_LIST is a static/class variable: SlashCommands.EFFECTS_LIST
            effects_list_data = SlashCommands.EFFECTS_LIST
        except AttributeError:
            # logger.error("EFFECTS_LIST not found on SlashCommands.")
            await interaction.response.send_message("Effect configuration is missing.", ephemeral=True)
            return

        available_options = []
        is_owner = await self.bot.is_owner(interaction.user)  # Assuming self.bot exists

        for name, data in effects_list_data.items():
            perm = data.get("perm", "everyone").lower()
            func = data.get("func")
            if not func: continue  # Skip effects without a function mapping

            allowed = False
            if perm == "owner":
                allowed = is_owner
            elif perm == "everyone":
                allowed = True
            # Add other permission checks here (roles, etc.) if applicable

            if allowed:
                description = _parse_docstring_for_description(func)
                available_options.append(
                    discord.SelectOption(label=name.capitalize(), value=name, description=description)
                )

        if not available_options:
            await interaction.response.send_message(
                "No effects are available for you to use on this image.",
                ephemeral=True
            )
            return

        view = EffectView(
            available_options=available_options,
            image_buffer=image_buffer,
            file_type=image_attachment.content_type.split("/")[-1],
            original_message_id=message.id,  # Pass the original message ID
            timeout=180
        )

        await interaction.response.send_message(
            f"Select effect(s) to apply:",
            view=view,
            ephemeral=True
        )
        # Store the ephemeral WebhookMessage for later editing (e.g., on timeout)
        view.ephemeral_interaction_message = await interaction.original_response()
