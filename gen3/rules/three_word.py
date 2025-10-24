"""
Three-Word Rule: messages must contain exactly three words.

Notes:
- Emojis, emoticons, symbols, punctuation, and numbers do not count toward the word count.
- Additionally allowed: exactly two words plus one standalone number (e.g., "i ate 6").
- Accepts alphabetic words, contractions, alphanumeric, and hyphenated words as single tokens.
- Multi-hyphenated words (two or more hyphens in one word) are not allowed.
- Multiple single-hyphenated words are allowed only if not consecutive (must be separated by a non-hyphenated word).
"""

from __future__ import annotations

import re

import unicodedata


def _remove_discord_emojis(text: str) -> str:
    """
    Remove Discord emoji markup from text prior to word counting.

    Handles:
    - :shortcode: style (e.g., :smile:)
    - Custom emoji markup like:
        <:name:id>
        <a:name:id> (animated)
        <a id> (name omitted form seen in some API contexts)
    - Collapses leftover whitespace after removals
    """
    try:
        # Remove :shortcode: style (letters, numbers, and underscores inside colons)
        text = re.sub(r":[A-Za-z0-9_]+:", " ", text)

        # Remove custom emoji markup, including the <a 1234567890> variant
        text = re.sub(r"<a?:[A-Za-z0-9_]+:\d+>", " ", text)  # <:name:id> and <a:name:id>
        text = re.sub(r"<a\s+\d+>", " ", text)  # <a 1234567890>
        text = re.sub(r"<:\s*\d+>", " ", text)  # (rare malformed <: 1234> edge case)

        # Remove mentions and channels (optional cleanup)
        text = re.sub(r"<[@#&!]\d+>", " ", text)

        # Collapse extra whitespace introduced by removals
        text = re.sub(r"\s+", " ", text).strip()

        return text
    except Exception:
        # On any regex failure, return original text unchanged
        return text


def extract_words_only(text: str) -> list[str]:
    """
    Extract words from text, including:
    - Alphabetic words (hello, world)
    - Alphanumeric words (Word1, test123)
    - Contractions (can't, won't, don't)
    - Hyphenated words (well-known, twenty-one) as single units

    Excluding:
    - Emojis and emoticons
    - Pure symbols and punctuation
    - Standalone numbers
    """
    # Preprocess to remove Discord emoji markup like :name: or <:name:id>
    text = _remove_discord_emojis(text)

    # Regex for hyphenated words, contractions, and alphanumeric words
    words = re.findall(
        r"\b[a-zA-Z]+-[a-zA-Z]+(?:-[a-zA-Z]+)*\b|\b[a-zA-Z]+(?:'[a-zA-Z]+)*(?:[a-zA-Z0-9]*)*\b|\b[a-zA-Z0-9]+\b",
        text,
    )

    filtered_words: list[str] = []
    for word in words:
        if any(char.isalpha() for char in word):
            filtered_words.append(word.lower())

    return filtered_words


def count_hyphenated_words(text: str) -> int:
    """Count the number of hyphenated words in the text."""
    hyphenated_pattern = r"\b[a-zA-Z]+-[a-zA-Z]+(?:-[a-zA-Z]+)*\b"
    hyphenated_words = re.findall(hyphenated_pattern, text)
    return len(hyphenated_words)


def has_multi_hyphenated_words(text: str) -> bool:
    """Return True if the text contains any multi-hyphenated words (>= 2 hyphens)."""
    hyphenated_pattern = r"\b[a-zA-Z]+-[a-zA-Z]+(?:-[a-zA-Z]+)*\b"
    hyphenated_words = re.findall(hyphenated_pattern, text)
    for word in hyphenated_words:
        if word.count("-") >= 2:
            return True
    return False


def are_hyphenated_words_properly_separated(text: str) -> bool:
    """
    Validate that hyphenated words are not consecutive. Returns False if any two
    hyphenated words appear back-to-back.
    """
    words = extract_words_only(text)
    hyphenated_pattern = r"^[a-zA-Z]+-[a-zA-Z]+(?:-[a-zA-Z]+)*$"

    for i in range(len(words) - 1):
        current_word = words[i]
        next_word = words[i + 1]
        if re.match(hyphenated_pattern, current_word, re.IGNORECASE) and re.match(
                hyphenated_pattern, next_word, re.IGNORECASE
        ):
            return False
    return True


def is_emoji_or_symbol(char: str) -> bool:
    """Heuristic: True for many emoji/symbol categories."""
    category = unicodedata.category(char)
    return category.startswith(("So", "Sm", "Sc", "Sk", "Pd", "Po", "Ps", "Pe", "Pc", "Mn", "Mc"))


def analyze_message_content(text: str) -> dict:
    """Return analysis details used by the rule for debugging and messaging."""
    # Remove Discord emoji markup so numbers inside emoji IDs don't get counted
    cleaned = _remove_discord_emojis(text)

    words = extract_words_only(cleaned)
    word_count = len(words)

    # Extract standalone number tokens (integers only for speed and clarity)
    numbers = re.findall(r"\b\d+\b", cleaned)
    number_count = len(numbers)

    all_tokens = cleaned.split()
    filtered_out: list[str] = []
    for token in all_tokens:
        token_words = re.findall(r"\b[a-zA-Z]+\b", token)
        if not token_words or not any(word.isalpha() for word in token_words):
            filtered_out.append(token)

    return {
        "word_count": word_count,
        "words": words,
        "number_count": number_count,
        "numbers": numbers,
        "filtered_out": filtered_out,
        "original": text,
    }


async def three_word_rule(content: str, current_strikes: int = 0) -> dict:
    """
    Gen3 rule function: messages must be exactly 3 words long.

    - Emojis, emoticons, symbols, punctuation, and numbers don't count towards word count.
    - Additional constraint: Multi-hyphenated words are not allowed.
    - Multiple hyphenated words allowed only if separated by non-hyphenated words.
    """
    # Handle empty or whitespace-only messages
    if not content or not content.strip():
        return {
            "passes": False,
            "reason": "Empty messages are not allowed! You need exactly 3 words.",
            "analysis": {"word_count": 0, "words": [], "filtered_out": [], "original": content},
        }

    # Multi-hyphenated words are not allowed
    if has_multi_hyphenated_words(content):
        return {
            "passes": False,
            "reason": "Multi-hyphenated words are not allowed! \nWords like 'multi-word-compound' are forbidden. Use single-hyphenated words only!",
            "analysis": {
                "word_count": 0,
                "words": [],
                "filtered_out": [],
                "original": content,
            },
        }

    # If more than one hyphenated word exists, ensure they are not consecutive
    hyphenated_count = count_hyphenated_words(content)
    if hyphenated_count > 1 and not are_hyphenated_words_properly_separated(content):
        return {
            "passes": False,
            "reason": f"Hyphenated words must be separated by non-hyphenated words!\nYou have {hyphenated_count} hyphenated words that are too close together. Place non-hyphenated words between them!",
            "analysis": {
                "word_count": 0,
                "words": [],
                "filtered_out": [],
                "original": content,
                "hyphenated_count": hyphenated_count,
            },
        }

    # Analyze the message content for word/number count
    analysis = analyze_message_content(content)
    analysis["hyphenated_count"] = hyphenated_count
    word_count = analysis["word_count"]
    number_count = analysis.get("number_count", 0)
    words = analysis["words"]

    # Passing conditions:
    # - Exactly 3 alphabetic words, or
    # - Exactly 2 alphabetic words plus exactly 1 standalone number
    two_words_one_number = (word_count == 2 and number_count == 1)
    exactly_three_words = (word_count == 3)

    if exactly_three_words or two_words_one_number:
        # Craft a friendly reason reflecting hyphenation and numbers
        if two_words_one_number:
            if hyphenated_count >= 1:
                if hyphenated_count == 1:
                    return {
                        "passes": True,
                        "reason": f"Perfect! Accepted 2 words + 1 number with 1 hyphenated word: '{' '.join(words)}'",
                        "analysis": analysis,
                    }
                else:
                    return {
                        "passes": True,
                        "reason": f"Perfect! Accepted 2 words + 1 number with {hyphenated_count} properly separated hyphenated words: '{' '.join(words)}'",
                        "analysis": analysis,
                    }
            else:
                return {
                    "passes": True,
                    "reason": f"Perfect! Accepted 2 words + 1 number: '{' '.join(words)}' + 1 number",
                    "analysis": analysis,
                }
        else:
            # exactly_three_words
            if hyphenated_count >= 1:
                if hyphenated_count == 1:
                    return {
                        "passes": True,
                        "reason": f"Perfect! Your message has exactly 3 words with 1 hyphenated word: '{' '.join(words)}'",
                        "analysis": analysis,
                    }
                else:
                    return {
                        "passes": True,
                        "reason": f"Perfect! Your message has exactly 3 words with {hyphenated_count} properly separated hyphenated words: '{' '.join(words)}'",
                        "analysis": analysis,
                    }
            else:
                return {
                    "passes": True,
                    "reason": f"Perfect! Your message has exactly 3 words: '{' '.join(words)}'",
                    "analysis": analysis,
                }

    # Failing conditions
    if word_count == 0:
        return {
            "passes": False,
            "reason": "Your message contains no valid words! You need exactly 3 words or 2 words + 1 number.",
            "analysis": analysis,
        }

    # If we have fewer than needed (and didn't match the 2 words + 1 number case)
    if word_count < 3:
        return {
            "passes": False,
            "reason": (
                f"Too few words! You have {word_count} word{'s' if word_count != 1 else ''}. "
                f"Allowed: exactly 3 words, or 2 words + 1 number."
            ),
            "analysis": analysis,
        }

    # Otherwise, too many words
    return {
        "passes": False,
        "reason": f"Too many words! You have {word_count} words but need exactly 3 (numbers don't count as words).",
        "analysis": analysis,
    }


__all__ = [
    "extract_words_only",
    "count_hyphenated_words",
    "has_multi_hyphenated_words",
    "are_hyphenated_words_properly_separated",
    "is_emoji_or_symbol",
    "analyze_message_content",
    "three_word_rule",
]
