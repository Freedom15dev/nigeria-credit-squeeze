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


_self_check()
