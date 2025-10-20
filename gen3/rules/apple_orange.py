"""
Apple/Orange demo rule.

Passes if message contains 'apple', fails if it contains 'orange'.
If both appear, 'orange' takes precedence and it fails.
"""

from __future__ import annotations

async def apple_orange_rule(content: str, current_strikes: int = 0) -> dict:
    """
    Demo rule: pass if message contains 'apple' (case-insensitive),
    fail if it contains 'orange'. If both appear, 'orange' takes precedence.
    """
    text = content.lower() if content else ""
    contains_orange = "orange" in text
    contains_apple = "apple" in text

    if contains_orange:
        return {
            "passes": False,
            "reason": "Contains forbidden word 'orange'. 🍊❌",
        }
    if contains_apple:
        return {
            "passes": True,
            "reason": "Contains required word 'apple'. 🍎✅",
        }
    return {
        "passes": False,
        "reason": "Message must include 'apple'. 🍎❌",
    }
