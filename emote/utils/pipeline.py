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
import time

from emote.utils.database import Database
from emote.utils.effects import Emote, initialize

db = Database()


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


async def create_pipeline(self, message, emote: Emote, queued_effects: dict):
    from emote.slash_commands import SlashCommands

    pipeline = [(lambda _: initialize(emote))]
    effects_list = SlashCommands.EFFECTS_LIST
    permission_list = SlashCommands.PERMISSION_LIST
    issues = []

    for effect_name in queued_effects:
        effect = effects_list.get(effect_name)
        if effect is None:
            issues.append((effect_name, "NotFound"))
            continue

        if not permission_list[effect['perm']](message, self):
            issues.append((effect_name, "PermissionDenied"))
            continue

        pipeline.append(effect['func'])

    return pipeline, issues


async def execute_pipeline(pipeline):
    result = None
    emote = None

    for func in pipeline:
        result = await func(result)
        emote = result

    return emote


async def timed_execution(func, input_tuple, start_time):
    result_tuple = await func(input_tuple)
    end_time = time.perf_counter()
    time_elapsed = end_time - start_time

    return result_tuple, time_elapsed
