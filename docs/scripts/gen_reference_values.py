#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the coordinate values the format and flow pages quote in prose.

Three sources, each read at its pin:

- the interposer PDK's mount plane, ``beol.attachment_surface_z_um`` in
  ``libs.tech/intm4tm2_stack.json`` of OpenIntM4TM2;
- the specification's hand-written worked example,
  ``examples/interposer_demo_design.chiplet`` in chiplet-system-spec, which the
  formats/ pages walk through;
- the generated reference design,
  ``examples/two_die_interposer/outputs/two_die_interposer.chiplet`` in
  ADK-Tools, which flow/08 walks through.

The two ``.chiplet`` files are different documents with different numbers, so
each gets its own prefix (``spec-`` and ``ref-``) and a page quotes only its
own. Both declare the PDK's plane, and every die z must be that plane plus the
die's stack height as an exact decimal sum (coordinate-frame contract 1.5 and
3.5); a file that disagrees fails the build instead of reaching a page.

The ``.chiplet`` files are read by a targeted line parser, not a YAML library,
because docs/requirements.txt carries none. It understands exactly the shapes
the two files use (block mappings, block sequences of ``- id:`` components, and
one-line flow mappings) and fails on any key it cannot find.

Writes ``docs/_reference_values.inc``.
"""

import os
import re
from decimal import Decimal, InvalidOperation

from _common import (
    DOCS_DIR,
    GENERATED_BANNER,
    INTERPOSER,
    SPEC,
    TOOLS,
    fail,
    format_number,
    read_json,
    read_text,
    require_submodule,
    write_text,
)

SPEC_EXAMPLE = os.path.join("examples", "interposer_demo_design.chiplet")
REF_DESIGN = os.path.join(
    "examples", "two_die_interposer", "outputs", "two_die_interposer.chiplet"
)


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def content(line):
    """The line without a trailing comment; blank for comment-only lines."""
    stripped = line.split(" #", 1)[0].rstrip()
    return "" if stripped.lstrip().startswith("#") else stripped


def sub_block(lines, start):
    """The lines indented deeper than lines[start], up to the first dedent."""
    base = indent_of(lines[start])
    block = []
    for line in lines[start + 1:]:
        if content(line) and indent_of(line) <= base:
            break
        block.append(line)
    return block


def flow_mapping(text, where):
    """Parse a one-line flow mapping such as ``{x: 1.0, y: 2.0}``."""
    text = text.strip()
    if not (text.startswith("{") and text.endswith("}")):
        fail("{}: expected a flow mapping, found {!r}".format(where, text))
    result = {}
    for item in text[1:-1].split(","):
        key, sep, value = item.partition(":")
        if not sep:
            fail("{}: malformed flow mapping {!r}".format(where, text))
        result[key.strip()] = value.strip()
    return result


class Chiplet:
    """The handful of lookups the pages need from one ``.chiplet`` file."""

    def __init__(self, path, label):
        self.label = label
        self.lines = read_text(path).splitlines()

    def where(self, *keys):
        return "{}: {}".format(self.label, ".".join(keys))

    def top_level(self, key):
        for number, line in enumerate(self.lines):
            if indent_of(line) == 0 and content(line) == key + ":":
                return sub_block(self.lines, number)
        fail("{} not found".format(self.where(key)))

    def component(self, comp_id):
        for number, line in enumerate(self.lines):
            text = content(line).strip()
            if text in ("- id: {}".format(comp_id), '- id: "{}"'.format(comp_id)):
                # Field keys sit two columns right of the dash.
                fields = [" " * (indent_of(line) + 2) + text[2:]]
                fields += sub_block(self.lines, number)
                return fields
        fail("component {} not found in {}".format(comp_id, self.label))

    def field(self, block, comp_id, key):
        """A component field: a scalar, or a mapping (flow or block style)."""
        level = indent_of(block[0])
        for number, line in enumerate(block):
            if indent_of(line) != level:
                continue
            name, sep, value = content(line).strip().partition(":")
            if not sep or name != key:
                continue
            value = value.strip()
            if value.startswith("{"):
                return flow_mapping(value, self.where(comp_id, key))
            if value:
                return value
            mapping = {}
            for child in sub_block(block, number):
                if not content(child):
                    continue
                k, s, v = content(child).strip().partition(":")
                if not s or not v.strip():
                    fail("{}: unexpected line {!r}".format(self.where(comp_id, key), child))
                mapping[k.strip()] = v.strip()
            return mapping
        fail("{} not found".format(self.where(comp_id, key)))

    def subfield(self, comp_id, key, sub):
        mapping = self.field(self.component(comp_id), comp_id, key)
        if not isinstance(mapping, dict) or sub not in mapping:
            fail("{} not found".format(self.where(comp_id, key, sub)))
        return mapping[sub]

    def scalar(self, comp_id, key):
        value = self.field(self.component(comp_id), comp_id, key)
        if isinstance(value, dict):
            fail("{} is a mapping, expected a scalar".format(self.where(comp_id, key)))
        return value.strip("\"'")

    def stack_height(self, stack_id):
        """Sum of the layer heights of one connection stack, in decimal."""
        stacks = self.top_level("connection_stacks")
        for number, line in enumerate(stacks):
            if content(line).strip() == stack_id + ":":
                heights = re.findall(
                    r"\bheight:\s*([0-9.]+)", "\n".join(sub_block(stacks, number))
                )
                if not heights:
                    fail("{} has no layer heights".format(self.where("connection_stacks", stack_id)))
                return sum(decimal(h, self.where(stack_id, "height")) for h in heights)
        fail("{} not found".format(self.where("connection_stacks", stack_id)))


def decimal(text, where):
    try:
        return Decimal(text)
    except InvalidOperation:
        fail("{}: {!r} is not a number".format(where, text))


def plain(value):
    """A Decimal as the shortest plain text: 54.8103, 44, never 4.4E+1."""
    return format(value.normalize(), "f")


def checked_die_z(doc, comp_id, plane):
    """The die's z text, after checking it is the plane plus its stack."""
    z_text = doc.subfield(comp_id, "position", "z")
    stack = doc.scalar(comp_id, "connection")
    height = doc.stack_height(stack)
    if decimal(z_text, doc.where(comp_id, "position", "z")) != plane + height:
        fail(
            "{}: z {} is not the plane {} plus {} ({})".format(
                doc.label, z_text, plain(plane), stack, plain(height)
            )
        )
    return z_text, height


def checked_plane(doc, plane):
    text = doc.scalar("interposer", "attachment_surface_z")
    if decimal(text, doc.where("interposer", "attachment_surface_z")) != plane:
        fail(
            "{} declares attachment_surface_z {}, the PDK key is {}".format(
                doc.label, text, plain(plane)
            )
        )


def main():
    require_submodule(INTERPOSER, "OpenIntM4TM2")
    require_submodule(SPEC, "chiplet-spec")
    require_submodule(TOOLS, "ADK-Tools")

    stack = read_json(os.path.join(INTERPOSER, "libs.tech", "intm4tm2_stack.json"))
    try:
        plane_value = stack["beol"]["attachment_surface_z_um"]
    except (KeyError, TypeError):
        fail("intm4tm2_stack.json has no beol.attachment_surface_z_um")
    plane = decimal(repr(plane_value), "beol.attachment_surface_z_um")

    spec = Chiplet(os.path.join(SPEC, SPEC_EXAMPLE), "chiplet-spec/" + SPEC_EXAMPLE)
    ref = Chiplet(os.path.join(TOOLS, REF_DESIGN), "ADK-Tools/" + REF_DESIGN)

    values = [("attach-z", plain(plane))]

    checked_plane(spec, plane)
    heights = {}
    for die in ("U1", "U2"):
        z_text, heights[die] = checked_die_z(spec, die, plane)
        values.append(("spec-{}-z".format(die.lower()), z_text))
        values.append(("spec-{}-stack".format(die.lower()), plain(heights[die])))
    # What a writer that sums in binary and prints 17 significant digits emits
    # for U1 instead (contract 1.5), quoted as the counterexample.
    binary = "%.17g" % (float(plane) + float(heights["U1"]))
    if decimal(binary, "binary sum") == plane + heights["U1"]:
        fail("the plane plus U1's stack is exact in binary; formats/03 needs "
             "another counterexample")
    values.append(("spec-u1-z-binary", "``{}``".format(binary)))

    checked_plane(ref, plane)
    for key in ("width", "height", "thickness"):
        values.append(
            (
                "ref-interposer-{}".format(key),
                format_number(ref.subfield("interposer", "dimensions", key)),
            )
        )
    values.append(
        ("ref-interposer-x-text", "``{}``".format(ref.subfield("interposer", "position", "x")))
    )
    die_dims = {}
    for die in ("U1", "U2"):
        die_dims[die] = tuple(
            format_number(ref.subfield(die, "dimensions", key))
            for key in ("width", "height", "thickness")
        )
        z_text, _height = checked_die_z(ref, die, plane)
        values.append(("ref-{}-z".format(die.lower()), z_text))
    if die_dims["U1"] != die_dims["U2"]:
        fail("{}: U1 and U2 no longer share dimensions".format(ref.label))
    for key, value in zip(("width", "height", "thickness"), die_dims["U1"]):
        values.append(("ref-die-{}".format(key), value))

    text = GENERATED_BANNER.format(script=os.path.basename(__file__)) + "\n"
    for name, value in values:
        text += ".. |{}| replace:: {}\n".format(name, value)
    write_text(os.path.join(DOCS_DIR, "_reference_values.inc"), text)


if __name__ == "__main__":
    main()
