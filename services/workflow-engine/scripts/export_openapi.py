"""Export the OpenAPI 3.1 schema for the workflow-engine service.
Run via: `python -m scripts.export_openapi` from the service root,
or `python scripts/export_openapi.py` with PYTHONPATH=.

Writes `openapi.json` next to this script (overwriting if exists)."""
import json
import sys
from pathlib import Path


def main() -> int:
    # Ensure project root is on sys.path so `app.*` imports resolve
    service_root = Path(__file__).resolve().parent.parent
    if str(service_root) not in sys.path:
        sys.path.insert(0, str(service_root))

    from app.main import app  # noqa: E402

    schema = app.openapi()
    out_path = Path(__file__).resolve().parent / "openapi.json"
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
    print(f"OpenAPI schema exported: {out_path} ({out_path.stat().st_size} bytes, "
          f"{len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
