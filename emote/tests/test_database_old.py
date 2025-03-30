import asyncio
import unittest
from unittest.mock import patch, AsyncMock

from emote.utils.database import Database


# Helper async context manager class
class AsyncContextManager:
    async def __aenter__(self):
        # Return a mock connection object (could be AsyncMock or any other mock)
        return AsyncMock()

    async def __aexit__(self, exc_type, exc_val, tb):
        pass


class TestDatabaseMethods(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        # Use a dummy server id for tests that require it.
        self.test_server_id = "server1"

    def tearDown(self):
        self.loop.close()

    @patch("asyncpg.create_pool", new_callable=AsyncMock)
    def test_init_pool(self, mock_create_pool):
        # Create a mock connection pool object
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        # Configure the acquire() method to return an async context manager
        mock_pool.acquire.return_value = AsyncContextManager()

        db = Database()

        # Run the init_pool coroutine, which calls init_schema, which in turn uses pool.acquire() in an async with.
        self.loop.run_until_complete(db.init_pool())

        # Verify that asyncpg.create_pool was called once with the expected parameters
        mock_create_pool.assert_called_once_with(**db.CONNECTION_PARAMS)

        # Check that the pool was set correctly in the Database instance
        self.assertEqual(db.pool, mock_pool)

    @patch("asyncpg.connect")
    def test_fetch_query(self, mock_connect):
        conn = AsyncMock()
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
