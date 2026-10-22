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
#                     catalog      the first catalog version, with C-ArmLSpine and the shards
#                                  already there (afterok setup, afterany carmlspine)
#                     xr_*         the X-ray chain: fetch (afterok setup), bank and ingest,
#                                  catalog (afterany bank and the first catalog)
#                     dp_*         the CT platform fetch, after the X-ray fetch (X-ray before CT)
#                     probe        what the raw case134 and case39 sweeps are on disk
#                     v1_driver    the version 1 run (afterok the first catalog, carmlspine,
#                                  setup and weights)
#   status          the gate's jobs and their states; the end of the log of each newest job that
#                   failed, masked (grid/redact.sed), and for a job that reads DICOM headers,
#                   person keys or a sign-in only its tracebacks and status lines (grid/log-shapes.awk);
#                   the stage reports with their paths cut and a quoting reason withheld
#                   (grid/report-shapes.awk), masked; the newest run
#   leaks           the leak checks over every shard on the volume, once no ingest is queued
#   v1              the version 1 run alone (again, after a failure), while start's other jobs are
#                   still live: each input is there, made by a live job of the gate's, or submitted
#                   now (the weights, the C-ArmLSpine ingest, a catalog build afterok on it), and
#                   the run waits afterok on each, so an input that fails again cancels it; the
#                   catalog version is the one grid/v1-version.sh chooses
#   latency         the latency jobs for the newest run that has a checkpoint, with the case134 sweep
#   fetch <id>      one set of grid/fetch-xray.json, a credentialed one with ~/.netrc, banked and catalogued
#   stop            cancel the gate's own jobs that are still queued or running, and nothing else
#
# While a version 1 run lasts, grid/logs/HOLD names its job and commit (grid/v1-driver.sbatch); the
# gate's side skips its fast-forward while the file is there, and every word but a refused one
# clears a hold whose job Slurm no longer holds, so the run's later steps run the code it recorded.
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
# DATA_ROOT reaches the jobs only when the caller set it (a test's folder): on the grid each stage
# keeps its own default, since stage 2 reads a set DATA_ROOT as its off-grid layout
# (<root>/<id>/raw in place of each recipe's raw folder), where LUMOS and VinDr-SpineXR are not.
GRID_DATA=/rs/rs_grp_oschome/go2432/data
DATA_ROOT_GIVEN=""
[ -z "${DATA_ROOT:-}" ] || [ "$DATA_ROOT" = "$GRID_DATA" ] || DATA_ROOT_GIVEN=yes
export -n DATA_ROOT 2>/dev/null
DATA_ROOT=${DATA_ROOT:-$GRID_DATA}
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
# Matched whole, so one argument holding two words ("v1 latency") is refused and never runs nothing.
case "$word" in
  start|status|leaks|v1|latency|fetch|stop) ;;
  "") echo "refusing: no word; one of: $WORDS"; exit 64 ;;
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
export PATH="$REPO/grid/bin:$PATH" SCHWINGNET="$REPO"
[ -z "$DATA_ROOT_GIVEN" ] || export DATA_ROOT
export PYDRV=$REPO/grid/bin/train-cpu-python
WHO=${USER:-$(id -un)}

commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)
echo "schwingnet $word${id:+ $id} at commit $commit on $(hostname) $(date -u '+%F %T') UTC"

record() {  # record ID WHAT: one line of the gate's own job list, the word with its id (fetch:<id>)
  echo "$1 $word${id:+:$id} $2 $(date -u '+%FT%TZ')" >> "$STATE"
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
QUEUED=""
snapshot() {  # what Slurm holds for WHO, read once per word; a failed squeue refuses the word
  local out
  if ! out=$("$SQUEUE" -h -u "$WHO" -o '%i' 2>/dev/null); then
    echo "refusing: squeue failed, so the gate cannot tell which of its jobs are queued or running; send the word again"
    return 75
  fi
  QUEUED=" $(echo "$out" | sed 's/_.*//' | sort -u | tr '\n' ' ') "
}
live_ids() {  # the gate's jobs Slurm still holds, queued or running (an array as its base id)
  gate_ids | sort -u | while read -r job; do
    case "$QUEUED" in *" $job "*) echo "$job" ;; esac
  done
}
live_of() {  # live_of WHAT [FROM]: the newest live job the gate submitted for WHAT (from the word FROM)
  local job from what
  [ -f "$STATE" ] || return 0
  tac "$STATE" | while read -r job from what _; do
    if [ "$what" = "$1" ] && { [ -z "${2:-}" ] || [ "$from" = "$2" ]; }; then
      case "$QUEUED" in *" $job "*) echo "$job"; break ;; esac
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
carmlspine_ready() {  # a train and a test shard of C-ArmLSpine are on the data root, as 00-carmlspine.sbatch reads it
  local kind
  for kind in train test; do
    grep -lqs "\"kind\": *\"$kind\"" "$DATA_ROOT"/carmlspine/shards/*/MANIFEST.json || return 1
  done
}
v1_version() {  # the catalog version the version 1 run would read now, as v1-driver.sbatch chooses it
  bash "$REPO/grid/v1-version.sh" "$STORE" "$DATA_ROOT" "$REPO" 2>/dev/null
}
ingest_failed_here() {  # the newest C-ArmLSpine ingest was refused at the commit the gate is at now
  local report=$LOGS/00-carmlspine-STAGE-REPORT.md
  [ "$commit" != unknown ] && [ -f "$report" ] || return 1
  head -n 1 "$report" | grep -q "commit $commit\$" && grep -qE 'refused|FAILED' "$report"
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
  DEPEND=$depend CATALOG_DEPEND=${CATALOG_DEPEND:-} bash "$REPO/grid/run-xray-chain.sh" "$@" 2>&1 | sed 's/^/  /'
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
  local live setup weights_dep="" ingest first opts platform job name
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
  # The first catalog version: C-ArmLSpine and every shard already on the data root, built once the
  # ingest ends, so the version 1 run starts hours after it and not days after the X-ray fetch. The
  # X-ray chain's own catalog job builds the next version after it, once its banks are in.
  mapfile -t opts < <(depend_on "$(joined "$setup" "afterany:$ingest")")
  first=$(submit catalog ${opts[@]+"${opts[@]}"} --export=ALL 03-catalog.sbatch) || return 1
  # X-ray before CT (the owner's order of 2026-10-21). The fetch waits on setup alone, since without
  # the environments every stage would fail; the chain's catalog waits on the first catalog too.
  XR_FETCH="" XR_CATALOG=""
  if CATALOG_DEPEND="afterany:$first" chain "$setup"; then
    # The CT platform chain after the X-ray fetch, so the X-ray sets take the network first. Each
    # job it printed is recorded, a refusal part-way or not, so 'stop' reaches every one.
    platform=$(DEPEND="afterany:$XR_FETCH" bash "$REPO/grid/run-platform-fetch.sh" 2>&1)
    [ $? = 0 ] || echo "  the platform fetch refused; the X-ray jobs stand"
    echo "$platform" | sed -n '/^Not submitted/q; p' | sed 's/^/  /'
    echo "$platform" | sed -n 's/^\([a-z0-9_]*\): job \([0-9][0-9]*\).*/\2 \1/p' | while read -r job name; do
      record "$job" "dp_$name"
    done
  else
    echo "  the X-ray chain was not submitted (above), so the CT platform chain is not either (X-ray before CT); 'stop', then 'start' again"
  fi
  # The probe reads what the sweeps are on disk with the node's own python3; it needs nothing above.
  # Its job id is read from what this call printed, never from LAST_LATENCY.txt, which an earlier
  # call may have left; a probe that was not submitted is said and start goes on without it.
  probed=$(bash "$REPO/grid/run-latency-sweep.sh" --probe 2>&1)
  probe_rc=$?
  echo "$probed" | sed 's/^/  /'
  if [ "$probe_rc" = 0 ]; then
    echo "$probed" | awk '$1 == "probe" && $2 ~ /^[0-9]+$/ { print $2 }' | while read -r job; do record "$job" probe; done
  else
    echo "  the probe was not submitted (exit $probe_rc, above); the rest of start goes on"
  fi
  # Version 1 needs C-ArmLSpine (its test part is the frozen persons), the first catalog with its
  # split check passed, the environments and the weights: afterok on each, so a failure cancels it.
  v1_driver "$(joined "afterok:$first" "afterok:$ingest" "$setup" "$weights_dep")" || {
    echo "  the version 1 run was not submitted (above); the jobs above stand, and 'v1' submits it alone after them"
    return 1
  }
  echo "submitted. 'status' follows them; 'leaks' once the catalog job has ended; 'latency' once the version 1 run has its checkpoint."
}

# status shows the end of the log of each of the gate's newest jobs that ended in one of these
# states (sacct's first word: "CANCELLED by <uid>" is CANCELLED), at most SHOWN_JOBS of them, two
# tasks of an array, TAIL_LINES lines each and LINE_CHARS characters a line.
FAILED_STATES=" FAILED TIMEOUT OUT_OF_MEMORY NODE_FAIL CANCELLED "
SHOWN_JOBS=6 ARRAY_TASKS=2 TAIL_LINES=15 SHAPE_LINES=400 LINE_CHARS=200
# The jobs whose logs hold nothing read from a patient's file, a person key or a sign-in, shown
# whole (masked): the container and the environments, and the public weights file. Every other
# job's log, any name not here among them, is shown only as shapes: the C-ArmLSpine ingest and the
# X-ray stages read DICOM headers and print person keys, the fetches run wget and curl with a
# sign-in, the probe prints the sweeps' file names, which carry case numbers, and the catalog, the
# leak checks, the latency jobs and the run print persons.
OPEN_LOGS=" sn_setup sn_weights "
newest_jobs() {  # " <id> <id> ... ": the newest job the gate submitted for each thing it makes
  # Keyed by what was made, so a v1 that ran the ingest again hides start's failed one; an X-ray
  # job's key carries its word, so each fetch's chain is its own.
  echo " $(tac "$STATE" 2>/dev/null | awk '{ key = $3; if (key ~ /^xr_/) key = $2 " " key; if (!(key in seen)) { seen[key] = 1; print $1 } }' | tr '\n' ' ') "
}
masked() {  # every line status shows of a log or a stage report: masked, then cut
  sed -r -f "$REPO/grid/redact.sed" | cut -c "1-$LINE_CHARS"
}
report_shapes() {  # a stage report's lines with their paths cut and a quoting reason withheld
  awk -v data="$DATA_ROOT" -v runs="$RUNS" -v models="$MODELS" -v repo="$REPO" \
    -f "$REPO/grid/shape-words.awk" -f "$REPO/grid/report-shapes.awk"
}
clean_tail() {  # clean_tail FILE: the file's last 64 KiB as lines of printable ASCII
  tail -c 65536 "$1" | tr '\r' '\n' | LC_ALL=C tr -cd '\11\12\40-\176'
}
log_tail() {  # log_tail NAME FILE: a failed job's log, its end whole for an open job, as shapes otherwise
  local kept withheld
  case "$OPEN_LOGS" in
    *" $1 "*) clean_tail "$2" | tail -n "$TAIL_LINES" | masked | sed 's/^/    /'; return ;;
  esac
  kept=$(clean_tail "$2" | tail -n "$SHAPE_LINES" | awk -f "$REPO/grid/shape-words.awk" -f "$REPO/grid/log-shapes.awk")
  withheld=$(echo "$kept" | sed -n 's/^#withheld \([0-9][0-9]*\)$/\1/p' | tail -n 1)
  echo "$kept" | grep -v '^#withheld ' | tail -n "$TAIL_LINES" | masked | sed 's/^/    /'
  echo "    (${withheld:-0} of its last $SHAPE_LINES lines withheld: this job can print DICOM header values, person keys or a sign-in, so only its tracebacks and status lines are shown; the whole log stays on the grid)"
}
failed_tails() {  # failed_tails SACCT: the end of the log of each newest job that failed
  local newest shown=0 more=0 tasks="" job name state elapsed code node base end log
  newest=$(newest_jobs)
  while IFS='|' read -r job name state elapsed code node; do
    base=${job%%_*} end=${state%% *}
    case "$newest" in *" $base "*) ;; *) continue ;; esac
    case "$FAILED_STATES" in *" $end "*) ;; *) continue ;; esac
    if [ "$base" != "$job" ]; then
      [ "$(echo "$tasks" | tr ' ' '\n' | grep -cx "$base")" -lt "$ARRAY_TASKS" ] || continue
      tasks="$tasks $base"
    fi
    [ "$shown" -lt "$SHOWN_JOBS" ] || { more=$((more + 1)); continue; }
    shown=$((shown + 1))
    # the log name the job's own --output=logs/%x_%j.out (%x_%A_%a for an array task) gives
    if ! [[ $job =~ ^[0-9]+(_[0-9]+)?$ ]] || ! [[ $name =~ ^[A-Za-z0-9_.-]+$ ]]; then
      echo "## $base ended $end; no log name can be made from what sacct gave"; continue
    fi
    log=${name}_${job}.out
    # A job that is no array but whose script names its log %x_%A_%a (latency-sweep.sbatch, run
    # once for the probe and the sweep) gets the task id 4294967294, Slurm's NO_VAL, in its name.
    [ -f "$LOGS/$log" ] || [ "$base" != "$job" ] || [ ! -f "$LOGS/${name}_${job}_4294967294.out" ] || log=${name}_${job}_4294967294.out
    echo "## $job ($name) ended $end after $elapsed, exit $code: logs/$log"
    if [ -f "$LOGS/$log" ]; then
      log_tail "$name" "$LOGS/$log"
    elif [ "$end" = CANCELLED ]; then
      echo "    cancelled before it started (a job it waited on failed, or 'stop'); no log"
    else
      echo "    no log at logs/$log"
    fi
  done <<< "$1"
  [ "$more" = 0 ] || echo "## $more more failed jobs not shown; their logs are under $LOGS"
}

word_status() {
  local ids report run lines job name state elapsed code node
  ids=$(gate_ids | tail -n 60 | tr '\n' ',' | sed 's/,$//')
  if [ -z "$ids" ]; then
    echo "no job submitted by the gate yet; 'start' submits the graph"
  else
    echo "## the gate's newest jobs (sacct): id, what, state, elapsed, exit code, node"
    lines=$("$SACCT" -X -n -P -j "$ids" --format=JobID,JobName,State,Elapsed,ExitCode,NodeList 2>/dev/null)
    while IFS='|' read -r job name state elapsed code node; do
      [ -n "$job" ] || continue
      echo "  $job $(awk -v j="${job%%_*}" '$1 == j { print $3 }' "$STATE" | tail -n 1) $state $elapsed $code $node"
    done <<< "$lines"
    failed_tails "$lines"
  fi
  for report in "$LOGS"/*STAGE-REPORT.md; do
    [ -f "$report" ] || continue
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    tail -n 12 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | sed 's/^/  /'
  done
  run=$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1)
  if [ -n "$run" ]; then
    echo "## newest run: $run"
    if [ -f "$run/train/checkpoint.json" ]; then echo "  checkpoint: training finished (train/checkpoint.json)"
    elif [ -f "$run/train/best.pt" ]; then echo "  checkpoint: not yet; training has kept a best epoch but has not finished"
    else echo "  checkpoint: not yet"; fi
    [ -f "$run/wandb-sync.json" ] && grep -o 'https://wandb\.ai/[^" ]*' "$run/wandb-sync.json" | sort -u | sed 's/^/  W\&B /' | head -n 4
    [ -f "$run/evaluate/results.md" ] && head -n 30 "$run/evaluate/results.md" | sed 's/^/  /'
  fi
}

word_leaks() {
  local busy line
  busy=$( { live_of carmlspine; live_of catalog; live_of xr_bank; live_of xr_catalog; } | tr '\n' ' ')
  if [ -n "${busy// /}" ]; then
    echo "refusing: an ingest or the catalog is still queued or running (jobs $busy); the leak checks read every shard once they end"
    return 75
  fi
  busy=$( { live_of leaks_fingerprint; live_of leaks_join; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: the leak checks are still queued or running (jobs $busy)"; return 75; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  CONCURRENCY=${CONCURRENCY:-32} bash "$REPO/grid/run-leaks.sh" 2>&1 | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ] || return 1
  line=$(last_line ' leaks fingerprint=')
  record "$(value_of fingerprint "$line")" leaks_fingerprint
  record "$(value_of join "$line")" leaks_join
}

word_v1() {
  local running setup opts ingest catalog ingest_dep="" catalog_dep="" weights_dep="" job version
  running=$(live_of v1_driver)
  [ -z "$running" ] || { echo "refusing: the version 1 run is already queued or running (job $running)"; return 75; }
  # Each input of the run is there, made by a live job of the gate's (start's or an earlier v1's),
  # or submitted now, so v1 runs again what failed while start's X-ray and CT jobs are still live,
  # which start refuses to while any of them is (issue #80). The run waits afterok on each input
  # still to come, so one that fails again cancels it rather than leaving it to fail on the GPU.
  setup=$(setup_dependency) || return 1
  job=$(live_of weights)
  if [ -n "$job" ]; then
    weights_dep="afterok:$job"
  elif weights_ready; then
    echo "  weights: $WEIGHTS is there; no job"
  else
    job=$(submit weights --export=ALL,MODELS="$MODELS" 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  # C-ArmLSpine's train and test shards: its test part is the frozen persons the run is measured on.
  ingest=$(live_of carmlspine)
  if [ -n "$ingest" ]; then
    ingest_dep="afterok:$ingest"
  elif carmlspine_ready; then
    echo "  carmlspine: a train and a test shard are under $DATA_ROOT/carmlspine/shards; no job"
  else
    if ingest_failed_here; then
      echo "  carmlspine: the last ingest was refused at this same commit $commit (logs/00-carmlspine-STAGE-REPORT.md);"
      echo "    it is submitted again and will fail the same way unless its bank changed; 'status' shows why it failed"
    fi
    mapfile -t opts < <(depend_on "$setup")
    ingest=$(submit carmlspine ${opts[@]+"${opts[@]}"} --export=ALL 00-carmlspine.sbatch) || return 1
    ingest_dep="afterok:$ingest"
  fi
  # A catalog version the run may read (grid/v1-version.sh): one there already, the gate's live catalog job
  # when it was submitted after a live ingest (start's and v1's always are), or a new build. The
  # build waits afterok on an ingest still to come, unlike start's, so a failed ingest cancels it
  # and no version without C-ArmLSpine is made for this run. The X-ray chain's xr_catalog jobs
  # are never waited on: they wait on fetches that take days.
  catalog=$(live_of catalog)
  if [ -n "$ingest_dep" ] && [ -n "$catalog" ] && [ "$catalog" -gt "$ingest" ]; then
    catalog_dep="afterok:$catalog"
  elif [ -z "$ingest_dep" ] && version=$(v1_version); then
    echo "  catalog: $version qualifies for the run (grid/v1-version.sh); no job"
  elif [ -z "$ingest_dep" ] && [ -n "$catalog" ]; then
    catalog_dep="afterok:$catalog"
  else
    mapfile -t opts < <(depend_on "$(joined "$setup" "$ingest_dep")")
    catalog=$(submit catalog ${opts[@]+"${opts[@]}"} --export=ALL 03-catalog.sbatch) || return 1
    catalog_dep="afterok:$catalog"
  fi
  v1_driver "$(joined "$catalog_dep" "$ingest_dep" "$weights_dep" "$setup")"
}

word_latency() {
  local run version catalog busy rc said
  busy=$( { live_of latency_gpu; live_of latency_cpu; live_of latency_sweep; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: latency jobs are still queued or running (jobs $busy)"; return 75; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  run=$(for one in $(ls -1dt "$RUNS"/*/ 2>/dev/null); do
          # train.py keeps best.pt from the first epoch on and writes checkpoint.json only when it
          # has finished, which the latency tools need, so a run still training is passed over
          [ -f "$one/RUN.json" ] && [ -f "$one/train/checkpoint.json" ] && [ -f "$one/train/best.pt" ] && { echo "${one%/}"; break; }
        done)
  [ -n "$run" ] || { echo "refusing: no run under $RUNS has finished training yet (RUN.json, train/checkpoint.json and train/best.pt)"; return 2; }
  version=$(sed -n 's/.*"catalog_version": *\([0-9][0-9]*\).*/\1/p' "$run/RUN.json" | head -n 1)
  [ -n "$version" ] || { echo "refusing: $run/RUN.json names no catalog_version"; return 2; }
  catalog=$(ls -1 "$STORE/versions/catalog-$(printf '%06d' "$version")-"*.sqlite 2>/dev/null | head -n 1)
  [ -n "$catalog" ] || { echo "refusing: catalog version $version is not under $STORE/versions"; return 2; }
  echo "  run: $run; catalog: $catalog"
  said=$(bash "$REPO/grid/run-latency-sweep.sh" --catalog "$catalog" "$run" --sweep "case134:bank=$SWEEP_BANK" 2>&1)
  rc=$?
  echo "$said" | sed 's/^/  /'
  # Every job this call submitted is recorded, a refusal part-way or not, so 'stop' reaches it; the
  # ids come from what this call printed, never from LAST_LATENCY.txt, which an earlier call may have left.
  echo "$said" | awk '($1 == "gpu" || $1 == "cpu" || $1 == "sweep") && $NF ~ /^[0-9]+$/ { print $NF, "latency_" $1 }' \
    | while read -r job what; do record "$job" "$what"; done
  [ "$rc" = 0 ] || return 1
}

word_fetch() {
  local section setup busy waits="" one args=(--only "$id")
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
  # One fetch of a set at a time: two would resume the same .part files at once. start's chain
  # fetches every open set, so an open id waits for it too.
  busy=$(live_of xr_fetch "fetch:$id")
  [ "$section" = credentialed ] || busy=$busy$(live_of xr_fetch start)
  [ -z "$busy" ] || { echo "refusing: a fetch that holds $id is still queued or running (job $busy)"; return 75; }
  # One catalog build at a time: this chain's catalog job waits for every one still live.
  for one in $(awk '$3 == "catalog" || $3 == "xr_catalog" { print $1 }' "$STATE" 2>/dev/null | sort -u); do
    case "$QUEUED" in *" $one "*) waits=$(joined "$waits" "afterany:$one") ;; esac
  done
  setup=$(setup_dependency) || return 1
  CATALOG_DEPEND=$waits chain "$setup" "${args[@]}"
}

word_stop() {
  local live
  live=$(live_ids | tr '\n' ' ')
  [ -n "${live// /}" ] || { echo "nothing of the gate's is queued or running"; return 0; }
  # shellcheck disable=SC2086
  "$SCANCEL" $live && echo "cancelled: $live"
}

release_hold() {  # the version 1 run's hold (grid/v1-driver.sbatch) is cleared once Slurm no longer holds its job
  local job
  [ -f "$LOGS/HOLD" ] || return 0
  job=$(awk '{ print $1; exit }' "$LOGS/HOLD")
  case "$QUEUED" in
    *" $job "*) echo "  the checkout holds still at $(awk '{ print substr($2, 1, 7); exit }' "$LOGS/HOLD") while the version 1 run (job $job) lasts" ;;
    *) rm -f "$LOGS/HOLD" ;;
  esac
}
if [ "$word" = status ]; then
  # status reads even when squeue does not answer; only a hold it can see is over is cleared
  snapshot > /dev/null && release_hold
else
  snapshot || { echo "schwingnet $word: exit 75"; exit 75; }
  release_hold
fi
case "$word" in
  start) word_start ;;
  # Bounded whatever the logs hold: 400 lines and 64 KiB reach the gate at most.
  status) out=$(word_status); printf '%s\n' "$(head -n 400 <<< "$out" | head -c 65536)" ;;
  leaks) word_leaks ;;
  v1) word_v1 ;;
  latency) word_latency ;;
  fetch) word_fetch ;;
  stop) word_stop ;;
esac
rc=$?
echo "schwingnet $word: exit $rc"
exit $rc
