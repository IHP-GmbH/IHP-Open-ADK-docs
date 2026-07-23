# -*- coding: utf-8 -*-
# Copyright 2026 IHP Open ADK Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# SPDX-License-Identifier: Apache-2.0
#
# Configuration file for the Sphinx documentation builder.

import os
import subprocess

# -- Paths -------------------------------------------------------------------

DOCS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.dirname(DOCS_DIR)
SRC_DIR = os.path.join(REPO_ROOT, "src")

# -- Project information -----------------------------------------------------

project = "IHP Open ADK"
copyright = "2026, IHP Open ADK Authors"
author = "IHP Open ADK Authors"


def _adk_version():
    """Version of the documented ADK.

    Read from the pinned submodule's VERSION file, which is the authoritative
    source (tests/test_config_consistency.py in the ADK enforces that VERSION
    and every config/*.json version key agree). Fall back to git describe only
    if the submodule is not checked out, and to "unknown" if that also fails.
    Read the Docs clones shallow, so git describe alone is not reliable.
    """
    version_file = os.path.join(SRC_DIR, "IHP-Open-ADK", "VERSION")
    try:
        with open(version_file) as fh:
            value = fh.read().strip()
        if value:
            return value
    except OSError:
        pass
    try:
        described = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if described.returncode == 0 and described.stdout.strip():
            return described.stdout.strip().lstrip("v")
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


release = _adk_version()
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.githubpages",
    "sphinx.ext.ifconfig",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinxcontrib.bibtex",
    "myst_parser",
]

# The PDK docs enable autosectionlabel without this and already collide on
# duplicate section titles across pages. Prefixing with the document name makes
# every generated anchor unique.
autosectionlabel_prefix_document = True

bibtex_bibfiles = ["refs.bib"]

# sphinx_symbiflow_theme puts callables into html_context, which Sphinx cannot
# pickle into the environment cache. The warning is harmless and would otherwise
# fail the -W build.
suppress_warnings = ["config.cache"]

templates_path = ["_templates"]

# Pages are reStructuredText. Markdown stays enabled so vendored .md from the
# source repositories can be included without conversion.
source_suffix = [".rst", ".md"]

master_doc = "index"
language = "en"
pygments_style = None

exclude_patterns = [
    "_build",
    "_figures",
    "env",
    "venv",
    "docs_env",
    "Thumbs.db",
    ".DS_Store",
    "**/_usage/*.txt",
]

# -- GitHub integration ------------------------------------------------------

on_rtd = os.environ.get("READTHEDOCS", None) == "True"
if not on_rtd:
    html_context = {
        "display_github": True,
        "github_user": "IHP-GmbH",
        "github_repo": "IHP-Open-ADK-docs",
        "github_version": "main",
        "conf_py_path": "/docs/",
    }

# -- Options for HTML output -------------------------------------------------

# The same theme the IHP Open PDK documentation is published with. Note that
# the PDK docs repository declares sphinx_rtd_theme on main; the branch Read the
# Docs actually builds ("latest") uses sphinx_symbiflow_theme, which is what the
# published site serves. This site matches the published site.
html_theme = "sphinx_symbiflow_theme"

html_logo = "_static/IHP-Logo-ohne-claim.svg"
html_static_path = ["_static"]
html_title = f"IHP Open ADK {release} documentation"

html_theme_options = {
    "nav_title": "IHP Open Assembly Design Kit",
    "touch_icon": "IHP-Logo-ohne-claim.svg",
    "color_primary": "#00508b",
    "color_accent": "teal",
    "github_url": "https://github.com/IHP-GmbH/IHP-Open-ADK",
    "repo_name": "IHP-GmbH/IHP-Open-ADK",
    "repo_type": "github",
    # Visible levels of the global TOC; -1 means unlimited.
    "globaltoc_depth": 4,
    # If False, expand all TOC entries.
    "globaltoc_collapse": False,
    "hide_symbiflow_links": True,
    "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
}

# -- Link checking -----------------------------------------------------------

linkcheck_ignore = [
    # Rate-limits anonymous requests from CI.
    r"https://github\.com/IHP-GmbH/.*/(blob|tree)/.*",
    r"https://doi\.org/.*",
]
linkcheck_timeout = 20
linkcheck_retries = 2

# -- Options for manual page output ------------------------------------------

man_pages = [("index", "ihp-open-adk", "IHP Open ADK Documentation", [author], 1)]

# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    "preamble": r"""
        % Unicode characters that appear in rule tables and process figures.
        \DeclareUnicodeCharacter{03A9}{\ensuremath{\Omega}}
        \DeclareUnicodeCharacter{03BC}{\ensuremath{\mu}}
        \DeclareUnicodeCharacter{00B5}{\ensuremath{\mu}}
        \DeclareUnicodeCharacter{00B2}{\ensuremath{^2}}
        \DeclareUnicodeCharacter{2295}{\ensuremath{\oplus}}
        \DeclareUnicodeCharacter{25A1}{\ensuremath{\Box}}
        \DeclareUnicodeCharacter{2192}{\ensuremath{\rightarrow}}
        \DeclareUnicodeCharacter{2190}{\ensuremath{\leftarrow}}

        % Box-drawing characters used in directory listings.
        \usepackage{newunicodechar}
        \newunicodechar{├}{|}
        \newunicodechar{└}{|}
        \newunicodechar{─}{-}
        \newunicodechar{│}{|}

        \usepackage{lscape}
        \usepackage{graphicx}
    """,
}


def setup(app):
    app.add_css_file("ADK_theme.css")
    app.add_css_file("theme-switch.css")
    app.add_css_file("style.css")
    app.add_js_file("theme-switch.js")
