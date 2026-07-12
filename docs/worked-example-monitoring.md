# Example 8: the plan, the actuals, and the miss

The monitoring half of the experience loop: set a plan from last year's rate
basis, watch six months of actuals arrive, and — when a segment runs 6.7%
over — say *why* with claimant-level attribution instead of a shrug. The
whole page is `experiencestudies` over `actuarialpy` primitives: forecast,
actual-versus-expected, the trailing monitor, claimant concentration, a
pooled restatement, and the two-tier underwriting statement, bundled to
Excel at the end. Every number on this page is the output of this exact
fixed-seed run.

## Half a year of claims, member by member

Two segments with member-level claim detail — about 2,850 claimants a month
— trending +7% a year. One PPO member, `P-M4471`, incurs 685,000 across
March–May 2026 (the transplant every block eventually meets):

```python
import numpy as np
import pandas as pd
import actuarialpy as ap
import experiencestudies as es
from actuarialpy import Experience

rng = np.random.default_rng(20260630)
months = pd.date_range("2024-07-01", "2026-06-01", freq="MS")
SHOCK = {"2026-03": 280_000.0, "2026-04": 265_000.0, "2026-05": 140_000.0}
MU = {"ppo": 7.015, "hmo": 6.975}

rows = []
for seg, mm in [("ppo", 3500.0), ("hmo", 6000.0)]:
    for i, m in enumerate(months):
        n = rng.poisson(mm * 0.30)
        mu = MU[seg] + np.log(1.07) * (i / 12)
        for k, amt in enumerate(rng.lognormal(mu, 0.8, size=n)):
            rows.append((seg, m, f"{seg[0].upper()}{i:02d}-{k:04d}", amt))
for key, amt in SHOCK.items():
    rows.append(("ppo", pd.Timestamp(key + "-01"), "P-M4471", amt))
detail = pd.DataFrame(rows, columns=["segment", "month", "member_id", "paid"])

EXPOSURE = {"ppo": 3500.0, "hmo": 6000.0}
P0 = {"ppo": 530.0, "hmo": 505.0}
panel = detail.groupby(["segment", "month"], as_index=False).agg(claims=("paid", "sum"))
panel["member_months"] = panel["segment"].map(EXPOSURE)
i = (panel["month"].dt.year - 2024) * 12 + panel["month"].dt.month - 7
panel["premium"] = panel["segment"].map(P0) * 1.07 ** (i / 12) * panel["member_months"]
panel["expense"] = 44.0 * panel["member_months"]
```

## The plan

The 2026 plan is the calendar-2025 rate basis trended forward — the base
rate per segment, the exposure, and the months from the 2025 midpoint to
each plan month. `forecast_experience` turns that into an expected-claims
column (`expected_from_rate` and `forecast_from_rate` are the elementwise
primitives underneath):

```python
cy25 = panel[panel["month"].dt.year == 2025]
base = (cy25.groupby("segment")[["claims", "member_months"]].sum()
        .assign(rate=lambda d: d["claims"] / d["member_months"]))
# rate: ppo 490.94   hmo 471.96 per member-month

plan = pd.DataFrame(
    [{"segment": s, "month": m, "base_rate": base.loc[s, "rate"],
      "member_months": EXPOSURE[s],
      "months_forward": (m.year - 2025) * 12 + (m.month - 7) + 0.5}
     for s in ("ppo", "hmo")
     for m in pd.date_range("2026-01-01", periods=6, freq="MS")])
plan = es.forecast_experience(plan, rate_col="base_rate",
                              exposure_col="member_months",
                              annual_trend=0.07,
                              months_forward="months_forward")
# ppo expected_rate: 509.27 in January rising to 523.83 in June
```

## Actual versus expected

`compare_actual_to_expected` aligns the two frames;
`summarize_actual_vs_expected` reports the variance in dollars, per
member-month, and as an A/E ratio — sums first, then ratios:

```python
actual = panel[panel["month"].dt.year == 2026].copy()
merged = es.compare_actual_to_expected(
    actual, plan[["segment", "month", "expected_expense"]],
    on=["segment", "month"], actual_col="claims", expected_col="expected_expense")

ave_seg = es.summarize_actual_vs_expected(
    merged, groupby="segment", actual_cols="claims",
    expected_cols="expected_expense", exposure_cols="member_months")
```

| segment | actual | expected | variance | variance PMPM | A/E |
|---|---:|---:|---:|---:|---:|
| hmo | 17,574,301 | 17,875,730 | −301,429 | −8.37 | 0.9831 |
| ppo | 11,568,101 | 10,846,909 | +721,193 | +34.34 | **1.0665** |

The HMO is inside noise. The PPO is 6.7% — 721 thousand — over. The monthly
view is where the honesty starts:

```python
ave_month = es.summarize_actual_vs_expected(
    merged[merged["segment"] == "ppo"], groupby="month", actual_cols="claims",
    expected_cols="expected_expense", exposure_cols="member_months")
```

| month | A/E (ppo) |
|---|---:|
| 2026-01 | 1.018 |
| 2026-02 | 1.082 |
| 2026-03 | 1.173 |
| 2026-04 | 1.090 |
| 2026-05 | 1.095 |
| 2026-06 | 0.942 |

February's 1.082 arrived *before* the member did, and June's 0.942 arrived
while the miss was real: at 3,500 members a single month swings ±4% on pure
sampling noise, so a monthly A/E cannot distinguish a bad draw from a bad
plan. The next two tools can.

## The trailing monitor

The `Experience` binds the column roles once; `es.rolling` is then a
one-liner, and the trailing-twelve window does what monthly A/E cannot —
average out the noise while holding a real event in view for a full year:

```python
exp = Experience(panel, expense="claims", revenue="premium",
                 exposure="member_months", date="month")
roll = es.rolling(exp, 12, groupby="segment")
```

| window ending | trailing LR (ppo) | claims PMPM |
|---|---:|---:|
| 2025-12 | 0.8680 | 490.94 |
| 2026-01 | 0.8714 | 495.68 |
| 2026-02 | 0.8757 | 500.91 |
| 2026-03 | 0.8873 | 510.45 |
| 2026-04 | 0.8909 | 515.39 |
| 2026-05 | 0.8970 | 521.83 |
| 2026-06 | 0.8939 | 522.97 |

Premium is on-trend, so the pre-event windows sit flat near 0.87; the March
window jumps 1.2 points and the level *stays* — a step, not a spike, which
is the trailing monitor's signature for a discrete event inside the window.

## Whose claims are these

The attribution question is claimant-level. Aggregate to members, rank,
and measure the concentration:

```python
h1 = detail[detail["month"].dt.year == 2026]
byc = es.summarize_claimants(h1, claimant_col="member_id",
                             amount_cols="paid", groupby="segment")
top = es.top_claimants(h1, claimant_col="member_id", amount_cols="paid",
                       groupby="segment", n=3)
conc = es.claim_concentration(byc, groupby="segment",
                              thresholds=[100_000, 250_000])
```

| segment | member | total | rank | share of segment |
|---|---|---:|---:|---:|
| ppo | P-M4471 | 685,000 | 1 | 0.0592 |
| ppo | P20-0118 | 27,581 | 2 | 0.0024 |
| ppo | P23-0305 | 20,801 | 3 | 0.0018 |
| hmo | H20-0836 | 22,841 | 1 | 0.0013 |

The top PPO claimant is 25 times the second — this is not a thick tail, it
is one member. `claim_concentration` says the same thing as a threshold
statement (one claimant over 250,000 carrying 5.9% of the segment; the HMO
has none), and `large_claimant_flags(byc, thresholds=[100_000, 250_000])`
marks the row for downstream pooling or case-management workflows.

## Pool it, and re-ask the question

Claimant-level pooling is one call —
`es.pool_claimants(exp, "member_id", 250_000)` or, on the claimant summary,
the `actuarialpy` primitive it delegates to:

```python
pooled = ap.pool_losses(byc, loss_col="total_expense", pooling_point=250_000.0)
pooled[pooled["member_id"] == "P-M4471"]
#  segment  member_id     paid  total_expense  pooled_loss  excess_loss
#      ppo    P-M4471  685,000        685,000      250,000      435,000

excess = pooled.groupby("segment")["excess_loss"].sum()   # ppo 435,000
```

Now the miss has an attribution ladder — the same A/E, asked three ways:

| basis | ppo A/E |
|---|---:|
| as reported | 1.0665 |
| excess over 250k pooled out | 1.0264 |
| excluding member P-M4471 entirely | 1.0033 |

One member explains 95% of the variance; the block itself is on plan to a
third of a point. The middle rung is the actionable one: even *pooled*, the
member's retained 250,000 is 2.3 points of A/E — and the plan carried no
provision for it. The missing provision has a price: 435,000 of excess over
21,000 member-months is **20.71 PMPM**, which is precisely the pooling
charge that [Example 7](worked-example-projection.md) carries as a rate
load and that [Example 3](worked-example.md) and
[Example 6](worked-example-tail.md) price from a severity model. The
monitoring loop did not just explain the miss — it produced next year's
assumption.

## The half-year, booked

The two-tier underwriting statement — gross margin (revenue less loss) and
gain (less operating expense), every denominator explicit, all ratios
ratios-of-sums per the
[shared definitions](conventions.md#margin-and-denominators):

```python
uw = es.underwriting_summary(
    actual, groupby="segment",
    revenue_cols="premium", loss_cols="claims", expense_cols="expense",
    exposure_col="member_months", premium_col="premium")
```

| segment | loss ratio | expense ratio | combined | gain ratio |
|---|---:|---:|---:|---:|
| hmo | 0.8611 | 0.0776 | 0.9387 | +0.0613 |
| ppo | 0.9259 | 0.0740 | 0.9998 | **+0.0002** |

The shock consumed the PPO segment's entire half-year gain — a combined
ratio of 0.9998, two basis points from breakeven — while the HMO earned its
6.1%. That asymmetry, one member wide, is the argument for the pooling
charge in one row.

## Ship it

Every view on this page is a plain DataFrame, so the monitoring pack is one
call — a workbook with one sheet per view:

```python
es.to_excel_report(
    {"ave_by_segment": ave_seg, "ave_ppo_monthly": ave_month,
     "rolling_12m": roll, "top_claimants": top,
     "concentration": conc, "underwriting": uw},
    "h1_monitor.xlsx")
```

(`to_excel_report` needs the `excel` extra:
`pip install "experiencestudies[excel]"`.)
