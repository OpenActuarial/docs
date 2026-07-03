# extremeloss

Extreme-value tail estimation for large claims: peaks-over-threshold with the
generalized Pareto distribution (GPD), tail analytics, and large-claim loading.
numpy and scipy only; matplotlib is optional via the `plot` extra, and
`lossmodels` integration via the `splice` extra.

The package covers threshold selection, GPD estimation, and the analytics built
on a fitted tail — return levels, exceedance probabilities, and excess-layer
charges — plus integration helpers for splicing an empirical body to a fitted
tail. It composes with `lossmodels` and the pooling primitives in `actuarialpy`.

Empirical tail measures follow the ecosystem VaR/TVaR estimators, and
simulation-backed quantities accept the shared `rng` argument — see
[Conventions](conventions.md).

See the API reference below for the full surface; each object's docstring carries
its own usage.

## Threshold selection

Scan candidate thresholds before committing to one. `threshold_diagnostic_table`
returns a `ThresholdScan` with the exceedance counts, GPD parameter estimates,
and mean excesses at each candidate; `mean_excess` returns the same diagnostics
for plotting (matplotlib via the `plot` extra):

```python
import numpy as np
import extremeloss as xl

scan = xl.threshold_diagnostic_table(
    losses, np.quantile(losses, [0.90, 0.925, 0.95, 0.975])
)
scan.thresholds, scan.n_exceedances, scan.xi, scan.beta, scan.mean_excess
```

Take the lowest threshold above which the shape estimate $\hat\xi$ is stable
and the mean-excess function is roughly linear — the classic
peaks-over-threshold trade between bias (threshold too low) and variance
(too few exceedances).

## Fitting the tail

`fit_pot(data, threshold)` selects the exceedances of the threshold and fits
the GPD to their *excesses*; `fit_gpd(excesses)` is the same fit when the
excesses are already in hand:

```python
fit = xl.fit_pot(losses, threshold=u)
fit.xi, fit.beta, fit.exceedance_fraction

# unconditional, ground-up tail metrics — the fit carries the exceedance rate
xl.gpd_var(0.995, fit.threshold, fit.xi, fit.beta, fit.exceedance_fraction)
xl.gpd_tvar(0.995, fit.threshold, fit.xi, fit.beta, fit.exceedance_fraction)
xl.return_level(200, fit)        # the 1-in-200 claim == gpd_var(0.995, ...)

tail = xl.GPDTail.from_fit(fit)  # conditional law on [u, inf), for splicing
```

`GPDFit` quotes **unconditional** quantities; `GPDTail` is the **conditional**
excess law a splice consumes. The distinction, and the $(\xi, \beta)$
parameterization, are pinned in
[Conventions](conventions.md#tail-fitting-and-splicing). Sampling accepts the
shared `rng` argument.

## Splicing onto a fitted body

The handoff runs one direction: `extremeloss` fits the tail and returns a
`lossmodels.SplicedSeverity`, so every downstream consumer holds the same
severity class whether or not it carries an EVT tail:

```python
sev = xl.splice_gpd_tail(body, fit)               # weight from the fit
sev = xl.fit_spliced_gpd(body, losses, threshold=u)  # weight from the data
```

Splicing is mass-matching, never density-continuity; pass `weight=` to
override the empirical body mass.

## From simulated portfolios

A `risksim.SimulationResult` feeds straight back into the tail toolkit:

```python
res = portfolio.simulate(100_000, contract=treaty, rng=7)   # risksim
xl.tail_summary_from_risksim(res)
# n / mean / std / min / max and VaR/TVaR at (0.95, 0.99, 0.995)
```

## API reference

```{eval-rst}
.. automodule:: extremeloss
   :members:
```
