# Overview

The OpenActuarial packages cover one analytical arc — from raw experience to
portfolio capital — as five focused libraries organized around a shared core.
Each installs and runs on its own; `actuarialpy` holds the primitives the others
can build on.

## Division of labor

- **actuarialpy** — experience analysis on a tidy table, and the shared
  primitives: PMPM and loss-ratio metrics, trend, completion, seasonality,
  credibility, financial mathematics (time value of money), and exposure /
  age bases. `ratingmodels` builds directly on these.
- **ratingmodels** — the pricing layer: manual and experience rate build-up,
  credibility blending, rate indication and rate-change decomposition, GLM
  relativities, and renewal constraints.
- **lossmodels** — loss-distribution modeling: severity and frequency fitting,
  and aggregate loss.
- **extremeloss** — the tail: peaks-over-threshold / GPD estimation and
  large-claim loading.
- **risksim** — portfolio Monte Carlo and risk measures.

## The workflow

Read left to right, the packages trace one analysis — experience, then pricing,
then loss, tail, and capital:

:::{mermaid}
flowchart LR
    AP["actuarialpy<br/>experience"]:::core
    RM["ratingmodels<br/>pricing"]
    LM["lossmodels<br/>loss"]
    EL["extremeloss<br/>tail"]
    RS["risksim<br/>capital"]
    AP --> RM --> LM --> EL --> RS
    classDef core fill:#eaf2ff,stroke:#3a6ea5,stroke-width:2px,color:#1a1a1a
:::

The arrows are the analytical sequence, not install requirements: every package
is usable on its own, and you can enter the arc at whatever stage your problem
starts.

## Dependencies

Only one package requires another. `ratingmodels` depends on `actuarialpy` and
delegates its credibility, trend, and time-value math to the core rather than
re-implementing them. `extremeloss` can optionally pull in `lossmodels` through
its `splice` extra for severity splicing. `lossmodels` and `risksim` have no
internal dependencies.

:::{mermaid}
flowchart LR
    AP["actuarialpy<br/>shared core"]:::core
    RM["ratingmodels"]
    LM["lossmodels"]
    EL["extremeloss"]
    RS["risksim"]
    RM -->|requires| AP
    EL -.->|optional, via splice| LM
    classDef core fill:#eaf2ff,stroke:#3a6ea5,stroke-width:2px,color:#1a1a1a
:::

Dependencies stay light — numpy and pandas in the core and `ratingmodels`, with
scipy (and matplotlib in `extremeloss`) where the loss and tail work needs it.

## Conventions

Every package works on plain numpy arrays and pandas Series/DataFrames. There is
no framework to buy into: functions take and return the data structures you
already have, and the classes (`Experience`, `ManualRate`, `RateIndication`, …)
are thin, inspectable wrappers over those functions.