"""Turn the raw CBN pulls into tidy monthly tables.

Every data trap from CLAUDE.md section 5 that lives in the CBN data is handled here,
and each function says what it does so the notebook can explain it in plain words.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fetch_cbn import latest_raw

START = pd.Timestamp("2006-01-01")

RATE_COLUMNS = [
    "interBankCallRate", "mrr", "mpr", "treasuryBill", "savingsDeposit",
    "oneMonthDeposit", "threeMonthsDeposit", "sixMonthsDeposit",
    "twelveMonthsDeposit", "primeLending", "maxLending",
]
CREDIT_COLUMNS = ["creditToPrivateSector", "creditToGovernment", "netDomesticCredit", "moneySupply_M2"]


def _read(name, path=None):
    path = Path(path) if path else latest_raw(name)
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))), path


def _add_month(df):
    df["month"] = pd.to_datetime({"year": df["tyear"].astype(int), "month": df["tmonth"].astype(int), "day": 1})
    return df


# ---------------------------------------------------------------- money market
def load_money_market(path=None):
    """Monthly interest rates (% per year), oldest first, with a joined policy_rate.

    Trap 1: the MPR is 0 from Jan to Nov 2006 because it only replaced the MRR in
    Dec 2006. policy_rate = MRR before the MPR existed, MPR after.
    """
    raw, _ = _read("money_market", path)
    df = _add_month(raw)
    for col in RATE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["month"] + RATE_COLUMNS].sort_values("month").reset_index(drop=True)
    # Trap 4: the T-bill rate is 0.00 in Dec 2017 and Dec 2018. A 0% T-bill rate is
    # not believable next to 13-15% in the months around it, so it is treated as missing.
    df["treasuryBill_zero_fixed"] = df["treasuryBill"] == 0
    df.loc[df["treasuryBill_zero_fixed"], "treasuryBill"] = np.nan
    df["policy_rate"] = np.where(df["mpr"] > 0, df["mpr"], df["mrr"])
    df["policy_rate_source"] = np.where(df["mpr"] > 0, "MPR", "MRR")
    return df


def missing_months(df, start=None, end=None):
    """Months between start and end that have no row (trap 4)."""
    start = start or df["month"].min()
    end = end or df["month"].max()
    full = pd.date_range(start, end, freq="MS")
    return full.difference(pd.DatetimeIndex(df["month"]))


# ---------------------------------------------------------------- money & credit
def load_credit(path=None):
    """Monthly money and credit stats from Jan 2006, in ₦ millions, NOMINAL (trap 3).

    The feed mixes yearly rows (where tmonth holds the year) with monthly rows;
    only the monthly ones are kept.

    Trap 2: creditToGovernment is negative in many months up to mid-2014. That is
    real: government held more deposits in the banking system than it borrowed,
    so on net it was a lender. The values are kept as they are.
    """
    raw, _ = _read("money_credit", path)
    raw = raw[raw["tmonth"].astype(int).between(1, 12)].copy()
    df = _add_month(raw)
    for col in CREDIT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["month"] >= START]
    return df[["month"] + CREDIT_COLUMNS].sort_values("month").reset_index(drop=True)


# ---------------------------------------------------------------- inflation
def load_inflation(path=None):
    """Monthly year-on-year inflation (%), same treatment as nigeria-savings-vs-inflation.

    - The CBN feed holds the NBS 2025 revision (published Jan 2026), not the first
      releases, and the CPI was rebased in Jan 2025. Both are used as published.
    - June 2025 repeats May 2025 in the feed. June is blanked and interpolated
      between May and July. The function checks the duplicate is still there first.
    """
    raw, _ = _read("inflation", path)
    df = _add_month(raw)
    df["inflation"] = pd.to_numeric(df["allItemsYearOn"], errors="coerce")
    df["food_inflation"] = pd.to_numeric(df["foodYearOn"], errors="coerce")
    df = df[["month", "inflation", "food_inflation"]].sort_values("month").reset_index(drop=True)

    may, june = pd.Timestamp("2025-05-01"), pd.Timestamp("2025-06-01")
    m = df.set_index("month")
    df["june_2025_fixed"] = False
    if june in m.index and may in m.index and m.loc[june, "inflation"] == m.loc[may, "inflation"]:
        is_june = df["month"] == june
        df.loc[is_june, ["inflation", "food_inflation"]] = np.nan
        df[["inflation", "food_inflation"]] = df[["inflation", "food_inflation"]].interpolate()
        df.loc[is_june, "june_2025_fixed"] = True
    return df[df["month"] >= START].reset_index(drop=True)


def add_price_index(df):
    """Chained monthly price index, Jan 2006 = 100 (method from the savings project).

    Each month's year-on-year rate is turned into a monthly step,
    (1 + yoy)^(1/12) - 1, and the steps are multiplied together.
    """
    df = df.copy()
    step = (1 + df["inflation"] / 100) ** (1 / 12)
    step.iloc[0] = 1
    df["price_index"] = 100 * step.cumprod()
    return df


# ---------------------------------------------------------------- one panel
def build_panel():
    """One row per month, Jan 2006 to the latest month in the money market feed.

    Missing money-market months stay as NaN in the rate columns. For charts only,
    *_filled columns hold linearly interpolated values (trap 4). Regressions must
    use the unfilled columns.
    """
    mm = load_money_market()
    credit = load_credit()
    infl = add_price_index(load_inflation())

    months = pd.DataFrame({"month": pd.date_range(START, mm["month"].max(), freq="MS")})
    panel = months.merge(mm, on="month", how="left").merge(credit, on="month", how="left").merge(
        infl, on="month", how="left")
    panel["mm_missing"] = panel["primeLending"].isna()
    panel["credit_missing"] = panel["creditToPrivateSector"].isna()
    for col in ["primeLending", "maxLending", "policy_rate", "treasuryBill", "savingsDeposit"] + CREDIT_COLUMNS:
        panel[f"{col}_filled"] = panel[col].interpolate()
    return panel
