#!/bin/bash
# Submit the X-ray chain as three dependent Slurm jobs (bash 4.2; the login node runs nothing
# but sbatch, df and this script, which is why the size budget is read with awk and not python):
#   1. grid/01-fetch.sbatch        every open set of grid/fetch-xray.json to the data root
#   2. grid/02-bank-ingest.sbatch  each raw copy into a bank, each bank into a shard (afterany:1)
#   3. grid/03-catalog.sbatch      the catalog rebuilt and split-checked (afterany:2)
# afterany, not afterok: a set that failed to fetch must not strand the rest, and each stage
# reports what it found. The job ids go to grid/LAST_RUN.txt and the logs under grid/logs/.
#
#   bash grid/run-xray-chain.sh                      # every open set
#   bash grid/run-xray-chain.sh --only lumos,fracatlas
#   bash grid/run-xray-chain.sh --credentialed --only mimic_cxr_jpg   # the opt-in PhysioNet list
#   SBATCH=echo bash grid/run-xray-chain.sh           # dry run: print the submissions
#
# Before submitting it sums the sizes the list states for the chosen entries and refuses when
# they exceed the volume's free space minus a 1 TB margin (df on /rs/rs_grp_oschome at submit
# time); an entry whose size is null counts as 0 and is named, so the owner knows it is unbudgeted.
# PYDRV: the python the stages run; the repository's pixi environment where pixi installed it,
# else python3 (then stage 2 and 3 fail at pydantic, and the report says so).
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SBATCH=${SBATCH:-sbatch}
DF=${DF:-df}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
# 5 TB, not 1: acquisition_fetch.sh stops its own job when the volume falls under 5 TB free
# (--floor-tb 5), so a chain admitted below that would start and stop at once.
MARGIN_GB=${MARGIN_GB:-5000}
LIST=$REPO/grid/fetch-xray.json
ONLY=""; CRED=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2 ;;
    --credentialed) CRED=1; shift ;;
    *) echo "unknown argument $1"; exit 64 ;;
  esac
done
[ -f "$LIST" ] || { echo "no $LIST: is SCHWINGNET the checkout?"; exit 2; }
mkdir -p "$REPO/grid/logs"
# The train-cpu environment first, since it holds Pillow, which stage 2 needs to convert a JPEG,
# TIFF or BMP set; the default environment holds pydantic for the ingest and the catalog but no
# Pillow; python3 last, which stages 2 and 3 then report as lacking pydantic.
if [ -z "${PYDRV:-}" ]; then
  if [ -x "$REPO/.pixi/envs/train-cpu/bin/python" ]; then PYDRV=$REPO/.pixi/envs/train-cpu/bin/python
  elif [ -x "$REPO/.pixi/envs/default/bin/python" ]; then PYDRV=$REPO/.pixi/envs/default/bin/python
  else PYDRV=python3; fi
fi
export PYDRV SCHWINGNET="$REPO"

# The size budget: id and size_gb per entry, in the file's order; the credentialed list starts
# at the line that names it. Each selected entry's size is summed; null counts as 0 and is named.
budget=$(awk -v only="$ONLY" -v cred="$CRED" '
  /"credentialed": \[/ { section = "cred" }
  /"id": "/ { id = $0; sub(/.*"id": "/, "", id); sub(/".*/, "", id) }
  /"size_gb": / { size = $0; sub(/.*"size_gb": /, "", size); sub(/[,} ].*/, "", size)
    wanted = (only == "") ? (section != "cred" || cred == 1) : (index("," only ",", "," id ",") > 0)
    if (wanted && section == "cred" && cred == 0) { gated = gated " " id }
    if (wanted) { if (size == "null") { unknown = unknown " " id } else { total += size }; n++ } }
  END { printf "%d %d %s|%s\n", n, total, gated, unknown }' "$LIST")
count=${budget%% *}; rest=${budget#* }; total_gb=${rest%% *}; rest=${rest#* }
gated=${rest%%|*}; unknown=${rest#*|}
if [ -n "${gated// /}" ]; then
  echo "refusing: ${gated# } is on the credentialed list; add --credentialed to run it"; exit 64
fi
if [ "$count" = 0 ]; then
  echo "refusing: no entry of grid/fetch-xray.json is named by --only ${ONLY:-}; nothing to submit"; exit 64
fi
free_gb=$("$DF" -BG --output=avail "$VOLUME" 2>/dev/null | tail -n 1 | tr -dc '0-9')
[ -n "$free_gb" ] || { echo "cannot read the free space of $VOLUME with df"; exit 2; }
echo "size budget: $count entries, $total_gb GB stated; $VOLUME has $free_gb GB free, margin $MARGIN_GB GB"
[ -z "$unknown" ] || echo "no size stated for:${unknown} (counted as 0; read the page)" | sed "s/for: */for: /"
if [ "$total_gb" -gt $(( free_gb - MARGIN_GB )) ]; then
  echo "refusing to submit: $total_gb GB exceeds the free space minus the margin; free room or narrow with --only"
  exit 3
fi

FETCH_ARGS=""
[ -z "$ONLY" ] || FETCH_ARGS="--only $ONLY"
[ "$CRED" = 0 ] || FETCH_ARGS="$FETCH_ARGS --credentialed"
ONLY_IDS=$(echo "$ONLY" | tr ',' ' ')

submit() {  # submit [sbatch options...] SCRIPT: prints the job id; a dry run prints the line instead
  local out
  if [ "$SBATCH" != sbatch ]; then
    # The stage's number stands in for the job id, since a subshell cannot count for its caller.
    echo "would submit: sbatch --parsable -D $REPO/grid $*" >&2; echo "DRY$(basename "${@: -1}" | cut -c2)"; return 0
  fi
  out=$("$SBATCH" --parsable -D "$REPO/grid" "$@") || { echo "sbatch failed: $out" >&2; return 1; }
  echo "$out" | tail -n 1 | cut -d';' -f1
}
# The stages read their settings from the environment (--export=ALL), never from --export's
# own list, whose comma-separated grammar would cut an --only list of ids at its first comma.
export FETCH_ARGS ONLY="$ONLY_IDS"
# DEPEND (sbatch's dependency grammar, as grid/gate.sh gives it) holds stage 1 back until the jobs
# it names allow; a dependency that can never be met cancels the stage instead of stranding it.
first=()
[ -z "${DEPEND:-}" ] || first=(--dependency="$DEPEND" --kill-on-invalid-dep=yes)
j1=$(submit ${first[@]+"${first[@]}"} --export=ALL "$REPO/grid/01-fetch.sbatch") || exit 1
j2=$(submit --dependency=afterany:"$j1" --export=ALL "$REPO/grid/02-bank-ingest.sbatch") || exit 1
j3=$(submit --dependency=afterany:"$j2" --export=ALL "$REPO/grid/03-catalog.sbatch") || exit 1
{
  echo "$(date '+%F %T') fetch=$j1 bank=$j2 catalog=$j3 only=${ONLY:-all} credentialed=$CRED size_gb=$total_gb pydrv=$PYDRV"
} | tee -a "$REPO/grid/LAST_RUN.txt"
echo "submitted: 1 fetch $j1 -> 2 bank-ingest $j2 (afterany) -> 3 catalog $j3 (afterany)"
echo "ETA: stage 1 is network-bound, about 1 hour per 20 GB on a compute node (${total_gb} GB stated, so about $(( total_gb / 20 + 1 )) hours; a 4-day wall time, requeued on preemption); stage 2 minutes per source (hashing and copying; a JPG set converts at a few hundred frames a minute); stage 3 under a minute."
echo "watch: squeue -u \$USER; the reports: $REPO/grid/logs/0*-STAGE-REPORT.md"
