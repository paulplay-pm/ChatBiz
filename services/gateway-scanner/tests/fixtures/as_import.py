"""Aliased import — `import openai as oai` should still match package "openai"."""

import openai as oai
from anthropic import Anthropic as A

# Use the aliases so the imports aren't dead-code that ruff might remove.
_ = oai
_ = A
