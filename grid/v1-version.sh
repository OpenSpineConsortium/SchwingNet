#!/bin/bash
# The catalog version the version 1 run reads (issue #80), chosen the same way by grid/gate.sh's v1
# word, which asks whether a catalog build is needed, and by grid/v1-driver.sbatch, which runs on it:
# the newest line of VERSIONS.jsonl that
#   - holds both of C-ArmLSpine's parts, train and test (its test part is the frozen persons the run
#     is measured on),
#   - holds every C-ArmLSpine shard at the head of its chain on the volume, so a version built before
#     the newest ingest is never run on,
#   - has a split-check marker, $STORE/checked/<file>, that grid/03-catalog.sbatch wrote after the
#     check passed, naming the sha256 of data/splits/test-persons.json and rule.json as they are now,
#     so a version checked against an older freeze is checked again before any run reads it,
#   - and whose file is under $STORE/versions.
# With a fourth argument SOURCE, the version must also hold SOURCE's train part, as the block smoke
# test's two_source plan needs (grid/sweep-driver.sbatch, issue #252); with three it chooses as above.
# Prints the file's name and exits 0, or says on stderr why no version qualifies and exits 1. Runs on
# the login node, so bash, grep, sed, awk and sha256sum only (warrior kills python by name).
#
#   v1-version.sh STORE DATA_ROOT REPO [SOURCE]
set -uo pipefail
STORE=$1 DATA_ROOT=$2 REPO=$3 SOURCE=${4:-}
# A source is an id, lower-case letters, digits and _; anything else names no source a version holds.
case "$SOURCE" in *[!a-z0-9_]*) echo "no catalog version is chosen for '$SOURCE', which is no source id" >&2; exit 1 ;; esac

digest() { sha256sum < "$1" 2>/dev/null | cut -d' ' -f1; }

head_shards() {  # the C-ArmLSpine shards on the volume that no other shard there supersedes
  local manifests
  manifests=$(ls "$DATA_ROOT"/carmlspine/shards/*/MANIFEST.json 2>/dev/null) || return 0
  # tools/ingest.py writes a manifest with indent 1 and sorted keys, so its own name and supersedes
  # are the lines one space in; an item's keys sit deeper.
  # shellcheck disable=SC2086
  awk '/^ "name": "/ { split($0, q, "\""); names[q[4]] = 1 }
       /^ "supersedes": "/ { split($0, q, "\""); gone[q[4]] = 1 }
       END { for (n in names) if (!(n in gone)) print n }' $manifests | sort
}

marked() {  # marked FILE: the split check passed on FILE against today's freeze and rule
  local marker=$STORE/checked/$1
  [ -f "$marker" ] \
    && grep -qx "test-persons $persons" "$marker" \
    && grep -qx "rule $rule" "$marker"
}

holds_heads() {  # holds_heads LINE: every head shard is in the line's shards list
  local shards shard
  shards=" $(echo "$1" | grep -o '"shards":\[[^]]*\]' | sed 's/^"shards":\[//; s/\]$//; s/"//g; s/,/ /g') "
  for shard in $heads; do
    case "$shards" in *" $shard "*) ;; *) return 1 ;; esac
  done
}

persons=$(digest "$REPO/data/splits/test-persons.json")
rule=$(digest "$REPO/data/splits/rule.json")
[ -n "$persons" ] && [ -n "$rule" ] || { echo "no data/splits/test-persons.json or rule.json under $REPO" >&2; exit 1; }
[ -f "$STORE/VERSIONS.jsonl" ] || { echo "no catalog version yet ($STORE/VERSIONS.jsonl)" >&2; exit 1; }
heads=$(head_shards)
# An older version that meets every test is as good as the newest, so a newest version whose split
# check failed leaves the run on the last one that passed; the reason given is the newest one's.
why=""
because() { [ -n "$why" ] || why=$1; }
while IFS= read -r line; do
  case "$line" in *'"carmlspine|test":'*) ;; *) continue ;; esac
  case "$line" in *'"carmlspine|train":'*) ;; *) continue ;; esac
  file=$(echo "$line" | sed -n 's/.*"file": *"\(catalog-[0-9]*-[0-9a-f]*\.sqlite\)".*/\1/p')
  [ -n "$file" ] || continue
  if [ -n "$SOURCE" ] && [[ $line != *"\"$SOURCE|train\":"* ]]; then
    because "the newest version with C-ArmLSpine ($file) holds no $SOURCE train part"
  elif ! holds_heads "$line"; then
    because "the newest version with C-ArmLSpine ($file) lacks a C-ArmLSpine shard now on the volume"
  elif ! marked "$file"; then
    because "the newest version with C-ArmLSpine ($file) has no passed split check against the current test persons and rule"
  elif [ ! -f "$STORE/versions/$file" ]; then
    because "VERSIONS.jsonl names $file, which is not under versions/"
  else
    echo "$file"
    exit 0
  fi
done < <(tac "$STORE/VERSIONS.jsonl")
because "no catalog version holds both of the C-ArmLSpine parts"
echo "$why" >&2
exit 1
