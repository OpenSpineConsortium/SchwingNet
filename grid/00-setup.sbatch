#!/bin/bash
#SBATCH --job-name=sn_setup
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.out
# The pixi environments for every SchwingNet job on the grid (issue #53), made once per pixi.lock:
#   1. pixi 0.81.0 into the lab volume's tools/pixi-0.81.0/bin, its release asset checked against
#      the sha256 this repository measured (.claude/hooks/beethoven-qa-session-start.sh holds the
#      same pair); a folder of SchwingNet's own, so a pixi of another project's in ~/.pixi is never
#      replaced;
#   2. the container (grid/box.sh): a sandbox built from docker://node:22-bookworm on the lab volume,
#      unless it is there, since the nodes' glibc 2.17 cannot run what pixi.lock holds;
#   3. .pixi on the lab volume, a link from the checkout, so the environments and pixi's cache sit
#      on one file system (hard links, not copies) and the home folder's quota is not spent;
#   4. the four environments installed inside the container and each imported once; only when all
#      four import is .pixi/SETUP.sha256 written, the sha256 of the pixi.lock they came from, which
#      the gate reads to know the environments are ready.
# The report is logs/00-setup-STAGE-REPORT.md. Nothing is deleted but this job's own scratch.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
OWN=$LAB/go2432
SANDBOX=${SCHWINGNET_SANDBOX:-$OWN/containers/schwingnet-bookworm}
IMAGE=${SCHWINGNET_IMAGE:-docker://node:22-bookworm}
PIXI_VERSION=0.81.0
PIXI_BIN=${SCHWINGNET_PIXI_BIN:-$OWN/tools/pixi-$PIXI_VERSION/bin}
PIXI_SHA256=248510f5f75460a2ae4ec62d761e15c0191dc35db3b1da6f82d9f17c6017051d
ENVS="default train-cpu train-gpu telemetry"
# Absolute, since the job changes to the checkout before it installs the environments.
REPORT=$REPO/grid/logs/00-setup-STAGE-REPORT.md
cd "$REPO" || exit 2
mkdir -p grid/logs
cd grid || exit 2
export PIXI_CACHE_DIR=$OWN/.cache/pixi APPTAINER_CACHEDIR=$OWN/.cache/apptainer
scratch=$OWN/tmp/sn_setup_${SLURM_JOB_ID:-$$}
mkdir -p "$PIXI_CACHE_DIR" "$APPTAINER_CACHEDIR" "$scratch" "$(dirname "$SANDBOX")"
trap 'rm -rf "$scratch"' EXIT
export APPTAINER_TMPDIR=$scratch
report() { echo "- $*" | tee -a "$REPORT"; }
fail() { report "FAILED: $*"; echo "SN_SETUP_RC=1"; exit 1; }
echo "# Setup of the pixi environments: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname)" > "$REPORT"
report "commit $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null); node glibc $(ldd --version 2>/dev/null | head -n 1 | awk '{ print $NF }')"
report "home: $(df -h "$HOME" 2>/dev/null | tail -n 1 | awk '{ print $4 " free of " $2 }'); lab volume: $(df -h "$LAB" 2>/dev/null | tail -n 1 | awk '{ print $4 " free of " $2 }')"

# 1. pixi
if "$PIXI_BIN/pixi" --version 2>/dev/null | grep -q "$PIXI_VERSION"; then
  report "pixi $PIXI_VERSION: already in $PIXI_BIN"
else
  mkdir -p "$PIXI_BIN"
  url="https://github.com/prefix-dev/pixi/releases/download/v${PIXI_VERSION}/pixi-x86_64-unknown-linux-musl"
  curl -fsSL -o "$scratch/pixi" "$url" || fail "could not fetch pixi $PIXI_VERSION from $url"
  echo "$PIXI_SHA256  $scratch/pixi" | sha256sum --status -c - || fail "the pixi fetched is not the one this repository measured (sha256 differs); nothing installed"
  chmod 755 "$scratch/pixi" && mv "$scratch/pixi" "$PIXI_BIN/pixi" || fail "could not place pixi in $PIXI_BIN"
  report "pixi $PIXI_VERSION: fetched, sha256 matched, placed in $PIXI_BIN"
fi

# 2. the container
if [ -x "$SANDBOX/bin/bash" ]; then
  report "container: $SANDBOX is there"
else
  APPTAINER=$(command -v apptainer 2>/dev/null)
  if [ -z "$APPTAINER" ]; then
    for init in /etc/profile.d/lmod.sh /etc/profile.d/modules.sh /usr/share/lmod/lmod/init/bash; do
      # shellcheck disable=SC1090
      [ -f "$init" ] && source "$init" >/dev/null 2>&1 && module load apptainer/1.2.2 >/dev/null 2>&1 && break
    done
    APPTAINER=$(command -v apptainer 2>/dev/null || echo /wsu/el7/gnu7/apptainer/1.2.2/bin/apptainer)
  fi
  [ -x "$APPTAINER" ] || fail "no apptainer on this node (module apptainer/1.2.2)"
  rm -rf "$SANDBOX.part"
  started=$(date +%s)
  "$APPTAINER" build --sandbox "$SANDBOX.part" "$IMAGE" > "$scratch/build.log" 2>&1 \
    || { tail -n 5 "$scratch/build.log" | sed 's/^/  /' >> "$REPORT"; fail "apptainer build $IMAGE"; }
  mv "$SANDBOX.part" "$SANDBOX" || fail "could not move the sandbox into place"
  report "container: built $SANDBOX from $IMAGE in $(( $(date +%s) - started )) s, $(du -sh "$SANDBOX" 2>/dev/null | cut -f1)"
fi
report "container glibc: $(bash "$REPO/grid/box.sh" ldd --version 2>/dev/null | head -n 1 | awk '{ print $NF }')"

# 3. .pixi on the lab volume
if [ ! -e "$REPO/.pixi" ] && [ ! -L "$REPO/.pixi" ]; then
  mkdir -p "$OWN/pixi/SchwingNet" && ln -s "$OWN/pixi/SchwingNet" "$REPO/.pixi" || fail "could not link .pixi to the lab volume"
  report ".pixi: linked to $OWN/pixi/SchwingNet"
else
  report ".pixi: $(readlink -f "$REPO/.pixi")"
fi

# 4. the environments, each installed and imported inside the container
declare -A IMPORTS=(
  [default]="import pydantic, beartype, icontract"
  [train-cpu]="import torch, PIL, numpy, pydicom, pydantic"
  [train-gpu]="import torch, onnxruntime, pydantic; print('torch', torch.__version__, 'cuda build', torch.version.cuda)"
  [telemetry]="import wandb; print('wandb', wandb.__version__)"
)
rm -f "$REPO/.pixi/SETUP.sha256"
ok=1
cd "$REPO" || exit 2
# the lock the installs read, hashed before they start: the gate fast-forwards this checkout before
# every word, so a lock that changed while they ran must not be recorded as the one they built
lock=$(sha256sum < "$REPO/pixi.lock" | cut -d' ' -f1)
for env in $ENVS; do
  started=$(date +%s)
  if bash grid/box.sh pixi install --locked -e "$env" > "$scratch/install-$env.log" 2>&1; then
    said=$(bash grid/box.sh "$REPO/.pixi/envs/$env/bin/python" -c "${IMPORTS[$env]}" 2>&1)
    if [ $? = 0 ]; then
      report "$env: installed in $(( $(date +%s) - started )) s, imports ${said:+($said)}"
    else
      report "$env: installed, but the imports failed: $(echo "$said" | tail -n 1)"; ok=0
    fi
  else
    report "$env: pixi install refused: $(grep -v '^ *$' "$scratch/install-$env.log" | tail -n 2 | tr '\n' ' ')"; ok=0
  fi
done
[ "$ok" = 1 ] || fail "an environment is not ready (above); the gate submits nothing that needs one"
[ "$(sha256sum < "$REPO/pixi.lock" | cut -d' ' -f1)" = "$lock" ] || fail "pixi.lock changed while the environments were installed; the next 'start' makes them again from the new lock"
echo "$lock" > "$REPO/.pixi/SETUP.sha256"
report "ready: .pixi/SETUP.sha256 = $(cat "$REPO/.pixi/SETUP.sha256")"
echo "SN_SETUP_RC=0"
