from emote.slash_commands import SlashCommands
from .base import Emote


async def latency(emote: Emote) -> Emote:
    """
    Toggles the latency measurement flag for subsequent processing.

    User:
        Displays how long it takes to process your emote.
        Use this to see processing time in milliseconds.

        This effect can only be used once per emote.

    Parameters:
        emote (Emote): The emote object to pass through without modification.

    Returns:
        Emote: The same emote object after toggling the latency flag.
    """
    SlashCommands.latency_enabled = not SlashCommands.latency_enabled

    return emote
