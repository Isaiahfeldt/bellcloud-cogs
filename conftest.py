"""Root conftest — stubs out redbot so tests can run without a full Red installation."""
import sys
import types
from unittest.mock import MagicMock

# Build a minimal redbot stub using MagicMock so decorator chains work.
redbot = MagicMock()
redbot.core.bot.Red = object
redbot.core.commands.Cog = object

sys.modules["redbot"] = redbot
sys.modules["redbot.core"] = redbot.core
sys.modules["redbot.core.bot"] = redbot.core.bot
sys.modules["redbot.core.commands"] = redbot.core.commands
sys.modules["redbot.core.config"] = redbot.core.config
