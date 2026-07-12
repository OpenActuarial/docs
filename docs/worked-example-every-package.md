# Example 11: every package, one object

The whole ecosystem off a single construction call. Three source extracts —
membership, a claims listing, billing — become an `ExperienceSet`, and the
same `book` object then feeds studies, trend, projection, rating, severity
and frequency fitting, and tail fitting. Every number below is real output
from executing this page's code against the released packages (seeded, so
it reproduces exactly).

## Sources to workbook

```python
import actuarialpy as ap

book = ap.ExperienceSet.from_tables(
    membership,                          # one row per member-month
    grain=["member_id", "month"], exposure="member_months",
    sources=[
        ap.Source(claims, expense="paid_amount", wide_by="claim_type",
                  date="incurred_date", name="claims"),
        ap.Source(billing, revenue="premium"),
    ],
    date="month", period="M", dimensions="group_id",
    valuation_date="2026-06-30",
)
book.member_names        # ('tab', 'claims')
book.reconcile()         # ties each listing's totals to the tab
```

```text
members: ('tab', 'claims') | tab rows: 4320
listing     measure  ties
 claims paid_amount  True
```

Two grain-honest members from one call: `book.tab` (member-month worksheet,
claim types pivoted to expense columns, grain verified unique) and
`book["claims"]` (the untouched listing at claim grain). `reconcile()`
proves nothing was dropped on the way in.

## experiencestudies: the block's performance

Study functions accept the set and route to the tab.

```python
import experiencestudies as es

es.summary(book, "group_id")
```

```text
group_id  total_expense  total_revenue  loss_ratio
 1102052     1349904.36      1267200.0        1.07
 2203987     1041596.70       806400.0        1.29
```

Both groups run hot — the block needs a rate action, which the rest of the
page quantifies.

## actuarialpy: trend on the retained layer

Trend belongs on retained experience, so filter the shock layer out of the
listing first — `filter` is just a transformation — then aggregate and fit.

```python
pooled = book["claims"].filter(query="paid_amount < 18_000")
monthly = (pooled.data
           .groupby(pd.Grouper(key="incurred_date", freq="MS"))
           ["paid_amount"].sum().reset_index())
fit = ap.fit_trend(ap.Experience(monthly, expense="paid_amount",
                                 date="incurred_date"))
```

```text
AP trend (retained layer): +2.6%  R2=0.01
```

The generator's true trend is +7%; twelve monthly points of heavy-tailed
claims recover +2.6% with an R² that says exactly how little the fit should
be trusted — which is the honest reading a rate filing needs, not a defect
of the tooling. Real work uses 24–36 months.

## projectionmodels: the claim projection

`project(book, ...)` routes to the tab and melts the recorded claim-type
pivot into the projection dimension by itself; assumptions stay explicit
arguments.

```python
import projectionmodels as pm

proj = pm.project(
    book, exposure=future_membership,
    horizon=pm.ProjectionHorizon("2027-01-01", periods=6),
    trend=fit.annual_trend, credibility=0.85,
    complement=pm.Assumption("manual", manual_rates,
                             lookup=["claim_type"], value_col="manual"),
).project()
proj.summarize(by=["group_id"])
```

```text
group_id   pmpm
 1102052 501.87
 2203987 597.37
```

## ratingmodels: the renewal worksheet

One row per group off the same object; the multi-expense tab needs the
`expense=` selection, pooling takes the claimant and the point.

```python
import ratingmodels as rm

rm.experience_rate(book, by="group_id",
                   expense=["inpatient", "outpatient"],
                   pooling_point=18_000.0, claimant_col="member_id",
                   trend_annual=fit.annual_trend, trend_years=1.5)
```

```text
group_id  pooled_excess  loss_cost   rate
 1102052      151913.43     495.23 582.63
 2203987      206456.99     542.51 638.25
```

Indicated rates of 583/638 against 480 premium — the quantified version of
the loss ratios in the study section.

## lossmodels: severity and frequency from the listing

The fitting integrations route the set to the claims listing (claim grain);
handing them the tab is refused, because member-month sums are a compound
distribution, not severity.

```python
from lossmodels.integrations.actuarialpy import (
    fit_frequency_from_experience, fit_severity_from_experience)

sev = fit_severity_from_experience(book, by="claim_type")
freq = fit_frequency_from_experience(book, freq="M")
```

```text
LM severity: {'inpatient': 'burr', 'outpatient': 'burr'} | frequency: poisson
```

## extremeloss: the tail above the pooling point

Extracting excesses is structural; choosing the threshold is judgment, so
it stays an argument.

```python
from extremeloss.integrations.actuarialpy import fit_gpd_from_experience

tail = fit_gpd_from_experience(book, threshold=18_000.0)
```

```text
EL tail: GPD xi=-0.04 (30 exceedances over 18k)
```

## risksim and the model boundary

The fitted models — not the experience — feed aggregate simulation. That is
the deliberate boundary: `risksim` and the collective-risk layer consume
frequency/severity models, so they never touch `Experience` at all.

```python
import lossmodels as lm

crm = lm.CollectiveRiskModel(frequency=freq["best_model"],
                             severity=sev["outpatient"]["best_model"])
crm.sample(10_000, rng=rng).mean()
```

```text
CRM aggregate mean (outpatient/mo): 148,116
```

## The shape of the whole thing

Sources → bindings → consumers. One construction call builds every
grain-honest worksheet; studies, projection, and rating read the tab;
severity and tail fitting read the listing; simulation reads the fitted
models. Entering at a coarser grain (an aggregated extract bound directly
as an `Experience`) keeps everything at or above that grain and loses what
is below it — the tab can never yield a severity distribution, and the
guards say so out loud rather than fitting garbage. Bind the finest grain
you have, declare it, and derive everything coarser.
