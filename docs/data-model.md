# The data model: Experience and ExperienceSet

Most of this ecosystem's functions accept plain numpy arrays and pandas
frames, and for one-off calculations that is the right tool. But a real
analysis reuses the same block of experience across several packages —
a summary here, a trend there, a projection, a rate. Re-declaring which
column is the loss, which is the premium, which is the exposure, and at
what grain, at every call is where mistakes get in.

`Experience` and `ExperienceSet` (both in `actuarialpy`, the shared core)
solve exactly that: **bind the data's actuarial meaning once, then hand the
same object to every package.** This page is the reference for that contract.
It is optional — nothing forces you to adopt it — but for composed workflows
it is the recommended path, and it is what the [worked
examples](worked-example-experience.md) and the [ecosystem
tour](worked-example-every-package.md) are built on.

## Experience: one prepared table, its roles bound

`Experience` wraps a tidy DataFrame and records what its columns *mean* —
the measure roles (`expense`, `revenue`, `exposure`, `count`), the `date`
column, the segmentation `dimensions`, and the snapshot `valuation_date`:

```python
import actuarialpy as ap

exp = ap.Experience(
    panel,
    expense="paid_claims", revenue="premium",
    exposure="member_months", count="claim_count",
    date="incurred_month",
    dimensions=["group_id", "claim_type"],   # reporting cuts / lookups / grain defaults
    exposure_keys=["member_id", "incurred_month"],  # opt-in grain guard
    valuation_date="2026-06-30",
)
```

Three kinds of metadata do three different jobs. **Measure and date roles**
name what the columns are. **`dimensions`** are segmentation columns —
consumers use them as default reporting groupings and assumption-lookup keys;
they say nothing about row grain. **`exposure_keys`** identify one exposure
unit: when bound, construction validates that the frame is unique on them, so
long (service-line-grain) data is rejected at the door instead of silently
overcounting every per-exposure figure. Leave them unbound and no grain
safety is claimed.

The object holds **no actuarial judgment**. Every public method is an
immutable *transformation* that takes caller-supplied assumptions and returns
a new `Experience`, so restatements chain without mutating the source:

```python
work = (
    exp.filter(query="group_id == 1102052")
       .complete(completion_factors)     # develop to ultimate (valuation date from the object)
       .adjust(1.03)                     # a trend / restatement factor
       .deseasonalize(seasonal_factors)
)
```

Everything analytical is a *function that accepts an `Experience`* — a split
enforced by a test in each package (no public method on the class may return
anything else). `es.summary(exp)`, `rm.experience_rate(exp)`,
`pm.project(exp, ...)`, `ap.fit_trend(exp)` all read the bound roles rather
than asking you to name columns again.

## ExperienceSet: several grains, one construction call

Real actuarial data does not live at one grain. Exposure is a membership
table at member-month grain; claims are a transaction listing at claim-line
grain; premium is billed at group-month grain. A severity fit needs the
claim lines; an experience summary needs the aggregated member-month tab.
Forcing all of that into one physical table is where allocation errors hide.

`ExperienceSet` keeps the related representations together and lets each
consumer take the one it needs. **One construction call builds them all:**

```python
import actuarialpy as ap

book = ap.ExperienceSet.from_tables(
    membership,                                  # defines the grain
    grain=["member_id", "month"], exposure="member_months",
    sources=[
        ap.Source(claim_lines, expense="paid_amount",
                  date="incurred_date", name="claims"),
        ap.Source(billing, revenue="billed_premium"),
    ],
    date="month", period="M", dimensions="group_id",
    valuation_date="2026-06-30",
)
```

The result is a bundle of ordinary, materialized, grain-honest `Experience`
members:

```text
book
├── book.tab        aggregated Experience at the declared grain (member-month)
└── book["claims"]  the claim-line listing, kept at its own grain
```

`book.tab` is the worksheet — the aggregated `Experience` at the grain you
declared in `from_tables`. Each **named** `Source` (one given a `name=`)
also becomes a listing member, reachable by `book["claims"]`. What a
member's `.data` shows is exactly what a consumer receives — there is no
hidden state.

```{note}
`book.tab` is renamed to `book.primary` in the 0.47 release (with `tab`
kept as a deprecated alias for one minor version) — inside the workbook
metaphor every named listing is a "tab", so `.primary` states the intended
meaning less ambiguously. On the installed 0.46 line, use `book.tab`.
```

## What `from_tables` does — one fixed, auditable algorithm

Every `Source` is brought to the declared grain by the same rules, so there
is nothing bespoke to audit per table:

- **Finer tables aggregate up.** A claim-line table is grouped and summed to
  the grain — aggregation is structural, so the constructor may do it.
- **Coarser tables are refused.** A table missing a grain column (premium at
  group grain when the grain is member-month) is rejected: *allocation
  downward is judgment*, so you must do it before binding, not the library.
- **Unmatched keys are surfaced, never dropped.** Rows whose keys don't exist
  in the grain table are reported per `unmatched=` (`"warn"` or `"raise"`).
- **Empty cells are structural zeros.** A grain cell with no claims is zero
  claims, not missing data.
- **Pivots are recorded.** A `wide_by` reshape is stored as provenance so it
  can be undone structurally (see below).

This is the reconciliation an actuary otherwise does by hand between the
claims extract and the worksheet — made mechanical and repeatable.

## Reconcile and cohort

`reconcile()` ties every listing's measure totals back to the tab and returns
the check as a frame — a nonzero difference is exactly the surfaced
exclusions (orphan keys that never joined):

```python
book.reconcile()
#  listing     measure    role  source_total  tab_total  difference  ties
#   claims paid_amount expense      291000.0   291000.0         0.0  True
```

`cohort(...)` restricts to a population by filtering the grain table (the
population authority) and **re-deriving every member** from the filtered
sources — propagation by reconstruction, never mutation, so nothing goes
stale:

```python
existing = book.cohort(group_id="1102052")   # tab and every listing re-derived
```

## Which member does each package use?

Consumers accept the whole `book` and route themselves to the right member —
you do not unwrap it by hand:

| Consumer | Reads |
| --- | --- |
| `es.summary`, `es.rolling`, A/E, decomposition | the tab |
| `pm.project` | the tab |
| `rm.experience_rate` | the tab |
| severity fitting (`lossmodels`, `extremeloss`) | the claims listing |
| frequency fitting (`lossmodels`) | the claims listing |
| tail fitting (`extremeloss`) | the claims listing |
| `risksim` | fitted models, not experience data |

```python
import experiencestudies as es
import ratingmodels as rm
from lossmodels.integrations.actuarialpy import fit_severity_from_experience

es.summary(book, "group_id")             # tab   -> grouped experience study
rm.experience_rate(book, by="group_id")  # tab   -> credibility-blended indication
fit_severity_from_experience(book)       # claims listing -> a fitted severity
```

The severity and tail integrations live in each package's
`integrations.actuarialpy` module (imported above), not at the package root,
because `lossmodels` and `extremeloss` are array-level libraries with no hard
dependency on `actuarialpy` — the `Experience` seam is an optional edge.

## Wide claims by type — and one sharp edge

A `Source` can pivot a categorical (claim type, service line) into one column
per category with `wide_by=`, recorded so it can be melted back:

```python
book = ap.ExperienceSet.from_tables(
    membership, grain=["member_id", "month"], exposure="member_months",
    sources=[
        ap.Source(claim_lines, expense="paid_amount", wide_by="claim_type",
                  date="incurred_date", name="claims"),   # -> inpatient, outpatient, rx columns
        ap.Source(billing, revenue="billed_premium"),
    ],
    date="month", period="M", dimensions="group_id",
)
```

This is exactly what a claim projection by type wants. But it means the tab
now carries **several** expense columns. Consumers that need a single loss
column — `rm.experience_rate` is the common one — will raise
(`Multiple expense columns are bound ...`) rather than guess which to blend.
For those, either build the book without `wide_by` (a single `paid_amount`
column), pass the column explicitly, or run the rating off `book.tab.aggregate(...)`
collapsed to one measure. `es.summary` and the severity/tail fits are
unaffected — they sum or read the listing directly.

## What stays in pandas

Adopting the object model is not "everything must be an `Experience`."
DataFrames remain the right tool for SQL extracts, cleaning and mapping,
actuarial judgment such as allocation, assumption tables, future exposure,
model matrices, and any custom calculation. The balanced shape of a workflow:

> **pandas** prepares and extends the data · **Experience** binds one
> actuarial view · **ExperienceSet** coordinates related views ·
> the ecosystem's functions hand back ordinary DataFrames.

See [Choosing your input](choosing-your-input.md) for a quick decision guide,
and the [ecosystem tour](worked-example-every-package.md) for the whole thing
end to end.
