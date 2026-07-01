# risksim

Portfolio Monte Carlo simulation and risk measures: simulate aggregate outcomes
across a portfolio of contracts and summarize the distribution with standard risk
measures. numpy and pandas only.

The package builds a portfolio from contract definitions, simulates aggregate
outcomes, and reports risk measures (such as value-at-risk and tail value-at-risk)
over the simulated distribution — the capital view that sits at the end of the
experience → pricing → loss → tail → capital pipeline.

See the API reference below for the full surface; each object's docstring carries
its own usage.

## API reference

```{eval-rst}
.. automodule:: risksim
   :members:
```
