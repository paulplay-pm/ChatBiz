"""Export the OpenAPI schema for the audit-and-isolation service.

Reads the live FastAPI app's ``openapi()`` and serialises it to YAML
in ``docs/openapi/audit-and-isolation.yaml`` (and a JSON sibling for
machines that prefer JSON). The JSON file is the source of truth for
diffing across releases; the YAML is for human review and code-gen
tools (e.g. openapi-generator).

Why a script rather than a one-liner in the shell:

* ``app.main:app`` requires ``DATABASE_URL`` / ``REDIS_URL`` /
  ``CREDENTIAL_SERVICE_URL`` to be set (the ``Settings`` pydantic
  model is validated at import). We set sensible dev defaults
  here so the export works in CI without a running PG / Redis.
* The OpenAPI object includes the lifespan-driven Redis pool
  (which is lazy, so it never actually connects at export time,
  but the import path still needs the env vars to validate
  ``Settings``).
* We round-trip through ``json.loads(...)`` first to drop the
  custom ``BaseModel`` types that ``FastAPI.openapi()`` returns
  when those models aren't fully serialised — easier than walking
  the schema by hand.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Dev defaults so ``Settings`` validates without a real .env.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

import yaml  # noqa: E402  (after env-var set)

from app.main import app  # noqa: E402


def main() -> int:
    """Dump the OpenAPI schema to YAML + JSON, return 0 on success."""
    raw = app.openapi()
    # Round-trip through json to strip BaseModel typing.
    normalised = json.loads(json.dumps(raw, default=str))
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "openapi"
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = out_dir / "audit-and-isolation.yaml"
    json_path = out_dir / "audit-and-isolation.json"
    yaml_path.write_text(yaml.safe_dump(normalised, sort_keys=False, allow_unicode=True))
    json_path.write_text(json.dumps(normalised, indent=2, ensure_ascii=False))
    n_paths = len(normalised.get("paths", {}))
    print(f"exported: paths={n_paths} -> {yaml_path.relative_to(Path.cwd())}")
    print(f"exported: paths={n_paths} -> {json_path.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
