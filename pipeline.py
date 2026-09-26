#!/usr/bin/env python3
"""Calculate FIFO gains from the documented USD investment-ledger subset."""

import argparse
from pathlib import Path
import sys
import textwrap

import beancount_client
import cap_gains_check
from oa_client import OAClient
from reporting import configure_output, safe_text


def run(source: str, oa: OAClient) -> bool:
    gains = beancount_client.parse(source)
    if not gains:
        print("No disposals in the accepted ledger; no gain classification was performed.")
        return True
    plan = oa.start("Classify illustrative ordinary-purchase gains", "US")
    if not isinstance(plan, dict):
        raise ValueError("start must return an object")
    skills = plan.get("skills_to_load", [])
    if not isinstance(skills, list) or any(not isinstance(slug, str) for slug in skills):
        raise ValueError("skills_to_load must be an array of names")
    skill = oa.get_skill(skills[0]) if skills else {}
    complete = True
    for gain in gains:
        verdict = cap_gains_check.check(gain, skill)
        print(f"\n📈  {safe_text(gain['account'])} · {safe_text(gain['symbol'])} · {gain['units']:g} units")
        print(f"    Acquired {gain['acquire_date']} → sold {gain['sell_date']}")
        print(f"    Basis {cap_gains_check.money(gain['cost_basis'])} · "
              f"proceeds {cap_gains_check.money(gain['proceeds'])} · difference {cap_gains_check.money(gain['gain'])}")
        trust = ("unverified sample rules" if verdict["provenance"] == "sample"
                 else "provider metadata; not independently verified")
        print(f"    OpenAccountants → {safe_text(verdict.get('oa_skill_name') or 'capital-gains rules')} ({trust})")
        marker = "ℹ️" if verdict["complete"] else "⚠️"
        print(f"    {marker} {safe_text(verdict['headline'])}")
        print(textwrap.fill(safe_text(verdict["detail"]), width=96, initial_indent="       ", subsequent_indent="       "))
        complete = complete and verdict["complete"]
    return complete


def main(argv: list[str]) -> int:
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=str(Path(__file__).parent / "samples/portfolio.beancount"))
    parser.add_argument("--live", action="store_true", help="use the unverified OpenAccountants adapter")
    args = parser.parse_args(argv[1:])
    oa = OAClient() if args.live else OAClient(token=None)
    if args.live and not oa.live:
        parser.error("--live requires OA_MCP_TOKEN")
    mode = "LIVE ADAPTER (unverified)" if oa.live else "BUNDLED ILLUSTRATIVE RULES"
    print(f"beancount → OpenAccountants · capital-gains demo [{mode}]")
    try:
        complete = run(args.source, oa)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Calculation failed: {safe_text(error)}", file=sys.stderr)
        return 2
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
