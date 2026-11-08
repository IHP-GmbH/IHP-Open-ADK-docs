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
is what the README itself tells a reader to fill in. A release tag (``v``
and a digit) of any other shape is an error; local tags such as save points
are ignored. The README's "(see below)" pointers are dropped, since they point
nowhere here; any other "(see ...)" is an error rather than a dangling pointer.

Writes, under docs/install/:

- ``_recipe/clone.sh``: the block up to the staging checks, for the release
  page, which builds later;
- ``_recipe/build.sh``: the block up to reading the image ID, without the run
  line, which each page states in its own context;
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
RELEASE_TAG = re.compile(r"v\d{4}\.\d{2}")
INSTALL_DIR = os.path.join(DOCS_DIR, "install")


def release_tag():
    """The release tag ADK-Tools is pinned at, or the placeholder if untagged."""
    tags = release_tags(TOOLS)
    releases = [tag for tag in tags if RELEASE_TAG.fullmatch(tag)]
    if len(releases) > 1:
        fail("ADK-Tools HEAD carries several release tags: {}".format(", ".join(releases)))
    if not releases and tags:
        fail("ADK-Tools HEAD is tagged {} but not as vYYYY.MM".format(", ".join(tags)))
    return releases[0] if releases else PLACEHOLDER


def build_block(readme):
    """The text of the first bash block of the README's Build section."""
    section = re.search(r"^### Build\n(.*?)(?=^#{2,3} |\Z)", readme, re.MULTILINE | re.DOTALL)
    if not section:
        fail("ADK-Tools README has no '### Build' section")
    block = re.search(r"^```bash\n(.*?)^```", section.group(1), re.MULTILINE | re.DOTALL)
    if not block:
        fail("the Build section of the ADK-Tools README has no bash block")
    return block.group(1)


def index_of(lines, prefix):
    """The index of the one line that starts with prefix."""
    found = [n for n, line in enumerate(lines) if line.startswith(prefix)]
    if len(found) != 1:
        fail("expected one line starting {!r} in the README build block, found {}".format(
            prefix, len(found)))
    return found[0]


def main():
    require_submodule(TOOLS, "src/ADK-Tools")
    tag = release_tag()
    text = build_block(read_text(os.path.join(TOOLS, "README.md")))
    text = text.replace(" (see below)", "").replace(PLACEHOLDER, tag)
    if "(see " in text:
        fail("the README build block points at another README section: {}".format(
            re.search(r"\(see [^)]*\)?", text).group(0)))
    lines = text.splitlines(keepends=True)

    checks = index_of(lines, "./stage-sources.sh --check")
    image = index_of(lines, "export ADK_TOOLS_IMAGE=")
    if image < checks:
        fail("the README build block reads the image ID before the staging checks")
    write_text(os.path.join(INSTALL_DIR, "_recipe", "clone.sh"), "".join(lines[: checks + 1]))
    write_text(os.path.join(INSTALL_DIR, "_recipe", "build.sh"), "".join(lines[: image + 1]))
    write_text(
        os.path.join(INSTALL_DIR, "_release_tag.inc"),
        GENERATED_BANNER.format(script="gen_build_recipe.py")
        + "\n.. |release-tag| replace:: ``{}``\n".format(tag),
    )


if __name__ == "__main__":
    main()
