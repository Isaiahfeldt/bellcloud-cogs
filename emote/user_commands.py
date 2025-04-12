# --- START OF FILE user_commands.py ---

import discord
from discord import app_commands
from discord.ui import Select, View  # Import Select and View
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)

# --- Dummy Data ---
# In a real scenario, this might come from your cog's config or another source
# For now, just a list of effect names
AVAILABLE_EFFECTS = ["Blur", "Sharpen", "Invert", "Sepia", "Pixelate", "Greyscale", "Rotate"]


# --- Select Menu Class ---
class EffectSelect(Select):
    def __init__(self, options: list[discord.SelectOption]):
        # Set the placeholder text that will be shown on the dropdown
        # Also configure minimum and maximum selections
        super().__init__(
            placeholder="Choose one or more effects...",
            min_values=1,  # User must select at least 1
            max_values=len(options),  # User can select up to all available options
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # This is called when the user makes a selection
        # 'self.values' is a list of the 'value' strings of the selected options

        # Acknowledge the selection - You can edit the original message
        # For now, just confirm what was selected
        selected_effects = ", ".join(self.values)
        response_message = f"You selected the following effects: `{selected_effects}`.\n"
        response_message += "(Next step: Apply these effects to the target message's image!)"

        # Disable the select menu after selection and remove the view
        self.disabled = True
        await interaction.response.edit_message(content=response_message, view=None)
        # If you wanted to send a new message instead:
        # await interaction.response.send_message(f"You selected: {selected_effects}", ephemeral=True)
        # await interaction.message.edit(view=None) # remove menu from original message


# --- View Class ---
# A View holds UI components like Select menus and Buttons
class EffectView(View):
    def __init__(self, *, timeout=180):  # Add a timeout (in seconds)
        super().__init__(timeout=timeout)

        # Create the options for the select menu
        select_options = [
            discord.SelectOption(
                label=effect_name,
                description=f"Apply the {effect_name} effect.",  # Optional description
                value=effect_name  # The value returned when selected
            ) for effect_name in AVAILABLE_EFFECTS
        ]

        # Add the Select menu to the view
        self.add_item(EffectSelect(options=select_options))

    # Optional: Handle view timeout
    async def on_timeout(self):
        # Find the select menu item and disable it
        for item in self.children:
            if isinstance(item, Select):
                item.disabled = True
        # Try to edit the original message if possible (interaction might be gone)
        # This requires storing the original message or interaction if you need reliable editing on timeout
        # For simplicity here, we won't edit, just know the view timed out.
        print("Effect selection view timed out.")
        # If you had access to the original message object 'message':
        # try:
        #     await message.edit(content="Effect selection timed out.", view=self) # Pass 'self' to show disabled components
        # except discord.NotFound:
        #     pass # Message was deleted


@cog_i18n(_)
class UserCommands(commands.Cog):

    # Keep your commented-out code if you plan to use it later
    # ... (previous commented code) ...

    @app_commands.user_install()
    @app_commands.command(name="effect", description="Choose effects to apply to an image.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def effect(self, interaction: discord.Interaction) -> None:
        """Sends a select menu to choose image effects."""

        # Create an instance of our View
        view = EffectView()

        # Send the message with the View (which contains the Select menu)
        # Note: We are NOT using ephemeral=True here because we want to edit
        # the message later in the select menu's callback.
        # Ephemeral messages cannot be easily edited after the initial response window.
        await interaction.response.send_message(
            "Please select the effects you want to apply:",
            view=view
        )
        # Optional: Store the message if you need to edit it later (e.g., on timeout)
        # view.message = await interaction.original_response() # This gets the message object

# --- END OF FILE user_commands.py ---
