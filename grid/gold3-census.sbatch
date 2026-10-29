#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
# The gold tier census: one CPU job that reads what the grid holds and segments nothing (the owner's tap
# of 2026-10-29 12:26 UTC on "Send the 1 CPU job now": "The gate word's PR is merged once green and 1 CPU
# job is sent that reads only and segments nothing"; docs/research/gold3-ct/README.md section 7).
# grid/gate.sh's word `census gold3` queues it once as the batch class; the next send prints its report.
#
# Parts, each `tools/gold3_census.py <part>`, in this order, each writing <part>.json (what stays on the
# grid) and <part>.lines (what the report carries) under $OUT:
#   ts142    the older list of 142 TotalSegmentator subjects beside rule 3's admitted
#   autopet  autoPET's CTs in FDG-PET-CT-Lesions matched to ENHANCE.PET's studies by their grids
#   gold4    the field test over the census's SPINEPS masks, counts by collection
#   extent   TotalSegmentator's CTs read whole: their own padded planes, the field test again
#   held     the members' files on the data root against the sums recorded in the repository
# A part that fails is reported and the next one still runs, since each reads its own files.
#
# The job runs from its own copy of the tool, tools/gold3_field.py and data/gold3-ct/ under $OUT/code,
# made as it starts, so it takes no hold on the checkout and holds no other run back however long it
# reads. The interpreter is train-cpu's (numpy, no nibabel) inside the container where its environment
# is made, else the first of the SPINEPS environments' and the system's that imports numpy. Not requeued
# (--no-requeue from the gate), since a second run of it needs the owner's word.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
DATA=${DATA_ROOT:-$RS/data}
CENSUS_ROOT=${CENSUS_ROOT:-$RS/gold3_census}
CPUS=${SLURM_CPUS_PER_TASK:-4}
PARTS=${CENSUS_PARTS:-ts142 autopet gold4 extent held}
REPORT=$REPO/grid/logs/CENSUS-gold3.md
OUT=$CENSUS_ROOT/${SLURM_JOB_ID:-$$}
mkdir -p "$REPO/grid/logs" "$OUT"
chmod 700 "$CENSUS_ROOT" "$OUT" 2>/dev/null
export PYTHONNOUSERSITE=1
report() { echo "- $*" >> "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_CENSUS_RC=$1"
  exit "$1"
}
trap 'report "FAILED: the job was ended by a signal"; finish 143' TERM
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# census gold3: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"

# The copy the parts run from, so the checkout may move while they read.
mkdir -p "$OUT/code/tools" "$OUT/code/data" || { report "FAILED: no room for the code's copy under the census folder"; finish 2; }
for file in tools/gold3_census.py tools/gold3_field.py; do
  cp "$REPO/$file" "$OUT/code/$file" || { report "FAILED: the checkout has no $(basename "$file")"; finish 2; }
done
cp -r "$REPO/data/gold3-ct" "$OUT/code/data/" || { report "FAILED: the checkout has no gold 3 records"; finish 2; }
copied_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
[ "$copied_at" = "$started_at" ] || { report "FAILED: the checkout moved while the code was copied, so the copy may mix two commits; a second run waits for the owner's word"; finish 3; }

PY=""
for cand in "${PYDRV:-$REPO/grid/bin/train-cpu-python}" "$HOME/mambaforge/envs/spineps/bin/python" \
            "$RS/envs/spineps212/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter that imports numpy (train-cpu, the SPINEPS environments, the system's)"; finish 2; }
report "interpreter: $(basename "$PY"), Python $("$PY" -c 'import sys; print(sys.version.split()[0])'), numpy $("$PY" -c 'import numpy; print(numpy.__version__)')"
report "code: the tool, the field test and the gold 3 records copied at commit ${started_at:0:7}; nothing segmented, nothing trained"

failed=0
for part in $PARTS; do
  began=$(date -u +%s)
  if "$PY" "$OUT/code/tools/gold3_census.py" "$part" --data "$DATA" --rs "$RS" --home "$HOME" --out "$OUT" \
       --workers "$CPUS" > "$OUT/$part.out" 2>&1; then
    cat "$OUT/$part.lines" | sed 's/^/- /' >> "$REPORT.part"
    report "$part: done in $(( ($(date -u +%s) - began) / 60 )) min"
  else
    failed=1
    # the error's kind alone, since its message may name a path; the whole output stays under the census folder
    report "FAILED at $part after $(( ($(date -u +%s) - began) / 60 )) min, $(tail -n 1 "$OUT/$part.out" | cut -d: -f1 | tr -cd 'A-Za-z0-9_ .' | cut -c1-80)"
  fi
done
finish "$failed"
