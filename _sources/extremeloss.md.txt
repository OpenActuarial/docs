# extremeloss

Extreme-value tail estimation for large claims: peaks-over-threshold with the
generalized Pareto distribution (GPD), tail analytics, and large-claim loading.
numpy and pandas only.

The package covers threshold selection, GPD estimation, and the analytics built
on a fitted tail — return levels, exceedance probabilities, and excess-layer
charges — plus integration helpers for splicing an empirical body to a fitted
tail. It composes with `lossmodels` and the pooling primitives in `actuarialpy`.

See the API reference below for the full surface; each object's docstring carries
its own usage.

## API reference

```{eval-rst}
.. automodule:: extremeloss
   :members:
```
