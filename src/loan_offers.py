"""Bank rates and loan app price tiers, read from the project's own outputs.

Nothing here is typed in by hand:
- bank rates come from data/processed/readme_numbers.json, which the notebook writes;
- app tiers are rebuilt from data/loan_offers.csv with the same rule as chapter 6 of the notebook.

Tiers, not lender names: callers only ever get the three tier numbers.
"""

import json
from pathlib import Path

import pandas as pd

import loan_math

ROOT = Path(__file__).resolve().parents[1]
NUMBERS = ROOT / "data" / "processed" / "readme_numbers.json"
OFFERS = ROOT / "data" / "loan_offers.csv"

TIER_LABELS = {"start": "Typical starting app rate", "mid": "Typical mid app rate", "high": "Highest advertised app rate"}


def bank_rates():
    """CBN average prime and maximum lending rates for the latest month, per year and per month."""
    n = json.loads(NUMBERS.read_text(encoding="utf-8"))
    return {
        "month": n["last_month_short"],
        "prime_year": n["prime_last"],
        "max_year": n["max_last"],
        "prime_month": loan_math.annual_to_monthly(n["prime_last"]),
        "max_month": loan_math.annual_to_monthly(n["max_last"]),
    }


def load_offers():
    return pd.read_csv(OFFERS)


def products_for(offers, days, business):
    """App products whose advertised tenor covers a loan of `days` days.

    Same rule as the article: payroll loans out; business loans only for business borrowers;
    products that don't publish a tenor stay in.
    """
    keep = offers["product_type"] != "payroll loan"
    if not business:
        keep &= offers["product_type"] != "business loan"
    known = offers["min_tenor_days"].notna() & offers["max_tenor_days"].notna()
    fits = (offers["min_tenor_days"] <= days) & (offers["max_tenor_days"] >= days)
    return offers[keep & (~known | fits)]


def tiers(products):
    """Typical starting rate (median of minimums), typical mid rate (median of range mid-points),
    highest advertised (highest maximum), all in % a month."""
    both = products.dropna(subset=["min_monthly_rate", "max_monthly_rate"])
    return {
        "start": float(products["min_monthly_rate"].median()),
        "mid": float(((both["min_monthly_rate"] + both["max_monthly_rate"]) / 2).median()),
        "high": float(products["max_monthly_rate"].max()),
    }


def _self_check():
    """The rebuilt tiers must match the article's (Tunde: 30 days, personal; Amaka: 180 days, business)."""
    n = json.loads(NUMBERS.read_text(encoding="utf-8"))
    offers = load_offers()
    for who, days, business in [("tunde", 30, False), ("amaka", 180, True)]:
        t = tiers(products_for(offers, days, business))
        for k in ["start", "mid", "high"]:
            assert round(t[k], 2) == n[f"{who}_rate_{k}"], (who, k, t[k], n[f"{who}_rate_{k}"])
    b = bank_rates()
    assert (b["prime_year"], b["max_year"]) == (19.04, 32.62)


if __name__ == "__main__":
    _self_check()
    print("loan_offers self-check passed: tiers and bank rates match the article.")
