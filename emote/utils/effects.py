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
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


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
        error (Optional[str]): An optional error message associated with the emote. Defaults to `None`.

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
    error: Optional[str] = None
    img_data: Optional[bytes] = None
    notes: Optional[str] = None


async def initialize(emote: Emote) -> Emote:
    """
    :param emote: The Emote object to be initialized.
    :return: The initialized Emote object.
    """
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


async def debug(emote: Emote) -> Emote:
    # Create a list to hold the debug information strings.
    notes = []

    # Append various details to the notes list.
    notes.append(f"emote_id: {emote.id}")
    notes.append(f"file_path: {emote.file_path}")
    notes.append(f"author_id: {emote.author_id}")
    notes.append(f"timestamp: {emote.timestamp}")
    notes.append(f"original_url: {emote.original_url}")
    notes.append(f"guild_id: {emote.guild_id}")
    notes.append(f"usage_count: {emote.usage_count}")

    if emote.error is not None:
        notes.append(f"error: {emote.error}")
    else:
        notes.append("error: None")

    # Include image data information explicitly.
    if emote.img_data is not None:
        notes.append(f"img_data_length: {len(emote.img_data)} bytes")
    else:
        notes.append("img_data: None")

    emote.notes = notes
    return emote


async def train(emote: Emote) -> Emote:
    from emote.slash_commands import SlashCommands
    SlashCommands.train_count = 3
    return emote
