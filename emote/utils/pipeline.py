import time

from emote.effects.base import Emote
from emote.utils.database import Database

db = Database()

CONFLICT_GROUPS = [
    {"latency", "latency2"}
]


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
    return pipeline


async def execute_pipeline(pipeline):
    return emote


async def timed_execution(func, input_tuple, start_time):
    """Times the execution of a function and returns the result with elapsed time."""
    result_tuple = await func(input_tuple)
    end_time = time.perf_counter()
    time_elapsed = end_time - start_time
    return result_tuple, time_elapsed
