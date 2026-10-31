#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# The QA loop with a transformer encoder (docs/research/qa-loop-transformer/PREREG.md): grid/qaloop.sbatch
# at the gate's commit, run as the kind qaloop_tx, so every link starts flows/launch.py qaloop_tx from
# the code's copy, its run is held to that PREREG, and the loop's own frozen PREREG is never edited.
# Queued by grid/gate.sh's word `qaloop <plan>` for a plan
# QALOOP_TX_PLANS names, with the same variables as grid/qaloop.sbatch; the job script is read from
# the commit the gate sent, never from the checkout, which may move under the chain.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
COMMIT=${QALOOP_COMMIT:-}
fail() { echo "qaloop_tx: $*; nothing ran"; echo "SN_QALOOP_RC=64"; exit 64; }
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]] || fail "QALOOP_COMMIT is the full commit the gate sent"
script=/dev/shm/${USER:-$(id -un)}_qaloop_tx_${SLURM_JOB_ID:-$$}.sbatch
git -C "$REPO" show "$COMMIT:grid/qaloop.sbatch" > "$script" 2>/dev/null \
  || { rm -f "$script"; fail "grid/qaloop.sbatch cannot be read at ${COMMIT:0:7}"; }
trap ':' TERM
QALOOP_KIND=qaloop_tx bash "$script" &
child=$!
while :; do
  wait "$child"
  rc=$?
  kill -0 "$child" 2>/dev/null || break
done
rm -f "$script"
exit "$rc"
