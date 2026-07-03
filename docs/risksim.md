# risksim

Portfolio Monte Carlo simulation and risk measures: simulate aggregate outcomes
across a portfolio of contracts and summarize the distribution with standard risk
measures. numpy only.

The package builds a portfolio from contract definitions, simulates aggregate
outcomes, and reports risk measures (such as value-at-risk and tail value-at-risk)
over the simulated distribution — the capital view that sits at the end of the
experience → pricing → loss → tail → capital pipeline.

`var` and `tvar` follow the ecosystem-wide empirical estimators (inverted-CDF
order statistic; Acerbi–Tasche), so a portfolio's risk measures here match the
same quantities computed in `lossmodels` or `extremeloss` byte for byte, and
every simulation accepts the shared `rng` argument (`None`, seed, or
`Generator`) for bit-reproducible runs — see [Conventions](conventions.md).

See the API reference below for the full surface; each object's docstring carries
its own usage.

## Portfolio simulation

A portfolio is a list of named items, each wrapping anything with a `.sample`
method — a fitted `lossmodels.CollectiveRiskModel` drops straight in:

```python
import risksim as rs

port = rs.Portfolio([
    rs.PortfolioItem("commercial", crm),
    rs.PortfolioItem("specialty", other_model, weight=0.4),
])
res = port.simulate(100_000, rng=7)
res.gross_losses, res.component_losses, res.component_names
```

`simulate` returns a `SimulationResult` carrying the gross, ceded, and
retained loss vectors, the per-component draws, and — when a contract is
applied — the per-layer recoveries. The `rng` argument (`None`, seed, or
`Generator`) resolves to one generator threaded through the components, so the
same seed reproduces every array bit for bit.

## Contracts

`AggregateLayer(attachment, limit, share)` follows the ecosystem coverage
semantics: `limit` is the layer **width**, so the layer exhausts at
`attachment + limit` (see
[Conventions](conventions.md#coverage-semantics)). `ContractProgram` stacks
layers, and `apply_contract` applies either to any loss vector, returning
`(ceded, retained)`:

```python
treaty = rs.AggregateLayer(attachment=3_200_000, limit=1_500_000,
                           name="agg_stop_loss")
res = port.simulate(100_000, contract=treaty, rng=7)
res.ceded_losses, res.retained_losses, res.layer_losses

ceded, retained = rs.apply_contract([50.0, 150.0, 400.0],
                                    rs.AggregateLayer(attachment=100.0, limit=200.0))
# ceded    -> [  0.,  50., 200.]
# retained -> [ 50., 100., 200.]
```

## Risk measures

```python
rs.metrics.var(res.gross_losses, 0.99)
rs.metrics.tvar(res.retained_losses, 0.99)
```

These are the ecosystem-wide empirical estimators — see the intro above and
[Conventions](conventions.md#risk-measures-var-and-tvar).

## API reference

```{eval-rst}
.. automodule:: risksim
   :members:
```
