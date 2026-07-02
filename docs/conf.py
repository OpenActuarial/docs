# Configuration file for the Sphinx documentation builder.
# OpenActuarial ecosystem docs. https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import importlib.metadata as _md

# -- Project information -----------------------------------------------------

project = "OpenActuarial"
author = "OpenActuarial"
copyright = "2026, OpenActuarial"

try:
    release = _md.version("actuarialpy")
except Exception:  # pragma: no cover - fallback when not installed
    release = "0.35.0"
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_design",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Treat both Markdown (MyST) and reStructuredText as sources.
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}

# -- MyST ---------------------------------------------------------------------

myst_enable_extensions = [
    "colon_fence",   # ::: fenced directives (sphinx-design cards, admonitions)
    "dollarmath",    # $inline$ and $$block$$ math in Markdown pages
    "deflist",
    "attrs_inline",
    "smartquotes",
]
myst_heading_anchors = 3

# -- Autodoc / API ------------------------------------------------------------

autodoc_default_options = {
    "members": True,           # honors each package's __all__
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "signature"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True
autosummary_generate = False
add_module_names = False               # render `pmpm`, not `actuarialpy.pmpm`
python_use_unqualified_type_names = True
toc_object_entries = True
toc_object_entries_show_parents = "hide"

napoleon_google_docstring = True
napoleon_numpy_docstring = True

# Unresolved cross-references (e.g. to numpy/pandas types) should not fail the
# build; enable intersphinx below in an environment with network access to link
# them. Kept off here so the site builds in isolated CI without external fetches.
nitpicky = False

# -- HTML output --------------------------------------------------------------

html_theme = "furo"
html_title = "OpenActuarial"
html_static_path = ["_static"]
html_extra_path = ["CNAME"]            # copied verbatim to the site root
html_css_files = ["custom.css"]
html_show_sourcelink = False

html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "light_css_variables": {
        "color-brand-primary": "#0b6bcb",
        "color-brand-content": "#0b6bcb",
        "font-stack--monospace": "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
    },
    "dark_css_variables": {
        "color-brand-primary": "#4098e6",
        "color-brand-content": "#4098e6",
    },
    "source_repository": "https://github.com/OpenActuarial/docs/",
    "source_branch": "main",
    "source_directory": "docs/",
}

# Mermaid: render to inline SVG in the browser.
mermaid_output_format = "raw"
