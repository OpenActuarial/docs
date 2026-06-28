# extremeloss

Extreme-value theory for loss data: peaks-over-threshold (generalized Pareto) and
block-maxima (generalized extreme value) tail fitting, tail risk measures (VaR/TVaR,
return levels), importance-sampling estimators for rare events, and bootstrap
uncertainty.

## Quickstart

```python
import numpy as np
import extremeloss as el

losses = np.random.default_rng(0).pareto(2.0, 50_000) * 100_000

# peaks-over-threshold: fit a generalized Pareto tail above a high threshold
fit = el.fit_pot(losses, threshold=np.quantile(losses, 0.95))
fit.xi, fit.beta                       # GPD shape and scale
el.return_level(1000, fit)             # the 1-in-1000 return level
el.gpd_var(0.999, fit.threshold, fit.xi, fit.beta, fit.exceedance_fraction)
```

## Choosing a threshold

```python
import extremeloss as el

el.threshold_diagnostic_table(losses)  # stability of xi across candidate thresholds
el.mean_excess(losses)                 # mean-excess (should be ~linear in the GPD range)
```

## Bootstrap uncertainty

Tail estimates from few exceedances are noisy; bootstrap the risk measures rather than
trusting a point estimate.

```python
import extremeloss as el

el.bootstrap_var(losses, 0.99)         # CI on the 99% VaR
el.bootstrap_tail_probability(losses, threshold=500_000)
```

## API reference

::: extremeloss
