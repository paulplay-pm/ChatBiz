"""CLI entry point for chatbiz-gateway-scanner.

Per task 1.1 of `openspec/changes/gateway-egress-enforcement-p0/` (eng-review
decision #1: data-isolation gateway is the egress enforcement point). This
scanner is a **compile-time defense**: it walks Python source trees and fails
if anyone imports an LLM provider SDK directly (bypassing the gateway).

Exit codes (3-tier, matches `tools/check-compose-naming.sh` convention):
  0 — scan completed, no violations found
  1 — scan completed, at least one violation found (CI should block)
  2 — scan could not run (bad path, config error, etc.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from gateway_scanner.scanner import (
    ScannerConfig,
    load_config,
    scan_path,
)

console = Console(stderr=True)


@click.command()
@click.argument(
    "path",
    default=".",
    type=click.Path(exists=False, path_type=Path),
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to scanner YAML config (defaults to ./gateway_scanner.yaml if present).",
)
@click.option(
    "--blocklist",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to blocklist YAML (overrides config file).",
)
@click.option(
    "--allowlist",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to allowlist YAML (overrides config file).",
)
def cli(path: Path, config: Path | None, blocklist: Path | None, allowlist: Path | None) -> None:
    """Scan PATH for LLM provider SDK imports that bypass the gateway.

    PATH may be a directory (recursive) or omitted (defaults to current dir).
    Exits 0 on clean, 1 on violations, 2 on setup error.
    """
    try:
        cfg = load_config(
            target=path,
            config_path=config,
            blocklist_path=blocklist,
            allowlist_path=allowlist,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(Panel(f"[red]config error:[/red] {exc}", title="gateway-scanner"))
        sys.exit(2)

    if not path.exists():
        console.print(Panel(f"[red]path not found:[/red] {path}", title="gateway-scanner"))
        sys.exit(2)
    if not path.is_dir():
        console.print(Panel(f"[red]not a directory:[/red] {path}", title="gateway-scanner"))
        sys.exit(2)

    violations = scan_path(path, cfg)
    if violations:
        console.print(
            Panel(
                f"[red]found {len(violations)} violation(s) — see file:line below[/red]",
                title="gateway-scanner",
            )
        )
        for v in violations:
            console.print(f"  [red]{v.file}:{v.line}:[/red] [yellow]{v.package}[/yellow]")
        sys.exit(1)

    console.print(
        Panel(f"[green]clean — scanned {path} under {cfg.total_rules} rule(s)[/green]", title="gateway-scanner")
    )
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    cli()
