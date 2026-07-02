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

Where they live: `risksim.metrics.var` / `risksim.metrics.tvar` for simulated portfolios, the
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
parameterizations — the forms on the SOA tables — and moments raise outside
their region of existence rather than returning garbage. Frequencies follow
the SciPy conventions instead: `NegativeBinomial(r, p)` is
`scipy.stats.nbinom`, not the tables' $(r, \beta)$, with $\beta = (1-p)/p$.
Every constructor's exact form and its numerically verified `scipy.stats`
equivalent are tabulated on the
[lossmodels page](lossmodels.md#distributions), including the two places the
code deviates from Appendix A as of 0.6.0 (`Exponential(rate)`; Weibull's
`(k, lam)` parameter names).

One naming trap is worth stating plainly, because the literature itself is
inconsistent:

| Class | Density support | What it is |
|---|---|---|
| `Pareto(alpha, theta)` | $x \ge \theta$ | **Pareto Type I** (a.k.a. single-parameter Pareto; `SingleParameterPareto` is the same distribution) |
| `ParetoII(alpha, theta)` | $x > 0$ | **Lomax** — the two-parameter distribution *Loss Models* calls simply "Pareto" |

For ground-up claim severities you almost always want `ParetoII`; `Pareto`
(Type I) is the tail-only law with a hard lower support bound. The fitters
mirror the naming: `fit_pareto` fits Type I, `fit_paretoII` fits the Lomax.

The same trap exists one shelf over. `lossmodels.GeneralizedPareto` is
Klugman's three-parameter transformed-beta severity — what *Loss Models*
calls the generalized Pareto — and **not** the extreme-value GPD. The
peaks-over-threshold law is deliberately not a `lossmodels` severity class:
it lives in `extremeloss`, anchored at its threshold (see *Tail fitting and
splicing* below).

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

## Tail fitting and splicing

The extreme-value GPD is parameterized $(\xi, \beta)$ — **shape** $\xi$
($\xi > 0$ heavy-tailed) and **scale** $\beta$ — anchored at a threshold
$u$. `fit_pot(data, threshold)` selects the exceedances of `data` above $u$
and fits their *excesses* $x - u$; `fit_gpd(excesses)` is the same fit when
the excesses are already in hand. Both return a `GPDFit`, which carries the
exceedance fraction and therefore quotes **unconditional**, ground-up tail
metrics (`gpd_var`, `gpd_tvar`); `GPDTail` is the *conditional* excess law
on $[u, \infty)$ (so $F_{\text{tail}}(u) = 0$), the form a splice consumes.

Splicing is **mass-matching, never density-continuity**:

$$
f(x) = \begin{cases}
w \, \dfrac{f_{\text{body}}(x)}{F_{\text{body}}(u)}, & 0 < x \le u \\[1ex]
(1 - w) \, f_{\text{tail}}(x), & x > u
\end{cases}
$$

with body mass $w = P(X \le u)$ and the body renormalized onto $(0, u]$.
The weight defaults to the empirical body mass $1 - {}$exceedance fraction
(from the data in `fit_spliced_gpd`, from the fit in `splice_gpd_tail`);
pass `weight=` to override. A density jump at the threshold is allowed and
stays visible — it is a diagnostic, not a defect to smooth away.

The handoff runs one direction: `extremeloss` fits the tail and returns a
`lossmodels.SplicedSeverity`, so every downstream consumer — collective
risk models, discretization, a `risksim` portfolio — holds the same
severity class whether or not it carries an EVT tail.

## Rates, exposure, and decomposition

The per-exposure vocabulary is fixed across the reporting stack:
**frequency** $=$ count / exposure, **severity** $=$ loss / count, and
**loss per exposure** $=$ loss / exposure (the pure premium), with the
identity

$$
\text{loss\_per\_exposure} \;=\; \text{frequency} \times \text{severity}
$$

holding row-by-row in every summary and pinned by tests. Rates are derived
*after* aggregation — counts, losses, and exposure are summed first — the
same ratio-of-sums rule as the weighted rollups below.

Trend decomposition reconciles exactly, with zero residual: the two-way
split uses symmetric midpoint weights, the three-way `mix_by` split uses
LMDI (order-free), and in both

$$
\begin{aligned}
\text{loss\_per\_exposure\_trend} &= \text{frequency\_trend} \times \text{severity\_trend} \;(\times\; \text{mix\_trend}) \\
\text{loss\_per\_exposure\_change} &= \text{frequency\_effect} + \text{severity\_effect} \;(+\; \text{mix\_effect}).
\end{aligned}
$$

**Natural units in the core, display constants at the edge.** No function
assumes what an exposure unit measures: nothing annualizes, nothing scales
per thousand, nothing knows a member-month from a car-year. Display
conventions are one visible line in the exhibit — utilization per 1,000 per
year for member-month data is `frequency * 12_000` — so both buried
constants, the period and the prefix, are stated where they are used.
Per-exposure output columns are the mechanical `{name}_per_{exposure_col}`;
the domain-naming rule below governs how a dialect gets its labels back.

## Margin and denominators

Underwriting margin is **two-tier** everywhere in the ecosystem:

$$
\text{gross margin} = \text{total revenue} - \text{total loss}, \qquad
\text{gain/(loss)} = \text{gross margin} - \text{total expense}.
$$

Gross margin is the loss-tier result — operating expense is excluded, which
is also why operating expense never enters a loss ratio. Gain/(loss) is the
underwriting result after expense. Both packages use these identical
definitions: the reporting side in [actuarialpy](actuarialpy.md)
(`UnderwritingSummary`, `underwriting_summary`) and the pricing side in
[ratingmodels](ratingmodels.md) (`PricingEvaluation`), where at charged rate
$P$ with loss cost $L$ per exposure unit, LAE ratio, fixed expense $F$, and
variable load $V$:

$$
\text{gross margin} = P - L(1+\text{lae}), \qquad
\text{margin} = P(1 - V) - L(1+\text{lae}) - F.
$$

At the indicated rate the margin ratio equals the retention's profit
provision $Q$ exactly, and the rate for **any** margin target $m$ has the same
form as the gross-up itself:

$$
P(m) \;=\; \frac{L(1+\text{lae}) + F}{1 - V - m},
$$

with the standard indication as the special case $m = Q$ and the zero-margin
rate at $m = 0$.

**Denominators are parameters, never assumptions.** Real exhibits mix bases
on one page — a loss ratio over total (net) revenue beside an expense ratio
over gross premium — so every ratio in the underwriting summary names its
denominator (`"total_revenue"` or `"premium"`). The identity

$$
\text{gain ratio} \;=\; 1 - \text{combined ratio}
\;=\; 1 - \text{loss ratio} - \text{expense ratio}
$$

holds exactly only when all ratios share one denominator;
`UnderwritingSummary.reconciliation()` reports the gap (for the default
mixed convention, exactly $\text{expense} \cdot (1/\text{gross} -
1/\text{net})$) so the drift is visible instead of silent.

**Domain naming is a view concern.** Required parameter and field names stay
line-agnostic everywhere (`losses`, `expenses`, `loss_cost`, `exposure`);
a domain's vocabulary appears only through the profile / label options on
output views — a health shop's `mlr`, a life shop's `benefit_ratio`, a
`labels={"gain_per_member_months": "gain_pmpm"}` rename — and per-exposure
outputs are always the mechanical `{name}_per_{exposure_col}`, never
inferred from column names. The calculation never changes.

**Weighted rollups.** Additive amounts roll up by summation and their ratios
as ratios of sums — never averages of row-level ratios. Quantities that are
already rates at the row level (rate actions, persistency) are averaged with
an **explicit, required weight** (`weighted_mean`, `weighted_summary`), and
the weight total is reported beside every average.

These are management / pricing metrics. Regulated ratio calculations (for
example, a rebate loss ratio prescribed by statute) have their own numerator
and denominator adjustments and are deliberately out of scope.
