"""
Gen3 rule functions package.

This package organizes the rule implementations used by the Gen3 cog.
Keep gen3.slash_commands as the integration surface and import rule
functions from here to keep things tidy and swappable.
"""

from .apple_orange import apple_orange_rule  # re-export
from .three_word import three_word_rule  # re-export
from .word_chain import word_chain_rule  # re-export

__all__ = [
    "apple_orange_rule",
    "three_word_rule",
    "word_chain_rule",
]
