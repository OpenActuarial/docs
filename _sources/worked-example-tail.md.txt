# Example 6: pricing the tail, with error bars

One block of claims, two defensible severity models, and an 82% disagreement
on the pooling charge — this page is about making that disagreement visible
instead of discovering it in a rate filing. Fit and compare severities with
`lossmodels`, carry parameter uncertainty into the limits factors, scan the
tail with `extremeloss`, and price the same excess layer both ways through
the `ratingmodels` pooling seam. Every number on this page is the output of
this exact fixed-seed run, pinned by a regression test in the `extremeloss`
suite.

## The claims, and the model contest

```python
import numpy as np
import lossmodels as lm
import extremeloss as el
import ratingmodels as rm

rng = np.random.default_rng(2026)
claims = rng.lognormal(mean=9.4, sigma=1.15, size=2_400)

lm.compare_fits({"lognormal": lm.fit_lognormal(claims),
                 "gamma": lm.fit_gamma(claims),
                 "weibull": lm.fit_weibull(claims)}, claims)
```

| model | aic | ks | ad |
|---|---|---|---|
| lognormal | **52,458.394** | **0.009** | **0.201** |
| weibull | 52,846.879 | 0.067 | 27.722 |
| gamma | 52,930.563 | 0.086 | 36.741 |

Not a close contest: the lognormal wins the body (K–S) and the tail
(Anderson–Darling) simultaneously. Note the *shape* of the losses for the
runners-up — a gamma that misses by 0.086 on K–S misses by 36.7 on A–D,
because A–D weights exactly the region an excess layer lives in.

## Parameters with error bars, factors with error bars

```python
best = lm.fit_lognormal(claims)
unc = lm.fit_uncertainty(best, claims)
unc.summary()
```

| parameter | estimate | se | ci_low | ci_high |
|---|---|---|---|---|
| mu | 9.3652 | 0.0236 | 9.3190 | 9.4114 |
| sigma | 1.1547 | 0.0167 | 1.1220 | 1.1874 |

The delta method carries that covariance to the factor actually filed:

```python
lm.increased_limits_table(best, limits=[250_000, 500_000, 1_000_000],
                          base_limit=250_000, uncertainty=unc)
```

| limit | ilf | ilf_se | ci_low | ci_high |
|---|---|---|---|---|
| 250,000 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| 500,000 | 1.0182 | 0.0023 | 1.0138 | 1.0227 |
| 1,000,000 | 1.0228 | 0.0031 | 1.0167 | 1.0288 |

An ILF of 1.0182 ± 0.0023 off 2,400 claims: the fourth decimal was never
real, and now the table says so.

## The tail, scanned with bands

```python
grid = np.quantile(claims, [0.85, 0.90, 0.93, 0.95])
scan = el.threshold_diagnostic_table(claims, grid)
```

| threshold quantile | xi | xi_se |
|---|---|---|
| 0.85 | 0.365 | 0.070 |
| 0.90 | 0.450 | 0.097 |
| 0.93 | 0.403 | 0.113 |
| 0.95 | 0.380 | 0.133 |

Within their bands the shape estimates are indistinguishable — which is
itself the finding. A lognormal has no true Pareto tail; what a GPD sees at
any finite threshold is a *local* effective shape around 0.4 that never
stabilizes to a limit. The scan cannot rule the GPD out, but nothing here
demands it either.

```python
u = float(np.quantile(claims, 0.90))
fit = el.fit_pot(claims, threshold=u)        # u = 51,810
# xi = 0.4502 (se 0.0972), beta = 29,152 (se 3,294)

el.gpd_return_level(fit, [10, 50], observations_per_period=2_400.0)
```

| return period | return level | se |
|---|---|---|
| 10 years | 2,140,226 | 1,051,790 |
| 50 years | 4,430,985 | 2,838,106 |

A 10-year loss of 2.1m ± 1.1m: the tail is estimable, barely, and the
band says exactly how barely.

## The same layer, priced both ways

Both models satisfy the two-method protocol (`sf` + `mean_excess`), so both
feed the pooling seam directly:

```python
for sev in (best, fit):
    rm.pooling_charge_from_severity(sev, pooling_point=250_000,
                                    expected_frequency=0.9)
```

| model | S(250k) | mean excess | charge per exposure |
|---|---|---|---|
| lognormal body | 0.00398 | 132,302 | **474.28** |
| GPD tail (u = q90) | 0.00445 | 215,323 | **862.02** |

Same claims, same attachment, an 82% difference — almost entirely from the
mean excess, because a fitted ξ of 0.45 grows the excess linearly in the
attachment while the lognormal's effective shape keeps decaying. Here the
evidence adjudicates: the generator is lognormal and every diagnostic above
said so. On real data it usually will not be this clean, and then this
two-row table *is* the risk-margin conversation — the model choice priced
in currency, with the compare-fits scorecard and the ξ bands as the
evidence on each side.
