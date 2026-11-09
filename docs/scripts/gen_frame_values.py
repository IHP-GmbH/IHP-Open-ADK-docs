#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the coordinate-frame values and excerpts the pages quote.

Sources, each read at its pin:

- the interposer PDK's mount plane, ``beol.attachment_surface_z_um`` in
  OpenIntM4TM2 ``libs.tech/intm4tm2_stack.json``, and its metal stack, with
  each via spanning the two metals the technology's connectivity joins it to
  and each GDS layer number from the canonical layer list;
- the interconnect methods manifest of IHP-Interconnect-IntM4TM2, for each
  method's pitch and spacing;
- the specification's hand-written worked example,
  chiplet-spec ``examples/interposer_demo_design.chiplet``, and the position
  example of its ``docs/coord_frame_contract.md``;
- the generated reference design, ADK-Tools
  ``examples/two_die_interposer/outputs/two_die_interposer.chiplet``, and the
  die layout it places (read with KLayout);
- the values Chiplet Studio's wire-bond demo round trip asserts, in its
  ``tests/test_coord_frame_contract.cpp``;
- the z tolerance of the ADK's ``openroad/chiplet2dbx.py`` (``Z_TOLERANCE``);
- the usage-class table of the specification's Python reference reader
  (``IO_CLASS_INTERFACE_TYPES``).

The two ``.chiplet`` files are different documents with different numbers, so
each has its own prefix (``spec-`` and ``refdesign-``) and a page quotes only
its own. Both must declare the PDK's plane, and every die z must be written as
the plane plus the die's stack height the way contract section 1.5 states: the
shortest text of the exact decimal sum, with ``N.0`` accepted for a whole N, as
ADK-Tools' ``ci/check_attach_plane.py`` accepts it. The comparison is on the
text as written, not on the value. That upstream check already holds the
reference design to this, so the check here matters for the specification's
example, which no upstream check reads. Decimal text is kept exact: YAML floats
load as Decimal and the PDK key is parsed with ``parse_float=Decimal``.

The die ids U1 and U2 are named here because the pages name them: flow/08 and
formats/03 describe two dies with those ids, so a file that renamed them would
make the prose wrong, and the build should stop.

The parts of the specification the pages show are written out as excerpts
under ``docs/formats/_excerpts/`` and included from there, so the CI drift
gate shows every upstream change to them.

Writes ``docs/_frame_values.inc``, ``docs/formats/_excerpts/*.yaml``,
``docs/formats/tables/io_class_interface_types.csv`` and
``docs/tools/tables/interposer_stack.csv``.
"""

import ast
import json
import math
import os
import re
from decimal import Decimal, InvalidOperation

import yaml

from _common import (
    ADK,
    DOCS_DIR,
    GENERATED_BANNER,
    INTERCONNECT,
    INTERPOSER,
    SPEC,
    SRC_DIR,
    TOOLS,
    fail,
    read_text,
    require_submodule,
    write_csv,
    write_text,
)

STUDIO = os.path.join(SRC_DIR, "chiplet-studio")

SPEC_EXAMPLE = os.path.join("examples", "interposer_demo_design.chiplet")
SPEC_CONTRACT = os.path.join("docs", "coord_frame_contract.md")
SPEC_READER = os.path.join("reference", "python", "chiplet_format_io", "__init__.py")
REF_DESIGN = os.path.join(
    "examples", "two_die_interposer", "outputs", "two_die_interposer.chiplet"
)
METHODS = os.path.join("manifest", "interconnect_methods.json")
STUDIO_TEST = os.path.join("tests", "test_coord_frame_contract.cpp")
CHIPLET2DBX = os.path.join("openroad", "chiplet2dbx.py")
EXCERPTS = os.path.join(DOCS_DIR, "formats", "_excerpts")

DIES = ("U1", "U2")

# The pad formats/03 transforms in its worked case, in die-local GDS um.
EXAMPLE_PAD = (Decimal("312.500"), Decimal("-845.000"))

# formats/03 quotes the contract's reason U1 takes Option 1, a pad pair at
# this pitch, as the specification's example. The contract must still say it,
# and it must still fall between the two options' minimum pitches.
SPEC_PAIR_PITCH = "79.93"
NEXT_OPTION = "cupillar_opt2"


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
    """The shortest text of a Decimal, without an exponent: 54.8103, 44."""
    return format(value.normalize(), "f")


def written_as_sum(text, total):
    """True when text is the exact sum written as contract section 1.5 states."""
    want = plain(total)
    return text == want or ("." not in want and text == want + ".0")


def literal(text):
    return "``{}``".format(text)


def point(x, y):
    return literal("({}, {})".format(plain(x), plain(y)))


def load_yaml(text, label):
    try:
        return yaml.load(text, Loader=DecimalLoader)
    except yaml.YAMLError as error:
        fail("{} does not parse: {}".format(label, error))


class Chiplet:
    def __init__(self, path, label):
        self.path = path
        self.label = label
        self.text = read_text(path)
        self.doc = load_yaml(self.text, label)
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

    def layer_values(self, stack_id, key):
        where = "{}: {} {}".format(self.label, stack_id, key)
        return [number(self.get(layer, key), where) for layer in self.layers(stack_id)]

    def stack_phrase(self, stack_id):
        """The stack's layers as prose, bottom first: 28 um ``CuPillar`` plus ..."""
        heights = self.layer_values(stack_id, "height")
        names = [self.get(layer, "name") for layer in self.layers(stack_id)]
        return " plus ".join(
            "{} um ``{}``".format(plain(h), name) for h, name in zip(heights, names)
        )

    def check_plane(self, plane):
        declared = self.value("interposer", "attachment_surface_z")
        if declared != plane:
            fail(
                "{} declares attachment_surface_z {}, the PDK key is {}".format(
                    self.label, plain(declared), plain(plane)
                )
            )

    def dbu(self):
        """The one database unit every technology of the file declares."""
        units = {
            number(tech.get("dbu", "0.001"), self.label + ": dbu")
            for tech in self.get(self.doc, "technologies").values()
        }
        if len(units) != 1:
            fail("{}: technologies disagree on dbu".format(self.label))
        return units.pop()


def read_plane():
    path = os.path.join(INTERPOSER, "libs.tech", "intm4tm2_stack.json")
    stack = json.loads(read_text(path), parse_float=Decimal)
    try:
        plane = number(stack["beol"]["attachment_surface_z_um"], "attachment_surface_z_um")
        tops = [m["zmax_um"] for m in stack["beol"]["metals"] if m["name"] == "TopMetal2"]
    except (KeyError, TypeError):
        fail("intm4tm2_stack.json has no beol.attachment_surface_z_um or metals")
    # formats/03 and tools/05 call the plane the top of TopMetal2.
    if [number(top, "TopMetal2 zmax_um") for top in tops] != [plane]:
        fail("intm4tm2_stack.json: the plane is no longer the top of TopMetal2")
    return plane


def interposer_stack_rows():
    """The metal stack top down: layer, GDS layer, z min, z max, thickness.

    Metals come from intm4tm2_stack.json. A via spans from the top of the
    metal below it to the bottom of the one above, as the technology's
    connectivity stacks pair them, so its z is derived rather than stored.
    """
    tech = os.path.join(INTERPOSER, "libs.tech", "klayout", "tech")
    stack = json.loads(
        read_text(os.path.join(INTERPOSER, "libs.tech", "intm4tm2_stack.json")),
        parse_float=Decimal,
    )
    try:
        metals = {
            m["name"]: (number(m["zmin_um"], m["name"]), number(m["zmax_um"], m["name"]))
            for m in stack["beol"]["metals"]
        }
    except (KeyError, TypeError):
        fail("intm4tm2_stack.json: beol.metals has no name, zmin_um and zmax_um")
    spans = dict(metals)
    for connection in re.findall(
        r"<connection>([^<]*)</connection>", read_text(os.path.join(tech, "intm4tm2.lyt"))
    ):
        parts = [part.strip() for part in connection.split(",")]
        if len(parts) != 3 or parts[0] not in metals or parts[2] not in metals:
            fail("intm4tm2.lyt: connection {!r} is not metal, via, metal of the "
                 "stack file's metals".format(connection))
        spans[parts[1]] = (metals[parts[0]][1], metals[parts[2]][0])
    gds = {}
    for line in read_text(os.path.join(tech, "intm4tm2_layers.txt")).splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[1] == "drawing":
            gds[fields[0]] = fields[2]
    rows = []
    for name, (low, high) in sorted(spans.items(), key=lambda item: -item[1][0]):
        if name not in gds:
            fail("intm4tm2_layers.txt has no drawing layer for {}".format(name))
        if not low < high:
            fail("intm4tm2 stack: {} spans {} to {}".format(name, low, high))
        cells = []
        for value in (low, high, high - low):
            fixed = value.quantize(Decimal("0.0001"))
            if fixed != value:
                fail("intm4tm2 stack: {} has more than four decimals".format(value))
            cells.append(str(fixed))
        rows.append([name, gds[name]] + cells)
    if [row[0] for row in rows if row[0] in metals] != sorted(
        metals, key=lambda name: -metals[name][0]
    ) or any(rows[i][2] != rows[i + 1][3] for i in range(len(rows) - 1)):
        fail("intm4tm2 stack: the metals and vias do not stack without a gap")
    return rows


def read_methods():
    """Each interconnect method's pitch and spacing, from the manifest."""
    doc = json.loads(read_text(os.path.join(INTERCONNECT, METHODS)), parse_float=Decimal)
    methods = {}
    for method_id, method in doc.get("methods", {}).items():
        rules = method.get("pitch_rules", {})
        try:
            methods[method_id] = {
                "pitch": number(rules["IXN_pitch"], method_id + " IXN_pitch"),
                "spacing": number(rules["IXN_spacing"], method_id + " IXN_spacing"),
            }
        except KeyError:
            fail("{}: {} has no IXN_pitch or IXN_spacing".format(METHODS, method_id))
    if not methods:
        fail("{}: no methods".format(METHODS))
    return methods


def die_values(prefix, chiplet, die, plane, methods, refdesign=False):
    """One die's z, method and stack, after checking the z is written as the sum.

    formats/03 quotes the specification's stack heights; flow/08 quotes the
    reference design's stack diameter and the method's pitch and spacing
    instead.
    """
    stack = str(chiplet.get(chiplet.component(die), "connection"))
    height = sum(chiplet.layer_values(stack, "height"))
    z_text = str(chiplet.get(chiplet.component(die), "position", "z"))
    if not written_as_sum(z_text, plane + height):
        fail(
            "{}: {} z {} is not written as the plane {} plus {} ({})".format(
                chiplet.label, die, z_text, plain(plane), stack, plain(height)
            )
        )
    name = prefix + die.lower()
    values = [
        (name + "-z", plain(plane + height)),
        (name + "-connection", literal(stack)),
        (name + "-stack-layers", chiplet.stack_phrase(stack)),
    ]
    if not refdesign:
        values.append((name + "-stack-height", plain(height)))
    else:
        diameters = set(chiplet.layer_values(stack, "diameter"))
        if len(diameters) != 1:
            fail("{}: {} layers differ in diameter".format(chiplet.label, stack))
        if stack not in methods:
            fail("{}: {} is not in the methods manifest".format(chiplet.label, stack))
        values += [
            (name + "-stack-diameter", plain(diameters.pop())),
            (name + "-pitch", plain(methods[stack]["pitch"])),
            (name + "-spacing", plain(methods[stack]["spacing"])),
        ]
    return values


def die_origin_offset(gds, cell_name, width, height, dbu):
    """How far the die's GDS origin sits from its bbox centre, in um, to the dbu."""
    if not os.path.isfile(gds):
        fail("die layout not found: {}".format(gds))
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(gds)
    cell = layout.cell(cell_name)
    if cell is None:
        fail("{}: top cell {} not found".format(gds, cell_name))
    box = cell.dbbox()

    def um(value):
        return Decimal(repr(value)).quantize(dbu)

    if (um(box.width()), um(box.height())) != (width.quantize(dbu), height.quantize(dbu)):
        fail("{}: bbox {} x {} differs from the .chiplet dimensions".format(
            gds, box.width(), box.height()))
    centre = box.center()
    return um(centre.x), um(centre.y)


def reference_design_values(plane, methods):
    ref = Chiplet(os.path.join(TOOLS, REF_DESIGN), "ADK-Tools/" + REF_DESIGN)
    ref.check_plane(plane)
    dbu = ref.dbu()
    values = [
        ("refdesign-interposer-" + key,
         plain(ref.value("interposer", "dimensions", key).quantize(dbu)))
        for key in ("width", "height", "thickness")
    ]
    # Quoted as written: formats/02 explains the float a bbox halving leaves.
    values.append(
        ("refdesign-interposer-x",
         literal(ref.get(ref.component("interposer"), "position", "x")))
    )
    for die in DIES:
        values += die_values("refdesign-", ref, die, plane, methods, refdesign=True)

    keys = ("width", "height", "thickness")
    dims = {die: tuple(ref.value(die, "dimensions", key) for key in keys) for die in DIES}
    if dims["U1"] != dims["U2"]:
        fail("{}: U1 and U2 no longer share dimensions".format(ref.label))
    values += [
        ("refdesign-die-" + key, plain(value.quantize(dbu)))
        for key, value in zip(keys, dims["U1"])
    ]

    # flow/08 states how far the shared die's GDS origin sits from its
    # outline centre, which is what chiplet2dbx shifts the outline by.
    layouts = {str(ref.get(ref.component(die), "layout")) for die in DIES}
    cells = {str(ref.get(ref.component(die), "top_cell")) for die in DIES}
    if len(layouts) != 1 or len(cells) != 1:
        fail("{}: U1 and U2 no longer share one layout".format(ref.label))
    gds = os.path.normpath(os.path.join(os.path.dirname(ref.path), layouts.pop()))
    dx, dy = die_origin_offset(gds, cells.pop(), dims["U1"][0], dims["U1"][1], dbu)
    if dx != 0:
        fail("{}: origin is off-centre in x too; flow/08 names y only".format(gds))
    if dy == 0:
        fail("{}: origin is centred; flow/08 says it is not".format(gds))
    values.append(("refdesign-die-origin-offset-y", plain(abs(dy))))
    return values


def spec_example_values(plane, methods):
    spec = Chiplet(os.path.join(SPEC, SPEC_EXAMPLE), "chiplet-spec/" + SPEC_EXAMPLE)
    spec.check_plane(plane)
    values = []
    for die in DIES:
        values += die_values("spec-", spec, die, plane, methods)

    # Contract 1.5's counterexample: the same U1 z printed to 17 significant
    # digits rather than as the shortest text that reads back as it.
    u1 = spec.component("U1")
    u1_stack = str(spec.get(u1, "connection"))
    u1_z = plane + sum(spec.layer_values(u1_stack, "height"))
    digits17 = "%.17g" % float(u1_z)
    if digits17 == plain(u1_z):
        fail("U1's z prints the same at 17 digits; formats/03 needs another "
             "counterexample")
    values.append(("spec-u1-z-17-digits", literal(digits17)))

    # The formats/03 worked case: one pad of U1 through mirror, rotation and
    # translation. The page walks a flip-chip die with no rotation, then turns
    # it by 90.
    if spec.get(u1, "orientation") != "flip_chip" or spec.value("U1", "rotation", "z") != 0:
        fail("{}: U1 is no longer an unrotated flip_chip die; rewrite the "
             "formats/03 worked case".format(spec.label))
    x = spec.value("U1", "position", "x")
    y = spec.value("U1", "position", "y")
    px, py = EXAMPLE_PAD
    shift = 2 * px
    pitch = methods[u1_stack]["pitch"]
    if shift % pitch == 0:
        fail("the face-up shift is a whole number of pitches; formats/03 says "
             "'more than'")
    values += [
        ("spec-u1-x", plain(x)),
        ("spec-u1-y", plain(y)),
        ("spec-u1-pad-local", point(px, py)),
        ("spec-u1-pad-local-mirrored", point(-px, py)),
        ("spec-u1-pad-local-x", plain(px)),
        ("spec-u1-pad-local-y", plain(py)),
        ("spec-u1-pad-flip", point(x - px, y + py)),
        ("spec-u1-pad-face-up", point(x + px, y + py)),
        ("spec-u1-pad-face-up-shift", plain(shift)),
        ("spec-u1-pad-face-up-pitches", str(math.floor(shift / pitch))),
        ("spec-u1-pitch", plain(pitch)),
        ("spec-u1-pad-flip-r90", point(x - py, y - px)),
    ]

    # The contract's reason for Option 1 over Option 2, quoted on formats/03.
    if SPEC_PAIR_PITCH + " um-pitch" not in read_text(os.path.join(SPEC, SPEC_CONTRACT)):
        fail("{} no longer gives the {} um pad pair".format(SPEC_CONTRACT, SPEC_PAIR_PITCH))
    if NEXT_OPTION not in methods:
        fail("{}: no {}".format(METHODS, NEXT_OPTION))
    next_pitch = methods[NEXT_OPTION]["pitch"]
    if not pitch <= Decimal(SPEC_PAIR_PITCH) < next_pitch:
        fail("the {} um pair no longer falls between {} and {}".format(
            SPEC_PAIR_PITCH, u1_stack, NEXT_OPTION))
    values += [
        ("spec-next-option", literal(NEXT_OPTION)),
        ("spec-next-option-pitch", plain(next_pitch)),
    ]
    return values


def excerpt_from_root(lines, label):
    """The document from its ``format_version`` root key on, without the header."""
    start = [n for n, line in enumerate(lines) if line.startswith("format_version:")]
    if len(start) != 1:
        fail("{}: no single format_version root key".format(label))
    return lines[start[0]:]


def component_excerpt(lines, comp_id, label):
    """The component's list item, dedented to its own column."""
    head = [n for n, line in enumerate(lines) if line.strip() == "- id: " + comp_id]
    if len(head) != 1:
        fail("{}: no single component {}".format(label, comp_id))
    indent = len(lines[head[0]]) - len(lines[head[0]].lstrip())
    item = [lines[head[0]]]
    for line in lines[head[0] + 1:]:
        if not line.strip() or len(line) - len(line.lstrip()) <= indent:
            break
        item.append(line)
    return [line[indent:] for line in item]


def contract_position_block(plane):
    """The contract's position example, the one YAML block of position and dimensions."""
    lines = read_text(os.path.join(SPEC, SPEC_CONTRACT)).splitlines()
    label = "chiplet-spec/" + SPEC_CONTRACT
    blocks, block = [], None
    for line in lines:
        if block is None and line.strip() == "```yaml":
            block = []
        elif block is not None and line.strip() == "```":
            blocks.append(block)
            block = None
        elif block is not None:
            block.append(line)
    found = []
    for block in blocks:
        doc = load_yaml("\n".join(block), label)
        if isinstance(doc, dict) and set(doc) == {"position", "dimensions"}:
            found.append((block, doc))
    if len(found) != 1:
        fail("{}: no single position example".format(label))
    block, doc = found[0]
    pos, dims = doc["position"], doc["dimensions"]
    x, y, z = (number(pos[k], label) for k in ("x", "y", "z"))
    w, h = (number(dims[k], label) for k in ("width", "height"))
    values = [
        ("contract-example-corner", point(x - w / 2, y - h / 2)),
        ("contract-example-stack-height", plain(z - plane)),
    ]
    return block, values


def studio_demo_values():
    """The positions Studio's wire-bond demo round trip asserts."""
    text = read_text(os.path.join(STUDIO, STUDIO_TEST))
    found = {}
    for obj, axis, value, tol in re.findall(
        r"EXPECT_NEAR\((\w+)->position\(\)\.([xyz]),\s*([-0-9.]+),\s*([-0-9.e]+)\)", text
    ):
        found[(obj, axis)] = (Decimal(value), tol)
    objects = ("u1", "u2", "interposer")
    for obj in objects:
        for axis in "xyz":
            if (obj, axis) not in found:
                fail("{}: no EXPECT_NEAR for {}.{}".format(STUDIO_TEST, obj, axis))
    xy_tolerances = {found[(obj, axis)][1] for obj in objects for axis in "xy"}
    z_tolerances = {found[(obj, "z")][1] for obj in ("u1", "u2")}
    if len(xy_tolerances) != 1 or len(z_tolerances) != 1:
        fail("{}: the tolerances differ between components".format(STUDIO_TEST))
    values = [("studio-demo-xy-tol", xy_tolerances.pop())]
    for obj in objects:
        xy = point(found[(obj, "x")][0], found[(obj, "y")][0])
        values.append(("studio-demo-{}-xy".format(obj), xy))
        values.append(("studio-demo-{}-z".format(obj), plain(found[(obj, "z")][0])))
    values.append(("studio-demo-die-z-tol", z_tolerances.pop()))
    return values


def chiplet2dbx_values():
    """The tolerance chiplet2dbx holds a die's z to."""
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


def write_excerpt(name, lines):
    write_text(os.path.join(EXCERPTS, name), "\n".join(lines) + "\n")


def main():
    require_submodule(INTERPOSER, "OpenIntM4TM2")
    require_submodule(INTERCONNECT, "IHP-Interconnect-IntM4TM2")
    require_submodule(SPEC, "chiplet-spec")
    require_submodule(TOOLS, "ADK-Tools")
    require_submodule(STUDIO, "chiplet-studio")
    require_submodule(ADK, "IHP-Open-ADK")

    plane = read_plane()
    methods = read_methods()
    block, contract_values = contract_position_block(plane)

    values = [("interposer-attachment-z", plain(plane))]
    values += contract_values
    values += spec_example_values(plane, methods)
    values += reference_design_values(plane, methods)
    values += studio_demo_values()
    values += chiplet2dbx_values()

    text = GENERATED_BANNER.format(script=os.path.basename(__file__)) + "\n"
    for name, value in values:
        text += ".. |{}| replace:: {}\n".format(name, value)
    write_text(os.path.join(DOCS_DIR, "_frame_values.inc"), text)

    label = "chiplet-spec/" + SPEC_EXAMPLE
    example = read_text(os.path.join(SPEC, SPEC_EXAMPLE)).splitlines()
    write_excerpt("spec_example.yaml", excerpt_from_root(example, label))
    write_excerpt("spec_example_u1.yaml", component_excerpt(example, "U1", label))
    write_excerpt("contract_position.yaml", block)

    write_csv(
        os.path.join(DOCS_DIR, "formats", "tables", "io_class_interface_types.csv"),
        io_class_rows(),
    )
    write_csv(
        os.path.join(DOCS_DIR, "tools", "tables", "interposer_stack.csv"),
        interposer_stack_rows(),
    )


if __name__ == "__main__":
    main()
