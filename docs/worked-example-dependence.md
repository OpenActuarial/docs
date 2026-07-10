# Example 9: two lines, one tail

A capital view is only as good as two things the point estimate never shows:
the dependence assumption between the lines and the Monte Carlo error in the
numbers. This page runs both through `risksim` — a two-line portfolio built
from `lossmodels` collective risk models, diversification measured and then
stress-tested with Iman–Conover reordering (normal and t scores at the *same*
rank correlation), a two-layer aggregate program priced on the result, and
every headline metric reported with the interval its sampling theory
supports. Every number on this page is the output of this exact fixed-seed
run.

## Two lines

A property book and a smaller, heavier-tailed liability line — anything with
a `.sample` method drops into a portfolio item:

```python
import numpy as np
import lossmodels as lm
import risksim as rs
from risksim import metrics, uncertainty
from risksim.dependence import impose_rank_correlation

prop = lm.CollectiveRiskModel(lm.NegativeBinomial(65.3, 0.269),
                                 lm.Lognormal(9.2, 0.95))
liab = lm.CollectiveRiskModel(lm.Poisson(26.0),
                                   lm.Lognormal(10.2, 1.35))

port = rs.Portfolio([rs.PortfolioItem("property", prop),
                     rs.PortfolioItem("liability", liab)])
res = port.simulate(200_000, rng=7)
M = res.component_losses          # the (n_sims, 2) matrix, columns in
                                  # res.component_names order
```

## The diversification you are claiming

Component draws are independent by default, and the standalone-versus-
combined comparison quantifies what that assumption is worth:

| | mean | VaR₉₉ | TVaR₉₉ | TVaR₉₉.₅ |
|---|---:|---:|---:|---:|
| property | 2,757,874 | 3,953,177 | 4,159,691 | 4,299,128 |
| liability | 1,738,858 | 4,566,745 | 5,809,053 | 6,745,713 |
| **combined, independent** | 4,496,732 | 7,479,457 | 8,697,291 | 9,620,716 |

The standalone TVaR₉₉.₅ sum to 11,044,841 against the combined 9,620,716 —
a **1,424,125 diversification benefit**, about 13% of the standalone
capital. That is the number the dependence assumption owns.

## Impose the dependence

`impose_rank_correlation` reorders the simulated columns to a target rank
correlation without touching any sampler — the marginals are preserved
*exactly*, which is checkable rather than assumed:

```python
corr = np.array([[1.0, 0.5], [0.5, 1.0]])
Mn = impose_rank_correlation(M, corr, rng=11)                      # normal scores
Mt = impose_rank_correlation(M, corr, rng=11, scores="t", df=4)    # t scores

np.allclose(np.sort(M[:, 0]), np.sort(Mn[:, 0]))    # True — same draws, new order
```

Both hit the target (achieved Spearman 0.481 and 0.494), and the means are
identical to the independent run by construction. The tails are not:

| dependence | mean | VaR₉₉ | TVaR₉₉ | TVaR₉₉.₅ | benefit at TVaR₉₉.₅ |
|---|---:|---:|---:|---:|---:|
| independent | 4,496,732 | 7,479,457 | 8,697,291 | 9,620,716 | 1,424,125 |
| ρ = 0.5, normal scores | 4,496,732 | 8,016,642 | 9,331,046 | 10,316,277 | 728,564 |
| ρ = 0.5, t scores, df = 4 | 4,496,732 | 8,003,939 | 9,272,676 | 10,219,875 | 824,966 |

A rank correlation of 0.5 erases **half the diversification benefit** —
seven hundred thousand of capital relief that existed only inside the
independence assumption.

## Same rank correlation, different tail

The two score choices above are calibrated to the *same* ρ, and on every
sum-based metric in that table they are within a whisker of each other. So
does the copula matter? Ask a joint question instead of a sum question —
the probability that *both* lines blow through their own 1-in-100 in the
same year:

```python
qm = metrics.var(M[:, 0], 0.99)
qs = metrics.var(M[:, 1], 0.99)
for X in (M, Mn, Mt):
    print(((X[:, 0] > qm) & (X[:, 1] > qs)).mean())
```

| dependence | joint exceedances (of 200,000) | P(both lines exceed own VaR₉₉) |
|---|---:|---:|
| independent | 12 | 0.00006 |
| ρ = 0.5, normal scores | 275 | 0.001375 |
| ρ = 0.5, t scores, df = 4 | **397** | **0.001985** |

Normal scores raise the joint-exceedance rate 23-fold over independence; t
scores raise it another 44% *at the identical rank correlation*, because
normal scores leave joint extremes asymptotically independent while the t
copula clusters them. And yet the sum's TVaR barely moved between the two.
Both facts are the lesson: a capital metric on the sum can be nearly blind
to tail dependence that a joint trigger — a second-event cover, a
combined-ratio covenant, an enterprise-wide stress test — feels at full strength.
Choose `scores=` by the question being asked, which is exactly why the
switch exists.

## Reinsure it

A two-layer aggregate program prices the dependence decision in treaty
currency. `limit` is the layer width per the
[coverage semantics](conventions.md#coverage-semantics), and `share` scales
the second layer's participation:

```python
program = rs.ContractProgram([
    rs.AggregateLayer(attachment=7_000_000, limit=3_000_000, name="first"),
    rs.AggregateLayer(attachment=10_000_000, limit=5_000_000, share=0.8,
                      name="second"),
])
ceded, retained = rs.apply_contract(Mt.sum(axis=1), program)
```

| world | ceded mean (pure premium) | 95% CI | retained TVaR₉₉.₅ |
|---|---:|---:|---:|
| independent | 17,859 | [16,951, 18,766] | 7,145,769 |
| ρ = 0.5, normal | 29,849 | [28,694, 31,003] | 7,215,111 |
| ρ = 0.5, t, df = 4 | 29,475 | [28,343, 30,608] | 7,186,535 |

Moving from independence to ρ = 0.5 raises the program's pure premium
**65%** — the reinsurer is selling back the diversification the cedent no
longer has. Between the two copulas the intervals overlap: this aggregate
trigger, like the sum's TVaR, cannot tell them apart. The dependence
*level* is priced; the tail *shape* at that level needs a joint trigger to
matter.

## How much of this is signal

Every number above came from 200,000 simulations, and
`risksim.uncertainty` reports what that is worth — normal theory for the
mean, distribution-free order statistics for VaR, percentile bootstrap for
TVaR:

```python
uncertainty.summary_with_error(retained, quantiles=(0.99, 0.995), rng=7)
```

| metric | estimate | se | 95% CI |
|---|---:|---:|---:|
| mean | 4,467,257 | 2,312 | [4,462,726, 4,471,789] |
| VaR₉₉ | 7,000,000 | — | [7,000,000, 7,000,000] |
| TVaR₉₉ | 7,093,268 | 12,621 | [7,071,722, 7,121,664] |
| TVaR₉₉.₅ | 7,186,535 | 25,040 | [7,143,683, 7,242,559] |

The retained VaR interval collapsing to a point is not a bug — the treaty
attaches at 7,000,000, the retained distribution has an atom there, and the
order-statistic interval lands on it from both sides: the contract pins the
quantile harder than any amount of simulation could. The ceded side is the
opposite story: a pure premium of 29,475 with a 95% interval of
[28,343, 30,608] is a **±4% error bar on the price** — small enough to
quote, big enough that the fourth digit was never real, and visible, which
is the point. If the band is too wide, the answer is more simulations, and
now you can see it.
