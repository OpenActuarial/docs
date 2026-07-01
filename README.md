# OpenActuarial documentation site

One shared documentation site for the five packages — `actuarialpy`, `ratingmodels`,
`lossmodels`, `risksim`, `extremeloss` — built with [MkDocs](https://www.mkdocs.org/) +
[Material](https://squidfunk.github.io/mkdocs-material/). The API reference is generated
from each package's docstrings via
[mkdocstrings](https://mkdocstrings.github.io/), so the reference pages improve
automatically as docstrings improve.

## Build locally

```bash
pip install -r requirements.txt
mkdocs serve          # live preview at http://127.0.0.1:8000
mkdocs build          # static site into ./site
```

The packages must be importable (they are listed in `requirements.txt`) because the
API reference introspects them at build time.

## Deploy

Pushing to `main` runs `.github/workflows/docs.yml`, which builds and publishes to the
`gh-pages` branch via `mkdocs gh-deploy`. Enable GitHub Pages on that branch in the
repository settings.

## Structure

```
mkdocs.yml            site config, navigation, theme, plugins
docs/
  index.md            landing: the five packages + install
  overview.md         how they compose (with a diagram)
  actuarialpy.md      overview + quickstart + API reference
  ratingmodels.md
  lossmodels.md
  risksim.md
  extremeloss.md
```

Each package page ends with a `::: packagename` block that mkdocstrings expands into the
full API reference from docstrings.
