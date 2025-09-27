# File: emote/utils/database.py
import hashlib
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

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

        session = boto3.session.Session()
        self.s3_client = session.client(
            's3',
            region_name='nyc3',
            endpoint_url='https://bkt-bellcloud.nyc3.digitaloceanspaces.com',
            aws_access_key_id=self.BUCKET_PARAMS['access_key_id'],
            aws_secret_access_key=self.BUCKET_PARAMS['secret_access_key']
        )

    async def init_pool(self):
        """Initialize the asyncpg connection pool."""
        self.pool = await asyncpg.create_pool(**self.CONNECTION_PARAMS, min_size=1, max_size=10)
        await self.init_cache_schema()

    async def close_pool(self):
        """Close the asyncpg connection pool."""
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def execute_query(self, query, *args, fetchval: bool = False):
        """Use the connection pool to execute a query."""
        if self.pool is None:
            raise Exception("Pool not initialized. Call init_pool() first.")
        async with self.pool.acquire() as conn:
            if fetchval:
                result = await conn.fetchval(query, *args)
            else:
                result = await conn.execute(query, *args)
            self.cache.clear()  # Invalidate cache on DB write
            return result

    async def fetch_query(self, query, *args):
        key = (query, args)  # Include the query in the cache key
        if key in self.cache:
            return self.cache[key]
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, *args)
            self.cache[key] = result
            return result

    async def update_file_to_bucket(self, interaction: discord.Interaction, name: str, url: str, file_type: str):
        with tempfile.TemporaryDirectory() as temp_dir:
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
                    self.s3_client.upload_file(
                        file_path,
                        'emote',
                        f"{interaction.guild.id}/{name.lower()}.{file_type}",
                        ExtraArgs={'ACL': 'public-read', 'ContentType': f"video/{file_type}"}
                    )
                else:
                    self.s3_client.upload_file(
                        file_path,
                        'emote',
                        f"{interaction.guild.id}/{name.lower()}.{file_type}",
                        ExtraArgs={'ACL': 'public-read', 'ContentType': f"image/{file_type}"}
                    )
                return True, None

            except botocore.exceptions.ClientError as e:
                return False, e

    async def remove_file_from_bucket(self, emote: Emote):
        if emote is not None:
            self.s3_client.delete_object(Bucket='emote', Key=emote.file_path)
            return True, None

        return False, None

    async def add_emote_to_database(self, interaction: discord.Interaction, name: str, url: str, file_type: str):
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
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

    async def remove_emote_from_database(self, interaction: discord.Interaction, name: str):
        emote: Optional[Emote] = await self.get_emote(str(name), interaction.guild.id, False)
        # Remove the erroneous 'return emote' line here
        query = (
            "DELETE FROM emote.media WHERE emote_name = $1 AND guild_id = $2"
        )
        values = (name, interaction.guild.id)

        result = await self.execute_query(query, *values)
        if result is not None:
            success, error = await self.remove_file_from_bucket(emote)
            if success:
                return True, None
            else:
                return False, error
        return False, None

    async def process_query_results(self, results):
        if not results:
            return False
        return results[0]['exists']

    async def check_emote_exists(self, emote_name, guild_id):
        """Check for the existence of an emote in the database."""
        key = (emote_name, guild_id)
        if key in self.cache:
            return self.cache[key]
        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1 AND guild_id = $2)"
        result = await self.fetch_query(query, emote_name, guild_id)
        exists = await self.process_query_results(result)
        self.cache[key] = exists
        return exists

    async def get_emote_names(self, guild_id):
        """Retrieve emote names from the database."""
        query = "SELECT emote_name FROM emote.media WHERE guild_id = $1"
        result = await self.fetch_query(query, guild_id)
        return await self.format_names_from_results(result)

    async def format_names_from_results(self, results):
        if results is None:
            return []
        return [row[0] for row in results]

    async def get_emote(self, emote_name, guild_id, inc_count: bool = False) -> Emote | None:
        """Get emote from database and optionally increment its usage count."""

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


    async def get_top_emotes_by_usage(self, guild_id, limit: int = 10):
        """Get top emotes by usage count for leaderboard."""
        query = (
            "SELECT emote_name, usage_count, author_id FROM emote.media "
            "WHERE guild_id = $1 ORDER BY usage_count DESC LIMIT $2"
        )
        result = await self.fetch_query(query, guild_id, limit)
        if result is None:
            return []
        return [(row[0], row[1], row[2]) for row in result]  # (name, usage_count, author_id)

    # === EMOTE EFFECTS CACHE SYSTEM ===

    async def init_cache_schema(self):
        """Initialize the emote effects cache table."""
        # Create the main table first
        create_table_query = """
        CREATE TABLE IF NOT EXISTS emote.effects_cache (
            cache_key VARCHAR(64) PRIMARY KEY,
            source_emote_name VARCHAR(255) NOT NULL,
            source_guild_id BIGINT NOT NULL,
            source_image_hash VARCHAR(64) NOT NULL,
            effect_combination VARCHAR(512) NOT NULL,
            cached_file_path VARCHAR(512) NOT NULL,
            created_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            last_accessed TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            file_size BIGINT NOT NULL,
            FOREIGN KEY (source_emote_name, source_guild_id) 
                REFERENCES emote.media(emote_name, guild_id) 
                ON DELETE CASCADE
        )
        """
        await self.execute_query(create_table_query)
        
        # Create the indexes separately
        create_index_source_query = """
        CREATE INDEX IF NOT EXISTS idx_effects_cache_source 
            ON emote.effects_cache(source_emote_name, source_guild_id)
        """
        await self.execute_query(create_index_source_query)
        
        create_index_accessed_query = """
        CREATE INDEX IF NOT EXISTS idx_effects_cache_accessed 
            ON emote.effects_cache(last_accessed)
        """
        await self.execute_query(create_index_accessed_query)

    def generate_cache_key(self, source_image_data: bytes, effect_combination: str) -> str:
        """Generate a unique cache key from source image and effect combination."""
        # Hash the source image data
        source_hash = hashlib.sha256(source_image_data).hexdigest()[:16]
        
        # Normalize and hash the effect combination
        effects_normalized = self._normalize_effect_combination(effect_combination)
        effects_hash = hashlib.md5(effects_normalized.encode()).hexdigest()[:16]
        
        # Combine to create cache key
        cache_key = f"{source_hash}_{effects_hash}"
        return cache_key

    def _normalize_effect_combination(self, effect_combination: str) -> str:
        """Normalize effect combination string for consistent caching."""
        if not effect_combination:
            return "none"
        
        # Split effects, sort them alphabetically for consistency
        effects = [effect.strip().lower() for effect in effect_combination.split(',')]
        effects.sort()
        return ','.join(effects)

    async def get_cached_effect(self, cache_key: str) -> Optional[dict]:
        """Get cached effect result by cache key."""
        query = """
        SELECT cached_file_path, created_timestamp, file_size 
        FROM emote.effects_cache 
        WHERE cache_key = $1
        """
        result = await self.fetch_query(query, cache_key)
        if result:
            # Update last accessed time
            await self.execute_query(
                "UPDATE emote.effects_cache SET last_accessed = $1 WHERE cache_key = $2",
                datetime.now(timezone.utc).replace(tzinfo=None), cache_key
            )
            return {
                'cached_file_path': result[0]['cached_file_path'],
                'created_timestamp': result[0]['created_timestamp'],
                'file_size': result[0]['file_size']
            }
        return None

    async def store_cached_effect(self, cache_key: str, source_emote_name: str, 
                                source_guild_id: int, source_image_hash: str,
                                effect_combination: str, cached_file_path: str, 
                                file_size: int) -> bool:
        """Store a cached effect result."""
        try:
            timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
            query = """
            INSERT INTO emote.effects_cache 
            (cache_key, source_emote_name, source_guild_id, source_image_hash, 
             effect_combination, cached_file_path, created_timestamp, last_accessed, file_size)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (cache_key) DO UPDATE SET
                last_accessed = $8,
                file_size = $9
            """
            await self.execute_query(
                query, cache_key, source_emote_name, source_guild_id, 
                source_image_hash, effect_combination, cached_file_path, 
                timestamp, timestamp, file_size
            )
            return True
        except Exception as e:
            print(f"Error storing cached effect: {e}")
            return False

    async def cleanup_cache_for_emote(self, emote_name: str, guild_id: int):
        """Clean up cache entries when an emote is deleted (called automatically by CASCADE)."""
        # This method is mainly for manual cleanup if needed
        # The CASCADE DELETE should handle automatic cleanup
        query = """
        DELETE FROM emote.effects_cache 
        WHERE source_emote_name = $1 AND source_guild_id = $2
        """
        await self.execute_query(query, emote_name, guild_id)

    async def get_cache_stats(self) -> dict:
        """Get statistics about the effects cache."""
        query = """
        SELECT 
            COUNT(*) as total_entries,
            SUM(file_size) as total_size,
            AVG(file_size) as avg_size
        FROM emote.effects_cache
        """
        result = await self.fetch_query(query)
        if result and result[0]:
            return {
                'total_entries': result[0]['total_entries'] or 0,
                'total_size': result[0]['total_size'] or 0,
                'avg_size': result[0]['avg_size'] or 0
            }
        return {'total_entries': 0, 'total_size': 0, 'avg_size': 0}
