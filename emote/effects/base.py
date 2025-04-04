# Contains the core Emote dataclass and initialize function
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

import aiohttp


@dataclass
class Emote:
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
        record the error in the emote.errors dictionary under the key 'initialize'.

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

    return emote
