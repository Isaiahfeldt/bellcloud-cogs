# File: emote/utils/database.py
import io
import os
from datetime import datetime, timezone
from typing import Optional, List, Tuple

import aiohttp
import asyncpg
import boto3
import botocore
import discord
from cachetools import TTLCache

from emote.utils.effects import Emote
from .enums import EmoteError  # Assuming enums might be used for errors


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
            maxsize=250,
            ttl=600
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
        if self.pool is not None:
            await self.close_pool()  # Ensure clean state if re-initializing
        self.pool = await asyncpg.create_pool(**self.CONNECTION_PARAMS, min_size=1, max_size=10)
        await self.init_emote_schema()
        await self.init_strike_schema()
        await self.init_variant_schema()

    async def close_pool(self):
        """Close the asyncpg connection pool."""
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def execute_query(self, query, *args, fetchval: bool = False, fetch: bool = False):
        """Use the connection pool to execute a query or fetch results."""
        if self.pool is None:
            raise Exception("Pool not initialized. Call init_pool() first.")

        # Determine if the operation is likely a write/modification
        is_write_operation = any(
            keyword in query.upper() for keyword in ["INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"]
        )

        async with self.pool.acquire() as conn:
            if fetchval:
                result = await conn.fetchval(query, *args)
            elif fetch:
                result = await conn.fetch(query, *args)
            else:
                result = await conn.execute(query, *args)  # Returns status string like 'INSERT 0 1'

            if is_write_operation:
                self.cache.clear()  # Invalidate cache on potential DB write/modification

            return result

    async def fetch_query(self, query, *args):
        """Fetch multiple rows, using cache."""
        key = ('fetch', query, args)
        if key in self.cache:
            return self.cache[key]
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, *args)
            self.cache[key] = result
            return result

    async def fetchrow_query(self, query, *args):
        """Fetch a single row, using cache."""
        key = ('fetchrow', query, args)
        if key in self.cache:
            return self.cache[key]
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, *args)
            self.cache[key] = result
            return result

    async def fetchval_query(self, query, *args):
        """Fetch a single value, using cache."""
        key = ('fetchval', query, args)
        if key in self.cache:
            return self.cache[key]
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, *args)
            self.cache[key] = result
            return result

    # === S3 Bucket Operations ===

    async def _upload_to_bucket(self, bucket: str, key: str, data: bytes, content_type: str) -> Tuple[
        bool, Optional[str]]:
        """Helper to upload bytes data to S3."""
        try:
            self.s3_client.upload_fileobj(
                io.BytesIO(data),
                bucket,
                key,
                ExtraArgs={'ACL': 'public-read', 'ContentType': content_type}
            )
            return True, None
        except botocore.exceptions.ClientError as e:
            print(f"S3 Upload Error to {bucket}/{key}: {e}")
            return False, str(e)
        except Exception as e:
            print(f"Unexpected Upload Error to {bucket}/{key}: {e}")
            return False, str(e)

    async def _remove_from_bucket(self, bucket: str, key: str) -> Tuple[bool, Optional[str]]:
        """Helper to remove an object from S3."""
        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            return True, None
        except botocore.exceptions.ClientError as e:
            print(f"S3 Delete Error for {bucket}/{key}: {e}")
            return False, str(e)
        except Exception as e:
            print(f"Unexpected Delete Error for {bucket}/{key}: {e}")
            return False, str(e)

    async def upload_emote_to_bucket(self, guild_id: int, name: str, url: str, file_type: str) -> Tuple[
        bool, Optional[str]]:
        """Downloads a file and uploads it as an original emote."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()  # Raise exception for bad status codes
                    emote_data = await response.read()
            except aiohttp.ClientError as e:
                print(f"Failed to download {url}: {e}")
                return False, f"Failed to download emote file: {e}"
            except Exception as e:
                print(f"Unexpected error downloading {url}: {e}")
                return False, f"Unexpected error downloading emote file: {e}"

        content_type = f"video/{file_type}" if file_type == 'mp4' else f"image/{file_type}"
        s3_key = f"{guild_id}/{name.lower()}.{file_type}"
        success, error = await self._upload_to_bucket('emote', s3_key, emote_data, content_type)
        return success, error

    async def upload_variant_to_bucket(self, guild_id: int, variant_filename: str, img_data: bytes, file_type: str) -> \
    Tuple[bool, Optional[str]]:
        """Uploads generated variant data to the bucket."""
        content_type = f"video/{file_type}" if file_type == 'mp4' else f"image/{file_type}"
        s3_key = f"{guild_id}/variants/{variant_filename}"  # Store in variants subfolder
        return await self._upload_to_bucket('emote', s3_key, img_data, content_type)

    async def remove_emote_from_bucket(self, emote_file_path: str) -> Tuple[bool, Optional[str]]:
        """Removes an original emote file from the bucket."""
        # emote_file_path is expected to be like "guild_id/emote_name.ext"
        return await self._remove_from_bucket('emote', emote_file_path)

    async def remove_variant_from_bucket(self, variant_file_path: str) -> Tuple[bool, Optional[str]]:
        """Removes a variant file from the bucket."""
        # variant_file_path is expected to be like "guild_id/variants/variant_name.ext"
        return await self._remove_from_bucket('emote', variant_file_path)

    # === Emote Operations ===

    async def init_emote_schema(self):
        """Initialize the emote schema and table."""
        create_schema_query = "CREATE SCHEMA IF NOT EXISTS emote;"
        create_table_query = """
        CREATE TABLE IF NOT EXISTS emote.media (
            id SERIAL PRIMARY KEY,
            file_path TEXT UNIQUE NOT NULL,
            author_id BIGINT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            original_url TEXT NOT NULL,
            emote_name TEXT NOT NULL,
            guild_id BIGINT NOT NULL,
            usage_count INTEGER DEFAULT 0,
            CONSTRAINT emote_guild_name_unique UNIQUE (guild_id, emote_name)
        );
        CREATE INDEX IF NOT EXISTS emote_guild_id_idx ON emote.media (guild_id);
        CREATE INDEX IF NOT EXISTS emote_guild_name_idx ON emote.media (guild_id, emote_name);
        """
        await self.execute_query(create_schema_query)
        await self.execute_query(create_table_query)

    async def add_emote_to_database(self, interaction: discord.Interaction, name: str, url: str, file_type: str) -> \
    Tuple[bool, Optional[EmoteError]]:
        """Adds original emote metadata to the database."""
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
        file_path = f"{interaction.guild.id}/{name.lower()}.{file_type}"
        query = (
            "INSERT INTO emote.media "
            "(file_path, author_id, timestamp, original_url, emote_name, guild_id, usage_count) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)"
            "ON CONFLICT (guild_id, emote_name) DO NOTHING"  # Avoid duplicates
        )
        values = (
            file_path,
            interaction.user.id,
            timestamp,
            url,
            name,
            interaction.guild.id,
            0
        )
        try:
            result = await self.execute_query(query, *values)
            # Check if insert actually happened
            if 'INSERT 0 1' in result:
                # Upload to bucket only if DB insert was successful
                success, error = await self.upload_emote_to_bucket(interaction.guild.id, name, url, file_type)
                if success:
                    self.cache.clear()  # Ensure cache is cleared on successful add
                    return True, None
                else:
                    # Rollback
                    print(f"S3 upload failed for {name}, attempting DB rollback.")
                    delete_query = "DELETE FROM emote.media WHERE file_path = $1"
                    await self.execute_query(delete_query, file_path)
                    return False, EmoteError.S3_UPLOAD_FAILED
            elif 'INSERT 0 0' in result:
                print(f"Emote '{name}' already exists in DB for guild {interaction.guild.id}.")
                return False, EmoteError.DUPLICATE_EMOTE_NAME
            else:
                print(f"Unexpected result from INSERT: {result}")
                return False, EmoteError.DATABASE_ERROR

        except asyncpg.UniqueViolationError:
            print(f"Unique constraint violation for emote '{name}' in guild {interaction.guild.id}.")
            return False, EmoteError.DUPLICATE_EMOTE_NAME
        except Exception as e:
            print(f"Error adding emote {name} to database: {e}")
            # Attempt rollback
            delete_query = "DELETE FROM emote.media WHERE file_path = $1"
            await self.execute_query(delete_query, file_path)
            return False, EmoteError.DATABASE_ERROR

    async def remove_emote_from_database(self, guild_id: int, name: str) -> Tuple[bool, Optional[EmoteError]]:
        """Removes original emote metadata and its variants from the database and S3."""
        emote: Optional[Emote] = await self.get_emote(name, guild_id, inc_count=False)
        if emote is None:
            return False, EmoteError.NOTFOUND_EMOTE_NAME

        # Remove associated variants first (DB + S3)
        variant_paths = await self.remove_variants_for_emote(emote.id)
        s3_variant_removal_errors = []
        for path in variant_paths:
            success, error = await self.remove_variant_from_bucket(path)
            if not success:
                s3_variant_removal_errors.append(f"Failed to delete variant {path}: {error}")

        # Remove original emote from DB
        delete_query = "DELETE FROM emote.media WHERE id = $1 RETURNING file_path"
        try:
            deleted_path = await self.execute_query(delete_query, emote.id, fetchval=True)
            if deleted_path:
                # Remove original emote from S3
                success, error = await self.remove_emote_from_bucket(deleted_path)
                if not success:
                    print(f"Failed to remove original emote from S3: {deleted_path}, Error: {error}")

                self.cache.clear()  # Clear cache after successful removal

                if s3_variant_removal_errors:
                    print("Errors occurred during variant S3 removal:", s3_variant_removal_errors)
                return True, None
            else:
                print(f"Emote {name} (ID: {emote.id}) not found during DELETE, possibly already removed.")
                return False, EmoteError.NOTFOUND_EMOTE_NAME

        except Exception as e:
            print(f"Error removing emote {name} (ID: {emote.id}) from database: {e}")
            return False, EmoteError.DATABASE_ERROR

    async def check_emote_exists(self, emote_name: str, guild_id: int) -> bool:
        """Check for the existence of an original emote in the database."""
        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1 AND guild_id = $2)"
        exists = await self.fetchval_query(query, emote_name, guild_id)
        return exists or False

    async def get_emote_names(self, guild_id: int) -> List[str]:
        """Retrieve original emote names from the database."""
        query = "SELECT emote_name FROM emote.media WHERE guild_id = $1 ORDER BY emote_name"
        result = await self.fetch_query(query, guild_id)
        return [row['emote_name'] for row in result] if result else []

    async def get_emote(self, emote_name: str, guild_id: int, inc_count: bool = False) -> Optional[Emote]:
        """Get original emote from database."""
        query = "SELECT * FROM emote.media WHERE emote_name = $1 AND guild_id = $2"
        emote_row = await self.fetchrow_query(query, emote_name, guild_id)

        if not emote_row:
            return None

        # Convert asyncpg.Record to dict and fix name
        emote_dict = dict(emote_row)
        emote_dict['name'] = emote_dict.pop('emote_name')
        return Emote(**emote_dict)

    async def increment_emote_usage(self, emote_id: int) -> None:
        """Increments the usage count for a specific original emote."""
        update_query = "UPDATE emote.media SET usage_count = usage_count + 1 WHERE id = $1"
        try:
            await self.execute_query(update_query, emote_id)
        except Exception as e:
            print(f"Error incrementing usage count for emote ID {emote_id}: {e}")

    # === Variant Operations ===

    async def init_variant_schema(self):
        """Initialize the variant table schema."""
        # Using 'april' schema as used for strikes, confirm if 'emote' is preferred later
        create_schema_query = "CREATE SCHEMA IF NOT EXISTS april;"
        create_table_query = """
        CREATE TABLE IF NOT EXISTS april.variants (
            variant_id SERIAL PRIMARY KEY,
            original_emote_id INTEGER NOT NULL REFERENCES emote.media(id) ON DELETE CASCADE,
            guild_id BIGINT NOT NULL,
            effects_signature TEXT NOT NULL,
            file_path TEXT UNIQUE NOT NULL,
            file_type TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT variant_emote_signature_unique UNIQUE (original_emote_id, effects_signature)
        );
        CREATE INDEX IF NOT EXISTS variant_original_emote_id_idx ON april.variants (original_emote_id);
        CREATE INDEX IF NOT EXISTS variant_guild_id_idx ON april.variants (guild_id);
        CREATE INDEX IF NOT EXISTS variant_signature_idx ON april.variants (original_emote_id, effects_signature);
        """
        await self.execute_query(create_schema_query)
        await self.execute_query(create_table_query)

    async def get_variant(self, original_emote_id: int, effects_signature: str) -> Optional[dict]:
        """Retrieve a specific variant record by original emote ID and signature."""
        query = """
            SELECT file_path, file_type
            FROM april.variants
            WHERE original_emote_id = $1 AND effects_signature = $2
        """
        variant_row = await self.fetchrow_query(query, original_emote_id, effects_signature)
        return dict(variant_row) if variant_row else None

    async def add_variant(self, original_emote_id: int, guild_id: int, effects_signature: str, file_path: str,
                          file_type: str) -> bool:
        """Adds a new variant record to the database."""
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
        query = """
            INSERT INTO april.variants
            (original_emote_id, guild_id, effects_signature, file_path, file_type, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (original_emote_id, effects_signature) DO NOTHING
        """
        values = (
            original_emote_id,
            guild_id,
            effects_signature,
            file_path,
            file_type,
            timestamp
        )
        try:
            result = await self.execute_query(query, *values)
            if 'INSERT 0 1' in result:
                self.cache.clear()  # Invalidate cache on new variant add
                return True
            elif 'INSERT 0 0' in result:
                # This is expected if cache failed but another process added it. Not necessarily an error.
                # print(f"Variant with signature '{effects_signature}' for emote ID {original_emote_id} already exists.")
                return False
            else:
                print(f"Unexpected result from variant INSERT: {result}")
                return False
        except asyncpg.UniqueViolationError:
            # This can happen in race conditions if ON CONFLICT somehow fails or isn't used.
            print(
                f"Unique constraint violation for variant signature '{effects_signature}' on emote {original_emote_id}.")
            return False
        except Exception as e:
            print(f"Error adding variant for emote ID {original_emote_id}: {e}")
            return False

    async def remove_variants_for_emote(self, original_emote_id: int) -> List[str]:
        """Deletes variant records for a specific emote and returns their file paths."""
        fetch_query = "SELECT file_path FROM april.variants WHERE original_emote_id = $1"
        delete_query = "DELETE FROM april.variants WHERE original_emote_id = $1"
        try:
            # Fetch paths first
            variant_rows = await self.fetch_query(fetch_query, original_emote_id)  # Use cached fetch first
            file_paths = [row['file_path'] for row in variant_rows] if variant_rows else []

            # Then delete
            if file_paths:
                await self.execute_query(delete_query, original_emote_id)
                self.cache.clear()  # Invalidate cache after delete
            return file_paths
        except Exception as e:
            print(f"Error removing variants for emote ID {original_emote_id}: {e}")
            return []

    async def remove_variants_for_guild(self, guild_id: int) -> List[str]:
        """Deletes all variant records for a specific guild and returns their file paths."""
        fetch_query = "SELECT file_path FROM april.variants WHERE guild_id = $1"
        delete_query = "DELETE FROM april.variants WHERE guild_id = $1"
        try:
            variant_rows = await self.fetch_query(fetch_query, guild_id)
            file_paths = [row['file_path'] for row in variant_rows] if variant_rows else []

            if file_paths:
                await self.execute_query(delete_query, guild_id)
                self.cache.clear()  # Invalidate cache after delete
            return file_paths
        except Exception as e:
            print(f"Error removing variants for guild ID {guild_id}: {e}")
            return []

    # === Strike Operations (April Fools) ===

    async def init_strike_schema(self):
        """Initialize the strike schema and table."""
        create_schema_query = "CREATE SCHEMA IF NOT EXISTS april;"
        create_table_query = """
        CREATE TABLE IF NOT EXISTS april.strikes (
            user_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            strikes INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        );
        CREATE INDEX IF NOT EXISTS strikes_guild_id_idx ON april.strikes (guild_id);
        """
        await self.execute_query(create_schema_query)
        await self.execute_query(create_table_query)

    async def increment_strike(self, user_id: int, guild_id: int) -> int:
        """Increments strike count, returns new count."""
        query = """
            INSERT INTO april.strikes (user_id, guild_id, strikes)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id, guild_id)
            DO UPDATE SET strikes = april.strikes.strikes + 1
            RETURNING strikes;
        """
        new_strikes = await self.execute_query(query, user_id, guild_id, fetchval=True)
        return new_strikes or 0

    async def decrease_strike(self, user_id: int, guild_id: int) -> int:
        """Decrements strike count, returns new count (min 0)."""
        query = """
            UPDATE april.strikes
            SET strikes = GREATEST(strikes - 1, 0)
            WHERE user_id = $1 AND guild_id = $2
            RETURNING strikes;
        """
        new_strikes = await self.execute_query(query, user_id, guild_id, fetchval=True)
        if new_strikes is None:
            return 0
        return new_strikes

    async def get_strikes(self, user_id: int, guild_id: int) -> int:
        """Gets current strike count."""
        query = "SELECT strikes FROM april.strikes WHERE user_id = $1 AND guild_id = $2"
        strikes = await self.fetchval_query(query, user_id, guild_id)
        return strikes or 0

    async def reset_strikes(self, user_id: int, guild_id: int) -> None:
        """Reset the strike count for a user in a given guild."""
        query = "DELETE FROM april.strikes WHERE user_id = $1 AND guild_id = $2"
        await self.execute_query(query, user_id, guild_id)
