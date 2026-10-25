#!/bin/bash
# The size rule's decisions for the X-ray fetch job, set by set (issue #163). tools/fetch_sources.py
# runs this, as `--admit "bash grid/admit.sh"` inside grid/01-fetch.sbatch, once it has read a set's
# exact size from its source and before the set's first byte lands, so each set is admitted whole
# or refused whole when the job reaches it, against the room as it is then, as a CT platform fetch
# is in its own job (grid/size-rule.sh, grid/platform-fetch.sbatch):
#
#   bash grid/admit.sh admit ID TOTAL NEED HOW...   the set's download, then its unpacking where
#                                                   its archives state their members, admitted (0)
#                                                   or refused (4)
#   bash grid/admit.sh unpack ID TOTAL NEED HOW...  the set decided again once its compressed tars
#                                                   have landed, for their members, which no source
#                                                   states before (0 or 4); refused, nothing of them
#                                                   is unpacked
#   bash grid/admit.sh refuse ID REASON...          a set whose size could not be read, refused (4)
#   bash grid/admit.sh landed ID BYTES              the set landed whole: the room of its bank
#                                                   handed to the chain's bank job, else settled
#   bash grid/admit.sh settle ID                    the set did not land: its admission settled
#
# The bank is held with the set (the issue's third part): what the bank and its shard may write of
# a set the recipe grid/banks/ID.json banks, by the format's budget of the raw copy (bank_budget),
# is added to the set's need, so a set is fetched only where its bank fits too, and once the set has
# landed that room passes to the chain's bank job, which grid/run-xray-chain.sh records beside the
# fetch job in grid/logs/XRAY_SIZES.txt, as a hold that job counts and decides when it banks the set
# (grid/02-bank-ingest.sbatch). A requeued job keeps what it was admitted, the download's and the
# unpacking's apart (admitted_before). Lines are in plain words, the shape the gate's status word
# keeps; DATA is the data root, VOLUME the lab volume and PYDRV the job's Python, which reads the
# quota's attributes on a node with no getfattr.
set -uo pipefail
REPO=${SCHWINGNET:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
DATA=${DATA:-/rs/rs_grp_oschome/go2432/data}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then RULE_PYTHON=${XATTR_PYTHON:-${PYDRV:-python3}}; else RULE_PYTHON=${PYDRV:-python3}; fi
job=${SLURM_JOB_ID:-none}

admit() {  # admit MARK ID TOTAL NEED HOW: the set with its bank, decided under the size rule
  local mark=$1 id=$2 total=$3 need=$4 how=$5 bank factor
  if ! is_count "$total" || ! is_count "$need"; then
    size_refused "$id" "the size reader gave no size"
    return
  fi
  if admitted_before "$id" "$mark"; then
    echo "$id: admitted already; job $job restarted and keeps the room it was given at $(date -u '+%FT%TZ')"
    return 0
  fi
  if ! read -r bank factor <<< "$(bank_budget "$id" "$total")" || ! is_count "$bank" \
    || ! fits_in_count "$total" "$bank" || ! fits_in_count "$need" "$bank"; then
    size_refused "$id" "its bank would need more than the size rule counts"
    return
  fi
  [ "$bank" = 0 ] || how="$how and its bank at $factor times"
  admit_fetch "$id" $(( total + bank )) $(( need + bank )) "$how" "$mark"
}

bank_job() {  # bank_job: the chain's bank job grid/run-xray-chain.sh recorded beside this fetch job, else nothing
  [ -f "$REPO/grid/logs/XRAY_SIZES.txt" ] || return 0
  awk -v job="$job" '$1 == job && $2 == "sets" { bank = $4 } END { print bank }' "$REPO/grid/logs/XRAY_SIZES.txt"
}

landed() {  # landed ID BYTES: the room of the set's bank handed to the chain's bank job, else the admission settled
  local id=$1 bytes=$2 file=$DATA/$1/meta/SIZE state holder bank factor base banker
  [ -f "$file" ] || return 0
  read -r state holder _ < "$file"
  [ "$state" = admitted ] && [ "$holder" = "$job" ] || return 0
  banker=$(bank_job) bank="" base=""
  if is_count "$bytes" && is_count "$banker"; then
    read -r bank factor <<< "$(bank_budget "$id" "$bytes")"
    base=$(landing_bytes "$id")
  fi
  if is_count "$bank" && [ "$bank" != 0 ] && [ -n "$base" ]; then
    # Measured from what the landing holds now, so the set itself counts for nothing more.
    echo "admitted $banker $bank $base $(date -u '+%FT%TZ') $bank hold" > "$file.new" && mv -f "$file.new" "$file" \
      && { echo "$id: landed; $(gb_up "$bank") gb held for its bank at $factor times by job $banker at $(date -u '+%FT%TZ')"; return 0; }
  fi
  settle_admission "$id" "$job"
  echo "$id: landed; its admission settled with no bank to hold at $(date -u '+%FT%TZ')"
}

word=${1:-}
[ $# -gt 0 ] && shift
case "$word" in
  admit) [ $# -ge 4 ] || { echo "admit takes ID TOTAL NEED HOW"; exit 64; }; admit "" "$1" "$2" "$3" "${*:4}" ;;
  unpack) [ $# -ge 4 ] || { echo "unpack takes ID TOTAL NEED HOW"; exit 64; }; admit unpack "$1" "$2" "$3" "${*:4}" ;;
  refuse) [ $# -ge 1 ] || { echo "refuse takes ID REASON"; exit 64; }; size_refused "$1" "${*:2}" ;;
  landed) [ $# -eq 2 ] || { echo "landed takes ID BYTES"; exit 64; }; landed "$1" "$2" ;;
  settle) [ $# -eq 1 ] || { echo "settle takes ID"; exit 64; }; settle_admission "$1" "$job"
    echo "$1: settled; job $job holds no room for it at $(date -u '+%FT%TZ')" ;;
  *) echo "admit.sh: one of admit, unpack, refuse, landed and settle"; exit 64 ;;
esac
