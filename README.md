# beancount → OpenAccountants: capital-gains demo

Demonstrates capital-gains classification from a beancount ledger using OpenAccountants sample rules, with an optional live MCP connection.

Default runs use bundled sample responses. Their rates, verdicts and reviewer labels are illustrative fixtures, not evidence that an accountant reviewed the demo or a live Guide. For live use, check the fetched Guide's review status, reviewer, version and review date against the [review method](https://www.openaccountants.com/review-method). A jurisdiction lead's name alone does not establish review. Have a qualified professional review outputs before filing or acting on them.

```
portfolio.beancount
  └─ FIFO lot matching → realized gains { symbol, acquire/sell date, gain }
        └─ OpenAccountants MCP  →  load the capital-gains skill
              └─ Verdict:  ✅ long-term — preferential rate (0/15/20%)
                           ⚠️ short-term — ordinary income rates (up to 37%)   ← the catch
                           ℹ️  capital loss — offsets gains
                 · holding period computed from the ledger
                 · the Guide version's published review record, if present
```

![beancount → OpenAccountants demo](demo.svg)

> Regenerate the visual: `python make_svg.py` (static SVG, no deps) · animated GIF: `brew install vhs && vhs demo.tape`

## Why this one

beancount is plain-text, double-entry accounting beloved by developers, and it's excellent at **lot tracking** — which makes it the perfect substrate for capital-gains tax. This demo reads a `.beancount` ledger, pairs buys and sells FIFO, and asks OpenAccountants the question the ledger can't answer itself: *how is each gain actually taxed?*

- **beancount = the lots and the cost basis.**
- **OpenAccountants = the tax treatment.** Short vs long term, the preferential-rate cutoff, NIIT; using the loaded rules; check the Guide version's review record.

No keys, no signup; `python pipeline.py` and it runs. (Set `OA_MCP_TOKEN` to use the live Guide content instead of the bundled samples; check its review status.)

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
export OA_MCP_TOKEN=...     # OpenAccountants account token (uses live Guide content; check review status)
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

- `cap_gains_check.py` does **classification + treatment, not an exact tax figure** (which needs total income, filing status, NIIT, state). `beancount_client.py` handles the common `{cost} @ price` lot syntax, not the full beancount grammar. Production leans on the full OA skill + an agent step; professional review must be established for the specific Guide version and your facts.
- Rules (the >1yr long-term cutoff, 0/15/20%, 3.8% NIIT) are 2025 US figures; the bundled reviewer label is illustrative. Inspect the actual `get_skill` response and its review record in live mode.
