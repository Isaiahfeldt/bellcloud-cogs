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
import asyncio
import time

from emote.utils.database import Database
from emote.utils.effects import Emote, initialize

db = Database()

# Define groups of effects that cannot be used together
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
    """
        Constructs a pipeline for processing effects on a given emote. Validates the
        queued effects and checks if the user has the appropriate permissions to
        execute them. Returns the constructed pipeline and a list of any issues
        encountered.

        Parameters:
        message (Any): The message object associated with the request; its type depends
            on the application's context.
        emote (Emote): An instance of the Emote class representing the emote to be
            processed.
        queued_effects (dict): A dictionary of effect names to be queued, where keys
            are strings representing effect names and values are their parameters.

        Returns:
        tuple: A tuple containing:
            - pipeline (list): A constructed list of callable functions to process
              the emote and apply effects in sequence.
            - issues (list): A list of encountered issues, where each issue is a
              tuple containing:
              - effect_name (str): The name of the effect that caused the issue.
              - error_code (str): A string code describing the issue (e.g.,
                "NotFound" or "PermissionDenied").
    """
    from emote.slash_commands import SlashCommands

    pipeline = [(lambda _: initialize(emote))]
    effects_list = SlashCommands.EFFECTS_LIST
    permission_list = SlashCommands.PERMISSION_LIST

    seen_effects = set()

    for effect_name, effect_args in queued_effects:
        effect_info = effects_list.get(effect_name)
        if effect_info is None:
            emote.issues[f"{effect_name}_effect"] = "NotFound"
            continue

        # Check for single-use violations
        if effect_info.get("single_use", False):
            if effect_name in seen_effects:
                emote.issues[f"{effect_name}_effect"] = "DuplicateNotAllowed"
                continue
            seen_effects.add(effect_name)

        # Check permissions
        if not permission_list[effect_info['perm']](message, self):
            emote.issues[f"{effect_name}_effect"] = "PermissionDenied"
            continue

        # Check for conflicting effects
        applied_conflicts = []
        for group in CONFLICT_GROUPS:
            if effect_name in group:
                for other_effect in group:
                    if other_effect != effect_name and other_effect in emote.effect_chain:
                        applied_conflicts.append(other_effect)

        if applied_conflicts:
            emote.errors[effect_name] = (
                f"Cannot apply {effect_name} because conflicting effect(s) "
                f"already applied: {', '.join(applied_conflicts)}"
            )
            continue

        # Mark effect as used in the effect chain
        emote.effect_chain[effect_name] = True

        # Create the effect wrapper
        async def effect_wrapper(emote, _effect_name=effect_name, func=effect_info['func'], args=effect_args):
            # try:
            return await func(emote, *args)
            # except TypeError as e:
            #     if "positional arguments" in str(e):
            #         emote.errors[f"{_effect_name}_effect"] = "TooManyArguments"
            #     else:
            #         emote.errors[f"{_effect_name}_effect"] = f"InvalidArguments: {str(e)}"
            #     return emote
            # except Exception as e:
            #     emote.errors[f"{_effect_name}_effect"] = str(e)
            #     #
            #     # max_characters = 500
            #     # traceback_str = str(traceback.format_exc())
            #     # chunks = wrap(traceback_str, width=max_characters, break_long_words=False, break_on_hyphens=False)
            #     #
            #     # for i, chunk in enumerate(chunks):
            #     #     emote.followup[f"{_effect_name}"] = (f"```{chunk}```")

            return emote

        pipeline.append(effect_wrapper)

    return pipeline


async def execute_pipeline(pipeline):
    """
    Executes a sequence of asynchronous functions in a pipeline, passing the result of
    each step to the next.

    :param pipeline: List of asynchronous functions to execute in order.
    :emote: The final result after executing all functions in the pipeline.
    """
    emote = None
    for operation in pipeline:
        try:
            # Add timeout (e.g., 30 seconds per effect)
            emote = await asyncio.wait_for(operation(emote), timeout=60)
        except asyncio.TimeoutError:
            emote.errors["timeout"] = "Operation timed out."
            break
    return emote


async def timed_execution(func, input_tuple, start_time):
    """Times the execution of a function and returns the result with elapsed time."""
    result_tuple = await func(input_tuple)
    end_time = time.perf_counter()
    time_elapsed = end_time - start_time
    return result_tuple, time_elapsed
