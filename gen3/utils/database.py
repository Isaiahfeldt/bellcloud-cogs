#  Copyright (c) 2024-2025, Isaiah Feldt
#  ͏
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU Affero General Public License (AGPL) as published by
#     - the Free Software Foundation, either version 3 of the License,
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

import asyncpg


class Gen3Database:
    """
    Dedicated database class for Gen3 cog operations.
    Self-contained and independent of other cogs.
    """

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
        # Connection pool (will be initialized via async call)
        self.pool: asyncpg.Pool | None = None

    async def init_pool(self):
        """Initialize the asyncpg connection pool."""
        self.pool = await asyncpg.create_pool(**self.CONNECTION_PARAMS, min_size=1, max_size=10)

    async def close_pool(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def execute_query(self, query: str, *args, fetchval=False, fetchrow=False, fetch=False):
        """Execute a database query with proper error handling."""
        if self.pool is None:
            await self.init_pool()

        async with self.pool.acquire() as connection:
            if fetchval:
                return await connection.fetchval(query, *args)
            elif fetchrow:
                return await connection.fetchrow(query, *args)
            elif fetch:
                return await connection.fetch(query, *args)
            else:
                await connection.execute(query, *args)

    async def fetch_query(self, query: str, *args):
        """Fetch multiple rows from a query."""
        return await self.execute_query(query, *args, fetch=True)

    async def init_schema(self):
        """
        Initialize the necessary schema and table if they do not exist.
        Also perform lightweight migrations to keep schema up-to-date.
        """
        # Ensure pool is initialized
        if self.pool is None:
            await self.init_pool()

        async with self.pool.acquire() as connection:
            # SQL to create the schema if it doesn't exist
            await connection.execute("CREATE SCHEMA IF NOT EXISTS gen3;")

            # Seasons table: scoped per guild
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gen3.seasons (
                    id BIGSERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    label TEXT,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ended_at TIMESTAMPTZ,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                );
                """
            )

            # Ensure only one active season per guild (partial unique index)
            await connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_seasons_active_per_guild
                    ON gen3.seasons (guild_id)
                    WHERE is_active;
                """
            )

            # Base strikes table definition with season support
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gen3.strikes (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    season_id BIGINT NOT NULL REFERENCES gen3.seasons(id),
                    strikes INTEGER DEFAULT 0,
                    msg_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, season_id)
                );
                """
            )

            # Migration: add columns if they don't exist
            await connection.execute(
                "ALTER TABLE IF EXISTS gen3.strikes ADD COLUMN IF NOT EXISTS msg_count INTEGER DEFAULT 0;"
            )
            await connection.execute(
                "ALTER TABLE IF EXISTS gen3.strikes ADD COLUMN IF NOT EXISTS season_id BIGINT;"
            )
            await connection.execute("UPDATE gen3.strikes SET msg_count = 0 WHERE msg_count IS NULL;")

            # Backfill legacy rows without a season
            legacy_guilds = await connection.fetch(
                "SELECT DISTINCT guild_id FROM gen3.strikes WHERE season_id IS NULL;"
            )
            for record in legacy_guilds:
                guild_id = int(record["guild_id"])
                season = await connection.fetchrow(
                    """
                    INSERT INTO gen3.seasons (guild_id, label, started_at, is_active)
                    VALUES ($1, 'Legacy Season', NOW(), TRUE)
                    ON CONFLICT (guild_id) WHERE is_active DO UPDATE SET label = EXCLUDED.label
                    RETURNING *;
                    """,
                    guild_id,
                )
                if season:
                    await connection.execute(
                        "UPDATE gen3.strikes SET season_id = $1 WHERE guild_id = $2 AND season_id IS NULL;",
                        season["id"],
                        guild_id,
                    )

            # Enforce NOT NULL and constraints now that backfill is done
            await connection.execute(
                "ALTER TABLE gen3.strikes ALTER COLUMN season_id SET NOT NULL;"
            )
            await connection.execute(
                """
                ALTER TABLE gen3.strikes
                    ADD CONSTRAINT IF NOT EXISTS strikes_season_fk
                    FOREIGN KEY (season_id) REFERENCES gen3.seasons(id);
                """
            )

            # Reset primary key to include season_id
            await connection.execute(
                "ALTER TABLE gen3.strikes DROP CONSTRAINT IF EXISTS strikes_pkey;"
            )
            await connection.execute(
                "ALTER TABLE gen3.strikes ADD CONSTRAINT strikes_pkey PRIMARY KEY (user_id, guild_id, season_id);"
            )

            await connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_strikes_guild_season ON gen3.strikes (guild_id, season_id);"
            )

    async def get_active_season(self, guild_id: int) -> asyncpg.Record | None:
        """Return the active season for a guild, if any."""
        query = "SELECT * FROM gen3.seasons WHERE guild_id = $1 AND is_active = TRUE LIMIT 1;"
        return await self.execute_query(query, guild_id, fetchrow=True)

    async def get_or_create_active_season(
        self, guild_id: int, *, label: str | None = None
    ) -> asyncpg.Record:
        """Fetch the active season for a guild or create one if missing."""
        season = await self.get_active_season(guild_id)
        if season:
            return season

        query = (
            "INSERT INTO gen3.seasons (guild_id, label, started_at, is_active) "
            "VALUES ($1, $2, NOW(), TRUE) RETURNING *;"
        )
        return await self.execute_query(query, guild_id, label, fetchrow=True)

    async def start_new_season(
        self, guild_id: int, label: str | None = None
    ) -> tuple[asyncpg.Record | None, asyncpg.Record]:
        """Close the active season and start a new one for the guild."""
        if self.pool is None:
            await self.init_pool()

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                current = await connection.fetchrow(
                    "SELECT * FROM gen3.seasons WHERE guild_id = $1 AND is_active = TRUE LIMIT 1;",
                    guild_id,
                )
                if current:
                    await connection.execute(
                        "UPDATE gen3.seasons SET is_active = FALSE, ended_at = COALESCE(ended_at, NOW()) WHERE id = $1;",
                        current["id"],
                    )

                new_season = await connection.fetchrow(
                    """
                    INSERT INTO gen3.seasons (guild_id, label, started_at, is_active)
                    VALUES ($1, $2, NOW(), TRUE)
                    RETURNING *;
                    """,
                    guild_id,
                    label,
                )

                # Double-check exclusivity of active season
                await connection.execute(
                    "UPDATE gen3.seasons SET is_active = FALSE WHERE guild_id = $1 AND id <> $2;",
                    guild_id,
                    new_season["id"],
                )

                return current, new_season

    async def list_seasons(self, guild_id: int):
        """Return all seasons for a guild ordered by creation."""
        query = "SELECT * FROM gen3.seasons WHERE guild_id = $1 ORDER BY id ASC;"
        return await self.fetch_query(query, guild_id)

    async def _get_active_season_id(self, guild_id: int) -> int:
        season = await self.get_or_create_active_season(guild_id)
        return int(season["id"])

    async def increment_strike(self, user_id: int, guild_id: int) -> int:
        """Increment the strike count for a user in a given guild's active season."""
        season_id = await self._get_active_season_id(guild_id)
        query = """
                INSERT INTO gen3.strikes (user_id, guild_id, season_id, strikes)
                VALUES ($1, $2, $3, 1)
                ON CONFLICT (user_id, guild_id, season_id)
                    DO UPDATE SET strikes = gen3.strikes.strikes + 1
                RETURNING strikes; \
                """
        return await self.execute_query(query, user_id, guild_id, season_id, fetchval=True)

    async def decrease_strike(self, user_id: int, guild_id: int) -> int:
        """Decrement the strike count for a user in a given guild."""
        season_id = await self._get_active_season_id(guild_id)
        query = """
                UPDATE gen3.strikes
                SET strikes = GREATEST(strikes - 1, 0)
                WHERE user_id = $1
                  AND guild_id = $2
                  AND season_id = $3
                RETURNING strikes \
                """
        result = await self.execute_query(query, user_id, guild_id, season_id, fetchval=True)

        # If no rows were updated (user had no strikes), return 0
        return result if result is not None else 0

    async def get_strikes(self, user_id: int, guild_id: int) -> int:
        """Get the strike count for a user in a given guild."""
        season_id = await self._get_active_season_id(guild_id)
        query = "SELECT strikes FROM gen3.strikes WHERE user_id = $1 AND guild_id = $2 AND season_id = $3"
        return await self.execute_query(query, user_id, guild_id, season_id, fetchval=True) or 0

    async def reset_strikes(self, user_id: int, guild_id: int) -> None:
        """Reset the strike count for a user in a given guild without losing message count."""
        season_id = await self._get_active_season_id(guild_id)
        query = (
            "INSERT INTO gen3.strikes (user_id, guild_id, season_id, strikes, msg_count) "
            "VALUES ($1, $2, $3, 0, 0) "
            "ON CONFLICT (user_id, guild_id, season_id) DO UPDATE SET strikes = 0;"
        )
        await self.execute_query(query, user_id, guild_id, season_id)

    async def ensure_user_row(self, user_id: int, guild_id: int) -> None:
        """Ensure a row exists for the user with strikes=0 and msg_count=0."""
        season_id = await self._get_active_season_id(guild_id)
        query = (
            "INSERT INTO gen3.strikes (user_id, guild_id, season_id, strikes, msg_count) "
            "VALUES ($1, $2, $3, 0, 0) ON CONFLICT (user_id, guild_id, season_id) DO NOTHING;"
        )
        await self.execute_query(query, user_id, guild_id, season_id)

    async def increment_msg_count(self, user_id: int, guild_id: int) -> int:
        """Increment the message count for the user in the guild, creating row if needed."""
        season_id = await self._get_active_season_id(guild_id)
        query = (
            "INSERT INTO gen3.strikes (user_id, guild_id, season_id, strikes, msg_count) "
            "VALUES ($1, $2, $3, 0, 1) "
            "ON CONFLICT (user_id, guild_id, season_id) DO UPDATE SET msg_count = gen3.strikes.msg_count + 1 "
            "RETURNING msg_count;"
        )
        return await self.execute_query(query, user_id, guild_id, season_id, fetchval=True)

    async def fetch_standings(self, guild_id: int):
        """Fetch active standings (strikes < 3), ordered by lowest strikes then msg_count desc."""
        season_id = await self._get_active_season_id(guild_id)
        query = (
            "SELECT user_id, strikes, msg_count FROM gen3.strikes "
            "WHERE guild_id = $1 AND season_id = $2 AND strikes < 3 "
            "ORDER BY strikes ASC, msg_count DESC, user_id ASC"
        )
        return await self.fetch_query(query, guild_id, season_id)

    async def fetch_struck_out(self, guild_id: int):
        """Fetch struck-out users (strikes >= 3), ordered by msg_count desc."""
        season_id = await self._get_active_season_id(guild_id)
        query = (
            "SELECT user_id, strikes, msg_count FROM gen3.strikes "
            "WHERE guild_id = $1 AND season_id = $2 AND strikes >= 3 "
            "ORDER BY msg_count DESC, user_id ASC"
        )
        return await self.fetch_query(query, guild_id, season_id)

    async def fetch_standings_for_season(self, guild_id: int, season_id: int):
        """Fetch standings for a specific season."""
        query = (
            "SELECT user_id, strikes, msg_count FROM gen3.strikes "
            "WHERE guild_id = $1 AND season_id = $2 AND strikes < 3 "
            "ORDER BY strikes ASC, msg_count DESC, user_id ASC"
        )
        return await self.fetch_query(query, guild_id, season_id)

    async def fetch_struck_out_for_season(self, guild_id: int, season_id: int):
        """Fetch struck-out users for a specific season."""
        query = (
            "SELECT user_id, strikes, msg_count FROM gen3.strikes "
            "WHERE guild_id = $1 AND season_id = $2 AND strikes >= 3 "
            "ORDER BY msg_count DESC, user_id ASC"
        )
        return await self.fetch_query(query, guild_id, season_id)
