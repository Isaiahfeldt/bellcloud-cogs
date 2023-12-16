import discord
import requests
import psycopg2
# import asyncpg
import re
# import traceback
import aiohttp
# import sys
import os
import shutil
import tempfile
import boto3
import botocore.exceptions
from time import time
from datetime import datetime, timedelta
from redbot.core.i18n import Translator, cog_i18n
from redbot.core import checks, Config, commands, app_commands

# Table fields
# id, file_path, author_id, timestamp, original_url, emote_name, guild_id

_ = Translator("Emote", __file__)

# Database connection parameters
host = 'db-bellcloud-do-user-13984511-0.b.db.ondigitalocean.com'
port = '25060'
database = "bellbotdb"
user = "doadmin"
password = "AVNS_JMR4kirisYj8RREHrLf"

session = boto3.session.Session()
s3_client = session.client('s3',
                           region_name='nyc3',
                           endpoint_url='https://bkt-bellcloud.nyc3.digitaloceanspaces.com',
                           aws_access_key_id='DO006L34NDHTUCVVZ9QG',
                           aws_secret_access_key='gDhVuBmXK7cRCW2/n62bk06Bj/TlXKDvnH5Qfg393YM')

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

        file_extension = content_type.split("/")[-1]
        if file_extension in allowed_formats:
            return True, file_extension
        else:
            return False, file_extension

    except requests.ConnectionError:
        return False, None


class AddEmoteModal(discord.ui.Modal, title='Name emote'):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emote_name = None  # Initialize emote_name attribute

    emote_modal = discord.ui.TextInput(
        style = discord.TextStyle.short,
        label= 'What do you want to name your emote?',
        required = True,
        placeholder = "A cool emote name",
        min_length=3,
        max_length=32
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.on_submit_interaction = interaction  # Save the interaction object
        self.stop()  # Stop the modal
        self.emote_name = self.emote_modal.value  # Update the emote_name attribute

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)

@cog_i18n(_)
@app_commands.guild_only()
class ContextMenus(DISCORD_COG_TYPE_MIXIN):

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
            return False

    async def add_emote_to_database_context(self, interaction, name, url, file_type):
        timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d %H:%M:%S')
        with psycopg2.connect(host=host, port=port, database=database, user=user, password=password) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO emote.media (file_path, author_id, timestamp, original_url, emote_name, guild_id, usage_count) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (f"{interaction.guild.id}/{name.lower()}.{file_type}", interaction.user.id, timestamp, url, name,
                     interaction.guild.id, 0))
                conn.commit()

    async def upload_file_to_bucket_context(self, interaction, url, name, file_type):
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
                        description="There was an error while uploading the file to the server.",
                        color=0xd58907
                    )
                    error_embed.set_author(
                        name="Emote Help Menu",
                        icon_url=interaction.client.user.display_avatar.url
                    )
                    error_embed.add_field(name="Error Message", value=str(e))
                    await interaction.followup.send(embed=error_embed, ephemeral=True)

            await self.add_emote_to_database_context(interaction, name, url, file_type)
        else:
            embed = discord.Embed(
                title="Hmm, something went wrong",
                description="The URL address was invalid or unreachable.",
                colour=0xd58907)
            embed.set_author(
                name="Emote Help Menu",
                icon_url=interaction.client.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    async def add_as_emote(self, interaction: DISCORD_INTERACTION_TYPE, message: discord.Message) -> None:
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="Hmm, something went wrong",
                description="You do not have the required permissions to use this command.",
                colour=0xd58907
            )
            embed.set_author(
                name="Emote Help Menu",
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Are any msg attachments?
        if not message.attachments and not re.findall(r'(https?://\S+)', message.content):
            embed = discord.Embed(
                title="Hmm, something went wrong",
                description="This msg does not have any attachments:\n"
                            f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}",
                colour=0xd58907
            )
            embed.set_author(
                name="Emote Help Menu",
                icon_url=interaction.client.user.display_avatar.url
            )
            embed.set_footer(
                # Link msg using guild_id / channel_id / message_id
                text=f"Test",
                icon_url=message.author.display_avatar.url
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Is there only one attachment?
        if len(message.attachments) > 1:
            embed = discord.Embed(
                title="Hmm, something went wrong",
                description="You can only add one attachment at a time.",
                colour=0xd58907
            )
            embed.set_author(
                name="Emote Help Menu",
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = AddEmoteModal()
        await interaction.response.send_modal(modal)
        timeout = await modal.wait()
        if timeout:
            return

        embed = discord.Embed(title="Adding emote...",
                              description="Please wait while the emote is being added to the server.",
                              colour=0x00ff00)
        embed.set_author(name="Emote Help Menu",
                         icon_url=interaction.client.user.display_avatar.url)
        await modal.on_submit_interaction.response.send_message(embed=embed, ephemeral=True)

        # Get the url of the attachment
        valid_urls = []
        valid_urls += re.findall(r'(https?://\S+)', message.content) # Search for any URLs in the message content and add them to the list
        for attachment in message.attachments:
            valid_urls.append(attachment.url)

        # Check if the URLs are valid
        valid_matches = []
        for url_string in valid_urls:
            if is_url_reachable(url_string):
                valid_matches.append(url_string)

        url = valid_matches[0] # Get the first valid URL
        name = modal.emote_name

        format_whitelist = ["png", "webm", "jpg", "jpeg", "gif", "mp4"]
        is_allowed, file_type = is_url_allowed_format(url, format_whitelist)  # Returns both a bool (is_allowed) and a string (file_type)

        # Contain any invalid characters?
        if not name.isalnum():
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description=f"The emote name contains invalid characters.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await modal.on_submit_interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # URL reachable?
        if not is_url_reachable(url):
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The URL address was invalid or unreachable.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await modal.on_submit_interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # URL cannot be from "https://media.bellbot.xyz/"
        if "https://media.bellbot.xyz" in url:
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The URL address cannot be from `https://media.bellbot.xyz`.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await modal.on_submit_interaction.delete_original_response()
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
                    await modal.on_submit_interaction.delete_original_response()
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
            await modal.on_submit_interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Emote name already exist?
        if await self.emote_exists_in_database(name):
            embed = discord.Embed(title="Hmm, something went wrong",
                                  description="The emote name already exists.",
                                  colour=0xd58907)
            embed.set_author(name="Emote Help Menu",
                             icon_url=interaction.client.user.display_avatar.url)
            await modal.on_submit_interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Upload to bucket
        await self.upload_file_to_bucket_context(interaction, url, name, file_type)

        embed = discord.Embed(title="Success!", description=f"Added **{name}** as an emote.", colour=0x00ff00)
        embed.set_author(name="Emote Help Menu", icon_url=interaction.client.user.display_avatar.url)
        await modal.on_submit_interaction.delete_original_response()
        await interaction.followup.send(embed=embed, ephemeral=True)
