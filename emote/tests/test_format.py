import unittest
from types import SimpleNamespace

from emote.utils.format import clean_emote_name, extract_emote_details


class FormatTests(unittest.TestCase):
    def test_clean_emote_name_trims_whitespace(self):
        self.assertEqual(clean_emote_name(": nick:"), "nick")

    def test_extract_emote_details_trims_whitespace(self):
        message = SimpleNamespace(content=": nick:")
        name, effects = extract_emote_details(message)
        self.assertEqual(name, "nick")
        self.assertEqual(effects, [])


if __name__ == "__main__":
    unittest.main()
