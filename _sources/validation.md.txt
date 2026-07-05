# Validation

Every claim below is enforced by a test in a package's suite — this page
is the map, with the source of truth and the file that pins it. It exists
because "the tests pass" is invisible from outside; this is what they
pass *against*. Two known divergences are stated at the end, because a
validation record that only reports agreement is advertising.

## Published literature

The chain ladder with Mack standard errors reproduces the numbers printed
in Mack (1993) on the Taylor & Ashe dataset: total reserve **18,680,856**
(to 1e-6) and total standard error **2,447,095** (to 0.5%), total CV
13.1% (`actuarialpy/tests/test_mack.py`). The same file transcribes
Mack's Theorem 3/4 recursion independently and demands agreement to
1e-10, and derives a complete 3×3 triangle by hand (σ² = 2/3 exactly,
mse(o2) = 6016/9 exactly).

The on-level parallelogram reproduces the classic textbook case — one
+10% change mid-year, annual policies, calendar-year period — as
1.1/1.0125 to machine precision (`ratingmodels/tests/test_onlevel.py`),
and the closed-form geometry is pinned against brute-force 20,001-point
numerical integration over random rate histories.

Return-level confidence intervals implement Coles (2001) §4.3.3 (GPD,
including the binomial exceedance-rate term) and §3.3.3 (GEV), with the
point estimates pinned to invert the fitted tail exactly
(`extremeloss/tests/evt/`).

## Independent libraries

**statsmodels.** GLM estimation is delegated to statsmodels, and the
adapter contract is tested by fitting statsmodels *independently* on the
same design and demanding identical coefficients and standard errors;
`predict_interval` matches `get_prediction` to 1e-6
(`ratingmodels/tests/test_statsmodels_crosscheck.py`).

**chainladder-python.** On the shared canonical dataset (GenIns ==
Taylor & Ashe): development factors and ultimates agree to machine
precision; the total Mack standard error agrees to ~0.2%, with the
residual traced to a documented methodological choice (see Known
divergences)
(`actuarialpy/tests/test_chainladder_equivalence.py`).

**SciPy.** `genpareto`/`genextreme` are the estimation engines for the
tail fits, and the observed-information covariances are checked against
the GPD's known Fisher-information asymptotics
(`avar(ξ) = (1+ξ)²/n` and companions).

## Closed forms and hand derivations

Where a closed form exists, the numerical machinery must reproduce it:
lognormal parameter standard errors σ/√n and σ/√(2n) at 1e-3 (the
observed information is exact there); the exponential rate's se = r/√n
(the regression test for a finite-difference step-scaling bug the
closed-form check caught); the memoryless mean excess; the GPD's
closed-form mean excess; the limited-expected-value identity
`e(d)·S(d) + LEV(d) = E[X]` across four severity families; and the
exponential loss-elimination-ratio delta-method standard error against
its analytic derivative at 1e-5.

## Empirical coverage of confidence intervals

Every interval shipped is validated the gold-standard way — simulate
from known truth, count containment — with the measured numbers stated
rather than hidden behind wide acceptance bands:

| Interval | Nominal | Measured | Where |
|---|---|---|---|
| GLM `predict_interval` | 95% | ≈ nominal | `ratingmodels/tests/test_interval_coverage.py` |
| `fit_uncertainty` parameter CIs | 95% | ≈ nominal | `lossmodels/tests/test_uncertainty_and_comparison.py` |
| GPD return level (Wald) | 95% | **≈ 91–92%** | `extremeloss/tests/evt/test_interval_coverage.py` |
| GEV return level (Wald) | 95% | ≈ nominal band | `extremeloss/tests/evt/test_gev_uncertainty.py` |
| Simulation mean / quantile CIs | 95% | ≈ nominal | `risksim/tests/test_uncertainty.py` |
| Mack prediction errors (10×5 trapezoid) | z ~ N(0,1) | mean 0.04, sd 1.08, 93.9% in ±1.96 | `actuarialpy/tests/test_mack.py` |

The GPD line is the honest one: symmetric Wald intervals on a
right-skewed return-level sampling distribution run modestly below
nominal at moderate exceedance counts; profile likelihood is the known
better tool where the last percent matters, and the test documents this
rather than widening its bands to hide it.

## Cross-package conformance

The pooling seam (`sf` + `mean_excess`) is cross-validated against fully
independent machinery — `lossmodels.Layer(d, ∞).mean()` computes
`E[(X−d)+]` by a different code path and must agree to 1e-6 — and
against raw data: an `EmpiricalSeverity` charge must equal the plain
sample mean of `(x − d)+` times frequency exactly. Every worked example
on this site pins its printed numbers with a regression test in the
hosting package's suite.

## Known divergences

**Final-period σ² in the Mack chain ladder.** chainladder-python's
default extrapolates by log-linear regression; this suite uses Mack's
min-rule from the 1993 paper. The totals differ by ~0.2% on Taylor &
Ashe, and this suite's figure is the one the paper prints. Neither is
wrong; the choice is documented in both places.

**GPD return-level Wald coverage.** Measured ≈ 91–92% at nominal 95%
with ~400 exceedances, as stated above.
