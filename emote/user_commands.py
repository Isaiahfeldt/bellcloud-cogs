# --- START OF FILE user_commands.py ---

import discord
from discord import app_commands
from discord.ui import Select, View
from redbot.core import commands  # Import checks for is_owner
from redbot.core.bot import Red  # Import Red type hint for bot
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


# --- Select Menu Class ---
# (Keep EffectSelect as before, it doesn't need changes for this part)
class EffectSelect(Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,
            max_values=len(options),  # Allow selecting multiple options
            options=options,
            custom_id="effect_multi_select"  # Add a custom_id for persistence if needed
        )

    async def callback(self, interaction: discord.Interaction):
        selected_effects = ", ".join(self.values)
        response_message = f"You selected the following effects: `{selected_effects}`.\n"
        response_message += "(Next step: Apply these effects to the target message's image!)"

        # Update the message and disable the view
        await interaction.response.edit_message(content=response_message, view=None)


# --- View Class ---
# Modify the View to accept the options during initialization
class EffectView(View):
    # Store the original message for potential editing on timeout
    message: discord.Message | None = None

    def __init__(self, available_options: list[discord.SelectOption], *, timeout=180):
        super().__init__(timeout=timeout)

        # Check if there are any options before adding the select menu
        if not available_options:
            # Handle the case where no options are available (e.g., log or potentially don't add the item)
            # For now, we'll assume the command checks this before creating the view
            pass
        else:
            # Add the Select menu *using the passed-in options*
            self.add_item(EffectSelect(options=available_options))

    async def on_timeout(self):
        if self.message:
            try:
                # Disable all components visually
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="Effect selection timed out.", view=self)
            except discord.NotFound:
                pass  # Message was deleted
            except discord.Forbidden:
                pass  # Missing permissions
        # Clean up the view reference associated with the message_id if using persistent views
        # self.stop() # Stop listening for interactions

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Optional: Ensure only the original command user can interact
        # return interaction.user.id == self.author_id # You'd need to store author_id in __init__
        return True  # Allow anyone for now


@cog_i18n(_)
class UserCommands(commands.Cog):
    # Add bot type hint for accessing other cogs and checks
    def __init__(self, bot: Red):
        self.bot = bot
        # You might need to ensure SlashCommands cog is loaded and EFFECTS_LIST is ready
        # This depends on your cog structure and load order.

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
                # Get the next non-empty line after "User:"
                for next_line in lines[user_line_index + 1:]:
                    stripped_next_line = next_line.strip()
                    if stripped_next_line:
                        # Take the first sentence
                        return stripped_next_line.split('.')[0].strip()
        except Exception:  # Catch potential errors during parsing
            pass  # Log error if needed
        return "No description available."  # Default fallback

    @app_commands.user_install()
    @app_commands.command(name="effect", description="Choose effects to apply to an image.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def effect(self, interaction: discord.Interaction) -> None:
        """Sends a select menu to choose image effects based on permissions."""

        slash_cog = self.bot.get_cog("SlashCommands")  # Get the SlashCommands cog instance
        if not slash_cog or not hasattr(slash_cog, "EFFECTS_LIST"):
            await interaction.response.send_message(
                "Error: The effects list is currently unavailable.", ephemeral=True
            )
            return

        effects_list_data = slash_cog.EFFECTS_LIST
        available_options = []

        # Check if the user is the bot owner
        is_owner = await self.bot.is_owner(interaction.user)

        for name, data in effects_list_data.items():
            perm = data.get("perm", "everyone").lower()
            func = data.get("func")

            if not func:  # Skip if no function is associated
                continue

            allowed = False
            if perm == "owner":
                allowed = is_owner
            # elif perm == "mod":
            # In DMs, guild_permissions aren't applicable.
            # Decide how to handle 'mod'. We'll disallow it in DMs.
            # allowed = False # Explicitly disallow mod commands in DMs
            elif perm == "everyone":
                allowed = True
            # Add any other permission levels here

            if allowed:
                # Parse the description from the function docstring
                description = self._parse_docstring_for_description(func)
                # Truncate description if it's too long for Discord SelectOption
                if len(description) > 100:
                    description = description[:97] + "..."

                # Create the SelectOption
                available_options.append(
                    discord.SelectOption(
                        label=name.capitalize(),  # Use the effect name as the label
                        value=name,  # Use the original key name as the value for the callback
                        description=description  # Use the parsed docstring part
                    )
                )

        # --- Send the response ---
        if not available_options:
            await interaction.response.send_message(
                "You do not have permission to use any effects, or no effects are configured.",
                ephemeral=True
            )
            return

        # Limit to 25 options max for a select menu
        if len(available_options) > 25:
            await interaction.response.send_message(
                "Warning: Too many effects available. Showing the first 25.",
                ephemeral=True  # Send warning ephemerally maybe?
            )
            available_options = available_options[:25]

        # Create an instance of our View, passing the dynamic options
        view = EffectView(available_options=available_options,
                          timeout=180)  # Add author_id if needed for interaction_check

        await interaction.response.send_message(
            "Please select the effect(s) you want to apply:",
            view=view
        )
        # Store the message object on the view if needed for timeout editing
        view.message = await interaction.original_response()
