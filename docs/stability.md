# API stability

The packages are pre-1.0 and versioned accordingly; this page states
what that means so it is a policy rather than a mood.

**Public API.** The documented names importable from a package's top
level (and its documented submodules, e.g. `risksim.metrics`,
`risksim.uncertainty`, `risksim.dependence`). Anything prefixed with an
underscore — attributes like `_design_info_` included — is internal and
may change without notice.

**Versioning.** Patch releases (`0.x.Y`) never intentionally change
public behavior: fixes, docs, performance. Minor releases (`0.X.0`) may
change or remove public API, always with a changelog entry stating what
changed and why; where feasible, a deprecated name keeps working for one
minor release with a `DeprecationWarning` before removal. Numerical
outputs may shift within documented tolerances when an underlying
method is corrected — a correction is a change, and the changelog says
so (see, for example, the `null_deviance_` and IRLS notes in the
ratingmodels changelog).

**Cross-package floors.** Sibling dependencies declare explicit version
ranges in each package's `pyproject.toml` — a floor always, and an
upper cap where the downstream package is exposed to sibling API
movement. The dependency direction is deliberately thin and one-way —
`experiencestudies`, `projectionmodels`, and `ratingmodels` each
require `actuarialpy`; everything else cooperates through small
duck-typed protocols (`sf` + `mean_excess`) rather than imports.

**Python.** All packages support Python 3.10–3.14. This sentence can no
longer silently drift: the CI `metadata` job fails any package whose
classifiers or `requires-python` disagree with the version list the matrix
actually tests, and a `min-deps` job runs every suite at the minimum
declared dependency versions on the oldest supported Python.

**What this documentation was built against.**

```{include} _build_info.md
```

**What 1.0 will mean.** Freezing the public surface listed above, with
removals thereafter only via a full deprecation cycle. The gate is not
feature count; it is a release or two of the current surface in the
wild without design regrets.
