# the clone lives at ADK_TOOLS_ROOT, outside ADK_WORK; the
# die-views/ folder of the adk-examples checkout at ADK_EXAMPLES_ROOT has to
# match die-views.sha256
export ADK_TOOLS_ROOT=~/adk-tools ADK_EXAMPLES_ROOT=~/adk-examples
export STAGE_DIE_VIEWS_DIR="$ADK_EXAMPLES_ROOT/die-views"
git clone --branch v2026.11.1 --recurse-submodules https://github.com/IHP-GmbH/ADK-Tools.git \
    "$ADK_TOOLS_ROOT"
cd "$ADK_TOOLS_ROOT"
./stage-sources.sh --check && ./stage-die-views.sh --check
nix build .#openroad .#librelane .#librelane-python .#sg13g2-pdk \
    .#cosim-devshell .#mixsim-ngspice .#mixsim-iverilog .#sg13g2-osdi \
    .#gtkwave .#gaw .#xschem .#vams-devshell
# ~1 h the first time, cached afterwards; JOBS=N overrides the default 8
# parallel compile jobs
./build.sh

# run.sh takes the image by its ID (sha256:<64 hex>), never a tag, and has no
# default: read the ID of the image you just built once
export ADK_TOOLS_IMAGE="$(docker image inspect --format '{{.Id}}' adk-tools:dev)"
