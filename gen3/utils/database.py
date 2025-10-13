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

import asyncpg
from redbot.core import data_manager


class Gen3Database:
    """
    Dedicated database class for Gen3 cog operations.
    Self-contained and independent of other cogs.
    """
    
    def __init__(self):
        self.pool = None
    
    async def init_pool(self):
        """Initialize the database connection pool using Red Bot's database config."""
        if self.pool is not None:
            return
            
        # Get database credentials from Red Bot's data manager
        db_config = data_manager.storage_details()
        
        if db_config.get("DB_TYPE") == "PostgreSQL":
            # Use PostgreSQL connection details
            self.pool = await asyncpg.create_pool(
                host=db_config.get("DB_HOST", "localhost"),
                port=db_config.get("DB_PORT", 5432),
                user=db_config.get("DB_USER", "postgres"),
                password=db_config.get("DB_PASS", ""),
                database=db_config.get("DB_NAME", "redbot"),
                min_size=1,
                max_size=5
            )
        else:
            raise Exception("Gen3 cog requires PostgreSQL database configuration")
    
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
        """
        # Ensure pool is initialized
        if self.pool is None:
            await self.init_pool()
        
        # SQL to create the schema if it doesn't exist
        create_schema_query = "CREATE SCHEMA IF NOT EXISTS gen3;"

        # SQL to create the table 'strikes' in the schema, adjust columns as needed.
        create_table_query = """
                             CREATE TABLE IF NOT EXISTS gen3.strikes
                             (
                                 user_id
                                 BIGINT
                                 NOT
                                 NULL,
                                 guild_id
                                 BIGINT
                                 NOT
                                 NULL,
                                 strikes
                                 INTEGER
                                 DEFAULT
                                 0,
                                 PRIMARY
                                 KEY
                             (
                                 user_id,
                                 guild_id
                             )
                                 ); \
                             """

        # Execute the commands
        await self.execute_query(create_schema_query)
        await self.execute_query(create_table_query)

    async def increment_strike(self, user_id: int, guild_id: int) -> int:
        """Increment the strike count for a user in a given guild."""
        query = """
                INSERT INTO gen3.strikes (user_id, guild_id, strikes)
                VALUES ($1, $2, 1) ON CONFLICT (user_id, guild_id)
            DO
                UPDATE SET strikes = gen3.strikes.strikes + 1
                    RETURNING strikes; \
                """
        return await self.execute_query(query, user_id, guild_id, fetchval=True)

    async def decrease_strike(self, user_id: int, guild_id: int) -> int:
        """Decrement the strike count for a user in a given guild."""
        query = """
                UPDATE gen3.strikes
                SET strikes = GREATEST(strikes - 1, 0)
                WHERE user_id = $1
                  AND guild_id = $2 RETURNING strikes \
                """
        result = await self.execute_query(query, user_id, guild_id, fetchval=True)

        # If no rows were updated (user had no strikes), return 0
        return result if result is not None else 0

    async def get_strikes(self, user_id: int, guild_id: int) -> int:
        """Get the strike count for a user in a given guild."""
        query = "SELECT strikes FROM gen3.strikes WHERE user_id = $1 AND guild_id = $2"
        return await self.execute_query(query, user_id, guild_id, fetchval=True) or 0

    async def reset_strikes(self, user_id: int, guild_id: int) -> None:
        """Reset the strike count for a user in a given guild."""
        query = "DELETE FROM gen3.strikes WHERE user_id = $1 AND guild_id = $2"
        await self.execute_query(query, user_id, guild_id)