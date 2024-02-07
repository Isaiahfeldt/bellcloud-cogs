#  Copyright (c) 2024, Isaiah Feldt
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

import asyncio
import unittest
from datetime import datetime
from unittest import mock

from emote.utils.effects import Emote
from emote.utils.effects import initialize
from emote.utils.pipeline import create_pipeline, execute_pipeline


class TestPipeline(unittest.TestCase):
    def setUp(self):
        # Set up the asyncio event loop for the tests
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

        self.emote = Emote(
            id=1,
            file_path="352972393368780810/emote.png",
            author_id=1234,
            timestamp=datetime.now(),
            original_url="https://example.com/emote.png",
            name="emote",
            guild_id=5678,
            usage_count=10,
            error=None
        )

        # Define a mock discord.Message object with required fields
        self.mock_discord_message = mock.Mock()
        self.mock_discord_message.author.guild_permissions.manage_messages = True

    def tearDown(self):
        self.loop.close()

    def test_create_pipeline(self):
        # Define a mock object to represent `self`
        mock_self = mock.Mock()

        # Instantiate an Emote object...
        test_emote = self.emote

        queued_effects = {'flip': {'func': mock.Mock(), 'perm': 'everyone', 'priority': 10}}

        # Run the function to test it
        result = self.loop.run_until_complete(
            create_pipeline(mock_self, self.mock_discord_message, test_emote, queued_effects))

        # Check if the function returned a correct pipeline and an empty list of issues
        self.assertIsInstance(result[0], list)
        self.assertIsInstance(result[1], list)
        self.assertEqual(len(result[1]), 0)

    def test_execute_pipeline(self):
        # Define a pipeline of functions to execute
        pipeline = [(lambda _: initialize(self.emote))]

        # Run the function to test it
        result = self.loop.run_until_complete(execute_pipeline(pipeline))

        # Check if the function returned an Emote and a list with one dictionary concerning elapsed time
        self.assertIsInstance(result, Emote)
        # self.assertIsInstance(result, list)
        # self.assertEqual(len(result), 1)


if __name__ == '__main__':
    unittest.main()
