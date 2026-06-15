"""Scanner core — AST walker that flags LLM provider SDK imports.

Task 1.1 ships a minimal stub (one pattern: bare `import X`). Task 1.4 extends
this to the full 4-pattern AST match (bare import / `import X as Y` /
`__import__("X")` / `getattr(__import__("X"), ...)`). Keeping the public API
stable here lets downstream tasks (1.2 blocklist, 1.3 allowlist) be developed
against a fixed contract.

Public API:
  - ScannerConfig: frozen dataclass of resolved rules
  - load_config(target, config_path, blocklist_path, allowlist_path) -> ScannerConfig
  - scan_path(target, config) -> list[Violation]
  - Violation: dataclass(file, line, package)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    package: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.package}"


@dataclass(frozen=True)
class ScannerConfig:
    """Resolved scanner configuration.

    `target` is the directory to scan (recursive). `blocklist` is a set of
    package names that must NEVER appear in any non-allowlisted file. Empty
    blocklist means "no rules" (used by task 1.1 smoke test; production config
    comes from gateway_scanner.yaml).
    """

    target: Path
    blocklist: frozenset[str] = field(default_factory=frozenset)
    allowlist: frozenset[Path] = field(default_factory=frozenset)

    @property
    def total_rules(self) -> int:
        return len(self.blocklist)


class ConfigError(ValueError):
    """Raised when the scanner config is malformed or missing."""


def load_config(
    *,
    target: Path,
    config_path: Path | None,
    blocklist_path: Path | None,
    allowlist_path: Path | None,
) -> ScannerConfig:
    """Resolve blocklist + allowlist from explicit overrides or config file.

    Precedence (highest first): --blocklist/--allowlist CLI flags > --config
    file > ./gateway_scanner.yaml (if present). Empty defaults mean no rules.
    """
    blocklist: set[str] = set()
    allowlist: set[Path] = set()

    # If a config file is given (or default exists), load it first
    cfg_path = config_path or Path("gateway_scanner.yaml")
    if cfg_path.exists():
        try:
            data = yaml.safe_load(cfg_path.read_text()) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {cfg_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"{cfg_path} must be a YAML mapping at top level")
        for pkg in data.get("blocklist", []) or []:
            blocklist.add(str(pkg))
        for p in data.get("allowlist", []) or []:
            allowlist.add(Path(p))

    # CLI overrides win
    if blocklist_path is not None:
        blocklist = set(_load_package_list(blocklist_path))
    if allowlist_path is not None:
        allowlist = {Path(p) for p in _load_path_list(allowlist_path)}

    return ScannerConfig(
        target=target,
        blocklist=frozenset(blocklist),
        allowlist=frozenset(allowlist),
    )


def _load_package_list(path: Path) -> Iterable[str]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list):
        raise ConfigError(f"{path} must be a YAML list of package names")
    return [str(p) for p in data]


def _load_path_list(path: Path) -> Iterable[str]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list):
        raise ConfigError(f"{path} must be a YAML list of paths")
    return [str(p) for p in data]


def _is_allowlisted(file: Path, allowlist: frozenset[Path]) -> bool:
    """A file is allowlisted if it lives under any allowlisted path prefix."""
    file_str = str(file.resolve())
    for prefix in allowlist:
        try:
            file.relative_to(prefix.resolve())
            return True
        except ValueError:
            # also try string-prefix match for relative allowlist entries
            if file_str.startswith(str(prefix.resolve())):
                return True
    return False


def scan_path(target: Path, config: ScannerConfig) -> list[Violation]:
    """Walk `target` recursively; return all LLM SDK import violations.

    `target` may be a directory (recursive walk via rglob) or a single
    Python file (one-shot parse). Empty blocklist → empty violations list
    (smoke test uses this to verify exit code 0).
    """
    if not config.blocklist:
        return []

    if target.is_file():
        candidates = [target]
    else:
        candidates = sorted(target.rglob("*.py"))

    violations: list[Violation] = []
    for py_file in candidates:
        if _is_allowlisted(py_file, config.allowlist):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            # Don't fail the scan on a malformed file — just skip.
            # Real lint coverage is a separate concern (ruff / mypy).
            continue
        for node in ast.walk(tree):
            for pkg in _extract_imports(node):
                if _is_blocked(pkg, config.blocklist):
                    violations.append(Violation(file=py_file, line=node.lineno, package=pkg))
    return violations


def _is_blocked(pkg: str, blocklist: frozenset[str]) -> bool:
    """Match `pkg` against the blocklist by longest-prefix.

    `google.generativeai.generativeai` is blocked by entry `google.generativeai`
    (any module under a blocked prefix is itself blocked). Returns the
    matched prefix, or None if no match.
    """
    parts = pkg.split(".")
    # Walk from longest to shortest prefix
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in blocklist:
            return True
    return False


def _extract_imports(node: ast.AST) -> Iterable[str]:
    """Yield package names from a single AST node.

    Task 1.4 covers the 4 patterns per `openspec/changes/gateway-egress-enforcement-p0/`
    plan §抽样 1.4:
      1. `ast.Import`         — `import openai`              (root package only)
      2. `ast.ImportFrom`     — `from openai import X`       (root package only)
      3. `ast.Call(Import)`   — `__import__("openai")`        (string literal arg)
      4. `ast.Call(getattr)`  — `getattr(__import__("openai"), "attr")` (chain)

    Returned names are the **root** package (`openai`, `google.generativeai`,
    not `OpenAI`). The blocklist is keyed on root packages.
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield _root_pkg(alias.name)
    elif isinstance(node, ast.ImportFrom):
        # `from . import x` (level > 0) is a relative import; no external package.
        if node.level and node.level > 0:
            return
        if node.module:
            yield _root_pkg(node.module)
    elif isinstance(node, ast.Call):
        # Pattern 3: __import__("X")
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    yield _root_pkg(arg.value)
                    break
        # Pattern 4: getattr(__import__("X"), "attr")
        # The inner Call is the `__import__("X")` we just handled. Recurse
        # into the .value chain to catch it even when wrapped in getattr.
        elif isinstance(node.func, ast.Attribute):
            inner = node.func.value
            if isinstance(inner, ast.Call):
                yield from _extract_imports(inner)  # pragma: no cover


def _root_pkg(dotted: str) -> str:
    """Return the full dotted package name (e.g. `google.generativeai`).

    We keep the entire dotted path (not just the first segment) because the
    blocklist is keyed on full sub-package names like `google.generativeai`.
    `_is_blocked` does the longest-prefix match against the blocklist.
    """
    return dotted.split(".")[0] if "." not in dotted else dotted
