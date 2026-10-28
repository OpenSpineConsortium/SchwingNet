#!/bin/bash
# The gold tier 3 CT dataset's one CPU job on the grid (HANDOFF.md beside this file, step 7), on the
# owner's count. It reads ENHANCE.PET's published masks twice, sets both readings beside
# each other and beside the count's own reading, takes them into the SchwingNet clone's facts files,
# writes the dataset's pages and builds its store on the lab volume. It writes only under $W and
# $DATA_ROOT/_gold3_ct; the session commits what it leaves in the clone.
#
# The session copies this file to $W and queues it with hpcworker's job submit, class batch, handing
# it W, VERT, RIBS and DATA_ROOT in its environment. A header keeps only the time, the CPUs and the
# memory (docs/memory/grid-jobs-go-through-hpcworker-job-submit.md). The first reading runs at most
# three processes (MAX_WORKERS of bordercall's holdings/count_enhance_pet.py, which
# holdings/enhance_facts.py takes), about 30 s a study with its three processes in the thread's
# 4-CPU container, so 13 hours or less for 1,600; the four readings run side by side, that one sets
# the wall time, and 24 hours leaves room for a slower node. A time-out is not requeued.
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
set -euo pipefail
: "${W:?W names the work folder}" "${VERT:?VERT names the vertebra masks}" "${RIBS:?RIBS names the rib masks}"
: "${DATA_ROOT:?DATA_ROOT names the data root}"
SN="$W/SchwingNet" BC="$W/bordercall"

# The nodes run CentOS 7 (glibc 2.17), and numpy 2.5.4 and scipy 1.18.1 need Python 3.12 and glibc
# 2.27 or later, so the job runs again inside SchwingNet's sandbox (grid/box.sh: Debian bookworm, glibc
# 2.36, the home and the lab volume bound). Slurm runs a spooled copy, which the sandbox cannot see, so
# the copy in $W is what re-enters. git runs here first, outside, where it is known to be.
if [ -z "${APPTAINER_CONTAINER:-}${SINGULARITY_CONTAINER:-}" ] && [ "${SCHWINGNET_NATIVE:-}" != 1 ]; then
  GOLD3_BORDERCALL_COMMIT=$(git -C "$BC" rev-parse HEAD)
  GOLD3_SCHWINGNET_COMMIT=$(git -C "$SN" rev-parse HEAD)
  export GOLD3_BORDERCALL_COMMIT GOLD3_SCHWINGNET_COMMIT
  exec bash "$SN/grid/box.sh" bash "$W/gold3-facts.sbatch"
fi
: "${GOLD3_BORDERCALL_COMMIT:=$(git -C "$BC" rev-parse HEAD)}" "${GOLD3_SCHWINGNET_COMMIT:=$(git -C "$SN" rev-parse HEAD)}"

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# glibc hands arrays of 1 MB or more back to the system when freed, so no worker keeps the heap of its
# largest study; with it the thread's container read at about 1.5 GB a process at most.
export MALLOC_MMAP_THRESHOLD_=1048576 MALLOC_TRIM_THRESHOLD_=1048576
OUT="$W/out" ENV="$W/env" STORE="$DATA_ROOT/_gold3_ct"
DATA="$SN/data/gold3-ct/enhance-pet"
mkdir -p "$OUT/a" "$OUT/b" "$OUT/count" "$ENV"

say() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }

once() {  # once NAME COMMAND...: run COMMAND unless an earlier run of this job finished it, its log in $OUT/NAME.log
  local name=$1
  shift
  if [ -f "$OUT/$name.done" ]; then
    say "$name: finished before this run, skipped"
    return 0
  fi
  say "$name: starting"
  if "$@" > "$OUT/$name.log" 2>&1; then
    touch "$OUT/$name.done"
    say "$name: finished"
  else
    say "$name: FAILED; the last lines of $OUT/$name.log:"
    tail -n 15 "$OUT/$name.log"
    return 1
  fi
}

# The Python the thread's container used: 3.13 with exactly these four, from PyPI as there. A stand-in
# (GOLD3_PY) is for a dry run off the grid only.
write_environment() {
  cat > "$ENV/pixi.toml" <<'TOML'
[workspace]
name = "gold3-facts"
channels = ["conda-forge"]
platforms = [{ name = "linux-64-glibc228", platform = "linux-64", glibc = "2.28" }]
conda-pypi-map = false

[dependencies]
python = "3.13.*"

[pypi-dependencies]
numpy = "==2.5.4"
scipy = "==1.18.1"
nibabel = "==5.4.2"
pillow = "==13.0.0"
TOML
  pixi install --manifest-path "$ENV/pixi.toml"
}

check_versions() {
  "$PY" - <<'PYEOF'
import sys
import nibabel, numpy, PIL, scipy
want = {"numpy": "2.5.4", "scipy": "1.18.1", "nibabel": "5.4.2", "pillow": "13.0.0"}
got = {"numpy": numpy.__version__, "scipy": scipy.__version__, "nibabel": nibabel.__version__, "pillow": PIL.__version__}
print("python", sys.version.split()[0], got)
sys.exit(0 if sys.version_info[:2] == (3, 13) and got == want else "not the container's versions")
PYEOF
}

# once runs each step as an if's condition, where bash ignores set -e, so every step chains with &&.
run_tests() {
  (cd "$BC" && "$PY" -m unittest discover -s holdings/tests -t .) && (cd "$SN" && "$PY" -m unittest tests.test_gold3_ct)
}

write_listings() {  # the bucket's listing as the first reading takes it: a JSON list of [key, bytes] a folder
  "$PY" - "$DATA/bucket.json" "$OUT" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as handle:
    bucket = json.load(handle)
for name in ("vertebrae", "ribs"):
    column = bucket["columns"].index(name)
    rows = [[bucket["prefixes"][name] + sid + ".nii.gz", sizes[column]] for sid, sizes in sorted(bucket["studies"].items())]
    with open("%s/%s_keys.json" % (sys.argv[2], name), "w") as out:
        json.dump(rows, out)
    print(name, len(rows))
PYEOF
}

first_reading() {
  cd "$BC" && "$PY" -m holdings.enhance_facts facts "$VERT" "$RIBS" "$DATA/ct-details.json" "$OUT/a/facts.jsonl" \
    --listing "$OUT/vertebrae_keys.json" "$OUT/ribs_keys.json" --repair-record "" --workers 3
}

second_reading() {
  cd "$BC" && "$PY" -m holdings.enhance_facts_check --masks "$VERT" --ribs "$RIBS" --out "$OUT/b/facts_b.jsonl" --workers 4
}

count_extents() {
  cd "$BC" && "$PY" -m holdings.count_enhance_pet extents "$VERT" "$OUT/count/extents.json" --workers 3
}

count_ribs() {
  cd "$BC" && "$PY" -m holdings.count_enhance_pet ribs "$VERT" "$RIBS" all "$OUT/count/ribs.json" --workers 3
}

read_side_by_side() {  # the four readings at once; each keeps its own log, and a requeue skips the finished
  local pids=() pid failed=0
  once first_reading first_reading & pids+=($!)
  once second_reading second_reading & pids+=($!)
  once count_extents count_extents & pids+=($!)
  once count_ribs count_ribs & pids+=($!)
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  return "$failed"
}

compare_readings() {  # exits 1 unless the two readings agree but for contact counts (holdings/enhance_facts_check.py)
  cd "$BC" && "$PY" -m holdings.enhance_facts_check compare "$OUT/a/facts.jsonl" "$OUT/b/facts_b.jsonl" "$OUT/agreement.json"
}

cross_check() {  # exits 1 unless the first reading gives what the count gave (holdings/enhance_facts_cross.py)
  cd "$BC" && "$PY" -m holdings.enhance_facts_cross "$OUT/a/facts.jsonl" "$OUT/count/extents.json" \
    "$OUT/count/ribs.json" "$OUT/cross.json" --touch "$DATA/touch.json"
}

take_facts() {
  cd "$SN" && "$PY" tools/gold3_ct.py take-facts "$OUT/a/facts.jsonl" "$OUT/b/facts_b.jsonl" \
    --read-on "the grid, Slurm job ${SLURM_JOB_ID:-unknown}, $(date -u +%F)" \
    --bordercall-commit "$GOLD3_BORDERCALL_COMMIT"
}

dataset_pages() {
  cd "$SN" && "$PY" tools/gold3_ct.py stats && "$PY" tools/gold3_ct.py qa && "$PY" tools/gold3_ct.py page \
    && "$PY" tools/gold3_ct.py check
}

dataset_store() {
  cd "$SN" && "$PY" tools/gold3_ct.py build --root "$STORE" --code-commit "$GOLD3_SCHWINGNET_COMMIT" \
    && mkdir -p "$STORE/exports" \
    && "$PY" tools/gold3_ct.py export --root "$STORE" --format csv --out "$STORE/exports/all.csv" \
    && "$PY" tools/gold3_ct.py export --root "$STORE" --format csv --tier gold3 --training-only \
         --out "$STORE/exports/gold3-training.csv" \
    && "$PY" tools/gold3_ct.py query "SELECT * FROM gold3_persons_by_member" --root "$STORE"
}

say "gold3 facts: job ${SLURM_JOB_ID:-none} on $(hostname), bordercall $GOLD3_BORDERCALL_COMMIT, SchwingNet $GOLD3_SCHWINGNET_COMMIT"
if [ -n "${GOLD3_PY:-}" ]; then
  PY=$GOLD3_PY
else
  once environment write_environment
  PY="$ENV/.pixi/envs/default/bin/python"
fi
check_versions
once tests run_tests
once listings write_listings
read_side_by_side
# Each is a stop: the readings must agree before anything reaches the clone (HANDOFF.md, section 7).
once compare compare_readings
once cross cross_check
once take_facts take_facts
once pages dataset_pages
once store dataset_store
cat "$OUT/take_facts.log" "$OUT/store.log"
say "GOLD3_FACTS_DONE"
