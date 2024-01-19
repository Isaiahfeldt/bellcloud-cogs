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
from dataclasses import dataclass
from datetime import datetime

from emote.utils.database import Database

db = Database()


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
        emote_name (str): The name of the emote.
        guild_id (int): The unique identifier of the guild the emote belongs to.
        usage_count (int): The number of times the emote has been used.
    """
    id: int
    file_path: str
    author_id: int
    timestamp: datetime
    original_url: str
    emote_name: str
    guild_id: int
    usage_count: int


# class EffectManager:
#     EFFECTS = {
#         'flip': {'func': flip, 'perm': 'everyone', 'priority': 10},
#         'latency': {'func': latency, 'perm': 'mod', 'priority': 1},
#     }
#
#     PERMISSION_LIST = {
#         'owner': lambda message, self: self.bot.is_owner(message.author),
#         'mod': lambda message, _: message.author.guild_permissions.manage_messages,
#         'everyone': lambda _, __: True,
#     }
#
#     def get_by_name(self, name, message):
#         effect_info = self.EFFECTS.get(name)
#         if effect_info is None:
#             # Add an error message instead of raising an exception
#             return None, f"Effect `{name}` not found."
#
#         # Check if the user has permission to use the effect
#         perm_func = self.PERMISSION_LIST.get(effect_info['perm'])
#         if perm_func and not perm_func(message, self):
#             return None, f"You do not have permission to use the effect `{name}`."
#
#         return effect_info['func'](), None


async def create_pipeline(self, message, emote_name: str, queued_effects: dict, ):
    from emote.slash_commands import SlashCommands

    pipeline = [(lambda _: db.get_emote(emote_name))]
    effects_list = SlashCommands.EFFECTS_LIST
    permission_list = SlashCommands.PERMISSION_LIST
    issues = []

    for effect_name in queued_effects:
        effect = effects_list.get(effect_name)
        if effect is None:
            issues.append((effect_name, "NotFound"))
            continue

        if effect_name == "latency":
            SlashCommands.latency_enabled = not SlashCommands.latency_enabled

        if not permission_list[effect['perm']](message, self):
            issues.append((effect_name, "PermissionDenied"))
            continue

        pipeline.append(effect['func'])

    return pipeline, issues


async def execute_pipeline(pipeline):
    result_messages, result = [], None

    for function in pipeline:
        result = await function(result)
        if isinstance(result, str):
            result_messages.append(result)

    return result_messages
