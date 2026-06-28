# OpenActuarial

OpenActuarial is a set of four small, composable Python libraries for actuarial and risk
modeling. Each does one thing and has a clean public API; together they cover experience
analysis, loss-distribution modeling, Monte Carlo risk simulation, and extreme-value
tail estimation. They share a deliberate design: general, reusable math in public
libraries — the data they run on stays wherever you keep it.

| Package | What it does |
|---|---|
| [**actuarialpy**](actuarialpy.md) | Experience analysis on a single tidy table: loss ratios, PMPM, trend, credibility, completion/reserving, seasonality, pooling. numpy + pandas only. |
| [**lossmodels**](lossmodels.md) | Severity and frequency distributions, fitting, goodness-of-fit, and collective-risk (compound) models. |
| [**risksim**](risksim.md) | Monte Carlo simulation of portfolios of risk models, with reinsurance contracts and layers. |
| [**extremeloss**](extremeloss.md) | Extreme-value theory: peaks-over-threshold (GPD) and block-maxima (GEV) tail fitting, tail risk measures, and bootstrap uncertainty. |

See [How they fit together](overview.md) for the way the four compose into a single
pipeline.

## Install

```bash
pip install actuarialpy lossmodels risksim extremeloss
```

Each package can be installed and used on its own; `extremeloss` and `risksim` offer
optional integrations with each other and with `lossmodels` when those are present.

## Example

```python
import numpy as np
import extremeloss as el

# fit a heavy tail and compute a 1-in-1000 loss
losses = np.random.default_rng(0).pareto(2.0, 50_000) * 100_000
fit = el.fit_pot(losses, threshold=np.quantile(losses, 0.95))
print(fit.xi, fit.beta)            # GPD shape and scale
print(el.return_level(1000, fit))  # the 1-in-1000 return level
```
