from emote.slash_commands import SlashCommands
from .base import Emote


async def debug(emote: Emote, mode: str = "basic") -> Emote:
    """
        User:
            Shows detailed information about the emote. Including its ID, file path, and other technical details.
            Useful when you need help troubleshooting issues with an emote.

            This effect can only be used once per emote.

        Parameters:
            emote (Emote): The emote object to pass through without modification.
            mode (str): The debug mode to use (currently only 'basic' is supported).

        Returns:
            Emote: The same emote object with debug information added.
    """

    SlashCommands.debug_enabled = True

    notes = emote.notes
    notes["emote_id"] = str(emote.id)
    notes["file_path"] = emote.file_path
    notes["author_id"] = emote.author_id
    notes["timestamp"] = emote.timestamp
    notes["original_url"] = emote.original_url
    notes["guild_id"] = emote.guild_id
    notes["usage_count"] = str(emote.usage_count + 1)

    if emote.img_data is not None:
        notes["img_data_length"] = f"{len(emote.img_data)} bytes"
    elif emote.effect_chain:
        notes["effect_chain"] = ", ".join(emote.effect_chain.keys())
    else:
        notes["img_data"] = "None"

    emote.notes = notes
    return emote
