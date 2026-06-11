"""Fixture: dynamic __import__ call (should be flagged via Call pattern)."""
def _lazy():  # noqa: ARG001
    return __import__("cohere")  # test fixture — string arg triggers AST Call match
