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
      actuarialpy.md     narrative + API reference
      experiencestudies.md
      projectionmodels.md
      ratingmodels.md
      lossmodels.md
      extremeloss.md
      risksim.md
      _static/           custom CSS
      CNAME              custom domain

## Deploy

Pushing to `main` runs `.github/workflows/docs.yml`, which builds the site and
publishes it to the `gh-pages` branch. Let CI own the deploy — don't also run it
from a laptop, or the two will fight over `gh-pages`.
