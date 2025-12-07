import asyncio
import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parent.parent / "rules" / "three_word.py"
spec = importlib.util.spec_from_file_location("three_word", MODULE_PATH)
three_word = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(three_word)

extract_words_only = three_word.extract_words_only
three_word_rule = three_word.three_word_rule


class ThreeWordRuleTests(unittest.TestCase):
    def test_extract_words_includes_hyphenated_contractions(self):
        text = "Gen-three's rule works"
        words = extract_words_only(text)

        self.assertEqual(words, ["gen-three's", "rule", "works"])

    def test_hyphenated_contraction_counts_as_hyphenated_word(self):
        message = "gen-three's well-known rule"
        result = asyncio.run(three_word_rule(message))

        self.assertFalse(result["passes"])
        self.assertIn("Hyphenated words must be separated", result["reason"])

    def test_decimal_number_counts_as_single_number(self):
        message = "took 3.5 hours"
        result = asyncio.run(three_word_rule(message))

        self.assertTrue(result["passes"])
        self.assertEqual(result["analysis"]["number_count"], 1)


if __name__ == "__main__":
    unittest.main()
