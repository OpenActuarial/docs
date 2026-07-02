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

## API reference

```{eval-rst}
.. automodule:: risksim
   :members:
```
