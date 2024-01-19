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

# test_database.py

import asyncio
import subprocess
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from emote.utils.database import Database


class TestDatabaseMethods(unittest.TestCase):

    # Using events loop for functions that require async/await
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    @patch("asyncpg.connect")
    def test_get_connection(self, mock_connect):
        db = Database()
        self.loop.run_until_complete(db.get_connection())
        self.assertTrue(mock_connect.called)

    @patch("asyncpg.connect")
    def test_fetch_query(self, mock_connect):
        conn = MagicMock()
        conn.fetch = AsyncMock()
        conn.close = AsyncMock()
        mock_connect.return_value = conn

        db = Database()
        sample_query = "SELECT * FROM table;"
        self.loop.run_until_complete(db.fetch_query(sample_query))
        conn.fetch.assert_called_once_with(sample_query)
        conn.close.assert_called_once()

    def test_emote_exists_in_database_real(self):
        EMOTE_NAMES = ["isaiah", "miku4"]  # replace with your emote names
        db = Database()
        for emote_name in EMOTE_NAMES:
            result = self.loop.run_until_complete(db.check_emote_exists(emote_name))
            self.assertTrue(result, f"Expected emote {emote_name} to exist in database, but it didn't.")

    def test_get_emote_real(self):
        emote_name = "miku4"
        db = Database()
        result = self.loop.run_until_complete(db.get_emote(emote_name))
        # print(result)

    @patch("asyncpg.connect")
    def test_emote_exists_in_database_mock(self, mock_connect):
        conn = AsyncMock()
        conn.fetch = AsyncMock()
        conn.close = AsyncMock()
        mock_connect.return_value = conn

        db = Database()
        sample_emote_name = "emote1"
        self.loop.run_until_complete(db.check_emote_exists(sample_emote_name))
        conn.fetch.assert_called_once()
        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1)"
        conn.fetch.assert_called_once_with(query, sample_emote_name)
        conn.close.assert_called_once()

    def test_process_query_results(self):
        db = Database()
        self.assertFalse(self.loop.run_until_complete(db.process_query_results(None)))
        self.assertFalse(self.loop.run_until_complete(db.process_query_results([])))
        self.assertTrue(self.loop.run_until_complete(db.process_query_results([{'exists': True}])))

    def test_format_names_from_results(self):
        db = Database()
        self.assertEqual(self.loop.run_until_complete(db.format_names_from_results(None)), [])
        self.assertEqual(self.loop.run_until_complete(db.format_names_from_results([['Name1'], ['Name2']])),
                         ['Name1', 'Name2'])

    def test_env_variables(self):
        result = subprocess.run(['docker', 'exec', 'bellbot_container', 'env'], capture_output=True, text=True)
        env_variables = result.stdout.split('\n')

        desired_variables = ['DB_HOST', 'DB_USER', 'DB_PORT', 'DB_PASSWORD',
                             'DB_DATABASE']
        for var in desired_variables:
            self.assertTrue(any(var in line for line in env_variables),
                            f'Expected {var} to exist in container environment, but it didn\'t.')


if __name__ == "__main__":
    unittest.main()
