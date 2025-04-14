# --- START OF FILE user_commands.py ---

import discord
from discord.ui import View
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


class EffectSelect(discord.ui.Select):
    """A select menu for choosing effects to apply to a message."""

    def __init__(self, options: list[discord.SelectOption], target_message_id: int, target_channel_id: int):
        """
        Initializes the EffectSelect menu.

        Args:
            options (list[discord.SelectOption]): A list of effect options.
            target_message_id (int): The ID of the message to apply effects to.
            target_channel_id (int): The ID of the channel containing the message.
        """
        self.target_message_id = target_message_id
        self.target_channel_id = target_channel_id
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

        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_effects = self.values
        await interaction.followup.send(
            f"Okay, I will apply effects: `{', '.join(selected_effects)}` to message ID `{self.target_message_id}`.",
            ephemeral=True
        )

        if interaction.message:
            print(f"Message Id: {interaction.message.id}")
            print(f"Message Content: {interaction.message.content}")
            await interaction.message.edit(content="Cancelled", view=None)


class EffectView(View):
    """A view that allows users to select and apply effects to a Discord message."""

    def __init__(self, available_options: list[discord.SelectOption], target_message_id: int, target_channel_id: int, *,
                 timeout=180):
        """
        Initializes the EffectView.

        Args:
            available_options (list[discord.SelectOption]): A list of available effect options.
            target_message_id (int): The ID of the message to apply the effect to.
            target_channel_id (int): The ID of the channel where the target message is located.
            timeout (int, optional): The timeout for the view in seconds. Defaults to 180.
        """
        super().__init__(timeout=timeout)
        self.attached_message: discord.Message | None = None
        if available_options:
            self.add_item(EffectSelect(
                options=available_options,
                target_message_id=target_message_id,
                target_channel_id=target_channel_id
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
