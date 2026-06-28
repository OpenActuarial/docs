# lossmodels

Severity and frequency distributions, maximum-likelihood fitting, goodness-of-fit, and
collective-risk (compound) models — the loss-distribution toolkit familiar from the
actuarial FAM/STAM syllabus, as composable objects.

## Quickstart

```python
import lossmodels as lm

# a severity distribution
sev = lm.Lognormal(mu=8.0, sigma=1.5)
sev.quantile(0.99)                     # 99th-percentile claim
sev.limited_expected_value(250_000)    # E[min(X, 250k)] -- a capped/limited loss

# a collective-risk (compound) model: random number of claims, random sizes
model = lm.CollectiveRiskModel(
    frequency=lm.Poisson(lam=3.0),
    severity=lm.Lognormal(mu=8.0, sigma=1.5),
)
model.mean()                           # E[aggregate]
model.var(0.99)                        # 99% Value-at-Risk of the aggregate
model.tvar(0.99)                       # 99% Tail VaR
```

## Fitting

```python
import numpy as np
import lossmodels as lm

data = lm.Lognormal(mu=8.0, sigma=1.2).sample(5_000, seed=0)
fit = lm.fit_lognormal(data)           # MLE
lm.fit_best_severity(data)             # compare candidates by AIC/BIC
```

## API reference

::: lossmodels
