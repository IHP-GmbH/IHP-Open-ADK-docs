# the Quickstart's exports, again in a fresh shell
export ADK_TOOLS_ROOT=~/adk-tools ADK_EXAMPLES_ROOT=~/adk-examples
export STAGE_DIE_VIEWS_DIR="$ADK_EXAMPLES_ROOT/die-views"
cd "$ADK_TOOLS_ROOT"
git fetch --tags
git checkout v2026.11.1    # a release clone sits on a tag, so there is nothing to pull
git submodule update --init --recursive
./stage-sources.sh --check && ./stage-die-views.sh --check
# realise the Nix packages at the new tag (step from the README Build section)
nix build .#openroad .#librelane .#librelane-python .#sg13g2-pdk \
    .#cosim-devshell .#mixsim-ngspice .#mixsim-iverilog .#sg13g2-osdi \
    .#gtkwave .#gaw .#xschem .#vams-devshell
./build.sh    # cached stages rebuild only what changed
