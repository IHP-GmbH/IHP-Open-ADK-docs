#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Check that formats/01 lists the specification's validation rules in order.

formats/01 summarises the rules of the specification's *Validation Rules*
section in the specification's own numbering, so that a page rule number can
be quoted against the specification. The summary is prose and is not
generated, so this check holds the numbering instead: the page must list
exactly the numbers 1..N that chiplet-spec ``docs/CHIPLET_FORMAT_SPEC.md``
lists, in order. The page's list sits between the RST comments
``.. validation-rules-begin`` and ``.. validation-rules-end``.

It writes nothing. It is a page check rather than part of a generator because
it reads a hand-written page, not a source.
"""

import os
import re

from _common import DOCS_DIR, SPEC, fail, read_text, require_submodule

SPEC_FORMAT = os.path.join("docs", "CHIPLET_FORMAT_SPEC.md")
PAGE = os.path.join(DOCS_DIR, "formats", "01_chiplet.rst")
BEGIN = ".. validation-rules-begin"
END = ".. validation-rules-end"


def numbers(lines):
    return [int(m.group(1)) for m in (re.match(r"^(\d+)\. ", line) for line in lines) if m]


def main():
    require_submodule(SPEC, "chiplet-spec")
    spec = read_text(os.path.join(SPEC, SPEC_FORMAT)).splitlines()
    if "## Validation Rules" not in spec:
        fail("{}: no Validation Rules section".format(SPEC_FORMAT))
    start = spec.index("## Validation Rules")
    end = next((n for n in range(start + 1, len(spec)) if spec[n].startswith("## ")), len(spec))
    rules = numbers(spec[start + 1:end])
    if rules != list(range(1, len(rules) + 1)):
        fail("{}: validation rules are not numbered 1..{}".format(SPEC_FORMAT, len(rules)))

    page = read_text(PAGE).splitlines()
    if page.count(BEGIN) != 1 or page.count(END) != 1 or page.index(BEGIN) > page.index(END):
        fail("formats/01: expected one {} ... {} pair".format(BEGIN, END))
    items = numbers(page[page.index(BEGIN) + 1:page.index(END)])
    if items != rules:
        fail("formats/01 lists validation rules {} but the specification has 1..{}".format(
            items, len(rules)))
    print("formats/01 follows the specification's {} validation rules".format(len(rules)))


if __name__ == "__main__":
    main()
