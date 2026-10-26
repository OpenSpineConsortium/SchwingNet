#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=2-00:00:00
# Stage 2 of the X-ray chain: for each recipe grid/banks/<id>.json, turn the raw copy into a
# bank (tools/bank.py --run) and ingest the bank into a content-hashed shard
# (tools/ingest.py run, superseding the source's current shard where the bank grew, so a raw
# copy that came in parts is counted once by the catalog). A recipe still spelled "to confirm", a raw folder not fetched, or a
# format the bank tool refuses (a DICOM set run without the train environment) is one line in the report and the
# loop goes on; the stage exits non-zero at the end when any source failed. PYDRV must hold
# pydantic, beartype and icontract (the repository's pixi environment). ONLY narrows the loop to
# a space-separated list of ids. The report is logs/02-bank-ingest-STAGE-REPORT.md. Off the grid
# (issue #40) DATA_ROOT puts each source's raw, bank and shards under <root>/<id>/ in place of the
# recipe's and the registry's paths, and BANKS names another recipe folder, so a test runs the
# stage on a filled-in copy of a recipe without touching the shipped one.
#
# Under Slurm the stage runs as Metaflow's BankFlow (issue #252): a job with SLURM_JOB_ID set,
# and no SCHWINGNET_FLOW_STEP, execs flows/launch.py bank with what the caller gave (ONLY,
# DATA_ROOT, BANKS, INGEST_DATE), so a job cut short and queued again resumes the newest run of
# the same words and code, every recipe that finished cloned and a cut ingest run again with
# its bank cloned. The flow's steps run this script again with SCHWINGNET_FLOW_STEP=1, one recipe
# (ONLY) and one half (PART=bank or PART=ingest) at a time, on the date the run chose once
# (INGEST_DATE); a direct bash call, as the tests make, runs the body as before, both halves.
# PYDRV must then carry Metaflow too, as grid/bin/train-cpu-python does.
#
# The size rule (grid/size-rule.sh, the owner's rule of 2026-10-23): grid/gate.sh's word `bank <id>`
# admits the job for BANK_NEED bytes, what the bank and its shard may write by the format's budget
# of the raw copy's bytes, and records that admission as $DATA/<id>/meta/SIZE when it queues the
# job, so every later decision counts it while Slurm holds the job. The job decides again before it
# writes a byte, its own admission aside, against the room as it is when it starts, since what the
# volume took while it waited in the queue, another user's files among it, can leave less than the
# word saw; and for the larger of BANK_NEED and what the frames' pixels bound the bank and its shard
# by (tools/bank.py --bound, read from the headers), since a lossy file, a JPEG or a lossy DICOM,
# holds fewer bytes than its frame takes as PNG, which the word's budget, read with no python on the
# login node, cannot see (the second review of #252). Refused, or where the bound cannot be read,
# it writes nothing, settles the admission and exits 4, and the catalog build afterok on it is
# cancelled with it; requeued by Slurm, it keeps the room it was given. Once a job, before the
# launcher, so the flow's steps (SCHWINGNET_FLOW_STEP) never decide again. The X-ray chain's bank
# job, sent with no BANK_NEED, decides every recipe it was sent the same way before the launcher
# (issue #163), one after another: each for the format's budget of what its raw copy holds, as the
# word reckons it, and the frames' bound, against the room as it is then, the hold the fetch job
# left for the recipe's set (grid/admit.sh) set aside for it and every other set's, and every
# recipe decided before it, still counted. Before the launcher and on the node, since the rule
# reads Slurm's queue with squeue and takes a flock on the data root, neither of which the
# container the launcher and its steps run in has (grid/box.sh). A step then banks a recipe only
# where this job admitted it: refused, or not decided, that recipe writes nothing and its report
# line says why, from the refusal the job recorded (meta/REFUSED); an admitted recipe's room is
# settled once its ingest half has run or its bank half failed. A recipe still spelled "to
# confirm" is not decided, since tools/bank.py refuses it before a frame. A bank made before is
# counted again, as the word counts it, which errs toward refusing; what the catalog build writes
# is not counted. A direct bash call, as the tests make, decides nothing and banks every recipe.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
# The size reader below is called by name through size_and_admit, which shellcheck cannot follow.
# shellcheck disable=SC2329
bank_need() {  # bank_need ID: "<total> <need> <how>" for size_and_admit, the larger of BANK_NEED and the bound of the recipe's frames
  local recipe=${BANKS:-$REPO/grid/banks}/$1.json raw out bound
  is_count "$BANK_NEED" || { echo "BANK_NEED is no count"; return 2; }
  if [ -n "${DATA_ROOT:-}" ]; then
    raw=$DATA_ROOT/$1/raw
  else
    raw=$("$PYDRV" -c "import json,sys; print(json.load(open(sys.argv[1]))['raw'])" "$recipe") \
      || { echo "the recipe's raw folder could not be read"; return 2; }
  fi
  # A raw folder the stage skips below writes nothing, so the word's budget stands for it.
  if [ ! -d "$raw" ] || [ -z "$(ls -A "$raw" 2>/dev/null)" ]; then
    echo "$BANK_NEED $BANK_NEED the bank and its shard"
    return 0
  fi
  out=$("$PYDRV" "$REPO/tools/bank.py" --recipe "$recipe" --raw "$raw" --bound --workers "${BANK_WORKERS:-${SLURM_CPUS_PER_TASK:-1}}") \
    || { echo "the bank tool could not bound the frames by their pixels (exit $?)"; return 2; }
  bound=$(printf '%s\n' "$out" | "$PYDRV" -c "import json,sys; print(json.load(sys.stdin)['most_bytes'])")
  is_count "$bound" || { echo "the bank tool gave no bound of the frames"; return 2; }
  if [ "$bound" -gt "$BANK_NEED" ]; then
    echo "$bound $bound the pixels of the bank and its shard"
  else
    echo "$BANK_NEED $BANK_NEED the bank and its shard"
  fi
}
bank_admitted() {  # 0 where the size rule admits the one recipe ONLY names for what bank_need says it may write, 4 where it refuses
  local id=${ONLY:-}
  case "$id" in
    ""|*[!a-z0-9_]*) echo "bank: BANK_NEED holds room for one recipe, which ONLY names alone, not '$id'; nothing was banked"; return 4 ;;
  esac
  DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data} VOLUME=${VOLUME:-/rs/rs_grp_oschome}
  # shellcheck source=grid/size-rule.sh
  . "$REPO/grid/size-rule.sh"
  # A compute node may have no getfattr; the job's own python reads the quota's attributes there,
  # as grid/unpack.sbatch does, never one the environment it was sent from names unless a test says so.
  if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then RULE_PYTHON=${XATTR_PYTHON:-$PYDRV}; else RULE_PYTHON=$PYDRV; fi
  size_and_admit "$id" bank_need "$id" && return 0
  settle_admission "$id" "${SLURM_JOB_ID:-none}"
  return 4
}
chain_job() {  # whether this is the X-ray chain's bank job as Slurm starts it, sent with no BANK_NEED: it decides every recipe here, before the launcher
  [ -n "${SLURM_JOB_ID:-}" ] && [ -z "${SCHWINGNET_FLOW_STEP:-}" ] && [ -z "${BANK_NEED:-}" ]
}
chain_step() {  # whether this is a step of the X-ray chain's bank job, which banks a recipe only where the job admitted it before the launcher
  [ -n "${SLURM_JOB_ID:-}" ] && [ -n "${SCHWINGNET_FLOW_STEP:-}" ] && [ -z "${BANK_NEED:-}" ]
}
rule_sourced() {  # the size rule, for one recipe of a step of the chain's bank job
  DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data} VOLUME=${VOLUME:-/rs/rs_grp_oschome}
  # shellcheck source=grid/size-rule.sh
  . "$REPO/grid/size-rule.sh"
  if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then RULE_PYTHON=${XATTR_PYTHON:-$PYDRV}; else RULE_PYTHON=$PYDRV; fi
}
bank_decided() {  # bank_decided ID RECIPE RAW: 0 where the size rule admits the chain's bank job to bank ID, else 4, with its line either way
  local factor bytes BANK_NEED
  rule_sourced
  [ "$(unconfirmed_fields "$2")" = 0 ] || return 0
  read -r factor _ <<< "$(bank_factor "$(recipe_format "$2")")"
  bytes=$(xattr_whole ceph.dir.rbytes "$3")
  if [ -z "$factor" ] || ! is_count "$bytes" || [ "$bytes" -gt $(( 999999999999999999 / factor )) ]; then
    size_refused "$1" "the room its bank needs could not be reckoned from its recipe and raw copy"
    settle_admission "$1" "$SLURM_JOB_ID"
    return 4
  fi
  BANK_NEED=$(( factor * bytes ))
  bank_admitted
}
chain_decided() {  # every recipe this job was sent, with a raw copy, decided by the size rule here on the node, before the launcher runs the steps in the container
  local recipe id raw
  for recipe in "${BANKS:-$REPO/grid/banks}"/*.json; do
    [ -f "$recipe" ] || continue
    id=$(basename "$recipe" .json)
    if [ -n "${ONLY:-}" ] && ! echo " $ONLY " | grep -q " $id "; then continue; fi
    if [ -n "${DATA_ROOT:-}" ]; then
      raw=$DATA_ROOT/$id/raw
    else
      raw=$("$PYDRV" -c "import json,sys; print(json.load(open(sys.argv[1]))['raw'])" "$recipe" 2>/dev/null) || raw=""
    fi
    [ -n "$raw" ] && [ -d "$raw" ] && [ -n "$(ls -A "$raw" 2>/dev/null)" ] || continue
    bank_decided "$id" "$recipe" "$raw" || true
  done
}
chain_refusal_words() {  # chain_refusal_words ID: why this job did not admit ID's bank, from the refusal it recorded where it did
  local job need free utc
  if [ -f "$DATA/$1/meta/REFUSED" ]; then
    read -r job need free utc _ < "$DATA/$1/meta/REFUSED"
    if [ "$job" = "$SLURM_JOB_ID" ]; then
      if is_count "$need" && is_count "$free"; then
        echo "the size rule refused its bank for space at $utc; it needs $(gb_up "$need") gb and only $(gb_down "$free") gb was free"
      else
        echo "the size rule refused its bank at $utc; the log of the job says why"
      fi
      return 0
    fi
  fi
  echo "the size rule did not decide its bank in this job at $(date -u '+%FT%TZ'); the log of the job says why"
}
chain_admitted() {  # chain_admitted ID: 0 where this job admitted ID's bank before the launcher, else the recipe's report line and 4
  local state holder mark words
  rule_sourced
  if [ -f "$DATA/$1/meta/SIZE" ]; then
    read -r state holder _ _ _ _ mark _ < "$DATA/$1/meta/SIZE"
    if [ "$state" = admitted ] && [ "$holder" = "$SLURM_JOB_ID" ] && [ "$mark" != hold ]; then return 0; fi
  fi
  words=$(chain_refusal_words "$1")
  echo "$1: not banked; $words"
  echo "- $1: bank refused: $words" >> "$REPORT"
  return 4
}
chain_settled() {  # chain_settled ID: the recipe's admission settled once the chain's bank job is done with it
  chain_step || return 0
  rule_sourced
  settle_admission "$1" "$SLURM_JOB_ID"
}
if [ -n "${BANK_NEED:-}" ] && [ -z "${SCHWINGNET_FLOW_STEP:-}" ]; then
  bank_admitted || { echo "XR_BANK_RC=4 $(date '+%F %T')"; exit 4; }
fi
if chain_job; then chain_decided; fi
if [ -n "${SLURM_JOB_ID:-}" ] && [ -z "${SCHWINGNET_FLOW_STEP:-}" ]; then
  words=()
  [ -z "${ONLY:-}" ] || words+=(--sources "$ONLY")
  [ -z "${DATA_ROOT:-}" ] || words+=(--data-root "$DATA_ROOT")
  [ -z "${BANKS:-}" ] || words+=(--banks "$BANKS")
  [ -z "${INGEST_DATE:-}" ] || words+=(--date "$INGEST_DATE")
  exec "$PYDRV" "$REPO/flows/launch.py" bank --max-workers 1 -- ${words[@]+"${words[@]}"}
fi
ONLY=${ONLY:-}
DATA_ROOT=${DATA_ROOT:-}
BANKS=${BANKS:-$REPO/grid/banks}
DATE=${INGEST_DATE:-$(date '+%F')}
PART=${PART:-}
case "$PART" in
  ""|bank|ingest) ;;
  *) echo "PART is bank, ingest or unset for both, not $PART; nothing ran"; echo "XR_BANK_RC=2 $(date '+%F %T')"; exit 2 ;;
esac
# The bank tool decodes in as many processes as the job has cores (DICOM and JPEG are the slow
# part); the bank is the same bytes whatever the number (tools/bank.py --workers).
export BANK_WORKERS=${BANK_WORKERS:-${SLURM_CPUS_PER_TASK:-1}}
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 0000000)
REPORT=logs/02-bank-ingest-STAGE-REPORT.md
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-${DATA_ROOT:+$DATA_ROOT/_tmp}}
TMPDIR=${TMPDIR:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR"
echo "XR_BANK start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} commit $COMMIT"
{
  echo "# Stage 2, bank and ingest: $(date '+%F %T')"
  echo
  echo "Code commit $COMMIT, ingest date $DATE; one line per recipe under grid/banks/."
  echo
} > "$REPORT"
failed=0
for recipe in "$BANKS"/*.json; do
  id=$(basename "$recipe" .json)
  if [ -n "$ONLY" ] && ! echo " $ONLY " | grep -q " $id "; then continue; fi
  raw=$("$PYDRV" -c "import json,sys; print(json.load(open(sys.argv[1]))['raw'])" "$recipe")
  bank=$("$PYDRV" -c "import json,sys; print(json.load(open(sys.argv[1]))['bank'])" "$recipe")
  prefix=$("$PYDRV" -c "import json,sys; r=json.load(open(sys.argv[1])); print(r.get('person_prefix', r['id']))" "$recipe")
  root_args=()
  if [ -n "$DATA_ROOT" ]; then
    raw=$DATA_ROOT/$id/raw; bank=$DATA_ROOT/$id/bank; root_args=(--grid-root "$DATA_ROOT/$id")
  fi
  echo "== $id: $(date '+%F %T')"
  if [ ! -d "$raw" ] || [ -z "$(ls -A "$raw" 2>/dev/null)" ]; then
    echo "- $id: skipped, nothing fetched under $raw" >> "$REPORT"; continue
  fi
  if [ "$PART" != ingest ]; then
    if chain_step && ! chain_admitted "$id"; then failed=1; continue; fi
    if ! out=$("$PYDRV" "$REPO/tools/bank.py" --recipe "$recipe" --raw "$raw" --bank "$bank" --run 2>&1); then
      echo "$out"; echo "- $id: bank refused: $(echo "$out" | tail -n 1)" >> "$REPORT"; failed=1
      chain_settled "$id"; continue
    fi
    echo "$out"
  fi
  [ "$PART" != bank ] || continue
  if ! out=$("$PYDRV" "$REPO/tools/ingest.py" run --bank "$bank" --source "$id" --kind train --split train \
        --date "$DATE" --code-commit "$COMMIT" --person-prefix "$prefix" --supersedes latest ${root_args[@]+"${root_args[@]}"} 2>&1); then
    echo "$out"; echo "- $id: ingest refused: $(echo "$out" | tail -n 1)" >> "$REPORT"; failed=1
    chain_settled "$id"; continue
  fi
  chain_settled "$id"
  echo "$out"
  shard=$(echo "$out" | "$PYDRV" -c "import json,sys; d=json.load(sys.stdin); print(d['shard'], d['outcome'], d['frames_kept'], 'frames,', d['persons'], 'persons,', d['labels'], 'labels')")
  echo "- $id: $shard" >> "$REPORT"
done
{
  echo
  if [ "$failed" = 0 ]; then echo "Every recipe that had a raw copy was banked and ingested."; else echo "Some recipes failed; the lines above say which, the job's log, which the gate word status shows, says why."; fi
  echo "A recipe spelled 'to confirm' is filled in from the page, by pull request, and the gate word fetch <id> runs this stage again for that id."
} >> "$REPORT"
cat "$REPORT"
echo "XR_BANK_RC=$failed $(date '+%F %T')"
exit $failed
