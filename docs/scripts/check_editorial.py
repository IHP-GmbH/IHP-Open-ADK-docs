#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Check the editorial constraints of docs/contrib/02_documentation.rst.

These are factual and legal constraints, not style preferences. The check
reads exactly the files the site publishes, in two groups:

- this site's own files: everything under ``docs/`` but ``_build`` and
  ``_repos`` (pages, figures, recipes and the generated tables, includes and
  transcripts), and any file outside ``docs/`` and ``src/`` a page includes,
  such as the README;
- upstream files the site publishes as they stand: the pages Sphinx builds
  from ``_repos/*/docs`` (``REPO_PAGES`` in conf.py), the files those pages
  include, and the files a page of this site includes from ``src/``.

Every rule covers the site's own files, generated copies of upstream text
included. On upstream files every rule applies but the vendor rule, because
contrib/02 keeps a vendor name inside a file quoted verbatim. The dash rule
skips the upstream files in DASH_EXEMPT, which have to be fixed upstream; an
exemption no published file needs any more is an error.

It writes nothing and exits 1 on any hit.
"""

import glob
import os
import re
import sys

from _common import DOCS_DIR, REPO_ROOT, SRC_DIR

OWN_SUFFIXES = (".rst", ".md", ".svg", ".sh", ".csv", ".inc", ".txt", ".yaml")
SKIP_DIRS = {"_build", "_repos", ".git", "__pycache__"}
REPO_PAGES = "_repos/*/docs/**"

# reStructuredText and MyST include directives, and the path each names.
RST_INCLUDE = re.compile(r"^\s*\.\. (?:literal)?include::\s+(\S+)", re.MULTILINE)
MYST_INCLUDE = re.compile(r"^\s*[`:]{3,}\{(?:literal)?include\}\s+(\S+)", re.MULTILINE)

# Upstream files allowed to carry dashes, each with the date the exemption was
# recorded. Remove an entry once the file is fixed upstream and the pin moves.
DASH_EXEMPT = {
    # Recorded 2026-11-09 at Chiplets-KiCad-Plugin 233b7da.
    "src/Chiplets-KiCad-Plugin/plugins/chiplet_export/README.md",
}

DASHES = "[\u2014\u2013]"
EMOJI = "[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]"

# (pattern, message, whether it covers upstream files, files allowed to match).
RULES = [
    (r"netgen|run_demo\.py",
     "Do not name the tools or scripts of the unreleased connectivity work.", True, set()),
    (r"pactech|pac tech",
     "Do not name a bumping vendor in the site prose.", False, set()),
    # The contributing page quotes this rule in order to state it.
    (r"signoff.?grade|production.?grade",
     "Do not claim signoff-grade or production-grade. This is a preview release.", True,
     {"docs/contrib/02_documentation.rst"}),
    (DASHES,
     "Em-dashes and en-dashes are not allowed. Use a comma, a colon or a new sentence.",
     True, DASH_EXEMPT),
    (EMOJI, "Emojis are not allowed in documentation sources.", True, set()),
    # flow/06 keeps its stage-N labels for old URL fragments; flow/01 owns the numbers.
    (r":ref:`(?:[^`<]*<)?stage-\d",
     "Do not link a legacy stage-N label. Stage numbers live in the flow/01 table.",
     False, set()),
]


def relative(path):
    """path relative to the repository root, through any _repos symlink."""
    return os.path.relpath(os.path.realpath(path), os.path.realpath(REPO_ROOT))


def own_files():
    files = []
    for root, dirs, names in os.walk(DOCS_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        files += [os.path.join(root, n) for n in sorted(names) if n.endswith(OWN_SUFFIXES)]
    return files


def included(page):
    """The files page includes, resolved as Sphinx resolves them."""
    with open(page, encoding="utf-8") as handle:
        text = handle.read()
    found = []
    for target in RST_INCLUDE.findall(text) + MYST_INCLUDE.findall(text):
        if target.startswith("/"):
            path = os.path.join(DOCS_DIR, target.lstrip("/"))
        else:
            path = os.path.join(os.path.dirname(page), target)
        if not os.path.isfile(path):
            sys.exit("error: {} includes {}, which does not exist".format(relative(page), target))
        found.append(path)
    return found


def scopes():
    """(own, upstream): sets of paths relative to the repository root."""
    own = {relative(path) for path in own_files()}
    upstream = set()
    pages = [path for path in glob.glob(os.path.join(DOCS_DIR, REPO_PAGES), recursive=True)
             if os.path.isfile(path)]
    upstream.update(relative(path) for path in pages)
    src = os.path.relpath(os.path.realpath(SRC_DIR), os.path.realpath(REPO_ROOT)) + os.sep
    for page in pages + [p for p in own_files() if p.endswith((".rst", ".md"))]:
        for path in included(page):
            name = relative(path)
            (upstream if name.startswith(src) else own).add(name)
    return own, upstream - own


def main():
    own, upstream = scopes()
    failed = False
    for pattern, message, on_upstream, allowed in RULES:
        regex = re.compile(pattern, re.IGNORECASE)
        hits = []
        for name in sorted(((own | upstream) if on_upstream else own) - allowed):
            with open(os.path.join(REPO_ROOT, name), encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    if regex.search(line):
                        hits.append("{}:{}: {}".format(name, number, line.strip()))
        if hits:
            failed = True
            print("::error::" + message)
            print("\n".join(hits))
    for name in sorted(DASH_EXEMPT):
        if name in upstream:
            with open(os.path.join(REPO_ROOT, name), encoding="utf-8") as handle:
                if re.search(DASHES, handle.read()):
                    continue
        failed = True
        print("::error::{} is exempt from the dash rule but is no longer published "
              "or has no dash left. Drop the exemption.".format(name))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
