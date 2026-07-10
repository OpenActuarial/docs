# Example 7: the renewal cycle, projected

The loop at the center of the [workflow diagram](overview.md#the-workflow), run
once around: three years of monthly claim history in, estimated assumptions,
a credibility-blended claim projection (`projectionmodels`), a rate indication
and capped renewal actions (`ratingmodels`), and those same actions fed back as
effective-dated `RenewalRateActions` into the premium and expense projections —
because you project the rates you set. The output is the exhibit every renewal
meeting wants: the loss-ratio path for the coming year, quarter by quarter,
with the cap and the calendar both priced. Every number on this page is the
output of this exact fixed-seed run.

## Three years of history

Two groups on one block — A large (5,000 member-months a month), B small (700)
and running 8% hotter — with inpatient and outpatient claims, +6.5% and +8.0%
annual trends, a planted seasonal shape peaking in December, and the last
three incurred months still developing (55% / 85% / 96% reported):

```python
import numpy as np
import pandas as pd
import projectionmodels as pm
import ratingmodels as rm
from projectionmodels.integrations import actuarialpy as apx

rng = np.random.default_rng(20270101)
months = pd.date_range("2024-01-01", "2026-12-01", freq="MS")
SEASON = np.array([0.97, 0.95, 0.99, 0.98, 1.00, 1.00,
                   0.99, 1.00, 1.01, 1.03, 1.04, 1.06])
VALUATION = pd.Timestamp("2026-12-31")
COMPLETION = {0: 0.55, 1: 0.85, 2: 0.96}      # months of maturity -> share reported

rows = []
for group, mm, level in [("A", 5000.0, 1.00), ("B", 700.0, 1.08)]:
    for ct, base, tr in [("inpatient", 175.0, 0.065), ("outpatient", 260.0, 0.080)]:
        for i, m in enumerate(months):
            rate = base * level * (1 + tr) ** (i / 12) * SEASON[m.month - 1]
            rate *= 1 + rng.normal(0, 0.02)
            maturity = (VALUATION.year - m.year) * 12 + VALUATION.month - m.month
            rows.append((group, ct, m, rate * mm * COMPLETION.get(maturity, 1.0), mm))
hist = pd.DataFrame(rows, columns=["group_id", "claim_type", "incurred_month",
                                   "reported_claims", "member_months"])
```

A payment-transaction extract supplies the raw material for completion —
eight origins, each paying out 55 / 30 / 11 / 4 over four development months:

```python
tx = pd.DataFrame(
    [(ct, o, o + pd.DateOffset(months=d), 1_000_000.0 * (1 + 0.02 * i) * s)
     for ct in ("inpatient", "outpatient")
     for i, o in enumerate(pd.date_range("2026-01-01", periods=8, freq="MS"))
     for d, s in enumerate((0.55, 0.30, 0.11, 0.04))],
    columns=["claim_type", "incurred_month", "paid_month", "paid"])
tx = tx[tx["paid_month"] <= VALUATION]
```

## Estimate the assumptions

Estimation is explicit and separate from projection execution: each
`projectionmodels.integrations.actuarialpy` adapter runs the corresponding
core primitive and returns an assumption object that keeps the indicated
values, the selection, and the diagnostics. Seasonality and trend are
estimated where they are believed to live — at claim-type level, book-wide —
so the history is aggregated to that grain first; credibility is per group,
on an exposure frame that does not double-count member-months across claim
types:

```python
completion = apx.estimate_completion(
    "claim_completion", tx, by=["claim_type"],
    origin_col="incurred_month", valuation_col="paid_month", amount_col="paid")

panel = hist.groupby(["claim_type", "incurred_month"], as_index=False).agg(
    reported_claims=("reported_claims", "sum"),
    member_months=("member_months", "sum"))
completed = completion.apply(panel, value_col="reported_claims",
                             date_col="incurred_month", valuation_date=VALUATION,
                             by=["claim_type"], out_col="completed_claims")

seasonality = apx.estimate_seasonality(
    "claim_seasonality", completed, by=["claim_type"],
    date_col="incurred_month", value_col="completed_claims",
    exposure_col="member_months")
deseason = apx.remove_seasonality(completed, seasonality,
                                  date_col="incurred_month",
                                  value_col="completed_claims",
                                  by=["claim_type"],
                                  out_col="deseasonalized_claims")
trend = apx.estimate_trend(
    "claim_trend", deseason, by=["claim_type"],
    date_col="incurred_month", value_col="deseasonalized_claims",
    exposure_col="member_months")

exposure_hist = hist.drop_duplicates(["group_id", "incurred_month"])
credibility = apx.estimate_credibility(
    "claim_credibility", exposure_hist, method="limited_fluctuation",
    by=["group_id"], exposure_col="member_months",
    full_credibility_standard=120_000.0)
```

The generator's assumptions come back:

| assumption | planted | estimated |
|---|---|---|
| completion (both types) | 0.55 / 0.85 / 0.96 / 1.00 | 0.55 / 0.85 / 0.96 / 1.00 — exact |
| inpatient trend | +6.5% | +6.51% |
| outpatient trend | +8.0% | +7.98% |
| December factor | 1.06 | 1.055 (IP), 1.063 (OP) |
| February factor | 0.95 | 0.945 (IP), 0.933 (OP) |
| credibility Z | — | A 1.000, B 0.458 |

B's 0.458 is exactly $\sqrt{25{,}200 / 120{,}000}$ — 36 months of 700
member-months against the full-credibility standard.

## Project the claims

`ClaimExperience` reads the history; `ClaimProjection.from_experience` runs
the pipeline in its
[fixed order](projectionmodels.md#cost-levels-and-pipeline-order) — complete
→ deseasonalize → trend to the blend basis → credibility blend →
trend to each period → reseasonalize → add rate loads → multiply by
exposure. The complement is a manual rate quoted at the prospective basis,
and the 14.50 PMPM rate load is a selected pooling charge — the book-level
excess analysis that produces such a number is
[Example 3](worked-example.md) and [Example 6](worked-example-tail.md), and
the pooled-basis recipe is in the `projectionmodels` repository's
`pooled_claims` example:

```python
horizon = pm.ProjectionHorizon("2027-01-01", periods=12)
periods = pd.period_range("2027-01", periods=12, freq="M").astype(str)
exposure = pd.DataFrame(
    [{"group_id": g, "projection_period": p, "member_months": mm}
     for g, mm in (("A", 5000.0), ("B", 700.0)) for p in periods])

experience = pm.ClaimExperience(
    hist, projection_keys=["group_id"], claim_type_col="claim_type",
    date_col="incurred_month", claims_col="reported_claims",
    exposure_col="member_months", valuation_date=VALUATION)
manual = pm.Assumption(
    "manual_claim_rate",
    pd.DataFrame({"claim_type": ["inpatient", "outpatient"],
                  "manual_claim_rate": [215.0, 335.0]}),
    lookup=["claim_type"], value_col="manual_claim_rate")

claim_projection = pm.ClaimProjection.from_experience(
    experience, exposure=exposure, exposure_col="member_months",
    horizon=horizon, completion=completion, seasonality=seasonality,
    trend=trend, credibility=credibility, complement=manual,
    rate_loads=(14.50,))
claim_results = claim_projection.project(
    scenarios=[pm.Scenario("baseline"),
               pm.Scenario("adverse", [pm.Adjustment(target="claim_trend",
                                                     method="add", value=0.02)])])
```

Every stage is a named column in the detail frame. One row — group B,
inpatient, July 2027 — is the whole audit trail:

```python
claim_results.to_frame()          # one row per key x claim type x period
```

| column | value |
|---|---:|
| `experience_claim_rate` | 208.01 |
| `trended_experience_rate` | 236.63 |
| `complement_claim_rate` | 215.00 |
| `claim_credibility` | 0.4583 |
| `credible_claim_rate` | 224.91 |
| `claim_seasonality` | 0.9945 |
| `rate_load_1` | 14.50 |
| `projected_claim_rate` | 238.75 |

The small group's hot experience (236.63 trended) is pulled 46% of the way
toward the 215 manual; group A, fully credible, carries its own 218.37
untouched. Summarized over the calendar year:

```python
cy = claim_results.summarize(by=["scenario", "group_id"],
                             measures=["member_months", "projected_claims",
                                       "claims_per_exposure"])
#  scenario group_id  member_months  projected_claims  claims_per_exposure
#  baseline        A         60,000        35,423,179               590.39
#  baseline        B          8,400         5,081,172               604.90
#   adverse        A         60,000        36,724,550               612.08
#   adverse        B          8,400         5,171,891               615.70
```

## Set the rates

The projected loss cost drives the indication. The credibility blend already
happened inside the projection, so the indication receives one number per
group — passing `credibility=1.0` makes `RateIndication` a pure gross-up
through the retention. Claim administration is 1.2% of claims, so it rides
the loss cost; the [vectorization
contract](conventions.md#vectorization-contract) prices both groups in one
call, and `renew` applies a 10% corridor:

```python
base_lc = (cy[cy["scenario"] == "baseline"]
           .set_index("group_id")["claims_per_exposure"])
current = pd.Series({"A": 585.0, "B": 612.0}, name="current")
retention = rm.RetentionLoad(fixed_expense=24.0, variable_expense_ratio=0.030,
                             profit_margin=0.02)
indication = rm.RateIndication(
    experience_loss_cost=base_lc * 1.012,   # claim admin rides the claims
    manual_loss_cost=base_lc * 1.012,       # blend already applied upstream
    credibility=1.0,
    current_rate=current,
    retention=retention)

action = rm.renew(current, indication.indicated_rate(), cap=0.10, floor=0.0)
action.to_frame()
#    current_rate  indicated_rate  proposed_rate  indicated_change  proposed_change  capped
# A         585.0          654.18         643.50            0.1183           0.1000    True
# B         612.0          669.64         669.64            0.0942           0.0942   False
```

The large group needed +11.8% and the corridor released 10; the small group's
manual blend kept its indication inside the cap, so B renews at formula. One
honesty note about that step: in production, indicated-to-selected is a
renewal-strategy decision — cohort performance, persistency risk,
competitive position, underwriting judgment — that the indication informs
rather than determines. `renew`'s cap-and-floor is a mechanical stand-in
for that selection here, and `RenewalRateActions` below will carry whatever
the forum actually issues.

## Project the premium you will actually charge

The issued actions — not the indicated ones — become an effective-dated
`RenewalRateActions` table, keyed to each group's renewal date. This is the
loop closing: the selected actions, wherever they were decided, are the
premium projection's input.

```python
actions = pm.RenewalRateActions(
    pd.DataFrame({"group_id": ["A", "B"],
                  "effective_date": pd.to_datetime(["2027-04-01", "2027-09-01"]),
                  "rate_action": action.proposed_change.to_numpy()}),
    projection_keys=["group_id"])

premium_results = pm.PremiumProjection(
    premium_data=pd.DataFrame({
        "group_id": ["A", "B"],
        "renewal_date": pd.to_datetime(["2027-04-01", "2027-09-01"]),
        "current_premium_rate": current.to_numpy()}),
    projection_keys=["group_id"],
    exposure=exposure, exposure_col="member_months", horizon=horizon,
    rate_actions=actions).project()

pdet = premium_results.detail()
pdet.loc[pdet["is_renewal_period"],
         ["group_id", "projection_period", "projected_premium_rate", "premium"]]
#  group_id projection_period  projected_premium_rate    premium
#         A           2027-04                  643.50  3,217,500
#         B           2027-09                  669.64    468,748
```

## Expenses, and the year as it will book

`ExpenseProjection` handles the three bases in one table — per-exposure
administration, commission as a percent of the projected premium, claim
administration as a percent of the projected claims — each trended from its
base date. The claim and premium projections feed it directly:

```python
expenses = pd.DataFrame(
    [{"group_id": g, "expense_type": et, "base_value": v, "basis": b,
      "base_date": pd.Timestamp("2027-01-01")}
     for g in ("A", "B")
     for et, v, b in (("administration", 24.0, "per_exposure"),
                      ("commission", 0.030, "percent_premium"),
                      ("claim_admin", 0.012, "percent_claims"))])

claims_pp = claim_results.summarize(
    by=["scenario", "group_id", "projection_period", "calendar_quarter"],
    measures=["member_months", "projected_claims"])
claims_base_pp = claims_pp[claims_pp["scenario"] == "baseline"]
premium_pp = premium_results.summarize(
    by=["group_id", "projection_period", "calendar_quarter"],
    measures=["premium"])

expense_pp = pm.ExpenseProjection(
    expenses=expenses, projection_keys=["group_id"],
    expense_type_col="expense_type", base_value_col="base_value",
    basis_col="basis", base_date_col="base_date", horizon=horizon,
    trend=pm.TrendAssumption.from_values("expense_trend", 0.03),
    exposure=exposure, exposure_col="member_months",
    premium=premium_pp[["group_id", "projection_period", "premium"]],
    claims=claims_base_pp[["group_id", "projection_period", "projected_claims"]],
).project().summarize(by=["group_id", "projection_period", "calendar_quarter"],
                      measures=["projected_expense"])
```

Merging the three projections on the shared period keys gives the exhibit —
the forward loss-ratio and gain path, with each renewal visibly landing:

```python
frame = (claims_base_pp
         .merge(premium_pp, on=["group_id", "projection_period", "calendar_quarter"])
         .merge(expense_pp, on=["group_id", "projection_period", "calendar_quarter"]))
q = frame.groupby(["group_id", "calendar_quarter"], as_index=False)[
    ["projected_claims", "premium", "projected_expense"]].sum()
q["loss_ratio"] = q["projected_claims"] / q["premium"]
q["gain_ratio"] = (q["premium"] - q["projected_claims"]
                   - q["projected_expense"]) / q["premium"]
```

| group | quarter | loss ratio | gain ratio |
|---|---|---:|---:|
| A | Q1 | 0.9535 | −0.0363 |
| A | Q2 | 0.8994 | **+0.0216** |
| A | Q3 | 0.9283 | −0.0082 |
| A | Q4 | 0.9752 | −0.0563 |
| B | Q1 | 0.9338 | −0.0145 |
| B | Q2 | 0.9689 | −0.0507 |
| B | Q3 | 0.9697 | −0.0508 |
| B | Q4 | 0.9603 | −0.0397 |

The shape is the story. A's April renewal lands hard — Q2 posts the 2%
target and change — then annual trend and the Q4 seasonal peak erode it
against a rate that stays flat until next April. B's September action
arrives too late to rescue its year. For the renewal year as a whole, A
books a 0.939 loss ratio and a −1.9% gain, B 0.958 and −3.9%: the rate was
priced to the calendar-year average cost level, but the actions earn in
mid-year while trend runs all year. The exhibit does not hide that timing —
it prices it.

## The adverse world

The `adverse` scenario added two points of claim trend at projection time;
`compare_scenarios` reads the cost straight off the results:

```python
claim_results.compare_scenarios(baseline="baseline", comparison="adverse",
                                by="group_id", measures="projected_claims")
#  group_id   baseline    comparison     change   pct_change
#         A  35,423,179   36,724,550  1,301,371       0.0367
#         B   5,081,172    5,171,891     90,719       0.0179
```

Two points of trend cost A 3.7% of claims but B only 1.8% — and that is not
noise, it is the blend. The complement is quoted at the prospective basis,
so it does not move when trend moves; only B's 46% experience share rides
the extra trend back from the experience midpoint. Credibility does not just
stabilize the estimate — it dampens the small group's trend risk, and the
scenario machinery makes that visible in one call. At the issued rates the
adverse year books at 0.973 (A) and 0.975 (B): about 3.4 and 1.7 points of
loss ratio, which is what "+2 points of trend" actually costs this block.
