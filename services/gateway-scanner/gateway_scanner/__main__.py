"""Static scanner for LLM provider imports.

The scanner enforces ``blocklist.yaml`` (a list of LLM provider
package names that MUST NOT be imported directly anywhere outside
``allowlist.yaml``). It walks a directory of Python source files,
parses each one with the standard library ``ast`` module, and
reports any forbidden imports as ``file:line:package_name``.

This is the **compile-time** half of the egress-enforcement
defense-in-depth. The runtime half lives in
``services/audit-and-isolation/app/auth.py`` (credential service
token validation) and is NOT touched by this tool.

Exit codes:

* 0 — no violations
* 1 — at least one violation found
* 2 — configuration error (missing/invalid blocklist or allowlist)
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .scanner import ConfigError, scan_dir


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--blocklist",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to blocklist.yaml (default: ./blocklist.yaml relative to PATH).",
)
@click.option(
    "--allowlist",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to allowlist.yaml (default: ./allowlist.yaml relative to PATH).",
)
def main(path: Path, blocklist: Path | None, allowlist: Path | None) -> None:
    """Scan PATH (a directory) for forbidden LLM provider imports."""
    try:
        blocklist_path = blocklist or (path / "blocklist.yaml")
        allowlist_path = allowlist or (path / "allowlist.yaml")
        violations = scan_dir(path, blocklist_path, allowlist_path)
    except ConfigError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    for v in violations:
        click.echo(f"{v.file}:{v.line}:{v.package}")
    sys.exit(1 if violations else 0)


if __name__ == "__main__":  # pragma: no cover
    main()
