#  Copyright (c) 2023, Isaiah Feldt
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

from enum import Enum


class EmbedColor(Enum):
    GREEN = 0x00ff00
    ORANGE = 0xd58907
    RED = 0xff0000


class EmoteAddError(Enum):
    INVALID_PERMISSION = "You do not have the required permissions to use this command."
    INVALID_NAME_CHAR = "The emote name contains invalid characters."
    EXCEED_NAME_LEN = "The emote name exceeds the maximum character limit."
    UNREACHABLE_URL = "The URL address was invalid or unreachable."
    INVALID_URL = "The URL address cannot be from `https://media.bellbot.xyz`."
    EXCEED_FILE_SIZE = "The file size exceeds the maximum limit of 50MB."
    INVALID_FILE_FORMAT = "The URL address points to an unsupported file format. Valid file formats include: png, webm, jpg, gif, and mp4."
    DUPLICATE_EMOTE_NAME = "The emote name already exists."
