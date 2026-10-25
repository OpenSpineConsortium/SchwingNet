#!/bin/bash
# The one entry point the Beethoven grid gate calls (issue #53), as the gate word
# `schwingnet <word> [<id>]`, so the owner never types a grid command again (his rule of
# 2026-10-21 19:37 UTC). The gate's side brings the checkout to main first (a clone at ~/SchwingNet
# when there is none, else a fast-forward) and then runs `bash ~/SchwingNet/grid/gate.sh <word> [<id>]`.
# On the login node this script runs only bash, git, hpcworker, squeue, sacct, scancel, flock, awk,
# sed and coreutils (warrior kills python by name); every byte of work is a Slurm job, queued through
# hpcworker's `job submit` with a class and no partition or QoS of ours (grid/hpcw.sh, issue #77),
# and every Python step of those jobs runs inside the container (grid/box.sh, grid/bin/).
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
#   fetch <id>      one set of grid/fetch-xray.json, a credentialed one with ~/.netrc, banked and catalogued;
#                   or one source of grid/run-platform-fetch.sh's --gated-ids (CADS, RSNA RATIC, RSPECT,
#                   ReXGradient once its token or link file is in place; the full NLST on the owner's yes),
#                   after any live X-ray fetch
#   explore <id>    one look inside a fetched set (tools/explore.py, grid/explore.sbatch): the first send
#                   queues one job for the listing of its raw folder and zips and, for a set the gate
#                   names one for (explore_against), the comparison with it by name and content; the
#                   next send prints the report, logs/EXPLORE-<id>.md, and queues nothing; a new fetch
#                   of the set or a change to tools/explore.py makes the next send look again
#   dropzip <id>    the deletion of a fetched set's download zips (tools/dropzip.py, grid/dropzip.sbatch,
#                   the owner's word of 2026-10-23): the first send queues one job, which deletes a zip
#                   only when every file in it sits unpacked beside it at the same size; the next send
#                   prints its report, logs/DROPZIP-<id>.md, and clears it, so a later send looks again
#   unpack <id>     the unpacking of a fetched set's download zips beside themselves (tools/unpack.py,
#                   grid/unpack.sbatch, the owner's word of 2026-10-23 for RSPECT): the first send
#                   queues one job, which starts writing only when the size rule admits what the
#                   unpacked files take; the next send prints its report, logs/UNPACK-<id>.md, and
#                   clears it, so a later send goes on where a job cut short stopped
#   nodequota       the volume's readout as a compute node reads it (grid/nodequota.sbatch, the owner's yes
#                   of 2026-10-24): the first send queues one job, the next prints logs/NODEQUOTA.md and
#                   clears it, so the send after that looks again
#   samples         the sample index (grid/run-samples.sh): plan, scan and merge, refused while one
#                   of them is live; status shows its MANIFEST.md, aggregates only
#   sweep <plan>    one plan of grid/sweeps/ (issue #252): the block smoke test on one GPU through
#                   the Metaflow flow (grid/sweep-driver.sbatch), after the setup, the weights and a
#                   live catalog build where the plan needs them, and afterany every live run that
#                   holds the checkout; status shows each plan's PROGRESS.txt under SMOKE
#   bank <id>       one recipe of grid/banks/ banked and ingested (grid/02-bank-ingest.sbatch with
#                   ONLY=<id>) and a catalog build afterok on it: two CPU jobs, once its held raw
#                   copy is there and the room under the quota takes what they write
#   experiment <n>  one requested combination of data and blocks, issue #<n> labelled experiment: the
#                   request the experiment workflow recorded as <n>.request on the branch experiments,
#                   fetched now and checked line by line, run as one GPU job (experiment-driver.sbatch)
#                   once the version 1 inputs are there (the environments, the weights, C-ArmLSpine's
#                   shards and a qualifying catalog version, which 'v1' makes), refused while a run for
#                   the same issue is live and afterany every other live run that holds the checkout;
#                   the job checks the values against the blocks module before anything trains
#   stop            cancel the gate's own jobs that are still queued or running, and nothing else
#   cancel <job>    cancel one of the gate's own live jobs and every other live job its word queued
#                   with it (a fetch's bank and catalog), and nothing else
#
# While a version 1 run, a sweep or an experiment run lasts, grid/logs/HOLD names its job and
# commit (grid/v1-driver.sbatch, grid/sweep-driver.sbatch, grid/experiment-driver.sbatch); the
# gate's side skips its fast-forward while the file is there, and every word but a refused one
# clears a hold whose job Slurm no longer holds, so the run's later steps run the code it
# recorded. One file holds one job, so each run that takes it waits afterany on every other one
# still live (checkout_holders) rather than run beside it.
# Every submission is one line of grid/logs/GATE_JOBS.txt (<job id> <word> <what> <when>) as well
# as of hpcworker's ledger for the project; status and stop read the gate's file, which knows the
# word each job came from, and touch no job it does not name. Which of them are live is read from
# squeue, as before: hpcworker's `job status` reads every job as ended when neither squeue nor sacct
# answers, and a gate that took that for "nothing live" would queue a second graph beside the first.
# HPCWORKER names the hpcworker (the gate's clone hands it here), SQUEUE, SACCT, SCANCEL and
# GETFATTR fakes for the tests, GETFATTR read by the size rule only where SIZE_RULE_STAND_INS=yes
# says so (grid/size-rule.sh); DATA_ROOT, RUNS, SMOKE and MODELS other folders. Exit codes: 0 done,
# 64 a word refused, 75 busy (a word still running, or jobs still live), 2 the checkout or a file
# missing, 1 a submission failed.
set -uo pipefail
# One stream, in order: what the jobs were and why a word was refused reach the gate together.
exec 2>&1
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SQUEUE=${SQUEUE:-squeue}
SACCT=${SACCT:-sacct}
SCANCEL=${SCANCEL:-scancel}
GETFATTR=${GETFATTR:-getfattr}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
SHARED_DATA=${SHARED_DATA:-/rs/rs_grp_oschome/shared/datasets}
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
# The block smoke test's results (issue #252): <plan>/<commit 7>-<catalog sha256 first 8>/ per sweep.
SMOKE=${SMOKE:-/rs/rs_grp_oschome/go2432/smoke}
MODELS=${MODELS:-/rs/rs_grp_oschome/go2432/models}
WEIGHTS=$MODELS/resnet18-f37072fd.pth
SWEEP_BANK=${SWEEP_BANK:-$DATA_ROOT/realxray/carmlspine_sweep}
NETRC=${NETRC:-$HOME/.netrc}
LOGS=$REPO/grid/logs
STATE=$LOGS/GATE_JOBS.txt
WORDS="start status leaks v1 latency fetch explore dropzip unpack nodequota samples sweep bank experiment stop cancel"
ENVS="default train-cpu train-gpu telemetry"

word=${1:-}
id=${2:-}
# Matched whole, so one argument holding two words ("v1 latency") is refused and never runs nothing.
case "$word" in
  start|status|leaks|v1|latency|fetch|explore|dropzip|unpack|nodequota|samples|sweep|bank|experiment|stop|cancel) ;;
  "") echo "refusing: no word; one of: $WORDS"; exit 64 ;;
  *) echo "refusing: '$word' is not one of: $WORDS"; exit 64 ;;
esac
if [ "$word" = fetch ] || [ "$word" = explore ] || [ "$word" = dropzip ] || [ "$word" = unpack ] || [ "$word" = sweep ] || [ "$word" = bank ]; then
  [ $# -eq 2 ] || { echo "refusing: $word takes exactly one id"; exit 64; }
  case "$id" in ""|*[!a-z0-9_]*) echo "refusing: an id is lower-case letters, digits and _"; exit 64 ;; esac
  [ ${#id} -le 40 ] || { echo "refusing: an id is at most 40 characters"; exit 64; }
elif [ "$word" = experiment ]; then
  [ $# -eq 2 ] || { echo "refusing: experiment takes exactly one issue number"; exit 64; }
  case "$id" in ""|*[!0-9]*|0*) echo "refusing: an issue is digits alone, with no leading zero"; exit 64 ;; esac
  [ ${#id} -le 9 ] || { echo "refusing: an issue is at most 9 digits"; exit 64; }
elif [ "$word" = cancel ]; then
  [ $# -eq 2 ] || { echo "refusing: cancel takes exactly one job"; exit 64; }
  case "$id" in ""|*[!0-9]*) echo "refusing: a job is digits alone"; exit 64 ;; esac
  [ ${#id} -le 12 ] || { echo "refusing: a job is at most 12 digits"; exit 64; }
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

# shellcheck source=grid/hpcw.sh
. "$REPO/grid/hpcw.sh"
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
# status still reads what it can without one (the logs of jobs queued before issue #77 among it)
[ "$word" = status ] || hpcw_bin > /dev/null || { echo "schwingnet $word: exit 2"; exit 2; }

commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)
echo "schwingnet $word${id:+ $id} at commit $commit on $(hostname) $(date -u '+%F %T') UTC"

record() {  # record ID WHAT: one line of the gate's own job list, the word with its id (fetch:<id>)
  echo "$1 $word${id:+:$id} $2 $(date -u '+%FT%TZ')" >> "$STATE"
  echo "  $2: job $1"
}
submit() {  # submit WHAT CLASS [K=V...] [job submit options...] -- SCRIPT: the job id on stdout, the record on stderr
  local what=$1 out
  out=$(hpcw_submit "$@" 2>&1) || { echo "  $out" >&2; return 1; }
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
  [ -n "$job" ] || job=$(submit setup batch -- 00-setup.sbatch) || return 1
  echo "afterok:$job"
}
joined() {  # joined DEP...: the non-empty dependencies, comma-separated
  local out="" one
  for one in "$@"; do [ -n "$one" ] && out=${out:+$out,}$one; done
  echo "$out"
}
depend_on() {  # depend_on DEPS: job submit's --after options for DEPS (sbatch's text) into opts, none when DEPS is empty
  # job submit adds --kill-on-invalid-dep=yes itself, so a dependency that can never be met ends the job
  hpcw_after "$1" || return 1
  opts=(${HPCW_AFTER[@]+"${HPCW_AFTER[@]}"})
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
checkout_holders() {  # afterany:<job> for every live job of the gate's that holds the checkout while it runs, comma-joined
  # A version 1 run, a sweep and an experiment run each write grid/logs/HOLD, one file naming one
  # job, and the first of two side by side to end would clear it while the other still runs, whose
  # end check then finds the checkout moved and throws the run away; so each waits for the others.
  local job waits=""
  [ -f "$STATE" ] || return 0
  for job in $(awk '$3 == "v1_driver" || $3 == "sweep" || $3 ~ /^experiment_[0-9]+$/ { print $1 }' "$STATE" | sort -u); do
    case "$QUEUED" in *" $job "*) waits=$(joined "$waits" "afterany:$job") ;; esac
  done
  echo "$waits"
}
v1_driver() {  # v1_driver DEPS: the version 1 run after DEPS and after every live run that holds the checkout
  local opts
  depend_on "$(joined "$1" "$(checkout_holders)")" || return 1
  # ${a[@]+"${a[@]}"}: the grid's bash 4.2 calls an empty array unbound under set -u
  submit v1_driver gpu RUNS="$RUNS" WEIGHTS="$WEIGHTS" ${opts[@]+"${opts[@]}"} --no-requeue -- v1-driver.sbatch >/dev/null
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
    job=$(submit weights batch MODELS="$MODELS" -- 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  depend_on "$setup" || return 1
  ingest=$(submit carmlspine batch ${opts[@]+"${opts[@]}"} -- 00-carmlspine.sbatch) || return 1
  # The first catalog version: C-ArmLSpine and every shard already on the data root, built once the
  # ingest ends, so the version 1 run starts hours after it and not days after the X-ray fetch. The
  # X-ray chain's own catalog job builds the next version after it, once its banks are in.
  depend_on "$(joined "$setup" "afterany:$ingest")" || return 1
  first=$(submit catalog batch ${opts[@]+"${opts[@]}"} -- 03-catalog.sbatch) || return 1
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
# Matched against what the gate recorded the job as (GATE_JOBS.txt), never the name Slurm shows.
OPEN_LOGS=" setup weights "
newest_jobs() {  # " <id> <id> ... ": the newest job the gate submitted for each thing it makes
  # Keyed by what was made, so a v1 that ran the ingest again hides start's failed one; an X-ray
  # job's key carries its word, so each fetch's chain is its own, and so does a sweep's, each plan's.
  echo " $(tac "$STATE" 2>/dev/null | awk '{ key = $3; if (key ~ /^xr_/ || key == "sweep") key = $2 " " key; if (!(key in seen)) { seen[key] = 1; print $1 } }' | tr '\n' ' ') "
}
what_of() {  # what_of ID: what the gate recorded job ID as
  awk -v j="$1" '$1 == j { what = $3 } END { print what }' "$STATE" 2>/dev/null
}
masked() {  # every line status shows of a log or a stage report: masked, then cut
  sed -r -f "$REPO/grid/redact.sed" | cut -c "1-$LINE_CHARS"
}
report_shapes() {  # a stage report's lines with their paths cut and a quoting reason withheld
  awk -v data="$DATA_ROOT" -v runs="$RUNS" -v models="$MODELS" -v repo="$REPO" \
    -f "$REPO/grid/shape-words.awk" -f "$REPO/grid/report-shapes.awk"
}
printable() {  # the last 64 KiB of stdin as lines of printable ASCII
  tail -c 65536 | tr '\r' '\n' | LC_ALL=C tr -cd '\11\12\40-\176'
}
log_text() {  # log_text ID TASK NAME: the end of a job's output, or nothing when there is none
  local id=$1 task=$2 name=$3 out old
  # hpcworker's log of the job, which job submit wrote (issue #77)
  if out=$(hpcw log --project "$HPCW_PROJECT" "$id" ${task:+--task "$task"} --lines "$SHAPE_LINES" 2>/dev/null) \
    && [ -n "$out" ] && [[ $out != "HPCW-JOB no output yet"* ]]; then
    printf '%s\n' "$out" | printable
    return 0
  fi
  # a job sbatch queued before then wrote logs/<Slurm's name>_<id>.out (_<task> for an array task;
  # _4294967294, Slurm's NO_VAL, for a job that is no array but whose script named its log %x_%A_%a)
  [[ $name =~ ^[A-Za-z0-9_.-]+$ ]] || return 0
  for old in "$LOGS/${name}_$id${task:+_$task}.out" "$LOGS/${name}_${id}_4294967294.out"; do
    [ -f "$old" ] && { printable < "$old"; return 0; }
  done
}
log_tail() {  # log_tail WHAT: a failed job's log on stdin, its end whole for an open job, as shapes otherwise
  local kept withheld
  case "$OPEN_LOGS" in
    *" $1 "*) tail -n "$TAIL_LINES" | masked | sed 's/^/    /'; return ;;
  esac
  kept=$(tail -n "$SHAPE_LINES" | awk -f "$REPO/grid/shape-words.awk" -f "$REPO/grid/log-shapes.awk")
  withheld=$(echo "$kept" | sed -n 's/^#withheld \([0-9][0-9]*\)$/\1/p' | tail -n 1)
  echo "$kept" | grep -v '^#withheld ' | tail -n "$TAIL_LINES" | masked | sed 's/^/    /'
  echo "    (${withheld:-0} of its last $SHAPE_LINES lines withheld: this job can print DICOM header values, person keys or a sign-in, so only its tracebacks and status lines are shown; the whole log stays on the grid)"
}
failed_tails() {  # failed_tails SACCT: the end of the log of each newest job that failed
  local newest shown=0 more=0 tasks="" job name state elapsed code node base task end what text
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
    if ! [[ $job =~ ^[0-9]+(_[0-9]+)?$ ]]; then
      echo "## $base ended $end; no log can be named from what sacct gave"; continue
    fi
    task=""; [ "$base" = "$job" ] || task=${job#*_}
    what=$(what_of "$base")
    echo "## $job (${what:-unrecorded}) ended $end after $elapsed, exit $code"
    text=$(log_text "$base" "$task" "$name")
    if [ -n "$text" ]; then
      printf '%s\n' "$text" | log_tail "$what"
    elif [ "$end" = CANCELLED ]; then
      echo "    cancelled before it started (a job it waited on failed, or 'stop'); no log"
    else
      echo "    no log of it yet"
    fi
  done <<< "$1"
  [ "$more" = 0 ] || echo "## $more more failed jobs not shown; their logs stay on the grid"
}

probe_text() {  # a heading line, then the newest latency probe's output; nothing when there is none
  # Since issue #77 the probe (latency_probe) logs to hpcworker's folder, read by its recorded id; a
  # probe sbatch queued before then left grid/logs/sn_probe_<id>_4294967294.out, read when no
  # recorded probe has output.
  local id out probe
  id=$(awk '$3 == "probe" { job = $1 } END { print job }' "$STATE" 2>/dev/null)
  if [ -n "$id" ] && out=$(log_text "$id" "" sn_probe) && [ -n "$out" ]; then
    echo "## the latency probe: job $id"
    printf '%s\n' "$out"
    return 0
  fi
  probe=$(ls -1t "$LOGS"/sn_probe_*.out 2>/dev/null | head -n 1)
  [ -n "$probe" ] || return 0
  echo "## the latency probe: $(basename "$probe") ($(date -r "$probe" '+%F %T'))"
  cat "$probe"
}
latency_lines() {  # the newest run's parity, latency and sweep numbers, one line a file (#99)
  local run file files=()
  run=$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1)
  [ -n "$run" ] || return 0
  for file in "$run"onnx/parity-*.json "$run"latency/*.json "$run"evaluate/latency.json "$run"sweep/*/summary.json; do
    [ -f "$file" ] && files+=("$file")
  done
  [ ${#files[@]} -gt 0 ] || return 0
  # Before the stage reports, so the 200 lines status keeps never cut the timing off.
  echo "## latency of the newest run, $(basename "$run")"
  awk -f "$REPO/grid/latency-lines.awk" "${files[@]}" | masked | sed 's/^/  /'
}

# The owner's tally of the lab volume (2026-10-22: "keep a tally of how much space ive used on ceph
# oschome"), so he chooses which sets stay on it at once and cycles the rest in and out. CephFS keeps
# each folder's recursive size as the attribute ceph.dir.rbytes, read at once whatever the tree
# holds, so no du walks millions of files; where the attribute is not there the size reads unknown.
rbytes_of() {  # the size rule's own reading (grid/size-rule.sh), read whole, so a value with a NUL or that is no count reads unknown
  xattr_whole ceph.dir.rbytes "$1"
}
gb_of() {  # whole GB, rounded up, of a byte count
  awk -v b="$1" 'BEGIN { printf "%d", (b + 999999999) / 1000000000 }'
}
space_lines() {  # one folder's sets, largest first: GB and the set's folder name
  local root=$1 one bytes
  for one in "$root"/*/; do
    [ -d "$one" ] || continue
    bytes=$(rbytes_of "${one%/}")
    if [ -n "$bytes" ]; then echo "$(gb_of "$bytes") $(basename "$one")"; else echo "? $(basename "$one")"; fi
  done | sort -k1,1nr
}
word_space() {
  local root label bytes
  # Labels, never paths: status leaves the grid, and its answer names no folder of the volume.
  echo "## space on the lab volume (CephFS ceph.dir.rbytes; GB rounded up)"
  # The room under the quota as the size rule reads it (grid/size-rule.sh, #160), never df, which on
  # CephFS reports the whole Ceph pool: 5,881,937 GB free on 2026-10-23 under a quota of 21,991 GB.
  DATA=$DATA_ROOT quota_readout "$VOLUME" "Lab Volume Disk Usage (CephFS quota; 1 gb = 10^9 bytes)" | sed 's/^/  /'
  for label in "data" "shared datasets"; do
    if [ "$label" = data ]; then root=$DATA_ROOT; else root=$SHARED_DATA; fi
    [ -d "$root" ] || { echo "  $label: not there"; continue; }
    bytes=$(rbytes_of "$root")
    if [ -n "$bytes" ]; then echo "  $label: $(gb_of "$bytes") GB in all"; else echo "  $label: ? GB in all"; fi
    space_lines "$root" | head -n 80 | sed 's/^/    /'
  done
}

samples_report() {  # the sample index's manifest, whole: counts per source and nothing else
  # (tools/sample_index.py), read up to the 180 lines run-samples.sh's report gives. Status's 400
  # lines once cut it off, after the jobs, and masked's 200 characters cut its widest rows, the
  # bank root that a dozen X-ray sources share, so the rows are folded, not cut, after the masks.
  # A root the manifest and the registry leave unmapped is named by its folder under the data
  # root, which the report's own path cuts show too; written "unmapped <folder>" here, since
  # redact.sed withholds "<word>:<value>" as a person key.
  local report=$LOGS/SAMPLES-STAGE-REPORT.md
  [ -f "$report" ] || return 0
  echo "## SAMPLES-STAGE-REPORT.md ($(date -r "$report" '+%F %T'))"
  head -n 180 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | sed 's/unmapped:/unmapped /g' \
    | report_shapes | sed -r -f "$REPO/grid/redact.sed" | fold -w $((LINE_CHARS - 10)) | sed 's/^/  /'
}

attr_digits() {  # attr_digits NAME FOLDER: one CephFS attribute's leading digits up to its first NUL, or nothing
  # Leading digits, since ceph.dir.rctime is seconds and nanoseconds; as a count only, as the size
  # rule takes one (is_count), since an age is worked out from them in bash's arithmetic.
  local digits
  digits=$(xattr_value "$1" "$2" | sed -n 's/^\([0-9][0-9]*\).*/\1/p')
  if is_count "$digits"; then echo "$digits"; fi
}
fetch_progress() {  # one line per live fetch of one set: what its raw folder holds, read with no walk
  # A fetch runs for hours and status shows a job's log only once it has ended, so until this nobody
  # could tell a slow fetch from a stalled one without a grid shell (#125). CephFS keeps each
  # folder's recursive file count, size and newest change as attributes, three reads on the login
  # node in place of a find over thousands of files, and no file name leaves the grid.
  local job from what id raw files bytes written now age seen=" "
  [ -f "$STATE" ] || return 0
  now=$(date -u +%s)
  tac "$STATE" | while read -r job from what _; do
    [ "$what" = xr_fetch ] || continue
    case "$from" in fetch:*) id=${from#fetch:} ;; *) continue ;; esac
    case "$QUEUED" in *" $job "*) ;; *) continue ;; esac
    case "$seen" in *" $id "*) continue ;; esac
    seen="$seen$id "
    raw=$DATA_ROOT/$id/raw
    [ -d "$raw" ] || { echo "  fetch of $id (job $job): nothing landed yet"; continue; }
    files=$(attr_digits ceph.dir.rfiles "$raw"); bytes=$(attr_digits ceph.dir.rbytes "$raw"); written=$(attr_digits ceph.dir.rctime "$raw")
    if [ -z "$files" ] || [ -z "$bytes" ] || [ -z "$written" ]; then
      echo "  fetch of $id (job $job): the raw folder is there; its size is not readable here (no CephFS attributes)"
      continue
    fi
    age=$((now - written))
    if [ "$age" -lt 120 ]; then age="${age}s ago"
    elif [ "$age" -lt 7200 ]; then age="$((age / 60)) min ago"
    else age="$((age / 3600)) h ago"; fi
    echo "  fetch of $id (job $job): $files files, $(( (bytes + 999999) / 1000000 )) MB, last write $age"
  done
}

word_status() {
  local ids report run lines shown job name state elapsed code node probe
  # First, so the status's 400 lines never cut it off; then the sweeps' progress, the one live view
  # of a sweep, which once came last and was cut, held to its own bound so that the two together
  # stay inside the 400 lines whatever the sections after them hold; then the sample manifest.
  word_space
  sweep_progress | head -n "$SWEEP_LINES_SHOWN"
  samples_report
  ids=$(gate_ids | tail -n 60 | tr '\n' ',' | sed 's/,$//')
  if [ -z "$ids" ]; then
    echo "no job submitted by the gate yet; 'start' submits the graph"
  else
    echo "## the gate's newest jobs (sacct): id, what, state, elapsed, exit code, node"
    lines=$("$SACCT" -X -n -P -j "$ids" --format=JobID,JobName,State,Elapsed,ExitCode,NodeList 2>/dev/null)
    while IFS='|' read -r job name state elapsed code node; do
      [ -n "$job" ] || continue
      echo "  $job $(what_of "${job%%_*}") $state $elapsed $code $node"
    done <<< "$lines"
    fetch_progress
    failed_tails "$lines"
  fi
  # The latency probe's answer (#87): counts, sizes, PNG dimensions and the export's meta keys only,
  # never a DICOM header, printed before the reports so it stays inside status's 200 lines; only
  # its own lines' shapes, with no folder or file name (grid/probe-shapes.awk), then masked (#80).
  probe=$(probe_text)
  if [ -n "$probe" ]; then
    printf '%s\n' "$probe" | head -n 1
    printf '%s\n' "$probe" | tail -n +2 | head -n 40 | LC_ALL=C tr -cd '\11\12\40-\176' \
      | awk -f "$REPO/grid/probe-shapes.awk" | masked | sed 's/^/  /'
  fi
  latency_lines
  for report in "$LOGS"/*STAGE-REPORT.md; do
    [ -f "$report" ] || continue
    [ "$(basename "$report")" != SAMPLES-STAGE-REPORT.md ] || continue
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

# A plan's section is its heading, its headline, up to SWEEP_ROWS_SHOWN rows, the line counting the
# rest and up to SWEEP_WANDB_SHOWN links, 27 lines; the four plans of grid/sweeps/ take 108 of the
# section's 120, and the space tally before it at most about 180, so both fit inside status's 400.
SWEEP_ROWS_SHOWN=20 SWEEP_WANDB_SHOWN=4 SWEEP_LINES_SHOWN=120
smoke_paths() {  # every line with the smoke folder's path cut to <smoke>, matched as text and not as a pattern
  awk -v smoke="$SMOKE" '{
    while (smoke != "" && (at = index($0, smoke)) > 0) $0 = substr($0, 1, at - 1) "<smoke>" substr($0, at + length(smoke))
    print }'
}
progress_lines() {  # progress_lines FILE: a sweep's PROGRESS.txt as status shows it
  # Its headline, the rows that have not matched their prediction yet (failed, mismatched or still
  # to come; the rows that matched are counted on the headline) and its W&B links. tools/block_sweep.py
  # writes the file whole and renames it into place, so it never reads half written.
  local unmatched count
  head -n 1 "$1"
  unmatched=$(tail -n +2 "$1" | awk '$1 == "row" && ($3 == "failed" || $3 == "to-come" || $3 == "to_come" ||
                                                    $4 == "no" || $4 == "false" || $4 == "mismatched")')
  count=$(printf '%s' "$unmatched" | grep -c '^row ')
  [ -z "$unmatched" ] || printf '%s\n' "$unmatched" | head -n "$SWEEP_ROWS_SHOWN"
  [ "$count" -le "$SWEEP_ROWS_SHOWN" ] \
    || echo "($((count - SWEEP_ROWS_SHOWN)) more rows not yet matched; the state folder's PROGRESS.txt holds them)"
  tail -n +2 "$1" | awk '$1 == "wandb"' | head -n "$SWEEP_WANDB_SHOWN"
}
sweep_progress() {  # for each plan under SMOKE, its newest sweep's PROGRESS.txt (issue #252)
  local plan progress
  for plan in "$SMOKE"/*/; do
    [ -d "$plan" ] || continue
    # A state folder is one that holds PROGRESS.txt, so the synthetic plan's catalog beside them is passed over.
    progress=$(ls -1t "$plan"*/PROGRESS.txt 2>/dev/null | head -n 1)
    [ -n "$progress" ] || continue
    echo "## sweep $(basename "$plan"), $(basename "$(dirname "$progress")") ($(date -r "$progress" '+%F %T'))" \
      | LC_ALL=C tr -cd '\11\12\40-\176' | masked
    progress_lines "$progress" | LC_ALL=C tr -cd '\11\12\40-\176' | smoke_paths | masked | sed 's/^/  /'
  done
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
    job=$(submit weights batch MODELS="$MODELS" -- 00-weights.sbatch) || return 1
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
    depend_on "$setup" || return 1
    ingest=$(submit carmlspine batch ${opts[@]+"${opts[@]}"} -- 00-carmlspine.sbatch) || return 1
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
    depend_on "$(joined "$setup" "$ingest_dep")" || return 1
    catalog=$(submit catalog batch ${opts[@]+"${opts[@]}"} -- 03-catalog.sbatch) || return 1
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
  # A look at the set taken before this fetch no longer says what it holds (word_explore).
  rm -f "$LOGS/EXPLORE-$id.md" "$LOGS/EXPLORE-$id.md.key"
  section=$(awk -v id="$id" '
    /"credentialed": \[/ { cred = 1 }
    index($0, "\"id\": \"" id "\"") { print (cred ? "credentialed" : "open"); exit }' "$REPO/grid/fetch-xray.json")
  if [ -z "$section" ]; then
    gated_platform_id || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
    word_fetch_gated
    return
  fi
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

gated_platform_id() {  # whether $id is one of the granted gated CT sources the platform script fetches alone
  bash "$REPO/grid/run-platform-fetch.sh" --gated-ids 2>/dev/null | grep -qxF -- "$id"
}
word_fetch_gated() {  # one gated CT source through the platform script, recorded as dp_<id> under fetch:<id>
  local busy xray="" one out rc
  # One fetch of a source at a time: two would write the same landing at once.
  busy=$(live_of "dp_$id")
  [ -z "$busy" ] || { echo "refusing: a fetch of $id is still queued or running (job $busy)"; return 75; }
  # X-ray before CT (the owner's order of 2026-10-21): the CT fetch waits on every X-ray fetch still live.
  for one in $(awk '$3 == "xr_fetch" { print $1 }' "$STATE" 2>/dev/null | sort -u); do
    case "$QUEUED" in *" $one "*) xray=$(joined "$xray" "afterany:$one") ;; esac
  done
  out=$(DEPEND="$xray" bash "$REPO/grid/run-platform-fetch.sh" --only "$id" 2>&1)
  rc=$?
  # The platform script's list of the owner's own lines (CT-RATE, NLST) is not this word's business.
  echo "$out" | sed -n '/^Not submitted/q; p' | sed 's/^/  /'
  echo "$out" | sed -n 's/^\([a-z0-9_]*\): job \([0-9][0-9]*\).*/\2 \1/p' | while read -r one name; do
    record "$one" "dp_$name"
  done
  return $rc
}

explore_against() {  # the sets $id is compared with, label=folder joined by |; nothing for most sets
  # The Kaggle scoliosis export (spine-datasets #23) may be AASCE's films re-exported by Roboflow:
  # both AASCE copies on the volume, as grid/fetch-xray.json's confirm list for it names them.
  case "$id" in
    kaggle_scoliosis_yolov5)
      echo "AASCE-ke30-mirror=$DATA_ROOT/thoracic_xr/mirror_zlinzju_ke30_u7_AASCE2019|AASCE-BoostNet=$DATA_ROOT/aasce2019_boostnet/raw/aasce" ;;
  esac
}
explore_tool_key() {  # what a report must have been written by to be printed: the tool's own hash
  sha256sum < "$REPO/tools/explore.py" | cut -c1-12
}
word_explore() {
  local raw report busy against
  raw=$DATA_ROOT/$id/raw report=$LOGS/EXPLORE-$id.md
  grep -q "\"id\": \"$id\"" "$REPO/grid/fetch-xray.json" || gated_platform_id \
    || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
  busy=$(live_of explore "explore:$id")
  [ -z "$busy" ] || { echo "refusing: the look at $id is still queued or running (job $busy); send explore $id again once it ends"; return 75; }
  if [ -f "$report" ] && [ "$(cat "$report.key" 2>/dev/null)" = "$(explore_tool_key)" ]; then
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 300 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 60000
    return 0
  fi
  busy=$( { live_of xr_fetch "fetch:$id"; live_of "dp_$id"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a fetch of $id is still queued or running (job $busy)"; return 75; }
  [ -d "$raw" ] || { echo "refusing: $id has no raw folder on the data root yet; fetch it first"; return 2; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  against=$(explore_against)
  rm -f "$report" "$report.key"
  explore_tool_key > "$report.key"
  submit explore batch EXPLORE_ID="$id" EXPLORE_RAW="$raw" EXPLORE_AGAINST="$against" -- explore.sbatch > /dev/null || return 1
  echo "submitted one job. Send explore $id again once it ends to read the report."
}

word_dropzip() {
  local raw report busy
  raw=$DATA_ROOT/$id/raw report=$LOGS/DROPZIP-$id.md
  grep -q "\"id\": \"$id\"" "$REPO/grid/fetch-xray.json" || gated_platform_id \
    || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
  busy=$(live_of dropzip "dropzip:$id")
  [ -z "$busy" ] || { echo "refusing: the deletion for $id is still queued or running (job $busy); send dropzip $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Printed once: the next send looks again, so a zip a later fetch leaves is settled too.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 100 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 20000
    rm -f "$report"
    return 0
  fi
  # Never while the set is still landing or being read: a zip half unpacked has members not yet beside it.
  busy=$( { live_of xr_fetch "fetch:$id"; live_of "dp_$id"; live_of explore "explore:$id"; live_of unpack "unpack:$id"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a fetch, an unpacking or a look at $id is still queued or running (job $busy)"; return 75; }
  [ -d "$raw" ] || { echo "refusing: $id has no raw folder on the data root yet; fetch it first"; return 2; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  submit dropzip batch DROPZIP_ID="$id" DROPZIP_RAW="$raw" -- dropzip.sbatch > /dev/null || return 1
  echo "submitted one job. Send dropzip $id again once it ends to read what it deleted."
}

word_unpack() {
  local raw report busy
  raw=$DATA_ROOT/$id/raw report=$LOGS/UNPACK-$id.md
  grep -q "\"id\": \"$id\"" "$REPO/grid/fetch-xray.json" || gated_platform_id \
    || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
  busy=$(live_of unpack "unpack:$id")
  [ -z "$busy" ] || { echo "refusing: the unpacking of $id is still queued or running (job $busy); send unpack $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 100 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 20000
    rm -f "$report"
    return 0
  fi
  # Never beside a fetch of the set, a look at it or a deletion of its zips.
  busy=$( { live_of xr_fetch "fetch:$id"; live_of "dp_$id"; live_of explore "explore:$id"; live_of dropzip "dropzip:$id"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a fetch, a deletion or a look at $id is still queued or running (job $busy)"; return 75; }
  [ -d "$raw" ] || { echo "refusing: $id has no raw folder on the data root yet; fetch it first"; return 2; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  submit unpack batch UNPACK_ID="$id" UNPACK_RAW="$raw" DATA_ROOT="$DATA_ROOT" VOLUME="$VOLUME" -- unpack.sbatch > /dev/null || return 1
  echo "submitted one job. It starts writing only once the size rule admits it; send unpack $id again once it ends to read what it wrote."
}

experiment_request() {  # experiment_request N: the lines the workflow recorded for issue N, on stdout
  # From the branch experiments on origin, fetched now, since the gate's side brings main alone; a test
  # sets EXPERIMENTS_DIR to a folder of such files instead, where no origin answers.
  if [ -n "${EXPERIMENTS_DIR:-}" ]; then cat "$EXPERIMENTS_DIR/$1.request" 2>/dev/null; return; fi
  git -C "$REPO" fetch -q --no-tags origin "+refs/heads/experiments:refs/remotes/origin/experiments" 2>/dev/null || return 1
  git -C "$REPO" show "refs/remotes/origin/experiments:$1.request" 2>/dev/null
}
experiment_lines_ok() {  # experiment_lines_ok FILE: every line has the shape the workflow writes, the four settings once each
  # The shapes alone, on the login node, where no python runs; the driver checks the values against the
  # blocks module inside the container before anything trains.
  local n=0 line key
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    [ $n -le 40 ] || { echo "refusing: the request has more than 40 lines"; return 1; }
    [ ${#line} -le 120 ] || { echo "refusing: line $n of the request is over 120 characters"; return 1; }
    case "$line" in *[!A-Za-z0-9._,=:\ -]*) echo "refusing: line $n of the request holds a character outside letters, digits and . _ , = : -"; return 1 ;; esac
    case "$line" in
      "recipe: "[a-z]*|"epochs: "[1-9]*|"seed: "[0-9]*|"hours: "[0-9]*|"block: "[a-z]*=?*) ;;
      *) echo "refusing: line $n of the request is not one the gate takes: $(printf '%s' "$line" | cut -c1-60)"; return 1 ;;
    esac
  done < "$1"
  for key in recipe epochs seed hours; do
    [ "$(grep -c "^$key: " "$1")" = 1 ] || { echo "refusing: the request names $key once, not $(grep -c "^$key: " "$1") times"; return 1; }
  done
}
experiment_wall() {  # experiment_wall HOURS: the job's wall time as Slurm takes it, H:MM:00
  # The request's hours are the training's (the panel's "the training job's wall time"); in this one job the
  # evaluation follows the training, given a quarter of its hours as flow.py's slurm mode gives it, and an
  # hour more holds the checks and the container's start. Never less than the driver's own 24 hours, which
  # the version 1 run proved, so a short request runs as v1 did and a long one gets the time it asked for.
  awk -v h="$1" 'BEGIN { m = int((h * 1.25 + 1) * 60 + 0.999); if (m < 1440) m = 1440; printf "%d:%02d:00\n", int(m / 60), m % 60 }'
}
word_experiment() {
  local req=$LOGS/experiment-$id.request busy version hours wall holds opts
  busy=$(live_of "experiment_$id")
  [ -z "$busy" ] || { echo "refusing: the run for #$id is already queued or running (job $busy)"; return 75; }
  if ! experiment_request "$id" > "$req.new" || [ ! -s "$req.new" ]; then
    rm -f "$req.new"
    echo "refusing: no $id.request on the branch experiments; the experiment workflow writes it when issue #$id's combination holds (grid/README.md)"
    return 75
  fi
  mv "$req.new" "$req"
  experiment_lines_ok "$req" || { rm -f "$req"; return 64; }
  hours=$(sed -n 's/^hours: //p' "$req")
  case "$hours" in ''|*[!0-9.]*|*.*.*|.*|*.) rm -f "$req"; echo "refusing: hours is a number such as 4 or 2.5, not ${hours:-nothing}"; return 64 ;; esac
  wall=$(experiment_wall "$hours")
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  weights_ready || { echo "refusing: no ImageNet weights at $WEIGHTS; 'v1' makes them first"; return 75; }
  carmlspine_ready || { echo "refusing: C-ArmLSpine's train and test shards are not on the data root; 'v1' makes them first"; return 75; }
  version=$(v1_version) || { echo "refusing: no catalog version qualifies (grid/v1-version.sh); 'v1' builds one first"; return 75; }
  echo "  catalog: $version qualifies for the run (grid/v1-version.sh); no job"
  echo "  request: $(tr '\n' ' ' < "$req")"
  echo "  wall time: $wall for $hours hours of training"
  # Queued after every run that holds the checkout, as a sweep is, rather than refused.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$holds" || return 1
  submit "experiment_$id" gpu REQUEST="$req" ISSUE="$id" RUNS="$RUNS" WEIGHTS="$WEIGHTS" ${opts[@]+"${opts[@]}"} \
    --no-requeue --time "$wall" -- experiment-driver.sbatch > /dev/null || return 1
  echo "submitted one job. 'status' shows it; its report is logs/experiment-$id-STAGE-REPORT.md"
}
word_nodequota() {
  local report=$LOGS/NODEQUOTA.md busy
  busy=$(live_of nodequota)
  [ -z "$busy" ] || { echo "refusing: the node's readout is still queued or running (job $busy); send nodequota again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Printed once, so the send after it reads a node again.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 100 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 20000
    rm -f "$report"
    return 0
  fi
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  submit nodequota batch -- nodequota.sbatch > /dev/null || return 1
  echo "submitted one job. Send nodequota again once it ends to read what the node read."
}

word_samples() {
  local busy said rc
  busy=$( { live_of samples_plan; live_of samples_scan; live_of samples_merge; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: the sample index is still queued or running (jobs $busy)"; return 75; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  said=$(bash "$REPO/grid/run-samples.sh" 2>&1)
  rc=$?
  echo "$said" | sed 's/^/  /'
  # Every job this call printed is recorded, a refusal part-way or not, so 'stop' reaches it.
  echo "$said" | sed -n 's/^\(samples_[a-z]*\): job \([0-9][0-9]*\)$/\2 \1/p' | while read -r job what; do
    record "$job" "$what" > /dev/null
  done
  [ "$rc" = 0 ] || return 1
  echo "submitted. 'status' shows the index's MANIFEST.md (counts per source) once the merge ends."
}

# The block smoke test (issue #252). A plan is a file tools/block_sweep.py wrote with indent 1 and
# sorted keys, so its own keys are the lines one space in and a row's sit deeper; the login node
# runs no python, so sed and grep read it.
sweep_plans() {  # the plans under grid/sweeps/, by name
  local one names=""
  for one in "$REPO"/grid/sweeps/*.json; do [ -f "$one" ] && names="$names $(basename "$one" .json)"; done
  echo "${names# }"
}
plan_catalog() {  # plan_catalog FILE: the plan's catalog: synthetic, v1 or with:<source>
  sed -n 's/^ "catalog": "\([^"]*\)",\{0,1\}$/\1/p' "$1" | head -n 1
}
plan_names_weights() {  # plan_names_weights FILE: whether a row of the plan starts from an ImageNet file
  grep -q '^  *"weights": "[^"]' "$1"
}
CATALOG_DEP=""
sweep_catalog() {  # sweep_catalog CATALOG: the wait a plan's real catalog needs, in CATALOG_DEP; 75 with the reason where none can come
  # A live catalog build of the gate's goes first, start's, v1's or a bank's, since the version the
  # run reads is chosen when it starts (grid/v1-version.sh); else a version that qualifies now.
  local source="" job version
  CATALOG_DEP=""
  case "$1" in with:*) source=${1#with:} ;; esac
  job=$(live_of catalog)
  if [ -n "$job" ]; then
    CATALOG_DEP="afterok:$job"
    echo "  catalog: after the live catalog build, job $job"
    return 0
  fi
  if version=$(bash "$REPO/grid/v1-version.sh" "$STORE" "$DATA_ROOT" "$REPO" ${source:+"$source"} 2>/dev/null); then
    echo "  catalog: $version qualifies (grid/v1-version.sh $1); no job"
    return 0
  fi
  if [ -z "$source" ]; then
    echo "refusing: no catalog version qualifies for the v1 plan and no catalog build of the gate's is live; the v1 word or start makes the catalog first"
  else
    echo "refusing: no catalog version holds $source's train part beside C-ArmLSpine's and no catalog build of the gate's is live; bank $source first"
  fi
  return 75
}
word_sweep() {
  local plan=$REPO/grid/sweeps/$id.json catalog source running setup job weights_dep="" holds opts
  [ -f "$plan" ] || { echo "refusing: $id is not a plan under grid/sweeps/ (the plans: $(sweep_plans))"; return 64; }
  running=$(live_of sweep "sweep:$id")
  [ -z "$running" ] || { echo "refusing: a sweep of $id is already queued or running (job $running); 'status' follows it"; return 75; }
  # Every refusal before any job is queued, so a refused word leaves nothing behind.
  catalog=$(plan_catalog "$plan")
  case "$catalog" in
    synthetic) CATALOG_DEP=""; echo "  catalog: the synthetic one, which the run builds once under the smoke folder or finds there" ;;
    v1) sweep_catalog v1 || return ;;
    with:*)
      source=${catalog#with:}
      case "$source" in ""|*[!a-z0-9_]*) echo "refusing: grid/sweeps/$id.json names the catalog '$catalog', whose source is no id"; return 2 ;; esac
      sweep_catalog "$catalog" || return ;;
    *) echo "refusing: grid/sweeps/$id.json names no catalog the sweep knows ('$catalog'; synthetic, v1 or with:<source>)"; return 2 ;;
  esac
  setup=$(setup_dependency) || return 1
  [ -n "$setup" ] || echo "  setup: the environments match pixi.lock; no job"
  if plan_names_weights "$plan" && ! weights_ready; then
    job=$(live_of weights)
    [ -n "$job" ] || job=$(submit weights batch MODELS="$MODELS" -- 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  # Queued after every run that holds the checkout rather than refused, so the sweeps the owner
  # sends together run one after another, each on the code it records.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$(joined "$setup" "$weights_dep" "$CATALOG_DEP" "$holds")" || return 1
  # Not requeued: the word sent again resumes the cut sweep through the launcher (flows/launch.py),
  # and a requeue racing that word would start a second launcher on the same flow run.
  submit sweep gpu PLAN="$id" SMOKE="$SMOKE" DATA_ROOT="$DATA_ROOT" WEIGHTS="$WEIGHTS" MODELS="$MODELS" \
    ${opts[@]+"${opts[@]}"} --no-requeue -- sweep-driver.sbatch > /dev/null || return 1
  echo "submitted. 'status' shows the plan's PROGRESS.txt once the sweep writes it; the same word again after a cut sweep ends resumes it."
}

unconfirmed_fields() {  # unconfirmed_fields FILE: how many of a recipe's values still start "to confirm", its notes aside
  # As tools/bank.py's unconfirmed() counts them, a string value starting so in any case, which it
  # refuses before banking a frame; the recipes keep one value a line, so grep counts them.
  grep -v '^  "notes":' "$1" | grep -ciE '(^|[^\\])"[[:space:]]*to confirm'
}
recipe_raw() {  # recipe_raw FILE: the raw folder a recipe of grid/banks/ names, as stage 2 reads it
  # Off the grid stage 2 reads <data root>/<id>/raw in place of the recipe's path (issue #40), and
  # the gate hands the stage a data root only where its caller gave one.
  if [ -n "$DATA_ROOT_GIVEN" ]; then echo "$DATA_ROOT/$id/raw"; return 0; fi
  sed -n 's/^ *"raw": *"\([^"]*\)".*/\1/p' "$1" | head -n 1
}
bank_room() {  # bank_room NEED: 0 where the room under the quota takes NEED bytes after what the running fetches owe, saying both
  # The room the fetch word's chain decides against (grid/size-rule.sh, run-xray-chain.sh): what the
  # running fetches owe first, then the room twice a minute apart, the smaller kept.
  local DATA=$DATA_ROOT owed owed_bytes owed_n unsized free free_from room
  owed=$(owed_by_running "") || { echo "refusing: squeue did not answer, so what the running fetches owe is not known; nothing was queued"; return 75; }
  read -r owed_bytes owed_n unsized <<< "$owed"
  [ -z "$unsized" ] || { echo "refusing: the running fetch of $unsized states no size, so the room after it is not known; nothing was queued"; return 75; }
  read -r free free_from <<< "$(settled_room "$VOLUME")"
  if [ -z "$free" ]; then
    echo "refusing: the room on the lab volume could not be read: $(room_unread_words "$VOLUME"); nothing was queued"
    return 2
  fi
  room=$(( free > owed_bytes ? free - owed_bytes : 0 ))
  echo "  room: $(gb_down "$room") GB $(free_space_words "$free_from") after $(gb_up "$owed_bytes") GB owed to $(running_fetches "$owed_n")"
  [ "$1" -le "$room" ] || { echo "refusing: the bank and its shard need $(gb_up "$1") GB and the room is $(gb_down "$room") GB; nothing was queued"; return 75; }
}
word_bank() {
  local recipe=$REPO/grid/banks/$id.json busy raw bytes need setup bank opts
  [ -f "$recipe" ] || { echo "refusing: $id is not a recipe under grid/banks/"; return 64; }
  # One bank and one build at a time: two banks of one set write the same bank folder, and the X-ray
  # chain's stage 2 banks every recipe its fetch names, start's every one there is.
  busy=$( { live_of bank; live_of catalog; live_of xr_bank; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a bank or a catalog build of the gate's is still queued or running (jobs $busy)"; return 75; }
  [ "$(unconfirmed_fields "$recipe")" = 0 ] \
    || { echo "refusing: grid/banks/$id.json still has a field spelled \"to confirm\"; stage 2 refuses it until the page is read and the field filled in"; return 2; }
  raw=$(recipe_raw "$recipe")
  [ -n "$raw" ] && [ -d "$raw" ] && [ -n "$(ls -A "$raw" 2>/dev/null | head -n 1)" ] \
    || { echo "refusing: $id's raw copy is not on the volume (its recipe's raw folder is missing or empty); fetch it first"; return 2; }
  # What the raw copy holds, read with no walk as the size rule reads a folder, whole: the bank is at
  # most the raw copy's size for the formats here, and its shard copies the bank's frames once more,
  # so the two jobs write at most twice the raw copy.
  bytes=$(xattr_whole ceph.dir.rbytes "$raw")
  [ -n "$bytes" ] || { echo "refusing: what $id's raw copy holds could not be read (ceph.dir.rbytes); nothing was queued"; return 2; }
  need=$(( 2 * bytes ))
  echo "  raw copy: $(gb_up "$bytes") GB; the bank and its shard: at most $(gb_up "$need") GB"
  bank_room "$need" || return
  setup=$(setup_dependency) || return 1
  [ -n "$setup" ] || echo "  setup: the environments match pixi.lock; no job"
  depend_on "$setup" || return 1
  bank=$(submit bank batch ONLY="$id" ${opts[@]+"${opts[@]}"} -- 02-bank-ingest.sbatch) || return 1
  # Recorded as catalog, so v1 and sweep wait on it as on any build of the gate's.
  depend_on "afterok:$bank" || return 1
  submit catalog batch ${opts[@]+"${opts[@]}"} -- 03-catalog.sbatch > /dev/null || {
    "$SCANCEL" "$bank" && echo "  cancelled the bank job $bank, so no bank runs that no catalog build follows"
    return 1
  }
  echo "submitted. 'status' shows the stage reports; a sweep sent while the build is live waits on it."
}

word_stop() {
  local live
  live=$(live_ids | tr '\n' ' ')
  [ -n "${live// /}" ] || { echo "nothing of the gate's is queued or running"; return 0; }
  # shellcheck disable=SC2086
  "$SCANCEL" $live && echo "cancelled: $live"
}

word_cancel() {  # the job named, if the gate's and live, with every live job of the same word
  local from cancel
  from=$(awk -v job="$id" '$1 == job { print $2; exit }' "$STATE" 2>/dev/null)
  [ -n "$from" ] || { echo "refusing: job $id is not one of the gate's"; return 64; }
  case "$QUEUED" in *" $id "*) ;; *) echo "job $id is no longer queued or running; nothing cancelled"; return 0 ;; esac
  cancel=$(awk -v from="$from" '$2 == from { print $1 }' "$STATE" | sort -u | while read -r job; do
    case "$QUEUED" in *" $job "*) echo "$job" ;; esac
  done | tr '\n' ' ')
  # shellcheck disable=SC2086
  "$SCANCEL" $cancel && echo "cancelled ($from): $cancel"
}

release_hold() {  # a run's hold (grid/v1-driver.sbatch, grid/sweep-driver.sbatch, grid/experiment-driver.sbatch) is cleared once Slurm no longer holds its job
  local job
  [ -f "$LOGS/HOLD" ] || return 0
  job=$(awk '{ print $1; exit }' "$LOGS/HOLD")
  case "$QUEUED" in
    *" $job "*) echo "  the checkout holds still at $(awk '{ print substr($2, 1, 7); exit }' "$LOGS/HOLD") while the run that took it (job $job) lasts" ;;
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
  explore) word_explore ;;
  dropzip) word_dropzip ;;
  unpack) word_unpack ;;
  nodequota) word_nodequota ;;
  experiment) word_experiment ;;
  samples) word_samples ;;
  sweep) word_sweep ;;
  bank) word_bank ;;
  stop) word_stop ;;
  cancel) word_cancel ;;
esac
rc=$?
echo "schwingnet $word: exit $rc"
exit $rc
