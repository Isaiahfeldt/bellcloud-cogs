#  Copyright (c) 2023-2024, Isaiah Feldt
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

import os
import unittest


def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    test_dir = os.path.abspath('../tests')
    for test_file in os.listdir(test_dir):
        if test_file.startswith('test_') and test_file.endswith('.py'):
            print(f"\nRunning tests from {test_file}")
            tests = loader.discover(start_dir=test_dir, pattern=test_file)
            suite.addTests(tests)
    return suite


if __name__ == "__main__":
    # This allows you to run the file directly, and unittest will use the
    # load_tests function to load the tests.
    unittest.main()
