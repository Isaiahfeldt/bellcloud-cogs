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

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from textwrap import wrap
from time import time

import aiohttp
import asyncpg
import boto3
import botocore.exceptions
import discord
import psycopg2
import requests
from discord.app_commands import Choice
from discord.ext import commands
from redbot.core import app_commands
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("Emote", __file__)

# Database connection parameters
host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
database = os.getenv('DB_DATABASE')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')


def list_directory_contents(directory_path):
    if not os.path.isdir(directory_path):
        print(f"Error: '{directory_path}' is not a valid directory.")
        return

    print(f"Contents of directory: {directory_path}")
    print("-------------------------")
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)
        if os.path.isfile(item_path):
            print(f"File: {item}")
        elif os.path.isdir(item_path):
            print(f"Directory: {item}")
        else:
            print(f"Unknown item type: {item}")
    print("-------------------------")


def format_time_ago(timestamp):
    now = datetime.now()
    uploaded_time = datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S")
    time_difference = now - uploaded_time

    if time_difference < timedelta(minutes=1):
        return "Uploaded just now"
    elif time_difference < timedelta(hours=1):
        minutes = int(time_difference.total_seconds() / 60)
        if minutes == 1:
            return "Uploaded 1 minute ago"
        else:
            return f"Uploaded {minutes} minutes ago"
    elif time_difference < timedelta(days=1):
        hours = int(time_difference.total_seconds() / 3600)
        if hours == 1:
            return "Uploaded 1 hour ago"
        else:
            return f"Uploaded {hours} hours ago"
    else:
        return f"Uploaded on {uploaded_time.strftime('%B %d, %Y')}"


session = boto3.session.Session()
s3_client = session.client('s3',
                           region_name='nyc3',
                           endpoint_url='https://bkt-bellcloud.nyc3.digitaloceanspaces.com',
                           aws_access_key_id='DO006L34NDHTUCVVZ9QG',
                           aws_secret_access_key='gDhVuBmXK7cRCW2/n62bk06Bj/TlXKDvnH5Qfg393YM')


@cog_i18n(_)
@app_commands.guild_only()
class SlashCommands(commands.Cog):
    emote = app_commands.Group(name="emote", description="Sorta like emojis, but cooler")

    async def get_connection(self):
        connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }

        return await asyncpg.connect(**connection_params)

    async def execute_query(self, query, *args):
        conn = await self.get_connection()

        try:
            result = await conn.fetch(query, *args)
            return result
        finally:
            await conn.close()

    async def emote_exists_in_database(self, name):
        query = "SELECT * FROM emote.media WHERE emote_name = $1"
        result = await self.execute_query(query, name)

        # Check if result is not empty
        if result:
            return result[0]  # Assuming you expect only one row, so access the first element
        else:
            return []

    async def delete_emote(self, interaction, name):
        query = "DELETE FROM emote.media WHERE emote_name = $1"
        await self.execute_query(query, name)

        embed = discord.Embed(title="Success!", description=f"Removed the emote **{name}**.",
                              colour=0x00ff00)
        embed.set_author(name="Emote Help Menu",
                         icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def get_all_emote_names(self):
        query = "SELECT emote_name FROM emote.media"
        result = await self.execute_query(query)

        # Check if the result is None (empty)
        if result is None:
            return []  # Return an empty list when there are no emotes

        # Extract emote names from the result
        emote_names = [row[0] for row in result]
        return emote_names

    async def add_emote_to_database(self, interaction, name, url, file_type):
        timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d %H:%M:%S')
        with psycopg2.connect(host=host, port=port, database=database, user=user, password=password) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO emote.media (file_path, author_id, timestamp, original_url, emote_name, guild_id, usage_count) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (f"{interaction.guild.id}/{name.lower()}.{file_type}", interaction.user.id, timestamp, url, name,
                     interaction.guild.id, 0))
                conn.commit()

        embed = discord.Embed(title="Success!", description=f"Added **{name}** as an emote.", colour=0x00ff00)
        embed.set_author(name="Emote Help Menu", icon_url=interaction.client.user.display_avatar.url)
        await interaction.delete_original_response()
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def upload_file_to_bucket(self, interaction, url, name, file_type):
        res = requests.get(url, stream=True)
        if res.status_code == 200:
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = os.path.join(temp_dir, f"{name.lower()}.{file_type}")
                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(res.raw, f)

                # Upload file to S3 bucket
                try:
                    if file_type == 'mp4':
                        s3_client.upload_file(file_path, 'emote', f'{interaction.guild.id}/{name.lower()}.{file_type}',
                                              ExtraArgs={'ACL': 'public-read', 'ContentType': f'video/{file_type}'})
                    else:
                        s3_client.upload_file(file_path, 'emote', f'{interaction.guild.id}/{name.lower()}.{file_type}',
                                              ExtraArgs={'ACL': 'public-read', 'ContentType': f'image/{file_type}'})

                except botocore.exceptions.ClientError as e:
                    error_embed = discord.Embed(
                        title="Hmm, something went wrong",
                        description="There was an error while uploading the file to the server. Please try again later.",
                        color=0xd58907
                    )
                    error_embed.set_author(
                        name="Emote Help Menu",
                        icon_url=interaction.client.user.display_avatar.url
                    )
                    error_embed.add_field(name="Error Message", value=str(e))
                    await interaction.delete_original_response()
                    await interaction.followup.send(embed=error_embed, ephemeral=True)

            await self.add_emote_to_database(interaction, name, url, file_type)
        else:
            embed = discord.Embed(
                title="Hmm, something went wrong",
                description="The URL address was invalid or unreachable.",
                colour=0xd58907)
            embed.set_author(
                name="Emote Help Menu",
                icon_url=interaction.client.user.display_avatar.url)
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    @emote.command(name="add", description="Add an emote to the server")
    @app_commands.describe(
        name="The name of the new emote",
        url="The URL of a supported file type to add as an emote"
    )
    async def emote_add(self, interaction: discord.Interaction, name: str, url: str):
        # Can only be used by users with the "Manage Messages" permission
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="You do not have the required permissions to use this command.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        def is_url_reachable(url_string):
            try:
                response = requests.head(url_string)
                return response.status_code == 200
            except requests.ConnectionError:
                return False

        def is_url_allowed_format(url_string, allowed_formats):
            try:
                response = requests.head(url_string)
                if response.status_code != 200:
                    return False, None

                content_type = response.headers.get("content-type")
                if content_type is None:
                    return False, None

                file_extension = content_type.split("/")[-1].lower()
                if file_extension in allowed_formats:
                    return True, file_extension
                else:
                    return False, file_extension

            except requests.ConnectionError:
                return False, None

        format_whitelist = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
        is_allowed, file_type = is_url_allowed_format(url,
                                                      format_whitelist)  # Returns both a bool (is_allowed) and a string (file_type)

        # Send pre-emptive response embed
        embed = discord.Embed(title="Adding emote...",
                              description="Please wait while the emote is being added to the server.",
                              colour=0x00ff00)
        embed.set_author(name="Emote Help Menu",
                         icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Contain any invalid characters?
        if not name.isalnum():
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The emote name contains invalid characters.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Exceed the maximum character limit?
        if len(name) > 32:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The emote name exceeds the maximum character limit.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # URL reachable?
        if not is_url_reachable(url):
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The URL address was invalid or unreachable.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # URL cannot be from "https://media.bellbot.xyz/"
        if "https://media.bellbot.xyz" in url:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The URL address cannot be from `https://media.bellbot.xyz`.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # File size too large?
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                if resp.content_length > 52428800:
                    embed = discord.Embed(title="Hmm, something went wrong",
                                          description="The file size exceeds the maximum limit of 50MB.",
                                          colour=0xd58907)
                    embed.set_author(name="Emote Help Menu",
                                     icon_url=interaction.client.user.display_avatar.url)
                    await interaction.delete_original_response()
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

        # URL pointing to an allowed file format?
        if not is_allowed:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description=f"The URL address points to an unsupported **{file_type}** file format\n\nValid file formats include: **png, webm, jpg, gif, and mp4**",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            embed.add_field(name="Example",
                            value="```/emote add happydog https://example.com/happy_dog_2023.png```")
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Emote name already exist?
        if await self.emote_exists_in_database(name):
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The emote name already exists.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Upload to bucket
        await self.upload_file_to_bucket(interaction, url, name, file_type)

    @emote.command(name="remove", description="Remove an emote from the server")
    @app_commands.describe(name="The name of the emote to remove")
    async def emote_remove(self, interaction: discord.Interaction, name: str):
        # Can only be used by users with the "Manage Messages" permission
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="You do not have the required permissions to use this command.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Emote exists in the database?
        result = await self.emote_exists_in_database(name)
        if not result:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The emote does not exist.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Delete the emote file from DigitalOcean Spaces
        file_path = result[1]  # Assuming the file_path is the first column in the database

        try:
            s3_client.delete_object(Bucket='emote', Key=file_path)
        except Exception as e:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="An error occurred while removing the emote.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            embed.add_field(name="Error Details",
                            value=f'```{str(e)}```')
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Delete the emote entry from the database
        await self.delete_emote(interaction, name)

    @emote_remove.autocomplete("name")
    async def emote_remove_autocomplete_name(self, interaction: discord.Interaction, current: str):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # Retrieve all emote names from the database
        emote_names = await self.get_all_emote_names()
        matches = [name for name in emote_names if current.lower() in name.lower()]

        choices = []
        for match in matches:
            choices.append(Choice(name=match, value=match))
        return choices

    # fake_emote_names = [
    #     "emote1", "emote2", "emote3", "emote4", "emote5", "emote6", "emote7", "emote8", "emote9", "emote10",
    #     "emote11", "emote12", "emote13", "emote14", "emote15", "emote16", "emote17", "emote18", "emote19",
    #     "emote20", "emote991", "emote992", "emote993", "emote994", "emote995", "emote996", "emote997", "emote998",
    #     "emote999", "emote1000", "emote1001", "emote1002", "emote1003", "emote1004", "emote1005", "emote1006",
    #     "emote1007",
    #     "emote1008", "emote1009", "emote1010", "emote1", "emote2", "emote3", "emote4", "emote5", "emote6", "emote7",
    #     "emote8", "emote9", "emote10",
    #     "emote11", "emote12", "emote13", "emote14", "emote15", "emote16", "emote17", "emote18", "emote19",
    #     "emote20", "emote991", "emote992", "emote993", "emote994", "emote995", "emote996", "emote997", "emote998",
    #     "emote999", "emote1000", "emote1001", "emote1002", "emote1003", "emote1004", "emote1005", "emote1006",
    #     "emote1007",
    #     "emote1008", "emote1009", "emote1010", "emote1", "emote2", "emote3", "emote4", "emote5", "emote6", "emote7",
    #     "emote8", "emote9", "emote10",
    #     "emote11", "emote12", "emote13", "emote14", "emote15", "emote16", "emote17", "emote18", "emote19",
    #     "emote20", "emote991", "emote992", "emote993", "emote994", "emote995", "emote996", "emote997", "emote998",
    #     "emote999", "emote1000", "emote1001", "emote1002", "emote1003", "emote1004", "emote1005", "emote1006",
    #     "emote1007",
    #     "emote1008", "emote1009", "emote1010", "emote1", "emote2", "emote3", "emote4", "emote5", "emote6", "emote7",
    #     "emote8", "emote9", "emote10",
    #     "emote11", "emote12", "emote13", "emote14", "emote15", "emote16", "emote17", "emote18", "emote19",
    #     "emote20", "emote991", "emote992", "emote993", "emote994", "emote995", "emote996", "emote997", "emote998",
    #     "emote999", "emote1000", "emote1001", "emote1002", "emote1003", "emote1004", "emote1005", "emote1006",
    #     "emote1007",
    #     "emote1008", "emote1009", "emote1010",
    # ]

    @emote.command(name="list", description="List all emotes in the server")
    async def emote_list(self, interaction: discord.Interaction):
        # Can only be used by users with the "Manage Messages" permission
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="You do not have the required permissions to use this command.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        emote_names = await self.get_all_emote_names()

        # Create a list to hold the embeds
        embeds = []

        # Maximum characters allowed in a single field (1000 - len("Emotes:"))
        max_characters = 1000 - len("Emotes: ")

        # Create an embed to display the emote list
        embed = discord.Embed(color=0x00ff00)

        field_count = 0
        if emote_names:
            emote_list_str = ", ".join(emote_names)
            emote_list_chunks = emote_list_str.split(", ")

            # Split emote names into chunks that fit within the character limit
            chunks = wrap(emote_list_str, width=max_characters, break_long_words=False, break_on_hyphens=False)

            # Add each chunk as a separate field in the embed
            for i, chunk in enumerate(chunks):
                embed.add_field(name="Emotes:" if i == 0 else "\u200b", value=chunk, inline=False)
                field_count += 1

            # Use the guild icon as the author's icon
            embed.set_author(name=f"{interaction.guild.name}", icon_url=interaction.guild.icon.url)

            # Append the embed to the list
            embeds.append(embed)

        # Add the "Visit emote gallery" URL button to the last embed
        url_button = discord.ui.Button(style=discord.ButtonStyle.link, label="Visit emote gallery",
                                       url="https://bellbot.xyz/")

        # Create a view to add the button to
        view = discord.ui.View()
        view.add_item(url_button)

        # Send all embeds with ephemeral set accordingly
        # Ephemeral is set to True if field_count is higher than 3
        for i, embed in enumerate(embeds):
            ephemeral = False if field_count <= 3 else True
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral, view=view)

    @emote.command(name="info", description="Retrieves information about an emote")
    @app_commands.describe(name="The name of the emote to remove")
    async def emote_info(self, interaction: discord.Interaction, name: str):
        try:
            with psycopg2.connect(host=host, port=port, database=database, user=user, password=password) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM emote.media WHERE emote_name = %s", (name,))
                    result = cur.fetchone()

            if result is not None:
                emote_id, file_path, author_id, timestamp, original_url, emote_name, guild_id, usage_count = result

                # Retrieve guild information
                guild = self.bot.get_guild(guild_id)
                guild_name = guild.name if guild else "Unknown"

                # Mention the author if they are in the server
                author = guild.get_member(author_id) if guild else None
                author_mention = author.mention if author else f"<@{author_id}>"

                embed = discord.Embed(color=0x00ff00)
                embed.set_author(name=emote_name, url=f"https://media.bellbot.xyz/emote/{file_path}",
                                 icon_url=f"https://media.bellbot.xyz/emote/{file_path}")
                embed.add_field(name="Uploader", value=author_mention, inline=True)
                embed.add_field(name="Guild", value=guild_name, inline=True)
                embed.add_field(name="Times Used", value=usage_count, inline=True)
                embed.add_field(name="Original URL", value=original_url, inline=False)

                embed.set_image(url=f"https://media.bellbot.xyz/emote/{file_path}")
                embed.set_footer(text=f"Emote ID: {emote_id} | {format_time_ago(timestamp)} by {author.display_name}",
                                 icon_url=author.display_avatar.url)

                await interaction.response.send_message(embed=embed, ephemeral=False)
            else:
                embed = discord.Embed(title="Hmm, something went wrong",
                                      description="The emote does not exist.",
                                      colour=0xd58907)
                embed.set_author(name="Emote Help Menu",
                                 icon_url=interaction.client.user.display_avatar.url)
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="An error occurred while removing the emote.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            # embed.add_field(name="Error Details",
            #                 value=f'```{str(e)}```')
            embed.add_field(name="Error Details",
                            value=f'```{exc_type}, \n {exc_obj}, \n{fname}, \n{exc_tb.tb_lineno}```')
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            cur.close()
            conn.close()

    @emote_info.autocomplete("name")
    async def emote_info_autocomplete_name(self, interaction: discord.Interaction, current: str):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        choices = []

        # Retrieve all emote names from the database
        emote_names = await self.get_all_emote_names()
        matches = [name for name in emote_names if current.lower() in name.lower()]

        for match in matches:
            choices.append(Choice(name=match, value=match))
        return choices

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return  # Ignore messages sent by the bot itself

        if not message.content.startswith(":") or not message.content.endswith(":"):
            return  # Ignore messages that don't follow the emote format

        emote_name = message.content[1:-1]  # Extract the emote name from the message content

        with psycopg2.connect(host=host, port=port, database=database, user=user, password=password) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE emote.media SET usage_count = usage_count + 1 WHERE emote_name = %s", (emote_name,))
                conn.commit()
                cur.execute("SELECT file_path FROM emote.media WHERE emote_name = %s", (emote_name,))
                result = cur.fetchone()

        if result is not None:
            file_path = result[0]  # Extract the file_path from the database result
            file_url = f"https://media.bellbot.xyz/emote/{file_path}"  # Construct the final URL
            # embed = discord.Embed()
            # embed.set_image(url=file_url)
            await message.channel.send(f"{file_url}")
        else:
            await message.channel.send(f"Emote '{emote_name}' not found.")
