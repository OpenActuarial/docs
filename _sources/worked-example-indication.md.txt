# Example 5: triangle to indicated change

The indication workflow end to end, with the uncertainty carried through:
develop a claims triangle to ultimate with Mack standard errors
(`actuarialpy`), restate premium at current rate level with exact
parallelogram on-level factors, assemble the experience worksheet, and read
off the indicated change — then ask how much the development uncertainty
moves the answer. Every number on this page is the output of this exact
run, pinned by a regression test in the `ratingmodels` suite.

## The triangle, to ultimate with error bars

Three origin years of cumulative incurred, developed volume-weighted:

```python
import numpy as np
import pandas as pd
from actuarialpy.reserving import ChainLadder
import ratingmodels as rm

triangle = pd.DataFrame(
    {12: [4_120_000.0, 4_390_000.0, 4_610_000.0],
     24: [5_230_000.0, 5_650_000.0, np.nan],
     36: [5_490_000.0, np.nan, np.nan]},
    index=pd.Index([2022, 2023, 2024], name="origin"),
)
cl = ChainLadder.fit(triangle)
cl.age_to_age            # 12->24: 1.2785, 24->36: 1.0497
mack = cl.mack_standard_errors(triangle)
```

| origin | latest | ultimate | ibnr | se |
|---|---|---|---|---|
| 2022 | 5,490,000 | 5,490,000 | 0 | 0 |
| 2023 | 5,650,000 | 5,930,880 | 280,880 | 87,959 |
| 2024 | 4,610,000 | 6,186,869 | 1,576,869 | 115,787 |
| **Total** | 15,750,000 | 17,607,748 | **1,857,748** | **171,830** |

A total reserve of 1.86m with a standard error of 172k — a CV of about
9%. That last number is new information the point estimate never carried,
and it comes back at the end of the page.

## Premium, restated

Two rate changes during the experience window; annual policies, so the
transitions are parallelograms, computed in closed form:

```python
olf = rm.on_level_factors(
    periods=[("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31")],
    rate_changes=[("2023-07-01", 0.08), ("2024-04-01", 0.05)],
    policy_term=1.0,
)
olf["on_level_factor"]   # CY2023: 1.1227, CY2024: 1.0448
```

## The worksheet

`ExperienceExhibit` composes what the two packages produced — every
adjustment a visible column:

```python
proj = cl.project(triangle).loc[[2023, 2024]]
ex = rm.ExperienceExhibit(
    earned_premium=[7_450_000.0, 7_980_000.0],
    losses=proj["latest"].to_numpy(),
    on_level_factors=olf["on_level_factor"].to_numpy(),
    development_factors=proj["development_factor"].to_numpy(),
    trend_factors=[1.045**2, 1.045],     # trend to the rating period
    period_labels=["CY2023", "CY2024"],
)
ex.exhibit()
```

| period | on_level_premium | adjusted_losses | loss_ratio |
|---|---|---|---|
| CY2023 | 8,364,027 | 6,476,669 | 0.7743 |
| CY2024 | 8,337,712 | 6,465,278 | 0.7754 |

Weighted experience loss ratio: **0.7749**.

## The indication

The exhibit's totals wire straight into `RateIndication`; the gross-up is
the same `RetentionLoad` algebra as everywhere else in the package:

```python
retention = rm.RetentionLoad(variable_expense_ratio=0.11,
                             profit_margin=0.03, lae_ratio=0.05)
ind = ex.to_indication(manual_loss_cost=395.0, credibility=0.7,
                       current_rate=455.0, exposure=33_600.0,
                       retention=retention)
ind.indicated_rate()          # 473.87
ind.indicated_rate_change()   # +4.15%
```

## What the development uncertainty is worth

Re-run the exhibit with each origin's ultimate shifted by one Mack
standard error (the shifted ultimates *are* the developed losses, so the
development factors drop out):

```python
for shift in (-1.0, +1.0):
    bumped = proj["ultimate"].to_numpy() + shift * mack.loc[[2023, 2024], "se"].to_numpy()
    ex_s = rm.ExperienceExhibit(
        earned_premium=[7_450_000.0, 7_980_000.0], losses=bumped,
        on_level_factors=olf["on_level_factor"].to_numpy(),
        trend_factors=[1.045**2, 1.045],
        period_labels=["CY2023", "CY2024"])
    ex_s.to_indication(395.0, 0.7, 455.0, 33_600.0,
                       retention=retention).indicated_rate_change()
```

The +4.15% indication becomes **+2.93% at −1σ and +5.36% at +1σ**. One
standard error of development uncertainty is worth about ±1.2 points of
rate — which is the difference between a routine filing and a fight, and
now it is a number on the exhibit instead of a feeling.
