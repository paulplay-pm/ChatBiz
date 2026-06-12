"""Pytest bootstrap for services/mcp/tests.

Adds the parent ``services/mcp/`` directory to ``sys.path`` so that
``from app.security import ...`` and ``from servers import filesystem``
resolve without needing an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MCP_ROOT = Path(__file__).resolve().parents[2]
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))
