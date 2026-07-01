# actuarialpy

Experience analysis on a single tidy table, plus the shared numerical core the
rest of the ecosystem builds on. You build one DataFrame — claims/expense,
revenue, exposure, by period — and `Experience` gives you views (`by`,
`rolling`, `trend`, completion, seasonality, credibility, pooling) without
re-pivoting. numpy and pandas only; no scipy.

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

ap.pmpm(df["paid"], df["member_months"])       # per-member-per-month
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

## API reference

```{eval-rst}
.. automodule:: actuarialpy
   :members:
```
