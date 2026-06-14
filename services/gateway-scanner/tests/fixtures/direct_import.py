"""Direct import — the simplest case. `import openai` should match package "openai"."""

import openai
from openai import OpenAI

# Both lines should be flagged by the scanner.
print(openai)
