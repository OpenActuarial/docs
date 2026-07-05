# actuarialpy

Experience analysis on a single tidy table, plus the shared numerical core the
rest of the ecosystem builds on. You build one DataFrame — claims/expense,
revenue, exposure, by period — and `Experience` gives you views (`by`,
`rolling`, `trend`, completion, seasonality, credibility, pooling) without
re-pivoting.

## Quickstart

```python
import pandas as pd
import actuarialpy as ap

df = pd.DataFrame({
    "month": pd.period_range("2024-01", periods=6, freq="M").astype(str),
    "product": ["PPO"] * 6,
    "paid":    [120_000, 118_000, 125_000, 130_000, 128_000, 135_000],
    "premium": [150_000] * 6,
    "member_months": [1000, 1005, 1010, 1008, 1012, 1015],
})

exp = ap.Experience(df, expense="paid", revenue="premium",
                    exposure="member_months", date="month")

exp.by("product")                              # grouped view
exp.loss_ratio                                 # paid / premium

ap.per_exposure(df["paid"], df["member_months"])  # amount per exposure unit
ap.loss_ratio(df["paid"], df["premium"])       # as a free function
```

## Credibility

Credibility primitives live here — `ratingmodels` and the other packages
delegate to them rather than re-implementing. Limited-fluctuation (classical)
credibility from exposure:

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
    "product": ["PPO", "PPO", "HMO", "HMO"],
    "paid":    [125_000, 130_000, 88_000, 91_000],
    "member_months": [1010, 1008, 640, 655],
})

model = ap.BuhlmannStraub.from_frame(
    exp, group="product", value="paid", weight="member_months",
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

# level-payment loan: 200k principal, 6% nominal, 30 years monthly
ap.level_payment(200_000, 0.06 / 12, 360)          # 1199.10 per month
ap.amortization_schedule(200_000, 0.06 / 12, 360)  # full schedule (DataFrame)

ap.year_fraction("2024-01-01", "2024-07-01", convention="30/360")  # 0.5
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

## Retention primitives

The pooling module includes two general retention-stability primitives:

- `retained_cv(outcomes, retention, n_units=1)` — coefficient of variation of the
  retained aggregate of `n_units` i.i.d. units each capped at `retention`.
- `retention_for_target_cv(outcomes, n_units, target_cv, ...)` — inverts it: the
  retention at which retained CV hits a target. The basis for a size-graded
  pooling schedule.

## Underwriting margin and weighted rollups

The two-tier underwriting income statement — **gross margin** (revenue less
loss expense, operating expense excluded) and **gain/(loss)** (gross margin
less operating expense). The ratios mirror the `loss_ratio` /
`expense_ratio` / `combined_ratio` trio in `metrics`, and denominators are
explicit parameters because real exhibits mix them (loss ratio over net
revenue beside an expense ratio over gross premium); `reconciliation()`
reports the resulting gap in `gain% = 1 − combined ratio`. Domain naming is
a **view concern, never a calculation concern**: the `profile` option
renames the loss-ratio column the same way `summarize_experience` does
(`"health"` → `mlr`, `"life"` → `benefit_ratio`), and `labels` renames
anything else. The full convention is on the [conventions](conventions.md)
page.

```python
import actuarialpy as ap

uw = ap.UnderwritingSummary.from_per_exposure(
    revenue_per_exposure={"premium": 400.0, "refund": -1.4},
    loss_per_exposure={"claims": 340.0, "other_loss": 16.4},
    expense_per_exposure=37.4,
    exposure=300_000,
)
uw.loss_ratio, uw.expense_ratio, uw.combined_ratio   # explicit denominators
uw.gross_margin_per_exposure, uw.gain_per_exposure   # the two tiers
uw.to_frame(profile="health")                        # loss_ratio -> mlr, math unchanged

# grouped, from a tidy table: components summed first,
# every ratio a ratio of sums
ap.underwriting_summary(
    df, groupby="cohort",
    revenue_cols=["premium", "refund"], loss_cols=["claims"],
    expense_cols="expense", exposure_col="member_months",
    premium_col="premium",
)
# per-exposure outputs are the mechanical {name}_per_{exposure_col};
# domain names (a health shop's _pmpm) are opt-in via labels
```

Quantities that are already rates at the row level — rate actions,
persistency — cannot be summed. `weighted_mean` and `weighted_summary`
average them with a **required, named weight** and report the weight total
beside every average:

```python
ap.weighted_summary(book, value_cols="rate_action",
                    weight_col="premium", groupby="cohort")
```

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
