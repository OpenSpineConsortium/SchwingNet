#!/bin/bash
# Run one command inside SchwingNet's container on a WSU compute node (issue #53):
#   bash grid/box.sh <command> [<argument> ...]
# The grid's nodes run CentOS 7, whose glibc is 2.17, and pixi.lock is solved for glibc 2.34
# (pixi.toml's one platform), so the pixi environments run inside an Apptainer sandbox with a
# newer userland: docker://node:22-bookworm (glibc 2.36), the image spine-program's
# grid-apptainer-module-works note measured building unprivileged on a compute node with the
# module apptainer/1.2.2. grid/00-setup.sbatch builds the sandbox once, on the lab volume.
# Bound: the home folder (Apptainer's default), the lab volume and /dev/shm; on a node Slurm gave a
# GPU, --nv brings the host's driver in. pixi (~/.pixi/bin) leads the container's PATH, and CPU
# nodes tell pixi the CUDA the lock was solved for, since the platform asks for one.
# Inside the container already, or with SCHWINGNET_NATIVE=1, the command runs as it is.
set -uo pipefail
if [ -n "${APPTAINER_CONTAINER:-}${SINGULARITY_CONTAINER:-}" ] || [ "${SCHWINGNET_NATIVE:-}" = 1 ]; then
  exec "$@"
fi
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
SANDBOX=${SCHWINGNET_SANDBOX:-$LAB/go2432/containers/schwingnet-bookworm}
[ -x "$SANDBOX/bin/bash" ] || { echo "box: no sandbox at $SANDBOX; grid/00-setup.sbatch builds it (gate word start)" >&2; exit 69; }
apptainer_bin() {
  command -v apptainer 2>/dev/null && return 0
  local init
  for init in /etc/profile.d/lmod.sh /etc/profile.d/modules.sh /usr/share/lmod/lmod/init/bash; do
    [ -f "$init" ] || continue
    # shellcheck disable=SC1090
    source "$init" >/dev/null 2>&1 && module load apptainer/1.2.2 >/dev/null 2>&1 && break
  done
  command -v apptainer 2>/dev/null && return 0
  [ -x /wsu/el7/gnu7/apptainer/1.2.2/bin/apptainer ] && echo /wsu/el7/gnu7/apptainer/1.2.2/bin/apptainer
}
APPTAINER=$(apptainer_bin) || true
[ -n "$APPTAINER" ] || { echo "box: no apptainer on this node (module apptainer/1.2.2)" >&2; exit 69; }
opts=(-B "$LAB" -B /dev/shm --pwd "$PWD")
if [ -n "${CUDA_VISIBLE_DEVICES:-}${SLURM_JOB_GPUS:-}" ]; then
  opts+=(--nv)
else
  export CONDA_OVERRIDE_CUDA=${CONDA_OVERRIDE_CUDA:-12.4}
fi
export APPTAINERENV_PREPEND_PATH="$HOME/.pixi/bin"
export PIXI_CACHE_DIR=${PIXI_CACHE_DIR:-$LAB/go2432/.cache/pixi}
exec "$APPTAINER" exec "${opts[@]}" "$SANDBOX" "$@"
