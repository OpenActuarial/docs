# OpenActuarial

A small ecosystem of dependency-light Python libraries for the group health
pricing and risk workflow — experience analysis, rate building, loss modeling,
tail estimation, and portfolio capital — built on one shared core. numpy and
pandas only.

## The ecosystem

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} actuarialpy
:link: actuarialpy
:link-type: doc

**The core.** Experience analysis on a tidy table, plus the shared
primitives — credibility, trend, completion, seasonality, financial
mathematics, and exposure — that everything else builds on.
:::

:::{grid-item-card} ratingmodels
:link: ratingmodels
:link-type: doc

**Pricing.** Manual and experience rate build-up, credibility blending,
rate indication and decomposition, GLM relativities, and renewal constraints.
:::

:::{grid-item-card} lossmodels
:link: lossmodels
:link-type: doc

**Loss modeling.** Severity and frequency fitting, and aggregate loss
distributions.
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

## How they fit together

:::{mermaid}
flowchart LR
    AP["actuarialpy<br/>experience"] --> RM["ratingmodels<br/>pricing"] --> LM["lossmodels<br/>loss"] --> EL["extremeloss<br/>tail"] --> RS["risksim<br/>capital"]
:::

`actuarialpy` is the foundation: cross-cutting primitives — credibility, trend,
financial mathematics, exposure — live there once, and the other packages depend
on it rather than re-implementing them. Light dependencies throughout (numpy /
pandas).

## A cross-package example

Blend an experience rate with a manual rate and read the indicated change:

```python
import actuarialpy as ap
import ratingmodels as rm

# credibility from exposure (lives in actuarialpy; ratingmodels delegates to it)
z = ap.limited_fluctuation_z(exposure=96_000, full_credibility_standard=120_000)

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
actuarialpy
ratingmodels
lossmodels
extremeloss
risksim
:::
