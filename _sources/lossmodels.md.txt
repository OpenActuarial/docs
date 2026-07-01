# lossmodels

Loss-distribution modeling: fit severity and frequency distributions and combine
them into an aggregate loss distribution. numpy and pandas only.

The package is organized into severity, frequency, and aggregate modules, with
supporting estimation, empirical, and coverage utilities. Fitted models expose a
consistent interface, and the aggregate layer convolves a frequency and a
severity model into the aggregate loss for a block.

See the API reference below for the full surface; each object's docstring carries
its own usage.

## API reference

```{eval-rst}
.. automodule:: lossmodels
   :members:
```
