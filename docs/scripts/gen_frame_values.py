#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the coordinate-frame values the format and flow pages quote.

Sources, each read at its pin:

- the interposer PDK's mount plane, ``beol.attachment_surface_z_um`` in
  OpenIntM4TM2 ``libs.tech/intm4tm2_stack.json``;
- the specification's hand-written worked example,
  chiplet-spec ``examples/interposer_demo_design.chiplet``, which the formats/
  pages walk through and include;
- the generated reference design, ADK-Tools
  ``examples/two_die_interposer/outputs/two_die_interposer.chiplet``, and the
  die layout it places, which flow/08 walks through;
- the values Chiplet Studio's wire-bond demo round trip asserts, in its
  ``tests/test_coord_frame_contract.cpp``;
- the z tolerance of the ADK's ``openroad/chiplet2dbx.py`` (``Z_TOLERANCE``);
- the usage-class table of the specification's Python reference reader
  (``IO_CLASS_INTERFACE_TYPES``);
- the specification's numbered validation rules.

The two ``.chiplet`` files are different documents with different numbers, so
each has its own prefix (``spec-`` and ``refdesign-``) and a page quotes only
its own. Both must declare the PDK's plane, and every die z must be that plane
plus the die's stack height as an exact decimal sum (contract sections 1.5 and
3.5); a whole number written ``N.0`` counts as ``N``, as it does upstream.
ADK-Tools' ``ci/check_attach_plane.py`` already holds the reference design to
that, so the check here matters for the specification's example, which no
upstream check reads. Decimal text is kept exact: YAML floats load as Decimal
and the PDK key is parsed with ``parse_float=Decimal``.

The die ids U1 and U2 are named here because the pages name them: flow/08 and
formats/03 describe two dies with those ids, so a file that renamed them would
make the prose wrong, and the build should stop.

Pages also include parts of the specification's files by text markers. The
markers are repeated below and checked, so a file that moves them fails here
instead of silently including the wrong lines.

formats/01 summarises the specification's validation rules in the
specification's numbering. The rule count and order are checked against the
specification: each page item must name, in double backticks, the first
identifier the specification's rule of the same number names.

Writes ``docs/_frame_values.inc`` and
``docs/formats/tables/io_class_interface_types.csv``.
"""

import ast
import json
import os
import re
from decimal import Decimal, InvalidOperation

import yaml

from _common import (
    ADK,
    DOCS_DIR,
    GENERATED_BANNER,
    INTERPOSER,
    SPEC,
    SRC_DIR,
    TOOLS,
    fail,
    format_number,
    read_text,
    require_submodule,
    write_csv,
    write_text,
)

STUDIO = os.path.join(SRC_DIR, "chiplet-studio")

SPEC_EXAMPLE = os.path.join("examples", "interposer_demo_design.chiplet")
SPEC_CONTRACT = os.path.join("docs", "coord_frame_contract.md")
SPEC_FORMAT = os.path.join("docs", "CHIPLET_FORMAT_SPEC.md")
SPEC_READER = os.path.join("reference", "python", "chiplet_format_io", "__init__.py")
REF_DESIGN = os.path.join(
    "examples", "two_die_interposer", "outputs", "two_die_interposer.chiplet"
)
STUDIO_TEST = os.path.join("tests", "test_coord_frame_contract.cpp")
CHIPLET2DBX = os.path.join("openroad", "chiplet2dbx.py")
VALIDATION_PAGE = os.path.join(DOCS_DIR, "formats", "01_chiplet.rst")

DIES = ("U1", "U2")

# The pad formats/03 transforms in its worked case, in die-local GDS um.
EXAMPLE_PAD = (Decimal("312.500"), Decimal("-845.000"))


class DecimalLoader(yaml.SafeLoader):
    """SafeLoader whose floats are Decimals built from the text as written."""


DecimalLoader.add_constructor(
    "tag:yaml.org,2002:float",
    lambda loader, node: Decimal(loader.construct_scalar(node).replace("_", "")),
)


def number(value, where):
    """A YAML or JSON number, or a quoted one, as a Decimal."""
    if isinstance(value, bool):
        fail("{}: {!r} is not a number".format(where, value))
    try:
        return Decimal(str(value))
    except InvalidOperation:
        fail("{}: {!r} is not a number".format(where, value))


def plain(value):
    """A Decimal as plain text without an exponent: 54.8103, 44."""
    text = format(value.normalize(), "f")
    return text


def literal(text):
    return "``{}``".format(text)


def point(x, y):
    return literal("({}, {})".format(plain(x), plain(y)))


class Chiplet:
    def __init__(self, path, label):
        self.path = path
        self.label = label
        try:
            self.doc = yaml.load(read_text(path), Loader=DecimalLoader)
        except yaml.YAMLError as error:
            fail("{} does not parse: {}".format(label, error))
        if not isinstance(self.doc, dict):
            fail("{} is not a mapping".format(label))

    def get(self, node, *keys):
        for key in keys:
            if isinstance(key, int):
                ok = isinstance(node, list) and key < len(node)
            else:
                ok = isinstance(node, dict) and key in node
            if not ok:
                fail("{}: {} not found".format(self.label, ".".join(map(str, keys))))
            node = node[key]
        return node

    def component(self, comp_id):
        for comp in self.get(self.doc, "components"):
            if isinstance(comp, dict) and str(comp.get("id")) == comp_id:
                return comp
        fail("{}: component {} not found".format(self.label, comp_id))

    def value(self, comp_id, *keys):
        return number(
            self.get(self.component(comp_id), *keys),
            "{}: {}.{}".format(self.label, comp_id, ".".join(keys)),
        )

    def layers(self, stack_id):
        layers = self.get(self.doc, "connection_stacks", stack_id, "layers")
        if not isinstance(layers, list) or not layers:
            fail("{}: connection stack {} has no layers".format(self.label, stack_id))
        return layers

    def stack_height(self, stack_id):
        where = "{}: {} height".format(self.label, stack_id)
        return sum(number(self.get(layer, "height"), where) for layer in self.layers(stack_id))

    def stack_phrase(self, stack_id):
        """The stack's layers as prose, bottom first: 28 um ``CuPillar`` plus ..."""
        return " plus ".join(
            "{} um ``{}``".format(
                plain(number(self.get(layer, "height"), stack_id + " height")),
                self.get(layer, "name"),
            )
            for layer in self.layers(stack_id)
        )

    def die_z(self, comp_id, plane):
        """The die's z text, after checking it is the plane plus its stack."""
        z = self.value(comp_id, "position", "z")
        stack = str(self.get(self.component(comp_id), "connection"))
        height = self.stack_height(stack)
        if z != plane + height:
            fail(
                "{}: {} z {} is not the plane {} plus {} ({})".format(
                    self.label, comp_id, plain(z), plain(plane), stack, plain(height)
                )
            )
        return z, stack, height

    def check_plane(self, plane):
        declared = self.value("interposer", "attachment_surface_z")
        if declared != plane:
            fail(
                "{} declares attachment_surface_z {}, the PDK key is {}".format(
                    self.label, plain(declared), plain(plane)
                )
            )


def require_marker(text, label, before, after=None):
    """The first line holding ``before`` must start with it, as the include assumes."""
    lines = text.splitlines()
    hits = [n for n, line in enumerate(lines) if before in line]
    if not hits or not lines[hits[0]].lstrip().startswith(before):
        fail("{}: the include marker {!r} no longer opens its block".format(label, before))
    return lines, hits[0]


def check_include_markers():
    example = read_text(os.path.join(SPEC, SPEC_EXAMPLE))
    label = "chiplet-spec/" + SPEC_EXAMPLE
    lines, start = require_marker(example, label, "format_version:")
    if lines[start] != lines[start].lstrip():
        fail("{}: format_version is not the root key the include starts at".format(label))
    lines, start = require_marker(example, label, "- id: U1")
    for line in lines[start + 1:]:
        if "rotation:" in line:
            break
        if "- id:" in line:
            fail("{}: U1 has no rotation line before the next component".format(label))
    else:
        fail("{}: no rotation line after U1".format(label))

    contract = read_text(os.path.join(SPEC, SPEC_CONTRACT)).splitlines()
    label = "chiplet-spec/" + SPEC_CONTRACT
    opener = "lower-left corner at (250, 250) inside the interposer:"
    hits = [n for n, line in enumerate(contract) if opener in line]
    if len(hits) != 1 or contract[hits[0] + 1].strip() != "```yaml":
        fail("{}: the position example no longer follows {!r}".format(label, opener))
    for line in contract[hits[0] + 2:]:
        if "thickness: 50.0" in line:
            break
        if line.startswith("```"):
            fail("{}: the position example has no thickness: 50.0 line".format(label))


def reference_design_values(plane):
    ref = Chiplet(os.path.join(TOOLS, REF_DESIGN), "ADK-Tools/" + REF_DESIGN)
    ref.check_plane(plane)
    values = []
    for key in ("width", "height", "thickness"):
        values.append(
            ("refdesign-interposer-" + key,
             format_number(ref.value("interposer", "dimensions", key)))
        )
    values.append(
        ("refdesign-interposer-x-text",
         literal(ref.get(ref.component("interposer"), "position", "x")))
    )
    dims = {}
    for die in DIES:
        dims[die] = tuple(
            format_number(ref.value(die, "dimensions", key))
            for key in ("width", "height", "thickness")
        )
        z, stack, height = ref.die_z(die, plane)
        layers = ref.layers(stack)
        diameters = {
            number(ref.get(layer, "diameter"), stack + " diameter") for layer in layers
        }
        if len(diameters) != 1:
            fail("{}: {} layers differ in diameter".format(ref.label, stack))
        phrase = ref.stack_phrase(stack)
        prefix = "refdesign-" + die.lower()
        values += [
            (prefix + "-z", plain(z)),
            (prefix + "-stack", plain(height)),
            (prefix + "-stack-layers", phrase),
            (prefix + "-stack-diameter", plain(diameters.pop())),
        ]
    if dims["U1"] != dims["U2"]:
        fail("{}: U1 and U2 no longer share dimensions".format(ref.label))
    for key, value in zip(("width", "height", "thickness"), dims["U1"]):
        values.append(("refdesign-die-" + key, value))

    # flow/08 states how far the shared die's GDS origin sits from its
    # outline centre, which is what chiplet2dbx shifts the outline by.
    layouts = {str(ref.get(ref.component(die), "layout")) for die in DIES}
    cells = {str(ref.get(ref.component(die), "top_cell")) for die in DIES}
    if len(layouts) != 1 or len(cells) != 1:
        fail("{}: U1 and U2 no longer share one layout".format(ref.label))
    gds = os.path.normpath(os.path.join(os.path.dirname(ref.path), layouts.pop()))
    if not os.path.isfile(gds):
        fail("die layout not found: {}".format(gds))
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(gds)
    cell = layout.cell(cells.pop())
    if cell is None:
        fail("{}: top cell not found".format(gds))
    box = cell.dbbox()
    if (format_number(box.width()), format_number(box.height())) != dims["U1"][:2]:
        fail("{}: bbox {} x {} differs from the .chiplet dimensions".format(
            gds, box.width(), box.height()))
    centre = box.center()
    if format_number(round(centre.x, 6)) != "0":
        fail("{}: origin is off-centre in x too; flow/08 names y only".format(gds))
    offset = format_number(round(centre.y, 6))
    if offset == "0":
        fail("{}: origin is centred; flow/08 says it is not".format(gds))
    values.append(("refdesign-die-origin-offset-y", offset.lstrip("-")))
    return values


def spec_example_values(plane):
    spec = Chiplet(os.path.join(SPEC, SPEC_EXAMPLE), "chiplet-spec/" + SPEC_EXAMPLE)
    spec.check_plane(plane)
    values = []
    for die in DIES:
        z, stack, height = spec.die_z(die, plane)
        values += [
            ("spec-{}-z".format(die.lower()), plain(z)),
            ("spec-{}-stack".format(die.lower()), plain(height)),
            ("spec-{}-stack-layers".format(die.lower()), spec.stack_phrase(stack)),
            ("spec-{}-connection".format(die.lower()), literal(stack)),
        ]
    # What a writer that sums in binary and prints 17 significant digits
    # writes for U1 instead (contract 1.5), quoted as the counterexample.
    _z, _stack, u1_height = spec.die_z("U1", plane)
    binary = "%.17g" % (float(plane) + float(u1_height))
    if Decimal(binary) == plane + u1_height:
        fail("the plane plus U1's stack is exact in binary; formats/03 needs "
             "another counterexample")
    values.append(("spec-u1-z-binary", literal(binary)))

    # The formats/03 worked case: one pad of U1 through mirror, rotation and
    # translation.
    # The page walks a flip-chip die with no rotation, then turns it by 90.
    u1 = spec.component("U1")
    if spec.get(u1, "orientation") != "flip_chip" or spec.value("U1", "rotation", "z") != 0:
        fail("{}: U1 is no longer an unrotated flip_chip die; rewrite the "
             "formats/03 worked case".format(spec.label))
    x = spec.value("U1", "position", "x")
    y = spec.value("U1", "position", "y")
    px, py = EXAMPLE_PAD
    values += [
        ("spec-u1-x", plain(x)),
        ("spec-u1-y", plain(y)),
        ("example-pad", point(px, py)),
        ("example-pad-mirrored", point(-px, py)),
        ("example-pad-x", plain(px)),
        ("example-pad-y", plain(py)),
        ("spec-u1-pad-flip", point(x - px, y + py)),
        ("spec-u1-pad-face-up", point(x + px, y + py)),
        ("spec-u1-pad-face-up-shift", plain(2 * px)),
        ("spec-u1-pad-flip-r90", point(x - py, y - px)),
    ]
    return values


def studio_demo_values():
    """The positions Studio's wire-bond demo round trip asserts."""
    text = read_text(os.path.join(STUDIO, STUDIO_TEST))
    found = {}
    for obj, axis, value, tol in re.findall(
        r"EXPECT_NEAR\((\w+)->position\(\)\.([xyz]),\s*([-0-9.]+),\s*([-0-9.e]+)\)", text
    ):
        found[(obj, axis)] = (Decimal(value), tol)
    values = []
    tolerances = set()
    xy_tolerances = {found[(obj, axis)][1] for obj in ("u1", "u2", "interposer") for axis in "xy"
                     if (obj, axis) in found}
    if len(xy_tolerances) != 1:
        fail("{}: the x and y tolerances differ between components".format(STUDIO_TEST))
    values.append(("studio-demo-xy-tol", xy_tolerances.pop()))
    for obj in ("u1", "u2", "interposer"):
        for axis in "xyz":
            if (obj, axis) not in found:
                fail("{}: no EXPECT_NEAR for {}.{}".format(STUDIO_TEST, obj, axis))
        xy = point(found[(obj, "x")][0], found[(obj, "y")][0])
        values.append(("studio-demo-{}-xy".format(obj), xy))
        values.append(("studio-demo-{}-z".format(obj), plain(found[(obj, "z")][0])))
        if obj != "interposer":
            tolerances.add(found[(obj, "z")][1])
    if len(tolerances) != 1:
        fail("{}: U1 and U2 z tolerances differ".format(STUDIO_TEST))
    values.append(("studio-demo-die-z-tol", tolerances.pop()))
    return values


def chiplet2dbx_values():
    """The tolerance chiplet2dbx holds a die's z to, which flow/08 quotes."""
    text = read_text(os.path.join(ADK, CHIPLET2DBX))
    found = re.findall(r"^Z_TOLERANCE = ([0-9.e-]+)$", text, re.M)
    if len(found) != 1:
        fail("{}: no single Z_TOLERANCE constant".format(CHIPLET2DBX))
    return [("chiplet2dbx-z-tol", found[0])]


def io_class_rows():
    tree = ast.parse(read_text(os.path.join(SPEC, SPEC_READER)))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "IO_CLASS_INTERFACE_TYPES" for t in node.targets
        ):
            table = ast.literal_eval(node.value)
            break
    else:
        fail("{}: IO_CLASS_INTERFACE_TYPES not found".format(SPEC_READER))
    if not table:
        fail("IO_CLASS_INTERFACE_TYPES is empty")
    return [
        [literal(usage), ", ".join(literal(t) for t in types)]
        for usage, types in table.items()
    ]


def numbered_items(lines):
    """Map each top-level numbered item of a list to its text."""
    items = []
    for line in lines:
        match = re.match(r"^(\d+)\. (.*)", line)
        if match:
            items.append([int(match.group(1)), match.group(2)])
        elif items and line.startswith(" "):
            items[-1][1] += " " + line.strip()
    return items


def check_validation_rules():
    spec = read_text(os.path.join(SPEC, SPEC_FORMAT)).splitlines()
    try:
        start = spec.index("## Validation Rules")
    except ValueError:
        fail("{}: no Validation Rules section".format(SPEC_FORMAT))
    end = next((n for n in range(start + 1, len(spec)) if spec[n].startswith("## ")), len(spec))
    rules = numbered_items(spec[start + 1:end])

    page = read_text(VALIDATION_PAGE).splitlines()
    try:
        start = page.index("Validation rules")
        end = page.index("Reading and writing .chiplet files")
    except ValueError:
        fail("formats/01: the Validation rules section moved")
    items = numbered_items(page[start + 1:end])

    if [n for n, _ in rules] != list(range(1, len(rules) + 1)):
        fail("{}: validation rules are not numbered 1..{}".format(SPEC_FORMAT, len(rules)))
    if [n for n, _ in items] != [n for n, _ in rules]:
        fail(
            "formats/01 lists validation rules {} but the specification has 1..{}".format(
                [n for n, _ in items], len(rules)
            )
        )
    for (n, rule), (_, item) in zip(rules, items):
        token = re.search(r"`([^`]+)`", rule)
        if not token:
            continue
        name = token.group(1).rstrip(":")
        if "``{}``".format(name) not in item:
            fail(
                "formats/01 validation rule {} does not name ``{}``, which the "
                "specification's rule {} starts from".format(n, name, n)
            )
    return len(rules)


def main():
    require_submodule(INTERPOSER, "OpenIntM4TM2")
    require_submodule(SPEC, "chiplet-spec")
    require_submodule(TOOLS, "ADK-Tools")
    require_submodule(STUDIO, "chiplet-studio")
    require_submodule(ADK, "IHP-Open-ADK")

    stack_path = os.path.join(INTERPOSER, "libs.tech", "intm4tm2_stack.json")
    stack = json.loads(read_text(stack_path), parse_float=Decimal)
    try:
        plane = number(stack["beol"]["attachment_surface_z_um"], "attachment_surface_z_um")
    except (KeyError, TypeError):
        fail("intm4tm2_stack.json has no beol.attachment_surface_z_um")

    check_include_markers()
    rule_count = check_validation_rules()

    values = [("interposer-attachment-z", plain(plane))]
    values += spec_example_values(plane)
    values += reference_design_values(plane)
    values += studio_demo_values()
    values += chiplet2dbx_values()
    values.append(("spec-validation-rule-count", str(rule_count)))

    text = GENERATED_BANNER.format(script=os.path.basename(__file__)) + "\n"
    for name, value in values:
        text += ".. |{}| replace:: {}\n".format(name, value)
    write_text(os.path.join(DOCS_DIR, "_frame_values.inc"), text)
    write_csv(
        os.path.join(DOCS_DIR, "formats", "tables", "io_class_interface_types.csv"),
        io_class_rows(),
    )


if __name__ == "__main__":
    main()
