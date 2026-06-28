# actuarialpy

Experience analysis on a single tidy table. You build one DataFrame — claims/expense,
revenue, exposure, by period — and `Experience` gives you views (`by`, `rolling`,
`trend`, completion, seasonality, credibility, pooling) without re-pivoting. numpy and
pandas only; no scipy.

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

## Retention primitives

The pooling module includes two general retention-stability primitives:

- `retained_cv(outcomes, retention, n_units=1)` — coefficient of variation of the
  retained aggregate of `n_units` i.i.d. units each capped at `retention`.
- `retention_for_target_cv(outcomes, n_units, target_cv, ...)` — inverts it: the
  retention at which retained CV hits a target. Basis for a size-graded pooling schedule.

## API reference

::: actuarialpy
