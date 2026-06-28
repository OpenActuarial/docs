# risksim

Monte Carlo simulation of portfolios of risk models, with reinsurance contracts and
layers. You wrap any sampling model (for example a `lossmodels` collective-risk model)
in a `PortfolioItem`, collect items into a `Portfolio`, and simulate the aggregate —
gross, retained, ceded, and by layer.

## Quickstart

```python
import lossmodels as lm
import risksim as rs

# each group is a collective-risk model
group_a = lm.CollectiveRiskModel(lm.Poisson(lam=3.0), lm.Lognormal(8.0, 1.5))
group_b = lm.CollectiveRiskModel(lm.Poisson(lam=5.0), lm.Lognormal(8.2, 1.4))

portfolio = rs.Portfolio([
    rs.PortfolioItem("group_a", group_a),
    rs.PortfolioItem("group_b", group_b),
])

result = portfolio.simulate(50_000)            # SimulationResult
result.mean()                                  # expected aggregate loss
result.prob_exceeding(1_000_000)               # P(aggregate > 1M)
result.summary()                               # gross/retained/ceded summary
```

## Reinsurance layers

```python
import risksim as rs

layer = rs.AggregateLayer(attachment=1_000_000, limit=2_000_000)
result = portfolio.simulate(50_000, contract=layer)
result.ceded_mean()                            # expected ceded into the layer
result.retained_mean()                         # expected retained
```

## API reference

::: risksim
