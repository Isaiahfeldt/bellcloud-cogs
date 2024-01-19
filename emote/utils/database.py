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
from collections import defaultdict

import asyncpg
from cachetools import TTLCache


class Database:
    def __init__(self):
        self.CONNECTION_PARAMS: dict[str, str | None] = {
            "host": os.getenv('DB_HOST'),
            "port": os.getenv('DB_PORT'),
            "database": os.getenv('DB_DATABASE'),
            "user": os.getenv('DB_USER'),
            "password": os.getenv('DB_PASSWORD'),
        }
        self.cache = TTLCache(
            maxsize=100,
            ttl=200
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

        if query in self.cache:
            return self.cache[*args]

        conn = await self.get_connection()

        if query not in self.cache or self.cache.ttl == 0:
            await self.dump_emote_usage_to_database(conn)

        try:
            result = await conn.fetch(query, *args)
            self.cache[*args] = result
            return result
        finally:
            if conn:
                await conn.close()

    async def dump_emote_usage_to_database(self, conn):
        # conn = await self.get_connection()
        try:
            for emote_name, count in self.emote_usage_collection.items():
                query = "UPDATE emote.media SET usage_count = usage_count + $1 WHERE emote_name = $2"
                await conn.execute(query, count, emote_name)

            self.emote_usage_collection.clear()  # clear the staging area
        finally:
            pass
            # if conn:
            #     await conn.close()

    async def process_query_results(self, results):
        if not results:
            return False
        return results[0]['exists']

    async def check_emote_exists(self, emote_name):
        """
        :param emote_name: The name of the emote to check existence for in the database.
        :return: True if the emote exists in the database, False otherwise.
        """
        if emote_name in self.cache:
            return self.cache[emote_name]

        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1)"
        result = await self.fetch_query(query, emote_name)
        exists = await self.process_query_results(result)

        self.cache[emote_name] = exists
        return exists

    async def get_emote_names(self):
        """
        Retrieve the names of emotes from the media table.

        :return: A list of emote names.
        """
        query = "SELECT emote_name FROM emote.media"
        result = await self.fetch_query(query)
        return self.format_names_from_results(result)

    async def format_names_from_results(self, results):
        """
        :param results: the results from a database query

        :return: a list of names extracted from the results
        """
        if results is None:
            return []
        return [row[0] for row in results]

    async def get_emote(self, emote_name, inc_count: bool = False) -> dict:
        """
        Get emote from database.

        :param emote_name: The name of the emote.
        :param inc_count: Whether to increment the usage count of the emote. Defaults to False.

        :return: The emote record as an asyncpg.Record object.
        """

        # select_query = "SELECT file_path FROM emote.media WHERE emote_name = $1"
        select_query = "SELECT * FROM emote.media WHERE emote_name = $1"
        record = await self.fetch_query(select_query, emote_name)
        if not record:
            return None
        if inc_count:
            query = "UPDATE emote.media SET usage_count = usage_count + 1 WHERE emote_name = $1"
            await self.execute_query(query, emote_name)

        record_dict = dict(record[0])
        record_dict['name'] = record_dict.pop('emote_name')
        return record_dict
