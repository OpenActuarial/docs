# ratingmodels

The pricing layer of the ecosystem: manual and experience rate construction,
credibility blending, rate indication and rate-change decomposition, GLM
relativity estimation, model evaluation (Gini and lift), and renewal
constraints — an auditable build-up from base rate to filed rate. Depends on
`actuarialpy` for its credibility and trend primitives.

## Quickstart

Blend an experience rate with a manual rate and read the indicated change:

```python
import ratingmodels as rm

z = rm.limited_fluctuation_credibility(n=96_000, n_full=120_000)

manual = rm.ManualRate(base_pmpm=480, factors={"area": 1.05, "industry": 0.97})

indication = rm.RateIndication(
    experience_claims_pmpm=512,
    manual_claims_pmpm=manual.claims_pmpm(),
    credibility=z,
    current_rate=560,
    target_loss_ratio=0.85,
)

indication.indicated_rate_change()        # blended, credibility-weighted change
indication.rate_change_decomposition()    # attribute the change to each driver
```

## The build-up engine

Rate build-ups are a sequence of typed steps — start, add, multiply,
checkpoint — evaluated into a result that carries the full audit trail:

```python
import ratingmodels as rm

result = rm.evaluate([
    rm.start("Par base claim cost", 941.63),
    rm.add("$30 specialist copay", -11.44),
    rm.multiply("Rating region", 1.083),
    rm.checkpoint("Net claim cost PMPM"),
])

result.value        # final PMPM
result.to_frame()   # every step as a DataFrame — inputs, factors, running total
```

Because each step is explicit, the build-up is reproducible and reviewable: the
same object renders the number and the audit trail behind it.

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

## API reference

```{eval-rst}
.. automodule:: ratingmodels
   :members:
```
