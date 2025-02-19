#  Copyright (c) 2024, Isaiah Feldt
#  ͏
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU Affero General Public License (AGPL) as published by
#     - the Free Software Foundation, either version 3 of this License,
#     - or (at your option) any later version.
#  ͏
#     - This program is distributed in the hope that it will be useful,
#     - but without any warranty, without even the implied warranty of
#     - merchantability or fitness for a particular purpose.
#     - See the GNU Affero General Public License for more details.
#  ͏
#     - You should have received a copy of the GNU Affero General Public License
#     - If not, please see <https://www.gnu.org/licenses/#GPL>.
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict

import aiohttp


@dataclass
class Emote:
    """
    Data class representing an emote.

    Attributes:
        id (int): The unique identifier of the emote.
        file_path (str): The file path of the emote image.
        author_id (int): The unique identifier of the emote's author.
        timestamp (datetime): The timestamp when the emote was created.
        original_url (str): The original URL from which the emote was downloaded.
        name (str): The name of the emote.
        guild_id (int): The unique identifier of the guild the emote belongs to.
        usage_count (int): The number of times the emote has been used.
        errors (Optional[str]): An optional error message associated with the emote. Defaults to `None`.

    This class is decorated with the `dataclass` decorator for convenient attribute access and comparison.

    Example usage:

        emote = Emote(
            id=1,
            file_path="352972393368780810/emote.png",
            author_id=1234,
            timestamp=datetime.now(),
            original_url="https://example.com/emote.png",
            name="emote",
            guild_id=5678,
            usage_count=10,
            error=None
        )

    TODO: Currently the Emote

    """
    id: int
    file_path: str
    author_id: int
    timestamp: datetime
    original_url: str
    name: str
    guild_id: int
    usage_count: int
    errors: Dict[str, str] = field(default_factory=dict)
    issues: Dict[str, str] = field(default_factory=dict)
    notes: Dict[str, str] = field(default_factory=dict)
    img_data: Optional[bytes] = None


async def initialize(emote: Emote) -> Emote:
    """
    Fetch the emote image from the provided original_url and store the image data
    in-memory in the emote.img_data attribute. If an error occurs during the fetch,
    record the error in the emote.error dictionary under the key 'initialize'.

    :param emote: The Emote object to be initialized.
    :return: The initialized Emote object with its image data loaded or an error noted.
    """
    emote.original_url = f"https://media.bellbot.xyz/emote/{emote.file_path}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(emote.original_url) as response:
                if response.status == 200:
                    emote.img_data = await response.read()
                else:
                    emote.errors["initialize"] = f"HTTP error status: {response.status}"
    except Exception as e:
        emote.errors["initialize"] = f"Exception occurred: {str(e)}"

    from emote.slash_commands import SlashCommands
    emote.notes["was_cached"] = SlashCommands.was_cached

    return emote


async def latency(emote: Emote) -> Emote:
    from emote.slash_commands import SlashCommands
    SlashCommands.latency_enabled = not SlashCommands.latency_enabled
    return emote


async def flip(emote: Emote) -> Emote:
    emote.file_path = emote.file_path[::-1]  # Reverse the string
    emote_dict = asdict(emote)  # Convert Emote object back to dict (requires from dataclasses import asdict)
    emote = Emote(**emote_dict)  # Convert dict back to Emote object

    return emote


async def debug(emote: Emote, mode: str = "basic") -> Emote:
    from emote.slash_commands import SlashCommands
    SlashCommands.debug_enabled = True

    # Create a dictionary to hold the debug information.
    notes = emote.notes

    # Add key-value pairs for each debug detail.
    notes["emote_id"] = str(emote.id)
    notes["file_path"] = emote.file_path
    notes["author_id"] = emote.author_id
    notes["timestamp"] = emote.timestamp
    notes["original_url"] = emote.original_url
    notes["guild_id"] = emote.guild_id
    notes["usage_count"] = str(emote.usage_count)

    emote.notes["debug_mode"] = mode

    # TODO move this logic to send_debug_embed in chat.py
    # if emote.error is not None:
    #     notes["error"] = str(emote.error)
    # else:
    #     notes["error"] = "None"

    if emote.img_data is not None:
        notes["img_data_length"] = f"{len(emote.img_data)} bytes"
    else:
        notes["img_data"] = "None"

    emote.notes = notes
    return emote


async def train(emote: Emote, amount: int = 3) -> Emote:
    """
        Duplicate the provided Emote for a specified number of times within a valid range.

        Parameters:
            emote (Emote): The emote object to be trained.
            amount (int): The number of times to train the emote. If invalid, defaults
                to 3. Must be an integer between 1 and 6, inclusive.

        Returns:
            Emote: The updated emote object with the training details and potential
                error messages.
    """
    from emote.slash_commands import SlashCommands

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        amount = 3
        emote.errors["train"] = "Train amount must be a number."
    else:
        if not 1 <= amount <= 6:
            amount = min(max(amount, 1), 6)
            emote.errors["train"] = "Train amount must be between values of 1 and 6."

    SlashCommands.train_count = amount
    return emote

async def flip(emote: Emote, direction: str = "h") -> Emote:
    """
    Flips the emote's image without modifying filename/path.
    Directions: "h" (horizontal), "v" (vertical), "hv/vh" (both).
    Stores errors in emote.error['flip'].
    """
    if emote.img_data is None:
        emote.error["flip"] = "No image data available"
        return emote

    try:
        from PIL import Image
        import io

        direction = direction.lower()
        valid = {'h', 'v', 'hv', 'vh'}
        if direction not in valid:
            raise ValueError(f"Invalid direction '{direction}'. Use h/v/hv/vh")

        with Image.open(io.BytesIO(emote.img_data)) as img:
            # Apply flips
            if 'h' in direction:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            if 'v' in direction:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)

            # Save to buffer without changing filename
            output_buffer = io.BytesIO()
            img.save(output_buffer, format=img.format)
            emote.img_data = output_buffer.getvalue()

    except Exception as e:
        emote.error["flip"] = str(e)
    
    return emote
