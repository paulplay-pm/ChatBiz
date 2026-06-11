"""Fixture: imports inside a string / comment (should NOT be flagged)."""
# This is a comment that mentions openai but isn't an import.
"""This docstring mentions anthropic in a string."""
import json  # noqa: F401  # test fixture — should NOT match any blocklist entry
