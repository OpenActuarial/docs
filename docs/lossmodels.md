# lossmodels

Loss-distribution modeling: fit severity and frequency distributions —
including to claims data net of deductibles and limits — and combine them into
an aggregate loss distribution. numpy and scipy only.

The package is organized into severity, frequency, aggregate, estimation,
empirical, and coverage modules. Fitted models expose a consistent
`pdf`/`cdf`/`sf`/`quantile`/`mean`/`sample` interface; the estimation layer
fits and compares them; the aggregate layer convolves a frequency and a
severity model into the aggregate loss for a block.

## Distributions

The continuous severity inventory follows the *Loss Models* (FAM/ASTAM
Appendix A) parameterizations — exponential, gamma, lognormal, Weibull, the
transformed-beta family (Burr, inverse Burr, Pareto II/Lomax, loglogistic,
paralogistic, …), inverse distributions, and generalized Pareto — plus
`SplicedSeverity` for body–tail constructions. Frequencies cover Poisson,
negative binomial, binomial, geometric, and logarithmic, with `ZeroTruncated`
and `ZeroModified` wrappers for the (a, b, 1) class. Mind the Pareto naming:
`Pareto` is Type I and `ParetoII` is the Lomax that *Loss Models* calls
"Pareto" — see [Conventions](conventions.md#distribution-naming-and-parameterizations).

## Fitting

Complete-data fitting is one call per family, or one call across families:

```python
import lossmodels as lm

x = lm.Lognormal(mu=8.6, sigma=1.4).sample(20_000, rng=1)

fit = lm.fit_lognormal(x)                  # closed-form MLE
best = lm.fit_best_severity(x)             # nine families, ranked by AIC
best["best_name"]                          # 'lognormal'
lm.goodness_of_fit(best["best_model"], x, k=2)   # loglik, AIC/BIC, KS, AD, CvM
```

`fit_best_severity` fits every registered family (exponential, gamma,
lognormal, Weibull, Pareto I, Pareto II, loglogistic, inverse gamma, Burr) by
MLE and ranks by AIC or BIC; candidates that fail to fit are skipped.
Method-of-moments alternatives (`method="moments"`) and frequency selection
(`fit_best_frequency`) follow the same pattern.

## Fitting under deductibles and limits

Real claim data is rarely ground-up and complete: a deductible left-truncates
(losses below it never enter the data) and a policy limit right-censors (a
capped payment says only that the loss was *at least* the cap). Fitting a
complete-data likelihood to such values is biased — often badly. Every
severity fitter therefore accepts the individual-data likelihood of
*Loss Models*: with truncation points $t_i$ and censoring indicators
$\delta_i$,

$$
\ell(\theta) \;=\; \sum_i \Big[\, \delta_i \log f(x_i)
  + (1-\delta_i) \log S(x_i) - \log S(t_i) \,\Big].
$$

The practical entry point converts per-payment data into the
`(values, truncation, censored)` triple:

```python
import lossmodels as lm

# payments net of an 800 deductible, capped at a 20,000 maximum payment
values, truncation, censored = lm.payments_to_ground_up(
    payments, deductible=800, max_payment=20_000,
)

fit = lm.fit_lognormal(values, truncation=truncation, censored=censored)

best = lm.fit_best_severity(               # selection under the same likelihood
    values, truncation=truncation, censored=censored,
)
```

With both keywords omitted, every fitter runs its original complete-data path
unchanged. The exponential and Pareto Type I keep closed forms in the
censored/truncated case; gamma, lognormal, Weibull, and the transformed-beta
fitters use the generic machinery (`fit_mle_censored`,
`censored_log_likelihood`), which works for any model exposing `pdf` and
`cdf`.

Diagnostics follow the data: `aic`/`bic`/`goodness_of_fit` accept the same
keywords and score with the individual-data likelihood; `pit_values` returns
the probability-integral transform $(F(x_i)-F(t_i))/(1-F(t_i))$, exactly
Uniform(0, 1) under the true model for uncensored data with arbitrary
truncation points; `ks_statistic` uses the PIT under truncation and compares
against the **Kaplan–Meier** estimate (`kaplan_meier`, product-limit under
left truncation and right censoring) when censoring is present.

## Aggregate losses

`CollectiveRiskModel` composes a frequency and a severity into the aggregate
loss $S = \sum_{j=1}^{N} X_j$, by simulation or by discretized recursion:

```python
import lossmodels as lm

crm = lm.CollectiveRiskModel(
    frequency=lm.Poisson(lam=120),
    severity=lm.Lognormal(mu=8.6, sigma=1.4),
)

s = crm.sample(100_000, rng=7)     # one generator threads through both draws
crm.mean(), crm.variance()         # exact compound moments
```

Simulation-based measures (`var`, `tvar`, `stop_loss`,
`limited_expected_value` on the aggregate side) accept the same `rng`
argument, and the empirical estimators follow the ecosystem VaR/TVaR
convention — see [Conventions](conventions.md#risk-measures-var-and-tvar).
`discretize_severity` (midpoint by default) prepares severity PMFs for
Panjer/FFT-style recursion.

## Coverage modifications

The coverage module applies policy terms to a ground-up severity:
`OrdinaryDeductible`, `PolicyLimit`, and `Layer(d, u)` with per-loss payment
$\min((X-d)_+, u)$ — note `u` is the **maximum payment** (layer width), not
the upper attachment; a 5M xs 1M layer is `Layer(1_000_000, 5_000_000)`.
Layer moments are computed deterministically from
$E[Y^2] = \int 2\,y\,S(y)\,dy$.

See the API reference below for the full surface; each object's docstring
carries its own usage.

## API reference

```{eval-rst}
.. automodule:: lossmodels
   :members:
```
