#!/usr/bin/env python3
"""beancount -> OpenAccountants capital-gains pipeline.

    python pipeline.py                      # bundled sample ledger (mock mode)
    python pipeline.py samples/portfolio.beancount

The flow:
    beancount ledger -> realized gains (FIFO) -> OA MCP (start -> get_skill)
    -> classify short vs long term -> verdict

No API keys, no signup — pure plain-text in, verified tax treatment out. Set
OA_MCP_TOKEN to pull the live verified rules instead of the bundled ones.
"""

from __future__ import annotations

import os
import sys

import beancount_client
import cap_gains_check
from oa_client import OAClient

STATUS = {"ok": "✅", "warn": "⚠️ ", "info": "ℹ️ "}


def run(source: str, oa: OAClient) -> None:
    gains = beancount_client.parse(source)
    if not gains:
        print("  (no realized gains found in the ledger)")
        return

    # Same jurisdiction skill for the whole ledger — load once.
    plan = oa.start("Classify realized capital gains", "US")
    slug = (plan.get("skills_to_load") or [None])[0]
    skill = oa.get_skill(slug) if slug else {}

    for g in gains:
        print(f"\n📈  {g['symbol']} · {g['units']:g} units · acquired {g['acquire_date']} → "
              f"sold {g['sell_date']} · gain ${g['gain']:,.2f}")
        v = cap_gains_check.check(g, skill)
        trust = f"tier {v.get('tier')}" + (f", signed off by {v['verifier']}" if v.get("verifier") else "")
        print(f"    OpenAccountants → {v.get('oa_skill_name') or 'capital-gains rules'}  ({trust})")
        print(f"    {STATUS.get(v['status'], '')} {v['headline']}")
        print(f"       {v['detail']}")


def main(argv: list[str]) -> int:
    oa = OAClient()
    mode = "LIVE" if oa.live else "MOCK (set OA_MCP_TOKEN to use the live verified rules)"
    print(f"beancount → OpenAccountants · capital-gains demo  [{mode}]")
    here = os.path.dirname(os.path.abspath(__file__))
    source = argv[1] if len(argv) > 1 else os.path.join(here, "samples", "portfolio.beancount")
    run(source, oa)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
