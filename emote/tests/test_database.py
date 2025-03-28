# File: emote/tests/test_database.py
#  Copyright (c) 2023-2024, Isaiah Feldt
#
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU Affero General Public License (AGPL) as published by
#     - the Free Software Foundation, either version 3 of this License,
#     - or (at your option) any later version.
#
#     - This program is distributed in the hope that it will be useful,
#     - but without any warranty, without even the implied warranty of
#     - merchantability or fitness for a particular purpose.
#     - See the GNU Affero General Public License for more details.
#
#     - You should have received a copy of the GNU Affero General Public License
#     - If not, please see <https://www.gnu.org/licenses/#GPL>.

import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from emote.utils.database import Database


class TestDatabaseMethods(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        # Use a dummy server id for tests that require it.
        self.test_server_id = "server1"

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
            result = self.loop.run_until_complete(db.check_emote_exists(emote_name, self.test_server_id))
            self.assertTrue(result, f"Expected emote {emote_name} to exist in database, but it didn't.")

    def test_get_emote_real(self):
        emote_name = "miku4"
        db = Database()
        result = self.loop.run_until_complete(db.get_emote(emote_name, self.test_server_id))
        # Further assertions can be added here based on expected result.

    @patch("asyncpg.connect")
    def test_emote_exists_in_database_mock(self, mock_connect):
        conn = AsyncMock()
        conn.fetch = AsyncMock()
        conn.close = AsyncMock()
        mock_connect.return_value = conn

        db = Database()
        sample_emote_name = "emote1"
        self.loop.run_until_complete(db.check_emote_exists(sample_emote_name, self.test_server_id))
        # Verify that the query was called with server_id parameter.
        query = "SELECT EXISTS (SELECT 1 FROM emote.media WHERE emote_name = $1 AND server_id = $2)"
        conn.fetch.assert_called_once_with(query, sample_emote_name, self.test_server_id)
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


if __name__ == "__main__":
    unittest.main()
