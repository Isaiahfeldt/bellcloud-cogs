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

def clean_emote_name(emote_name: str):
    """
    :param emote_name: The name of the emote to be cleaned.
    :return: The cleaned emote name where the prefix and postfix character sequence is removed, if it exists.

    """
    return emote_name[2:-1] if emote_name.startswith(":~") else emote_name[1:-1]


def extract_emote_details(message: str):
    """
    :param message: The content string containing the emote name and effects separated by an underscore.
    :return: A tuple containing the extracted emote name and a list of emote effects.

    """
    parsed_content = clean_emote_name(message)
    if "_" not in parsed_content:
        return parsed_content, []

    emote_name, emote_effects = parsed_content.split("_", 1)
    emote_effects = emote_effects.split("_")
    return emote_name, emote_effects
