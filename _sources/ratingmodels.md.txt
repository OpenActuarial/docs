# ratingmodels

The pricing layer of the ecosystem: manual and experience rate construction,
credibility blending, rate indication and rate-change decomposition, GLM
relativity estimation with diagnostics, frequency–severity models,
credibility-smoothed factors, out-of-sample validation (splits, calibration,
actual-to-expected, Gini and lift), renewal constraints, and rate-dislocation
reporting — an auditable path from base rate to filed rate, validated along
the way. Depends on `actuarialpy` for its credibility and trend primitives
and on `statsmodels` for GLM estimation.
Everything is vectorized under one contract: the same call that rates one
group rates a whole book of columns.

## Quickstart

Blend an experience rate with a manual rate and read the indicated change:

```python
import ratingmodels as rm

z = rm.limited_fluctuation_credibility(n=96_000, n_full=120_000)

manual = rm.ManualRate(base_loss_cost=480, factors={"area": 1.05, "industry": 0.97})

indication = rm.RateIndication(
    experience_loss_cost=512,
    manual_loss_cost=manual.loss_cost(),
    credibility=z,
    current_rate=560,
    target_loss_ratio=0.85,
)

indication.indicated_rate_change()        # blended, credibility-weighted change
indication.rate_change_decomposition()    # attribute the change to each driver
```

## Columns in, columns out

Every numeric argument accepts a scalar **or** a column, under one contract
(the [vectorization convention](conventions.md#vectorization-contract)):
scalar in, float out — exactly the call above; Series in, Series out,
elementwise, index preserved, scalars broadcasting. So the quickstart *is*
the book-level code — swap floats for columns:

```python
import pandas as pd
import ratingmodels as rm

book = pd.DataFrame(
    {"n": [820.0, 1450.0, 260.0],
     "base": [420.0, 435.0, 410.0],
     "area": [1.05, 0.98, 1.12],
     "exp_lc": [506.5, 499.2, 494.7],
     "current": [545.0, 560.0, 530.0]},
    index=pd.Index(["G1", "G2", "G3"], name="group"),
)

z = rm.limited_fluctuation_credibility(book["n"], n_full=1_082)
manual = rm.ManualRate(book["base"], factors={"area": book["area"]})

indication = rm.RateIndication(
    experience_loss_cost=book["exp_lc"],
    manual_loss_cost=manual.loss_cost(),
    credibility=z,
    current_rate=book["current"],
)

book["change"] = indication.indicated_rate_change()   # one change per row
rm.renew(book["current"], indication.indicated_rate(),
         cap=0.10, floor=0.0).to_frame()               # tidy renewal actions
```

For this workflow end to end on a three-group book — pooling to book-level
uplift — see [Example 2: pricing a book, in columns](worked-example-book.md).

Validation stays row-level — one bad row fails the call and the error names
the offending index label — and helpers that reduce *across* inputs
(`product`, the build-up engine, `blend`, trend) raise on mismatched Series
indexes rather than silently aligning to NaN. Aggregations grow a `by=` for
the grouped question: `base_rate_from_experience(..., by="segment")` returns
a DataFrame of base rates (one per segment), and `pool_claims(amounts,
point, by=groups)` pools a whole claim file in one pass.

## The build-up engine

Rate build-ups are a sequence of typed steps — start, add, multiply,
checkpoint — evaluated into a result that carries the full audit trail:

```python
import ratingmodels as rm

result = rm.evaluate([
    rm.start("Par base claim cost", 941.63),
    rm.add("$30 specialist copay", -11.44),
    rm.multiply("Rating region", 1.083),
    rm.checkpoint("Net claim cost"),
])

result.value        # final per-unit value
result.to_frame()   # every step as a DataFrame — inputs, factors, running total
```

Because each step is explicit, the build-up is reproducible and reviewable: the
same object renders the number and the audit trail behind it. Operands take
columns too — per-group bases, factors, even `segment_multiply` weights and
participation shares — and the breakdown switches to tidy long format, one
row per `(step, entity)`, with `value` and every checkpoint returned as a
Series on the shared index.

## GLM relativities

`GLMRelativities` estimates rating factors jointly — correcting for the
correlation between rating variables that one-way analysis cannot — with a
log-link GLM. Estimation is delegated to `statsmodels.GLM`: a mature
estimator owns the solver, convergence, covariance, and the fitted null
model, while ratingmodels owns the actuarial layer — the design encoding
and base-level semantics, coefficient-to-relativity conversion, prediction
with unseen-level fallback, and the exhibits. Poisson, gamma, and Tweedie
variance functions; exposure as a log offset for aggregate responses; prior
weights; categorical predictors (base level = most populous, or set
explicitly) and continuous covariates in the same linear predictor:

```python
import ratingmodels as rm

model = rm.GLMRelativities(family="poisson").fit(
    df,
    response="claims",
    predictors=["area", "industry"],     # categorical -> relativities
    continuous=["age"],                  # numeric, enters the predictor directly
    exposure="member_months",            # log offset
    base_levels={"area": "A"},
)

model.relativities_["area"]     # multiplicative factors, base level = 1.0
model.base_value_               # exp(intercept): the base rate
model.summary()                 # coef, SE, z, relativity per term
model.predict(new_df, exposure="member_months")
model.to_factor_tables()        # {"area": FactorTable, ...} for the build-up
model.results_                  # the fitted statsmodels results object
```

Standard errors use the Pearson-estimated dispersion (quasi-likelihood — the
robust default for pricing data, where overdispersion is the norm);
`dispersion_`, `null_deviance_`, `deviance_explained_`, and a `converged_`
flag are exposed alongside. Unseen levels at prediction time fall back to the
base level, and `to_factor_tables()` turns the fitted relativities into
named `FactorTable` lookups with the same unknown-level behavior — the
bridge from estimation into the build-up and renewal machinery. Anything the
wrapper does not surface is one attribute away: `results_` is the fitted
statsmodels object (`results_.get_influence()`,
`results_.get_prediction(...)`, Wald tests, ...).

### Aggregate vs. rate responses

Exposure enters this model in one of two ways, and the difference matters
for everything except Poisson. When the response is an **aggregate** —
claim counts or total amounts — exposure is a log offset:
`E[Y] = e·exp(Xβ)`, so pass `exposure="member_months"`. When the response
is already a **rate** — pure premium, loss per unit, anything divided by
exposure — do *not* pass `exposure`; pass it as `weights` instead, so the
variance scales as `V(μ)/e`. The two parameterizations coincide only at
variance power `p = 1`; for gamma and Tweedie, the weights form is the one
consistent with a response averaged over `e` independent claims. It is
exactly how the severity component of the
[frequency–severity model](#frequencyseverity-models) is fit: response
`amount/count`, weights `count`. `weights` are variance weights throughout
(statsmodels `var_weights`): the variance of row *i* is `φ·V(μᵢ)/wᵢ`.

### Diagnostics

A model that produces relativities but cannot be interrogated is half a
model. Every fitted GLM exposes its residuals and the uncertainty of every
factor:

```python
model.relativity_table(confidence_level=0.95)
# (variable, level) -> coef, se, relativity, ci_low, ci_high, is_base

model.residuals(df, kind="deviance")       # index-aligned Series
model.residuals(df, kind="pearson")        # squares sum to pearson_chi2_
model.residuals(df, kind="standardized")   # leverage-adjusted, ~N(0,1) scale
```

The relativity intervals are `exp(coef ± z·se)` on the quasi-likelihood
standard errors — the base level is shown at 1.0 with no interval (it is the
reference, fixed by construction, not estimated), and continuous covariates
appear as per-unit factors. Column names for `residuals` default to those
used at fit, so `model.residuals(validation_frame)` just works; plotting
deviance or standardized residuals against fitted values and against each
rating variable is the standard check that the variance function and link
are adequate.

The adapter is held to a contract: the test suite fits statsmodels
*independently* — its own family objects, offset construction, and weights,
on the exact design matrix `GLMRelativities` built — and asserts the
marshaling conventions and the in-package evaluation math (residuals,
relativity intervals, family deviance) agree across every family.

There is deliberately no penalized (ridge/lasso) fit: shrinkage would
invalidate exactly this covariance machinery. When thin levels need
stabilizing, use [credibility smoothing](#credibility-smoothed-relativities)
— the actuarial answer, with the uncertainty story intact. Should
regularization at scale ever become a genuine requirement, `glum` is the
designated engine for that job, behind this same API.

### Interactions

When the effect of one variable depends on the level of another — urban
manufacturing is worse than urban *or* manufacturing suggests — add the
pair to the design. Categorical × categorical uses treatment coding (an
indicator per **observed** non-base × non-base cell, so main effects keep
their interpretation and unobserved cells cannot alias the design);
categorical × continuous fits one slope modifier per non-base level:

```python
model = rm.GLMRelativities(family="poisson").fit(
    df, response="claims", predictors=["area", "industry"],
    exposure="member_months",
    interactions=[("area", "industry")],
)

model.relativities_["area:industry"]   # MultiIndex (area, industry) -> factor
model.relativity_table()               # adds ("area:industry", "B | mfg") rows
```

The interaction factor multiplies **on top of** both main effects.
`to_factor_tables()` deliberately excludes interactions — a `FactorTable`
is single-variable by contract; read cells from `relativities_["a:b"]`.

### Prediction intervals

`predict_interval` puts delta-method confidence bounds on the fitted mean
for any frame — the uncertainty of the *rate* the model assigns to a cell,
from the quasi-likelihood coefficient covariance (it matches
`results_.get_prediction` to numerical precision):

```python
model.predict_interval(new_business, exposure="member_months")
# predicted | ci_low | ci_high        (index-aligned with the input)
```

This is an interval for the mean, not for individual outcomes — a single
group's claims vary far more than its expected claims. For outcome
distributions, simulate frequency and severity instead.

## Frequency–severity models

The standard pricing decomposition — `loss_per_exposure = frequency ×
severity`, the ecosystem [convention](conventions.md) — fit as two log-link
GLMs and composed into one pure-premium model:

```python
model = rm.FrequencySeverityModel().fit(
    df,
    claim_count="claim_count",
    claim_amount="claim_amount",
    exposure="exposure",
    frequency_predictors=["area", "industry", "tier"],
    severity_predictors=["industry", "tier"],   # severity thins out fast
)

model.frequency_prediction(df, exposure="exposure")   # expected counts
model.severity_prediction(df)                         # expected cost per claim
model.pure_premium_prediction(df, exposure="exposure")  # exactly their product

model.combined_relativities()["industry"]
# level -> frequency | severity | combined  (combined = product)
model.base_value_        # pure premium per exposure unit at base levels
model.to_factor_tables() # combined relativities as FactorTable lookups
```

Frequency (Poisson by default) fits on every record with exposure as a log
offset; severity (Gamma by default) fits only on records with claims,
weighted by claim count — the average of *k* claims carries *k* claims' worth
of information. Because both links are logs, the pure-premium relativity of a
level is the *product* of its frequency and severity relativities, and
fitting the pieces separately shows *why* a level is expensive — more claims,
larger claims, or both — which a single Tweedie fit cannot. Variables used by
only one component pass through with the other's factor at 1.0. Each
component is a full `GLMRelativities`, so every diagnostic above
(`relativity_table`, `residuals`, `summary`) applies per part.

Rows with positive amounts but zero counts raise (severity is undefined
there); claims closed at zero amount are excluded from the severity fit with
a warning and still count toward frequency.

`predict_interval` exists here too -- component log-scale variances add
under the stated independence of the two fits, and `predicted` equals
`pure_premium_prediction` exactly -- so moving from a GLM to a
frequency-severity model keeps its error bars.

Both components accept interaction terms
(`frequency_interactions=[("area", "industry")]`; severity defaults to the
frequency list). Categorical × categorical cells surface in
`combined_relativities()` under an `"a:b"` key with a MultiIndex of level
pairs, `combined` being the per-cell frequency × severity product;
`to_factor_tables()` excludes interactions, exactly as the GLM does.

## Credibility-smoothed relativities

Sparse levels produce unstable one-way relativities. The classical actuarial
answer is neither dropping them nor generic regularization but credibility:
shrink each level toward a complement, in proportion to the evidence behind
it —

```python
rm.credibility_relativities(
    df, factor="industry", response="claims", exposure="exposure",
    method="buhlmann",          # Z estimated by empirical Bühlmann–Straub
    prior=1.0,                  # or a mapping of current filed factors
)
# level -> n | exposure | response | observed | credibility | prior | relativity
```

`relativity = Z·observed + (1−Z)·prior`, per level. With
`method="buhlmann"` (the default), `Z` comes from the empirical
Bühlmann–Straub estimators across levels — the credibility math lives in
`actuarialpy`, as everywhere in the ecosystem. With
`method="limited_fluctuation"`, the square-root rule
`Z = min(1, √(n/full_credibility))` applies against a full-credibility
standard in response units (for claim counts, `full_credibility_standard`).
A scalar prior of 1.0 shrinks toward "no effect"; passing the current filed
factors as the prior shrinks toward the existing plan instead.

The blunt companion for levels too thin to carry a column at all:

```python
recoded, summary = rm.collapse_sparse_levels(
    df["industry"], exposure=df["exposure"], min_exposure=1_000,
)
df["industry_grouped"] = recoded    # thin levels -> "Other"
```

`summary` records which levels collapsed, so the same recode applies to
future data.

## Validation

A pricing model should be judged on data it did not see, and the *shape* of
the held-out data matters: rows of the same group are correlated, and the
deployed model always predicts forward in time. The splits encode both
facts, with no scikit-learn dependency:

```python
train, valid = rm.temporal_split(df, date="experience_month", cutoff="2025-01-01")
train, valid = rm.group_split(df, group="group_id", test_fraction=0.25,
                              weights="exposure", random_state=0)
train, valid = rm.random_split(df, test_fraction=0.25, random_state=0)
```

`group_split` keeps every group whole on one side (scattering a group's rows
across train and test leaks its risk level into validation); `temporal_split`
cuts at a date for the honest out-of-time test. Each returns `(train, test)`
with row order preserved, and raises rather than silently returning an empty
side.

### Ordering, level, and segments

A rating plan is judged on segmentation — how well predictions *order* risks
— and on calibration — whether they are *right on the level*. The four
exhibits, all exposure-weighted:

```python
pred = model.predict(valid, exposure="exposure")

rm.gini_coefficient(valid["claims"], pred, exposure=valid["exposure"])

rm.lift_table(valid["claims"], pred, exposure=valid["exposure"], n_bands=10)
# band | n | exposure | predicted_mean | actual_mean | lift

rm.calibration_table(valid["claims"], pred, exposure=valid["exposure"])
# band | n | exposure | predicted_mean | actual_mean | ae_ratio

rm.actual_expected_table(valid["claims"], pred, exposure=valid["exposure"],
                         by={"area": valid["area"], "tier": valid["tier"]})
# (variable, level) | n | exposure | actual | expected | means | ae_ratio
```

A model that segments shows lift rising monotonically across bands; the Gini
summarizes the same ordering in one number, comparable across books. A model
that is calibrated shows `ae_ratio` near 1.0 in every calibration band —
systematic drift is the signature of over-shrunk predictions — and in every
segment of the A/E exhibit, which takes one variable, several at once
(tidy `(variable, level)` output), or none for the overall row.
`gini_coefficient`, `lift_table`, and `calibration_table` all take `by=`
group labels to score every segment of a validation frame in one call.

### Comparing candidates

`compare_models` scores fitted GLMs side by side on one frame — pass the
validation split for an honest comparison:

```python
rm.compare_models({"full": full_model, "no_industry": smaller_model},
                  valid, response="claims", exposure="exposure")
# family | n_params | converged | dispersion | deviance | null_deviance
#   | deviance_explained | gini | ae_ratio | calibration_error
```

Deviance is family-specific (comparable within a family); `gini`,
`ae_ratio`, and `calibration_error` compare across families. No AIC is
reported — the standard errors are quasi-likelihood, so a true likelihood is
not available.

## Rate indications

`RateIndication` blends experience against a manual, grosses up through
`RetentionLoad`, and reads off the indicated rate and change — but it
consumes *point* inputs: a trended, developed loss cost and an on-level
premium. `ExperienceExhibit` is where those come from, with every
adjustment a visible worksheet column:

```python
ex = rm.ExperienceExhibit(
    earned_premium=[1_000_000, 1_100_000],
    losses=[700_000, 650_000],
    on_level_factors=olf["on_level_factor"],      # from on_level_factors
    development_factors=proj["development_factor"],  # from ChainLadder
    trend_factors=[1.05, 1.02],
    period_labels=["CY2023", "CY2024"],
)
ex.exhibit()   # premium | OLF | on-level premium | losses | dev | trend
#              #   | adjusted_losses | loss_ratio | weight

ind = ex.to_indication(manual_loss_cost=70.0, credibility=0.6,
                       current_rate=90.0, exposure=24_000, retention=ret)
ind.indicated_rate_change()
```

The wiring is exact by construction: the indication's own
`experience_loss_ratio()` reproduces the exhibit's aggregate ratio, and at
full credibility the indicated rate **is** `retention.gross_rate(...)` of
the assembled loss cost — the same expense algebra as the build-up and
`PricingEvaluation`, not a second implementation that can drift.

## Rating plans

A fitted model is not yet a plan. `RatingPlan` is the implemented object —
a base rate plus a `FactorTable` per rating variable — that rates a census
with the full build-up visible, audits its own coverage, and round-trips
through a dict for filing and version control:

```python
plan = rm.RatingPlan.from_model(model)        # factors + base_value_
plan.validate(census)                          # levels the plan cannot rate
rated = plan.rate(census, exposure="members")  # base_rate | {var}_factor ...
#   | combined_relativity | rate | premium

plan.rate(census, unknown="error")     # unmapped level -> hard stop, not 1.0
plan.average_relativity(census, exposure="members")   # off-balance check
rebuilt = rm.RatingPlan.from_dict(plan.to_dict())     # schema-versioned
```

`plan.rate(...)["premium"]` reproduces `model.predict(...)` exactly when
the plan came from `from_model` — the plan **is** the model, restated as
tables.

Comparing the plan you have against the plan you propose is a first-class
operation:

```python
comp = rm.compare_rating_plans(current, proposed, census, exposure="members")
comp.summary()        # premiums, avg change, share increasing/decreasing
comp.dislocation()    # the banded exhibit (next section)
comp.by(census["region"])   # who absorbs the move
```

## Rate dislocation

An average rate change hides everything operational — who takes a large
increase, how much premium sits in each band, and what the constraints cost.
Band the book by rate change:

```python
rm.rate_dislocation(
    current_rate=df["current_rate"],
    proposed_rate=df["proposed_rate"],
    exposure=df["exposure"],
    bands=[-0.10, -0.05, 0.0, 0.05, 0.10],
)
# band          | n | exposure | current_premium | proposed_premium
#   | avg_change | exposure_share        (+ an "All" total row)
```

Bands are `(low, high]` with empty bands kept, so the exhibit shape is
stable across runs; because the default edges include 0.0, increases and
decreases are always separated. And quantify the gap between the indication
and what was actually proposed — what capping left on the table, and the
rate action still owed:

```python
rm.constraint_impact(
    indicated_rate=df["indicated"],
    proposed_rate=df["issued"],
    exposure=df["exposure"],
    current_rate=df["current_rate"],
    by=df["segment"],           # which segments absorbed the capping
)
# premium_shortfall | premium_excess | n_below/above | exposure_below/above
#   | indicated_change | realized_change | remaining_change
```

Both are pure comparisons of rate vectors, so any source of "current" and
"proposed" works — a renewal run (`renew`), a re-rated plan, or scenario
output.

## On-level factors

Historical premium was earned at historical rates; the indication needs it
at today's. `on_level_factors` is the parallelogram method computed in
closed form — the earned rate index is a piecewise-linear function of time
and is integrated exactly, so the classic textbook case (+10% mid-year,
annual policies, calendar-year period) reproduces `1.1 / 1.0125` to
machine precision rather than to grid resolution:

```python
rm.on_level_factors(
    periods=[("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31")],
    rate_changes=[("2023-07-01", 0.08), ("2024-04-01", 0.05)],
    policy_term=1.0,          # 0 = instant earning; 1.0 = annual parallelogram
)
# period_start | period_end | average_earned_index | current_index
#   | on_level_factor
```

## Pooling charges from a severity model

`experience_rate` takes `pooling_charge` as an input; this is where it
comes from. Any severity object exposing the two-method tail protocol —
`sf(x)` and `mean_excess(d)` — prices the excess layer above a pooling
point, returned as an auditable build-up:

```python
charge = rm.pooling_charge_from_severity(
    severity, pooling_point=250_000, expected_frequency=0.7,
    expense_ratio=0.08, risk_margin=0.05,
)
# exceedance_probability | mean_excess | expected_excess_per_claim
#   | pure_excess_cost | pooling_charge
```

The protocol is duck-typed and deliberately tiny: `lossmodels`
distributions (and layers) satisfy it, `extremeloss` GPD tail fits satisfy
it with their closed-form mean excess, and any custom object with the two
methods qualifies — no cross-package dependency in either direction.

## Pricing scenarios and margin

The indication answers *what does the formula say*; management pricing asks
what margin falls out at the action actually **issued**, after
**concessions**, at **plan** — and what action produces zero or a target
margin. `PricingEvaluation` evaluates a case at any rate action with the
same expense algebra as the gross-up, so at the indicated rate the margin
ratio equals the retention's `profit_margin` exactly:

```python
import ratingmodels as rm

ret = rm.RetentionLoad(fixed_expense=8, variable_expense_ratio=0.10,
                       profit_margin=0.03, lae_ratio=0.02)
case = rm.PricingEvaluation(loss_cost=410, current_rate=470, retention=ret,
                            exposure=14_400, persistency=0.85)

case.at(0.062, name="issued")        # premium, gross margin, margin, ratio
case.rate_change_for_margin(0.03)    # closed form: P(m) = (L(1+lae)+F)/(1-V-m)
case.zero_margin_rate_change()       # the m = 0 special case
```

Evaluate named actions across a book into one tidy long table — cohort
rollups and key-case exhibits are then pivots of library output — and solve
the exhibit input *"actions must be X% higher to hold the target margin"*
in closed form:

```python
tidy = rm.scenario_frame(book, {"formula": formula_actions,
                                "issued": issued_actions, "plan": 0.118})
tidy.pivot(index="case", columns="scenario", values="margin_ratio")

rm.uplift_for_target_margin(book, issued_actions, target_margin=0.03)
```

`book` is either a mapping of scalar evaluations or a single **vector**
`PricingEvaluation` built from columns — loss costs, current rates,
exposures, persistencies as Series — in which case `at()` evaluates every
case at once, `ScenarioOutcome.to_frame()` is one tidy row per case, and
actions may be per-case Series. The uplift solve is the same closed form
either way; the two paths agree to floating point.

Scenario names are your vocabulary — the library evaluates actions and
reports margin; what "issued" or a concession budget means stays with the
caller. Margin definitions are shared ecosystem-wide; see
[conventions](conventions.md).

## API reference

```{eval-rst}
.. automodule:: ratingmodels
   :members:
```
