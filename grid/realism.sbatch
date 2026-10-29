#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# One stage of the FluXray reproduction (docs/research/flux-realism/PREREG.md), as one run of the
# Metaflow flow flows/realism.py, which flows/launch.py starts or resumes: the launcher is the one
# way a stage runs (the owner's rule of 2026-10-29 02:39 UTC), so the run is held to the frozen
# PREREG, writes its CLAIM 2024 and REFORMS report and keeps its progress page under the Metaflow
# datastore, progress/RealismFlow/<run>/index.html; tools/realism.py is never run here alone.
# grid/gate.sh's word `realism <stage>` queues it with STAGE in the environment, as one GPU job, on
# the owner's count of 2026-10-29 02:35 UTC (two GPU jobs, the edit and then the stats):
#
#   edit    every input checked and hashed, FluXray's poses, the subjects drawn by the frozen seed,
#           raw DRRs of their ENHANCE.PET CTs at the drawn poses with exact masks, the klein-9B edit
#           of each in the plan's seed arms, FluXray's paired filter with the flux000 member,
#           FluXray's own images of the same samples and the endplate angles at 1024 and at 256
#   stats   the kept edits and the raw renders, each against FluXray's images of the same samples, in
#           the three feature spaces, and the replication's one word
#
# lora and eval, the adapter's stages, are refused until they have a count and a PREREG of their own.
# Each run keeps its files under $REALISM_ROOT/<stage>-<run key>-<run id>/ on the lab volume; the report,
# logs/REALISM-<stage>.md, carries the launcher's decision, the flow's lines, the run's SUMMARY.md
# and where its progress page is, and the next `realism <stage>` prints it. The public packages go
# into a throwaway environment beside train-gpu's (venv_for), never into pixi.lock; they are the
# pins the PREREG froze (schwingnet.realism.PINS, which tools/realism.py inputs, in the edit, and
# environment, in the stats, hold the environment to, and tests/test_gate.py holds this line to).
# Not requeued (--no-requeue from the gate): the gate queues a failed stage again only once a fix
# has moved the checkout, and the launcher then resumes its run where the code the run executes is
# unchanged. A job Slurm ends with TERM, at its time limit or a cancel, still writes its exit, and
# one killed past that leaves logs/REALISM-<stage>.md.part, which the gate prints as unfinished. The
# checkout holds still while the stage lasts (grid/logs/HOLD), and a stage whose checkout moved
# anyway is failed, since its report names the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
MODELS=${MODELS:-$LAB/go2432/models}
REALISM_ROOT=${REALISM_ROOT:-$LAB/go2432/realism}
REALISM_PIN="diffusers==0.42.0 transformers==5.20.2 accelerate==1.15.0 peft==0.21.2 safetensors==0.8.0 huggingface_hub==2.3.0 flexray==1.0.2 lmdb==3.0.0 nibabel==5.3.2"
STAGE=${STAGE:-}
case "$STAGE" in
  edit|stats) ;;
  lora|eval) echo "realism: the stage $STAGE waits for a count and a PREREG of its own; this count runs edit or stats"; echo "SN_REALISM_RC=64"; exit 64 ;;
  *) echo "realism: STAGE is edit or stats"; echo "SN_REALISM_RC=64"; exit 64 ;;
esac
REPORT=$REPO/grid/logs/REALISM-$STAGE.md
mkdir -p "$REPO/grid/logs" "$REALISM_ROOT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
report() { echo "- $*" | tee -a "$REPORT.part"; }
pointer_field() {  # pointer_field NAME: one string field of the stage's pointer, as the flow's write_json lays it out
  sed -n "s/^ *\"$1\": *\"\([^\"]*\)\",\{0,1\}\$/\1/p" "$REALISM_ROOT/$STAGE.last.json" 2>/dev/null | head -n 1
}
summary() {  # summary DECISION RUN: this job's run folder, and the SUMMARY.md this job wrote there
  # The pointer the flow's start and end write outlives the job that wrote it, so it counts only
  # where it names the key the launcher's decision line gives this job and a run of this job's: the
  # run the launcher's last line names, or the run a resume carries on (the decision's origin, whose
  # start the resume clones, pointer and all); and SUMMARY.md only where this job wrote it. A
  # launcher that refused, or a start that failed before the pointer, would otherwise put an
  # earlier run's folder and numbers beside this job's exit.
  local key origin this named folder
  key=$(printf '%s\n' "$1" | sed -n 's/.*"key": *"\([^"]*\)".*/\1/p')
  origin=$(printf '%s\n' "$1" | sed -n 's/.*"origin": *"\([^"]*\)".*/\1/p')
  this=$2
  [ -n "$key" ] || { report "run folder: none for this job (the launcher named no run key)"; return; }
  folder=$(pointer_field folder)
  if [ -z "$folder" ] || [ "$(pointer_field key)" != "$key" ]; then
    report "run folder: none for this job ($REALISM_ROOT/$STAGE.last.json names no run of the key $key)"
    return
  fi
  named=$(pointer_field run)
  named=${named#RealismFlow/}
  if [ -z "$named" ] || { [ "$named" != "$this" ] && [ "$named" != "$origin" ]; }; then
    report "run folder: none for this job ($REALISM_ROOT/$STAGE.last.json names run ${named:-none} of the key $key, not this job's run ${this:-unnamed}${origin:+ or the run $origin it resumes})"
    return
  fi
  report "run folder: $folder"
  if [ "$(stat -c %Y "$folder/SUMMARY.md" 2>/dev/null || echo 0)" -ge "$job_began" ]; then
    { echo; echo "### SUMMARY.md"; echo; cat "$folder/SUMMARY.md"; echo; } >> "$REPORT.part"
  else
    report "SUMMARY.md: not written by this job (the run did not reach its end step)"
  fi
}
finish() {
  local rc=$1 ended_at
  trap '' TERM  # a TERM from here on would write a second report over this one
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ]; then
    report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the stage, so a later step may have run the newer code while this report names the older; its results are not used"
    [ "$rc" != 0 ] || rc=3
  fi
  report "exit $rc at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_REALISM_RC=$rc"
  exit "$rc"
}
job_began=$(date +%s)
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# realism $STAGE: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
# Slurm's TERM, at the time limit or a cancel, comes a while before its KILL: enough to say so and
# write the exit a shell gives TERM, so the next send reads a finished report.
trap 'report "TERMINATED: Slurm ended the stage (its time limit, or a cancel) before it finished"; finish 143' TERM

venv_for() {  # venv_for PINS: a virtual environment holding PINS beside train-gpu's packages, made once
  local key venv
  key=$(printf '%s' "$1" | sha256sum | cut -c1-12)
  venv=$LAB/go2432/.cache/realism/venv-$key
  if [ ! -f "$venv/READY" ]; then
    rm -rf "$venv"
    bash grid/box.sh pixi run --locked -e train-gpu python -m venv --system-site-packages "$venv" || return 1
    # shellcheck disable=SC2086
    bash grid/box.sh "$venv/bin/python" -m pip install --quiet $1 || return 1
    printf '%s\n' "$1" > "$venv/READY"
  fi
  echo "$venv"
}
found_under() {  # found_under <root> <find words...>: the first path find gives, or nothing
  local root=$1
  shift
  find "$root" "$@" -print -quit 2>/dev/null
}

# The FleXray bundle and the ImageNet weights both stages read; the stats stage takes the rest from
# the edit's record.
weights=$(dirname "$(found_under "$DATA/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json)")
[ -f "$weights/ensemble.json" ] || { report "FAILED: no ensemble.json under $DATA/hf_flexray_weights/raw (fetch hf_flexray_weights)"; finish 2; }
imagenet=$MODELS/resnet18-f37072fd.pth
[ -s "$imagenet" ] || { report "FAILED: no $imagenet, which the imagenet space reads (the gate's weights job makes it)"; finish 2; }
words=(--stage "$STAGE" --out "$REALISM_ROOT" --bundle "$weights" --imagenet "$imagenet")
if [ "$STAGE" = edit ]; then
  samples=$(found_under "$DATA/hf_flexray_data/raw" -path '*FluXray*' -name samples.csv)
  [ -n "$samples" ] || { report "FAILED: no FluXray samples.csv under $DATA/hf_flexray_data/raw (fetch hf_flexray_data)"; finish 2; }
  db=$(found_under "$DATA/hf_flexray_data/raw" -type d -path '*FluXray*' -name 1.0)
  [ -n "$db" ] || { report "FAILED: no FluXray ThunderDB under $DATA/hf_flexray_data/raw"; finish 2; }
  # The recipe's klein-9B and no other: the PREREG names it, and the flow refuses any other.
  klein=$(found_under "$DATA/hf_flux2_klein_9b/raw" -maxdepth 3 -name model_index.json)
  [ -n "$klein" ] || { report "FAILED: no FLUX.2 klein-9B weights under $DATA/hf_flux2_klein_9b/raw (fetch hf_flux2_klein_9b)"; finish 2; }
  words+=(--samples "$samples" --db "$db" --ct "$DATA/aws_enhance_pet_ct/raw" --truth "$DATA/aws_enhance_pet_labels/raw"
          --klein "$(dirname "$klein")")
  report "inputs: FluXray $samples; klein-9B $(dirname "$klein"); FleXray bundle $weights; ImageNet $imagenet"
fi

venv=$(venv_for "$REALISM_PIN") || { report "FAILED: the environment for the realism pins could not be made"; finish 1; }
report "environment: $REALISM_PIN"
report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
out=$(mktemp "$REPO/grid/logs/realism-flow-${SLURM_JOB_ID:-$$}.XXXXXX")
# The Metaflow datastore is the launcher's default on the grid, where the run's progress page is.
bash grid/box.sh "$venv/bin/python" flows/launch.py realism --max-workers 1 -- "${words[@]}" 2>&1 | tee "$out"
rc=${PIPESTATUS[0]}
# The launcher has exited, so a TERM from here on ends only the report's last lines: the exit kept
# is the launcher's, which says how the run ended, and not the 143 a TERM during the run means.
trap 'report "TERMINATED: Slurm ended the job after the launcher exited $rc, before the report was whole"; finish "$rc"' TERM
decision=$(grep -m 1 '"decision":' "$out")
report "launcher: ${decision:-it printed no decision line}"
# Metaflow's runtime heads each line a task prints with its time and [run/step/task (pid N)], even
# under --quiet, so the end step's lines are found by their own head wherever the line begins; the
# last 40 are kept, since the report and the verdict come last and SUMMARY.md holds the rest whole.
sed -n 's/^\([^[]*\[[^]]*\] \)\{0,1\}RealismFlow: //p' "$out" | tail -n 40 | while IFS= read -r line; do report "$line"; done
run=$(grep '"successful":' "$out" | tail -n 1)
report "Metaflow: ${run:-the launcher named no run}"
# The run's page, from the datastore root the decision line names and the run the last line names.
root=$(printf '%s\n' "$decision" | sed -n 's/.*"root": *"\([^"]*\)".*/\1/p')
id=$(printf '%s\n' "$run" | sed -n 's/.*"run": *"RealismFlow\/\([0-9A-Za-z_-]*\)".*/\1/p')
[ -n "$root" ] || root="(the datastore the launcher names)"
report "progress page: $root/progress/RealismFlow/${id:-<run>}/index.html (Open OnDemand's Files app, then View or Download)"
summary "$decision" "$id"
report "launcher exited $rc"
finish "$rc"
