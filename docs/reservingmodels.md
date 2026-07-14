# reservingmodels

Claims development and stochastic reserve estimation: chain-ladder and the
deterministic methods re-exported from `actuarialpy`, Mack's analytic standard
errors, and the over-dispersed-Poisson bootstrap of the full predictive
reserve distribution, with residual diagnostics.

The deterministic triangle engine — chain-ladder development, completion
factors, Bornhuetter–Ferguson / Benktander / Cape Cod, and Mack standard
errors — lives in `actuarialpy.reserving`, where those primitives already sit
because `actuarialpy.Experience.complete()` and the projection and pricing
packages build on them. `reservingmodels` re-exports them as **aliases**
(`reservingmodels.ChainLadder is actuarialpy.ChainLadder`) so a reserving
analyst has one import for the whole workflow, and adds the stochastic layer on
top. It depends on `actuarialpy` directly for that reason; it composes with
`risksim` through the `.sample()` protocol, with no dependency in either
direction.

Empirical tail measures follow the ecosystem VaR/TVaR estimators, and every
simulation accepts the shared `rng` argument (`None`, a seed, or a
`Generator`) — see [Conventions](conventions.md).

The full features run end to end, with every number shown, in
[Example 11: the reserve, with a distribution](worked-example-reserving.md).

## Triangles and the deterministic engine

A triangle is a square `K × K` cumulative development array — origins on the
index, developments `0 … K-1` on the columns, the unobserved lower-right as
`NaN`. The deterministic methods are the re-exported `actuarialpy` primitives:

```python
import reservingmodels as rv

triangle = rv.datasets.taylor_ashe()      # canonical benchmark; reserve 18,680,856

cl = rv.ChainLadder.fit(triangle)         # volume-weighted development
cl.project(triangle)                      # per-origin ultimate and IBNR
cl.mack_standard_errors(triangle)         # Mack (1993) distribution-free SE
```

`develop_ultimate` applies Bornhuetter–Ferguson, Benktander, or Cape Cod with a
supplied a-priori; `completion_factors` / `apply_completion` cover the health
completion-factor (lag) workflow; `make_completion_triangle` builds a triangle
from transaction-grain claims. Because these are aliases, a pattern fitted
through `reservingmodels` is the same object `actuarialpy` and the other
packages use. Their full reference lives on the [actuarialpy](actuarialpy.md)
page; the API section below documents only what `reservingmodels` adds.

## The bootstrap: a predictive distribution

The chain ladder gives one number; the bootstrap gives its distribution.
`BootstrapODP` implements the semiparametric over-dispersed-Poisson bootstrap
of England & Verrall. Incremental claims follow an ODP with mean
$m_{ij}=x_i y_j$ and $\mathrm{Var}[C_{ij}]=\phi\,m_{ij}$; the MLE of $m$ equals
the volume-weighted chain-ladder fitted incrementals, so this is the stochastic
layer *on top of* the chain ladder — its mean reproduces the chain-ladder
reserve. Each replicate resamples the degrees-of-freedom-adjusted Pearson
residuals into a pseudo-triangle (estimation error), refits, and draws each
future cell from $\mathrm{Gamma}(m^\*/\phi,\ \phi)$ (process error).

```python
boot = rv.BootstrapODP.fit(triangle)
boot.dispersion          # Pearson phi (52,601 on Taylor–Ashe)
boot.point_reserve       # the chain-ladder reserve — report this
dist = boot.reserve_distribution(size=100_000, rng=42)
```

## Reading the distribution

`reserve_distribution` returns a `ReserveDistribution`: the simulated reserves
with the point estimate and convenience summaries.

```python
dist.point_reserve         # chain-ladder point estimate (the central figure)
dist.mean()                # bootstrap mean — ~1% high (ratio-estimator bias)
dist.prediction_error()    # SD of the predictive distribution
dist.quantile(0.99)        # empirical VaR (inverted-CDF)
dist.tvar(0.99)            # empirical TVaR (Acerbi–Tasche)
dist.to_frame()            # per-origin + total predictive exhibit
```

Two rules the API is built around. **Report the point estimate, not the
bootstrap mean** — the mean carries the small upward bias of a product of ratio
estimators, so `point_reserve` is the central figure and the bootstrap supplies
the spread and the tail. And **the prediction error need not match Mack**: Mack
assumes $\mathrm{Var}\propto C$, the ODP assumes $\mathrm{Var}\propto$ mean, so
on Taylor–Ashe the bootstrap runs about 22% above Mack — a genuine difference
between two variance models of the same quantity, not an error.

## Diagnostics

The bootstrap is only as trustworthy as the ODP assumptions: that the Pearson
residuals carry no pattern in origin, development, or calendar direction.

```python
rv.pearson_residuals(triangle)     # tidy: origin, development, calendar, residual
rv.residual_summary(triangle)      # count, mean, std, min, max
rv.calendar_year_effects(triangle) # mean residual by calendar diagonal
```

A trend across `calendar` is the classic warning that one development pattern
does not describe every diagonal — a claims-inflation or process change the
chain ladder, and therefore the bootstrap, would miss. When the model holds the
residual standard deviation sits near $\sqrt{\phi}$ and the mean near zero.

## Reserve risk as capital

A fitted `BootstrapODP` exposes `.sample(size, rng)` — one draw is one
simulated total unpaid amount — so it is a `risksim` portfolio component with
no cross-dependency:

```python
import risksim as rs

port = rs.Portfolio([rs.PortfolioItem("reserve_risk", boot)])
sim = port.simulate(100_000, rng=7)
rs.metrics.tvar(sim.gross_losses, 0.99)     # capital held for the reserve
```

Aggregating several reserving segments, and imposing a rank correlation across
them, is then the standard `risksim` workflow (the dependence mechanics are
[Example 9](worked-example-dependence.md)).

## API reference

```{eval-rst}
.. automodule:: reservingmodels
   :members:
   :exclude-members: ChainLadder, chain_ladder_by, completion_factors, completion_factors_by, apply_completion, develop_ultimate, make_completion_triangle, validate_completion_factors, development_months, lag_months, ibnr
```

## Fitting from an `Experience`

`reservingmodels.integrations.actuarialpy` builds the triangle — and a fitted
bootstrap — straight from a claims-listing `actuarialpy.Experience` (one row per
transaction, with an origin period and a valuation period):

```python
from reservingmodels.integrations import actuarialpy as seam

triangle = seam.triangle_from_experience(exp, origin="origin_date",
                                         valuation="valuation_date")
boot = seam.fit_bootstrap_from_experience(exp, origin="origin_date",
                                          valuation="valuation_date")
```

Because `reservingmodels` re-exports `actuarialpy` it always has the dependency
available, so this seam needs no optional extra.
```{eval-rst}
.. automodule:: reservingmodels.integrations.actuarialpy
   :members:
```
