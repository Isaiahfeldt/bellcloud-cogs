import discord
from discord import app_commands
from discord.ui import Select, View
from redbot.core import commands  # checks might still be useful if you add other permission checks
# Red type hint import removed as __init__ is gone, but can be kept if preferred for type hints elsewhere
# from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import SlashCommands

_ = Translator("Emote", __file__)


# --- Select Menu Class ---
class EffectSelect(Select):
    def __init__(self, options: list[discord.SelectOption]):
        # Ensure we don't exceed 25 options
        display_options = options[:25]
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(display_options),  # Can select up to the number of displayed options
            options=display_options,
            custom_id="effect_multi_select"
        )

    async def callback(self, interaction: discord.Interaction):
        # self.values contains the 'value' strings of selected options
        selected_effects = ", ".join(self.values)
        response_message = f"You selected the following effects: `{selected_effects}`.\n"
        response_message += "(Next step: Apply these effects to the target message's image!)"

        # Update the message and disable the view
        await interaction.response.edit_message(content=response_message, view=None)


# --- View Class ---
class EffectView(View):
    message: discord.Message | None = None

    def __init__(self, available_options: list[discord.SelectOption], *, timeout=180):
        super().__init__(timeout=timeout)

        if not available_options:
            pass
        else:
            # Add the Select menu using the passed-in options
            self.add_item(EffectSelect(options=available_options))

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden):
                # Ignore if message deleted or permissions are missing
                pass
        # self.stop() # Stop listening


@cog_i18n(_)
class UserCommands(commands.Cog):
    # No __init__(self, bot) here - relies on the main cog's __init__

    # --- Helper Function to Parse Docstring ---
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
                        # Take the first sentence, max 100 chars for description
                        desc = stripped_next_line.split('.')[0].strip()
                        return desc[:100]
        except Exception:
            # Log error maybe? logging.exception("Error parsing docstring")
            pass
        return "No description available."[:100]  # Fallback, ensure max length

    @app_commands.user_install()
    @app_commands.command(name="effect", description="Choose effects to apply to an image.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def effect(self, interaction: discord.Interaction) -> None:
        """Sends a select menu to choose image effects based on permissions."""

        # Assume EFFECTS_LIST is a dictionary {name: {"func": func, "perm": perm_level}}
        effects_list_data = SlashCommands.EFFECTS_LIST
        available_options = []

        # Check ownership using self.bot.is_owner (inherited from Emotes cog)
        is_owner = await self.bot.is_owner(interaction.user)

        for name, data in effects_list_data.items():
            perm = data.get("perm", "everyone").lower()
            func = data.get("func")

            if not func:
                continue  # Skip effects without a function defined

            allowed = False
            if perm == "owner":
                allowed = is_owner
            elif perm == "everyone":
                allowed = True

            if allowed:
                description = self._parse_docstring_for_description(func)
                available_options.append(
                    discord.SelectOption(
                        label=name.capitalize(),
                        value=name,
                        description=description
                    )
                )

        # --- Send the response ---
        if not available_options:
            await interaction.response.send_message(
                "You do not have permission to use any available effects, or no effects are configured for DM use.",
                ephemeral=True
            )
            return

        # Create the view with the filtered options
        view = EffectView(available_options=available_options, timeout=180)

        # Send message with the view
        await interaction.response.send_message(
            "Please select the effect(s) you want to apply:",
            view=view
        )
        # Store the message for potential timeout editing
        view.message = await interaction.original_response()
