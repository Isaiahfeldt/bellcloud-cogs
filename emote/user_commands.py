# --- START OF FILE user_commands.py ---

from typing import Dict, Callable, Optional, Any  # For type hinting

import discord
from discord import app_commands
from discord.ui import Select, View
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


# --- Select Menu Class ---
# (No changes needed here)
class EffectSelect(Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(options),
            options=options,
            custom_id="effect_multi_select"
        )

    async def callback(self, interaction: discord.Interaction):
        selected_effects = ", ".join(self.values)
        response_message = f"You selected the following effects: `{selected_effects}`.\n"
        response_message += "(Next step: Apply these effects to the target message's image!)"
        await interaction.response.edit_message(content=response_message, view=None)


# --- View Class ---
# (No changes needed here)
class EffectView(View):
    message: discord.Message | None = None

    def __init__(self, available_options: list[discord.SelectOption], *, timeout=180):
        super().__init__(timeout=timeout)
        if available_options:
            self.add_item(EffectSelect(options=available_options))
        # else: handle no options case if necessary (e.g. log, don't add item)

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="Effect selection timed out.", view=self)
            except (discord.NotFound, discord.Forbidden):
                pass
        # self.stop()

    # Optional check
    # async def interaction_check(self, interaction: discord.Interaction) -> bool:
    #     return interaction.user.id == self.author_id


@cog_i18n(_)
class UserCommands(commands.Cog):
    def _parse_docstring_for_description(self, func: Callable) -> str:
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
                        return stripped_next_line.split('.')[0].strip()
        except Exception:
            pass
        return "No description available."

    @app_commands.user_install()
    @app_commands.command(name="effect", description="Choose effects to apply to an image.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def effect(self, interaction: discord.Interaction) -> None:
        """Sends a select menu to choose image effects based on permissions."""

        slash_cog = self.bot.get_cog("SlashCommands")
        if not slash_cog:
            await interaction.response.send_message(
                "Error: The SlashCommands cog is not loaded.", ephemeral=True
            )
            return

        # Safely get attributes from the SlashCommands cog
        effects_list_data: Optional[Dict[str, Dict[str, Any]]] = getattr(slash_cog, "EFFECTS_LIST", None)
        reaction_effects_data: Optional[Dict[str, Callable]] = getattr(slash_cog, "reaction_effects", None)

        if not effects_list_data:
            await interaction.response.send_message(
                "Error: The effects list data is missing.", ephemeral=True
            )
            return
        if not reaction_effects_data:
            await interaction.response.send_message(
                "Error: The reaction effects data is missing.", ephemeral=True
            )
            return

        # --- Create a reverse lookup map: function -> emoji ---
        # This makes finding the emoji for a given function much faster
        function_to_emoji: Dict[Callable, str] = {
            func: emoji for emoji, func in reaction_effects_data.items()
        }
        # -------------------------------------------------------

        available_options = []
        is_owner = await self.bot.is_owner(interaction.user)

        for name, data in effects_list_data.items():
            perm = data.get("perm", "everyone").lower()
            func = data.get("func")

            if not func:
                continue

            allowed = False
            if perm == "owner":
                allowed = is_owner
            # elif perm == "mod": # No guild context in DMs
            #     allowed = False
            elif perm == "everyone":
                allowed = True

            if allowed:
                description = self._parse_docstring_for_description(func)
                if len(description) > 100:
                    description = description[:97] + "..."

                # --- Look up the emoji for this function ---
                emoji_for_option = function_to_emoji.get(func)  # Returns None if not found
                # ------------------------------------------

                available_options.append(
                    discord.SelectOption(
                        label=name.capitalize(),
                        value=name,
                        description=description
                        # emoji=emoji_for_option  # Pass the found emoji (or None)
                    )
                )

        if not available_options:
            await interaction.response.send_message(
                "You do not have permission to use any effects, or no effects are configured.",
                ephemeral=True
            )
            return

        if len(available_options) > 25:
            # Consider how to handle > 25 options. Pagination? Multiple menus?
            # For now, just take the first 25 and warn.
            await interaction.response.send_message(
                "Warning: Too many effects available. Showing the first 25.",
                ephemeral=True  # Maybe send this before the main message?
            )
            available_options = available_options[:25]

        view = EffectView(available_options=available_options, timeout=180)

        await interaction.response.send_message(
            "Please select the effect(s) you want to apply:",
            view=view
        )
        view.message = await interaction.original_response()

# --- END OF FILE user_commands.py ---
