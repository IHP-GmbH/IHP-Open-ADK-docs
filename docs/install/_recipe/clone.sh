# the clone lives at ADK_TOOLS_ROOT, outside ADK_WORK; the
# adk-examples checkout at ADK_EXAMPLES_ROOT is at the same v2026.11 tag
export ADK_TOOLS_ROOT=~/adk-tools ADK_EXAMPLES_ROOT=~/adk-examples
export STAGE_DIE_VIEWS_DIR="$ADK_EXAMPLES_ROOT/die-views"
git clone --branch v2026.11 --recurse-submodules https://github.com/IHP-GmbH/ADK-Tools.git \
    "$ADK_TOOLS_ROOT"
cd "$ADK_TOOLS_ROOT"
./stage-sources.sh --check && ./stage-die-views.sh --check
