# beancount → OpenAccountants: capital-gains demo

**The pitch in one line:** beancount tracks your lots in plain text. OpenAccountants tells you the **tax treatment of each realized gain** — short- vs long-term, across jurisdictions — signed off by a named licensed accountant. No API keys, no signup.

```
portfolio.beancount
  └─ FIFO lot matching → realized gains { symbol, acquire/sell date, gain }
        └─ OpenAccountants MCP  →  load the verified capital-gains skill
              └─ Verdict:  ✅ long-term — preferential rate (0/15/20%)
                           ⚠️ short-term — ordinary income rates (up to 37%)   ← the catch
                           ℹ️  capital loss — offsets gains
                 · holding period computed from the ledger
                 · the named CPA who signed off the rates
```

![beancount → OpenAccountants demo](demo.svg)

> Regenerate the visual: `python make_svg.py` (static SVG, no deps) · animated GIF: `brew install vhs && vhs demo.tape`

## Why this one

beancount is plain-text, double-entry accounting beloved by developers, and it's excellent at **lot tracking** — which makes it the perfect substrate for capital-gains tax. This demo reads a `.beancount` ledger, pairs buys and sells FIFO, and asks OpenAccountants the question the ledger can't answer itself: *how is each gain actually taxed?*

- **beancount = the lots and the cost basis.**
- **OpenAccountants = the tax treatment.** Short vs long term, the preferential-rate cutoff, NIIT — with verified rules a real accountant signed off on.

No keys, no signup — `python pipeline.py` and it runs. (Set `OA_MCP_TOKEN` to use the live verified rules instead of the bundled ones.)

## What it shows

A sample ledger run through the OpenAccountants MCP:

| Holding | Verdict |
|---|---|
| AAPL — held ~7 months | ⚠️ **Short-term — ordinary income rates (up to 37%)** |
| BTC — held >3 years | ✅ Long-term — 0/15/20% |
| VTI — held ~4 years | ✅ Long-term — 0/15/20% |
| TSLA — sold at a loss | ℹ️ Capital loss — offsets gains |

**The money shot:** the AAPL gain. Held a year or less, so it's **short-term — taxed at ordinary income rates (up to 37%), not the 15% long-term rate** people assume. The ledger knows the dates; OpenAccountants knows what they mean for your tax.

## Run it

```bash
git clone https://github.com/openaccountants/beancount-tax-demo
cd beancount-tax-demo
python pipeline.py                      # bundled sample ledger (mock mode, no keys)
python pipeline.py samples/portfolio.beancount
```

### Go live

```bash
export OA_MCP_TOKEN=...     # OpenAccountants account token (uses the live verified rules)
python pipeline.py
```

## Files

| File | Role |
|------|------|
| `pipeline.py` | Orchestrator + CLI: ledger → OA → verdict report |
| `beancount_client.py` | Parses the ledger, pairs buys/sells FIFO → realized gains |
| `oa_client.py` | OpenAccountants MCP JSON-RPC client (live or mock) |
| `cap_gains_check.py` | Classifies short vs long term → verdict |
| `samples/portfolio.beancount` | A small investment ledger |

## Honest notes

- `cap_gains_check.py` does **classification + treatment, not an exact tax figure** (which needs total income, filing status, NIIT, state). `beancount_client.py` handles the common `{cost} @ price` lot syntax, not the full beancount grammar. Production leans on the full OA skill + an agent step; the named-CPA sign-off makes the verdict relianceable.
- Rules (the >1yr long-term cutoff, 0/15/20%, 3.8% NIIT) are 2025 US figures; live, every value comes from `get_skill`. The verifier (Amir Pelinkovic) is the real OpenAccountants US lead.

Holding periods use calendar dates. A 28 February 2024 acquisition sold on 28 February 2025 is short-term despite spanning 366 days; selling on 1 March 2025 is long-term. The demo handles ordinary purchases, not inherited property or other special holding-period rules. Source: [IRS Publication 550, Holding Period](https://www.irs.gov/publications/p550#en_US_2025_publink100010540).

Run the offline checks with `python -m unittest discover -s tests -v`.
