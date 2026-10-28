# Handoff: the gold tier 3 CT dataset, run on the grid through Beethoven (2026-10-28)

Thread "Finish scan import and tier counts". The owner's ask, 2026-10-27 22:49 UTC, verbatim: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". Then, 2026-10-28 00:04 UTC: "maybe these steps should jsut work on the grid? can you write a handoff for this to run over the beethoven extension on the grid?"

This page is for a Claude Code session the owner opens on the grid with the Beethoven extension. It says what to run, in what order, and what must hold before anything is committed. The design is docs/research/gold3-ct/ (README.md where the programme stands, SPEC.md the build plan, BRIEF.md what exists with file and line references); this page carries none of it. Confidential like the rest of SchwingNet and bordercall: nothing here or made from it goes to a public place, and no path under the data root, no DICOM UID and no PatientID leaves the grid.

## Why the grid

Reading the masks takes about 50 seconds and 1.6 GB per study for the first reading (more for the 0.7 mm whole-body studies, the largest 695 million voxels), so 1,600 studies is most of a day on the thread's 4-CPU container, and running two readings side by side there ran it out of memory twice on 2026-10-27. On a 16-CPU batch job it is about two hours. The grid also holds what the container never can: the TotalSegmentator and VerSe members' masks, the autoPET CTs, and the lab volume where the store belongs ($DATA_ROOT/_gold3_ct).

## 0. The owner's count, before anything runs

Print this block in the session and wait for the owner's yes. Nothing below step 2 runs without it, and nothing beyond it runs at all.

1. One fetch, through the gate word so the size rule reads the exact size first and refuses it whole if it would pass the CephFS quota: `fetch aws_enhance_pet_labels`, 11,256,936,591 bytes (the public bucket's whole ground-truth prefix, seven label folders, listed 2026-10-27). This work reads two of them, Vertebrae (381,439,888 bytes) and Ribs (312,882,241 bytes); the gate word has no narrower form, and the other five serve the paused Flux realism programme when it is restarted.
2. One CPU job, hpcworker's batch class (16 CPUs, 64 GB, 12 hours; requeued on preemption, and every step resumes where it stopped): both readings of the masks, their comparison, the count's own cross-check reading, and the store build. It writes only in the work folder and under $DATA_ROOT/_gold3_ct.

Not in this count, each its own yes later: the Leipzig and Careggi CTs (45,207,300,328 bytes, a new url-route line) for CT views and the lumbosacral reads no mask can settle; any SPINEPS or bordercall run (the bordercall pilot of 2 CPU jobs is approved and unsent, and belongs to its own word). Never: CT-RATE without the owner's terabytes, Radiopaedia by script, usage credits, a segmenter run, TotalSegmentator as a segmenter.

## 1. Where things are

| what | where |
| --- | --- |
| The plan | SchwingNet, branch claude/project-thread-cne00q: docs/research/gold3-ct/README.md, SPEC.md, BRIEF.md |
| Dataset records | SchwingNet, same branch: data/gold3-ct/members.json, verse.json, totalsegmentator.json; data/gold3-ct/enhance-pet/record.json, bucket.json (the listing with exact bytes), SHA256SUMS (the 3,194 masks this thread read), ct-details.json (CT-details.xlsx's rows, so no second fetch is needed) |
| The store tool | SchwingNet, same branch: tools/gold3_ct.py (build, query, stats, qa, export, page, check; standard library only) and tests/test_gold3_ct.py; STATS.md, QA.md and page-data.json under docs/research/gold3-ct/, made with no facts yet |
| The mask readers | bordercall, branch claude/project-thread-cne00q: holdings/enhance_facts.py (the first reading, reusing the count's own rules), holdings/enhance_facts_check.py (the second, written blind from the plan, with `compare`), holdings/enhance_views.py (front and side pictures for a reader), tests under holdings/tests/ |
| The count | bordercall main: holdings/count_enhance_pet.py, whose extents and ribs steps are the cross-check |
| The draft pull requests | bordercall #17 and SchwingNet's, both from claude/project-thread-cne00q; their bodies are the record |

Container paths in SPEC.md and BRIEF.md map to the grid as follows: /tmp/claude-0/enh/masks is $VERT and /tmp/claude-0/enh/ribs is $RIBS (step 4); /mnt/project-files/enhance-pet-repair, which holds the three repaired vertebra masks, is not on the grid (bordercall keeps no mask in git), so the three repaired rows, 1134r, 1283r and 1347r, come from the thread's container (step 8); CT-details.xlsx is SchwingNet's data/gold3-ct/enhance-pet/ct-details.json; the seed outputs of the count are made again in step 6.

## 2. Open the session

1. Start a Beethoven worker on the grid and open its session (Beethoven's New session, or the Claude project's own Work locally from the + menu, docs/memory/beethoven-worker-and-claude-projects.md).
2. Tell it: "Read docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md on SchwingNet's branch claude/project-thread-cne00q and follow it."
3. The session runs as a worker under the owner's login (docs/agents/WORKERS.md) and works only on the branch above in each repository.

## 3. The work folder

Never work in ~/SchwingNet: it is the grid gate's own checkout, brought to main by every gate word and held by running jobs (grid/logs/HOLD).

```
W=$HOME/work/gold3; mkdir -p "$W" && cd "$W"
git clone --branch claude/project-thread-cne00q https://github.com/OpenSpineConsortium/SchwingNet.git
git clone --branch claude/project-thread-cne00q https://github.com/OpenSpineConsortium/bordercall.git
```

Both repositories are private: if git cannot reach them with the owner's own credentials on the grid, stop and tell the owner exactly that; never ask for or handle a token.

Then step 0: print the count and wait for the owner's yes.

## 4. The fetch, after the yes

1. Read the room first: `bash ~/SchwingNet/grid/gate.sh status | sed -n '1,30p'`.
2. Send the word once: `bash ~/SchwingNet/grid/gate.sh fetch aws_enhance_pet_labels`. It prints the exact size, the admission and the job. Never send it a second time while its job is queued or running.
3. When `status` shows the job ended, find the two folders and count them; both counts must be 1,597:

```
DATA_ROOT=/rs/rs_grp_oschome/go2432/data
VERT=$(dirname "$(find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*/Vertebrae/0001.nii.gz' | head -n 1)")
RIBS=$(dirname "$(find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*/Ribs/0001.nii.gz' | head -n 1)")
ls "$VERT" | grep -c 'nii.gz$'; ls "$RIBS" | grep -c 'nii.gz$'
```

4. The grid's copy must be byte for byte the copy the thread read. In a batch job or the worker's own allocation (never on the login node, where python is killed by name; sha256sum is fine anywhere):

```
cd "$(dirname "$VERT")" && sha256sum --quiet -c "$W/SchwingNet/data/gold3-ct/enhance-pet/SHA256SUMS"
```

Any mismatch stops the work: tell the owner which files, and change nothing.

## 5. The environment

The same versions the thread's container used, so every float rounds the same way and the facts are the same bytes:

```
python3 -m venv "$W/venv" && "$W/venv/bin/pip" install numpy==2.5.4 scipy==1.18.1 nibabel==5.4.2 pillow==13.0.0
cd "$W/bordercall" && "$W/venv/bin/python" -m unittest discover -s holdings/tests -t .
```

The tests must pass before the job is queued.

## 6. The job

Write the job script in the work folder, never in either repository (a .sbatch header keeps only time, CPUs and memory; hpcworker's site profile places the job, docs/memory/grid-jobs-go-through-hpcworker-job-submit.md):

```
cat > "$W/gold3-facts.sbatch" <<'EOF'
#!/bin/bash
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY="$W/venv/bin/python"; OUT="$W/out"; mkdir -p "$OUT/a" "$OUT/b" "$OUT/count"
DATA="$W/SchwingNet/data/gold3-ct/enhance-pet"
# The bucket listing as the first reading takes it, a JSON list of [key, bytes] per folder.
"$PY" - "$DATA/bucket.json" "$OUT" <<'PYEOF'
import json, sys
bucket = json.load(open(sys.argv[1]))
for name in ("vertebrae", "ribs"):
    column = bucket["columns"].index(name)
    rows = [[bucket["prefixes"][name] + sid + ".nii.gz", sizes[column]] for sid, sizes in sorted(bucket["studies"].items())]
    json.dump(rows, open("%s/%s_keys.json" % (sys.argv[2], name), "w"))
PYEOF
cd "$W/bordercall"
"$PY" -m holdings.enhance_facts facts "$VERT" "$RIBS" "$DATA/ct-details.json" "$OUT/a/facts.jsonl" \
    --listing "$OUT/vertebrae_keys.json" "$OUT/ribs_keys.json" --repair-record "" --workers 10
"$PY" -m holdings.enhance_facts_check --masks "$VERT" --ribs "$RIBS" --out "$OUT/b/facts_b.jsonl" --workers 6
"$PY" -m holdings.enhance_facts_check compare "$OUT/a/facts.jsonl" "$OUT/b/facts_b.jsonl" "$OUT/agreement.json"
"$PY" -m holdings.count_enhance_pet extents "$VERT" "$OUT/count/extents.json" --workers 3
"$PY" -m holdings.count_enhance_pet ribs "$VERT" "$RIBS" all "$OUT/count/ribs.json" --workers 3
echo GOLD3_FACTS_DONE
EOF
hpcworker job submit --project schwingnet --name gold3_facts --class batch --dir "$W" --check -- gold3-facts.sbatch
W="$W" VERT="$VERT" RIBS="$RIBS" hpcworker job submit --project schwingnet --name gold3_facts --class batch --dir "$W" -- gold3-facts.sbatch
```

Check the exact options each reader takes with `--help` before writing the script; the readers' own docstrings are the authority where this page and they differ. Read the job's output with `hpcworker job log`; a requeued job carries on, since each reader keeps its partial rows.

## 7. What must hold before anything is committed

Each is a stop: if one fails, find why before anything else, write it down, and tell the owner.

1. The masks' hashes equal SHA256SUMS (step 4).
2. The first reading's voxels per label equal the count's extents.json for all 1,597; its rib voxels equal the count's ribs.json; and on each side the lowest rib's contacts, lead and tie equal the count's for all 1,597 (the count reads only the lowest rib, the first reading every rib).
3. The two readings agree (agreement.json): every study's label voxels, rib voxels and sternum voxels equal, every distance within 0.1 mm, and every rib's lead and tie equal. Contact counts may differ by a few voxels where two spine labels lie at exactly the same distance from a rib voxel, since the count gives such a voxel to whichever scipy names and the second reading to the head-most label; any study where that changes a lead is a fail of the dataset's check Q14 and is listed, never smoothed over.
4. The thread checked three studies in its container on 2026-10-28 with the first reading of that hour (0001, 0529, 0603): voxels, head-foot extents, rib voxels, the lowest ribs' contacts and the L4-to-sacrum distance all equalled the count. The grid's rows for those three must say the same: 0001's lowest ribs meet label 19 (108 contacts left, 121 right) and its 23-28, 24-28 and 23-24 distances are 15.3, 0.9 and 0.9 mm; 0603's label 13 has two pieces and its ribs 6 to 11 lead one label below their own (the split T6 of the labelling errors).
5. The 1,597 facts reproduce the note's numbers: docs/research/enhance-pet-gold-tier-3.md and the README's counts (1,557 whole; 3 repaired at gold 4; 37 with no C2; the rib table of the 107 unusual studies and 100 controls; L4 touching the sacrum in 3-D in all 39 four-lumbar spines).

## 8. The dataset

1. Copy $W/out/a/facts.jsonl to SchwingNet's data/gold3-ct/enhance-pet/facts.jsonl, keeping the three repaired rows (1134r, 1283r, 1347r) the thread's container wrote there if the branch holds them, or leaving them to the thread if it does not, with its FACTS.json beside it (the tool, bordercall's commit, the masks' SHA256SUMS hash, ct-details.json's sha256, the date, the row count), as SPEC.md section 5 says.
2. If tools/gold3_ct.py is on the branch, run its build (root $DATA_ROOT/_gold3_ct), stats, qa, export and page; if it is not, write it first to SPEC.md sections 3 to 5, with its tests. Commit STATS.md, QA.md and the page's data file; the store itself stays on the lab volume.
3. The grid-only members, from files already on the volume and nothing fetched or segmented: TotalSegmentator's 142 (read ${HOME}/model_night/ts_clean_subjects.txt and check its sha256, 2f96f917292b85416d1b803230732624a3dde0bae7c2c29f54abc4f2a30dc1b7, before anything; BRIEF.md "Need the grid") and VerSe's 17 (the sacrum, by the SPINEPS masks already on the volume, BRIEF.md). Only counts and the committed ids leave the grid; rows with paths stay in the store.
4. The anomaly statuses follow SPEC.md section 3 exactly: "confirmed_by_masks" means two masks of the same readers agree and every structural check passes, which is not a person's read of the CT; "reader_confirmed" comes only from a recorded reader verdict; every lumbosacral question says needs_ct.

## 9. Gates, pull requests, and the way back

1. bordercall: `python -m unittest discover -s holdings/tests -t .` passes; never touch schwingcheck/, the root tests/, tests/test_schwingcheck_*.py or requirements-schwingcheck.txt, which are another account's.
2. SchwingNet: `bash scripts/check.sh` passes, run in a throwaway copy of the clone (docs/memory/run-the-checks-in-a-throwaway-copy.md); the pre-push hook runs the gate and refuses a push from a tree with anything uncommitted.
3. Commit on claude/project-thread-cne00q in each, push with `git push -u origin claude/project-thread-cne00q` (never main, never a force), and write what ran, the counts, the cross-checks and an adversarial review into each draft pull request's body under "## Adversarial review".
4. Tell the owner in the session what the job found, in a few lines, with the two pull request links. The thread "Finish scan import and tier counts" then publishes the private artifact from the page's data file (a grid session has no Artifact tool) and draws the reader pictures with holdings/enhance_views.py.
5. Do not mark either pull request ready or merge it from the grid unless the owner says so in the session; the thread finishes them.
