#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
# The owner's gold and silver tiers, case by case, over every SPINEPS mask the transitional census
# lists (the owner's sort of 2026-10-27: gold when one study shows the whole spine, C2 to the
# sacrum, so the count from C2 can be checked, silver when it shows less; 1 to 4 by pairing with a
# real X-ray and a person's annotation). grid/gate.sh's word `census tiers` queues it as one job of
# the batch class. tools/corpus_tiers.py census reads each mask as the bordercall corpus does (the
# centroid file's C2, at most one body above it, no gap a missed body would leave) and adds the
# sacrum; annotation and pairing come from the committed data/corpus-tiers/sources.json.
#
# Nothing is segmented, nothing trains and no mask is written: the masks are only read. The
# per-case file stays under $OUT on the lab volume; the report, counts by collection and tier, is
# what the gate prints. The checkout holds still while the job lasts (grid/logs/HOLD), and a job
# whose checkout moved anyway is failed, since its report names the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
TIERS=${TIERS:-$RS/ruleclass/tiers}
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
export SSN
STAGE=${STAGE:-}
case "$STAGE" in tiers) ;; *) echo "census: STAGE is tiers"; echo "SN_CENSUS_RC=64"; exit 64 ;; esac
CPUS=${SLURM_CPUS_PER_TASK:-4}
REPORT=$REPO/grid/logs/CENSUS-$STAGE.md
OUT=${CENSUS_ROOT:-$RS/corpus_tiers}/$STAGE
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  local rc=$1 ended_at
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ]; then
    report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the job, so its counts may come from newer code than this report names; they are not used"
    [ "$rc" != 0 ] || rc=3
  fi
  report "exit $rc at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_CENSUS_RC=$rc"
  exit "$rc"
}
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# census $STAGE: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
{ flock -w 60 9 2>/dev/null || :; echo "${SLURM_JOB_ID:-$$} $started_at" >> "$HOLD"; } 9>>"$HOLD.lock"
unhold() { { flock -w 60 9 2>/dev/null || :; [ ! -f "$HOLD" ] || { awk -v me="${SLURM_JOB_ID:-$$}" '$1 != me' "$HOLD" > "$HOLD.tmp"; if [ -s "$HOLD.tmp" ]; then mv -f "$HOLD.tmp" "$HOLD"; else rm -f "$HOLD" "$HOLD.tmp"; fi; }; } 9>>"$HOLD.lock"; }
trap unhold EXIT
trap 'exit 143' TERM

# The interpreter: the first that reads a mask (numpy, scipy and nibabel).
PY=""
for cand in "${CENSUS_PYTHON:-}" "$HOME/mambaforge/envs/spineps/bin/python" "$RS/envs/spineps212/bin/python" \
            "$REPO/.pixi/envs/train-cpu/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy, scipy, nibabel" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter with numpy, scipy and nibabel (tried the SPINEPS environments and train-cpu)"; finish 2; }
report "interpreter: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"
[ -d "$TIERS" ] || { report "FAILED: no census tier lists at $TIERS"; finish 2; }
[ -f "$SSN/tools/spineps_ids.py" ] || report "NOTE: no $SSN/tools/spineps_ids.py; every raw-id mask is read as partial, set aside unrelabelled"
[ -f data/corpus-tiers/sources.json ] || { report "FAILED: no data/corpus-tiers/sources.json at this commit"; finish 2; }

if ! "$PY" tools/corpus_tiers.py census --tiers "$TIERS" --out "$OUT" --workers "$CPUS" > "$OUT/census.txt" 2>&1; then
  report "FAILED at census: $(tail -n 3 "$OUT/census.txt" | tr '\n' ' ' | cut -c1-300)"
  finish 1
fi
report "census written (tools/corpus_tiers.py census; cases.csv under $OUT, which stays on the grid):"
"$PY" tools/corpus_tiers.py report --out "$OUT" 2>&1 | head -n 120 | sed 's/^/    /' >> "$REPORT.part"
finish 0
