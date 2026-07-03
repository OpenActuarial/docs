# ratingmodels

The pricing layer of the ecosystem: manual and experience rate construction,
credibility blending, rate indication and rate-change decomposition, GLM
relativity estimation, model evaluation (Gini and lift), and renewal
constraints — an auditable build-up from base rate to filed rate. Depends on
`actuarialpy` for its credibility and trend primitives. Everything is
vectorized under one contract: the same call that rates one group rates a
whole book of columns.

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
log-link GLM fit by iteratively reweighted least squares. Poisson, gamma, and
Tweedie variance functions; exposure as a log offset; prior weights;
categorical predictors (base level = most populous, or set explicitly) and
continuous covariates in the same linear predictor:

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
```

Standard errors use the Pearson-estimated dispersion (quasi-likelihood — the
robust default for pricing data, where overdispersion is the norm);
`dispersion_`, `null_deviance_`, and a `converged_` flag are exposed
alongside. Unseen levels at prediction time fall back to the base level.

## Model evaluation

A rating plan is judged on segmentation — how well predictions *order* risks.
`gini_coefficient` is the exposure-weighted ordered-Lorenz Gini of pricing
practice (normalized by the perfect model, so 1.0 means perfect segmentation
and 0.0 none), and `lift_table` bands the book into equal-exposure groups by
predicted risk:

```python
pred = model.predict(df, exposure="member_months")

rm.gini_coefficient(df["claims"], pred, exposure=df["member_months"])

rm.lift_table(df["claims"], pred, exposure=df["member_months"], n_bands=10)
# band | n | exposure | predicted_mean | actual_mean | lift
```

A model that segments shows lift rising monotonically across bands; the
Gini summarizes the same ordering in one number, comparable across books.
Both take `by=` group labels to score every segment of a validation frame
at once — a Series of Ginis, and per-group lift tables under a
`(group, band)` MultiIndex.

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
