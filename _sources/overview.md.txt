# Overview

The OpenActuarial packages cover one workflow — from raw experience to portfolio
capital — as five focused libraries over a shared core.

## Division of labor

- **actuarialpy** — experience analysis on a tidy table, and the shared
  primitives: PMPM and loss-ratio metrics, trend, completion, seasonality,
  credibility, financial mathematics (time value of money), and exposure /
  age bases. Everything else depends on it.
- **ratingmodels** — the pricing layer: manual and experience rate build-up,
  credibility blending, rate indication and rate-change decomposition, GLM
  relativities, and renewal constraints.
- **lossmodels** — loss-distribution modeling: severity and frequency fitting,
  and aggregate loss.
- **extremeloss** — the tail: peaks-over-threshold / GPD estimation and
  large-claim loading.
- **risksim** — portfolio Monte Carlo and risk measures.

## Dependencies

:::{mermaid}
flowchart TD
    AP["actuarialpy"]
    RM["ratingmodels"]
    LM["lossmodels"]
    EL["extremeloss"]
    RS["risksim"]
    AP -->|credibility, trend, TVM| RM
    AP -.-> LM
    AP -.-> EL
    AP -.-> RS
:::

`actuarialpy` holds the cross-cutting primitives so each downstream package can
stay small. The strongest link is `ratingmodels`, which delegates its
credibility to `actuarialpy` rather than carrying its own. Dependencies stay
light throughout — numpy and pandas, no scipy.

## Conventions

Every package works on plain numpy arrays and pandas Series/DataFrames. There is
no framework to buy into: functions take and return the data structures you
already have, and the classes (`Experience`, `ManualRate`, `RateIndication`, …)
are thin, inspectable wrappers over those functions.
