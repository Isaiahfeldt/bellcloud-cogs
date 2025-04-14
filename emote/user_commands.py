# --- START OF FILE user_commands.py ---

import discord
from discord.ui import View, Select
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import SlashCommands

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
        await interaction.response.defer(ephemeral=True, thinking=True)

        selected_effects = self.values

        await interaction.followup.send(
            f"Okay, I would apply effects: `{', '.join(selected_effects)}` to message ID `{self.target_message_id}`.",
            ephemeral=True
        )

        # Optionally disable the original message's view if needed, although deferring might be enough
        if interaction.message:
            print(f"Message Id: {interaction.message.id}")
            print(f"Message Content: {interaction.message.content}")
            await interaction.message.delete()


class EffectView(View):
    # Store the message this view is attached to if needed for timeout editing
    attached_message: discord.Message | None = None

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
            target_message_id=message.id,
            target_channel_id=interaction.channel_id,  # Channel where interaction happened
            timeout=180
        )

        await interaction.response.send_message(
            f"Select effect(s) to apply this message:",
            view=view,
            ephemeral=True
        )
        view.attached_message = await interaction.original_response()
