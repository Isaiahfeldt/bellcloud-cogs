"""
One-time introspection script — dumps Red Config defaults for all loaded cogs.
Run inside Bell's Python environment on the VPS:
  python bellapi/introspect.py

Uses MagicMock stubs for redbot modules, with a real _FakeConfig that
records register_guild/global/etc calls so _defaults is populated.
"""
import sys
import json
from unittest.mock import MagicMock

# --- Stub redbot modules ---
redbot = MagicMock()
redbot.core.bot.Red = object
redbot.core.commands.Cog = object

class _FakeConfig:
    @classmethod
    def get_conf(cls, cog_instance, identifier, force_registration=False):
        inst = cls()
        inst._defaults = {}
        return inst

    def register_guild(self, **kwargs):
        self._defaults.setdefault("GUILD", {}).update(kwargs)

    def register_global(self, **kwargs):
        self._defaults.setdefault("GLOBAL", {}).update(kwargs)

    def register_member(self, **kwargs):
        self._defaults.setdefault("MEMBER", {}).update(kwargs)

    def register_channel(self, **kwargs):
        self._defaults.setdefault("CHANNEL", {}).update(kwargs)

    def register_user(self, **kwargs):
        self._defaults.setdefault("USER", {}).update(kwargs)

redbot.core.config.Config = _FakeConfig

sys.modules["redbot"] = redbot
sys.modules["redbot.core"] = redbot.core
sys.modules["redbot.core.bot"] = redbot.core.bot
sys.modules["redbot.core.commands"] = redbot.core.commands
sys.modules["redbot.core.config"] = redbot.core.config

# --- Cog imports (add/remove based on what's actually loaded on your bot) ---
COG_MODULES = [
    ("Gen3Cog",     "gen3.slash_commands",  "Gen3Cog"),
    ("Emotes",      "emote.emote",          "Emotes"),
    # Native Red cogs — import paths may vary by Red version.
    # If a cog fails with ImportError, SSH into the VPS and find the real path:
    #   find /var/lib/docker/volumes/bellbot_redbot/_data/venv -name "*.py" | xargs grep -l "class Admin" 2>/dev/null
    ("Admin",       "redbot.cogs.admin",    "Admin"),
    ("Mod",         "redbot.cogs.mod",      "Mod"),
    ("ModLog",      "redbot.cogs.modlog",   "ModLog"),
    ("General",     "redbot.cogs.general",  "General"),
    ("CustomHelp",  "redbot.cogs.customhelp", "CustomHelp"),
    ("Say",         "redbot.cogs.say",      "Say"),
    ("Downloader",  "redbot.cogs.downloader", "Downloader"),
    ("Cleanup",     "redbot.cogs.cleanup",  "Cleanup"),
    ("CycleStatus", "redbot.cogs.cyclestatus", "CycleStatus"),
    ("BellApi",     "bellapi.cog",          "BellApi"),
]

results = {}

for cog_label, module_path, class_name in COG_MODULES:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        bot = MagicMock()
        bot.owner_ids = set()
        instance = cls(bot)
        defaults = getattr(instance.config, "_defaults", {})
        results[cog_label] = {
            scope: {k: repr(v) for k, v in keys.items()}
            for scope, keys in defaults.items()
        }
    except Exception as e:
        results[cog_label] = {"ERROR": str(e)}

print(json.dumps(results, indent=2))
