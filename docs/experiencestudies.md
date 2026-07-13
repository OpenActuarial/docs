# experiencestudies

The study layer of the ecosystem: experience summaries and views,
actual-versus-expected and simple forecasting, claimant and concentration
analysis, cohort and duration studies, driver and frequency–severity
decomposition, rolling monitors, banded summaries, and the two-tier
underwriting income statement — study functions over the canonical
[`actuarialpy.Experience`](actuarialpy.md). Where [actuarialpy](actuarialpy.md) answers "what is the loss ratio /
development factor / credibility weight for this table?", `experiencestudies`
answers "how is this block performing, why is it moving, and where is the risk
concentrated?". It does not perform data preparation or encode filed
methodology: the caller supplies the tidy table and selects the analysis.
Every result is a DataFrame or Series.

There are two interfaces. The **free functions** — `summarize_experience`,
`summarize_actual_vs_expected`, `summarize_claimants`, `cohort_summary`,
`decompose_per_exposure_trend`, `frequency_severity_summary`,
`rolling_summary`, `summarize_by_band`, and the forecasting helpers — each
take a DataFrame and return a DataFrame. The **study functions** — `summary`,
`views`, `rolling`, `margin`, `claimants`, `pool_claimants`,
`actual_vs_expected`, `decompose_trend`, and friends — take the canonical
`Experience`, which remembers the expense, revenue, exposure, and date
columns once — the recommended path for any multi-step analysis, with the free functions as the low-level escape hatch for one-off calculations. Its restatements (`adjust`, `deseasonalize`, `complete`,
`filter`, `with_status`) live on the object in `actuarialpy` and each return
a new `Experience`, so adjustments compose without mutating the source.

## Quickstart

```python
import pandas as pd
from actuarialpy import Experience

import experiencestudies as es
from experiencestudies import summarize_experience

df = pd.DataFrame({
    "month": pd.date_range("2025-01-01", periods=12, freq="MS"),
    "lob": ["auto"] * 6 + ["property"] * 6,
    "claims": [820, 910, 875, 1010, 990, 1105, 380, 395, 402, 410, 425, 440.0],
    "premium": [1500.0] * 6 + [600.0] * 6,
    "earned_units": [1000] * 12,
})

# recommended: bind the column roles once, then every view derives from them
exp = Experience(df, expense="claims", revenue="premium",
                 exposure="earned_units", date="month")
es.summary(exp, "lob")   # grouped experience summary
es.rolling(exp, 3)       # trailing three-month monitor

# low-level: the same summary straight from a DataFrame, columns named explicitly
summarize_experience(
    df, groupby="lob",
    expense_cols="claims", revenue_cols="premium", exposure_cols="earned_units",
)
#  lob      | earned_units | ... | loss_ratio
#  auto     |         6000 | ... |     0.6344
#  property |         6000 | ... |     0.6811
```

Per-exposure output columns are the mechanical `{name}_per_{exposure_col}`;
domain names (a health shop's `mlr` or `_pmpm`) are opt-in via `profile` /
`labels` on the output views, never in the calculation.

## Restatements compose

Adjustments return a new `Experience`, so a restated view is a chain. The
seasonal and completion factors come from `actuarialpy`
(`seasonality_factors`, `completion_factors`) and are applied on the
`Experience` itself:

```python
restated = (
    exp.adjust(1.03)                      # apply a 3% trend/restatement factor
       .deseasonalize(seasonal_factors)   # divide out a seasonal shape
       .complete(completion_factors, valuation_date="2025-12-31")  # gross up to ultimate
)
es.summary(restated, "lob")               # terminal summary of the restated view
```

Binding `count` (a claim or service count) unlocks the frequency–severity
views: `frequency_severity()` and `decompose_trend()`, which splits a
per-exposure movement into exact frequency, severity, and (optionally) mix
effects — [Example 1](worked-example-experience.md) runs both on a full
panel.

## Claimants and concentration

Identify and rank large claimants, and measure how concentrated the losses
are:

```python
import experiencestudies as es

by_claimant = es.summarize_claimants(claims, claimant_col="claimant_id",
                                     amount_cols="paid")

es.top_claimants(claims, claimant_col="claimant_id", amount_cols="paid", n=3)
#  claimant_id |     paid | rank | share_of_total | cumulative_share
#  m1        | 550,000  |    1 |         0.7534 |           0.7534
#  m2        |  96,000  |    2 |         0.1315 |           0.8849
#  m5        |  61,000  |    3 |         0.0836 |           0.9685

es.claim_concentration(by_claimant, top_n=[1, 3], thresholds=[100_000])
# claimant_count | total_amount | ... | amount_over_100000 | share_over_100000
```

`large_claimant_flags` marks claimants over a threshold for downstream
pooling or exclusion work.

## Actual versus expected and forecasting

`expected_from_rate` and `forecast_from_rate` build expected or forecast
values from a rate basis; `forecast_experience` applies them across a frame;
`compare_actual_to_expected` aligns the actuals against the plan and
`summarize_actual_vs_expected` reports the variance in dollars, per
exposure, and as an actual-to-expected ratio — sums first, then ratios:

```python
plan = es.forecast_experience(basis, rate_col="base_rate",
                              exposure_col="member_months",
                              annual_trend=0.07,
                              months_forward="months_forward")

merged = es.compare_actual_to_expected(
    actual, plan[["segment", "month", "expected_expense"]],
    on=["segment", "month"],
    actual_col="claims", expected_col="expected_expense")

es.summarize_actual_vs_expected(merged, groupby="segment",
                                actual_cols="claims",
                                expected_cols="expected_expense",
                                exposure_cols="member_months")
#  segment |     actual |   expected | variance | variance_per_member_months | actual_to_expected
#  hmo     | 17,574,301 | 17,875,730 | -301,429 |                      -8.37 |             0.9831
#  ppo     | 11,568,101 | 10,846,909 | +721,193 |                     +34.34 |             1.0665
```

[Example 8](worked-example-monitoring.md) runs the whole monitoring cycle —
plan, A/E, trailing monitor, claimant attribution of the miss, and a pooled
restatement. The same frame shape runs a mortality or lapse study
unchanged: actuals are deaths or lapses, the expected column is a table
rate times exposure, and the A/E ratio is the study's headline. (For full
multi-period claim, premium, and expense projections with renewal rate
actions and scenarios, use [projectionmodels](projectionmodels.md).)

## Underwriting income statement

`underwriting_summary` (and the `UnderwritingSummary` object) build the
two-tier underwriting result — **gross margin** (revenue less loss expense,
operating expense excluded) and **gain/(loss)** (gross margin less operating
expense) — with each ratio's denominator an explicit parameter, since real
exhibits mix them. The shared definitions are pinned on the
[conventions](conventions.md#margin-and-denominators) page.

```python
es.underwriting_summary(
    book, groupby="cohort",
    revenue_cols=["premium", "refund"], loss_cols="claims",
    expense_cols="expense", exposure_col="member_months",
    premium_col="premium",
)
#  cohort   | ... | loss_ratio | expense_ratio | combined_ratio | gain_ratio
#  existing | ... |     0.8223 |        0.0903 |         0.9126 |     0.0871
#  new      | ... |     0.8904 |        0.1267 |         1.0172 |    -0.0173
```

Components are summed first, so every ratio is a ratio of sums, and the
identity `gain ratio = 1 − combined ratio` holds exactly whenever all ratios
share one denominator.

## Reporting

`to_excel_report` writes a dict of named views to a multi-sheet Excel
workbook (one sheet per key). The values are plain DataFrames, so any summary
on this page — grouped experience, an underwriting statement, a rolling
monitor — can be a sheet:

```python
es.to_excel_report(
    {"experience": es.summary(exp, "lob"),
     "rolling_12m": es.rolling(exp, 12, groupby="lob"),
     "underwriting": uw},
    "monitoring_pack.xlsx")
```

It needs the `excel` extra:

```bash
pip install "experiencestudies[excel]"
```

## Relationship to actuarialpy

`experiencestudies` depends on `actuarialpy` and never the other way around —
the dependency is strictly one-directional. The size-banding split is the
clearest example: the `assign_band` primitive lives in `actuarialpy`, while
`summarize_by_band` (which needs an experience summary) lives here. The same
split holds throughout: credibility, trend, completion, and seasonality are
computed by the core, and this package composes them into studies.

## API reference

```{eval-rst}
.. automodule:: experiencestudies
   :members:
```
