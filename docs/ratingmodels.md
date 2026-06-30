# ratingmodels

Group rate build-up and indication — the pricing layer between experience analysis and
loss modeling. It turns a base rate and rating factors into a manual rate, blends a
group's own experience by credibility, grosses up through retention to a charged rate,
and explains the change. Every build-up produces a reconciling, auditable breakdown.
numpy and pandas only; credibility comes from `actuarialpy`.

## Quickstart

```python
import actuarialpy as ap
import ratingmodels as rm

# credibility for the group's own experience (from the shared core)
z = ap.limited_fluctuation_z(exposure=96_000, full_credibility_standard=120_000)

# manual rate from a base and rating relativities
manual = rm.ManualRate(base_pmpm=480, factors={"area": 1.05, "industry": 0.97})

# blend experience against the manual and indicate a rate change
indication = rm.RateIndication(
    experience_claims_pmpm=512,
    manual_claims_pmpm=manual.claims_pmpm(),
    credibility=z,
    current_rate=560,
    target_loss_ratio=0.85,
)

indication.indicated_rate_change()       # the indicated rate change
indication.rate_change_decomposition()   # an auditable explanation of the change
```

## The build-up engine

A rate is assembled by an ordered, auditable sequence of operations — `start`,
`multiply` (a relativity), `add` (a dollar amount), `segment_multiply`, and
`checkpoint` — that yields a reconciling breakdown, like a rating worksheet:

```python
import ratingmodels as rm

med = rm.evaluate([
    rm.start("Par Base Claim Cost", 941.63),
    rm.add("$30 specialist copay", -11.44),
    rm.multiply("Rating Region", 1.083),
    rm.checkpoint("Medical Par Base Claim Cost"),
])

med.value        # final running total
med.breakdown    # DataFrame: step, operation, label, operand, running_total
```

The package supplies the build-up *grammar* and the retention gross-up (where the target
loss ratio falls out as an output, not an input); the factor values stay in your code.

## API reference

::: ratingmodels
    options:
      docstring_style: numpy
