#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Copy the image build recipe out of the pinned ADK-Tools README.

The README's Build section is the one place the build sequence is maintained.
The install pages include this copy of it instead of retyping it, so a changed
step in ADK-Tools shows up as a diff here rather than as a page that quietly
stops matching the build.

Two things change on the way. The README writes the release tag as
``vYYYY.MM``; when ADK-Tools is pinned at a tag, that tag replaces the
placeholder, and otherwise the placeholder stays. Cross-references to other
README sections ("(see below)") are dropped, since they point nowhere here.

Writes docs/install/_generated/build_recipe.sh, included with literalinclude,
and docs/install/_generated/release_tag.inc, which defines |release-tag|.
"""

import os
import re
import subprocess

from _common import (
    DOCS_DIR,
    GENERATED_BANNER,
    TOOLS,
    fail,
    read_text,
    require_submodule,
    write_text,
)

PLACEHOLDER = "vYYYY.MM"
OUT_DIR = os.path.join(DOCS_DIR, "install", "_generated")


def release_tag():
    """The tag ADK-Tools is pinned at, or the placeholder if it is not tagged."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            cwd=TOOLS,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return PLACEHOLDER
    tag = result.stdout.strip()
    return tag if result.returncode == 0 and re.fullmatch(r"v\d{4}\.\d{2}", tag) else PLACEHOLDER


def build_block(readme):
    """The first bash block of the README's Build section."""
    section = re.search(r"^### Build\n(.*?)(?=^#{2,3} )", readme, re.MULTILINE | re.DOTALL)
    if not section:
        fail("ADK-Tools README has no '### Build' section")
    block = re.search(r"^```bash\n(.*?)^```", section.group(1), re.MULTILINE | re.DOTALL)
    if not block:
        fail("the Build section of the ADK-Tools README has no bash block")
    return block.group(1)


def main():
    require_submodule(TOOLS, "src/ADK-Tools")
    recipe = build_block(read_text(os.path.join(TOOLS, "README.md")))
    tag = release_tag()
    recipe = recipe.replace(" (see below)", "").replace(PLACEHOLDER, tag)
    write_text(os.path.join(OUT_DIR, "build_recipe.sh"), recipe)
    write_text(
        os.path.join(OUT_DIR, "release_tag.inc"),
        GENERATED_BANNER.format(script="gen_build_recipe.py")
        + "\n.. |release-tag| replace:: ``{}``\n".format(tag),
    )


if __name__ == "__main__":
    main()
