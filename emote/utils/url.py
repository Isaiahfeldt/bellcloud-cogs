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
from urllib.parse import urlparse

import requests


def head_request(url):
    """
    @param url: The URL string for the HEAD request.
    @return: The response object of the HEAD request if successful, error message or None.
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
    @param url: The URL string to check if it is reachable.
    @return: True if the URL is reachable and returns a status code of 200, False otherwise.
    """
    try:
        response = head_request(url)
        if response is None:
            return False
        return response.status_code == 200
    except ValueError:
        return False


def is_media_format_valid(url: str, allowed_formats):
    """
    @param url: The URL string to be checked.
    @param allowed_formats:
    @return: A tuple (bool, str) indicating whether the URL has an allowed format and the file extension if it does.
    """
    response = head_request(url)
    if response is None or response.status_code != 200:
        return False, None, 'URL was not reachable'
    content_type = response.headers.get("content-type")
    if content_type is None:
        return False, None,
    file_extension = content_type.split("/")[-1].lower()
    if file_extension in allowed_formats:
        return True, file_extension
    else:
        return False, file_extension


def is_media_size_valid(url: str, max_size: int) -> bool:
    """
    @param url: The URL string of the image to be checked.
    @param max_size: The maximum size for the image (in bytes).
    @return: True if the image size is less than or equal to the max_size, False otherwise.
    """
    response = head_request(url)
    if response is None or response.status_code != 200:
        return False

    content_length = response.headers.get("content-length")
    if content_length is None or int(content_length) > max_size:
        return False

    return True


def is_url_blacklisted(url: str) -> bool:
    blacklisted_websites = ["https://media.bellbot.xyz"]

    for website in blacklisted_websites:
        if website in url:
            return True
    return False
