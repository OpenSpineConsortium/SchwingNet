#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# The auto-anatomist's second screen (docs/research/autoanatomist-screen2/PREREG.md): the first
# screen's job script, grid/autoanatomist.sbatch, run as the kind autoanatomist2, so every part
# starts flows/launch.py autoanatomist2 from the code's copy and its runs are held to the second
# screen's frozen PREREG. The registry gives every kind a job script of its own (flows/registry.txt),
# and grid/gate.sh queues the second screen's plans (AUTOANATOMIST2_PLANS) with this one.
#
# This script runs the first screen's script as it stands at the commit the gate sent
# (AUTOANATOMIST_COMMIT), read from git and not from the checkout, which may have moved since the
# send; that script then copies the code at the same commit, as it does for the first screen.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
COMMIT=${AUTOANATOMIST_COMMIT:-}
fail() { echo "autoanatomist2: $*; nothing ran"; echo "SN_AUTOANATOMIST_RC=64"; exit 64; }
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]] || fail "AUTOANATOMIST_COMMIT is the full commit the gate sent"
script=/dev/shm/${USER:-$(id -un)}_autoanatomist2_${SLURM_JOB_ID:-$$}_${SLURM_ARRAY_TASK_ID:-0}.sbatch
git -C "$REPO" show "$COMMIT:grid/autoanatomist.sbatch" > "$script" 2>/dev/null \
  || { rm -f "$script"; fail "grid/autoanatomist.sbatch cannot be read at ${COMMIT:0:7}"; }
# Slurm's TERM reaches every process of the job, the first screen's script among them, whose own
# trap passes it on to the launcher; this script only waits on, through the TERM, for that script to
# end, and then exits with its code.
trap ':' TERM
AUTOANATOMIST_KIND=autoanatomist2 bash "$script" &
child=$!
while :; do
  wait "$child"
  rc=$?
  kill -0 "$child" 2>/dev/null || break
done
rm -f "$script"
exit "$rc"
