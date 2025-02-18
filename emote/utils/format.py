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
import re

import discord


def is_enclosed_in_colon(message: discord.Message) -> bool:
    return message.content.startswith(":") and message.content.endswith(":")


def clean_emote_name(emote_name: str):
    """
    :param emote_name: The name of the emote to be cleaned.
    :return: The cleaned emote name where the prefix and postfix character sequence is removed, if it exists.
    """
    return emote_name[2:-1] if emote_name.startswith(":~") else emote_name[1:-1]


def extract_emote_details(message: discord.Message):
    parsed_content = clean_emote_name(message.content.lower())
    if "_" not in parsed_content:
        return parsed_content, []

    emote_name, effects_part = parsed_content.split("_", 1)

    # New regex pattern to capture effect names and arguments
    effect_pattern = r"([a-zA-Z]+)(?:\(([^)]*)\))?"
    emote_effects = []

    for match in re.finditer(effect_pattern, effects_part):
        effect_name, effect_args = match.groups()
        parsed_args = []

        if effect_args:
            # Split arguments and auto-detect types
            for arg in effect_args.split(','):
                arg = arg.strip()
                if arg.isdigit():
                    parsed_args.append(int(arg))
                elif arg.lower() in ['true', 'false']:
                    parsed_args.append(arg.lower() == 'true')
                else:
                    parsed_args.append(arg.strip('"\' '))

        emote_effects.append((effect_name, parsed_args))

    return emote_name, emote_effects
