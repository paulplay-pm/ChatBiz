"""ChatBiz gateway-static-scanner — compile-time guard against LLM provider SDK imports.

The runtime enforcement point is `services/audit-and-isolation/` (egress gateway,
P0 per eng-review decision #1). This tool provides a defense-in-depth layer
at the **import-time** level: it walks Python source trees and fails CI if
anyone imports an LLM provider SDK directly, bypassing the gateway.

Per task 1.1 of `openspec/changes/gateway-egress-enforcement-p0/`, this package
ships only `pyyaml` + `click` + `rich` as runtime dependencies (no FastAPI / DB /
httpx), so it can be invoked from any CI runner without standing up the full
service stack.

See `README.md` for usage, `pyproject.toml` for dependency list, and
`openspec/changes/gateway-egress-enforcement-p0/specs/gateway-llm-blacklist/spec.md`
for the policy this scanner enforces.
"""

__version__ = "0.1.0"
