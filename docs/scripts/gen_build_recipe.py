#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Copy the image build recipe out of the pinned ADK-Tools README.

The README's Build section is the one place the build sequence is maintained.
The install pages include these copies of it instead of retyping it, so a
changed step in ADK-Tools shows up as a diff here rather than as a page that
quietly stops matching the build.

The README writes the release tag as ``vYYYY.MM``. When ADK-Tools is pinned
exactly at a release tag, that tag replaces the placeholder; when it is pinned
at an untagged commit, as on a development branch, the placeholder stays, which
is what the README itself tells a reader to fill in. A point release of a
month, ``vYYYY.MM.N`` (v2026.11.1), is a release tag too. A release tag (``v``
and a digit) of any other shape is an error; local tags (not release tags)
are ignored. The README's "(see below)" pointers are dropped, since they point
nowhere here; any other "(see ...)" is an error rather than a dangling pointer.

Writes, under docs/install/:

- ``_recipe/clone.sh``: the block up to the staging checks, for the release
  page, which builds later;
- ``_recipe/build.sh``: the block up to reading the image ID, without the run
  line, which each page states in its own context;
- ``_recipe/update.sh``: the block of the README's "Updating an existing
  clone" section, for the update recipe on the ADK-Tools page, with the Build
  block's ``nix build`` command spliced in before its ``./build.sh``. The
  README asks for the Nix packages to be realised at every commit built, but
  its update block leaves the step out, and a reader runs a block top to
  bottom;
- ``_release_tag.inc``: defines |release-tag|.
"""

import os
import re

from _common import (
    DOCS_DIR,
    GENERATED_BANNER,
    TOOLS,
    fail,
    read_text,
    release_tags,
    require_submodule,
    write_text,
)

PLACEHOLDER = "vYYYY.MM"
RELEASE_TAG = re.compile(r"v\d{4}\.\d{2}(\.\d+)?")
INSTALL_DIR = os.path.join(DOCS_DIR, "install")


def release_tag():
    """The release tag ADK-Tools is pinned at, or the placeholder if untagged."""
    tags = release_tags(TOOLS)
    releases = [tag for tag in tags if RELEASE_TAG.fullmatch(tag)]
    if len(releases) > 1:
        fail("ADK-Tools HEAD carries several release tags: {}".format(", ".join(releases)))
    if not releases and tags:
        fail("ADK-Tools HEAD is tagged {} but not as vYYYY.MM or vYYYY.MM.N".format(", ".join(tags)))
    return releases[0] if releases else PLACEHOLDER


def section_block(readme, heading):
    """The text of the first bash block of the README section under heading,
    a whole heading line such as "### Build"."""
    section = re.search(
        r"^{}\n(.*?)(?=^#{{2,3}} |\Z)".format(re.escape(heading)),
        readme, re.MULTILINE | re.DOTALL)
    if not section:
        fail("ADK-Tools README has no {!r} section".format(heading))
    block = re.search(r"^```bash\n(.*?)^```", section.group(1), re.MULTILINE | re.DOTALL)
    if not block:
        fail("the {!r} section of the ADK-Tools README has no bash block".format(heading))
    return block.group(1)


def resolve(text, tag):
    """The block with the release tag filled in and its pointers dropped."""
    text = text.replace(" (see below)", "").replace(PLACEHOLDER, tag)
    if "(see " in text:
        fail("a README block points at another README section: {}".format(
            re.search(r"\(see [^)]*\)?", text).group(0)))
    return text


def index_of(lines, prefix, block="build"):
    """The index of the one line that starts with prefix."""
    found = [n for n, line in enumerate(lines) if line.startswith(prefix)]
    if len(found) != 1:
        fail("expected one line starting {!r} in the README {} block, found {}".format(
            prefix, block, len(found)))
    return found[0]


def command_at(lines, start):
    """The command starting at lines[start], with its continuation lines."""
    end = start
    while lines[end].rstrip("\n").endswith("\\"):
        end += 1
        if end == len(lines):
            fail("the README build block ends inside a continued command")
    return lines[start: end + 1]


def update_recipe(build_lines, update_block):
    """The update block with the build block's nix build command before its
    ./build.sh line."""
    nix = command_at(build_lines, index_of(build_lines, "nix build "))
    lines = update_block.splitlines(keepends=True)
    if any(line.startswith("nix build") for line in lines):
        fail("the README update block now realises the Nix packages itself; "
             "stop splicing the build block's nix build into it")
    build = index_of(lines, "./build.sh", "update")
    note = "# realise the Nix packages at the new tag (step from the README Build section)\n"
    return "".join(lines[:build] + [note] + nix + lines[build:])


def main():
    require_submodule(TOOLS, "src/ADK-Tools")
    tag = release_tag()
    readme = read_text(os.path.join(TOOLS, "README.md"))
    lines = resolve(section_block(readme, "### Build"), tag).splitlines(keepends=True)

    checks = index_of(lines, "./stage-sources.sh --check")
    image = index_of(lines, "export ADK_TOOLS_IMAGE=")
    if image < checks:
        fail("the README build block reads the image ID before the staging checks")
    write_text(os.path.join(INSTALL_DIR, "_recipe", "clone.sh"), "".join(lines[: checks + 1]))
    write_text(os.path.join(INSTALL_DIR, "_recipe", "build.sh"), "".join(lines[: image + 1]))
    write_text(
        os.path.join(INSTALL_DIR, "_recipe", "update.sh"),
        update_recipe(lines, resolve(section_block(readme, "## Updating an existing clone"), tag)),
    )
    write_text(
        os.path.join(INSTALL_DIR, "_release_tag.inc"),
        GENERATED_BANNER.format(script="gen_build_recipe.py")
        + "\n.. |release-tag| replace:: ``{}``\n".format(tag),
    )


if __name__ == "__main__":
    main()
