#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the shipped-adapter tables from pdk_adapters/.

An adapter is the only place a PDK-specific layer number is allowed to appear,
so the list of shipped adapters is the list of substrates and bumping methods
the ADK can check out of the box. Reading it from the directory keeps the
table honest when an adapter is added or removed.
"""

import glob
import os
import re

from _common import (
    ADK,
    DOCS_DIR,
    fail,
    format_number as fmt,
    read_text,
    require_submodule,
    write_csv,
)

# The one-line summary of an adapter is the first non-empty comment line after
# the SPDX header.
SPDX = re.compile(r"^#\s*SPDX-License-Identifier:")
COMMENT = re.compile(r"^#\s?(.*)$")
ASSIGN = re.compile(r"^\s*interconnect_rules\[['\"](?P<key>\w+)['\"]\]\s*=\s*(?P<val>[-\d.]+)")
DECLARES = re.compile(r"^\s*(?P<name>\w+)\s*=\s*(?!=)")


def summary_of(path):
    """First prose comment line of an adapter file."""
    seen_spdx = False
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if SPDX.match(stripped):
            seen_spdx = True
            continue
        if not seen_spdx:
            continue
        match = COMMENT.match(stripped)
        if not match:
            if stripped:
                break
            continue
        text = match.group(1).strip()
        if text:
            return text.rstrip(".")
    fail("no summary comment found in adapter {}".format(path))


def declared_names(path):
    """Top-level assignments an adapter makes, in declaration order."""
    names = []
    for line in read_text(path).splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = DECLARES.match(line)
        if match and match.group("name") not in names:
            names.append(match.group("name"))
    return names


def main():
    require_submodule(ADK, "src/IHP-Open-ADK")
    base = os.path.join(ADK, "pdk_adapters")

    interposer_rows = []
    for path in sorted(glob.glob(os.path.join(base, "interposer", "*.drc"))):
        name = os.path.splitext(os.path.basename(path))[0]
        names = declared_names(path)
        if "chiplet_attachment_input" not in names:
            fail(
                "interposer adapter {} does not declare the required abstract "
                "input chiplet_attachment_input".format(path)
            )
        interposer_rows.append([name, summary_of(path), ", ".join(names)])
    if not interposer_rows:
        fail("no interposer adapters found under {}".format(base))
    write_csv(
        os.path.join(DOCS_DIR, "adk", "tables", "interposer_adapters.csv"),
        interposer_rows,
    )

    interconnect_rows = []
    for path in sorted(glob.glob(os.path.join(base, "interconnect", "*.drc"))):
        name = os.path.splitext(os.path.basename(path))[0]
        values = {}
        for line in read_text(path).splitlines():
            match = ASSIGN.match(line)
            if match:
                values[match.group("key")] = float(match.group("val"))
        required = {"IXN_spacing", "IXN_pitch", "IXN_pad_size"}
        missing = required - set(values)
        if missing:
            fail(
                "interconnect adapter {} does not set required key(s): {}".format(
                    path, ", ".join(sorted(missing))
                )
            )
        interconnect_rows.append(
            [
                name,
                summary_of(path),
                fmt(values["IXN_spacing"]),
                fmt(values["IXN_pitch"]),
                fmt(values["IXN_pad_size"]),
            ]
        )
    if not interconnect_rows:
        fail("no interconnect adapters found under {}".format(base))
    write_csv(
        os.path.join(DOCS_DIR, "adk", "tables", "interconnect_adapters.csv"),
        interconnect_rows,
    )


if __name__ == "__main__":
    main()
