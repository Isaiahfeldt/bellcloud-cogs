#  Copyright (c) 2023, Isaiah Feldt
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

from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)


# noinspection SpellCheckingInspection
@cog_i18n(_)
class HybridCommands(commands.Cog):
    pass

    # emote = app_commands.Group(name="emote", description="Sorta like emojis, but cooler")
    #
    # @commands.hybrid_group(name="emote", aliases=["e"])
    # @commands.guild_only()
    # async def emote(self, ctx: commands.Context):
    #     """Sorta like emojis, but cooler"""
    #     pass
    #
    # @emote.command(
    #     name="add",
    #     description="Add an emote to the server",
    #     aliases=["a"],
    # )
    # @app_commands.describe(
    #     name="The name the emote should be saved as",
    #     url="The URL of a supported image format to add as an emote",
    # )
    # async def command_add_emote(self, ctx: commands.Context, name: str, url: str):
    #     """Downloads and adds media as an emote with the given name.
    #
    #     Valid file formats include:
    #     - .png
    #     - .webm
    #     - .jpg
    #     - .gif
    #     - .mp4
    #
    #     To add an emote named 'happydog', use the following command:
    #     !emote add happydog https://example.com/happy_dog_2023.png
    #     """
    #
    # def is_url_reachable(url_string):
    #     try:
    #         response = requests.head(url_string)
    #         return response.status_code == 200
    #     except requests.ConnectionError:
    #         return False
    # def is_url_allowed_format(url_string, allowed_formats):
    #     try:
    #         response = requests.head(url_string)
    #         if response.status_code != 200:
    #             return False, None
    #
    #         content_type = response.headers.get("content-type")
    #         if content_type is None:
    #             return False, None
    #
    #         file_extension = content_type.split("/")[-1]
    #         if file_extension in allowed_formats:
    #             return True, file_extension
    #         else:
    #             return False, file_extension
    #
    #     except requests.ConnectionError:
    #         return False, None
    #
    #
    #
    # format_whitelist = ["png", "webm", "jpg", "jpeg", "gif", "mp4"] is_allowed, file_type = is_url_allowed_format(
    # url, format_whitelist) # Returns both a bool (is_allowed) and a string (file_type)
    #
    #     if not is_url_reachable(url):
    #         await ctx.send("The URL is invalid or unreachable.", ephemeral=True)
    #         return
    #
    #     if is_allowed:
    #         await ctx.send(f"The URL points to an allowed **{file_type}** file format.")
    #     else:
    #         await ctx.send(f"The URL points to an unsupported **{file_type}** file format.", ephemeral=True)
    #
