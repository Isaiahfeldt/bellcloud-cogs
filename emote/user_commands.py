import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from emote.slash_commands import SlashCommands

_ = Translator("Emote", __file__)


@cog_i18n(_)
class UserCommands(commands.Cog):

    @app_commands.user_install()
    @app_commands.command(name="effect", description="Adds effects to images")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    @app_commands.describe(effect_name="Name of the effect to apply")
    @app_commands.choices(effect_name=[
        app_commands.Choice(name=name, value=name) for name in SlashCommands.EFFECTS_LIST
    ])
    async def effect(self, interaction: discord.Interaction, effect_name: str) -> None:
        effect_info = SlashCommands.EFFECTS_LIST.get(effect_name.lower())

        if not effect_info:
            await interaction.response.send_message(f"Effect '{effect_name}' not found.", ephemeral=True)
            return

        # Check user's permission for the effect
        perm = effect_info.get("perm", "everyone")
        allowed = False
        if perm == "owner":
            allowed = await SlashCommands.bot.is_owner(interaction.user)
        elif perm == "mod":
            allowed = interaction.user.guild_permissions.manage_messages
        elif perm == "everyone":
            allowed = True

        if not allowed:
            await interaction.response.send_message(
                "You do not have permission to view details for this effect.",
                ephemeral=True
            )
            return

        effect_func = effect_info.get("func")

        await interaction.response.send_message(f'Here is your function: {effect_func}')
