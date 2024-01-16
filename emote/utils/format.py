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

def convert_emote_name(emote_name):
    return emote_name[2:-1] if emote_name.startswith(":~") else emote_name[1:-1]


def extract_emote_effects(content):
    parsed_content = convert_emote_name(content)
    if "_" not in parsed_content:
        return parsed_content, []

    emote_name, emote_effects = parsed_content.split("_", 1)
    emote_effects = emote_effects.split("_")
    return emote_name, emote_effects
