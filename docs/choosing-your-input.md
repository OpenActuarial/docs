# Choosing your input

Every package here accepts plain numpy and pandas objects, and several also
accept the canonical [`Experience` and `ExperienceSet`](data-model.md)
containers. They are not competing frameworks — they are different entry
points for different jobs. This page is the quick guide to which one to
reach for.

## The short version

> **pandas** prepares and extends the data · **Experience** binds one
> actuarial view · **ExperienceSet** coordinates related views · the
> ecosystem's functions hand back ordinary DataFrames.

Use pandas to get the data ready. Use `Experience` or `ExperienceSet` to run
a repeatable analysis across packages. Drop back to a DataFrame for custom or
low-level work whenever you want. You never have to wrap an array to call a
function.

## Decision guide

| Your starting point | Reach for |
| --- | --- |
| A single ratio, array, or Series calculation | a scalar / numpy / pandas **primitive** — `ap.loss_ratio`, `ap.trend_factor`, `ap.limited_fluctuation_z` |
| One prepared table at a known grain, feeding one analysis | **`ap.Experience`** — bind the roles once |
| Several source tables, or one grain feeding several packages | **`ap.ExperienceSet.from_tables`** — one construction call, routed per consumer |
| Company ETL, allocation, assumption tables, future exposure, a custom calc | a plain **pandas DataFrame** — then bind it, or reach into `.data` |

The rule of thumb: **the moment the same data will feed more than one
calculation or package, bind it.** Binding the roles, grain, dates, and
valuation context once is what lets the same block flow through a study, a
projection, and a rate without re-declaring columns — and it is where the
grain guards and reconciliation checks live.

## Three tiers of interface

Where a package offers more than one interface, the docs mark them so you can
tell the recommended path from the escape hatch:

- **Workflow API** — takes an `Experience`/`ExperienceSet`, reads the bound
  roles. The recommended path for multi-step analysis:
  `es.summary(exp)`, `pm.project(exp, ...)`, `rm.experience_rate(exp)`.
- **Tabular API** — takes an explicit-column DataFrame. The low-level escape
  hatch for one-off or custom work:
  `es.summarize_experience(df, ...)`, `rm.base_rate_from_experience(df, ...)`.
- **Primitive API** — scalars and Series in, same type out:
  `ap.loss_ratio(...)`, `ap.per_exposure(...)`, `rm.blend(...)`.

All three are supported and none is deprecated. The question is only which
fits the task in front of you.

## See it work

The single best illustration is the [ecosystem
tour](worked-example-every-package.md): three source extracts become one
`ExperienceSet`, and that one object then feeds studies, projection, rating,
severity, frequency, and tail fitting — each receiving data at the grain it
needs. The [data model reference](data-model.md) documents the containers in
full.
