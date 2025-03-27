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

from emote.tests import test_database, test_url

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # add tests to the test suite
    suite.addTests(loader.loadTestsFromModule(test_database))
    suite.addTests(loader.loadTestsFromModule(test_url))

    # run the suite
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
