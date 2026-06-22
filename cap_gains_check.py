"""Classify a realized gain against the loaded OA capital-gains rules.

The one that bites people: a gain on something held a year or less is
**short-term** — taxed at ordinary income rates (up to 37%), not the 0/15/20%
long-term rate most assume. This flags those.

DELIBERATE SCOPE: classification + treatment, not an exact tax figure (which
needs total income, filing status, NIIT, state). Production leans on the full OA
skill + an agent step; the named-CPA sign-off makes the verdict relianceable.
"""

from __future__ import annotations


def check(gain: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    base = {"oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
            "tier": oa_skill.get("tier"), "verifier": oa_skill.get("verifier")}
    days = gain["holding_days"]
    amt = gain["gain"]
    lt_min = rules.get("long_term_min_days", 366)

    if amt < 0:
        return {**base, "status": "info",
                "headline": f"Capital loss (${amt:,.2f})",
                "detail": "Offsets capital gains; up to $3,000/yr deductible against ordinary income, rest carries forward."}

    if days >= lt_min:
        lt = rules.get("long_term", {})
        niit = rules.get("niit", {})
        return {**base, "status": "ok",
                "headline": f"Long-term gain — preferential rate ({lt.get('headline', '0/15/20%')})",
                "detail": f"Held {days} days (>1yr). {niit.get('note', '')}".strip()}

    st = rules.get("short_term", {})
    return {**base, "status": "warn",
            "headline": f"Short-term gain — {st.get('treatment', 'ordinary income rates')}",
            "detail": f"Held only {days} days (≤1yr) — taxed as ordinary income, NOT the long-term 0/15/20% rate."}
