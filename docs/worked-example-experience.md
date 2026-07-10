# Example 1: experience to a renewal rate

The first two boxes of the workflow, end to end: read a monthly experience
panel with `experiencestudies` — frequency-severity and trend decomposition
through the fluent `Experience` object — over `actuarialpy` primitives for
seasonality, trend, and credibility, then carry the projected loss cost into a
`ratingmodels` indication and constrain it into a bookable renewal. Every
number on this page is the output of this exact fixed-seed run, pinned by a
regression test in the `ratingmodels` suite.

## The panel

Three years of monthly experience for one block, two segments with a shifting
mix (the south segment grows while the north shrinks), genuine seasonality, and
frequency and severity trends of +2% and +4.5% a year baked into the
generator:

```python
import numpy as np
import pandas as pd
import actuarialpy as ap
import ratingmodels as rm
from experiencestudies import Experience

rng = np.random.default_rng(42)
months = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
rows = []
for seg, mm0, growth, f0, s0 in [("north", 5200, -0.010, 0.30, 950.0),
                                 ("south", 3100, +0.055, 0.34, 880.0)]:
    for i, m in enumerate(months):
        yrs = i / 12.0
        mm = mm0 * (1 + growth) ** yrs
        season = 1.0 + 0.06 * np.cos(2 * np.pi * (m.month - 1.5) / 12)
        freq = f0 * 1.02 ** yrs * season * (1 + rng.normal(0, 0.015))
        sev = s0 * 1.045 ** yrs * (1 + rng.normal(0, 0.01))
        cc = freq * mm
        rows.append((m, seg, mm, cc, cc * sev, 393.0 * mm))
df = pd.DataFrame(rows, columns=["month", "segment", "member_months",
                                 "claim_count", "incurred", "premium"])
df["year"] = df["month"].dt.year
```

## Read the experience

Bind the column roles once and every view derives from them:

```python
exp = Experience(df, expense="incurred", revenue="premium",
                 exposure="member_months", date="month", count="claim_count")

exp.frequency_severity(groupby="year")
#  year  frequency  severity  loss_per_exposure
#  2023     0.3182    938.35             298.58
#  2024     0.3256    980.67             319.29
#  2025     0.3314   1024.87             339.60
```

The identity `loss_per_exposure == frequency * severity` holds on every row —
see [Rates, exposure, and decomposition](conventions.md#rates-exposure-and-decomposition).

## Decompose the change

Where did the 2024 → 2025 change come from? With `mix_by`, the LMDI split
separates within-segment frequency and severity movement from the effect of
the book shifting toward the south segment:

```python
d = exp.decompose_trend(period_col="year", prior_period=2024,
                        current_period=2025, mix_by="segment").iloc[0]
# loss_per_exposure : 319.29 -> 339.60   (trend 1.0636)
# frequency_trend 1.0156   severity_trend 1.0465   mix_trend 1.0007
# effects: frequency +5.09  severity +14.98  mix +0.24  (sum +20.31, exact)
```

The generator's +2% frequency and +4.5% severity come back almost exactly;
the mix term is small because the segments' cost levels are close. Both
reconciliations — multiplicative and additive — are exact by construction.

## Seasonality and trend

Fit monthly factors on the aggregated panel, deseasonalize, and fit the
underlying trend on what remains:

```python
dm = df.groupby("month", as_index=False)[["incurred", "member_months"]].sum()
factors = ap.seasonality_factors(dm, date_col="month", value_col="incurred",
                                 exposure_col="member_months")
# January 1.049, July 0.940 — the winter peak the generator planted

dm2 = ap.deseasonalize(dm, factors, date_col="month", value_col="incurred")
fit = ap.fit_trend(dm2, value_col="incurred_deseasonalized",
                   date_col="month", exposure_col="member_months")
# annual_trend 0.0666   r² 0.961   (true combined trend: 1.02 × 1.045 − 1 = 6.6%)
```

## Project and blend

Trend the 2025 loss cost 18 months to the rating-period midpoint, take the
credibility from the claim volume, and blend against a manual:

```python
proj = 339.60 * ap.trend_factor(fit.annual_trend, months=18)   # -> 374.10

std = ap.full_credibility_claims(severity_cv=1.2)               # -> 2,641 claims
z = ap.limited_fluctuation_z(34_234, std)                       # -> 1.000
ap.limited_fluctuation_z(1_200, std)                            # -> 0.674 for a small case

manual = rm.ManualRate(base_loss_cost=248.0, factors={"area": 1.06, "industry": 0.97})
ind = rm.RateIndication(experience_loss_cost=proj,
                        manual_loss_cost=manual.loss_cost(),   # 254.99
                        credibility=z, current_rate=393.0,
                        target_loss_ratio=0.85)
ind.indicated_rate()          # -> 440.11
ind.indicated_rate_change()   # -> +12.0%
```

At 34,000 claims the block is fully credible even on the aggregate-loss
standard, so the manual carries no weight here — the second line shows the
credibility a 1,200-claim case would get, which is where the blend earns its
keep.

## Constrain it, and price the constraint

A renewal corridor caps the change; the pricing layer then says exactly what
the cap costs:

```python
final = rm.corridor(current_rate=393.0, indicated_rate=ind.indicated_rate(),
                    max_up=0.09, max_down=0.03)               # -> 428.37 (+9.0%)

ret = rm.RetentionLoad(fixed_expense=22.0, variable_expense_ratio=0.10,
                       profit_margin=0.02)
pe = rm.PricingEvaluation(loss_cost=proj, current_rate=393.0, retention=ret)
pe.at(ind.indicated_rate() / 393.0 - 1).margin_rate   # ->  0.00% of premium
pe.at(final / 393.0 - 1).margin_rate                  # -> −2.47% of premium
```

The margin at the indicated rate is exactly zero — the 0.85 target and this
retention describe the same economics, so the two layers agree by identity,
not coincidence. The corridor releases 9 of the indicated 12 points; the
remaining 3 show up as a −2.47% margin at the capped rate. That is the cost
of the constraint, quantified.
