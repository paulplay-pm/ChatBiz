"""Idempotent seed for the ``model_routing`` table.

Run via::

    python -m alembic.seed

or, in the docker-compose migration container::

    alembic upgrade head && python -m alembic.seed

The seed uses ``INSERT ... ON CONFLICT DO NOTHING`` (PG upsert) so it is
safe to re-run: an already-seeded row with the same ``model_name`` (the
table's primary key) is left untouched.

Three default upstream models ship with the MVP:

* ``qwen-max``              — public provider (DashScope / Qwen)
* ``deepseek-r1``           — public provider (DeepSeek)
* ``internal-vllm-qwen``    — private provider (in-house vLLM)

The runtime routing table loader filters on ``enabled = true`` at
startup, so disabling a row in the database is the kill switch.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import insert

from app.database import get_session
from app.models.audit import ModelRouting

SEED: list[dict[str, str | int]] = [
    {
        "model_name": "qwen-max",
        "model_kind": "public",
        "upstream_base_url": "https://dashscope.aliyuncs.com",
    },
    {
        "model_name": "deepseek-r1",
        "model_kind": "public",
        "upstream_base_url": "https://api.deepseek.com",
    },
    {
        "model_name": "internal-vllm-qwen",
        "model_kind": "private",
        "upstream_base_url": "http://vllm.internal:8000",
    },
]


async def main() -> None:
    async with get_session() as s:
        await s.execute(insert(ModelRouting).values(SEED).on_conflict_do_nothing())


if __name__ == "__main__":
    asyncio.run(main())
