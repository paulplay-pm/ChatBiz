"""Static scanner: walk a directory, parse Python files with ``ast``,
report any direct LLM provider imports that aren't in the allowlist.

The detection layer is pure (``text -> [Violation]``); this module
adds the file-walking and allowlist/path-globbing logic. Keeping the
detection layer pure makes it cheap to unit-test in isolation.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = ["ConfigError", "Violation", "scan_dir", "scan_file"]


class ConfigError(Exception):
    """Raised when blocklist/allowlist files are missing or malformed."""


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    package: str


# 4 import patterns we detect:
#   1. ``import openai``
#   2. ``from openai import OpenAI``
#   3. ``import openai as oai``
#   4. ``__import__("openai")`` and getattr(__import__("openai"), ...)
#
# The first three are static AST nodes; the last two are Call nodes
# with a string literal argument. We cover them all to keep the
# false-negative rate below the 5% budget in the spec.
def _extract_pkg_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        # `import openai` or `import openai as oai`
        for alias in node.names:
            return alias.name.split(".")[0]
    if isinstance(node, ast.ImportFrom):
        # `from openai import OpenAI`
        if node.module and node.level == 0:
            return node.module.split(".")[0]
        return None
    if isinstance(node, ast.Call):
        # `__import__("openai")` — first positional arg must be a string
        func = node.func
        is_dunder = (
            (isinstance(func, ast.Name) and func.id == "__import__")
            or (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Call)
                and _extract_pkg_name(func.value) == "__import__"
            )
        )
        if not is_dunder:
            return None
        if not node.args:
            return None
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value.split(".")[0]
    return None


def _load_blocklist(path: Path) -> set[str]:
    if not path.exists():
        raise ConfigError(f"blocklist not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"blocklist YAML parse error in {path}: {exc}") from exc
    if not isinstance(data, dict) or "packages" not in data:
        raise ConfigError(
            f"blocklist {path} must be a YAML mapping with a top-level 'packages' key"
        )
    pkgs = data["packages"]
    if not isinstance(pkgs, list):
        raise ConfigError(f"blocklist {path} 'packages' must be a list")
    return {str(p) for p in pkgs}


def _load_allowlist(path: Path) -> list[str]:
    if not path.exists():
        # Allowlist is optional — if missing, scan everything.
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"allowlist YAML parse error in {path}: {exc}") from exc
    if not isinstance(data, dict) or "paths" not in data:
        raise ConfigError(
            f"allowlist {path} must be a YAML mapping with a top-level 'paths' key"
        )
    paths = data["paths"]
    if not isinstance(paths, list):
        raise ConfigError(f"allowlist {path} 'paths' must be a list")
    # Allow entries are either relative globs (resolved against scan_root
    # at match time) or absolute paths.
    return [str(p) for p in paths]


def _is_allowlisted(rel_file: Path, allowlist: list[str]) -> bool:
    # Normalize to forward slashes so globs are portable across OSes.
    rel_posix = rel_file.as_posix()
    for pattern in allowlist:
        # Relative glob. We need `**` to match any number of directories
        # (fnmatch doesn't, so we hand-roll a small converter).
        if _glob_match(rel_posix, pattern):
            return True
    return False


def _glob_match(path: str, pattern: str) -> bool:
    """Match ``path`` against ``pattern`` with `**` meaning "any number of
    directories". ``fnmatch`` doesn't do this; we translate `**` to `.*`
    and `*` to `[^/]*` and use re."""
    import re
    # If the pattern doesn't contain `**`, fall back to plain fnmatch
    # (cheaper and slightly faster for the common case).
    if "**" not in pattern:
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"**/{pattern}")
    # Translate: `**` -> `.*`, `*` -> `[^/]*`, escape other regex chars.
    regex_parts = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
            regex_parts.append(".*")
            i += 2
            # Eat a trailing slash so `**/` doesn't require an extra char.
            if i < len(pattern) and pattern[i] == "/":
                i += 1
        elif c == "*":
            regex_parts.append("[^/]*")
            i += 1
        else:
            regex_parts.append(re.escape(c))
            i += 1
    regex = "^" + "".join(regex_parts) + "$"
    return re.match(regex, path) is not None


def scan_file(file: Path, blocklist: set[str]) -> list[Violation]:
    """Return every forbidden import in ``file`` matching ``blocklist``."""
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except SyntaxError:
        # Don't gate on syntax errors in other people's code; the CI
        # pipeline already has its own lint step for that.
        return []
    out: list[Violation] = []
    for node in ast.walk(tree):
        pkg = _extract_pkg_name(node)
        # Only ast.stmt-style nodes (Import, ImportFrom) and Call nodes
        # carry a lineno. ast.expr-only descendants (e.g. Name, Constant)
        # would silently fail attribute access — _extract_pkg_name returns
        # None for those, so this branch only runs for nodes we know
        # have a line number.
        if pkg and pkg in blocklist:
            line = getattr(node, "lineno", 0) or 0
            out.append(Violation(file=file, line=line, package=pkg))
    return out


def scan_dir(
    scan_root: Path,
    blocklist_path: Path,
    allowlist_path: Path,
) -> list[Violation]:
    """Walk ``scan_root`` (recursively) and return every Violation."""
    blocklist = _load_blocklist(blocklist_path)
    allowlist = _load_allowlist(allowlist_path)

    out: list[Violation] = []
    for file in sorted(scan_root.rglob("*.py")):
        rel = file.relative_to(scan_root)
        if _is_allowlisted(rel, allowlist):
            continue
        out.extend(scan_file(file, blocklist))
    return out
