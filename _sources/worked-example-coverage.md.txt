# Example 4: censored payments to coverage terms

Real claim extracts rarely show ground-up losses: anything below the
deductible was never reported, and anything at the limit is capped. This
example takes exactly that kind of data through `lossmodels` — back to the
ground-up scale, through a censoring-aware fit, and out to repriced coverage
terms and their aggregate distribution. Every number is the output of this
fixed-seed run, pinned by a regression test in the `lossmodels` suite.

## The data you actually have

Ground-up truth is Lognormal(7.4, 1.1); the policy pays claims net of a 500
deductible up to a 10,000 maximum payment:

```python
import numpy as np
import lossmodels as lm

rng = np.random.default_rng(7)
true = lm.Lognormal(7.4, 1.1)
x = true.sample(6000, rng=rng)                     # two years of ground-up claims
payments = np.clip(x - 500.0, 0.0, 10_000.0)
obs = payments[payments > 0]                       # below-deductible: never reported
# 6,000 ground-up -> 5,140 observed payments, 278 of them capped;
# 14.3% of claims are invisible to the data
```

## Back to the ground-up scale

One call restores the estimation-ready triple — ground-up values, per-claim
left-truncation points (the deductible), and censoring flags (the capped
payments) — per the [truncation and censoring
conventions](conventions.md#truncation-and-censoring):

```python
values, trunc, cens = lm.payments_to_ground_up(obs, deductible=500.0,
                                               max_payment=10_000.0)
```

A Kaplan–Meier fit on that triple is the nonparametric check that the
plumbing is right — it should track the *conditional* survival
$S(t)/S(500)$ of the true law, and it does:

```python
times, surv = lm.kaplan_meier(values, truncation=trunc, censored=cens)
# S(2,000): KM 0.4854   truth 0.4975
# S(8,000): KM 0.0872   truth 0.0867
```

## The naive fit versus the right fit

The common mistake is to add the deductible back and fit as if the data were
complete. That gets the mean roughly right and the *tail* badly wrong,
because the missing small claims and the capped large ones both squeeze the
fitted dispersion:

```python
naive = lm.fit_lognormal(obs + 500.0)
fitc = lm.fit_mle_censored(lm.Lognormal, values, initial_params=[7.0, 1.0],
                           truncation=trunc, censored=cens)
# true     (mu, sigma) = (7.400, 1.100)
# naive                = (7.649, 0.833)   <- sigma crushed by 24%
# censored             = (7.370, 1.112)   <- recovered
```

Everything downstream — layer prices, tail quantiles, reinsurance — runs off
`sigma`, which is exactly the parameter the naive fit destroys.

## Reprice the terms

With a credible ground-up severity, coverage alternatives are closed-form
LEV arithmetic (see [coverage semantics](conventions.md#coverage-semantics):
the second `Layer` argument is the width). Compare the current terms with a
proposal that doubles the limit and funds it with a higher deductible:

```python
from lossmodels.coverage import Layer, OrdinaryDeductible

sev = fitc
cur = Layer(sev, 500.0, 10_000.0)     # current: 10,000 xs 500
prop = Layer(sev, 1000.0, 20_000.0)   # proposed: 20,000 xs 1,000

cur.mean(), prop.mean()               # -> 2,122.75 vs 1,978.08 per ground-up claim
OrdinaryDeductible(sev, 500.0).loss_elimination_ratio()    # -> 16.0%
OrdinaryDeductible(sev, 1000.0).loss_elimination_ratio()   # -> 28.8%
```

## The aggregate picture

Discretize each layer (the coverage transforms expose `cdf`, so
`discretize_severity` takes them directly, zero-atom and all) and convolve
with the ground-up frequency. One numerical note earns its keep here: at
3,000 expected claims the Panjer recursion's mass at zero underflows —
`panjer_recursion` now raises and says so — and the FFT route is the right
tool:

```python
from lossmodels.aggregate import (discretize_severity, fft_aggregate_poisson,
                                  stop_loss_from_pmf, tvar_from_pmf, var_from_pmf)

for lay in (cur, prop):
    pmf = discretize_severity(lay, h=250.0, max_loss=25_000.0)
    agg = fft_aggregate_poisson(lm.Poisson(3000.0), pmf, n_steps=65_536)
```

|                     |    current |   proposed |
|---------------------|-----------:|-----------:|
| payments per year   |      2,551 |      1,983 |
| aggregate mean      |  6,365,033 |  5,931,669 |
| P99                 |  6,803,250 |  6,448,250 |
| TVaR₉₉              |  6,868,594 |  6,525,867 |
| stop-loss at 6.6M   |      9,445 |         92 |

(Payment counts follow from Poisson thinning — the payment frequency is
exactly $3{,}000 \cdot S(d)$ — and the aggregate means reconcile with Wald's
identity to within the documented downward discretization bias.)

The proposal cuts expected cost 6.8% and the 1-in-100 by 5.2%: the higher
deductible more than funds the doubled limit at this severity. And because
the retained tail now sits well inside 6.6M, an aggregate stop-loss at that
attachment goes from a 9,445 pure premium to essentially free — the kind of
statement only the full aggregate distribution can make.
