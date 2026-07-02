# OpenActuarial

OpenActuarial is a dependency-light Python ecosystem for general actuarial workflows: experience analysis, rating and pricing models, loss modeling, tail estimation, simulation, and portfolio capital. The packages are organized around a shared core, while each library installs and runs independently.

## The ecosystem

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} actuarialpy
:link: actuarialpy
:link-type: doc

**The core.** Experience analysis on a tidy table, plus the shared
primitives — credibility, trend, completion, seasonality, financial
mathematics, exposure, and underwriting margin — that `ratingmodels`
builds on directly.
:::

:::{grid-item-card} ratingmodels
:link: ratingmodels
:link-type: doc

**Pricing.** Manual and experience rate build-up, credibility blending,
rate indication and decomposition, GLM relativities and model evaluation,
renewal constraints, and pricing scenarios with margin targets.
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

Left to right, the packages trace one analysis — experience, pricing, loss, tail,
and capital:

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

The arrows are the analytical sequence, not install requirements. `actuarialpy`
is the shared core — credibility, trend, financial math, and exposure live there
once — and `ratingmodels` builds directly on it. `lossmodels`, `extremeloss`, and
`risksim` install independently (`extremeloss` can optionally integrate
`lossmodels` for severity splicing). Dependencies stay light: numpy everywhere, pandas
in the core and `ratingmodels`, scipy where the loss and tail work needs it.

## A cross-package example

Blend an experience rate with a manual rate and read the indicated change:

```python
import actuarialpy as ap
import ratingmodels as rm

# credibility from exposure (lives in actuarialpy; ratingmodels delegates to it)
z = ap.limited_fluctuation_z(exposure=96_000, full_credibility_standard=120_000)

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

## Install

```bash
pip install actuarialpy ratingmodels lossmodels extremeloss risksim
```

Each package installs independently; `ratingmodels` pulls in `actuarialpy` as a
dependency.

:::{toctree}
:hidden:
:maxdepth: 1

overview
conventions
actuarialpy
ratingmodels
lossmodels
extremeloss
risksim
:::