# OpenActuarial

OpenActuarial is a dependency-light Python ecosystem for general actuarial workflows, including experience analysis, projection, rating and pricing models, loss modeling, tail estimation, simulation, and portfolio capital. The packages are modular and can be installed individually, with `actuarialpy` providing the shared calculation primitives that the workflow packages build on.

## The ecosystem

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} actuarialpy
:link: actuarialpy
:link-type: doc

**The primitives.** Ratios and per-exposure metrics, chain-ladder
development and IBNR, credibility, trend, seasonality, financial
mathematics, exposure and lifecycle bases, banding, pooling, margins,
and weighted rollups — pure calculation on numpy and pandas, which the
experience, projection, and pricing layers build on directly.
:::

:::{grid-item-card} experiencestudies
:link: experiencestudies
:link-type: doc

**Experience.** Experience reporting and analysis — summaries and views,
actual-versus-expected, claimant and concentration analysis, cohort and
duration studies, driver and frequency–severity decomposition, rolling
monitors, banded summaries, and the two-tier underwriting summary —
study functions over the canonical `Experience`.
:::

:::{grid-item-card} projectionmodels
:link: projectionmodels
:link-type: doc

**Projection.** Focused claim, premium, and expense projections on
supplied exposure — renewal rate actions, a complete → deseasonalize →
trend → blend → reseasonalize claim pipeline, scenario adjustments, and
exposure-weighted summaries of the results.
:::

:::{grid-item-card} ratingmodels
:link: ratingmodels
:link-type: doc

**Pricing.** Manual and experience rate build-up, credibility blending,
rate indication and decomposition, GLM relativities with diagnostics,
frequency–severity models, validation splits and tables, renewal
constraints, dislocation reporting, and pricing scenarios with margin
targets.
:::

:::{grid-item-card} lossmodels
:link: lossmodels
:link-type: doc

**Loss modeling.** Severity and frequency fitting — including under
deductibles and limits — and aggregate loss distributions.
:::

:::{grid-item-card} extremeloss
:link: extremeloss
:link-type: doc

**Tails.** Extreme-value tail estimation — peaks-over-threshold / GPD and
large-claim loading.
:::

:::{grid-item-card} risksim
:link: risksim
:link-type: doc

**Capital.** Portfolio Monte Carlo simulation and risk measures.
:::

::::

## The workflow

In use, the packages compose into a renewal cycle: study the experience,
project claims, set rates, and project premium under those rates. Every
arrow below corresponds to a real interface.

:::{mermaid}
flowchart LR
    subgraph CORE["built on actuarialpy"]
        ES["experiencestudies<br/>experience"]
        PM["projectionmodels<br/>projection"]
        RM["ratingmodels<br/>pricing"]
    end
    ES --> PM
    ES --> RM
    PM -- "projected loss cost" --> RM
    RM -- "indicated changes & loads" --> PM
    LM["lossmodels<br/>severity & frequency"] -- "pooling charge" --> RM
    EL["extremeloss<br/>tail"] -- "pooling charge" --> RM
    LM -. "splice" .-> EL
    LM --> RS["risksim<br/>capital"]
    EL --> RS
    classDef core fill:#eaf2ff,stroke:#3a6ea5,stroke-width:2px,color:#1a1a1a
    class CORE core
:::

The pricing–projection pair is deliberately a loop, with one honest caveat
about who decides what. Pricing produces the *indicated* change; the
*selected* action is a business decision — renewal strategy, cohort review,
underwriting judgment — that the indication and the monitoring views inform
rather than determine. In ecosystem terms: `ratingmodels` supplies the
indication, `experiencestudies` supplies the cohort, persistency, and
actual-versus-expected views the forum argues from, and
`RenewalRateActions` carries whatever was selected, because you project the
rates you set. `rm.renew`'s cap-and-floor is a mechanical stand-in for that
selection, not a claim that pricing makes it. The severity
and tail work runs as its own forward-looking mode — fit the body, splice
the tail, simulate the aggregate, measure the capital — and reaches the
deterministic side through pricing: any severity exposing `sf` and
`mean_excess` prices a pooling charge, which enters the claim projection as
a rate load. `actuarialpy` is not a stage data passes through: it is the
primitives layer the boxed packages are built on, and the ecosystem's only
required install edges point into it (the [overview](overview.md) draws the
dependency graph).

Each seam above is runnable end to end — see the worked examples:
[Example 1: experience to a renewal rate](worked-example-experience.md),
[Example 2: pricing a book, in columns](worked-example-book.md),
[Example 3: claims to capital](worked-example.md),
[Example 4: censored payments to coverage terms](worked-example-coverage.md),
[Example 5: triangle to indicated change](worked-example-indication.md),
[Example 6: pricing the tail, with error bars](worked-example-tail.md),
[Example 7: the renewal cycle, projected](worked-example-projection.md),
[Example 8: the plan, the actuals, and the miss](worked-example-monitoring.md),
[Example 9: two lines, one tail](worked-example-dependence.md),
[Example 10: the pinned ratio, two ways](worked-example-contract.md), and
[the ecosystem tour](worked-example-every-package.md).

## From source tables to a whole workflow

The shortest path from raw extracts to an analysis is one construction call:
three source tables — membership, a claims listing, billing — become one
[`ExperienceSet`](data-model.md), and the same `book` then routes itself to
each package at the grain that package needs.

```python
import actuarialpy as ap
import experiencestudies as es
import ratingmodels as rm

# one construction call: membership defines the grain, each Source names its role
book = ap.ExperienceSet.from_tables(
    membership,                                  # one row per member-month
    grain=["member_id", "month"], exposure="member_months",
    sources=[
        ap.Source(claim_lines, expense="paid_amount",
                  date="incurred_date", name="claims"),
        ap.Source(billing, revenue="billed_premium"),
    ],
    date="month", period="M", dimensions="group_id",
    valuation_date="2026-06-30",
)

book.reconcile()                          # ties every listing back to the tab
es.summary(book, "group_id")              # tab -> grouped experience study
rm.experience_rate(book, by="group_id")   # tab -> credibility-blended indication
# book["claims"] (claim-line grain) -> severity, frequency, and tail fitting
```

```text
ExperienceSet.from_tables(membership, claims, billing)
├── book.tab       -> experience studies / projection / rating   (member-month grain)
└── book["claims"] -> severity / frequency / tail fitting          (claim-line grain)
```

One source definition, several workflows — see [Start here: one data
definition across the ecosystem](worked-example-every-package.md) for the full
tour, and [Choosing your input](choosing-your-input.md) for when to reach for
the object model versus plain pandas.

## A composition on one table

With a single prepared table you wrap it directly — the study layer reads the
block, the primitives supply credibility, and the pricing layer blends and
indicates. Every number below is real output:

```python
import pandas as pd
import actuarialpy as ap
import experiencestudies as es
import ratingmodels as rm

df = pd.DataFrame({
    "month": pd.date_range("2025-01-01", periods=12, freq="MS"),
    "segment": ["north"] * 12,
    "incurred": [8_000 * v for v in [498, 505, 512, 508, 516, 511,
                                    519, 514, 522, 517, 509, 513.0]],
    "premium": [8_000 * 560.0] * 12,
    "member_months": [8_000] * 12,
})

# study layer: how is the block performing?
exp = ap.Experience(df, expense="incurred", revenue="premium",
                    exposure="member_months", date="month")
seg = es.summary(exp, "segment")                            # loss ratio 0.914
loss_cost = seg["total_expense_per_member_months"].iloc[0]  # 512.00 per member-month

# primitives: credibility from exposure (lives in actuarialpy)
z = ap.limited_fluctuation_z(exposure=96_000, full_credibility_standard=120_000)  # 0.894

# pricing: blend against a manual rate and indicate
manual = rm.ManualRate(base_loss_cost=480, factors={"area": 1.05, "industry": 0.97})
indication = rm.RateIndication(
    experience_loss_cost=loss_cost,
    manual_loss_cost=manual.loss_cost(),
    credibility=z,
    current_rate=560,
    target_loss_ratio=0.85,
)

indication.indicated_rate_change()        # +7.0% — blended, credibility-weighted
indication.rate_change_decomposition()    # attribute the change to each driver
```

Every numeric argument in the pricing calls also accepts a column — the same
call prices a whole book; see
[Example 2: pricing a book, in columns](worked-example-book.md).

## Install

```bash
pip install actuarialpy experiencestudies projectionmodels ratingmodels lossmodels extremeloss risksim
```

Any subset works — pip resolves the declared dependencies: the workflow
packages (`experiencestudies`, `projectionmodels`, `ratingmodels`) declare
`actuarialpy`, and `ratingmodels` additionally declares `statsmodels`.

:::{toctree}
:hidden:
:caption: Getting started
:maxdepth: 1

overview
choosing-your-input
worked-example-every-package
:::

:::{toctree}
:hidden:
:caption: The data model
:maxdepth: 1

data-model
:::

:::{toctree}
:hidden:
:caption: Packages
:maxdepth: 1

actuarialpy
experiencestudies
projectionmodels
ratingmodels
lossmodels
extremeloss
risksim
:::

:::{toctree}
:hidden:
:caption: Worked examples
:maxdepth: 1

worked-example-experience
worked-example-book
worked-example
worked-example-coverage
worked-example-indication
worked-example-tail
worked-example-projection
worked-example-monitoring
worked-example-dependence
worked-example-contract
:::

:::{toctree}
:hidden:
:caption: Reference
:maxdepth: 1

conventions
validation
stability
:::
