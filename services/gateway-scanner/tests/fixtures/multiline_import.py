"""Multi-line / parenthesised imports — must still match the root package.

`from openai import (\n    OpenAI,\n    AsyncOpenAI,\n)` should be flagged once on
the import line, not zero times (some scanners miss parenthesised forms).
"""

from openai import (
    OpenAI,
    AsyncOpenAI,
)
from google.generativeai import GenerativeModel

_ = OpenAI
_ = AsyncOpenAI
_ = GenerativeModel
