"""Commented import — should NOT be flagged (comments don't reach the AST)."""

# import openai
# from anthropic import Anthropic
x = 1  # import cohere
print(x)
