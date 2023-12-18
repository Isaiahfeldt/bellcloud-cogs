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

import requests


class URLUtils:
    def __init__(self, allowed_formats):
        self.allowed_formats = allowed_formats

    def head_request(self, url_string):
        try:
            return requests.head(url_string)
        except requests.ConnectionError:
            return None

    def is_url_reachable(self, url_string):
        response = self.head_request(url_string)
        return response is not None and response.status_code == 200

    def is_url_allowed_format(self, url_string):
        response = self.head_request(url_string)
        if response is None or response.status_code != 200:
            return False, None
        content_type = response.headers.get("content-type")
        if content_type is None:
            return False, None
        file_extension = content_type.split("/")[-1].lower()
        if file_extension in self.allowed_formats:
            return True, file_extension
        else:
            return False, file_extension
