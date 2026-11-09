#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the interposer metal stack the Interposer PDK page shows.

Sources, each read at the OpenIntM4TM2 pin:

- ``libs.tech/intm4tm2_stack.json`` for the metals, the mount plane and the
  passivation films over it;
- the technology's connectivity (``<connection>`` in ``intm4tm2.lyt``) for the
  vias: a via spans from the top of the metal below it to the bottom of the
  metal above, so its z is derived rather than stored;
- ``intm4tm2_layers.txt`` for each GDS layer number.

``read_stack`` is also how gen_frame_values.py reads the mount plane, so the
stack file is parsed in one place.

Writes ``docs/tools/tables/interposer_stack.csv`` and
``docs/tools/_interposer_stack.inc``.
"""

import json
import os
import re
from decimal import Decimal, InvalidOperation

from _common import (
    DOCS_DIR,
    GENERATED_BANNER,
    INTERPOSER,
    fail,
    read_text,
    require_submodule,
    write_csv,
    write_text,
)

STACK = os.path.join(INTERPOSER, "libs.tech", "intm4tm2_stack.json")
TECH = os.path.join(INTERPOSER, "libs.tech", "klayout", "tech")
# The pages call the mount plane the top of this metal.
TOP_METAL = "TopMetal2"
# The table states every z to this many decimals, and fails on more.
QUANTUM = Decimal("0.0001")


def decimal(value, where):
    """A JSON number as an exact Decimal."""
    if isinstance(value, bool):
        fail("intm4tm2_stack.json: {} is {!r}, not a number".format(where, value))
    try:
        return Decimal(str(value))
    except InvalidOperation:
        fail("intm4tm2_stack.json: {} is {!r}, not a number".format(where, value))


def plain(value):
    """The shortest text of a Decimal, without an exponent: 10.8103, 2.8."""
    return format(value.normalize(), "f")


def read_stack():
    """The stack file as {"plane", "metals": {name: (zmin, zmax)},
    "passivation": [(name, material, thickness)]}, bottom up, after checking
    that the plane is the top of TOP_METAL."""
    stack = json.loads(read_text(STACK), parse_float=Decimal)
    try:
        beol = stack["beol"]
        plane = decimal(beol["attachment_surface_z_um"], "attachment_surface_z_um")
        metals = {
            m["name"]: (decimal(m["zmin_um"], m["name"]), decimal(m["zmax_um"], m["name"]))
            for m in beol["metals"]
        }
        passivation = [
            (film["name"], film["material"], decimal(film["thickness_um"], film["name"]))
            for film in beol["passivation"]
        ]
    except (KeyError, TypeError):
        fail("intm4tm2_stack.json: beol needs attachment_surface_z_um, metals "
             "with name, zmin_um and zmax_um, and passivation films with name, "
             "material and thickness_um")
    if TOP_METAL not in metals or metals[TOP_METAL][1] != plane:
        fail("intm4tm2_stack.json: the plane is no longer the top of {}".format(TOP_METAL))
    return {"plane": plane, "metals": metals, "passivation": passivation}


def via_spans(metals):
    """Each via of the technology's connectivity, as (zmin, zmax)."""
    spans = {}
    for connection in re.findall(
        r"<connection>([^<]*)</connection>", read_text(os.path.join(TECH, "intm4tm2.lyt"))
    ):
        parts = [part.strip() for part in connection.split(",")]
        if len(parts) != 3 or parts[0] not in metals or parts[2] not in metals:
            fail("intm4tm2.lyt: connection {!r} is not metal, via, metal of the "
                 "stack file's metals".format(connection))
        spans[parts[1]] = (metals[parts[0]][1], metals[parts[2]][0])
    return spans


def stack_rows(metals):
    """The metal stack top down: layer, GDS layer, z min, z max, thickness."""
    gds = {}
    for line in read_text(os.path.join(TECH, "intm4tm2_layers.txt")).splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[1] == "drawing":
            gds[fields[0]] = fields[2]
    spans = dict(metals, **via_spans(metals))
    layers = sorted(spans.items(), key=lambda item: -item[1][0])
    # Every layer must start where the one below it ends: no gap, no overlap.
    for (upper, (low, _)), (lower, (_, high)) in zip(layers, layers[1:]):
        if low != high:
            fail("intm4tm2 stack: {} starts at {} but {} below it ends at {}".format(
                upper, low, lower, high))
    rows = []
    for name, (low, high) in layers:
        if name not in gds:
            fail("intm4tm2_layers.txt has no drawing layer for {}".format(name))
        if not low < high:
            fail("intm4tm2 stack: {} spans {} to {}".format(name, low, high))
        cells = []
        for value in (low, high, high - low):
            fixed = value.quantize(QUANTUM)
            if fixed != value:
                fail("intm4tm2 stack: {} has more than four decimals".format(value))
            cells.append(str(fixed))
        rows.append([name, gds[name]] + cells)
    return rows


def passivation_values(stack):
    """Substitutions for the films over the plane and the top of the last."""
    # tools/05 names the two films.
    if [name for name, _material, _thickness in stack["passivation"]] != ["oxide", "nitride"]:
        fail("intm4tm2_stack.json: the passivation is no longer oxide, then nitride")
    values = [("interposer-passivation-{}".format(name), plain(thickness))
              for name, _material, thickness in stack["passivation"]]
    top = stack["plane"] + sum(thickness for _n, _m, thickness in stack["passivation"])
    values.append(("interposer-passivation-top", plain(top)))
    return values


def main():
    require_submodule(INTERPOSER, "src/OpenIntM4TM2")
    stack = read_stack()
    write_csv(
        os.path.join(DOCS_DIR, "tools", "tables", "interposer_stack.csv"),
        stack_rows(stack["metals"]),
    )
    write_text(
        os.path.join(DOCS_DIR, "tools", "_interposer_stack.inc"),
        GENERATED_BANNER.format(script=os.path.basename(__file__)) + "\n" + "".join(
            ".. |{}| replace:: {}\n".format(name, value)
            for name, value in passivation_values(stack)),
    )


if __name__ == "__main__":
    main()
