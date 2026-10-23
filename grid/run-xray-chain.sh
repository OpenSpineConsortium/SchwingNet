#!/bin/bash
# Submit the X-ray chain as three dependent Slurm jobs through hpcworker's job submit (grid/hpcw.sh;
# bash 4.2; the login node runs nothing but hpcworker, getfattr, squeue, df and this script, which is
# why the size budget is read with awk and not python):
#   1. grid/01-fetch.sbatch        every open set of grid/fetch-xray.json to the data root
#   2. grid/02-bank-ingest.sbatch  each raw copy into a bank, each bank into a shard (afterany:1)
#   3. grid/03-catalog.sbatch      the catalog rebuilt and split-checked (afterany:2)
# afterany, not afterok: a set that failed to fetch must not strand the rest, and each stage
# reports what it found. The job ids go to grid/LAST_RUN.txt, the stage reports to grid/logs/ and
# each job's output to hpcworker's log folder for the project.
#
#   bash grid/run-xray-chain.sh                      # every open set
#   bash grid/run-xray-chain.sh --only lumos,fracatlas
#   bash grid/run-xray-chain.sh --credentialed --only mimic_cxr_jpg   # the opt-in PhysioNet list
#   HPCW_DRY=1 bash grid/run-xray-chain.sh            # dry run: print the submissions
#
# Before submitting it sums the sizes the list states for the chosen entries, rounded up to the
# whole GB, and refuses when they exceed the room left under the volume's CephFS quota after what
# the running fetches still owe, read at submit time with no margin (grid/size-rule.sh; df reports
# the whole Ceph pool there, issue #160); an entry whose size is null counts as 0 and is named, so
# the owner knows it is unbudgeted. The size rule's lock is held from that reading until the
# chain's sizes are recorded, so no fetch admitted in between misses the chain, nor the chain it.
# The X-ray sets are not yet sized from their sources one by one, as the CT platform's are in their
# jobs (issue #163): until they are, this sum of the list's sizes is their only check.
# PYDRV: the python the stages run; the repository's pixi environment where pixi installed it,
# else python3 (then stage 2 and 3 fail at pydantic, and the report says so).
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
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
# The sum is rounded up to the whole GB, read to the thousandth first so that a sum such as
# 14.2 + 0.8 is not taken for a hair over 15; the stated sum is kept for the messages.
budget=$(awk -v only="$ONLY" -v cred="$CRED" '
  /"credentialed": \[/ { section = "cred" }
  /"id": "/ { id = $0; sub(/.*"id": "/, "", id); sub(/".*/, "", id) }
  /"size_gb": / { size = $0; sub(/.*"size_gb": /, "", size); sub(/[,} ].*/, "", size)
    wanted = (only == "") ? (section != "cred" || cred == 1) : (index("," only ",", "," id ",") > 0)
    if (wanted && section == "cred" && cred == 0) { gated = gated " " id }
    if (wanted) { if (size == "null") { unknown = unknown " " id } else { total += size }; n++ } }
  END { stated = sprintf("%.3f", total) + 0; whole = int(stated); if (stated > whole) whole++
    printf "%d %d %s %s|%s\n", n, whole, stated, gated, unknown }' "$LIST")
count=${budget%% *}; rest=${budget#* }; total_gb=${rest%% *}; rest=${rest#* }
stated_gb=${rest%% *}; rest=${rest#* }
gated=${rest%%|*}; unknown=${rest#*|}
if [ -n "${gated// /}" ]; then
  echo "refusing: ${gated# } is on the credentialed list; add --credentialed to run it"; exit 64
fi
if [ "$count" = 0 ]; then
  echo "refusing: no entry of grid/fetch-xray.json is named by --only ${ONLY:-}; nothing to submit"; exit 64
fi
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
# One decision at a time with the fetch jobs' own (grid/size-rule.sh, admit_fetch), from the room's
# reading to the record of this chain's sizes; a dry run sends nothing, and off the grid there is
# no data root to hold the lock in.
if [ -z "${HPCW_DRY:-}" ] && [ -d "$DATA" ]; then
  exec 8> "$DATA/.size-rule.lock"
  flock -w "${SIZE_RULE_WAIT:-900}" 8 || {
    echo "refusing to submit: another fetch held the size check for ${SIZE_RULE_WAIT:-900} seconds; nothing was queued"
    exit 3
  }
fi
read -r free_gb free_from <<< "$(volume_free_gb "$VOLUME")"
[ -n "$free_gb" ] || { echo "cannot read the free space of $VOLUME: neither its CephFS quota nor df answered"; exit 2; }
owed=$(owed_by_running "") || { echo "cannot read what the running fetches owe: squeue did not answer; nothing was queued"; exit 2; }
read -r owed_bytes owed_n owed_unsized <<< "$owed"
owed_gb=$(gb_up "$owed_bytes")
counted=""
[ "$stated_gb" = "$total_gb" ] || counted=", counted as $total_gb GB"
echo "size budget: $count entries, $stated_gb GB stated$counted; $VOLUME has $free_gb GB $(free_space_words "$free_from"), $owed_gb GB of it owed to $(running_fetches "$owed_n")"
[ -z "$unknown" ] || echo "no size stated for:${unknown} (counted as 0; read the page)" | sed "s/for: */for: /"
if [ -n "$owed_unsized" ]; then
  echo "refusing to submit: the running fetch of $owed_unsized states no size, so nothing is admitted beside it"
  exit 3
fi
if [ "$total_gb" -gt $(( free_gb - owed_gb )) ]; then
  echo "refusing to submit: $total_gb GB exceeds the room the quota has left after the running fetches; free room or narrow with --only"
  exit 3
fi

FETCH_ARGS=""
[ -z "$ONLY" ] || FETCH_ARGS="--only $ONLY"
[ "$CRED" = 0 ] || FETCH_ARGS="$FETCH_ARGS --credentialed"
ONLY_IDS=$(echo "$ONLY" | tr ',' ' ')

# shellcheck source=grid/hpcw.sh
. "$REPO/grid/hpcw.sh"
# The stages read their settings from the environment, which job submit hands each job, never from
# --export's own list, whose comma-separated grammar would cut an --only list of ids at its first comma.
export FETCH_ARGS ONLY="$ONLY_IDS"
# DEPEND (sbatch's dependency grammar, as grid/gate.sh gives it) holds stage 1 back until the jobs
# it names allow; job submit ends a stage whose dependency can never be met instead of stranding it.
hpcw_after "${DEPEND:-}" || exit 1
# All three or none: a stage refused after the first cancels what was submitted, so no fetch runs
# that nothing recorded and no later chain waits on half of this one.
undo() { "${SCANCEL:-scancel}" "$@" && echo "cancelled what was submitted before the refusal: $*" >&2; exit 1; }
j1=$(hpcw_submit xr_fetch batch ${HPCW_AFTER[@]+"${HPCW_AFTER[@]}"} -- 01-fetch.sbatch) || exit 1
hpcw_after "afterany:$j1" || undo "$j1"
j2=$(hpcw_submit xr_bank batch ${HPCW_AFTER[@]+"${HPCW_AFTER[@]}"} -- 02-bank-ingest.sbatch) || undo "$j1"
# CATALOG_DEPEND adds to stage 3's wait (grid/gate.sh names its first catalog job there, so two
# catalog builds never run at once and the C-ArmLSpine ingest never holds back the fetch).
hpcw_after "afterany:$j2${CATALOG_DEPEND:+,$CATALOG_DEPEND}" || undo "$j1" "$j2"
j3=$(hpcw_submit xr_catalog batch ${HPCW_AFTER[@]+"${HPCW_AFTER[@]}"} -- 03-catalog.sbatch) || undo "$j1" "$j2"
{
  echo "$(date '+%F %T') fetch=$j1 bank=$j2 catalog=$j3 only=${ONLY:-all} credentialed=$CRED size_gb=$total_gb pydrv=$PYDRV"
} | tee -a "$REPO/grid/LAST_RUN.txt"
# What the size rule counts the fetch at while it runs (grid/size-rule.sh): the sizes the list
# states, their sum rounded up to the whole GB; a set whose size the list leaves null counts
# nothing. Recorded before the lock is let go, so the next decision sees it.
[ -n "${HPCW_DRY:-}" ] || echo "$j1 $(( total_gb * 1000000000 )) $(date -u '+%FT%TZ')" >> "$REPO/grid/logs/XRAY_SIZES.txt"
exec 8>&-
echo "submitted: 1 fetch $j1 -> 2 bank-ingest $j2 (afterany) -> 3 catalog $j3 (afterany)"
echo "ETA: stage 1 is network-bound, about 1 hour per 20 GB on a compute node (${stated_gb} GB stated, so about $(( total_gb / 20 + 1 )) hours; a 4-day wall time, requeued on preemption); stage 2 minutes per source (hashing and copying; a JPG set converts at a few hundred frames a minute); stage 3 under a minute."
echo "watch: the gate word status; the reports: $REPO/grid/logs/0*-STAGE-REPORT.md"
