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


async def create_pipeline(message, self, emote_name: str, effects_list: list, cmd_and_perm: dict, permissions: dict):
    pipeline = [(lambda _: db.get_emote(emote_name))]

    for command_name in effects_list:
        if command_name in cmd_and_perm:
            command = cmd_and_perm[command_name]
            if permissions[command['perm']]:
                message.channel.send(permissions)
                message.channel.send(permissions[command['perm']])
                pipeline.append(command['func'])
    return pipeline


# TODO:
# change result to a dict where each function appends its own elapsed time


async def execute_pipeline(pipeline, start_time):
    result_messages, result = [], None
    start_time = time.perf_counter()
    for function in pipeline:
        function_start_time = time.perf_counter()
        result = await function(result)
        function_end_time = time.perf_counter()
        if isinstance(result, str):
            elapsed_time = function_end_time - function_start_time
            result_messages.append(f"{elapsed_time:.6f} seconds: {result}")
    return result_messages
