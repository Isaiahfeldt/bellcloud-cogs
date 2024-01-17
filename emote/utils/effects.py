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


async def latency(result):
    from emote.slash_commands import SlashCommands
    SlashCommands.latency_enabled = not SlashCommands.latency_enabled
    return result

    # if result is not None:
    #     file_url = f"https://media.bellbot.xyz/emote/{result}"
    #     await message.channel.send(f"{file_url}\n\nTime taken: {elapsed_time}s")
    # else:
    #     await message.channel.send(f"Emote '{emote_name}' not found.\n\nTime taken: {elapsed_time}s")


async def flip(url):
    return url[::-1]  # Reverses the string
