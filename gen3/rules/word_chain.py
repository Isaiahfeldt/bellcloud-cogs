"""
Word chain rule implementation and helpers.

This was originally embedded in the slash commands module but has been
relocated so rules can be swapped in and out more easily.
"""

from __future__ import annotations

import random
import re
from typing import Any

# Common words to exclude from selection
EXCLUDED_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he", "in", "is", "it",
    "its", "of", "on", "that", "the", "to", "was", "will", "with", "you", "your", "i", "me", "my",
    "we", "us", "our", "they", "them", "their", "this", "these", "those", "than", "then", "there",
    "here", "where", "when", "how", "what", "who", "why", "can", "could", "should", "would", "have",
    "had", "do", "does", "did", "get", "got", "just", "now", "so", "very", "much", "more", "most",
    "some", "any", "no", "not", "up", "out", "if", "about", "into", "over", "after"
}

# Base digit emojis for dynamic number generation
DIGIT_EMOJIS = {
    '0': "0️⃣", '1': "1️⃣", '2': "2️⃣", '3': "3️⃣", '4': "4️⃣",
    '5': "5️⃣", '6': "6️⃣", '7': "7️⃣", '8': "8️⃣", '9': "9️⃣"
}


def get_position_emoji(position: int) -> str:
    """
    Generate emoji representation for any position number dynamically.

    Args:
        position: The position number to convert to emoji

    Returns:
        str: Emoji representation of the position number
    """
    if position == 10:
        return "🔟"  # Special case for 10

    # Convert position to string and map each digit to its emoji
    position_str = str(position)
    emoji_parts = [DIGIT_EMOJIS[digit] for digit in position_str]

    return ''.join(emoji_parts)


# Provide a legacy/static mapping for tests and convenience (1..20)
POSITION_EMOJIS = {i: get_position_emoji(i) for i in range(1, 21)}

# Word chain tracking - global state for current required word
current_required_word: str | None = None


def extract_words(text: str) -> list[str]:
    """
    Extract meaningful words from text, excluding articles, prepositions, and common words.

    Args:
        text: The input text to extract words from

    Returns:
        list: List of meaningful words in lowercase
    """
    # Remove punctuation and split into words
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    # Filter out excluded words and words shorter than 3 characters
    meaningful_words = [word for word in words if word not in EXCLUDED_WORDS and len(word) >= 3]

    return meaningful_words


async def word_chain_rule(content: str, current_strikes: int = 0) -> dict[str, Any]:
    """
    Word chain rule function for gen3 events.

    Args:
        content: The message content to analyze
        current_strikes: Current number of strikes the user has

    Returns:
        dict: {"passes": bool, "reason": str, "selected_word": str|None, "word_position": int|None}
    """
    global current_required_word

    # If no required word is set, this message passes and we select a new word
    if current_required_word is None:
        meaningful_words = extract_words(content)

        if meaningful_words:
            # Select a random word from the meaningful words
            selected_word = random.choice(meaningful_words)

            # Find the position of this word in the original text
            content_words = re.findall(r'\b[a-zA-Z]+\b', content.lower())
            word_position = content_words.index(selected_word) + 1  # 1-indexed

            current_required_word = selected_word

            return {
                "passes": True,
                "reason": f"Message accepted! Next person must include the word '{selected_word}'",
                "selected_word": selected_word,
                "word_position": word_position
            }
        else:
            return {
                "passes": True,
                "reason": "No meaningful words found to select. Message accepted!",
                "selected_word": None,
                "word_position": None
            }

    # Check if the message contains the required word
    content_lower = content.lower()
    if current_required_word in content_lower:
        # Message passes, now select a new word from this message
        meaningful_words = extract_words(content)

        if meaningful_words:
            selected_word = random.choice(meaningful_words)
            content_words = re.findall(r'\b[a-zA-Z]+\b', content.lower())
            word_position = content_words.index(selected_word) + 1  # 1-indexed

            current_required_word = selected_word

            return {
                "passes": True,
                "reason": f"Great! Your message contained '{current_required_word}'. Next person must include '{selected_word}'",
                "selected_word": selected_word,
                "word_position": word_position
            }
        else:
            # Keep the same required word since no new words to select
            return {
                "passes": True,
                "reason": f"Message accepted! Next person still needs to include '{current_required_word}'",
                "selected_word": None,
                "word_position": None
            }
    else:
        # Message fails - doesn't contain required word
        return {
            "passes": False,
            "reason": f"Oops! Your message must contain the word '{current_required_word}' to continue the chain!"
        }


def reset_word_chain_state() -> None:
    """Clear the tracked word so a new chain can start fresh."""
    global current_required_word
    current_required_word = None
