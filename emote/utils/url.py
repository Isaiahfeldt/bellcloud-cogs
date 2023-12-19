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
        return "Error: Invalid URL"

    try:
        return requests.head(url)
    except requests.ConnectionError:
        return None


def is_url_reachable(url: str) -> str:
    """
    @param url: The URL string to check if it is reachable.
    @return: True if the URL is reachable and returns a status code of 200, False otherwise.
    """
    response = head_request(url)
    return response is not None and response.status_code == 200


def is_url_allowed_format(url: str, allowed_formats):
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
