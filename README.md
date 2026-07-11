# OpenActuarial documentation

Source for the unified documentation site at <https://openactuarial.org> — one
Sphinx site covering all seven packages in the OpenActuarial ecosystem
(actuarialpy, experiencestudies, projectionmodels, ratingmodels, lossmodels,
extremeloss, risksim).

## Build locally

    pip install -r requirements.txt
    make html            # or: sphinx-build -b html docs _build/html
    make serve           # build + serve at http://localhost:8000

`autodoc` introspects the *installed* packages, so the API reference reflects the
versions in your environment. For local iteration, install the packages editable
(`pip install -e ../actuarialpy` etc.) and rebuild.

## Structure

    docs/
      conf.py            Sphinx configuration
      index.md           landing page: the packages + install
      overview.md        how they compose
      <package>.md       narrative + API reference, one per package
      conventions.md     ecosystem-wide mathematical conventions
      stability.md       per-package API stability
      validation.md      comparisons against external references
      worked-example*.md nine end-to-end examples, runnable top to bottom
      _static/           custom CSS
      CNAME              custom domain

## Nightly checks

`.github/workflows/ecosystem-smoke.yml` reruns every package's test suite
against current PyPI releases each night and runs a blocking link check over
the site, so cross-package drift and link rot surface within a day.

## Deploy

Pushing to `main` runs `.github/workflows/docs.yml`, which builds the site and
publishes it to the `gh-pages` branch. Let CI own the deploy — don't also run it
from a laptop, or the two will fight over `gh-pages`.
