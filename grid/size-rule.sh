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
# the login node, and by Python's os.getxattr on a node with no getfattr (RULE_PYTHON, which
# grid/platform-fetch.sbatch sets to the acq environment's). Where neither runs, nothing is read,
# and df is never asked in its place on a mount that may be CephFS, kernel or FUSE. Every figure
# the rule counts, the quota and each ceph.dir.rbytes, is read whole, every byte past any NUL, and
# taken only as a count of at most 18 digits with no other byte (xattr_whole, is_count): on
# 2026-10-23 getfattr in the owner's shell printed the volume's ceph.dir.rbytes as 48 digits and
# its ceph.dir.rfiles as 25, and bash's arithmetic wraps such a number without a word, which would
# have read the use as less than nothing and the room as 2.5 EB, so every fetch would have been
# admitted. A NUL is no exception, after the digits too: CephFS's kernel client through Linux 5.2
# wrote these values with snprintf straight into the reader's buffer, which puts a NUL over the
# last digit where that buffer is just the value's length, so the figure would read a tenth of
# what it is (#180). A reading that is no count admits nothing, and the readout says which one it
# was. The file count and the file limit, which the readout shows and the rule does not count,
# are read up to their first NUL.
# The status word then found the same 48 digits on the login node, where every folder under the
# volume read clean (issue #170). CephFS keeps the use as one 64-bit count and also gives it as the
# folder's size where the mount reports a folder's recursive size as its size, a path that does not
# pass through getxattr; so where the volume's attribute is no count, or a count below the data
# root's, which the volume holds, its use is read by stat, once the data root, inside the volume on
# its mount and holding at least a gigabyte, shows that stat gives a folder's ceph.dir.rbytes
# (volume_used). Python cannot be that second reader there, since warrior kills it by name. The
# grid's mount gives a folder's entry count as its size instead (the status word at 17:15 UTC gave
# the volume 3 and the data root 126; issue #172), so where stat cannot stand in, the use is the sum
# of what the volume's own entries hold, each folder by its ceph.dir.rbytes, which reads clean below
# the volume, and each file or link by its own size: taken only where every entry reads whole on the
# volume's own mount, none of them a mount the mount table lists, they are as many as stat gives as
# the volume's size, and the one that holds the data root holds no less than the data root's own
# ceph.dir.rbytes, read whole before them (use_by_entries), so an entry left out, the one that holds
# the data root cut short, or a folder mounted over one of them admits nothing.
#
# CephFS carries new bytes, and each half of a move from one folder to another, up to the folders
# above them with a lag of seconds, so one reading of the use can miss bytes a landing already
# shows, which would then count neither as owed nor as used, or miss a set halfway through a move
# between two of the volume's own entries. A fetch's decision therefore reads what the running
# fetches owe first and the room after it, twice, a minute apart, and keeps the smaller; where the
# use is the sum of the volume's own entries, the second reading counts each entry at the larger of
# its two readings, and one gone since at its first (settled_room, entries_census, #180). Bytes a
# landing shows when it is read are then counted as used unless CephFS carries them up more than a
# minute late, and a set moved between two entries, once or in several moves the same way, is
# missed only where the entry it reached still does not show it a minute after the entry it left
# showed it gone; a set moved there and back within the minute can still hide, and one moved while
# a fetch decides can count twice and refuse it. A running fetch is credited what its own landing
# shows, never capped by what the folders above it show, since they hold other writers' bytes too
# and such a cap could still credit bytes they do not show: the minute stands in for it. And
# CephFS holds a write to every quota on its path, so a byte quota of its own on the data root, on a
# folder between it and the volume, or on a folder above the volume up to the root of the volume's
# mount, would stop part-way a fetch the volume's quota leaves room for: the rule reads no such
# quota and admits nothing while one stands or cannot be read, nor while the data root is no folder
# inside the volume on its mount, whose quota is then not the one a fetch there meets
# (quota_below). A VOLUME or DATA_ROOT that names the wrong folder therefore refuses every fetch
# rather than read another room. A quota on a folder above the root of the mount, which the client
# does not show, is not read.
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
# REPO name the folders. The tools, the Python that reads the attributes where no getfattr runs,
# the mount table and the minute between the room's two readings are this file's own: a test
# stands in for them, through GETFATTR, XATTR_PYTHON, STAT, SQUEUE, DF, MOUNTINFO and
# SIZE_RULE_SETTLE, only where it sets SIZE_RULE_STAND_INS=yes, since a job inherits the
# environment it was sent from, and a stray STAT or MOUNTINFO there would change what the rule
# reads, unseen (#180). So is the user whose jobs squeue lists, which a test names through USER, and
# a shell function the environment exports under the name of a tool the rule runs is dropped, since
# bash would run it in the tool's place. A job whose node may have no getfattr and no python3 names
# a Python of its own in RULE_PYTHON after sourcing this file, as grid/platform-fetch.sbatch and
# grid/unpack.sbatch do.
if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then
  RULE_GETFATTR=${GETFATTR:-getfattr} RULE_STAT=${STAT:-stat} RULE_SQUEUE=${SQUEUE:-squeue} RULE_DF=${DF:-df}
  RULE_MOUNTINFO=${MOUNTINFO:-/proc/self/mountinfo} RULE_SETTLE=${SIZE_RULE_SETTLE:-60}
  RULE_PYTHON=${XATTR_PYTHON:-python3} RULE_USER=${USER:-}
else
  RULE_GETFATTR=getfattr RULE_STAT=stat RULE_SQUEUE=squeue RULE_DF=df
  RULE_MOUNTINFO=/proc/self/mountinfo RULE_SETTLE=60 RULE_PYTHON=python3 RULE_USER=""
  unset -f getfattr stat squeue df python3 sleep id awk tr readlink mktemp sed sort rm tail date mkdir cut od
fi
# The file settled_room hands a census from the room's first reading to its second through
# (entries_census): its own, never the environment's.
RULE_CENSUS_IN="" RULE_CENSUS_OUT=""

xattr_bytes() {  # xattr_bytes NAME FOLDER: every byte of a CephFS attribute's value, NULs and all, nothing where it is not there; 2 where no reader runs or the read fails
  local said
  # An attribute that is not there is nothing, and so is one on a filesystem that keeps no CephFS
  # attributes at all, as on a mount df answers for; a read that fails otherwise, as on a folder the
  # user may not read or where the metadata server does not answer, is no reading at all, never a
  # quota that is not there. getfattr ends 1 for each, so its own words in C's locale tell them
  # apart, while the value goes straight on, NULs and all.
  if command -v "$RULE_GETFATTR" > /dev/null 2>&1; then
    { said=$(LC_ALL=C "$RULE_GETFATTR" --only-values -n "$1" "$2" 2>&1 >&3 3>&-) && return 0; } 3>&1
    case $said in *": $1: No such attribute" | *": $1: Operation not supported") return 0 ;; esac
    return 2
  fi
  "$RULE_PYTHON" -c '
import errno, os, sys
try:
    sys.stdout.buffer.write(os.getxattr(sys.argv[2], sys.argv[1]))
except OSError as error:
    sys.exit(0 if error.errno in (errno.ENODATA, errno.EOPNOTSUPP) else 3)' "$1" "$2" 2>/dev/null || return 2
}

xattr_value() {  # xattr_value NAME FOLDER: a CephFS attribute's value up to its first NUL; 2 where no reader runs or the read fails
  # Cut at the first NUL here and nowhere else: bash drops a NUL from what a command prints, and
  # would join whatever follows it to the digits before it; a line break inside is kept, so a value
  # that holds one is no count rather than the part before it.
  xattr_bytes "$1" "$2" | { IFS= read -r -d '' value; printf '%s' "$value"; }
  return "${PIPESTATUS[0]}"
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

xattr_digits() {  # xattr_digits NAME FOLDER: a CephFS attribute as a count, or nothing where it is not there; 2 where no reader runs or the read fails, 3 when it reads as no count
  local value
  value=$(xattr_value "$1" "$2") || return 2
  [ -n "$value" ] || return 0
  # Never part of a value taken as the whole: what is no count is no reading.
  is_count "$value" || return 3
  echo "$value"
}

xattr_whole() {  # xattr_whole NAME FOLDER: the attribute as a count where every byte of it is a digit; else nothing, ending 2 where no reader runs or the read fails and 3 where it is there and no count
  local value
  # Every byte, past any NUL, so a NUL cannot cut a count short unseen: a NUL, a line break or any
  # other byte that is no digit becomes x, and a value that holds one is no count. A NUL after the
  # digits is no exception: CephFS's kernel client through Linux 5.2 wrote these values with
  # snprintf, which puts a NUL over the last digit where the reader's buffer is just the value's
  # length, and the count would read a tenth of what it is. Neither getfattr nor Python asks with
  # such a buffer, so a whole value refused costs nothing.
  value=$(xattr_bytes "$1" "$2" | LC_ALL=C tr -c '0-9' 'x'; exit "${PIPESTATUS[0]}") || return 2
  [ -n "$value" ] || return 0
  is_count "$value" || return 3
  echo "$value"
}

whole_words() {  # whole_words NAME FOLDER: what one whole reading of the attribute gave, in words, for the readout
  local value others
  value=$(xattr_whole "$1" "$2")
  case $? in
    2) echo "$1 was not read; no reader ran, or its read failed" ;;
    3) value=$(xattr_bytes "$1" "$2" | LC_ALL=C tr -c '0-9' 'x')
       others=${value//[0-9]/}
       echo "$1 reads as no count: ${#value} bytes, ${#others} of them no digit, where a count is at most 18 digits and nothing else" ;;
    *) echo "$1 reads ${value:-as not there}" ;;
  esac
}

xattr_words() {  # xattr_words NAME FOLDER: what one reading of the attribute gave, in words, for the readout
  local value
  value=$(xattr_digits "$1" "$2")
  case $? in
    2) echo "$1 was not read; no reader ran, or its read failed" ;;
    3) value=$(xattr_value "$1" "$2")
       echo "$1 reads as no count, ${#value} characters up to its first NUL where a count has at most 18 digits" ;;
    *) echo "$1 reads ${value:-as not there}" ;;
  esac
}

size_by_stat() {  # size_by_stat FOLDER: the size of the folder FOLDER names, links followed, where stat gives a count, else nothing
  local size
  # -L, since /rs/rs_grp_oschome may be a link into /.rs/volumes, and a link's own size is the
  # length of the path it holds, which would read as a volume of a few bytes.
  size=$("$RULE_STAT" -L -c %s "$1" 2>/dev/null) || return 0
  if is_count "$size"; then echo "$size"; fi
}

device_of() {  # device_of FOLDER: the device stat gives the folder FOLDER names, links followed, where it is a count, else nothing
  local device
  device=$("$RULE_STAT" -L -c %d "$1" 2>/dev/null) || return 0
  if is_count "$device"; then echo "$device"; fi
}

data_root_on() {  # data_root_on VOLUME: 0 where DATA names a folder inside VOLUME on its mount; 1 where DATA names no folder, 2 where it lies outside VOLUME, 3 where it lies on another device
  local volume data device
  [ -n "${DATA:-}" ] && [ -d "$DATA" ] || return 1
  # Inside once every link and .. is resolved, so neither can name a folder elsewhere, and with the
  # slash, so a sibling such as /rs/rs_grp_oschome2 is not inside /rs/rs_grp_oschome.
  volume=$(readlink -f -- "$1" 2>/dev/null) && data=$(readlink -f -- "$DATA" 2>/dev/null) || return 2
  case "$data" in "${volume%/}"/?*) ;; *) return 2 ;; esac
  # And on the same device, since a folder mounted inside the volume shows nothing of the volume's mount.
  device=$(device_of "$1")
  [ -n "$device" ] && [ "$(device_of "$DATA")" = "$device" ] || return 3
}

data_root_bytes() {  # data_root_bytes VOLUME: the data root's ceph.dir.rbytes, every byte of it a digit, where the data root lies inside VOLUME on its mount, a floor under what VOLUME and its entry that holds the data root hold; else nothing, ending 3 where it lies there and its attribute is there and no count
  # Read whole, since a floor cut short at a NUL would pass a reading cut short as well.
  data_root_on "$1" || return 0
  xattr_whole ceph.dir.rbytes "$DATA"
}

holding_entry() {  # holding_entry VOLUME: the name of VOLUME's own entry the data root lies under, every link resolved, where the data root lies inside VOLUME on its mount; else nothing
  local volume data rest
  data_root_on "$1" || return 0
  volume=$(readlink -f -- "$1" 2>/dev/null) && data=$(readlink -f -- "$DATA" 2>/dev/null) || return 0
  rest=${data#"${volume%/}"/}
  printf '%s' "${rest%%/*}"
}

mount_points() {  # mount_points: every mount point the mount table lists, as the kernel writes it there, one a line; fails where the table cannot be read
  # The kernel writes a space, a tab, a line break and a backslash in a mount point as \ooo, so
  # every point is one line and its fifth field.
  awk '{ print $5 }' "$RULE_MOUNTINFO" 2> /dev/null
}

is_mount_point() {  # is_mount_point POINTS PATH: whether POINTS, mount_points' list, holds PATH, a path whose links are resolved, as the kernel resolves a mount point's
  local escaped=${2//\\/\\134}
  escaped=${escaped// /\\040}
  escaped=${escaped//$'\t'/\\011}
  escaped=${escaped//$'\n'/\\012}
  case $'\n'"$1"$'\n' in *$'\n'"$escaped"$'\n'*) return 0 ;; esac
  return 1
}

stat_gives_rbytes() {  # stat_gives_rbytes VOLUME: where stat gives a folder's ceph.dir.rbytes as its size on VOLUME's mount, as the data root shows, the data root's bytes, the lower of two readings; else nothing, ending 1
  local before size after low high
  # Shown on the data root, which lies inside the volume on the same mount and whose attribute
  # reads: a mount that gives a folder's entry count as its size, as the kernel client does under
  # its norbytes option, fails here instead of being read as a volume of a few bytes.
  data_root_on "$1" || return 1
  before=$(xattr_whole ceph.dir.rbytes "$DATA") && [ -n "$before" ] || return 1
  size=$(size_by_stat "$DATA")
  after=$(xattr_whole ceph.dir.rbytes "$DATA") && [ -n "$after" ] || return 1
  [ -n "$size" ] || return 1
  # Between two readings of the attribute, so bytes landing meanwhile never fail the check; and of
  # at least a gigabyte, more than any folder holds entries, since an empty data root holds as many
  # bytes as entries, none, and would pass on a mount that gives the count.
  if [ "$before" -le "$after" ]; then low=$before high=$after; else low=$after high=$before; fi
  [ "$low" -ge 1000000000 ] && [ "$size" -ge "$low" ] && [ "$size" -le "$high" ] || return 1
  echo "$low"
}

volume_entries() {  # volume_entries VOLUME: every entry of VOLUME's own folder, hidden ones too, each ended by a NUL
  # In a subshell, so the caller's settings stay as they were: the hf-token route decides under
  # set -f, which would leave the pattern as it stands. A * never matches . or .., dotglob or not.
  (
    set +f
    shopt -s nullglob dotglob
    for entry in "${1%/}"/*; do printf '%s\0' "$entry"; done
  )
}

entry_bytes() {  # entry_bytes ENTRY DEVICE: what the volume's entry ENTRY holds by CephFS, where it lies on DEVICE and reads as a count; else nothing, ending 2 where it lies on another device
  local device bytes
  # Only on the volume's own mount, since a folder mounted there would hide what the volume holds
  # under it. A folder by its ceph.dir.rbytes read whole; a file or a link by its own size, which
  # CephFS counts, a link's being the length of the path it holds.
  device=$("$RULE_STAT" -c %d "$1" 2>/dev/null)
  is_count "$device" || return 0
  [ "$device" = "$2" ] || return 2
  if [ -d "$1" ] && [ ! -L "$1" ]; then
    bytes=$(xattr_whole ceph.dir.rbytes "$1")
  else
    bytes=$("$RULE_STAT" -c %s "$1" 2>/dev/null)
  fi
  if is_count "$bytes"; then echo "$bytes"; fi
}

entries_census() {  # entries_census VOLUME: "<entries> <folders> <elsewhere> <unread> <bytes> <held>", VOLUME's own entries, the folders among them, those on another mount, those that cannot be read or read no count, what the others hold and what the one that holds the data root holds, - where none reads as it; 1 where stat gives no device for VOLUME, 2 where the mount table cannot be read
  local device volume points holding entry name bytes before key rc entries=0 folders=0 elsewhere=0 unread=0 sum=0 held=-
  local -A earlier=() listed=()
  device=$(device_of "$1")
  [ -n "$device" ] || return 1
  volume=$(readlink -f -- "$1" 2>/dev/null) || return 1
  points=$(mount_points) || return 2
  holding=$(holding_entry "$1")
  # The second of settled_room's two readings counts each entry at the larger of this census and
  # the first's, and an entry listed then and gone now at its reading then, so a set moving between
  # two entries counts where the one it left still showed it or the one it reached already does
  # (#180). A record cut short or no count, or a first census that cannot be read, leaves an entry
  # unread.
  if [ -n "$RULE_CENSUS_IN" ]; then
    if [ -r "$RULE_CENSUS_IN" ]; then
      # read leaves in name what it found after the last NUL, nothing where the file ended whole
      while IFS= read -r -d '' name; do
        IFS= read -r -d '' bytes || bytes=""
        if ! is_count "$bytes"; then
          unread=$(( unread + 1 ))
          continue
        fi
        before=${earlier["$name"]:-}
        [ -n "$before" ] && [ "$before" -ge "$bytes" ] || earlier["$name"]=$bytes
      done < "$RULE_CENSUS_IN"
      [ -z "$name" ] || unread=$(( unread + 1 ))
    else
      unread=$(( unread + 1 ))
    fi
  fi
  while IFS= read -r -d '' entry; do
    entries=$(( entries + 1 ))
    if [ -d "$entry" ] && [ ! -L "$entry" ]; then folders=$(( folders + 1 )); fi
    name=${entry##*/}
    listed["$name"]=1
    # A mount at the entry, which a kernel that gives every CephFS folder the same device hides
    # from stat, and one on another device apart; one whose count would take the sum past 18
    # digits, which bash wraps without a word, as one that reads no count.
    if is_mount_point "$points" "${volume%/}/$name"; then
      elsewhere=$(( elsewhere + 1 ))
      continue
    fi
    bytes=$(entry_bytes "$entry" "$device")
    rc=$?
    if [ "$rc" = 2 ]; then
      elsewhere=$(( elsewhere + 1 ))
      continue
    fi
    # Settled_room's first reading keeps what each entry read, and an entry it cannot keep is unread.
    if [ -n "$bytes" ] && [ -n "$RULE_CENSUS_OUT" ]; then
      printf '%s\0%s\0' "$name" "$bytes" >> "$RULE_CENSUS_OUT" || bytes=""
    fi
    before=${earlier["$name"]:-}
    if [ -n "$bytes" ] && [ -n "$before" ] && [ "$before" -gt "$bytes" ]; then bytes=$before; fi
    if [ -n "$bytes" ] && fits_in_count "$sum" "$bytes"; then
      sum=$(( sum + bytes ))
      [ "$name" != "$holding" ] || held=$bytes
    else
      unread=$(( unread + 1 ))
    fi
  done < <(volume_entries "$1")
  for key in "${!earlier[@]}"; do
    [ -z "${listed["$key"]:-}" ] || continue
    before=${earlier["$key"]}
    if fits_in_count "$sum" "$before"; then sum=$(( sum + before )); else unread=$(( unread + 1 )); fi
  done
  echo "$entries $folders $elsewhere $unread $sum $held"
}

use_by_entries() {  # use_by_entries VOLUME: "<bytes> <entries> <folders> <held> <floor>", what VOLUME holds as the sum of what its own entries hold, where that sum is a reading of it, with the figures that show it: its entries, the folders among them, what the one that holds the data root holds and the data root's ceph.dir.rbytes; else nothing, ending 1
  local floor entries folders elsewhere unread sum held
  # The data root's figure first, so bytes landing under it while the entries are read can only
  # raise what the entry that holds it holds above it.
  floor=$(data_root_bytes "$1")
  read -r entries folders elsewhere unread sum held <<< "$(entries_census "$1")"
  # Every entry read whole on the volume's own mount (a census that failed gives nothing, which is
  # no 0), and as many entries as the mount counts, where it gives a folder's entry count as its
  # size, so the listing left none out; and the entry that holds the data root, the one entry a
  # figure of its own can check, holds no less than the data root, so it was not cut short.
  [ "$elsewhere" = 0 ] && [ "$unread" = 0 ] || return 1
  [ "$(size_by_stat "$1")" = "$entries" ] || return 1
  [ -n "$floor" ] && is_count "$held" && [ "$held" -ge "$floor" ] || return 1
  echo "$sum $entries $folders $held $floor"
}

volume_used() {  # volume_used VOLUME: "<bytes> attribute", "<bytes> stat" or "<bytes> entries <entries> <folders> <held> <floor>", what VOLUME holds, with the figures use_by_entries checked a sum by, or nothing where its attribute is not there; 2 when no reader ran or its read failed, 3 when no reading counts
  local used rc floor
  # Whole, so a NUL that cut it short reads as no count, never as a tenth of the use (#180).
  used=$(xattr_whole ceph.dir.rbytes "$1")
  rc=$?
  [ "$rc" != 2 ] || return 2
  [ "$rc" = 3 ] || [ -n "$used" ] || return 0
  # The volume holds the data root, so a count below the data root's is no reading of the volume,
  # whatever cut it short, as a NUL among its digits would; nor is one beside a data root whose own
  # attribute is there and no count, since nothing then shows it was not cut short.
  if [ "$rc" = 0 ] && floor=$(data_root_bytes "$1"); then
    if [ -z "$floor" ] || [ "$used" -ge "$floor" ]; then
      echo "$used attribute"
      return 0
    fi
  fi
  if floor=$(stat_gives_rbytes "$1"); then
    used=$(size_by_stat "$1")
    if [ -n "$used" ] && [ "$used" -ge "$floor" ]; then
      echo "$used stat"
      return 0
    fi
  fi
  # Where stat gives a folder's entry count as its size, as on the grid (#172), what the volume's
  # own entries hold, whose attributes read where the volume's does not.
  used=$(use_by_entries "$1") || return 3
  echo "${used%% *} entries ${used#* }"
}

getfattr_bytes() {  # getfattr_bytes NAME FOLDER: "<n> bytes, <text>", every byte getfattr gives, one that is no printable ASCII as \ooo, the first 96 shown
  # The value whole, past any NUL, so the readout shows what the reading rule refused.
  command -v "$RULE_GETFATTR" > /dev/null 2>&1 || return 0
  "$RULE_GETFATTR" --only-values -n "$1" "$2" 2>/dev/null | od -An -v -tu1 | awk '
    { for (i = 1; i <= NF; i++) { n++; b = $i + 0
        if (n <= 96) text = text ((b > 32 && b < 127 && b != 92) ? sprintf("%c", b) : sprintf("\\%03o", b)) } }
    END { printf "%d byte%s, %s%s\n", n, (n == 1 ? "" : "s"), text, (n > 96 ? " and more" : "") }'
}

stat_figure() {  # stat_figure FORMAT FOLDER: what stat gives for FORMAT, links followed, its digits and minus signs alone, the first 40
  "$RULE_STAT" -L -c "$1" "$2" 2>/dev/null | LC_ALL=C tr -dc '0-9-' | cut -c 1-40
}

mount_kind() {  # mount_kind FOLDER: the kind of mount stat names for FOLDER, letters, digits and . / _ - alone, else nothing
  local kind
  kind=$("$RULE_STAT" -f -c %T "$1" 2>/dev/null | LC_ALL=C tr -dc 'a-zA-Z0-9./_-' | cut -c 1-40)
  echo "${kind:-nothing}"
}

stat_words() {  # stat_words VOLUME: what stat gives for VOLUME and for the data root, and why the data root shows nothing of the volume's mount where it does not, in words
  local size said data_size data_bytes device data_device
  size=$(stat_figure %s "$1")
  said="stat gives the volume's size as ${size:-nothing}"
  data_root_on "$1"
  case $? in
    0) data_size=$(stat_figure %s "$DATA")
       data_bytes=$(xattr_whole ceph.dir.rbytes "$DATA") || [ $? != 3 ] || data_bytes="no count"
       echo "$said and the data root's as ${data_size:-nothing} on a mount it calls $(mount_kind "$1"), where the data root's ceph.dir.rbytes is ${data_bytes:-unread}" ;;
    3) device=$(stat_figure %d "$1")
       data_device=$(stat_figure %d "$DATA")
       echo "$said on a mount it calls $(mount_kind "$1"), device ${device:-nothing}, and the data root lies on device ${data_device:-nothing}, another mount, so it shows nothing of the volume's" ;;
    2) echo "$said on a mount it calls $(mount_kind "$1"), and the data root, its links and any .. resolved, is no folder inside the volume, so it shows nothing of the volume's mount" ;;
    *) echo "$said on a mount it calls $(mount_kind "$1"), with no data root to show what stat gives a folder on the volume's mount" ;;
  esac
}

counted() {  # counted N ONE MANY: "1 ONE" or "N MANY"
  if [ "$1" = 1 ]; then echo "1 $2"; else echo "$1 $3"; fi
}

entries_words() {  # entries_words VOLUME: what the volume's own entries hold and why their sum is no reading of it, in counts and never names, since the status word leaves the grid
  local census entries folders elsewhere unread sum held size floor said
  census=$(entries_census "$1")
  case $? in
    1) echo "its own entries cannot be summed, since stat gives it no device"; return 0 ;;
    2) echo "its own entries cannot be summed, since the mount table cannot be read to show none of them is a mount"; return 0 ;;
  esac
  read -r entries folders elsewhere unread sum held <<< "$census"
  if [ "$entries" = 0 ]; then
    echo "its folder lists no entry to sum, as one that cannot be read lists none"
    return 0
  fi
  said="its own $(counted "$entries" entry entries), $(counted "$folders" "of them a folder" "of them folders"), hold $sum where they read"
  size=$(size_by_stat "$1")
  floor=$(data_root_bytes "$1")
  if [ "$elsewhere" != 0 ]; then
    echo "$said, and $(counted "$elsewhere" lies lie) on another mount, which hides what the volume holds under it, so their sum is no reading of it"
  elif [ "$unread" != 0 ]; then
    echo "$said, and $(counted "$unread" "cannot be read or reads" "cannot be read or read") no count, so their sum is no reading of it"
  elif [ "$size" != "$entries" ]; then
    size=$(stat_figure %s "$1")
    echo "$said, and stat gives the volume's size as ${size:-nothing} where its entries are $entries, so the listing cannot be checked against it"
  elif [ -z "$floor" ]; then
    echo "$said, with no data root inside it on its mount whose ceph.dir.rbytes reads whole as a count, to show their sum leaves none short"
  elif ! is_count "$held"; then
    echo "$said, with none of them read as the one that holds the data root, to show their sum leaves none short"
  elif [ "$held" -lt "$floor" ]; then
    echo "$said, and the one that holds the data root holds $held, less than the data root's $floor, so their sum is no reading of it"
  else
    echo "$said"
  fi
}

rbytes_words() {  # rbytes_words VOLUME: VOLUME's ceph.dir.rbytes, read whole, in words; 4 where it reads, as no count, as a count below the data root's or beside a data root whose own is not read whole as a count, and so is no reading of the volume
  local value floor
  value=$(xattr_whole ceph.dir.rbytes "$1")
  case $? in
    3) whole_words ceph.dir.rbytes "$1"; return 4 ;;
    0) [ -n "$value" ] || { whole_words ceph.dir.rbytes "$1"; return 0; } ;;
    *) whole_words ceph.dir.rbytes "$1"; return 0 ;;
  esac
  floor=$(data_root_bytes "$1")
  case $? in
    2) echo "ceph.dir.rbytes reads $value, and the data root's inside it was not read, so nothing shows it is a reading of the volume"
       return 4 ;;
    3) echo "ceph.dir.rbytes reads $value, and the data root's inside it reads as no count, so nothing shows it is a reading of the volume"
       return 4 ;;
  esac
  if [ -n "$floor" ] && [ "$value" -lt "$floor" ]; then
    echo "ceph.dir.rbytes reads $value, less than the data root's $floor inside it, so it is no reading of the volume"
    return 4
  fi
  echo "ceph.dir.rbytes reads $value"
}

use_words() {  # use_words VOLUME USED HOW: the use volume_used read, USED by HOW, or why none counts, with what getfattr and stat give where stat was asked
  local bytes
  case "$3" in
    attribute) echo "ceph.dir.rbytes reads $2"; return 0 ;;
    stat) echo "its use reads $2 as the volume's size by stat"; return 0 ;;
    entries) echo "its use reads $2 as the sum of what its own entries hold"; return 0 ;;
  esac
  rbytes_words "$1"
  [ "$?" = 4 ] || return 0
  bytes=$(getfattr_bytes ceph.dir.rbytes "$1")
  [ -z "$bytes" ] || echo "getfattr gives it as $bytes"
  stat_words "$1"
  entries_words "$1"
}

stat_note() {  # stat_note VOLUME: why the readout's Used is the volume's size by stat, and what shows that stat gives a folder's ceph.dir.rbytes
  local bytes
  bytes=$(getfattr_bytes ceph.dir.rbytes "$1")
  echo "Used is the volume's size by stat, since its $(rbytes_words "$1")${bytes:+; getfattr gives it as $bytes}"
  echo "On this mount stat gives a folder's ceph.dir.rbytes as its size: the data root's size by stat, $(size_by_stat "$DATA"), matches its own ceph.dir.rbytes read before and after"
}

entries_note() {  # entries_note VOLUME ENTRIES FOLDERS HELD FLOOR: why the readout's Used is the sum of what the volume's own entries hold, by the figures use_by_entries checked it by
  local bytes
  bytes=$(getfattr_bytes ceph.dir.rbytes "$1")
  echo "Used is the sum of what the volume's own entries hold, since its $(rbytes_words "$1")${bytes:+; getfattr gives it as $bytes}"
  echo "Each of its $(counted "$2" entry entries), $(counted "$3" "of them a folder" "of them folders"), read whole on the volume's own mount, none of them a mount, a folder by its ceph.dir.rbytes and a file or link by its size: stat gives the volume's size as $2, its count of entries, and the one that holds the data root holds $4, no less than the data root's ceph.dir.rbytes, $5"
}

quota_below() {  # quota_below VOLUME: 1 where VOLUME's is the one byte quota on the data root's path up to the root of VOLUME's mount; else 0 where the data root, or a folder above it inside VOLUME, carries one of its own, 2 where one of theirs cannot be read whole, 3 where a folder above VOLUME on its mount carries one, 4 where one of theirs, or the mount table, cannot be read, 5 where the data root is no folder inside VOLUME on its mount
  local volume folder value points
  data_root_on "$1" || return 5
  volume=$(readlink -f -- "$1" 2>/dev/null) && folder=$(readlink -f -- "$DATA" 2>/dev/null) || return 2
  volume=${volume%/}
  # From the data root up, every link resolved, to VOLUME's own folder, whose quota is the one the
  # rule reads. 0 is none.
  while [ "$folder" != "$volume" ] && [ "${#folder}" -gt "${#volume}" ]; do
    value=$(xattr_whole ceph.quota.max_bytes "$folder") || return 2
    [ -z "$value" ] || [ "$value" = 0 ] || return 0
    folder=${folder%/*}
  done
  # Then on above VOLUME to the root of its mount, the root among them, where the mount table puts
  # it: a quota there binds a fetch as well.
  points=$(mount_points) || return 4
  folder=$volume
  until is_mount_point "$points" "${folder:-/}"; do
    [ -n "$folder" ] || return 4
    folder=${folder%/*}
    value=$(xattr_whole ceph.quota.max_bytes "${folder:-/}") || return 4
    [ -z "$value" ] || [ "$value" = 0 ] || return 3
  done
  return 1
}

volume_free_bytes() {  # volume_free_bytes VOLUME: "<bytes free> quota" or "<bytes free> df", else nothing
  local volume=$1 quota used avail
  # A quota below the volume's binds a fetch too, and the rule reads none (quota_below).
  quota_below "$volume"
  [ "$?" = 1 ] || return 1
  quota=$(xattr_whole ceph.quota.max_bytes "$volume") || return 1
  used=$(volume_used "$volume") || return 1
  used=${used%% *}
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
  case "$("$RULE_STAT" -f -c %T "$volume" 2>/dev/null)" in
    ""|ceph|fuse|fuseblk|fuse.*) return 1 ;;
  esac
  avail=$("$RULE_DF" -B1 --output=avail "$volume" 2>/dev/null | tail -n 1 | tr -dc '0-9')
  is_count "$avail" || return 1
  echo "$avail df"
}

settled_room() {  # settled_room VOLUME: "<bytes free> quota" or "... df", the smaller of two readings RULE_SETTLE seconds apart from the same figure, the second counting each of the volume's own entries at the larger of its two readings where the use is their sum; else nothing
  local first first_from second="" second_from="" census RULE_CENSUS_IN="" RULE_CENSUS_OUT=""
  # A minute, against the seconds in which CephFS's metadata server carries new bytes and each half
  # of a move up to the volume (it nudges its folders' recursive figures every 5 seconds by
  # default), so bytes a landing showed before the first reading are in the second unless the
  # server lags a minute; and a set moving between two of the volume's own entries is missed only
  # where the one it left shows it gone at the first reading and the one it reaches does not show it
  # yet at the second, since each entry counts at the larger of its two (entries_census). The first
  # census is kept in a file of the rule's own, in TMPDIR, the job's or the login node's, since each
  # reading runs in a subshell; where none can be made, nothing is read.
  census=$(mktemp "${TMPDIR:-/tmp}/size-rule-census.XXXXXX" 2>/dev/null) || return 1
  RULE_CENSUS_OUT=$census
  read -r first first_from <<< "$(volume_free_bytes "$1")"
  RULE_CENSUS_OUT=""
  if [ -n "$first" ]; then
    sleep "$RULE_SETTLE"
    RULE_CENSUS_IN=$census
    read -r second second_from <<< "$(volume_free_bytes "$1")"
  fi
  rm -f -- "$census"
  [ -n "$first" ] && [ -n "$second" ] && [ "$second_from" = "$first_from" ] || return 1
  [ "$second" -ge "$first" ] || first=$second
  echo "$first $first_from"
}

quota_below_words() {  # quota_below_words VOLUME: in words, why a quota below VOLUME's keeps the rule from reading the room, where one does; else nothing
  quota_below "$1"
  case $? in
    0) echo "the data root or a folder above it inside the volume carries a quota of its own, which the size rule does not read" ;;
    2) echo "a quota on the data root or a folder above it inside the volume could not be read" ;;
    3) echo "a folder above the volume on its mount carries a quota of its own, which the size rule does not read" ;;
    4) echo "a quota on a folder above the volume on its mount could not be read" ;;
    5) echo "the data root is no folder inside the volume on its mount, so the volume's quota is not the one a fetch there meets" ;;
  esac
}

room_unread_words() {  # room_unread_words VOLUME: why the room under VOLUME's quota could not be read, for a refusal
  local why
  why=$(quota_below_words "$1")
  echo "${why:-the room under the quota could not be read}"
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
  out=$("$RULE_SQUEUE" -h -u "${RULE_USER:-$(id -un)}" -o '%i' 2>/dev/null) || return 1
  printf '%s\n' "$out" | sed 's/_.*//' | sort -u
}

stated_bytes() {  # stated_bytes ID: the size grid/run-platform-fetch.sh's line for ID states, in bytes, else nothing
  local gb
  gb=$(bash "$REPO/grid/run-platform-fetch.sh" --stated "$1" 2>/dev/null)
  awk -v g="$gb" 'BEGIN { if (g + 0 > 0) printf "%.0f\n", g * 1000000000 }'
}

landing_bytes() {  # landing_bytes ID: what the landing holds by CephFS, read whole, 0 where there is none, else nothing
  # Whole, since a base cut short at a NUL would credit a fetch with bytes that were there before
  # it and leave what it owes short (#180).
  [ -e "$DATA/$1" ] || { echo 0; return 0; }
  xattr_whole ceph.dir.rbytes "$DATA/$1"
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
  # What the running fetches owe first and the room after it (#180): a byte a landing shows when
  # it is read is no longer owed, so the room is read after it, and again a minute later, for the
  # use to hold that byte; read the other way round, a byte landing between the two reads would
  # count neither as owed nor as used.
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
  # VOLUME is the caller's, as DATA is.
  # shellcheck disable=SC2153
  read -r room from <<< "$(settled_room "$VOLUME")"
  if [ -z "$room" ]; then
    exec 8>&-
    size_refused "$id" "$(room_unread_words "$VOLUME")"
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
# still running owe and the room left for a new one, the figure admit_fetch decides against. It
# reads once, what the running fetches owe first and the use after it, as a fetch's decision does;
# the decision reads the room again a minute later and keeps the smaller (settled_room), which a
# readout typed at the shell does not wait for, so while data lands or moves the two can differ by
# what moved in that minute. Called by grid/oschome-quota.sh in the owner's shell and by
# grid/gate.sh's status word, which names no folder, so the title is the caller's.
quota_readout() {  # quota_readout VOLUME TITLE: the readout; 1 when the volume has no quota that can be read
  local volume=$1 quota used how entries folders held floor files files_said="" max_files said owed_read owed n unsized below
  said=$(owed_by_running "")
  owed_read=$?
  quota=$(xattr_whole ceph.quota.max_bytes "$volume")
  read -r used how entries folders held floor <<< "$(volume_used "$volume")"
  files=$(xattr_digits ceph.dir.rfiles "$volume")
  max_files=$(xattr_digits ceph.quota.max_files "$volume")
  below=$(quota_below_words "$volume")
  echo "$2"
  if [ -z "$quota" ] || [ "$quota" = 0 ] || [ -z "$used" ]; then
    echo "The CephFS quota or its use could not be read, so the size rule admits no fetch:"
    whole_words ceph.quota.max_bytes "$volume" | sed 's/^/  /'
    use_words "$volume" "$used" "$how" | sed 's/^/  /'
    [ -z "$below" ] || echo "  and $below"
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
  [ "$how" != stat ] || stat_note "$volume"
  [ "$how" != entries ] || entries_note "$volume" "$entries" "$folders" "$held" "$floor"
  if [ "$owed_read" != 0 ]; then
    echo "Owed  =         not known; squeue did not answer, so the size rule admits no fetch now"
    return 0
  fi
  read -r owed n unsized <<< "$said"
  if [ -n "$unsized" ]; then
    echo "Owed  =         not known; the running fetch of $unsized states no size, so the size rule admits nothing beside it"
    return 0
  fi
  awk -v q="$quota" -v u="$used" -v o="$owed" -v n="$n" -v why="$below" 'BEGIN {
    room = q - u - o; if (room < 0) room = 0
    printf "Owed  =         %.2fgb still to land for %d running fetch%s\n", o / 1e9, n, (n == 1 ? "" : "es")
    if (why != "") printf "Room  =         none for a new fetch, since %s\n", why
    else printf "Room  =         %.2fgb for a new fetch, which lands whole or not at all\n", room / 1e9
  }'
}
