# modals.py
import discord
from discord.ui import Modal, TextInput


class EmoteNameModal(Modal):
    def __init__(self, callback):
        super().__init__(title="Name Your Emote")
        self.callback = callback
        self.name = TextInput(
            label="Emote Name",
            placeholder="Enter a name for your emote...",
            max_length=32
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, self.name.value)
