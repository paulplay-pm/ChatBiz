"""Dynamic import via __import__ and getattr — the most evasive pattern.

A naive grep / regex would miss these. The scanner walks the AST, sees
`Call(func=Name("__import__"))` and the `getattr(__import__("..."), "...")`
chain.
"""

cohere = __import__("cohere")
genai = getattr(__import__("google.generativeai"), "generativeai")

# Force "use" so the imports aren't optimized away.
_ = cohere
_ = genai
