"""Parse a strict USD investment-ledger subset and calculate exact FIFO gains."""

from collections import defaultdict, deque
from datetime import date
from decimal import Decimal, localcontext
import re

NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
ACCOUNT = r"(?:Assets|Income)(?::[A-Z][A-Za-z0-9-]*)+"
COMMODITY = r"[A-Z](?:[A-Z0-9._]*[A-Z0-9])?"
QUOTED = r'"(?:[^"\\]|\\.)*"'
HEADER = re.compile(r"(\d{4}-\d{2}-\d{2})\s+\*\s+" + QUOTED + r"(?:\s+" + QUOTED + r")?")
OPEN = re.compile(r"(\d{4}-\d{2}-\d{2})\s+open\s+(" + ACCOUNT + r")")
POSTING = re.compile(r"\s+(" + ACCOUNT + r")\s+(" + NUMBER + r")\s+(" + COMMODITY + r")\s*(.*)")
BUY = re.compile(r"\{\s*(" + NUMBER + r")\s+USD\s*\}")
SELL = re.compile(r"\{\s*(?:(" + NUMBER + r")\s+USD\s*)?\}\s*@\s*(" + NUMBER + r")\s+USD")
OTHER_FIAT = {"EUR", "GBP", "CAD", "AUD"}


def number(value, *, cash=False):
    result = Decimal(value)
    limit, scale = (Decimal("1e24"), 36) if cash else (Decimal("1e12"), 18)
    if result.copy_abs() > limit or result.as_tuple().exponent < -scale:
        raise ValueError("number exceeds the documented magnitude or precision limit")
    return result


def apply_trade(occurred, postings, lots):
    investments, cash, income = [], [], []
    for account, units, symbol, rest in postings:
        if symbol in {"TRUE", "FALSE", "NULL"}:
            raise ValueError("reserved Beancount keywords cannot be commodities")
        if symbol in OTHER_FIAT:
            raise ValueError("only USD cost and cash currency are supported")
        if symbol == "USD":
            if rest:
                raise ValueError("USD postings cannot carry cost or price annotations")
            (cash if account.startswith("Assets:") else income).append((account, units))
        else:
            investments.append((account, units, symbol, rest))
    if len(investments) != 1 or len(cash) != 1:
        raise ValueError("each trade needs one investment posting and one USD cash posting")
    account, units, symbol, rest = investments[0]
    if not account.startswith("Assets:") or units == 0:
        raise ValueError("investment quantity must be nonzero in an Assets account")
    key = (account, symbol, "USD")
    if units > 0:
        match = BUY.fullmatch(rest)
        if not match or income:
            raise ValueError("a purchase needs a unit USD cost and no income posting")
        cost = number(match[1])
        if cost < 0 or cash[0][1] != -(units * cost):
            raise ValueError("purchase cost and USD cash posting do not agree")
        lots[key].append([occurred, units, cost])
        return []
    match = SELL.fullmatch(rest)
    if not match or len(income) != 1:
        raise ValueError("a sale needs {} or {unit USD cost}, one @ USD price and explicit income")
    specified_cost = number(match[1]) if match[1] is not None else None
    price = number(match[2])
    if price < 0 or (specified_cost is not None and specified_cost < 0):
        raise ValueError("sale price and cost must be non-negative")
    quantity = units.copy_negate()
    remaining, selected = quantity, []
    for lot in lots[key]:
        if specified_cost is not None and specified_cost != lot[2]:
            raise ValueError("the supplied cost would bypass or conflict with FIFO lots")
        take = min(remaining, lot[1])
        selected.append((lot, take))
        remaining -= take
        if remaining == 0:
            break
    if remaining:
        raise ValueError("sale quantity exceeds available inventory in this account")
    basis = sum((lot[2] * take for lot, take in selected), Decimal(0))
    proceeds = price * quantity
    if cash[0][1] != proceeds or income[0][1] != -(proceeds - basis):
        raise ValueError("sale price, FIFO basis, cash and income postings do not agree")
    gains = []
    for lot, take in selected:
        lot_basis, lot_proceeds = lot[2] * take, price * take
        gains.append({"account": account, "symbol": symbol, "currency": "USD", "units": take,
                      "acquire_date": lot[0].isoformat(), "sell_date": occurred.isoformat(),
                      "holding_days": (occurred - lot[0]).days,
                      "cost_basis": lot_basis, "proceeds": lot_proceeds, "gain": lot_proceeds - lot_basis})
        lot[1] -= take
        if lot[1] == 0:
            lots[key].popleft()
    return gains


def parse(path: str) -> list[dict]:
    # ponytail: Accept only the documented trade subset; use Beancount's parser for broader grammar.
    lots, gains, opened = defaultdict(deque), [], set()
    current, postings, previous, header_line, trades = None, [], date.min, 0, 0

    def finish():
        try:
            return apply_trade(current, postings, lots)
        except ValueError as error:
            raise ValueError(f"line {header_line}: {error}") from error

    with localcontext() as context:
        context.prec = 80
        with open(path, encoding="utf-8") as fh:
            for line_number, raw in enumerate(fh, 1):
                line = raw.rstrip()
                if not line.strip() or line.lstrip().startswith(";"):
                    continue
                opening, header = OPEN.fullmatch(line), HEADER.fullmatch(line)
                if opening or header:
                    if current is not None:
                        gains.extend(finish())
                        trades += 1
                        current, postings = None, []
                    try:
                        occurred = date.fromisoformat((opening or header)[1])
                    except ValueError as error:
                        raise ValueError(f"line {line_number}: invalid calendar date") from error
                    if occurred < previous:
                        raise ValueError(f"line {line_number}: dates must be chronological")
                    previous = occurred
                    if opening:
                        if opening[2] in opened:
                            raise ValueError(f"line {line_number}: duplicate account opening")
                        opened.add(opening[2])
                    else:
                        current, header_line = occurred, line_number
                    continue
                posting = POSTING.fullmatch(line)
                if current is None or posting is None:
                    raise ValueError(f"line {line_number}: unsupported ledger syntax")
                account, value, symbol, rest = posting.groups()
                if account not in opened:
                    raise ValueError(f"line {line_number}: account has not been opened")
                try:
                    units = number(value, cash=symbol == "USD")
                except ValueError as error:
                    raise ValueError(f"line {line_number}: {error}") from error
                postings.append((account, units, symbol, rest))
        if current is not None:
            gains.extend(finish())
            trades += 1
    if not trades:
        raise ValueError("ledger must contain at least one supported trade")
    return gains
