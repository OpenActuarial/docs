# projectionmodels

Focused actuarial projections of claims, premium, and expenses on supplied
exposure. The package is intentionally organized around concrete workflows —
most users should not need to construct a calculation graph or define a
custom state engine. It depends on [actuarialpy](actuarialpy.md) for its
completion, trend, seasonality, and credibility estimation.

The package root contains the workflow objects most actuaries need:

| Object | Role |
| --- | --- |
| `ClaimExperience` | Prepare a base claim rate from experience |
| `ClaimProjection` | Project claim rates and claims by claim type |
| `PremiumProjection` | Roll premium forward, including renewal rate actions |
| `RenewalRateActions` | Supply effective-dated rate actions |
| `ExpenseProjection` | Project per-exposure, fixed, premium-based, and claim-based expenses |
| `ProjectionHorizon` | Define monthly, quarterly, or annual projection periods |
| `ProjectionDates` | Define entry, exit, renewal, and experience date columns |
| `DateCohort` | Split records into existing/new or other date cohorts |
| `Adjustment` / `Scenario` | Run sensitivities and alternative assumptions |
| `ProjectionResults` | Summarize without averaging ratios or duplicating exposure |

Lower-level modeling objects are available from `projectionmodels.advanced`,
but they are not part of the primary workflow.

## Quickstart: premium at renewal

```python
import pandas as pd
import projectionmodels as pm

premium_data = pd.DataFrame({
    "group_id": ["A", "B"],
    "renewal_date": pd.to_datetime(["2027-03-01", "2027-07-01"]),
    "current_premium_rate": [100.0, 100.0],
    "rate_action": [0.10, 0.20],
})

periods = pd.period_range("2027-01", periods=12, freq="M").astype(str)
exposure = pd.DataFrame(
    [{"group_id": g, "projection_period": p, "member_months": 1_000.0}
     for g in ("A", "B") for p in periods]
)

results = pm.PremiumProjection(
    premium_data=premium_data,
    projection_keys=["group_id"],
    exposure=exposure,
    exposure_col="member_months",
    horizon=pm.ProjectionHorizon("2027-01-01", periods=12),
    recurring_rate_action_col="rate_action",
).project()
```

Group A remains at \$100 through February, increases to \$110 at its March
renewal, and carries that rate forward; group B increases to \$120 in July.
For different actions at different renewals, provide an effective-dated
`RenewalRateActions` table instead of a recurring action column.

## Claims by claim type

`ClaimExperience` prepares a base rate from history, and
`ClaimProjection.from_experience` carries it through the projection:

```python
experience = pm.ClaimExperience(
    hist,
    projection_keys=["group_id"],
    claim_type_col="claim_type",
    date_col="incurred_month",
    claims_col="reported_claims",
    exposure_col="member_months",
    valuation_date="2026-12-31",
)

projection = pm.ClaimProjection.from_experience(
    experience,
    exposure=exposure,
    exposure_col="member_months",
    horizon=pm.ProjectionHorizon("2027-01-01", periods=12),
    trend=pm.TrendAssumption.from_values("claim_trend", 0.06),
    # optionally: completion=, seasonality=, credibility=, complement=
)

results = projection.project()
results.to_frame()      # per key × claim type × period detail
```

Trend, seasonality, completion, and credibility may be supplied directly as
assumption tables (`TrendAssumption.from_values` and friends) or estimated
from history (below).

### Cost levels and pipeline order

The claim workflow evaluates, in order: complete → deseasonalize → trend the
experience rate to the blend basis → credibility blend → trend from the basis
to each projection period → reseasonalize → add `rate_loads` → multiply by
exposure. Exposure is whatever unit the book uses — member-months,
policy-months, car-years — named with `exposure_col`.

The complement is used **as stated**. By default the blend basis is the
prospective midpoint of the horizon (`complement_basis="prospective"`), the
level at which manual and book rates are conventionally quoted — so a
zero-credibility projection reproduces the complement rather than a trended
copy of it. Set `complement_basis="experience"` if your complement is quoted
at experience-period cost level, or pass an explicit as-of date. Because the
month arithmetic is exactly additive, results at full credibility are
identical under every basis.

`rate_loads` (for example a pooling charge) are added to the projected rate
as stated: flat across periods, after seasonality, outside the blend.

## Estimating assumptions with actuarialpy

Estimation is explicit and separate from projection execution. The
`projectionmodels.integrations.actuarialpy` adapters estimate each assumption
with the corresponding core primitive (`completion_factors`, `fit_trend`,
`seasonality_factors`, `limited_fluctuation_z`) and return assumption objects
that retain indicated values and diagnostics:

```python
from projectionmodels.integrations.actuarialpy import (
    estimate_completion,
    estimate_credibility,
    estimate_seasonality,
    estimate_trend,
)

trend = estimate_trend(
    "claim_trend",
    deseasonalized_history,
    by=["claim_type"],
    date_col="incurred_month",
    value_col="deseasonalized_claims",
    exposure_col="member_months",
)
```

An actuary can replace an indication while preserving the audit trail — the
assumption keeps both the estimate and the selection.

## Results

`ProjectionResults` holds the per-period detail and summarizes it correctly:
exposure-weighted rates, summed amounts — never a naive average of ratios,
never exposure counted twice across claim types:

```python
results.to_frame()                       # full detail
results.summarize(by="calendar_quarter") # weighted rates, summed exposure and amounts
```

## API reference

```{eval-rst}
.. automodule:: projectionmodels
   :members:
```
