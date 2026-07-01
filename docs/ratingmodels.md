# ratingmodels

The pricing layer of the ecosystem: manual and experience rate construction,
credibility blending, rate indication and rate-change decomposition, GLM
relativity estimation, and renewal constraints — an auditable build-up from base
rate to filed rate. Depends on `actuarialpy` for its credibility and trend
primitives.

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

## API reference

```{eval-rst}
.. automodule:: ratingmodels
   :members:
```
