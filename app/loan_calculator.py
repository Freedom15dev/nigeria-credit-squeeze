"""What will this loan really cost me?

A small Streamlit calculator built on the analysis in "Who Gets to Borrow in Nigeria?".
All the maths lives in src/loan_math.py; this file only collects inputs and shows results.

Run from the project folder:  streamlit run app/loan_calculator.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import loan_math  # noqa: E402  (needs the path above)
import loan_offers  # noqa: E402

ARTICLE_URL = "https://www.linkedin.com/pulse/who-gets-borrow-nigeria-i-followed-two-borrowers-find-freedom-oboh-q6mof"
REPO_URL = "https://github.com/Freedom15dev/nigeria-credit-squeeze"
APP_URL = "https://naija-loan-cost.streamlit.app/"
NEW_HOME_URL = "https://money-matters-ng.streamlit.app/"  # the calculator's new home (My loan)

NAVY, BLUE, ORANGE, GREY = "#0F1E33", "#2A6FDB", "#D9822B", "#8A94A6"

# Limits from the brief (section 4)
MAX_AMOUNT = 1_000_000_000      # ₦1 billion: anything above is almost certainly a typo
MAX_MONTHLY_RATE = 100.0
MAX_DAYS, MAX_MONTHS = 365, 60
LONGEST_APP_DAYS = 365  # longer loans are compared with bank rates only (see comparison())

PRESETS = {
    "Tunde": dict(amount=100_000.0, rate=8.25, rate_unit="per month", length=1, length_unit="months",
                  method="Not sure, show me both", purpose="Personal"),
    "Amaka": dict(amount=500_000.0, rate=8.25, rate_unit="per month", length=6, length_unit="months",
                  method="Not sure, show me both", purpose="Business"),
}
DEFAULTS = PRESETS["Tunde"]


def naira(v):
    """₦ with thousand separators and no decimals."""
    return f"₦{v:,.0f}"


def length_text(n, unit):
    """'1 month', '6 months', '15 days'."""
    n = int(n)
    return f"{n} {unit[:-1] if n == 1 else unit}"


def pct(v):
    """A rate to at most 2 decimal places, without trailing zeros."""
    return f"{v:,.2f}".rstrip("0").rstrip(".") + "%"


# ------------------------------------------------------------------ inputs
def apply_preset(name):
    for key, value in PRESETS[name].items():
        st.session_state[key] = value


def init_state():
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)


def loan_inputs():
    """Step 1, in a box at the top of the page so it's the first thing anyone sees, phone or desktop.
    Returns the inputs as a dict (not yet validated)."""
    with st.container(border=True):
        st.header("Step 1: Your loan")
        st.caption("Type in your own loan, or try an example from the article:")
        c1, c2 = st.columns(2)
        c1.button("Tunde: ₦100k, 1 month", on_click=apply_preset, args=("Tunde",), width="stretch")
        c2.button("Amaka: ₦500k, 6 months", on_click=apply_preset, args=("Amaka",), width="stretch")

        # Two columns on a wide screen; they stack into one on a phone
        left, right = st.columns(2)
        with left:
            amount = st.number_input("Amount you want to borrow (₦)", step=10_000.0, format="%.0f", key="amount")
            st.caption(f"That's **{naira(amount)}**" if amount and amount > 0 else " ")
            rate = st.number_input("Interest rate (%)", step=0.25, format="%.2f", key="rate",
                                   help="Loan apps usually quote per month, banks per year.")
            rate_unit = st.radio("The rate is", ["per month", "per year"], horizontal=True, key="rate_unit",
                                 help="Loan apps usually quote per month, banks per year.")
        with right:
            length = st.number_input("Loan length", step=1, key="length")
            length_unit = st.radio("Length in", ["days", "months"], horizontal=True, key="length_unit")
            method = st.radio(
                "How is interest charged?",
                ["Reducing balance", "Flat", "Not sure, show me both"],
                key="method",
                help=("**Reducing balance:** you pay interest only on what you still owe, so it shrinks as you repay.  \n"
                      "**Flat:** you pay interest on the full amount every month, even after you've repaid part of it."),
            )
            purpose = st.radio("What's the loan for?", ["Personal", "Business"], horizontal=True, key="purpose",
                               help="Used only to pick which loan app products to compare you with.")

    return dict(amount=amount, rate=rate, rate_unit=rate_unit, length=length, length_unit=length_unit,
                method=method, purpose=purpose)


def validate(inp):
    """Friendly messages for impossible or unlikely inputs. An empty list means all is well."""
    problems = []
    if inp["amount"] is None or inp["amount"] <= 0:
        problems.append("Please enter an amount above ₦0.")
    elif inp["amount"] > MAX_AMOUNT:
        problems.append(f"That's more than {naira(MAX_AMOUNT)}. Please check the amount for an extra zero.")

    monthly = inp["rate"] / 12 if inp["rate_unit"] == "per year" else inp["rate"]
    if inp["rate"] is None or inp["rate"] < 0:
        problems.append("The interest rate can't be negative.")
    elif monthly > MAX_MONTHLY_RATE:
        problems.append("Please enter a rate of at most 100% a month (1,200% a year).")

    if inp["length"] is None or inp["length"] < 1:
        problems.append("The loan length must be at least 1 day or 1 month.")
    elif inp["length_unit"] == "days" and inp["length"] > MAX_DAYS:
        problems.append(f"For loans longer than {MAX_DAYS} days, please enter the length in months.")
    elif inp["length_unit"] == "months" and inp["length"] > MAX_MONTHS:
        problems.append(f"Please enter a length of at most {MAX_MONTHS} months (5 years).")
    return problems


# ------------------------------------------------------------------ the maths (all from loan_math)
def describe_loan(inp):
    """Everything the page needs about the user's loan, calculated with loan_math."""
    monthly = loan_math.annual_to_monthly(inp["rate"]) if inp["rate_unit"] == "per year" else inp["rate"]
    in_days = inp["length_unit"] == "days"
    months = inp["length"] / 30 if in_days else int(inp["length"])  # days ÷ 30, as the brief says
    one_payment = in_days or months == 1  # repaid in one go at the end
    P = inp["amount"]

    if one_payment:
        # A single repayment: interest = amount × monthly rate × months. Flat and reducing are the same.
        total = loan_math.flat_total(P, monthly, months)
        totals = {"Reducing balance": total, "Flat": total}
        instalments = {}
    else:
        totals = {m: loan_math.repayment(P, monthly, months, "reducing" if m == "Reducing balance" else "flat")
                  for m in ["Reducing balance", "Flat"]}
        instalments = {"Reducing balance": loan_math.reducing_payment(P, monthly, months),
                       "Flat": totals["Flat"] / months}

    shown = "Reducing balance" if inp["method"] != "Flat" else "Flat"
    return dict(inp=inp, P=P, monthly=monthly, months=months, one_payment=one_payment,
                totals=totals, instalments=instalments, shown=shown,
                simple_year=loan_math.simple_annual(monthly), effective_year=loan_math.effective_annual(monthly))


# ------------------------------------------------------------------ step 2: the answer
def answer(loan):
    inp, P = loan["inp"], loan["P"]
    total = loan["totals"][loan["shown"]]
    length = length_text(inp["length"], inp["length_unit"])
    st.header("Step 2: The answer")
    if inp["method"] == "Not sure, show me both" and not loan["one_payment"]:
        st.caption("Shown on reducing balance, the cheaper way to charge interest. Flat is compared below.")

    c1, c2 = st.columns(2)
    c1.metric("Total you'll repay", naira(total))
    c2.metric("Total interest", naira(total - P))
    if loan["instalments"]:
        st.metric("Monthly instalment", naira(loan["instalments"][loan["shown"]]),
                  help="Equal payments each month until the loan is repaid.")

    c3, c4 = st.columns(2)
    c3.metric("Yearly rate (simple)", pct(loan["simple_year"]),
              help="The monthly rate × 12. This is how most lenders quote an APR (annual percentage rate).")
    c4.metric("Yearly rate (effective)", pct(loan["effective_year"]),
              help="What the monthly rate adds up to over a year if interest is charged on interest (compounded).")

    when = "after " + length if loan["one_payment"] else "over " + length
    st.markdown(
        f"**You borrow {naira(P)} and repay {naira(total)} {when}.** "
        f"That's {pct(loan['simple_year'])} a year, or about {pct(round(loan['effective_year']))} if the interest compounded."
    )

    if inp["method"] == "Not sure, show me both":
        red, flat = loan["totals"]["Reducing balance"], loan["totals"]["Flat"]
        if loan["one_payment"]:
            st.info("For a loan repaid in one go, flat and reducing balance give the same total.")
        else:
            a, b = st.columns(2)
            a.metric("Reducing balance", naira(red), help="Interest only on what you still owe.")
            b.metric("Flat", naira(flat), delta=f"{naira(flat - red)} more", delta_color="inverse",
                     help="Interest on the full amount every month.")
            st.markdown(f"**Flat interest would cost you {naira(flat - red)} more.** Ask your lender which one they use.")


def breakdown(loan):
    """Month-by-month tables (reducing vs flat) and a chart of the interest paid each month."""
    if loan["one_payment"]:
        return  # one repayment at the end: there is no month-by-month schedule to show
    months = loan["months"]
    sched = {m: pd.DataFrame(loan_math.schedule(loan["P"], loan["monthly"], months, key))
             for m, key in [("Reducing balance", "reducing"), ("Flat", "flat")]}

    with st.expander("See the month-by-month breakdown"):
        cols = st.columns(2)
        for col, (name, df) in zip(cols, sched.items()):
            table = df.rename(columns={"month": "Month", "payment": "Payment", "interest": "Interest",
                                       "principal": "Principal", "balance": "Balance left"})
            for c in ["Payment", "Interest", "Principal", "Balance left"]:
                table[c] = table[c].map(naira)
            col.markdown(f"**{name}**")
            col.table(table)  # a static table wraps to fit a phone screen

        fig = go.Figure()
        for name, color in [("Reducing balance", BLUE), ("Flat", ORANGE)]:
            df = sched[name]
            fig.add_trace(go.Scatter(x=df["month"], y=df["interest"], name=name, mode="lines+markers",
                                     line=dict(color=color, width=3),
                                     hovertemplate="Month %{x}: ₦%{y:,.0f} interest<extra>" + name + "</extra>"))
        fig.update_layout(
            title=dict(text="Interest paid each month", font=dict(size=15, color=NAVY)),
            height=300, margin=dict(l=10, r=10, t=45, b=10), plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", y=-0.25, x=0), font=dict(color=NAVY),
            xaxis=dict(title="Month", tickmode="linear", dtick=1 if months <= 12 else 6, showgrid=False),
            yaxis=dict(tickprefix="₦", tickformat=",.0f", gridcolor="#E3E6EB", rangemode="tozero"),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("Flat interest stays the same every month because it's charged on the full amount you borrowed. "
                   "Reducing-balance interest shrinks as you pay the loan down.")


# ------------------------------------------------------------------ step 3: how does it compare?
@st.cache_data
def reference_data():
    return loan_offers.bank_rates(), loan_offers.load_offers()


def total_at(loan, monthly_rate):
    """What the same amount and length would cost at another monthly rate, charged the same way."""
    if loan["one_payment"]:
        return loan_math.flat_total(loan["P"], monthly_rate, loan["months"])
    method = "flat" if loan["shown"] == "Flat" else "reducing"
    return loan_math.repayment(loan["P"], monthly_rate, loan["months"], method)


def comparison(loan):
    inp = loan["inp"]
    bank, offers = reference_data()
    days = inp["length"] if inp["length_unit"] == "days" else inp["length"] * 30
    products = loan_offers.products_for(offers, days, business=inp["purpose"] == "Business")

    rows = [
        ("Bank: prime rate", bank["prime_month"], BLUE),
        ("Bank: maximum rate", bank["max_month"], BLUE),
        ("Your loan", loan["monthly"], ORANGE),
    ]
    # No app product in the data advertises loans over a year; the only ones left would be short-term
    # quick loans with no published tenor, so long loans are compared with banks only.
    bank_only = days > LONGEST_APP_DAYS or products.empty
    if not bank_only:
        t = loan_offers.tiers(products)
        rows += [(loan_offers.TIER_LABELS[k], t[k], GREY) for k in ["start", "mid", "high"] if t[k] == t[k]]  # skip NaN
    rows.sort(key=lambda r: total_at(loan, r[1]))
    labels = [f"{name} · {pct(rate)} a month" for name, rate, _ in rows]
    totals = [total_at(loan, rate) for _, rate, _ in rows]
    y = list(range(len(rows)))

    st.header("Step 3: How does it compare?")
    st.markdown(f"Total you'd repay on **{naira(loan['P'])}** for "
                f"**{length_text(inp['length'], inp['length_unit'])}** at each rate:")
    fig = go.Figure(go.Bar(
        x=totals, y=y, orientation="h", width=0.45, marker_color=[c for _, _, c in rows],
        text=[naira(v) for v in totals], textposition="outside", cliponaxis=False,
        textfont=dict(color=NAVY, size=13), customdata=labels,
        hovertemplate="%{customdata}<br>Total repaid: %{text}<extra></extra>",
    ))
    # Each label sits just above its bar, so the bars can use the full width on a phone
    for yi, lab, (name, _, _) in zip(y, labels, rows):
        fig.add_annotation(x=0, y=yi - 0.42, text=f"<b>{lab}</b>" if name == "Your loan" else lab,
                           showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12, color=NAVY))
    fig.update_layout(
        height=68 * len(rows) + 30, margin=dict(l=0, r=0, t=10, b=0), bargap=0.5,
        plot_bgcolor="white", paper_bgcolor="white", font=dict(color=NAVY, size=13), showlegend=False,
        xaxis=dict(visible=False, range=[0, max(totals) * 1.38]),
        yaxis=dict(visible=False, autorange="reversed", range=[len(rows) - 0.5, -0.9]),  # cheapest at the top
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    how = "one repayment at the end" if loan["one_payment"] else loan["shown"].lower()
    if bank_only:
        st.caption(
            f"No loan app in this data advertises loans this long, so only bank rates are shown. "
            f"Bank rates: CBN averages, {bank['month']}. Your actual offer depends on you. All bars: {how}."
        )
    else:
        st.caption(
            f"Bank rates: CBN averages, {bank['month']}. App rates: advertised, as checked Apr–Nov 2026, "
            f"using the {len(products)} app products in the project's data that offer this loan length "
            f"({inp['purpose'].lower()} loans). Your actual offer depends on you. All bars: {how}."
        )


# ------------------------------------------------------------------ step 4: what if you pay late?
PENALTIES = {
    "Daily late fee": "A fee of a small % of the amount due, added every day you're late.",
    "Rollover interest": "Interest of a % per day on the amount due, added every day you're late (simple, not compounded).",
    "Monthly rollover at your loan's rate": "Every 30 days late, the whole amount due becomes a new one-month loan at your rate.",
}


def late_payment(loan):
    st.header("Step 4: What if you pay late?")
    if loan["one_payment"]:
        due = loan["totals"][loan["shown"]]
        st.markdown(f"On the due date you owe **{naira(due)}**. If you can't pay it:")
    else:
        due = loan["instalments"][loan["shown"]]
        st.markdown(f"Each month you owe an instalment of **{naira(due)}**. If you miss one:")

    days_late = st.slider("Days late", 0, 90, 30, key="days_late")
    kind = st.radio("Penalty type", list(PENALTIES), key="penalty", help="  \n".join(f"**{k}:** {v}" for k, v in PENALTIES.items()))
    if kind == "Daily late fee":
        rate = st.number_input("Late fee (% of the amount due, per day)", min_value=0.0, max_value=10.0,
                               value=0.0333, step=0.01, format="%.4f")
        owed = lambda d: loan_math.daily_charge_total(due, rate, d)
    elif kind == "Rollover interest":
        rate = st.number_input("Rollover interest (% per day)", min_value=0.0, max_value=10.0,
                               value=1.0, step=0.1, format="%.2f")
        owed = lambda d: loan_math.daily_charge_total(due, rate, d)
    else:
        owed = lambda d: loan_math.monthly_rollover_total(due, loan["monthly"], d)

    now = owed(days_late)
    c1, c2 = st.columns(2)
    c1.metric(f"You'd owe after {days_late} days", naira(now))
    c2.metric("Extra because you were late", naira(now - due))

    days = list(range(0, 91))
    fig = go.Figure(go.Scatter(
        x=days, y=[owed(d) for d in days], mode="lines", line=dict(color=ORANGE, width=3,
        shape="hv" if kind.startswith("Monthly") else "linear"),
        hovertemplate="Day %{x}: ₦%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[days_late], y=[now], mode="markers", marker=dict(color=NAVY, size=11),
                             hoverinfo="skip"))
    fig.update_layout(
        height=260, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False, font=dict(color=NAVY),
        xaxis=dict(title="Days late", range=[0, 92], showgrid=False, tickvals=[0, 30, 60, 90]),
        yaxis=dict(tickprefix="₦", tickformat=",.0f", gridcolor="#E3E6EB"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Example penalty terms based on what lenders publish. Check your own lender's terms. "
               "The chart starts at the amount due, so small changes look bigger than they are.")


# ------------------------------------------------------------------ step 5: before you borrow
def tips():
    st.header("Step 5: Before you borrow")
    st.markdown(
        "1. **Turn the rate into a yearly one.** 10% a month sounds smaller than 32% a year, but it's 120% a year.\n"
        "2. **Ask for the total in naira.** \"How much will I repay altogether, and when?\"\n"
        "3. **Borrow for the length you need.** A longer loan multiplies a monthly rate; a shorter one you can't "
        "repay leads to penalties.\n"
        "4. **Read what happens after the due date.** Late fees and rollovers can cost more than the interest.\n"
        "5. **Check the lender is on the FCCPC approved list** of digital lenders "
        "([fccpc.gov.ng](https://fccpc.gov.ng/approvals-of-dmls/))."
    )
    with st.expander("How this works"):
        st.markdown(
            "- **Days and months.** A length in days is turned into months as days ÷ 30. A loan entered in days, or "
            "for 1 month, is treated as **one repayment at the end**, so flat and reducing give the same total. "
            "Loans of 2 months or more are repaid in **equal monthly instalments**.\n"
            "- **Yearly rates.** Simple = monthly rate × 12 (how an APR is usually quoted). Effective = "
            "(1 + monthly rate)¹² − 1, what the rate adds up to if interest is charged on interest.\n"
            "- **Reducing balance** charges interest only on what you still owe. **Flat** charges it on the full "
            "amount every month.\n"
            "- **Comparison rates.** Bank: CBN average prime and maximum lending rates for the latest month in the "
            "data. Apps: advertised rates from the app products in the project's data that offer your loan "
            "length, summed up as a typical starting rate (median of minimums), typical mid rate (median of range "
            "mid-points) and the highest advertised rate. No lender is named or recommended.\n"
            "- **Late payment.** Daily charges are simple interest on the amount due, not compounded. A monthly "
            "rollover adds one month of interest at your rate for every full 30 days late.\n"
            f"- The maths is in [src/loan_math.py]({REPO_URL}/blob/main/src/loan_math.py), checked by hand."
        )


# ------------------------------------------------------------------ page
def header():
    st.title("What will this loan really cost me?")
    st.markdown(
        f"A calculator from my analysis of 20 years of CBN data and Nigerian loan app rates. "
        f"[Read the article]({ARTICLE_URL}) · [See the code on GitHub]({REPO_URL})"
    )
    st.caption(f"Share it: [naija-loan-cost.streamlit.app]({APP_URL})")


def footer():
    st.divider()
    st.caption("This is an educational calculator, not financial advice. It stores nothing and asks for no personal details.")
    st.caption(f"Built by Freedom Oboh with Python and Streamlit · [Article]({ARTICLE_URL}) · [GitHub]({REPO_URL})")


def main():
    st.set_page_config(page_title="Loan cost calculator", page_icon="₦", layout="centered")
    st.info(f"**[The loan calculator now lives in (+234) Money Matters →]({NEW_HOME_URL})**  \n"
            "It has the same maths, bank rates that update every month, and Nigeria's inflation, naira and savings "
            "in one place. This page still works.", icon="➡️")
    init_state()
    header()
    inp = loan_inputs()

    problems = validate(inp)
    if problems:
        for p in problems:
            st.error(p)
        st.info("Fix the loan details in **Step 1** above.")
        footer()
        return

    loan = describe_loan(inp)
    answer(loan)
    breakdown(loan)
    comparison(loan)
    late_payment(loan)
    tips()
    footer()


main()
