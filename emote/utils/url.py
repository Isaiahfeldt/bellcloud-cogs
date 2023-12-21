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
import re
from urllib.parse import urlparse

import requests


def head_request(url):
    """
    Sends a HEAD request to the specified URL.

    :param url: The URL string for the HEAD request.
    :type url: str
    :return: The response object of the HEAD request if successful, else None if a connection error occurs.
    :raises ValueError: If the provided URL is invalid.
    """
    # Check if URL is valid
    parsed_url = urlparse(url)
    if not all([parsed_url.scheme, parsed_url.netloc]):
        raise ValueError("Invalid URL")

    try:
        return requests.head(url)
    except requests.ConnectionError:
        return None


def is_url_reachable(url: str) -> bool:
    """
    :param url: The URL to check if it is reachable.
    :return: True if the URL is reachable, False otherwise.
    :rtype: bool
    """
    try:
        response = head_request(url)
        if response is None:
            return False
        return response.status_code == 200
    except ValueError:
        return False


def is_media_format_valid(url: str, valid_formats: list):
    """
    :param url: The URL string to be checked.
    :param valid_formats: List of allowed file formats
    :return: A tuple (bool, str) indicating whether the URL has an allowed format and the file extension if it does.
    :rtype: tuple (bool, str)
    """
    response = head_request(url)
    if response is None or response.status_code != 200:
        return False, None, 'URL was not reachable'
    content_type = response.headers.get("content-type")
    if content_type is None:
        return False, None,
    file_extension = content_type.split("/")[-1].lower()
    if file_extension in valid_formats:
        return True, file_extension
    else:
        return False, file_extension


def is_media_size_valid(url: str, max_size: int) -> bool:
    """
    :param url: The URL string of the image to be checked.
    :param max_size: The maximum size for the image (in bytes).
    :return: True if the image size is less than or equal to the max_size, False otherwise.
    :rtype: bool
    """
    response = head_request(url)
    if response is None or response.status_code != 200:
        return False

    content_length = response.headers.get("content-length")
    if content_length is None or int(content_length) > max_size:
        return False

    return True


def is_url_blacklisted(url: str) -> tuple:
    """
    :param url: The URL to check if it is blacklisted.
    :return: Tuple where first element is a boolean indicating if the URL is blacklisted and the second element is the matching string in the URL. If no match was found, the second element is None.
    :rtype: tuple
    """
    blacklisted_websites = ["https://media.bellbot.xyz"]
    for website in blacklisted_websites:
        match = re.search(website, url)
        if match:
            return True, match.group()
    return False, None
