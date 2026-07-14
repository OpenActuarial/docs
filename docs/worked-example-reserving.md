# Example 11: the reserve, with a distribution

A ten-year paid triangle, one reserve number every actuary reports, and the
question that number cannot answer on its own — *how wrong could it be?* This
page carries the Taylor–Ashe triangle from the chain-ladder point estimate to
the full predictive distribution of the unpaid claims, checks the model has the
right to run, reconciles the two error models, and turns the reserve into
capital in `risksim`. Development and the deterministic methods come from
`actuarialpy` (re-exported through `reservingmodels`); the distribution and
diagnostics are `reservingmodels`; the capital is `risksim`. Every number on
this page is the output of this exact fixed-seed run, pinned by a regression
test in the `reservingmodels` suite.

## The triangle, and the number everyone reports

```python
import reservingmodels as rv

triangle = rv.datasets.taylor_ashe()
cl = rv.ChainLadder.fit(triangle)
cl.mack_standard_errors(triangle).loc["Total"]
```

| reserve | Mack SE | CV |
|---|---|---|
| **18,680,856** | 2,447,095 | 13.1% |

The chain ladder develops the triangle to an 18.7m reserve; Mack (1993) puts a
distribution-free standard error on it without simulating anything. That is
already more than a point estimate — but a single number and its SD do not tell
you the shape of the tail, and the tail is where a reserve fails.

## The whole distribution, not just its width

```python
boot = rv.BootstrapODP.fit(triangle)
dist = boot.reserve_distribution(size=100_000, rng=42)

boot.dispersion        # 52,601
dist.point_reserve     # 18,680,856  — reproduces the chain ladder exactly
dist.mean()            # 18,909,342  — the bootstrap mean, +1.2% (ratio bias)
dist.prediction_error()  # 2,996,849
```

The bootstrap fits the over-dispersed Poisson whose mean surface *is* the chain
ladder, so `point_reserve` lands on 18,680,856 to the dollar; the estimated
dispersion $\phi = 52{,}601$ matches the published fit. Report the point
estimate, not the bootstrap mean — the 1.2% gap is the known upward bias of a
product of ratio estimators, not signal. What the bootstrap adds is the
quantiles:

```python
for q in (0.50, 0.75, 0.95, 0.99, 0.995):
    dist.quantile(q)
dist.tvar(0.99)
```

| quantile | reserve |
|---|---|
| 50% (median) | 18,713,157 |
| 75% | 20,770,994 |
| 95% | 24,138,798 |
| 99% | 26,886,153 |
| 99.5% | 27,949,893 |
| **TVaR 99%** | **28,458,966** |

The 99th percentile sits 8.2m — a third — above the booked reserve, and TVaR
carries the average of the worst 1%. A 13% CV on the point estimate *sounds*
mild; the 99.5% quantile is what a capital calculation actually consumes.

## Per-origin, where the risk actually sits

```python
dist.to_frame()
```

| origin | reserve | se | q95 | q99 |
|---|---|---|---|---|
| … | | | | |
| 7 | 2,194,440 | 496,466 | 3,063,438 | 3,685,963 |
| 8 | 3,952,518 | 795,231 | 5,343,556 | 6,297,848 |
| 9 | 4,322,826 | 1,058,224 | 6,182,766 | 7,605,661 |
| 10 | 4,708,405 | 2,035,330 | 8,239,562 | 11,659,798 |
| **Total** | **18,909,342** | **2,996,849** | **24,138,798** | **27,949,893** |

The uncertainty is not spread evenly. The youngest origin (10) has the second
*largest* reserve but by far the largest relative error — its q99 is nearly 2.5×
its mean — because it is developed off a single observation and the bootstrap
refits the whole pattern each replicate. The total SE (2,996,849) is far below
the sum of the origin SEs: the origins are estimated through one shared
development pattern, so their errors are correlated, and the bootstrap captures
that automatically.

## Is the bootstrap even entitled to run?

```python
rv.residual_summary(triangle)
rv.calendar_year_effects(triangle)
```

| n | mean | std | min | max |
|---|---|---|---|---|
| 55 | 0.60 | 187.3 | −403.8 | 533.2 |

The 55 Pearson residuals are centred near zero, and their spread sits in the
neighbourhood of $\sqrt{\phi}\approx 229$ — the ODP variance assumption is
credible. `calendar_year_effects` shows no monotone drift across diagonals: the
largest-magnitude diagonal means fall on the one-, two-, and three-cell
diagonals, where a single residual dominates, not a systematic
calendar-year (inflation) trend that would break the single-pattern assumption.
When that check fails, the bootstrap's tail is not trustworthy no matter how
tidy the quantiles look — which is the point of running it.

## Mack vs the bootstrap

```python
mack = cl.mack_standard_errors(triangle).loc["Total"]
proc = (boot.dispersion * boot.point_reserve) ** 0.5     # process SD
```

| method | reserve | SE | CV |
|---|---|---|---|
| chain ladder / Mack | 18,680,856 | 2,447,095 | 13.1% |
| ODP bootstrap | 18,909,342 | 2,996,849 | 15.9% |

The bootstrap SE runs 22% above Mack's, and that is a feature, not a
discrepancy: Mack assumes $\mathrm{Var}(C_{i,k+1}\mid C_{i,k})\propto C_{i,k}$,
the ODP assumes $\mathrm{Var}\propto$ mean, and the two answer the same question
under different variance laws. The bootstrap SE decomposes cleanly — estimation
error 2,828,156 and process error $\sqrt{\phi\cdot R}=991{,}281$ combine as
$\sqrt{2{,}828{,}156^2 + 991{,}281^2} = 2{,}996{,}849$ — so nothing is
double-counted; the width is exactly estimation risk plus process risk. Having
both numbers is the honest position: they bracket the reserve risk under two
defensible models.

## The reserve as capital

A fitted bootstrap is a `risksim` component — one `.sample` draw is one
simulated unpaid total — so the reserve joins a capital model with no
dependency between the packages:

```python
import risksim as rs

port = rs.Portfolio([rs.PortfolioItem("reserve_risk", boot)])
sim = port.simulate(100_000, rng=7)
rs.metrics.tvar(sim.gross_losses, 0.99)      # 28,318,860
```

| booked reserve | TVaR(99%) | capital margin |
|---|---|---|
| 18,680,856 | 28,318,860 | **9,638,004** |

That last row is the whole point of the exercise stated in currency: you book
18.7m, but holding to a 99% tail-value standard needs roughly 9.6m more. The
portfolio TVaR reproduces the standalone distribution's tail because the seam is
transparent — `risksim` simply consumed the reserve model — and from here a
second reserving segment aggregates in with a rank correlation exactly as
[Example 9: two lines, one tail](worked-example-dependence.md) does it. The
reserve stops being a number and becomes a distribution you can hold capital
against.
