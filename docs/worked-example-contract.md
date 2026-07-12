# Example 10: the pinned ratio, two ways

Some experience-rated contracts fix a loss ratio and solve the premium from
it. That inverts the usual build-up — the ratio is the input, the rate is the
output, and the renewal "selection" is formulaic: the one case where the
indication *is* the action, because the contract says so. This page runs the
two standard pins side by side on the same block. Under the **gross** pin,
`claims / premium = LR*`, premium is a function of the claims projection
alone and expenses are exhibit-only. Under the **net** pin,
`claims / (premium − expenses) = LR*`, the dollar expenses are projected
*before* the solve and feed the premium. Same nominal 0.85, materially
different deals — including one that loses money.

The constructors here arrived in `ratingmodels` 0.7.3. Every number on this
page is the output of this exact deterministic run, pinned by regression
tests in the `projectionmodels` and `ratingmodels` suites.

## The pins, as algebra

Both are parameterizations of the fundamental insurance equation. The gross
pin leaves no degree of freedom for expenses:

$$
\frac{C}{P} = \text{LR}^* \;\Longrightarrow\; P = \frac{C}{\text{LR}^*}.
$$

The net pin nets expenses $E = F + VP$ out of the denominator — the dollar
loads $F$ ride the numerator, the percent-of-premium loads $V$ cannot be
"projected first" (they are circular in $P$) and divide instead:

$$
\frac{C}{P - F - VP} = \text{LR}^*
\;\Longrightarrow\;
P = \frac{C/\text{LR}^* + F}{1 - V}.
$$

One consequence worth holding onto: the net pin's margin is
claims-proportional, $P - E - C = C\,(1-\text{LR}^*)/\text{LR}^*$, while the
gross pin makes expenses and margin fight over the same $P(1-\text{LR}^*)$.

## The claims, projected

Twelve months of mature experience, two claim types, type-keyed trend. The
contract pins the *annual* ratio, so the contract-year grain — exposure
weighted — is the one that matters.

```python
import numpy as np
import pandas as pd
from actuarialpy import Experience
import projectionmodels as pm
import ratingmodels as rm

KEYS = ["group_id"]
RENEWAL = pd.Timestamp("2027-07-01")
horizon = pm.ProjectionHorizon("2026-07-01", periods=24)
exposure = pd.DataFrame({
    "group_id": "A",
    "projection_period": pd.period_range("2026-07", periods=24, freq="M").astype(str),
    "member_months": np.linspace(1_000.0, 1_046.0, 24).round(0),
})

months = pd.date_range("2025-07-01", periods=12, freq="MS")
history = pd.DataFrame(
    [{"group_id": "A", "claim_type": ct, "incurred_month": m,
      "reported_claims": base * (1 + tr) ** (i / 12) * 1_000.0,
      "member_months": 1_000.0}
     for ct, base, tr in (("inpatient", 260.0, 0.075),
                          ("outpatient", 190.0, 0.060))
     for i, m in enumerate(months)])

experience = Experience(
    history, expense="reported_claims", exposure="member_months",
    date="incurred_month", dimensions=[*KEYS, "claim_type"])
claim_trend = pm.TrendAssumption.from_values(
    "claim_trend",
    pd.DataFrame({"claim_type": ["inpatient", "outpatient"],
                  "annual_trend": [0.075, 0.060]}),
    lookup=["claim_type"], rate_col="annual_trend")

claims = pm.project(
    experience, exposure=exposure, exposure_col="member_months",
    horizon=horizon, trend=claim_trend,
).project().summarize(by=["group_id", "projection_period"],
                      measures=["member_months", "projected_claims"])
claims["cy"] = np.where(claims["projection_period"] < "2027-07", "CY1", "CY2")

annual = claims.groupby("cy")[["member_months", "projected_claims"]].sum()
c1, c2 = (annual["projected_claims"] / annual["member_months"])[["CY1", "CY2"]]
#  c1 = 497.3488, c2 = 531.5452 — blended claims trend +6.8757%
```

## The expenses that don't need premium

Three of the four expense bases are premium-independent, and all three are
in this retention: a $25 flat fee held flat by a **zero trend keyed to its
expense type**, a care-management fee trending at 3%, and a hospital
surcharge at 8% of projected claims. The surcharge is `percent_claims` — the
claims table joins per period, so each month's surcharge is 8% of *that
month's* claims — and being claims-proportional makes it premium-independent
too. Only the commission, a percent of premium, must wait.

```python
def expense_trend(pairs):
    types, rates = map(list, zip(*pairs, strict=True))
    return pm.TrendAssumption.from_values(
        "expense_trend",
        pd.DataFrame({"expense_type": types, "expense_trend": rates}),
        lookup="expense_type")

dollar = pm.ExpenseProjection(
    pd.DataFrame({"group_id": ["A"] * 3,
                  "expense_type": ["admin_fee", "care_mgmt", "hcra_surcharge"],
                  "base_value": [25.0, 8.0, 0.08],
                  "basis": ["per_exposure", "per_exposure", "percent_claims"],
                  "base_date": pd.Timestamp("2026-07-01")}),
    projection_keys=KEYS, expense_type_col="expense_type",
    base_value_col="base_value", basis_col="basis", base_date_col="base_date",
    horizon=horizon,
    trend=expense_trend([("admin_fee", 0.0),        # contractually flat
                         ("care_mgmt", 0.03),
                         ("hcra_surcharge", 0.0)]),  # the 8% is a rate
    exposure=exposure, exposure_col="member_months",
    claims=claims[["group_id", "projection_period", "projected_claims"]],
).project().summarize(by=["group_id", "projection_period"],
                      measures=["projected_expense"])
dollar["cy"] = np.where(dollar["projection_period"] < "2027-07", "CY1", "CY2")

f1, f2 = (dollar.groupby("cy")["projected_expense"].sum()
          / annual["member_months"])[["CY1", "CY2"]]
#  f1 = 72.9073, f2 = 75.8866 per member-month
```

## The solve, per contract

The only stage where the two contracts differ. Full credibility, because the
contract has already made the selection; the `RateIndication` call is
identical either way — `retention=` absorbs the pin.

```python
gross = rm.RetentionLoad.from_gross_loss_ratio(
    0.85, variable_items={"commission": 0.03})
net_cy1 = rm.RetentionLoad.from_net_loss_ratio(
    0.85, fixed_expense=f1, variable_items={"commission": 0.03})
net_cy2 = rm.RetentionLoad.from_net_loss_ratio(
    0.85, fixed_expense=f2, variable_items={"commission": 0.03})

def solve(contract_cy1, contract_cy2):
    rate1 = contract_cy1.gross_rate(c1)
    action = rm.RateIndication(
        experience_loss_cost=c2, manual_loss_cost=c2, credibility=1.0,
        current_rate=rate1, retention=contract_cy2,
    ).indicated_rate_change()
    return rate1, action

gross_rate1, gross_action = solve(gross, gross)
#  585.1162, +6.8757% — the action IS the claims trend, identically
net_rate1, net_action = solve(net_cy1, net_cy2)
#  678.3747, +6.5667% — the slower expense trend dilutes the action
```

The gross action reproducing the claims trend is not a coincidence, it is
the contract: $P_2/P_1 = C_2/C_1$ when both are $C/\text{LR}^*$. The net
action sits 31 basis points lower because $F$ trends at roughly 1%–3% while
claims trend at 6.9% — expense discipline moderates the renewal, mechanically.

## Premium under the action, and the booking view

Stages three and four never change between pins. Premium projects under the
selected action; then the full expense schedule — commission now included —
runs against the projected premium for the view the year will book.

```python
def project_premium(rate1, action):
    return pm.PremiumProjection(
        premium_data=pd.DataFrame({"group_id": ["A"],
                                   "current_premium_rate": [rate1],
                                   "renewal_date": [RENEWAL]}),
        projection_keys=KEYS, exposure=exposure, exposure_col="member_months",
        horizon=horizon,
        rate_actions=pm.RenewalRateActions(
            frame=pd.DataFrame({"group_id": ["A"], "effective_date": [RENEWAL],
                                "rate_action": [action]}),
            projection_keys=KEYS),
    ).project().summarize(by=["group_id", "projection_period"],
                          measures=["premium"])

def project_booking(premium):
    return pm.ExpenseProjection(
        pd.DataFrame({"group_id": ["A"] * 4,
                      "expense_type": ["admin_fee", "care_mgmt",
                                       "hcra_surcharge", "commission"],
                      "base_value": [25.0, 8.0, 0.08, 0.03],
                      "basis": ["per_exposure", "per_exposure",
                                "percent_claims", "percent_premium"],
                      "base_date": pd.Timestamp("2026-07-01")}),
        projection_keys=KEYS, expense_type_col="expense_type",
        base_value_col="base_value", basis_col="basis", base_date_col="base_date",
        horizon=horizon,
        trend=expense_trend([("admin_fee", 0.0), ("care_mgmt", 0.03),
                             ("hcra_surcharge", 0.0), ("commission", 0.0)]),
        exposure=exposure, exposure_col="member_months",
        claims=claims[["group_id", "projection_period", "projected_claims"]],
        premium=premium[["group_id", "projection_period", "premium"]],
    ).project().summarize(by=["group_id", "projection_period"],
                          measures=["projected_expense"])
```

## The exhibit

Aggregate to the contract year, check the ratio the contract actually pins,
and let the margin say what kind of deal was signed.

```python
def exhibit(pin, rate1, action):
    premium = project_premium(rate1, action)
    booking = project_booking(premium)
    for frame in (premium, booking):
        frame["cy"] = np.where(frame["projection_period"] < "2027-07", "CY1", "CY2")
    C = annual["projected_claims"]
    P = premium.groupby("cy")["premium"].sum()
    E = booking.groupby("cy")["projected_expense"].sum()
    ratio = C / P if pin == "gross" else C / (P - E)
    margin = P * 0.15 - E if pin == "gross" else P - E - C
    return ratio.round(4), margin.round(0)

exhibit("gross", gross_rate1, gross_action)
#  ratio 0.8500 / 0.8500     margin  −32,676 / −10,495
exhibit("net", net_rate1, net_action)
#  ratio 0.8500 / 0.8500     margin  1,064,794 / 1,165,022
```

| | gross pin | net pin |
|---|---:|---:|
| in-force rate | 585.12 | 678.37 |
| renewal action | +6.88% | +6.57% |
| contract ratio, CY1 / CY2 | 0.8500 / 0.8500 | 0.8500 / 0.8500 |
| margin, CY1 | **−32,676** | 1,064,794 |
| margin, CY2 | **−10,495** | 1,165,022 |

Both contracts hold their ratio to the fourth decimal — annually. Monthly,
the ratio wobbles as trend accrues against a rate that steps only at
renewal; asserting the pin at any finer grain than the contract's own is a
false alarm generator. The margins are the story: the same nominal 0.85 is
a 9% premium difference and, with a hospital surcharge riding the expense
stack, the gross-pinned deal is **underwater** — fifteen retention points
cannot cover roughly ninety per-member-month of expenses. The gross pin
never consults the expense projection when setting premium, which is
exactly why the exhibit has to; the net pin prices the expenses in and
banks a claims-proportional margin. Which ratio a contract pins is not a
bookkeeping detail. It is the deal.
