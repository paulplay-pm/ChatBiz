"""Fixture: getattr chain on __import__ result."""
def get_client():  # noqa: ARG001
    mod = __import__("mistralai")  # test fixture
    return getattr(mod, "Mistral")  # test fixture
