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

# test_database.py

import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from emote.utils.database import Database, process_query_results


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
    def test_execute_query(self, mock_connect):
        conn = MagicMock()
        conn.fetch = AsyncMock()
        conn.close = AsyncMock()
        mock_connect.return_value = conn

        db = Database()
        sample_query = "SELECT * FROM table;"
        self.loop.run_until_complete(db.execute_query(sample_query))
        conn.fetch.assert_called_once_with(sample_query)
        conn.close.assert_called_once()

    def test_emote_exists_in_database_real(self):
        EMOTE_NAMES = ["isaiah", "miku4"]  # replace with your emote names
        db = Database()
        for emote_name in EMOTE_NAMES:
            result = self.loop.run_until_complete(db.emote_exists_in_database(emote_name))
            self.assertTrue(result, f"Expected emote {emote_name} to exist in database, but it didn't.")

    @patch("asyncpg.connect")
    def test_emote_exists_in_database_mock(self, mock_connect):
        conn = AsyncMock()
        conn.fetch = AsyncMock()
        conn.close = AsyncMock()
        mock_connect.return_value = conn

        db = Database()
        sample_emote_name = "emote1"
        self.loop.run_until_complete(db.emote_exists_in_database(sample_emote_name))
        conn.fetch.assert_called_once()
        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1)"
        conn.fetch.assert_called_once_with(query, sample_emote_name)
        conn.close.assert_called_once()

    def test_process_query_results(self):
        self.assertFalse(self.loop.run_until_complete(process_query_results(None)))
        self.assertFalse(self.loop.run_until_complete(process_query_results([])))
        self.assertTrue(self.loop.run_until_complete(process_query_results([{'exists': True}])))

    def test_get_names_from_results(self):
        db = Database()
        self.assertEqual(self.loop.run_until_complete(db.get_names_from_results(None)), [])
        self.assertEqual(self.loop.run_until_complete(db.get_names_from_results([['Name1'], ['Name2']])),
                         ['Name1', 'Name2'])


if __name__ == "__main__":
    unittest.main()
