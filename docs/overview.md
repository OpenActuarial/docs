# Overview

The OpenActuarial packages span a connected analytical workflow—from raw experience to portfolio capital—through seven focused, modular libraries. Each package can be installed individually. `actuarialpy` provides the shared calculation primitives, and the experience, projection, and pricing layers build on it.

## Division of labor

- **actuarialpy** — the shared primitives: ratios and per-exposure metrics,
  chain-ladder development and IBNR, credibility, trend, seasonality,
  financial mathematics (time value of money), exposure / age and lifecycle
  bases, size banding, pooling, margins, and weighted rollups. Pure
  calculation on numpy and pandas — no I/O, no composed reports — which
  `experiencestudies`, `projectionmodels`, and `ratingmodels` build on
  directly.
- **experiencestudies** — the study layer: experience summaries and views,
  actual-versus-expected and simple forecasting, claimant and concentration
  analysis, cohort and duration studies, driver and frequency–severity
  decomposition, rolling monitors, banded summaries, the two-tier
  underwriting income statement, and the Excel report writer — study
  functions over the canonical `actuarialpy.Experience`.
- **projectionmodels** — the projection layer: claim, premium, and expense
  projections on supplied exposure, organized as concrete workflows —
  the `project` entrypoint over `ClaimProjection`, `PremiumProjection` with
  effective-dated `RenewalRateActions`, `ExpenseProjection`, projection
  horizons and date cohorts, scenario adjustments, and results that
  summarize without averaging ratios or duplicating exposure.
- **ratingmodels** — the pricing layer: manual and experience rate build-up,
  credibility blending, rate indication and rate-change decomposition, GLM
  relativities with diagnostics and confidence intervals, frequency–severity
  models, credibility-smoothed factors, validation splits and tables, renewal
  constraints, rate-dislocation reporting, and pricing scenarios with
  closed-form margin solves.
- **lossmodels** — loss-distribution modeling: severity and frequency fitting
  (complete data or under deductibles and limits), model selection and
  diagnostics, and aggregate loss.
- **extremeloss** — the tail: peaks-over-threshold / GPD estimation and
  large-claim loading.
- **risksim** — portfolio Monte Carlo and risk measures.

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

The loop between pricing and projection is deliberate, with the division of
labor stated honestly: the pricing layer produces the *indicated* change,
the *selected* action is a renewal-strategy decision that the indication and
the `experiencestudies` monitoring views inform rather than determine, and
`PremiumProjection` takes whatever was selected (as `RenewalRateActions`),
because you project the rates you set. The
distribution work is its own forward-looking mode — severity and frequency
in `lossmodels`, the tail in `extremeloss`, aggregate simulation and risk
measures in `risksim` — and it reaches the deterministic side through
pricing: any severity object exposing `sf` and `mean_excess` prices a
pooling charge in `ratingmodels`, which enters `ClaimProjection` as a
`rate_load`. `actuarialpy` is not a stage data passes through: it is the
primitives layer the boxed packages are built on. Every package is usable on
its own — enter the graph wherever your problem starts. The install-time
picture is below.

## Dependencies

The dependency direction is strictly one-way, from the workflow layers down
to the core. `experiencestudies`, `projectionmodels`, and `ratingmodels` each
depend on `actuarialpy` and delegate their credibility, trend, completion,
seasonality, and time-value math to it rather than re-implementing;
`ratingmodels` also depends on `statsmodels`, to which it delegates GLM
estimation for the same reason. `extremeloss` can optionally pull in
`lossmodels` through its `splice` extra for severity splicing. `lossmodels`
and `extremeloss` stay array-level at the core but each ships an optional
`integrations/actuarialpy` module (the `actuarialpy` extra) that consumes the
canonical claims-listing `Experience` -- an optional edge pointing the same
direction as every other. `risksim`'s core is numpy-only: it consumes fitted models through a formal
`SupportsSample` protocol -- anything with a `.sample()` method, which every
`lossmodels` distribution and `extremeloss` tail fit satisfies, along with
any distribution object from outside the ecosystem -- so its only declared
edge is a dev-extra on `lossmodels` for its own tests. It never touches
experience, so no edge to `actuarialpy` exists or should.

:::{mermaid}
flowchart LR
    AP["actuarialpy<br/>primitives + Experience contract"]:::core
    ES["experiencestudies"]
    PM["projectionmodels"]
    RM["ratingmodels"]
    LM["lossmodels"]
    EL["extremeloss"]
    RS["risksim"]
    ES -->|requires| AP
    PM -->|requires| AP
    RM -->|requires| AP
    EL -.->|optional, via splice| LM
    LM -.->|optional, via actuarialpy extra| AP
    EL -.->|optional, via actuarialpy extra| AP
    LM -.->|".sample() protocol, dev extra"| RS
    EL -.->|".sample() protocol"| RS
    classDef core fill:#eaf2ff,stroke:#3a6ea5,stroke-width:2px,color:#1a1a1a
:::

`extremeloss` pulls in matplotlib
only through its optional `plot` extra (`pip install "extremeloss[plot]"`), for
the diagnostic plots; the base install does not require it. `experiencestudies`
pulls in openpyxl only through its `excel` extra, for the workbook writer.

Where packages *cooperate without depending*, they do it through a
deliberately tiny duck-typed protocol: any severity object exposing
`sf(x)` and `mean_excess(d)` — every `lossmodels` distribution, every
`extremeloss` GPD tail fit — plugs into
`ratingmodels.pooling_charge_from_severity`. The seam is two methods, not
an import. `risksim` runs on the same principle from the other side: its
`SupportsSample` protocol accepts any object with `.sample()` -- every
`lossmodels` distribution, every `extremeloss` tail, or any distribution you
bring from outside the ecosystem -- so the workflow diagram's arrows into
`risksim` are protocol seams, not imports. The data-object seam works the same way in reverse: the
`Experience`/`ExperienceSet` contract flows *up* through the layers as data,
while every import edge keeps pointing *down* -- a package consuming the
contract is a package depending on `actuarialpy`, never the other way
around.

## Conventions

Every package works on plain numpy arrays and pandas Series/DataFrames. There is
no framework to buy into: functions take and return the data structures you
already have, and the classes (`Experience`, `ManualRate`, `RateIndication`, …)
are thin, inspectable wrappers over those functions. Cross-package numerical
conventions — the empirical VaR/TVaR estimators, the `rng` reproducibility
contract, distribution naming, coverage semantics, and the truncation/censoring
data layout — are collected on the [Conventions](conventions.md) page.

These conventions are enforced, not aspirational. The distribution
parameterizations are pinned against `scipy.stats` by conformance tests, the
risk-measure estimators are asserted byte-identical across the three packages
that implement them, the identities quoted on the conventions page are test
assertions, every example script is executed by its package's test suite, and
the [worked examples](worked-example-experience.md) are themselves regression tests.
