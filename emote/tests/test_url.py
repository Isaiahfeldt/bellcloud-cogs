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

import unittest
from unittest.mock import patch, Mock

from emote.utils.url import is_url_reachable, is_media_size_valid, is_url_blacklisted


class ConditionTests(unittest.TestCase):

    @patch('emote.utils.url.head_request')
    def test_is_url_reachable_true(self, mock_head_request):
        mock_head_request.return_value.status_code = 200
        url = "https://example.com"
        result = is_url_reachable(url)
        self.assertTrue(result)

    def test_is_url_reachable_str(self):
        url = "Asd"
        result = is_url_reachable(url)
        self.assertFalse(result)

    @patch('emote.utils.url.head_request')
    def test_is_url_reachable_false(self, mock_head_request):
        mock_head_request.return_value.status_code = 404
        url = "https://example.com"
        result = is_url_reachable(url)
        self.assertFalse(result)

    @patch('emote.utils.url.head_request')
    def test_is_url_reachable_none(self, mock_head_request):
        mock_head_request.return_value = None
        url = "https://example.com"
        result = is_url_reachable(url)
        self.assertFalse(result)

    @patch('emote.utils.url.head_request')  # replace with the correct module
    def test_check_image_size_with_large_image(self, mock_head_request):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "10000000"}  # Simulate an image of size 10,000,000 bytes.
        mock_head_request.return_value = mock_response
        url = "https://example.com/large_image.jpg"
        max_size = 2000000  # 2,000,000 bytes.

        result = is_media_size_valid(url, max_size)

        self.assertEqual(result, False)

    @patch('emote.utils.url.head_request')  # replace with the correct module
    def test_check_image_size_with_small_image(self, mock_head_request):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "100000"}  # Simulate an image of size 100,000 bytes.
        mock_head_request.return_value = mock_response
        url = "https://example.com/small_image.jpg"
        max_size = 2000000  # 2,000,000 bytes.

        result = is_media_size_valid(url, max_size)

        self.assertEqual(result, True)

    @patch('emote.utils.url.head_request')  # replace with the correct module
    def test_check_image_size_with_missing_content_length(self, mock_head_request):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_head_request.return_value = mock_response
        url = "https://example.com/image.jpg"
        max_size = 2000000  # 2,000,000 bytes.

        result = is_media_size_valid(url, max_size)

        self.assertEqual(result, False)

    def test_url_blacklisted(self):
        # Test if a non-blacklisted URL returns False
        url = "https://www.google.com"
        result = is_url_blacklisted(url)
        self.assertEqual(result, False, "Expected False, but received True.")

        # Test if a blacklisted URL returns True
        blacklisted_url = "https://media.bellbot.xyz/"
        allowed_url = "https://static.wikia.nocookie.net/goanimate-news/images/9/93/Hatsune_Miku.png"

        self.assertEqual(is_url_blacklisted(blacklisted_url), True, "Expected website to be blacklisted.")
        self.assertFalse(is_url_blacklisted(allowed_url), False)

        # Test if a blacklisted URL that is a part of another URL returns True
        url_part_blacklisted = "https://media.bellbot.xyz/something_else"
        result_part_blacklisted = is_url_blacklisted(url_part_blacklisted)
        self.assertEqual(result_part_blacklisted, True, "Expected True, but received False.")


if __name__ == "__main__":
    unittest.main()
