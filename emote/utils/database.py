# File: emote/utils/database.py
import os
import tempfile
from datetime import datetime, timezone

import aiohttp
import asyncpg
import boto3
import botocore
import discord
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
        # In‑memory cache for query results
        self.cache = TTLCache(
            maxsize=100,
            ttl=1200
        )
        # Connection pool (will be initialized via async call)
        self.pool: asyncpg.Pool | None = None

    async def init_pool(self):
        """
            Initialize the asyncpg connection pool.
        """
        self.pool = await asyncpg.create_pool(**self.CONNECTION_PARAMS, min_size=1, max_size=10)

    async def close_pool(self):
        """
            Close the asyncpg connection pool.
        """
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def execute_query(self, query, *args):
        """
            Use the connection pool to execute a query.
        """
        if self.pool is None:
            raise Exception("Pool not initialized. Call init_pool() first.")
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *args)
            self.cache.clear()  # Invalidate cache on DB write
            return result

    async def fetch_query(self, query, *args):
        """
            Use the pool to fetch query results.
        """
        if self.pool is None:
            raise Exception("Pool not initialized. Call init_pool() first.")
        # Check cache first
        if args in self.cache:
            return self.cache[args]
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, *args)
            self.cache[args] = result
            return result

    async def update_file_to_bucket(self, interaction: discord.Interaction, name: str, url: str, file_type: str):
        session = boto3.session.Session()
        s3_client = session.client(
            's3',
            region_name='nyc3',
            endpoint_url='https://bkt-bellcloud.nyc3.digitaloceanspaces.com',
            aws_access_key_id=self.BUCKET_PARAMS['access_key_id'],
            aws_secret_access_key=self.BUCKET_PARAMS['secret_access_key']
        )

        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, f"{name}.{file_type}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await response.read())
                else:
                    raise FileNotFoundError(f"Failed to download {url}")

        try:
            if file_type == 'mp4':
                s3_client.upload_file(
                    file_path,
                    'emote',
                    f"{interaction.guild.id}/{name.lower()}.{file_type}",
                    ExtraArgs={'ACL': 'public-read', 'ContentType': f"video/{file_type}"}
                )
                return True, None
            else:
                s3_client.upload_file(
                    file_path,
                    'emote',
                    f"{interaction.guild.id}/{name.lower()}.{file_type}",
                    ExtraArgs={'ACL': 'public-read', 'ContentType': f"image/{file_type}"}
                )
                return True, None

        except botocore.exceptions.ClientError as e:
            return False, e

    async def add_emote_to_database(self, interaction: discord.Interaction, name: str, url: str, file_type: str):
        timestamp = datetime.now(timezone.utc)
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
            success, error = await self.update_file_to_bucket(interaction, name, url, file_type)
            if success:
                return True, None
            else:
                return False, error

    async def process_query_results(self, results):
        if not results:
            return False
        return results[0]['exists']

    async def check_emote_exists(self, emote_name, guild_id):
        """
            Check for the existence of an emote in the database.
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
            Retrieve emote names from the database.
        """
        query = "SELECT emote_name FROM emote.media WHERE guild_id = $1"
        result = await self.fetch_query(query, guild_id)
        return await self.format_names_from_results(result)

    async def format_names_from_results(self, results):
        if results is None:
            return []
        return [row[0] for row in results]

    async def get_emote(self, emote_name, guild_id, inc_count: bool = False) -> Emote | None:
        """
            Get emote from database and optionally increment its usage count.
        """

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
