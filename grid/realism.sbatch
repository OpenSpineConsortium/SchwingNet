#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# One stage of the Flux realism programme (docs/research/flux-realism/README.md): the FLUX.2 klein
# edit that made FluXray reproduced on our own DRRs of the same CTs at the same poses, measured
# against FluXray, and an edit adapter finetuned on the pairs. grid/gate.sh's word `realism <stage>`
# queues it with STAGE, the stage, in the environment, as one GPU job; no stage runs without the
# owner's word and count for it. The stages, in order:
#
#   edit    the poses read from FluXray's samples.csv, a subject split, raw DRRs of REALISM_SUBJECTS
#           ENHANCE.PET CTs at REALISM_PER_SUBJECT recorded poses each with exact masks, the klein
#           edit of each (klein-9b where its weights are landed, else klein-4b) in REALISM_ARMS seed
#           arms, FluXray's own paired filter with the flux000 member, FluXray's images of the same
#           subjects out of its ThunderDB, and the endplate-angle measurement at 1024 and at 256
#   stats   the metric suite of the zero-shot edit and of the raw DRRs against FluXray
#   lora    the control/target pairs of the training split, the trainer's configuration from the
#           pre-registered plan, one LoRA on klein-base-4b (ostris/ai-toolkit at TOOLKIT_COMMIT),
#           and the edit of the evaluation split through it
#   eval    the metric suite of the LoRA edit and of the zero-shot edit against FluXray, evaluation
#           split only
#
# Everything lands under $REALISM_ROOT/<stage>/ on the lab volume; the report, logs/REALISM-<stage>.md,
# carries counts, the verdict words and digests, and the next `realism <stage>` prints it. The public
# packages go into a throwaway environment beside train-gpu's (venv_for, as grid/bench.sbatch), never
# into pixi.lock. Not requeued (--no-requeue from the gate). The checkout holds still while the stage
# lasts (grid/logs/HOLD), and a stage whose checkout moved anyway is failed, since its report names
# the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
MODELS=${MODELS:-$LAB/go2432/models}
REALISM_ROOT=${REALISM_ROOT:-$LAB/go2432/realism}
SUBJECTS=${REALISM_SUBJECTS:-100}
PER_SUBJECT=${REALISM_PER_SUBJECT:-4}
ARMS=${REALISM_ARMS:-2}
TARGET=${REALISM_TARGET:-fluxray}
# The undistilled base takes more steps and a guidance above one; these two are the numbers to tune,
# and the report names them.
BASE_STEPS=${REALISM_BASE_STEPS:-28}
BASE_GUIDANCE=${REALISM_BASE_GUIDANCE:-4.0}
# PyPI's releases of 2026-10-26; the trainer is a clone at one commit, with its own requirements.
REALISM_PIN="diffusers==0.42.0 transformers==5.20.2 accelerate==1.15.0 peft==0.21.2 safetensors==0.8.0 huggingface_hub==2.3.0 flexray==1.0.2 lmdb==3.0.0 nibabel==5.3.2"
TOOLKIT_REPO=https://github.com/ostris/ai-toolkit.git
TOOLKIT_COMMIT=73ebae13a468942ded8b47991b5d56eeeea25c36
STAGE=${STAGE:-}
case "$STAGE" in edit|stats|lora|eval) ;; *) echo "realism: STAGE is edit, stats, lora or eval"; echo "SN_REALISM_RC=64"; exit 64 ;; esac
REPORT=$REPO/grid/logs/REALISM-$STAGE.md
OUT=$REALISM_ROOT/$STAGE
EDIT=$REALISM_ROOT/edit
LORA=$REALISM_ROOT/lora
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  local rc=$1 ended_at
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
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# realism $STAGE: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM

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
weights_dir() {  # the FleXray bundle the fetch landed: the folder that holds ensemble.json
  dirname "$(find "$DATA/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json -print -quit 2>/dev/null)"
}
klein_dir() {  # klein_dir <4b|9b|base-4b|base-9b>: the diffusers folder of that FLUX.2 klein, or nothing
  local found
  found=$(find "$DATA/hf_flux2_klein_${1//-/_}/raw" -maxdepth 3 -name model_index.json -print -quit 2>/dev/null)
  [ -n "$found" ] && dirname "$found"
}
fluxray_db() {  # FluXray's ThunderDB folder as the fetch landed it
  find "$DATA/hf_flexray_data/raw" -type d -path '*FluXray*' -name 1.0 -print -quit 2>/dev/null
}
step() {  # step <name> <command...>: one tool call, its output kept, the stage failed on a nonzero exit
  local name=$1
  shift
  "$@" > "$OUT/$name.log" 2>&1 || { report "FAILED: $name ($(tail -n 1 "$OUT/$name.log" | cut -c1-200))"; finish 1; }
}
count_lines() { [ -f "$1" ] && wc -l < "$1" || echo 0; }
report_ok() {  # the stage before this one finished with exit 0
  [ -f "$1" ] && tail -n 1 "$1" | grep -q '^- exit 0 '
}
sha_of() { sha256sum < "$1" | cut -c1-16; }

venv=$(venv_for "$REALISM_PIN") || { report "FAILED: the environment for the realism pins could not be made"; finish 1; }
PY=("bash" "grid/box.sh" "$venv/bin/python")
report "environment: $REALISM_PIN"

case "$STAGE" in
  edit)
    weights=$(weights_dir)
    [ -f "$weights/ensemble.json" ] || { report "FAILED: no ensemble.json under $DATA/hf_flexray_weights/raw (fetch hf_flexray_weights)"; finish 2; }
    samples=$(find "$DATA/hf_flexray_data/raw" -path '*FluXray*' -name samples.csv -print -quit 2>/dev/null)
    [ -n "$samples" ] || { report "FAILED: no FluXray samples.csv under $DATA/hf_flexray_data/raw (fetch hf_flexray_data)"; finish 2; }
    db=$(fluxray_db)
    [ -n "$db" ] || { report "FAILED: no FluXray ThunderDB under $DATA/hf_flexray_data/raw"; finish 2; }
    find "$DATA/aws_enhance_pet_ct/raw" -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . || { report "FAILED: no ENHANCE.PET CT under $DATA/aws_enhance_pet_ct/raw (fetch aws_enhance_pet_ct)"; finish 2; }
    find "$DATA/aws_enhance_pet_labels/raw" -path '*Vertebrae*' -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . || { report "FAILED: no ENHANCE.PET truth under $DATA/aws_enhance_pet_labels/raw (fetch aws_enhance_pet_labels)"; finish 2; }
    if klein=$(klein_dir 9b); then model=klein-9b; elif klein=$(klein_dir 4b); then model=klein-4b
    else report "FAILED: no FLUX.2 klein weights (fetch hf_flux2_klein_4b, or hf_flux2_klein_9b once the owner has accepted its licence on the hub)"; finish 2; fi
    report "edit model: $model at $klein; FleXray bundle: $weights; FluXray: $samples"
    report "plan: $SUBJECTS subjects, $PER_SUBJECT poses each, $ARMS seed arm(s); seeds from the subject, the pose and the arm (schwingnet.realism.seed_for)"
    step poses "${PY[@]}" tools/realism.py poses --samples "$samples" --out "$OUT/poses.json"
    step split "${PY[@]}" tools/realism.py split --poses "$OUT/poses.json" --out "$OUT/split" --limit "$SUBJECTS"
    report "poses: $(tail -n 1 "$OUT/poses.log" | cut -c1-200); split: $(tail -n 1 "$OUT/split.log" | cut -c1-200)"
    step render "${PY[@]}" tools/realism.py render --ct "$DATA/aws_enhance_pet_ct/raw" --truth "$DATA/aws_enhance_pet_labels/raw" \
      --poses "$OUT/poses.json" --out "$OUT/render" --weights "$weights" --only "$OUT/split/all.txt" --per-subject "$PER_SUBJECT" --device cuda
    report "render: $(tail -n 1 "$OUT/render.log" | cut -c1-200); manifest sha256 $(sha_of "$OUT/render/manifest.jsonl")"
    step edit "${PY[@]}" tools/realism.py edit --raw "$OUT/render" --weights "$klein" --model "$model" --out "$OUT/zero-shot" --arms "$ARMS" --device cuda
    report "edit: $(tail -n 1 "$OUT/edit.log" | cut -c1-200)"
    step filter "${PY[@]}" tools/realism.py filter --raw "$OUT/render" --edited "$OUT/zero-shot" --weights "$weights" --out "$OUT/filter" --device cuda
    report "filter: $(tail -n 1 "$OUT/filter.log" | cut -c1-200)"
    step export "${PY[@]}" tools/realism.py fluxray-export --db "$db" --out "$OUT/fluxray" --subjects "$OUT/split/all.txt"
    report "fluxray export: $(tail -n 1 "$OUT/export.log" | cut -c1-200)"
    step measure "${PY[@]}" tools/realism.py measure --masks "$OUT/render" --out "$OUT/measure"
    report "measure: $(tail -n 1 "$OUT/measure.log" | cut -c1-200)"
    { echo; cat "$OUT/measure/measure.md" 2>/dev/null; } >> "$REPORT.part"
    ;;
  stats)
    report_ok "$REPO/grid/logs/REALISM-edit.md" || { report "FAILED: the edit stage has not finished with exit 0 (send realism edit first)"; finish 2; }
    weights=$(weights_dir)
    imagenet=()
    [ ! -f "$MODELS/resnet18-f37072fd.pth" ] || imagenet=(--imagenet-weights "$MODELS/resnet18-f37072fd.pth")
    [ ${#imagenet[@]} -gt 0 ] || report "NOTE: no $MODELS/resnet18-f37072fd.pth; the imagenet space is left out"
    for pair in "zero-shot:$EDIT/filter/kept" "raw:$EDIT/render/raw"; do
      name=${pair%%:*}; a=${pair#*:}
      step "stats-$name" "${PY[@]}" tools/realism.py stats --a "$a" --b "$EDIT/fluxray/img" --out "$OUT/$name" --weights "$weights" ${imagenet[@]+"${imagenet[@]}"} --device cuda
      report "$name against FluXray: $(head -n 1 "$OUT/$name/stats.md" | cut -c1-200)"
      { echo; echo "### $name against FluXray"; echo; cat "$OUT/$name/stats.md"; } >> "$REPORT.part"
    done
    ;;
  lora)
    report_ok "$REPO/grid/logs/REALISM-edit.md" || { report "FAILED: the edit stage has not finished with exit 0 (send realism edit first)"; finish 2; }
    base=$(klein_dir base-4b) || { report "FAILED: no FLUX.2 klein-base-4b weights (fetch hf_flux2_klein_base_4b)"; finish 2; }
    case "$TARGET" in fluxray) target=$EDIT/fluxray ;; teacher) target=$EDIT/zero-shot ;; *) report "FAILED: REALISM_TARGET is fluxray or teacher"; finish 64 ;; esac
    report "target: $TARGET ($target); base: klein-base-4b at $base; trainer: ostris/ai-toolkit at ${TOOLKIT_COMMIT:0:7}"
    step pairs "${PY[@]}" tools/realism.py pairs --control "$EDIT/render" --target "$target" --out "$OUT/pairs" --only "$EDIT/split/train.txt"
    report "pairs: $(tail -n 1 "$OUT/pairs.log" | cut -c1-200)"
    step config "${PY[@]}" tools/realism.py lora-config --pairs "$OUT/pairs" --out "$OUT/config.json" --training-folder "$OUT/train" --target "$TARGET"
    report "config: $(tail -n 1 "$OUT/config.log" | cut -c1-200); sha256 $(sha_of "$OUT/config.json")"
    toolkit=$LAB/go2432/.cache/realism/ai-toolkit
    if [ ! -f "$toolkit/READY" ] || [ "$(cat "$toolkit/READY")" != "$TOOLKIT_COMMIT" ]; then
      rm -rf "$toolkit"
      git clone --quiet "$TOOLKIT_REPO" "$toolkit" > "$OUT/clone.log" 2>&1 && git -C "$toolkit" checkout --quiet "$TOOLKIT_COMMIT" >> "$OUT/clone.log" 2>&1 \
        || { report "FAILED: the trainer's clone at $TOOLKIT_COMMIT ($(tail -n 1 "$OUT/clone.log" | cut -c1-200))"; finish 1; }
      printf '%s\n' "$TOOLKIT_COMMIT" > "$toolkit/READY"
    fi
    trainer=$(venv_for "-r $toolkit/requirements.txt") || { report "FAILED: the trainer's environment could not be made"; finish 1; }
    step train bash grid/box.sh "$trainer/bin/python" "$toolkit/run.py" "$OUT/config.json"
    lora=$(find "$OUT/train" -name '*.safetensors' -newer "$OUT/config.json" -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2-)
    [ -n "$lora" ] || { report "FAILED: the trainer wrote no .safetensors under $OUT/train"; finish 1; }
    report "lora: $(basename "$lora"), sha256 $(sha_of "$lora"), $(stat -c %s "$lora") bytes"
    step edit "${PY[@]}" tools/realism.py edit --raw "$EDIT/render" --weights "$base" --model klein-base-4b --lora "$lora" --steps "$BASE_STEPS" --guidance "$BASE_GUIDANCE" \
      --out "$OUT/edited" --arms "$ARMS" --only "$EDIT/split/eval.txt" --device cuda
    report "edit through the LoRA ($BASE_STEPS steps, guidance $BASE_GUIDANCE, to tune): $(tail -n 1 "$OUT/edit.log" | cut -c1-200)"
    ;;
  eval)
    report_ok "$REPO/grid/logs/REALISM-lora.md" || { report "FAILED: the lora stage has not finished with exit 0 (send realism lora first)"; finish 2; }
    weights=$(weights_dir)
    imagenet=()
    [ ! -f "$MODELS/resnet18-f37072fd.pth" ] || imagenet=(--imagenet-weights "$MODELS/resnet18-f37072fd.pth")
    for pair in "lora:$LORA/edited/edited" "zero-shot:$EDIT/filter/kept"; do
      name=${pair%%:*}; a=${pair#*:}
      step "stats-$name" "${PY[@]}" tools/realism.py stats --a "$a" --b "$EDIT/fluxray/img" --out "$OUT/$name" --weights "$weights" ${imagenet[@]+"${imagenet[@]}"} \
        --only "$EDIT/split/eval.txt" --device cuda
      report "$name against FluXray, evaluation split: $(head -n 1 "$OUT/$name/stats.md" | cut -c1-200)"
      { echo; echo "### $name against FluXray, evaluation split"; echo; cat "$OUT/$name/stats.md"; } >> "$REPORT.part"
    done
    ;;
esac
finish 0
