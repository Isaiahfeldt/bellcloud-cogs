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

import asyncpg


async def process_query_results(results):
    """
    :param results: A list of query results.
    :return: A boolean value indicating if the results exist.
    """
    if not results:
        return False
    return results[0]['exists']


class Database:
    CONNECTION_PARAMS = {
        "host": os.getenv('DB_HOST'),
        "port": os.getenv('DB_PORT'),
        "database": os.getenv('DB_DATABASE'),
        "user": os.getenv('DB_USER'),
        "password": os.getenv('DB_PASSWORD'),
    }

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

        This method executes the provided SQL query with the given arguments and returns the result. It first gets a
        connection from the connection pool using the get_connection() method. Then *, it executes the query using
        the fetch() method of the connection object, passing the query and arguments as parameters. Finally,
        it releases the connection back to the pool by closing * it.

        Note: This method is an asynchronous method and should be awaited when called.

        Example usage:
        result = await execute_query("SELECT * FROM users")
        """
        conn = await self.get_connection()
        try:
            return await conn.fetch(query, *args)
        finally:
            if conn:
                await conn.close()

    async def emote_exists_in_database(self, name):
        """
        :param name: The name of the emote to check existence for in the database.
        :return: True if the emote exists in the database, False otherwise.
        """
        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1)"
        result = await self.execute_query(query, name)
        return await process_query_results(result)

    async def get_names_from_results(self, results):
        """
        :param results: the results from a database query
        :return: a list of names extracted from the results
        """
        if results is None:
            return []
        return [row[0] for row in results]

    async def get_emote_names(self):
        """
        Retrieve the names of emotes from the media table.

        :return: A list of emote names.
        """
        query = "SELECT emote_name FROM emote.media"
        result = await self.execute_query(query)
        return self.get_names_from_results(result)
