"""Beancount ledger -> realized capital gains.

Beancount is a plain-text, double-entry accounting system that's great at lot
tracking. This reads a .beancount file, pairs buys and sells FIFO per commodity,
and emits each realized gain with its holding period — the facts the
capital-gains check needs. No beancount install required (lightweight parser).

DELIBERATE SCOPE: handles the common `{cost} @ price` lot syntax used in the
sample; it is not a full beancount parser.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import date

FIAT = {"USD", "EUR", "GBP", "CAD", "AUD"}
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\s+[*!]")
POST_RE = re.compile(r"^\s+\S+\s+(-?\d+(?:\.\d+)?)\s+([A-Z][A-Z0-9._]*)\b(.*)$")
COST_RE = re.compile(r"\{\s*([\d.]+)")
PRICE_RE = re.compile(r"@\s*([\d.]+)")


def _d(y, m, d) -> date:
    return date(int(y), int(m), int(d))


def parse(path: str) -> list[dict]:
    lots: dict[str, deque] = defaultdict(deque)  # commodity -> [ [date, units, cost], ... ]
    gains: list[dict] = []
    cur: date | None = None

    with open(path) as fh:
        for line in fh:
            md = DATE_RE.match(line)
            if md:
                cur = _d(*md.groups())
                continue
            mp = POST_RE.match(line)
            if not mp or cur is None:
                continue
            units = float(mp.group(1))
            commodity = mp.group(2)
            if commodity in FIAT:
                continue
            rest = mp.group(3)
            cost = COST_RE.search(rest)
            price = PRICE_RE.search(rest)

            if units > 0 and cost:  # buy
                lots[commodity].append([cur, units, float(cost.group(1))])
            elif units < 0 and price:  # sell -> FIFO match
                qty = -units
                sale_px = float(price.group(1))
                while qty > 1e-9 and lots[commodity]:
                    lot = lots[commodity][0]
                    take = min(qty, lot[1])
                    gains.append({
                        "symbol": commodity,
                        "units": take,
                        "acquire_date": lot[0].isoformat(),
                        "sell_date": cur.isoformat(),
                        "holding_days": (cur - lot[0]).days,
                        "cost_basis": round(lot[2] * take, 2),
                        "proceeds": round(sale_px * take, 2),
                        "gain": round((sale_px - lot[2]) * take, 2),
                    })
                    lot[1] -= take
                    qty -= take
                    if lot[1] <= 1e-9:
                        lots[commodity].popleft()
    return gains
