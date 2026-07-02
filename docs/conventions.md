# Conventions

Cross-package conventions the ecosystem holds everywhere. When two packages
compute the same quantity, they compute it the same way — the risk-measure
estimators below are conformance-tested to be byte-identical across
`risksim`, `lossmodels`, and `extremeloss`.

## Risk measures: VaR and TVaR

**Value-at-Risk** uses the actuarial (lower-quantile) definition

$$
\mathrm{VaR}_q(X) \;=\; \inf\{\, x : F(x) \ge q \,\},
$$

whose empirical plug-in is the order statistic $x_{(\lceil nq \rceil)}$ —
equivalent to `np.quantile(losses, q, method="inverted_cdf")`.

**Tail Value-at-Risk** (expected shortfall) uses the average-quantile,
coherent definition

$$
\mathrm{TVaR}_q(X) \;=\; \frac{1}{1-q} \int_q^1 \mathrm{VaR}_u(X)\, du,
$$

whose empirical plug-in (Acerbi–Tasche) is, with sorted losses
$x_{(1)} \le \dots \le x_{(n)}$ and $k = \lceil nq \rceil$,

$$
\mathrm{TVaR}_q \;=\; \frac{\sum_{i>k} x_{(i)} \;+\; x_{(k)}\,(k - nq)}{n\,(1-q)}.
$$

This estimator is exact for the empirical distribution — it weights an atom at
the VaR correctly, reduces to the mean of the largest $n(1-q)$ observations
when $nq$ is an integer, and guarantees $\mathrm{TVaR}_q \ge \mathrm{VaR}_q$
at every $q$.

Where they live: `risksim.var` / `risksim.tvar` for simulated portfolios, the
empirical module in `lossmodels` (including the PMF-based `var_from_pmf` /
`tvar_from_pmf` for discretized aggregates), and the tail metrics in
`extremeloss`. Same formulas, same edge-case behavior, everywhere.

## Randomness and reproducibility

Every `sample` method and Monte Carlo estimator in the ecosystem accepts an
`rng` argument with one convention:

`rng=None` (default)
: Uses the legacy global `numpy.random` state — backward compatible with
  code that calls `np.random.seed(...)`.

`rng=<int>`
: A seed; the function constructs `np.random.default_rng(seed)`.

`rng=<numpy.random.Generator>`
: Used as-is.

Composed simulations thread **one** generator through every draw: a
`CollectiveRiskModel` passes the same generator to its frequency and severity
models, and a `risksim` portfolio run passes it to every contract. Two runs
with the same seed are bit-for-bit identical; two components in one run never
share a seed by accident.

```python
import lossmodels as lm

crm = lm.CollectiveRiskModel(lm.Poisson(lam=120), lm.Lognormal(mu=8.6, sigma=1.4))
crm.sample(10_000, rng=42)     # reproducible
crm.sample(10_000, rng=42)     # ... identical
```

## Distribution naming and parameterizations

Continuous severities follow the *Loss Models* (FAM/ASTAM Appendix A)
parameterizations exactly — the forms on the SOA tables — and moments raise
outside their region of existence rather than returning garbage.

One naming trap is worth stating plainly, because the literature itself is
inconsistent:

| Class | Density support | What it is |
|---|---|---|
| `Pareto(alpha, theta)` | $x \ge \theta$ | **Pareto Type I** (a.k.a. single-parameter Pareto; `SingleParameterPareto` is the same distribution) |
| `ParetoII(alpha, theta)` | $x > 0$ | **Lomax** — the two-parameter distribution *Loss Models* calls simply "Pareto" |

For ground-up claim severities you almost always want `ParetoII`; `Pareto`
(Type I) is the tail-only law with a hard lower support bound. The fitters
mirror the naming: `fit_pareto` fits Type I, `fit_paretoII` fits the Lomax.

## Coverage semantics

`Layer(d, u)` is a payment layer with per-loss payment

$$
Y \;=\; \min\big((X - d)_+,\; u\big),
$$

so `d` is the attachment and **`u` is the maximum payment in the layer (the
width), not the upper attachment point**. A "5M xs 1M" layer is
`Layer(1_000_000, 5_000_000)`. `OrdinaryDeductible(d)` and `PolicyLimit(u)`
are the one-sided special cases.

`discretize_severity` defaults to `method="midpoint"` (since lossmodels
0.6.0) — the standard, nearly unbiased choice for Panjer/FFT input. Pass
`method="upper"` to reproduce pre-0.6 output.

## Truncation and censoring

Fitting functions describe incomplete claim data with one triple, always on
the **ground-up** scale:

`values`
: Observed ground-up amounts. For a censored observation this is the
  censoring point (a lower bound on the loss).

`truncation`
: Per-observation left-truncation points (the deductible); `0` means
  untruncated. Scalars broadcast.

`censored`
: Boolean flags; `True` marks a right-censored observation (the payment hit
  its maximum).

`lossmodels.payments_to_ground_up(payments, deductible, max_payment)` converts
the common per-payment layout — payments net of a deductible, capped at a
maximum payment — into this triple, flagging capped payments as censored. See
the [lossmodels](lossmodels.md) page for the likelihood these conventions
feed.
