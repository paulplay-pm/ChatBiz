"""Jinja2 rendering helper for node template strings.

Used by every node that accepts a templated string field (LLM prompt, HTTP URL,
condition expression, variable assignment, etc). The renderer uses
``StrictUndefined`` so any reference to a missing context variable raises a
clear error rather than silently rendering an empty string.

For MVP this is the minimal implementation; Phase 5 will add custom filters
(``tojson``, ``default``) and a sandboxed environment that blocks attribute
access on user-controlled objects.
"""
from __future__ import annotations

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError

_env = Environment(undefined=StrictUndefined, autoescape=False)


def render_jinja(template_str, context: dict) -> str:
    """Render a Jinja2 template string. If input is not a string, returns it unchanged.

    Fast path: if the input has no ``{{`` or ``{%`` markers, return it as-is so
    we don't pay the Jinja2 compile cost for plain literal strings (this matters
    because most variable assignment values are literals, not templates).

    Raises:
        ValueError: on template syntax errors or missing variable references.
            We collapse both into ``ValueError`` so node executors can convert
            to ``UserError`` (boundary #3) at the call site.
    """
    if not isinstance(template_str, str):
        return template_str
    if not template_str or ("{{" not in template_str and "{%" not in template_str):
        return template_str
    try:
        return _env.from_string(template_str).render(**context)
    except TemplateSyntaxError as e:
        raise ValueError(f"Jinja2 语法错误: {e.message} at line {e.lineno}")
    except Exception as e:
        # UndefinedError or other — surface a single ValueError so callers can
        # uniformly treat template failures as user errors (boundary #3).
        raise ValueError(f"Jinja2 渲染错误: {e}")


__all__ = ["render_jinja"]
