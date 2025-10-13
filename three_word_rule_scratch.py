#!/usr/bin/env python3

"""
Scratch function for gen3 gimmick: messages can only be exactly 3 words long.
Emojis, emoticons, symbols, and punctuation don't count towards word count.

This function can potentially be integrated into the gen3 cog as a new yearly gimmick.
"""

import re

import unicodedata


def extract_words_only(text: str) -> list[str]:
    """
    Extract words from text, including:
    - Alphabetic words (hello, world)
    - Alphanumeric words (Word1, test123)  
    - Contractions (can't, won't, don't)
    
    Excluding:
    - Emojis and emoticons 
    - Pure symbols and punctuation
    - Standalone numbers
    
    Args:
        text: The input text to extract words from
        
    Returns:
        list: List of valid words
    """
    # Use regex to find words including contractions and alphanumeric combinations
    # This pattern includes letters, numbers, and apostrophes within words
    words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)*(?:[a-zA-Z0-9]*)*\b|\b[a-zA-Z0-9]+\b", text)

    # Additional filtering to handle edge cases
    filtered_words = []
    for word in words:
        # Accept words that contain at least one letter
        # This allows contractions (can't) and alphanumeric (Word1) but excludes pure numbers
        if any(char.isalpha() for char in word):
            filtered_words.append(word.lower())

    return filtered_words


def count_hyphenated_words(text: str) -> int:
    """
    Count the number of hyphenated words in the text.
    A hyphenated word is defined as alphabetic characters separated by hyphens.
    
    Args:
        text: The input text to analyze
        
    Returns:
        int: Number of hyphenated words found
    """
    # Find all hyphenated words using regex
    # Pattern matches sequences like "hello-world", "twenty-one", "well-known-fact" 
    hyphenated_pattern = r'\b[a-zA-Z]+-[a-zA-Z]+(?:-[a-zA-Z]+)*\b'
    hyphenated_words = re.findall(hyphenated_pattern, text)

    return len(hyphenated_words)


def is_emoji_or_symbol(char: str) -> bool:
    """
    Check if a character is an emoji, symbol, or special character.
    
    Args:
        char: Single character to check
        
    Returns:
        bool: True if character is emoji/symbol, False otherwise
    """
    # Unicode categories for emojis and symbols
    category = unicodedata.category(char)
    return category.startswith(('So', 'Sm', 'Sc', 'Sk', 'Pd', 'Po', 'Ps', 'Pe', 'Pc', 'Mn', 'Mc'))


def analyze_message_content(text: str) -> dict:
    """
    Analyze message content to provide detailed breakdown for debugging.
    
    Args:
        text: The message content to analyze
        
    Returns:
        dict: Analysis breakdown with word count, filtered content, etc.
    """
    # Extract only alphabetic words
    words = extract_words_only(text)
    word_count = len(words)

    # Show what was filtered out for debugging
    all_tokens = text.split()
    filtered_out = []

    for token in all_tokens:
        # Check if token contains any alphabetic words
        token_words = re.findall(r'\b[a-zA-Z]+\b', token)
        if not token_words or not any(word.isalpha() for word in token_words):
            filtered_out.append(token)

    return {
        "word_count": word_count,
        "words": words,
        "filtered_out": filtered_out,
        "original": text
    }


async def three_word_rule(content: str, current_strikes: int = 0) -> dict:
    """
    Gen3 rule function: messages must be exactly 3 words long.
    
    Emojis, emoticons, symbols, punctuation, and numbers don't count towards word count.
    Only alphabetic sequences count as "words".
    
    Additional constraint: Only one hyphenated word is allowed per message.
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has (unused for this rule)
    
    Returns:
        dict: {"passes": bool, "reason": str, "analysis": dict}
    """
    # Handle empty or whitespace-only messages
    if not content or not content.strip():
        return {
            "passes": False,
            "reason": "Empty messages are not allowed! You need exactly 3 words. 📝❌",
            "analysis": {"word_count": 0, "words": [], "filtered_out": [], "original": content}
        }

    # Check for hyphenated word constraint FIRST
    hyphenated_count = count_hyphenated_words(content)
    if hyphenated_count > 1:
        return {
            "passes": False,
            "reason": f"Too many hyphenated words! You have {hyphenated_count} hyphenated words but only 1 is allowed. "
                      f"Remove {hyphenated_count - 1} hyphenated word{'s' if hyphenated_count > 2 else ''}! 🔗❌",
            "analysis": {
                "word_count": 0,
                "words": [],
                "filtered_out": [],
                "original": content,
                "hyphenated_count": hyphenated_count
            }
        }

    # Analyze the message content for word count
    analysis = analyze_message_content(content)
    analysis["hyphenated_count"] = hyphenated_count  # Add hyphenated count to analysis
    word_count = analysis["word_count"]
    words = analysis["words"]

    # Check if exactly 3 words
    if word_count == 3:
        if hyphenated_count == 1:
            return {
                "passes": True,
                "reason": f"Perfect! Your message has exactly 3 words with 1 hyphenated word allowed: '{' '.join(words)}' ✅🎯🔗",
                "analysis": analysis
            }
        else:
            return {
                "passes": True,
                "reason": f"Perfect! Your message has exactly 3 words: '{' '.join(words)}' ✅🎯",
                "analysis": analysis
            }
    elif word_count == 0:
        return {
            "passes": False,
            "reason": "Your message contains no valid words! You need exactly 3 alphabetic words. 🚫📝",
            "analysis": analysis
        }
    elif word_count < 3:
        missing = 3 - word_count
        return {
            "passes": False,
            "reason": f"Too few words! You have {word_count} word{'s' if word_count != 1 else ''} "
                      f"but need exactly 3. Add {missing} more word{'s' if missing != 1 else ''}! ⬆️📝",
            "analysis": analysis
        }
    else:  # word_count > 3
        excess = word_count - 3
        return {
            "passes": False,
            "reason": f"Too many words! You have {word_count} words but need exactly 3. "
                      f"Remove {excess} word{'s' if excess != 1 else ''}! ⬇️✂️",
            "analysis": analysis
        }


# Test function to demonstrate edge cases with expected outcomes
def test_three_word_rule():
    """
    Test function to validate the 3-word rule with expected outcomes.
    Each test case includes whether it should pass or fail for validation.
    """

    # Test cases with expected outcomes: (message, should_pass, description)
    test_cases = [
        # Valid cases (exactly 3 words) - should all PASS
        ("hello world today", True, "Basic 3 words"),
        ("I love coding", True, "Simple 3 words"),
        ("The quick brown", True, "3 words with articles"),
        ("Hello 😀 world 🎉 today! 🚀", True, "3 words with emojis"),
        ("Test... message... here!!!", True, "3 words with punctuation"),
        ("Word1 word2 word3", True, "Alphanumeric words"),
        ("HELLO world Today", True, "Mixed case"),
        ("Can't won't don't", True, "3 contractions"),

        # Invalid cases (too few words) - should all FAIL
        ("", False, "Empty message"),
        ("   ", False, "Whitespace only"),
        ("hello", False, "1 word only"),
        ("hello world", False, "2 words only"),
        ("😀😀😀", False, "Only emojis"),
        ("123 456 789", False, "Only numbers"),
        ("!@# $%^ &*()", False, "Only symbols"),
        ("hello 😀😀😀", False, "1 word + emojis"),
        ("hello world 😀😀😀", False, "2 words + emojis"),

        # Invalid cases (too many words) - should all FAIL
        ("hello world today everyone", False, "4 words"),
        ("I really love coding so much", False, "6 words"),
        ("This is a test message with many words", False, "8 words"),
        ("Hello 😀 world 🎉 today 🚀 everyone 🎈 here!", False, "5 words + emojis"),

        # Edge cases - expected outcomes based on word count
        ("hello-world test case", True, "Hyphenated counts as 3 separate words, 1 hyphenated word allowed"),
        ("can't won't shouldn't", True, "3 contractions"),
        ("test123 hello456 world789", True, "Mixed alphanumeric - 3 words"),
        ("héllo wørld tødäy", False, "Unicode characters may not be recognized"),
        ("ALLCAPS lowercase MiXeD", True, "Mixed case - 3 words"),
        ("a i o", True, "Very short words - still 3 words"),
        ("supercalifragilisticexpialidocious hello world", True, "1 very long word + 2 others = 3"),

        # Hyphenated word constraint tests
        ("twenty-one cats here", True, "3 words with 1 hyphenated word (allowed)"),
        ("well-known public figure", True, "3 words with 1 hyphenated word (allowed)"),
        ("hello-world good-bye test", False, "5 words with 2 hyphenated words (not allowed)"),
        ("twenty-one thirty-two cats", False, "4 words with 2 hyphenated words (not allowed)"),
        ("well-known good-looking nice-person", False, "6 words with 3 hyphenated words (not allowed)"),
        ("multi-word-compound test case", True, "3 words with 1 multi-hyphenated word (allowed)"),
        ("first-second-third fourth-fifth sixth", False, "6 words with 2 multi-hyphenated words (not allowed)"),
    ]

    print("=== Three Word Rule Test Cases with Expected Outcomes ===\n")

    correct_predictions = 0
    total_tests = len(test_cases)

    for i, (test_message, expected_pass, description) in enumerate(test_cases, 1):
        print(f"Test {i}: '{test_message}'")
        print(f"  Description: {description}")
        print(f"  Expected: {'PASS' if expected_pass else 'FAIL'}")

        # Run the rule function (simulate async)
        import asyncio
        result = asyncio.run(three_word_rule(test_message))

        # Check if actual result matches expected outcome
        actual_pass = result["passes"]
        is_correct = actual_pass == expected_pass

        if is_correct:
            correct_predictions += 1
            validation_status = "✅ CORRECT"
        else:
            validation_status = "❌ INCORRECT"

        # Display results
        actual_result = "✅ PASS" if actual_pass else "❌ FAIL"
        print(f"  Actual: {actual_result}")
        print(f"  Validation: {validation_status}")
        print(f"  Reason: {result['reason']}")
        print(f"  Analysis: {result['analysis']['word_count']} words found: {result['analysis']['words']}")
        if result['analysis']['filtered_out']:
            print(f"  Filtered out: {result['analysis']['filtered_out']}")
        print()

    # Display summary
    print("=" * 60)
    print(f"VALIDATION SUMMARY:")
    print(f"  Total tests: {total_tests}")
    print(f"  Correct predictions: {correct_predictions}")
    print(f"  Incorrect predictions: {total_tests - correct_predictions}")
    print(f"  Accuracy: {(correct_predictions / total_tests * 100):.1f}%")

    if correct_predictions == total_tests:
        print(f"  🎉 ALL TESTS PASSED VALIDATION! The rule is working as expected.")
    else:
        print(f"  ⚠️  Some tests failed validation. Review incorrect predictions above.")
    print("=" * 60)


# Integration example for gen3 cog
def integration_example():
    """
    Show how this function could be integrated into the gen3 cog system.
    """

    example_code = '''
# To integrate this into gen3 cog, simply update the check_gen3_rules function:

async def check_gen3_rules(content: str, current_strikes: int = 0) -> dict:
    """
    Flexible rule checker for gen3 events. 
    This function can be easily modified to use different rule functions for different events.
    
    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has
    
    Returns:
        dict: {"passes": bool, "reason": str, "analysis": dict}
    """
    # For the 3-word gimmick year with hyphenated word constraint, use the three_word_rule
    return await three_word_rule(content, current_strikes)
    
    # For other years, swap in different rule functions:
    # return await word_chain_rule(content, current_strikes)  # Previous year
    # return await apple_orange_rule(content, current_strikes)  # Demo rule
    # return await custom_rule_2026(content, current_strikes)  # Future rule

# Three Word Rule Features:
# - Messages must be exactly 3 words long
# - Emojis, symbols, and punctuation don't count toward word count
# - Contractions (can't, won't) count as single words
# - Alphanumeric words (Word1, test123) are allowed
# - Maximum of 1 hyphenated word per message allowed
# - Hyphenated words still count as separate words for the 3-word count
#   (e.g., "hello-world test" = 3 words: hello, world, test)
'''

    print("=== Gen3 Cog Integration Example ===")
    print(example_code)


if __name__ == "__main__":
    # Run tests
    test_three_word_rule()

    # Show integration example
    integration_example()
