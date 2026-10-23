# shellcheck shell=bash
# The owner's size rule (2026-10-23, issue #160): "make sure any datasets that are selected for
# storage know exactly how much space they will require and block those which would cause overflow,
# all or nothing datasets". A fetch reads its exact size from its source before it downloads a byte
# (grid/fetch_size.py), and starts only when what it still has to land fits in the room left under
# the lab volume's CephFS quota after what every admitted fetch still running has yet to land. There
# is no floor and no margin, so the quota can be filled to the byte, and the rule stops no fetch
# part-way: each is admitted whole, or refused before it starts and lands nothing. A job Slurm
# requeues keeps its admission and goes on. What the rule does not see can still fill the volume
# under a running fetch: writes no admission counts (the X-ray chain's banks and shards, the jobs'
# TMPDIR on the volume, the group's other users), a file quota (ceph.quota.max_files, which the
# readout shows and the rule does not count) and the lag with which CephFS adds new bytes to
# ceph.dir.rbytes.
#
# The room is read where the limit binds. The volume is a CephFS folder under a quota, and df and
# statvfs report the whole Ceph pool instead: on 2026-10-23 df said 5,881,937 GB free under a quota
# of 21,991 GB (20 TiB). CephFS keeps the quota as ceph.quota.max_bytes and what
# counts against it as ceph.dir.rbytes, attributes of the folder read with no walk: by getfattr on
# the login node, and by Python's os.getxattr on a node with no getfattr (XATTR_PYTHON, which
# grid/platform-fetch.sbatch sets to the acq environment's). Where neither runs, nothing is read,
# and df is never asked in its place on a mount that may be CephFS, kernel or FUSE. A value is
# taken up to its first NUL and only as a count of at most 18 digits (is_count): on 2026-10-23
# getfattr in the owner's shell printed the volume's ceph.dir.rbytes as 48 digits and its
# ceph.dir.rfiles as 25, and bash's arithmetic wraps such a number without a word, which would
# have read the use as less than nothing and the room as 2.5 EB, so every fetch would have been
# admitted. A reading that is no count admits nothing, and the readout says which one it was.
#
# What each fetch still owes is kept beside its landing, $DATA/<id>/meta:
#   QUEUED   "<job> <utc>", written when grid/run-platform-fetch.sh submits the job
#   SIZE     "admitted <job> <bytes to land> <bytes the landing held then> <utc> <total>", written
#            by the job when its size fits
#   REFUSED  "<job> <bytes to land> <bytes free> <utc> <total>", written by the job when it does not,
#            and never over an admission another job holds
# A job counts against the room while Slurm holds it (squeue): admitted, the bytes it had to land
# less what its landing has grown by since; queued and not yet started, nothing, since it decides
# against what is admitted when it starts; an X-ray fetch, at the sizes its list stated when
# grid/run-xray-chain.sh sent it (grid/logs/XRAY_SIZES.txt), whole while it runs; a fetch the gate
# sent before this rule, at the size its line in grid/run-platform-fetch.sh states less what its
# landing holds. A running fetch whose size nothing states, an X-ray fetch sent before its size was
# recorded or a line that states none, cannot be counted, so nothing is admitted beside it.
#
# Sourced by grid/platform-fetch.sbatch (the decision, in the job), grid/run-platform-fetch.sh and
# grid/run-xray-chain.sh (the room after the running fetches, on the login node). DATA, VOLUME and
# REPO name the folders; GETFATTR, XATTR_PYTHON and SQUEUE the tools, so a test can stand in for them.

xattr_value() {  # xattr_value NAME FOLDER: a CephFS attribute's value up to its first NUL; 2 when no reader runs
  local python=${XATTR_PYTHON:-python3}
  # Cut at the first NUL here and nowhere else: bash drops a NUL from what a command prints, and
  # would join whatever follows it to the digits before it; a line break inside is kept, so a value
  # that holds one is no count rather than the part before it.
  if command -v "${GETFATTR:-getfattr}" > /dev/null 2>&1; then
    "${GETFATTR:-getfattr}" --only-values -n "$1" "$2" 2>/dev/null | { IFS= read -r -d '' value; printf '%s' "$value"; }
    return 0
  fi
  # An attribute that is not there is nothing; a Python that does not run is no reading at all.
  "$python" -c '
import os, sys
try:
    sys.stdout.write(os.getxattr(sys.argv[2], sys.argv[1]).split(b"\0")[0].decode("ascii", "replace"))
except OSError:
    pass' "$1" "$2" 2>/dev/null || return 2
}

is_count() {  # is_count TEXT: whether TEXT is a count bash's arithmetic holds whole, with any sum of a few
  # At most 18 digits, under the 19 of the largest 64-bit integer, since bash wraps a longer number
  # without a word (on 2026-10-23 a 48-digit reading would have left more room than the pool has);
  # no leading zero, which bash's arithmetic reads as octal.
  case "$1" in ""|*[!0-9]*|0?*) return 1 ;; esac
  [ "${#1}" -le 18 ]
}

fits_in_count() {  # fits_in_count SUM ADD: whether SUM + ADD is still a count, for two counts
  [ "$2" -le $(( 999999999999999999 - $1 )) ]
}

xattr_digits() {  # xattr_digits NAME FOLDER: a CephFS attribute as a count, or nothing where it is not there; 2 when no reader runs, 3 when it reads as no count
  local value
  value=$(xattr_value "$1" "$2") || return 2
  [ -n "$value" ] || return 0
  # Never part of a value taken as the whole: what is no count is no reading.
  is_count "$value" || return 3
  echo "$value"
}

xattr_words() {  # xattr_words NAME FOLDER: what one reading of the attribute gave, in words, for the readout
  local value
  value=$(xattr_digits "$1" "$2")
  case $? in
    2) echo "$1 was not read; neither getfattr nor Python ran" ;;
    3) value=$(xattr_value "$1" "$2")
       echo "$1 reads as no count, ${#value} characters up to its first NUL where a count has at most 18 digits" ;;
    *) echo "$1 reads ${value:-as not there}" ;;
  esac
}

volume_free_bytes() {  # volume_free_bytes VOLUME: "<bytes free> quota" or "<bytes free> df", else nothing
  local volume=$1 quota used avail
  quota=$(xattr_digits ceph.quota.max_bytes "$volume") || return 1
  used=$(xattr_digits ceph.dir.rbytes "$volume") || return 1
  if [ -n "$quota" ] && [ "$quota" != 0 ]; then
    [ -n "$used" ] || return 1
    echo "$(( quota > used ? quota - used : 0 )) quota"
    return 0
  fi
  # A CephFS folder with no quota of its own would be read from df as the whole pool, which is the
  # error this rule fixes; it is no answer, so VOLUME must name the quota's own folder. A FUSE
  # mount, as ceph-fuse makes, says only fuse or fuseblk, and a type stat cannot read may be
  # either, so df answers only for a mount that names another kind.
  [ -z "$used" ] || return 1
  case "$("${STAT:-stat}" -f -c %T "$volume" 2>/dev/null)" in
    ""|ceph|fuse|fuseblk|fuse.*) return 1 ;;
  esac
  avail=$("${DF:-df}" -B1 --output=avail "$volume" 2>/dev/null | tail -n 1 | tr -dc '0-9')
  is_count "$avail" || return 1
  echo "$avail df"
}

volume_free_gb() {  # volume_free_gb VOLUME: "<whole GB free> quota" or "... df", else nothing
  local bytes from
  read -r bytes from <<< "$(volume_free_bytes "$1")"
  [ -n "$bytes" ] || return 1
  echo "$(( bytes / 1000000000 )) $from"
}

free_space_words() {  # free_space_words FROM: how a line names the figure it read
  case "$1" in
    quota) echo "free under its quota" ;;
    *) echo "free by df (no quota on it)" ;;
  esac
}

gb_up() { echo $(( ($1 + 999999999) / 1000000000 )); }
gb_down() { echo $(( $1 / 1000000000 )); }
running_fetches() {  # running_fetches N: "1 running fetch" or "N running fetches"
  if [ "$1" = 1 ]; then echo "1 running fetch"; else echo "$1 running fetches"; fi
}

live_job_ids() {  # the jobs Slurm holds for the user, queued or running, one a line; fails when squeue does
  local out
  out=$("${SQUEUE:-squeue}" -h -u "${USER:-$(id -un)}" -o '%i' 2>/dev/null) || return 1
  printf '%s\n' "$out" | sed 's/_.*//' | sort -u
}

stated_bytes() {  # stated_bytes ID: the size grid/run-platform-fetch.sh's line for ID states, in bytes, else nothing
  local gb
  gb=$(bash "$REPO/grid/run-platform-fetch.sh" --stated "$1" 2>/dev/null)
  awk -v g="$gb" 'BEGIN { if (g + 0 > 0) printf "%.0f\n", g * 1000000000 }'
}

landing_bytes() {  # landing_bytes ID: what the landing holds by CephFS, 0 where there is none, else nothing
  [ -e "$DATA/$1" ] || { echo 0; return 0; }
  xattr_digits ceph.dir.rbytes "$DATA/$1"
}

size_files() {  # every admission's SIZE file under DATA, one a line, globbed even where the caller set noglob
  # The hf-token route decides under set -f, so its include pattern reaches hf-get as written; a
  # glob left unexpanded there would count no running fetch and admit one that overflows.
  local file noglob=""
  if shopt -qo noglob; then noglob=yes; set +f; fi
  for file in "$DATA"/*/meta/SIZE; do
    [ -f "$file" ] && printf '%s\n' "$file"
  done
  [ -z "$noglob" ] || set -f
}

owed_by_running() {  # owed_by_running SELF: "<bytes> <fetches> [unsized...]" the fetches Slurm holds, SELF aside, have yet to land
  local self=${1:-} ids live file id state job need base landed owe owed=0 n=0 unsized="" counted=" " what
  ids=$(live_job_ids) || return 1
  live=" $(printf '%s' "$ids" | tr '\n' ' ') "
  while read -r file; do
    [ -f "$file" ] || continue
    id=${file%/meta/SIZE}
    id=${id##*/}
    read -r state job need base _ < "$file"
    [ "$state" = admitted ] && [ "$job" != "$self" ] || continue
    case "$live" in *" $job "*) ;; *) continue ;; esac
    counted="$counted$job "
    if ! is_count "$need" || ! is_count "$base"; then unsized="$unsized $id"; continue; fi
    # Owed: what it had to land less what its landing has grown by since, so files already there
    # before it, another part of the same set, count for nothing; unreadable, the whole of it.
    landed=$(landing_bytes "$id")
    [ -n "$landed" ] || landed=$base
    owe=$(( need - (landed - base) ))
    [ "$owe" -gt 0 ] || owe=0
    # A sum past what a count holds would wrap; records that large say no size this rule can count.
    if ! fits_in_count "$owed" "$owe"; then unsized="$unsized $id"; continue; fi
    owed=$(( owed + owe ))
    n=$((n + 1))
  done < <(size_files)
  # An X-ray fetch, at the sizes its list stated when grid/run-xray-chain.sh sent it.
  if [ -f "$REPO/grid/logs/XRAY_SIZES.txt" ]; then
    while read -r job need _; do
      [ "$job" != "$self" ] || continue
      case "$live" in *" $job "*) ;; *) continue ;; esac
      case "$counted" in *" $job "*) continue ;; esac
      counted="$counted$job "
      if ! is_count "$need" || ! fits_in_count "$owed" "$need"; then
        case "$unsized" in *" xray_chain"*) ;; *) unsized="$unsized xray_chain" ;; esac
        continue
      fi
      owed=$(( owed + need ))
      n=$((n + 1))
    done < "$REPO/grid/logs/XRAY_SIZES.txt"
  fi
  [ -f "$REPO/grid/logs/GATE_JOBS.txt" ] || { echo "$owed $n${unsized}"; return 0; }
  while read -r job _ what _; do
    [ "$job" != "$self" ] || continue
    case "$live" in *" $job "*) ;; *) continue ;; esac
    case "$counted" in *" $job "*) continue ;; esac
    counted="$counted$job "
    case "$what" in
      dp_*)
        id=${what#dp_}
        # Sent under this rule and not started yet: it decides for itself when it starts.
        [ "$(awk '{ print $1; exit }' "$DATA/$id/meta/QUEUED" 2>/dev/null)" != "$job" ] || continue
        need=$(stated_bytes "$id")
        is_count "$need" || { unsized="$unsized $id"; continue; }
        landed=$(landing_bytes "$id")
        [ -n "$landed" ] || landed=0
        owe=$(( need - landed ))
        [ "$owe" -gt 0 ] || owe=0
        if ! fits_in_count "$owed" "$owe"; then unsized="$unsized $id"; continue; fi
        owed=$(( owed + owe ))
        n=$((n + 1)) ;;
      # sent before its size was recorded: nothing says what it still has to land
      xr_fetch) case "$unsized" in *" xray_chain"*) ;; *) unsized="$unsized xray_chain" ;; esac ;;
    esac
  done < "$REPO/grid/logs/GATE_JOBS.txt"
  echo "$owed $n${unsized}"
}

plain_words() {  # plain_words TEXT: lower-case letters, digits, spaces and semicolons alone, as status keeps them
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | LC_ALL=C tr -c 'a-z0-9 ;' ' ' | tr -s ' ' | sed 's/^ //; s/ $//'
}

size_refused() {  # size_refused ID REASON: 4, the refusal's line in the shape grid/log-shapes.awk keeps, and its REFUSED line
  mkdir -p "$DATA/$1/meta" && echo "${SLURM_JOB_ID:-none} - - $(date -u '+%FT%TZ') -" > "$DATA/$1/meta/REFUSED"
  echo "$1: refused; $(plain_words "${2:-the size reader said nothing}") at $(date -u '+%FT%TZ')"
  return 4
}

room_words() {  # room_words FROM: where the free figure was read
  case "$1" in quota) echo "under the quota" ;; *) echo "on the volume" ;; esac
}

admit_fetch() {  # admit_fetch ID TOTAL NEED HOW: 0 when the fetch may start, 4 when it is refused, with one line either way
  local id=$1 total=$2 need=$3 how job=${SLURM_JOB_ID:-none} said room from owed n unsized free base verdict
  how=$(plain_words "$4")
  mkdir -p "$DATA/$id/meta"
  # One decision at a time, so two fetches starting together never each find the other unadmitted.
  exec 8> "$DATA/.size-rule.lock"
  if ! flock -w "${SIZE_RULE_WAIT:-900}" 8; then
    exec 8>&-
    size_refused "$id" "another fetch held the size check for ${SIZE_RULE_WAIT:-900} seconds"
    return
  fi
  # VOLUME is the caller's, as DATA is.
  # shellcheck disable=SC2153
  read -r room from <<< "$(volume_free_bytes "$VOLUME")"
  if [ -z "$room" ]; then
    exec 8>&-
    size_refused "$id" "the room under the quota could not be read"
    return
  fi
  if ! said=$(owed_by_running "$job"); then
    exec 8>&-
    size_refused "$id" "the queue of slurm could not be read so what the running fetches owe is not known"
    return
  fi
  read -r owed n unsized <<< "$said"
  if [ -n "$unsized" ]; then
    exec 8>&-
    size_refused "$id" "the running fetch of $unsized states no size so nothing is admitted beside it"
    return
  fi
  free=$(( room > owed ? room - owed : 0 ))
  # What the landing holds now is the base its growth is measured from; read as nothing, every
  # byte already there would later count as this fetch's and leave its owed short.
  base=$(landing_bytes "$id")
  if [ -z "$base" ]; then
    exec 8>&-
    size_refused "$id" "what its landing holds could not be read"
    return
  fi
  if [ "$need" -le "$free" ]; then
    verdict=admitted
    echo "admitted $job $need $base $(date -u '+%FT%TZ') $total" > "$DATA/$id/meta/SIZE"
  else
    verdict=refused
    echo "$job $need $free $(date -u '+%FT%TZ') $total" > "$DATA/$id/meta/REFUSED"
  fi
  exec 8>&-
  # Both figures rounded the same way, up, so a need that fits never reads as more than the room;
  # a refusal rounds the need up and the room down, so it never reads as fitting.
  if [ "$verdict" = admitted ]; then
    echo "$id: admitted; it needs $(gb_up "$need") gb of its $(gb_up "$total") gb by $how and $(gb_up "$free") gb is free $(room_words "$from") after $(gb_up "$owed") gb owed to $(running_fetches "$n") at $(date -u '+%FT%TZ')"
    return 0
  fi
  echo "$id: refused for space; it needs $(gb_up "$need") gb of its $(gb_up "$total") gb by $how and only $(gb_down "$free") gb is free $(room_words "$from") after $(gb_up "$owed") gb owed to $(running_fetches "$n") at $(date -u '+%FT%TZ')"
  return 4
}

admitted_before() {  # admitted_before ID: whether this job, restarted by Slurm, holds the admission of ID
  # The restart count as well as the id, so a job id Slurm hands out again once its counter wraps
  # never inherits an old admission.
  local state job
  [ "${SLURM_RESTART_COUNT:-0}" != 0 ] && [ -n "${SLURM_JOB_ID:-}" ] && [ -f "$DATA/$1/meta/SIZE" ] || return 1
  read -r state job _ < "$DATA/$1/meta/SIZE"
  [ "$state" = admitted ] && [ "$job" = "$SLURM_JOB_ID" ]
}

size_and_admit() {  # size_and_admit ID COMMAND...: the exact size COMMAND reads, then the rule's decision (0 go, 4 refused)
  local id=$1 said rc total need how
  shift
  # A job Slurm requeued, after a preemption or a node's failure, runs this script again under its
  # own id. The room it was admitted to is still held for it, at what it had to land less what its
  # landing has grown by since, so it goes on under that admission: deciding again would count the
  # part it landed twice, and a refusal then would leave that part stranded.
  if admitted_before "$id"; then
    echo "$id: admitted already; job $SLURM_JOB_ID restarted and keeps the room it was given at $(date -u '+%FT%TZ')"
    return 0
  fi
  said=$("$@")
  rc=$?
  said=$(printf '%s\n' "$said" | tail -n 1)
  if [ "$rc" != 0 ]; then
    size_refused "$id" "${said:-the size reader ended with exit $rc and said nothing}"
    return
  fi
  read -r total need how <<< "$said"
  if ! is_count "$total" || ! is_count "$need"; then
    size_refused "$id" "the size reader gave no size"
    return
  fi
  admit_fetch "$id" "$total" "$need" "$how"
}

mark_queued() {  # mark_queued ID JOB: the QUEUED line of a fetch sent under the rule, which decides when it starts
  # Never a data root of its own making: where there is none, as off the grid, the job is left
  # unmarked and counted at its line's stated size, which errs toward refusing.
  [ -d "$DATA" ] || return 0
  mkdir -p "$DATA/$1/meta" && echo "$2 $(date -u '+%FT%TZ')" > "$DATA/$1/meta/QUEUED"
}

# The owner's readout of the volume (2026-10-23: "is there something similar to my oschome drive? if
# not could you spin one up?"): WSU's wsuquota reads only the home directory, so this prints its
# layout for the lab volume from the three attributes the rule reads, then what the admitted fetches
# still running owe and the room left for a new one, the figure admit_fetch decides against. One
# reading, so the readout and the rule never disagree. Called by grid/oschome-quota.sh in the owner's
# shell and by grid/gate.sh's status word, which names no folder, so the title is the caller's.
quota_readout() {  # quota_readout VOLUME TITLE: the readout; 1 when the volume has no quota that can be read
  local volume=$1 quota used files files_said="" max_files said owed n unsized
  quota=$(xattr_digits ceph.quota.max_bytes "$volume")
  used=$(xattr_digits ceph.dir.rbytes "$volume")
  files=$(xattr_digits ceph.dir.rfiles "$volume")
  max_files=$(xattr_digits ceph.quota.max_files "$volume")
  echo "$2"
  if [ -z "$quota" ] || [ "$quota" = 0 ] || [ -z "$used" ]; then
    echo "The CephFS quota or its use could not be read, so the size rule admits no fetch:"
    xattr_words ceph.quota.max_bytes "$volume" | sed 's/^/  /'
    xattr_words ceph.dir.rbytes "$volume" | sed 's/^/  /'
    return 1
  fi
  # wsuquota's own layout: two decimals, a 96-cell bar filled by the share used, rounded down. A
  # limit on the number of files, where the quota sets one, is shown and not counted by the rule.
  [ -n "$files" ] || files_said=$(xattr_words ceph.dir.rfiles "$volume")
  awk -v q="$quota" -v u="$used" -v f="$files" -v fw="$files_said" -v mf="$max_files" 'BEGIN {
    free = q > u ? q - u : 0
    printf "Used  = %.2f%%  %.2fgb\n", 100 * u / q, u / 1e9
    printf "Free  = %.2f%%  %.2fgb\n", 100 * free / q, free / 1e9
    printf "Total =         %.2fgb\n", q / 1e9
    if (f != "") printf "File Count =    %.0f\n", f
    else if (fw ~ /no count|not read/) printf "File Count =    not read; %s\n", fw
    if (mf != "" && mf != 0) printf "File Limit =    %.0f, which the size rule does not count\n", mf
    cells = int(96 * u / q); if (cells > 96) cells = 96
    bar = "["; for (i = 0; i < 96; i++) bar = bar (i < cells ? "#" : "-"); print bar "]"
  }'
  if ! said=$(owed_by_running ""); then
    echo "Owed  =         not known; squeue did not answer, so the size rule admits no fetch now"
    return 0
  fi
  read -r owed n unsized <<< "$said"
  if [ -n "$unsized" ]; then
    echo "Owed  =         not known; the running fetch of $unsized states no size, so the size rule admits nothing beside it"
    return 0
  fi
  awk -v q="$quota" -v u="$used" -v o="$owed" -v n="$n" 'BEGIN {
    room = q - u - o; if (room < 0) room = 0
    printf "Owed  =         %.2fgb still to land for %d running fetch%s\n", o / 1e9, n, (n == 1 ? "" : "es")
    printf "Room  =         %.2fgb for a new fetch, which lands whole or not at all\n", room / 1e9
  }'
}
