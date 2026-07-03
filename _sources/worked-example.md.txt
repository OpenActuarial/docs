# A worked example: claims to capital

One block of business carried across the whole ecosystem: fit a severity body
(`lossmodels`), diagnose and fit the tail (`extremeloss`), splice, convolve
with frequency, reinsure and measure the capital (`risksim`), price it
(`ratingmodels`), and report the result (`actuarialpy`). Every number on this
page is the output of this exact fixed-seed run. The page is pinned by a
regression test in the `extremeloss` suite, so these numbers cannot silently
drift.

```python
import numpy as np
import lossmodels as lm
import extremeloss as xl
import risksim as rs
import ratingmodels as rm
import actuarialpy as ap

rng = np.random.default_rng(20260702)

# stand-in for a claims extract: 2,500 ground-up severities
losses = lm.Burr(2.2, 20_000, 1.6).sample(2500, rng=rng)
```

## Fit the body

Complete-data maximum likelihood is one call (fitting under deductibles and
limits is covered on the [lossmodels page](lossmodels.md)):

```python
body = lm.fit_lognormal(losses)
# -> Lognormal(mu=9.204, sigma=0.945)
```

## Diagnose and fit the tail

Scan candidate thresholds before committing to one:

```python
scan = xl.threshold_diagnostic_table(
    losses, np.quantile(losses, [0.90, 0.925, 0.95, 0.975])
)
# threshold    29,289   32,666   38,886   48,917
# n_exc           250      188      125       63
# xi            0.242    0.206    0.217   -0.041
```

The shape estimate is stable around $\hat\xi \approx 0.21$–$0.24$ through the
95th percentile and degenerates at the 97.5th, where only 63 exceedances
remain — so take the threshold at the 95th:

```python
u = float(np.quantile(losses, 0.95))
fit = xl.fit_pot(losses, threshold=u)
# -> GPDFit: threshold=38,886  xi=0.217  beta=15,281  (125 exceedances, 5.0%)

xl.return_level(200, fit)
# -> 84,555   (the 1-in-200 claim; identical to gpd_var(0.995, ...))
```

## Splice and convolve

The fitted tail reattaches to the lognormal body as a single
`lossmodels.SplicedSeverity` (mass-matching at the threshold — see
[Conventions](conventions.md#tail-fitting-and-splicing)), and eight years of
claim counts give the frequency:

```python
sev = xl.splice_gpd_tail(body, fit)
# -> SplicedSeverity, mean 13,937

counts = np.array([242, 166, 153, 164, 195, 163, 162, 176])
freq = lm.fit_negbinomial(counts)
# -> NegativeBinomial(r=65.3, p=0.269), mean ~178 claims per year

crm = lm.CollectiveRiskModel(freq, sev)
crm.mean()
# -> 2,475,636
```

## Reinsure and measure the capital

The collective risk model drops straight into a `risksim` portfolio — anything
with a `.sample` method does. An aggregate stop-loss of 1.5M excess of 3.2M
(`limit` is the layer *width*, per the
[coverage semantics](conventions.md#coverage-semantics)) reshapes the tail:

```python
port = rs.Portfolio([rs.PortfolioItem("commercial_block", crm)])
treaty = rs.AggregateLayer(attachment=3_200_000, limit=1_500_000,
                           name="agg_stop_loss")
res = port.simulate(100_000, contract=treaty, rng=7)

rs.metrics.var(res.gross_losses, 0.99)       # -> 3,503,943
rs.metrics.tvar(res.gross_losses, 0.99)      # -> 3,683,961
res.ceded_losses.mean()                      # -> 9,168
rs.metrics.tvar(res.retained_losses, 0.99)   # -> 3,200,000
```

The retained TVaR₉₉ sits exactly at the attachment: gross TVaR₉₉ is below the
layer's exhaustion point (4.7M), so the treaty pins the 1-in-100 retained tail
at 3.2M. The `rng` argument threads one generator through the simulation —
rerunning with `rng=7` reproduces every array bit for bit.

## Price it

```python
exposure = 12_500.0
loss_cost = crm.mean() / exposure            # -> 198.05 per unit-year

ret = rm.RetentionLoad(fixed_expense=22.0, variable_expense_ratio=0.09,
                       profit_margin=0.03, lae_ratio=0.05)
pe = rm.PricingEvaluation(loss_cost=loss_cost, current_rate=255.0,
                          retention=ret, exposure=exposure, persistency=0.90)

pe.premium_for_margin(0.03)   # -> 261.31
pe.at(0.0).margin_rate        # -> 2.10   (dollars per unit — a 0.8% margin at 255)
```

The capital view informs the margin: a 6% cost of capital on the retained
1-in-100 requirement (TVaR₉₉ less the mean, 730,705) is 3.51 per unit-year,
comfortably inside the 7.84 per unit that a 3% margin on 261.31 provides.

## Report it

```python
uw = ap.UnderwritingSummary.from_per_exposure(
    revenue_per_exposure={"premium": 261.31},
    loss_per_exposure={"expected_losses": 198.05 * 1.05},   # incl. LAE
    expense_per_exposure=0.09 * 261.31 + 22.0,
    exposure=exposure,
)
uw.loss_ratio         # -> 0.7958
uw.expense_ratio      # -> 0.1742
uw.combined_ratio     # -> 0.9700
uw.gain_per_exposure  # -> 7.84
```

The identities close the loop: the combined ratio is $1 - 0.03$ — exactly one
minus the priced margin, because the denominators line up — and the gain per
unit equals margin × premium. That reconciliation is not a coincidence; it is
the contract pinned on the [conventions page](conventions.md#margin-and-denominators).
