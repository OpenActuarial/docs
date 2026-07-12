# actuarialpy

Shared actuarial primitives and general tooling — the calculation core the
rest of the ecosystem builds on. Ratios and per-exposure metrics, chain-ladder
development and IBNR, credibility, trend, seasonal factors, financial
mathematics, exposure and lifecycle bases, size banding, pooling, margins, and
weighted rollups, applied to claims, exposure, and premium data. It does not
perform data preparation or encode filed methodology: the caller supplies the
table and selects the method. Every result is a DataFrame or Series, and the
only dependencies are numpy and pandas.

`actuarialpy` also owns the ecosystem's shared data contract: the canonical
`Experience` container ([below](#the-experience-container)). The *study
layer* that builds on both — experience summaries, actual-versus-expected,
claimant, cohort, and decomposition analyses, and the underwriting income
statement — lives in [experiencestudies](experiencestudies.md), which depends
on `actuarialpy` and never the other way around.

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
workflows on such a table, the canonical `Experience` object binds the
column roles once; the study views over it live in
[experiencestudies](experiencestudies.md).

## The Experience container

`Experience` is the ecosystem's canonical semantic wrapper for historical
actuarial data: it binds column roles, grain metadata, and snapshot context
once, so [experiencestudies](experiencestudies.md),
[projectionmodels](projectionmodels.md), and
[ratingmodels](ratingmodels.md) consume one object instead of re-declaring
columns.

```python
import actuarialpy as ap

exp = ap.Experience(
    panel,
    expense="paid_claims", revenue="premium",       # measure roles: at least
    exposure="member_months", count="claim_count",  #   one required, none mandatory
    date="incurred_month",
    dimensions=["group_id", "claim_type"],          # segmentation, lookups, grain defaults
    exposure_keys=["member_id", "incurred_month"],  # one row per exposure unit (opt-in guard)
    valuation_date="2026-06-30",
)
```

Three kinds of metadata do three different jobs. The **measure and date
roles** name what the columns mean. **`dimensions`** are segmentation
columns — consumers use them as defaults for reporting cuts, assumption
lookups, and projection grain; they say nothing about row grain.
**`exposure_keys`** identify one exposure unit: when bound, construction
validates the frame is unique on them, so long (service-line-grain) data is
rejected at the door instead of silently overcounting every per-exposure
figure. Leave them unbound and no grain safety is claimed.

The object holds **no actuarial judgment**. Its public methods are immutable
*transformations* — each takes caller-supplied assumptions as arguments and
returns a new `Experience`, so restatements chain:

```python
work = (
    exp.filter(query="group_id == 1102052")
       .complete(completion_factors)     # develops to ultimate; valuation date
       .adjust(1.03)                     #   defaults from the object
       .deseasonalize(seasonal_factors)
)
```

`complete()` also tracks state: it marks each developed column `"ultimate"`
in the object's `basis`, and completing a column already on an ultimate
basis raises — the double-development mistake is an error, not a silent
overstatement. Data that arrives already developed declares it at
construction (`basis={"paid_claims": "ultimate"}`).

**Multi-table sources bind at the doorway.** `Experience.from_tables` builds
the experience tab from source extracts -- a grain-defining table (membership,
validated unique) plus any number of `Source` specs naming their role in the
same vocabulary (`expense`, `revenue`, `count`), an optional `wide_by`
categorical to pivot (claim types become expense columns, recorded as
provenance), and each table's own date floored to the grain period. One fixed
algorithm: finer tables aggregate up, coarser tables are refused (allocation
is judgment), unmatched keys are surfaced, empty cells are structural zeros.

```python
exp = ap.Experience.from_tables(
    membership, grain=["member_id", "month"], exposure="member_months",
    sources=[
        ap.Source(claim_lines, expense="paid_amount",
                    wide_by="claim_type", date="incurred_date"),
        ap.Source(billing, revenue="billed_premium"),
    ],
    date="month", period="M", dimensions="group_id",
)
```

Coarser worksheets derive from it structurally: `exp.aggregate(by="group_id",
freq="MS")` sums the measure roles to a new validated grain (and requires
`exposure_keys`, since summing exposure is only provably safe on a proven
grain), and `exp.melt()` undoes a recorded pivot when a consumer needs the
categories long.

**One construction call: the `ExperienceSet` workbook.** When the same
sources feed several grains, `ExperienceSet.from_tables` builds them
together: the worksheet (`book.tab`) plus one listing member per *named*
`Source` spec (`book["claims"]`), each an ordinary, materialized,
grain-honest `Experience`. Consumers accept the set and route themselves --
studies, rating, and projection to the tab; severity and tail fitting to
the claims listing.

```python
book = ap.ExperienceSet.from_tables(
    membership, grain=["member_id", "month"], exposure="member_months",
    sources=[ap.Source(claim_lines, expense="paid_amount",
                       wide_by="claim_type", date="incurred_date",
                       name="claims"),
             ap.Source(billing, revenue="billed_premium")],
    date="month", period="M", dimensions="group_id",
)
book.cohort(group_id="1102052")   # re-derives every member from the sources
book.reconcile()                  # ties each listing's totals to the tab
```

`cohort(...)` filters the grain table (the population authority) and
rebuilds all members -- propagation by reconstruction, never mutation.
`reconcile()` surfaces exclusions (orphan keys) instead of dropping them
silently. One construction call is universal; one instance never holds two
grains.

Everything analytical is a *function that accepts an `Experience`* — a split
enforced by a test (no public method on the class may return anything else).
Here in `actuarialpy`, `fit_trend` and `trend_summary` are Experience-native
(`ap.fit_trend(work)` resolves the value, date, and exposure columns from
the bound roles); the study summaries live in
[experiencestudies](experiencestudies.md), projections in
[projectionmodels](projectionmodels.md), and worksheet construction in
[ratingmodels](ratingmodels.md).

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
