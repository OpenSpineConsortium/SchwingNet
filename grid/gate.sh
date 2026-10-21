#!/bin/bash
# The one entry point the Beethoven grid gate calls (issue #53), as the gate word
# `schwingnet <word> [<id>]`, so the owner never types a grid command again (his rule of
# 2026-10-21 19:37 UTC). The gate's side brings the checkout to main first (a clone at ~/SchwingNet
# when there is none, else a fast-forward) and then runs `bash ~/SchwingNet/grid/gate.sh <word> [<id>]`.
# On the login node this script runs only bash, git, sbatch, squeue, sacct, scancel, flock, awk,
# sed and coreutils (warrior kills python by name); every byte of work is a Slurm job, and every
# Python step of those jobs runs inside the container (grid/box.sh, grid/bin/).
#
#   start           the whole graph, with Slurm dependencies, once:
#                     setup        the container and the pixi environments, only when pixi.lock
#                                  changed since the environments were last made
#                     weights      the ImageNet ResNet-18 file, only when it is not there yet
#                     carmlspine   C-ArmLSpine's bank as a train and a test shard (afterok setup)
#                     xr_*         the X-ray chain: fetch, bank and ingest, catalog
#                                  (afterok setup, afterany carmlspine)
#                     dp_*         the CT platform fetch, after the X-ray fetch (X-ray before CT)
#                     probe        what the raw case134 and case39 sweeps are on disk
#                     v1_driver    the version 1 run (afterok catalog, setup and weights)
#   status          the gate's jobs and their states, the stage reports, the newest run
#   leaks           the leak checks over every shard on the volume, once no ingest is queued
#   v1              the version 1 run alone (again, after a failure)
#   latency         the latency jobs for the newest run that has a checkpoint, with the case134 sweep
#   fetch <id>      one set of grid/fetch-xray.json, a credentialed one with ~/.netrc, banked and catalogued
#   stop            cancel the gate's own jobs that are still queued or running, and nothing else
#
# Every submission is one line of grid/logs/GATE_JOBS.txt (<job id> <word> <what> <when>); status
# and stop read that file and touch no job it does not name. SBATCH, SQUEUE, SACCT and SCANCEL
# name fakes for the tests; DATA_ROOT, RUNS and MODELS other folders. Exit codes: 0 done, 64 a word
# refused, 75 busy (a word still running, or jobs still live), 2 the checkout or a file missing,
# 1 a submission failed.
set -uo pipefail
# One stream, in order: what the jobs were and why a word was refused reach the gate together.
exec 2>&1
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SBATCH=${SBATCH:-sbatch}
SQUEUE=${SQUEUE:-squeue}
SACCT=${SACCT:-sacct}
SCANCEL=${SCANCEL:-scancel}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
STORE=$DATA_ROOT/_catalog
RUNS=${RUNS:-/rs/rs_grp_oschome/go2432/runs}
MODELS=${MODELS:-/rs/rs_grp_oschome/go2432/models}
WEIGHTS=$MODELS/resnet18-f37072fd.pth
SWEEP_BANK=${SWEEP_BANK:-$DATA_ROOT/realxray/carmlspine_sweep}
NETRC=${NETRC:-$HOME/.netrc}
LOGS=$REPO/grid/logs
STATE=$LOGS/GATE_JOBS.txt
WORDS="start status leaks v1 latency fetch stop"
ENVS="default train-cpu train-gpu telemetry"

word=${1:-}
id=${2:-}
case " $WORDS " in
  *" $word "*) [ -n "$word" ] || { echo "refusing: no word; one of: $WORDS"; exit 64; } ;;
  *) echo "refusing: '$word' is not one of: $WORDS"; exit 64 ;;
esac
if [ "$word" = fetch ]; then
  [ $# -eq 2 ] || { echo "refusing: fetch takes exactly one id"; exit 64; }
  case "$id" in ""|*[!a-z0-9_]*) echo "refusing: an id is lower-case letters, digits and _"; exit 64 ;; esac
  [ ${#id} -le 40 ] || { echo "refusing: an id is at most 40 characters"; exit 64; }
else
  [ $# -eq 1 ] || { echo "refusing: $word takes no argument"; exit 64; }
fi
[ -d "$REPO/grid" ] || { echo "no $REPO/grid: the gate clones the repository there first"; exit 2; }
mkdir -p "$LOGS"
cd "$REPO/grid" || exit 2
# One word at a time: two starts sent together would each see no job of the other's yet.
exec 9> "$LOGS/gate.lock"
flock -w 60 9 || { echo "refusing: another gate word is still running"; exit 75; }
# The jobs and the scripts they start find pixi and the train-cpu python through the shims, which
# run them inside the container; the stages read PYDRV, the X-ray chain, the leaks and the ingest.
export PATH="$REPO/grid/bin:$PATH" SCHWINGNET="$REPO" DATA_ROOT
export PYDRV=$REPO/grid/bin/train-cpu-python
WHO=${USER:-$(id -un)}

commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)
echo "schwingnet $word${id:+ $id} at commit $commit on $(hostname) $(date -u '+%F %T') UTC"

record() {  # record ID WHAT: one line of the gate's own job list
  echo "$1 $word $2 $(date -u '+%FT%TZ')" >> "$STATE"
  echo "  $2: job $1"
}
submit() {  # submit WHAT [sbatch options...] SCRIPT: the job id on stdout, the record on stderr
  local what=$1 out
  shift
  out=$("$SBATCH" --parsable -D "$REPO/grid" "$@") || { echo "  sbatch refused $what: $out" >&2; return 1; }
  out=$(echo "$out" | tail -n 1 | cut -d';' -f1)
  case "$out" in ''|*[!0-9]*) echo "  sbatch gave no job id for $what: $out" >&2; return 1 ;; esac
  record "$out" "$what" >&2
  echo "$out"
}
gate_ids() {  # every job id the gate's list names, oldest first
  [ -f "$STATE" ] && awk '{ print $1 }' "$STATE"
}
live_ids() {  # the gate's jobs Slurm still holds, queued or running (an array as its base id)
  local queued
  queued=" $("$SQUEUE" -h -u "$WHO" -o '%i' 2>/dev/null | sed 's/_.*//' | sort -u | tr '\n' ' ') "
  gate_ids | sort -u | while read -r job; do
    case "$queued" in *" $job "*) echo "$job" ;; esac
  done
}
live_of() {  # live_of WHAT: the newest live job the gate submitted for WHAT, if any
  local live job from what
  live=" $(live_ids | tr '\n' ' ') "
  [ -f "$STATE" ] || return 0
  tac "$STATE" | while read -r job from what _; do
    if [ "$what" = "$1" ]; then
      case "$live" in *" $job "*) echo "$job"; break ;; esac
    fi
  done
}
envs_ready() {  # the four environments exist and were made from this pixi.lock
  local env stamp
  for env in $ENVS; do [ -x "$REPO/.pixi/envs/$env/bin/python" ] || return 1; done
  stamp=$(cat "$REPO/.pixi/SETUP.sha256" 2>/dev/null)
  [ -n "$stamp" ] && [ "$stamp" = "$(sha256sum < "$REPO/pixi.lock" | cut -d' ' -f1)" ]
}
weights_ready() {  # the file is there and its job wrote the digest torchvision's name promises
  [ -s "$WEIGHTS" ] && grep -q '^f37072fd' "$WEIGHTS.sha256" 2>/dev/null
}
catalog_ready() {  # the store names a current version that is there
  local current
  current=$(cat "$STORE/CURRENT" 2>/dev/null)
  [ -n "$current" ] && [ -f "$STORE/versions/$current" ]
}
setup_dependency() {  # prints afterok:<setup job> unless the environments are ready
  local job
  envs_ready && return 0
  job=$(live_of setup)
  [ -n "$job" ] || job=$(submit setup 00-setup.sbatch) || return 1
  echo "afterok:$job"
}
joined() {  # joined DEP...: the non-empty dependencies, comma-separated
  local out="" one
  for one in "$@"; do [ -n "$one" ] && out=${out:+$out,}$one; done
  echo "$out"
}
depend_on() {  # depend_on DEPS: the sbatch options for DEPS, none when DEPS is empty
  [ -n "$1" ] && printf '%s\n' "--dependency=$1" "--kill-on-invalid-dep=yes"
}
last_line() {  # last_line PATTERN: the newest line of LAST_RUN.txt that holds PATTERN
  grep -- "$1" "$REPO/grid/LAST_RUN.txt" 2>/dev/null | tail -n 1
}
value_of() {  # value_of KEY LINE: the value of KEY=value in LINE
  echo "$2" | tr ' ' '\n' | sed -n "s/^$1=//p" | head -n 1
}
chain() {  # chain DEPEND [run-xray-chain.sh arguments...]: the X-ray chain after DEPEND, ids recorded
  local depend=$1 before after
  shift
  before=$(last_line ' fetch=')
  DEPEND=$depend bash "$REPO/grid/run-xray-chain.sh" "$@" 2>&1 | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ] || return 1
  after=$(last_line ' fetch=')
  [ -n "$after" ] && [ "$after" != "$before" ] || { echo "  the X-ray chain wrote no new line to grid/LAST_RUN.txt"; return 1; }
  XR_FETCH=$(value_of fetch "$after"); XR_CATALOG=$(value_of catalog "$after")
  record "$XR_FETCH" xr_fetch; record "$(value_of bank "$after")" xr_bank; record "$XR_CATALOG" xr_catalog
}
v1_driver() {  # v1_driver DEPS: the version 1 run after DEPS
  local opts
  mapfile -t opts < <(depend_on "$1")
  # ${a[@]+"${a[@]}"}: the grid's bash 4.2 calls an empty array unbound under set -u
  submit v1_driver ${opts[@]+"${opts[@]}"} --export=ALL,RUNS="$RUNS",WEIGHTS="$WEIGHTS" v1-driver.sbatch >/dev/null
}

word_start() {
  local live setup weights_dep="" ingest opts platform job name
  live=$(live_ids | wc -l)
  if [ "$live" -gt 0 ]; then
    echo "refusing: $live of the gate's jobs are still queued or running; 'status' lists them, 'stop' cancels them"
    return 75
  fi
  setup=$(setup_dependency) || return 1
  [ -n "$setup" ] || echo "  setup: the environments match pixi.lock; no job"
  if weights_ready; then
    echo "  weights: $WEIGHTS is there; no job"
  else
    job=$(submit weights --export=ALL,MODELS="$MODELS" 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  mapfile -t opts < <(depend_on "$setup")
  ingest=$(submit carmlspine ${opts[@]+"${opts[@]}"} --export=ALL 00-carmlspine.sbatch) || return 1
  # X-ray before CT (the owner's order of 2026-10-21). afterany on the C-ArmLSpine ingest, since its
  # refusal must not hold back every other set; afterok on setup, since without the environments
  # every stage would fail.
  XR_FETCH="" XR_CATALOG=""
  chain "$(joined "$setup" "afterany:$ingest")" || echo "  the X-ray chain was not submitted (above); the rest goes on"
  # The CT platform chain after the X-ray fetch, so the X-ray sets take the network first.
  platform=$(DEPEND=${XR_FETCH:+afterany:$XR_FETCH} bash "$REPO/grid/run-platform-fetch.sh" 2>&1)
  [ $? = 0 ] || echo "  the platform fetch refused; the X-ray jobs stand"
  echo "$platform" | sed -n '/^Not submitted/q; p' | sed 's/^/  /'
  echo "$platform" | sed -n 's/^\([a-z0-9_]*\): job \([0-9][0-9]*\).*/\2 \1/p' | while read -r job name; do
    record "$job" "dp_$name"
  done
  # The probe reads what the sweeps are on disk with the node's own python3; it needs nothing above.
  bash "$REPO/grid/run-latency-sweep.sh" --probe 2>&1 | sed 's/^/  /'
  awk '$1 == "probe" { print $NF }' "$REPO/grid/LAST_LATENCY.txt" 2>/dev/null | while read -r job; do record "$job" probe; done
  if [ -n "$XR_CATALOG" ]; then
    v1_driver "$(joined "afterok:$XR_CATALOG" "$setup" "$weights_dep")" || return 1
  elif catalog_ready; then
    v1_driver "$(joined "$setup" "$weights_dep")" || return 1
  else
    echo "  v1_driver: not submitted, since no catalog job was queued and no catalog version is there"
  fi
  echo "submitted. 'status' follows them; 'leaks' once the catalog job has ended; 'latency' once the version 1 run has its checkpoint."
}

word_status() {
  local ids report run
  ids=$(gate_ids | tail -n 60 | tr '\n' ',' | sed 's/,$//')
  if [ -z "$ids" ]; then
    echo "no job submitted by the gate yet; 'start' submits the graph"
  else
    echo "## the gate's newest jobs (sacct): id, what, state, elapsed, exit code, node"
    "$SACCT" -X -n -P -j "$ids" --format=JobID,State,Elapsed,ExitCode,NodeList 2>/dev/null | while IFS='|' read -r job state elapsed code node; do
      echo "  $job $(awk -v j="${job%%_*}" '$1 == j { print $3 }' "$STATE" | tail -n 1) $state $elapsed $code $node"
    done
  fi
  for report in "$LOGS"/*STAGE-REPORT.md; do
    [ -f "$report" ] || continue
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    tail -n 12 "$report" | sed 's/^/  /'
  done
  run=$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1)
  if [ -n "$run" ]; then
    echo "## newest run: $run"
    [ -f "$run/train/best.pt" ] && echo "  checkpoint: train/best.pt is there" || echo "  checkpoint: not yet"
    [ -f "$run/wandb-sync.json" ] && grep -o 'https://wandb\.ai/[^" ]*' "$run/wandb-sync.json" | sort -u | sed 's/^/  W\&B /' | head -n 4
    [ -f "$run/evaluate/results.md" ] && head -n 30 "$run/evaluate/results.md" | sed 's/^/  /'
  fi
}

word_leaks() {
  local busy line
  busy=$( { live_of carmlspine; live_of xr_bank; live_of xr_catalog; } | tr '\n' ' ')
  if [ -n "${busy// /}" ]; then
    echo "refusing: an ingest or the catalog is still queued or running (jobs $busy); the leak checks read every shard once they end"
    return 75
  fi
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  CONCURRENCY=${CONCURRENCY:-32} bash "$REPO/grid/run-leaks.sh" 2>&1 | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ] || return 1
  line=$(last_line ' leaks fingerprint=')
  record "$(value_of fingerprint "$line")" leaks_fingerprint
  record "$(value_of join "$line")" leaks_join
}

word_v1() {
  local running setup
  running=$(live_of v1_driver)
  [ -z "$running" ] || { echo "refusing: the version 1 run is already queued or running (job $running)"; return 75; }
  catalog_ready || { echo "refusing: no catalog version under $STORE; 'start' builds one"; return 2; }
  weights_ready || { echo "refusing: no ImageNet weights at $WEIGHTS; 'start' fetches them"; return 2; }
  setup=$(setup_dependency) || return 1
  v1_driver "$setup"
}

word_latency() {
  local run version catalog
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  run=$(for one in $(ls -1dt "$RUNS"/*/ 2>/dev/null); do
          [ -f "$one/RUN.json" ] && [ -f "$one/train/best.pt" ] && { echo "${one%/}"; break; }
        done)
  [ -n "$run" ] || { echo "refusing: no run under $RUNS has RUN.json and train/best.pt yet"; return 2; }
  version=$(sed -n 's/.*"catalog_version": *\([0-9][0-9]*\).*/\1/p' "$run/RUN.json" | head -n 1)
  [ -n "$version" ] || { echo "refusing: $run/RUN.json names no catalog_version"; return 2; }
  catalog=$(ls -1 "$STORE/versions/catalog-$(printf '%06d' "$version")-"*.sqlite 2>/dev/null | head -n 1)
  [ -n "$catalog" ] || { echo "refusing: catalog version $version is not under $STORE/versions"; return 2; }
  echo "  run: $run; catalog: $catalog"
  bash "$REPO/grid/run-latency-sweep.sh" --catalog "$catalog" "$run" --sweep "case134:bank=$SWEEP_BANK" 2>&1 | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ] || return 1
  awk '{ print $NF, "latency_" $1 }' "$REPO/grid/LAST_LATENCY.txt" 2>/dev/null | while read -r job what; do
    record "$job" "$what"
  done
}

word_fetch() {
  local section setup args=(--only "$id")
  section=$(awk -v id="$id" '
    /"credentialed": \[/ { cred = 1 }
    index($0, "\"id\": \"" id "\"") { print (cred ? "credentialed" : "open"); exit }' "$REPO/grid/fetch-xray.json")
  [ -n "$section" ] || { echo "refusing: $id is not an id of grid/fetch-xray.json"; return 64; }
  if [ "$section" = credentialed ]; then
    # The owner's PhysioNet sign-in, read by the fetch job alone; never printed here.
    [ -f "$NETRC" ] || { echo "refusing: $id is credentialed and there is no ~/.netrc"; return 2; }
    [ "$(stat -c '%a' "$NETRC")" = 600 ] || { echo "refusing: ~/.netrc is not mode 600"; return 2; }
    grep -q 'physionet\.org' "$NETRC" || { echo "refusing: ~/.netrc has no physionet.org line"; return 2; }
    args+=(--credentialed)
  fi
  [ -z "$(live_of xr_catalog)" ] || echo "  note: an X-ray chain is still live; this fetch's catalog job runs after its own bank job"
  setup=$(setup_dependency) || return 1
  chain "$setup" "${args[@]}"
}

word_stop() {
  local live
  live=$(live_ids | tr '\n' ' ')
  [ -n "${live// /}" ] || { echo "nothing of the gate's is queued or running"; return 0; }
  # shellcheck disable=SC2086
  "$SCANCEL" $live && echo "cancelled: $live"
}

case "$word" in
  start) word_start ;;
  status) out=$(word_status); head -n 200 <<< "$out" ;;
  leaks) word_leaks ;;
  v1) word_v1 ;;
  latency) word_latency ;;
  fetch) word_fetch ;;
  stop) word_stop ;;
esac
rc=$?
echo "schwingnet $word: exit $rc"
exit $rc
