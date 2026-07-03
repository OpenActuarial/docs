# Example 2: pricing a book, in columns

Everything in `ratingmodels` follows the
[vectorization contract](conventions.md#vectorization-contract): scalar in,
float out; column in, column out. That makes column-wise the default way to
run anything bigger than one case — the objects are the same ones the scalar
API uses, their fields are just columns, and one call prices the book. This
page rates a three-group block end to end without a single Python loop:

    claim file -> grouped pooling -> experience and manual rates
    -> credibility -> indication -> per-case decomposition
    -> capped renewals -> pricing scenarios -> book-level uplift

Every number on this page is the output of this exact run, pinned by a
regression test in the `ratingmodels` suite.

## The book

One row per group, plus a large-claim file and each group's routine (bulk)
claims:

```python
import numpy as np
import pandas as pd
import ratingmodels as rm

book = pd.DataFrame(
    {
        "exposure": [9_600.0, 14_400.0, 6_000.0],     # member-months here
        "current":  [545.0, 560.0, 530.0],            # charged today
        "base":     [420.0, 435.0, 410.0],            # manual base loss cost
        "area":     [1.05, 0.98, 1.12],               # manual relativities
        "industry": [1.10, 1.00, 0.95],
        "n_claims": [820.0, 1_450.0, 260.0],          # credibility counts
    },
    index=pd.Index(["G1", "G2", "G3"], name="group"),
)

large = pd.DataFrame({"group": ["G1", "G1", "G2", "G3", "G3"],
                      "amount": [390e3, 310e3, 420e3, 610e3, 260e3]})
bulk = pd.Series([3.65e6, 5.88e6, 2.03e6], index=book.index)
```

## Pool the claim file

Grouped questions take `by=`. One pass over the claim file pools every
group at once:

```python
_, excess = rm.pool_claims(large["amount"], 250_000, by=large["group"])
incurred = bulk + large.groupby("group")["amount"].sum()

excess      # G1 200,000   G2 170,000   G3 370,000
incurred    # G1 4,350,000 G2 6,300,000 G3 2,900,000
```

## Experience and manual rates

The same constructors as the scalar workflow — the fields are columns now.
Validation stays row-level: one bad row fails the call, and the error names
the offending index label.

```python
retention = rm.RetentionLoad(fixed_expense=12.0, variable_expense_ratio=0.11,
                             profit_margin=0.03, lae_ratio=0.02)

experience = rm.ExperienceRate(
    incurred_claims=incurred,
    exposure=book["exposure"],
    trend_annual=0.07, trend_years=1.5,          # factor 1.1068, broadcast
    pooled_excess=excess,
    pooling_charge=28.0,
    retention=retention,
)
manual = rm.ManualRate(
    book["base"],
    {"area": book["area"], "industry": book["industry"]},
    retention=retention,
)
z = rm.limited_fluctuation_credibility(book["n_claims"], n_full=1_082)

experience.loss_cost()   # G1 506.47   G2 499.17   G3 494.71
manual.loss_cost()       # G1 485.10   G2 426.30   G3 436.24
z                        # G1 0.871    G2 1.000    G3 0.490
```

## The indication

Every derived quantity comes back as a Series on the book's index, so the
priced book is one `assign`:

```python
indication = rm.RateIndication(
    experience_loss_cost=experience.loss_cost(),
    manual_loss_cost=manual.loss_cost(),
    credibility=z,
    current_rate=book["current"],
    trend_total_factor=experience.trend_factor(),
    retention=retention,
)

priced = book.assign(
    blended=indication.blended_loss_cost().round(2),
    indicated=indication.indicated_rate().round(2),
    change=indication.indicated_rate_change().round(4),
)
#        exposure  current  blended  indicated  change
# group
# G1       9600.0    545.0   503.70     611.37  0.1218
# G2      14400.0    560.0   499.17     605.99  0.0821
# G3       6000.0    530.0   464.90     565.35  0.0667
```

## Why each rate moved

The decomposition runs per case; `to_frame()` stacks it into a tidy
`(case, driver)` long table, and the percentage-point contributions sum to
each row's total change exactly:

```python
d = indication.rate_change_decomposition()
d.to_frame().round(4).loc["G1"]
#              factor  pct_point_contribution
# driver
# trend        1.1068                  0.1075
# experience   1.0383                  0.0399
# benefit      1.0000                  0.0000
# demographic  1.0000                  0.0000
# residual     0.9761                 -0.0257

np.allclose(d.contributions.sum(axis=1), np.asarray(d.total_factor) - 1)
# True
```

## Constrain to bookable renewals

Caps and floors may be per-row vectors. `capped` reflects only a binding
cap or floor — G1's 10% cap binds; G2 and G3 renew at the formula:

```python
action = rm.renew(book["current"], indication.indicated_rate(),
                  cap=pd.Series([0.10, 0.10, 0.12], index=book.index),
                  floor=0.0)
action.to_frame().round(4)
#        current_rate  indicated_rate  proposed_rate  indicated_change  proposed_change  capped
# group
# G1            545.0        611.3669         599.50            0.1218           0.1000    True
# G2            560.0        605.9872         605.99            0.0821           0.0821   False
# G3            530.0        565.3475         565.35            0.0667           0.0667   False
```

## The book as one evaluation

A `PricingEvaluation` built from columns *is* the book. `scenario_frame`
takes it directly, and actions can be a per-case vector, a mapping, or one
number that broadcasts:

```python
evaluation = rm.PricingEvaluation(
    loss_cost=indication.blended_loss_cost(),
    current_rate=book["current"],
    retention=retention,
    exposure=book["exposure"],
    persistency=pd.Series([0.90, 0.95, 0.80], index=book.index),
)
tidy = rm.scenario_frame(evaluation, {
    "formula": indication.indicated_rate_change(),   # per-case vector
    "issued":  action.proposed_change,               # the capped actions
    "plan":    0.05,                                 # one number, broadcast
})
tidy.pivot(index="case", columns="scenario", values="margin_ratio").round(4)
# scenario  formula  issued    plan
# case
# G1           0.03   0.013 -0.0288
# G2           0.03   0.030  0.0037
# G3           0.03   0.030  0.0163
```

The `formula` column is the algebra closing: at the indicated rate the
margin ratio equals the retention's `profit_margin` exactly (see
[margin and denominators](conventions.md#margin-and-denominators)). The
`issued` column prices the concession — G1's cap costs 1.7 points of
margin.

## One number for the meeting

The closed-form uplift answers *"issued actions must be how much higher to
hold the book's 3% target?"* — persistency-and-exposure weighted, agreeing
with the scalar mapping form to floating point:

```python
rm.uplift_for_target_margin(evaluation, action.proposed_change,
                            target_margin=0.03)
# +0.6332%
```

## The receipts

The contract is pinned against row-by-row scalar loops throughout the test
suite; on this page's renewal, `max |vector − loop|` is exactly `0.0`. The
same workflow ships as a runnable script in the repository,
[`examples/vectorized_book.py`](https://github.com/OpenActuarial/ratingmodels/blob/main/examples/vectorized_book.py),
and the contract itself — return-type rules, broadcasting, labeled
elementwise validation, index-alignment guards, `by=` — is specified in
[conventions](conventions.md#vectorization-contract) and summarized in
[ratingmodels: columns in, columns out](ratingmodels.md#columns-in-columns-out).
