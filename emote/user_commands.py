# --- START OF FILE user_commands.py ---

import discord
from discord import app_commands
from discord.ui import Select, View
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import SlashCommands

# Assuming SlashCommands is accessible via self.bot.get_cog("SlashCommands")
# from emote.slash_commands import SlashCommands # Adjust if needed

_ = Translator("Emote", __file__)


# --- Select Menu Class ---
class EffectSelect(Select):
    # Add attributes to store context passed from the view
    def __init__(self, options: list[discord.SelectOption], target_message_id: int, target_channel_id: int):
        self.target_message_id = target_message_id
        self.target_channel_id = target_channel_id
        # Ensure we don't exceed 25 options
        display_options = options[:25]
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(display_options),
            options=display_options,
            custom_id="effect_context_multi_select"  # Changed ID slightly for clarity
        )

    async def callback(self, interaction: discord.Interaction):
        # Defer the response while processing
        await interaction.response.defer(ephemeral=True, thinking=True)

        selected_effects = self.values  # List of effect names (strings)

        # --- Simple confirmation for now ---
        await interaction.followup.send(
            f"Okay, I would apply effects: `{', '.join(selected_effects)}` to message ID `{self.target_message_id}`.",
            ephemeral=True  # Keep confirmation ephemeral until result is ready
        )


# --- View Class ---
class EffectView(View):
    # Store the message this view is attached to if needed for timeout editing
    attached_message: discord.Message | None = None

    # Accept target message info to pass down to the Select menu
    def __init__(self, available_options: list[discord.SelectOption], target_message_id: int, target_channel_id: int, *,
                 timeout=180):
        super().__init__(timeout=timeout)

        if available_options:
            self.add_item(EffectSelect(
                options=available_options,
                target_message_id=target_message_id,
                target_channel_id=target_channel_id
            ))

    async def on_timeout(self):
        if self.attached_message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.attached_message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden):
                pass


@cog_i18n(_)
class UserCommands(commands.Cog):

    def _parse_docstring_for_description(self, func) -> str:
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

    # --- Callback method for the "Apply Effect" context menu ---
    @app_commands.user_install()  # Enable for user installs
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)  # Restrict to DMs/Groups
    # This method needs to be part of the Emotes class to access self.bot etc.
    async def apply_effect_message_callback(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to apply effects to images in a message."""

        # Optional: Check if message has image attachments first
        has_image = message.attachments and any(
            att.content_type and att.content_type.startswith("image/") for att in message.attachments)
        # You might also check embeds for images if desired
        # has_image = has_image or any(embed.image or embed.thumbnail for embed in message.embeds)

        if not has_image:
            await interaction.response.send_message(
                "I couldn't find a direct image attachment in that message to apply effects to.",
                ephemeral=True
            )
            return

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
                description = self._parse_docstring_for_description(func)
                available_options.append(
                    discord.SelectOption(label=name.capitalize(), value=name, description=description)
                )

        if not available_options:
            await interaction.response.send_message(
                "You don't have permission for any effects, or none are configured for DM use.",
                ephemeral=True
            )
            return

        # Create the view, passing the target message's ID and channel ID
        view = EffectView(
            available_options=available_options,
            target_message_id=message.id,
            target_channel_id=interaction.channel_id,  # Channel where interaction happened
            timeout=180
        )

        # Send the view ephemerally - the result will be a separate message
        await interaction.response.send_message(
            f"Select effect(s) to apply to message `{message.id}`:",
            view=view,
            ephemeral=True
        )
        # Store the ephemeral message on the view if needed for timeout editing
        view.attached_message = await interaction.original_response()
