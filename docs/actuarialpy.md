# actuarialpy

Shared actuarial primitives and general tooling — the calculation core the
rest of the ecosystem builds on. Ratios and per-exposure metrics, chain-ladder
development and IBNR, credibility, trend, seasonal factors, financial
mathematics, exposure and lifecycle bases, size banding, pooling, margins, and
weighted rollups, applied to claims, exposure, and premium data. It does not
perform data preparation or encode filed methodology: the caller supplies the
table and selects the method. Every result is a DataFrame or Series, and the
only dependencies are numpy and pandas.

The *study layer* that builds on these primitives — the fluent `Experience`
object, experience summaries, actual-versus-expected, claimant, cohort, and
decomposition analyses, and the underwriting income statement — lives in
[experiencestudies](experiencestudies.md), which depends on `actuarialpy` and
never the other way around.

## Quickstart

Pass an aggregate at the grain you are analysing and call the primitive you
need — the free functions accept scalars, numpy arrays, or pandas Series and
return the same type:

```python
import pandas as pd
import actuarialpy as ap

ap.loss_ratio(1_240_000, 1_500_000)     # 0.827
ap.per_exposure(1_240_000, 12_000)      # 103.33 per exposure unit
ap.severity(1_240_000, 3_875)           # 320.00 per claim

# fit a trend on a monthly panel and project it forward
monthly = pd.DataFrame({
    "month": pd.date_range("2025-01-01", periods=12, freq="MS"),
    "loss_ratio": [0.802, 0.810, 0.807, 0.815, 0.818, 0.822,
                   0.825, 0.831, 0.828, 0.836, 0.840, 0.845],
})
fit = ap.fit_trend(monthly, date_col="month", value_col="loss_ratio")
fit.annual_trend                                     # 0.0552
fit.r_squared                                        # 0.974
ap.project_forward(0.845, fit.annual_trend, months=12)   # 0.8916
ap.trend_factor(fit.annual_trend, months=18)             # 1.0839
```

Build the aggregate with pandas at the grain that matches the question —
typically a single `groupby` that sums claims, counts exposure from the
exposure table, and joins premium. For repeated experience-analysis
workflows on such a table, the fluent `Experience` object in
[experiencestudies](experiencestudies.md) binds the column roles once and
derives every view from them.

## Credibility

Credibility primitives live here — `experiencestudies`, `projectionmodels`,
and `ratingmodels` delegate to them rather than re-implementing.
Limited-fluctuation (classical) credibility from exposure:

```python
import actuarialpy as ap

z = ap.limited_fluctuation_z(exposure=96_000, full_credibility_standard=120_000)
# -> 0.894
```

Greatest-accuracy (Bühlmann–Straub) credibility across risk classes, fit
straight from a tidy frame of group / value / weight:

```python
import pandas as pd
import actuarialpy as ap

exp = pd.DataFrame({
    "product": ["motor", "motor", "marine", "marine"],
    "paid":    [125_000, 130_000, 88_000, 91_000],
    "exposure": [1010, 1008, 640, 655],
})

model = ap.BuhlmannStraub.from_frame(
    exp, group="product", value="paid", weight="exposure",
)

model.k                    # Bühlmann k = EPV / VHM
model.z(weight=1_000)      # credibility Z for 1,000 units of exposure
```

`model.premium(risk_mean, weight)` then blends a class's own mean toward the
overall mean at that credibility.

## Financial mathematics

Time value of money on the same numpy/pandas footing — rate conversions,
present/future values, annuities-certain, loan amortization, and day-count
conventions:

```python
import actuarialpy as ap

ap.present_value(1000, 0.05, 3)          # 863.84  — discount at 5% for 3 yrs
ap.future_value(1000, 0.05, 3)           # 1157.63
ap.annuity_immediate(0.05, 10)           # 7.7217  — PV of 1/yr, 10 yrs @ 5%
ap.annuity_due(0.05, 10)                 # 8.1078

# a deferred pension: 30k a year for 25 years, first payment in 20 years
30_000 * ap.annuity_due(0.045, 25) * ap.discount_factor(0.045, 20)
                                         # 192,752.68

# level-payment loan: 200k principal, 6% nominal, 30 years monthly
ap.level_payment(200_000, 0.06 / 12, 360)          # 1199.10 per month
ap.amortization_schedule(200_000, 0.06 / 12, 360)  # full schedule (DataFrame)

ap.year_fraction("2024-01-01", "2024-07-01", convention="30/360")  # 0.5
```

The element-wise functions honor the ecosystem [vectorization
contract](conventions.md#vectorization-contract): a scalar rate returns a
`float`, while a numpy array or pandas Series returns the same kind on the same
index — so a per-scenario or per-period rate column maps straight to a result
column. The cash-flow reductions (`net_present_value`, `internal_rate_of_return`,
`present_value_curve`) take a whole stream and return a scalar; everything else
mirrors its input.

```python
import pandas as pd

rates = pd.Series([0.03, 0.05, 0.07], index=["low", "base", "high"], name="rate")

ap.discount_factor(rates, 10)     # Series on the same index: 0.7441, 0.6139, 0.5083
ap.annuity_immediate(rates, 20)   # Series: 14.8775, 12.4622, 10.5940

# assign results straight back onto a scenario frame
book = pd.DataFrame({"rate": [0.03, 0.05, 0.07]})
book["discount_10y"] = ap.discount_factor(book["rate"], 10)
book["annuity_20y"] = ap.annuity_immediate(book["rate"], 20)
```

## Exposure and age bases

Exact and rounded ages, and exposure-years over a study window — the inputs an
actual-to-expected study needs:

```python
import pandas as pd
import actuarialpy as ap

ap.age("1980-06-15", "2026-06-30")                   # 46.04  — exact
ap.age("1980-06-15", "2026-06-30", basis="last")     # 46     — age last birthday
ap.age("1980-06-15", "2026-06-30", basis="nearest")  # 46     — age nearest birthday

# fraction of a study window each life is exposed
cohort = pd.DataFrame({
    "entry": ["2024-03-01", "2024-01-15"],
    "term":  ["2025-09-01", "2025-12-31"],
})
ap.add_exposure_column(cohort, entry_col="entry", exit_col="term",
                       study_start="2024-01-01", study_end="2025-12-31")
```

## Pooling and retention

Row-level pooling is one call — `pool_losses` splits each loss at the
pooling point into a retained and an excess column, leaving attribution to
the caller ([Example 8](worked-example-monitoring.md) runs it at claimant
level, [Example 2](worked-example-book.md) uses the grouped `ratingmodels`
wrapper on a claim file):

```python
import pandas as pd
import actuarialpy as ap

claims = pd.DataFrame({"claim_id": [1, 2, 3],
                       "paid": [80_000.0, 310_000.0, 95_000.0]})
ap.pool_losses(claims, loss_col="paid", pooling_point=250_000.0)
#  claim_id     paid  pooled_loss  excess_loss
#         1   80,000       80,000            0
#         2  310,000      250,000       60,000
#         3   95,000       95,000            0
```

The module also includes two retention-stability primitives:
`retained_cv(outcomes, retention, n_units)` is the coefficient of variation
of the retained aggregate of `n_units` i.i.d. units each capped at
`retention`, and `retention_for_target_cv` inverts it — the retention at
which retained volatility hits a target, which is the basis for a
size-graded pooling schedule:

```python
import numpy as np

rng = np.random.default_rng(3)
outcomes = rng.lognormal(9.0, 1.4, size=20_000)   # per-unit annual outcomes

ap.retained_cv(outcomes, retention=100_000, n_units=40)   # 0.2119
ap.retained_cv(outcomes, retention=250_000, n_units=40)   # 0.2735

ap.retention_for_target_cv(outcomes, n_units=40, target_cv=0.10)    # 14,912
ap.retention_for_target_cv(outcomes, n_units=160, target_cv=0.10)   # 83,652
```

Raising the retention raises the retained CV — more volatile large claims
kept — and the inverse call reads a schedule straight off the data: at a 10%
stability standard, four times the units supports a five-and-a-half-times
retention.

## Weighted rollups

Quantities that are already rates at the row level — rate actions,
persistency — cannot be summed. `weighted_mean` and `weighted_summary`
average them with a **required, named weight** and report the weight total
beside every average:

```python
ap.weighted_summary(book, value_cols="rate_action",
                    weight_col="premium", groupby="cohort")
```

The composed two-tier underwriting income statement that used to sit beside
these rollups (`UnderwritingSummary`, `underwriting_summary`) now lives in
[experiencestudies](experiencestudies.md) — it is an assembled report rather
than an atomic calculation. The margin *primitives* (`margin`, `margin_ratio`,
`add_margin`) remain here, and the shared margin definitions are on the
[conventions](conventions.md#margin-and-denominators) page.

## Development and completion

`actuarialpy.reserving` fits chain-ladder development patterns from
cumulative triangles: `ChainLadder.fit` (volume-weighted or simple
age-to-age factors, optional tail), `project` for per-origin ultimates and
IBNR, and `completion_factors` / `apply_completion` for the
completion-factor workflow.

As of 0.40.0 the pattern carries its own uncertainty — the
distribution-free standard errors of Mack (1993):

```python
cl = ChainLadder.fit(triangle)           # volume-weighted
cl.mack_sigma_squared(triangle)          # variance parameters per period
cl.mack_standard_errors(triangle)
# latest | ultimate | ibnr | se | cv     (per origin, plus a Total row
#                                         with the cross-origin covariance)
```

Two honesty notes, stated rather than hidden: the errors are defined for
the volume-weighted estimator only (Mack's model *is* that estimator, so
`method="simple"` refuses), and a fitted `tail` is treated as
deterministic — ultimates and standard errors scale by it exactly.
Verified against the published Taylor–Ashe results (total reserve
18,680,856; total s.e. 2,447,095).

## API reference

```{eval-rst}
.. automodule:: actuarialpy
   :members:
```
