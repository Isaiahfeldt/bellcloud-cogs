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

db = Database()


async def create_pipeline(self, message, emote_name: str, queued_effects: dict, ):
    """
    :param self: The object instance.
    :param message: The message object.
    :param emote_name: The name of the emote.
    :param queued_effects: A dictionary containing queued effects.
    :return: A list representing the pipeline.

    This method creates a pipeline by appending lambda functions and effect commands to it based on the queued
    effects and permissions. The pipeline is then returned.
    """

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

        if not permission_list[effect['perm']](message, self):
            issues.append((effect_name, "PermissionDenied"))
            continue

        pipeline.append(effect['func'])

    return pipeline, issues


# TODO:
# change result to a dict where each function appends its own elapsed time


async def execute_pipeline(pipeline, start_time):
    result_message, result = "", None
    function_end_time = start_time
    for function in pipeline:
        result = await function(result)
        function_end_time = time.perf_counter()
        if isinstance(result, str):
            result_message = result

    elapsed_time = function_end_time - start_time
    return result_message, elapsed_time
