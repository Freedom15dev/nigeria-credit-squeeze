"""Loan arithmetic used in chapter 6: monthly to yearly rates, flat vs reducing balance,
and what a borrower repays in total.

All rates are passed as percentages (2.5 means 2.5%).
"""


def simple_annual(monthly_pct):
    """Monthly rate x 12. This is how many lenders state a yearly rate."""
    return monthly_pct * 12


def effective_annual(monthly_pct):
    """(1 + monthly)^12 - 1: what the monthly rate compounds to over a year."""
    return ((1 + monthly_pct / 100) ** 12 - 1) * 100


def annual_to_monthly(annual_pct):
    """A bank's yearly rate expressed per month (annual / 12, the way banks quote it)."""
    return annual_pct / 12


def flat_total(principal, monthly_pct, months):
    """Total repaid when interest is charged on the FULL amount for every month.

    Common with loan apps: you pay interest on money you have already paid back.
    """
    return principal * (1 + monthly_pct / 100 * months)


def reducing_payment(principal, monthly_pct, months):
    """Equal monthly instalment when interest is charged only on what is still owed."""
    r = monthly_pct / 100
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def reducing_total(principal, monthly_pct, months):
    """Total repaid on a reducing-balance loan with equal monthly instalments."""
    return reducing_payment(principal, monthly_pct, months) * months


def repayment(principal, monthly_pct, months, method="flat"):
    """Total repaid (principal + interest) by method: 'flat' or 'reducing'."""
    if method == "flat":
        return flat_total(principal, monthly_pct, months)
    if method == "reducing":
        return reducing_total(principal, monthly_pct, months)
    raise ValueError("method must be 'flat' or 'reducing'")


def schedule(principal, monthly_pct, months, method="reducing"):
    """Month-by-month repayment table: one dict per month with
    month, payment, interest, principal (the part of the loan repaid) and balance (left to repay).

    reducing: equal payments; interest each month = what you still owe x the monthly rate.
    flat: interest each month = the FULL amount borrowed x the monthly rate; the loan itself is
    repaid in equal parts.
    """
    r = monthly_pct / 100
    rows, balance = [], principal
    if method == "reducing":
        payment = reducing_payment(principal, monthly_pct, months)
    elif method != "flat":
        raise ValueError("method must be 'flat' or 'reducing'")
    for m in range(1, months + 1):
        if method == "reducing":
            interest = balance * r
            repaid = payment - interest if m < months else balance  # last month clears any rounding
            pay = interest + repaid
        else:
            interest = principal * r
            repaid = principal / months
            pay = interest + repaid
        balance -= repaid
        rows.append({"month": m, "payment": pay, "interest": interest, "principal": repaid,
                     "balance": max(balance, 0.0)})
    return rows


def daily_charge_total(amount_due, daily_pct, days_late):
    """Owed after `days_late` days when a daily charge (a late fee or rollover interest) is added on the
    amount due. Simple, not compounded: the kinder assumption."""
    return amount_due * (1 + daily_pct / 100 * days_late)


def monthly_rollover_total(amount_due, monthly_pct, days_late):
    """Owed if the whole amount due is rolled into a new month at the loan's rate every 30 days late."""
    return amount_due * (1 + monthly_pct / 100) ** (days_late // 30)


def _self_check():
    """Hand calculations, so the functions can be trusted."""
    # Tunde: N100,000 for 1 month at 10% a month -> N110,000. One month: flat = reducing.
    assert round(flat_total(100_000, 10, 1)) == 110_000
    assert round(reducing_total(100_000, 10, 1)) == 110_000
    # Amaka: N500,000 for 6 months at 5% flat -> 500,000 x (1 + 0.05 x 6) = N650,000
    assert round(flat_total(500_000, 5, 6)) == 650_000
    # Reducing balance at 5%: instalment = 500,000 x 0.05 / (1 - 1.05^-6) = N98,508.73
    assert abs(reducing_payment(500_000, 5, 6) - 98_508.73) < 0.01
    # 2.5% a month = 30% simple, 34.49% effective
    assert simple_annual(2.5) == 30
    assert abs(effective_annual(2.5) - 34.4889) < 0.001
    # Schedules: N500,000 over 6 months at 8.25% a month.
    red, flat = schedule(500_000, 8.25, 6, "reducing"), schedule(500_000, 8.25, 6, "flat")
    # Month 1: interest on the full N500,000 for both = 500,000 x 0.0825 = N41,250
    assert round(red[0]["interest"]) == round(flat[0]["interest"]) == 41_250
    # Flat: the same N41,250 every month, and N500,000 / 6 = N83,333.33 of the loan each month
    assert all(round(row["interest"]) == 41_250 for row in flat)
    assert abs(flat[0]["principal"] - 83_333.33) < 0.01
    # Reducing, month 6: the last instalment repays the balance plus one month's interest, so by hand
    # balance before month 6 = instalment / 1.0825 = 108,979.27 / 1.0825 = 100,673.69; x 0.0825 = N8,305.58
    assert abs(red[5]["interest"] - 8_305.58) < 0.05
    # Each schedule adds up to the totals above, and ends with nothing left to repay
    assert abs(sum(row["payment"] for row in red) - reducing_total(500_000, 8.25, 6)) < 0.01
    assert abs(sum(row["payment"] for row in flat) - flat_total(500_000, 8.25, 6)) < 0.01
    assert red[-1]["balance"] < 0.01 and flat[-1]["balance"] < 0.01
    # Late payment on N108,250 due (Tunde at 8.25%), 90 days late:
    # rollover 1% a day, simple: 108,250 x (1 + 0.01 x 90) = 108,250 x 1.9 = N205,675
    assert round(daily_charge_total(108_250, 1, 90)) == 205_675
    # late fee 0.03333% a day: 108,250 x (1 + 0.0003333 x 90) = N111,497
    assert round(daily_charge_total(108_250, 0.03333, 90)) == 111_497
    # monthly rollover at 8.25%: three new months by day 90 -> 108,250 x 1.0825^3 = N137,313
    assert round(monthly_rollover_total(108_250, 8.25, 90)) == 137_313
    # ...and nothing is added before the first 30 days are up
    assert monthly_rollover_total(108_250, 8.25, 29) == 108_250


_self_check()
