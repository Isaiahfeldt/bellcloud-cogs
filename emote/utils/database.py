#  Copyright (c) 2023-2024, Isaiah Feldt
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
import tempfile
from collections import defaultdict
from datetime import datetime
from time import time

import asyncpg
import boto3
import botocore
import discord
import requests
from cachetools import TTLCache

from emote.utils.effects import Emote


class Database:
    def __init__(self):
        self.CONNECTION_PARAMS: dict[str, str | None] = {
            "host": os.getenv('DB_HOST'),
            "port": os.getenv('DB_PORT'),
            "database": os.getenv('DB_DATABASE'),
            "user": os.getenv('DB_USER'),
            "password": os.getenv('DB_PASSWORD')
        }
        self.BUCKET_PARAMS: dict[str, str | None] = {
            "access_key_id": os.getenv('BK_ACCESS_KEY'),
            "secret_access_key": os.getenv('BK_SECRET_KEY')
        }
        self.cache = TTLCache(
            maxsize=100,
            ttl=1200
        )  # maxsize is the maximum number of items in the cache, and ttl is the "time to live" for each item
        self.emote_usage_collection = defaultdict(int)

    async def get_connection(self):
        """
        Get a connection to the database.

        :return: A connection object to execute queries asynchronously.
        """
        return await asyncpg.connect(**self.CONNECTION_PARAMS)

    async def execute_query(self, query, *args):
        """
        :param query: The SQL query to be executed.
        :param args: The arguments to be passed to the query.
        :return: The result of the query.

        Note: This method is an asynchronous method and should be awaited when called.

        Example usage:
        result = await execute_query("SELECT * FROM users")
        """
        conn = await self.get_connection()
        try:
            result = await conn.execute(query, *args)
            self.cache.clear()  # Invalidate all cache entries because database state changed
            return result
        finally:
            if conn:
                await conn.close()

    async def fetch_query(self, query, *args):
        """
        :param query: The SQL query to be fetched.
        :param args: The arguments to be passed to the query.
        :return: The result of the query.

        Note: This method is an asynchronous method and should be awaited when called.

        Example usage:
        result = await fetch_query("SELECT * FROM users")
        """

        if args in self.cache:  # Check if *args is in the cache
            from emote.slash_commands import SlashCommands
            SlashCommands.was_cached = True
            return self.cache[args]  # return the result associated with *args in the cache

        conn = await self.get_connection()

        if args not in self.cache or self.cache.ttl == 0:
            await self.dump_emote_usage_to_database(conn)

        try:
            result = await conn.fetch(query, *args)
            self.cache[args] = result
            return result
        finally:
            if conn:
                await conn.close()

    async def dump_emote_usage_to_database(self, conn):
        try:
            for key, count in self.emote_usage_collection.items():
                # If keys are tuples, they are of the form (emote_name, guild_id)
                if isinstance(key, tuple):
                    query = "UPDATE emote.media SET usage_count = usage_count + $1 WHERE emote_name = $2 AND guild_id = $3"
                    await conn.execute(query, count, key[0], key[1])
                else:
                    query = "UPDATE emote.media SET usage_count = usage_count + $1 WHERE emote_name = $2"
                    await conn.execute(query, count, key)
            self.emote_usage_collection.clear()  # Clear the staging area
        finally:
            pass

    async def update_file_to_bucket(self, interaction: discord.Interaction, name: str, url: str, file_type: str):
        session = boto3.session.Session()
        s3_client = session.client('s3',
                                   region_name='nyc3',
                                   endpoint_url='https://bkt-bellcloud.nyc3.digitaloceanspaces.com',
                                   aws_access_key_id=self.BUCKET_PARAMS['access_key_id'],
                                   aws_secret_access_key=self.BUCKET_PARAMS['secret_access_key']
                                   )

        res = requests.get(url, stream=True)
        if res.status_code == 200:
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = os.path.join(temp_dir, f"{name.lower()}.{file_type}")
                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(res.raw, f)

        try:
            if file_type == 'mp4':
                s3_client.upload_file(file_path, 'emote', f'{interaction.guild.id}/{name.lower()}.{file_type}',
                                      ExtraArgs={'ACL': 'public-read', 'ContentType': f'video/{file_type}'})
                return True, None
            else:
                s3_client.upload_file(file_path, 'emote', f'{interaction.guild.id}/{name.lower()}.{file_type}',
                                      ExtraArgs={'ACL': 'public-read', 'ContentType': f'image/{file_type}'})
                return True, None

        except botocore.exceptions.ClientError as e:
            return False, e

    async def add_emote_to_database(self, interaction: discord.Interaction, name: str, url: str, file_type: str):
        timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d %H:%M:%S')

        query = (
            "INSERT INTO emote.media "
            "(file_path, author_id, timestamp, original_url, emote_name, guild_id, usage_count) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)"
        )
        values = (
            f"{interaction.guild.id}/{name.lower()}.{file_type}",
            interaction.user.id,
            timestamp,
            url,
            name,
            interaction.guild.id,
            0
        )

        result = await self.execute_query(query, *values)

        if result is not None:
            await self.update_file_to_bucket(interaction, name, url, file_type)

    async def process_query_results(self, results):
        if not results:
            return False
        return results[0]['exists']

    async def check_emote_exists(self, emote_name, guild_id):
        """
        :param emote_name: The name of the emote to check existence for in the database.
        :return: True if the emote exists in the database, False otherwise.
        """
        key = (emote_name, guild_id)
        if key in self.cache:
            return self.cache[key]

        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1 AND guild_id = $2)"
        result = await self.fetch_query(query, emote_name, guild_id)
        exists = await self.process_query_results(result)

        self.cache[key] = exists
        return exists

    async def get_emote_names(self, guild_id):
        """
        Retrieve the names of emotes from the media table.

        :return: A list of emote names.
        """
        query = "SELECT emote_name FROM emote.media WHERE guild_id = $1"
        result = await self.fetch_query(query, guild_id)
        return self.format_names_from_results(result)

    async def format_names_from_results(self, results):
        """
        :param results: the results from a database query

        :return: a list of names extracted from the results
        """
        if results is None:
            return []
        return [row[0] for row in results]

    async def get_emote(self, emote_name, guild_id, inc_count: bool = False) -> Emote | None:
        """
        Get emote from database.

        :param emote_name: The name of the emote.
        :param inc_count: Whether to increment the usage count of the emote. Defaults to False.

        :return: The emote record as an asyncpg.Record object.
        """

        # Change `emote_name` to `name`
        def fix_emote_dict(emote_dict: dict) -> dict:
            fixed_dict = dict(emote_dict[0])
            fixed_dict['name'] = fixed_dict.pop('emote_name')
            return fixed_dict

        query = "SELECT * FROM emote.media WHERE emote_name = $1 AND guild_id = $2"
        emote_rows = await self.fetch_query(query, emote_name, guild_id)
        if not emote_rows:
            return None

        if inc_count:
            update_query = "UPDATE emote.media SET usage_count = usage_count + 1 WHERE emote_name = $1 AND guild_id = $2"
            await self.execute_query(update_query, emote_name, guild_id)

        return Emote(**fix_emote_dict(emote_rows))
