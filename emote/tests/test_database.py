# File: emote/tests/test_database.py

import unittest
from unittest import mock

from emote.utils.database import Database


class FakePool:
    async def acquire(self):
        fake_conn = mock.AsyncMock()

        class FakeContextManager:
            async def __aenter__(self):
                return fake_conn

            async def __aexit__(self, exc_type, exc, tb):
                pass

        return FakeContextManager()

    async def close(self):
        pass

    def __await__(self):
        async def inner():
            return self

        return inner().__await__()


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.database = Database()
        self.database.CONNECTION_PARAMS = {
            "user": "test_user",
            "password": "test_password",
            "database": "test_database",
            "host": "localhost",
        }
        # Optionally, initialize pool or other things needed for real tests.
        # await self.database.init_pool()
        # Set a test server id for use in the real integration tests
        self.test_server_id = 123456789

    async def asyncTearDown(self):
        if getattr(self.database, "pool", None) is not None:
            await self.database.pool.close()

    @mock.patch("asyncpg.create_pool")
    async def test_init_pool(self, mock_create_pool):
        fake_pool = FakePool()
        mock_create_pool.return_value = fake_pool
        with mock.patch.object(self.database, "init_schema", new=mock.AsyncMock()) as mock_init_schema:
            await self.database.init_pool()
            mock_create_pool.assert_called_once_with(
                **self.database.CONNECTION_PARAMS, min_size=1, max_size=10
            )
            mock_init_schema.assert_called_once()

    async def test_emote_exists_in_database_real(self):
        # This test will run against the actual database.
        # Make sure the test database contains the emotes "isaiah" and "miku4" beforehand.
        EMOTE_NAMES = ["isaiah", "miku4"]
        # Optionally, initialize the pool if needed for this test
        await self.database.init_pool()
        for emote_name in EMOTE_NAMES:
            result = await self.database.check_emote_exists(emote_name, self.test_server_id)
            self.assertTrue(result, f"Expected emote {emote_name} to exist in database, but it didn't.")


if __name__ == "__main__":
    unittest.main()
