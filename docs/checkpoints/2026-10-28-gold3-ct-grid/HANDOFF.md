# Handoff: the gold tier 3 CT dataset, run on the grid through Beethoven (2026-10-28)

Thread "Finish scan import and tier counts". The owner's ask, 2026-10-27 22:49 UTC, verbatim: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". Then, 2026-10-28 00:04 UTC: "maybe these steps should jsut work on the grid? can you write a handoff for this to run over the beethoven extension on the grid?"

This page is for a Claude Code session the owner opens on the grid with the Beethoven extension. The whole computation is one batch job, gold3-facts.sbatch beside this page, which builds its own Python, runs the tests, reads the masks twice, checks the readings against each other and against the count, takes them into the dataset, writes its pages and builds its store. The session does only what needs no Python: it clones, sends the fetch word, checks the masks' hashes, flips one line of members.json, queues the job, and commits what the job leaves. The design is docs/research/gold3-ct/ (README.md where the programme stands, SPEC.md the build plan, BRIEF.md what exists); this page carries none of it. Confidential like the rest of SchwingNet and bordercall: nothing here or made from it goes to a public place, and no path under the data root, no DICOM UID and no PatientID leaves the grid, in a commit, a message or anywhere else.

## 0. The owner's count, before anything runs

Print this block in the session and wait for the owner's yes. Nothing from step 6 on runs without it, and nothing beyond it runs at all.

1. One fetch, through the gate word, so the size rule reads the exact size and refuses it whole if it would pass the CephFS quota: `fetch aws_enhance_pet_labels`. The word's line states 2.5 GB; the prefix it lands is the public bucket's whole ground-truth folder, 11,256,936,591 bytes listed on 2026-10-27, of which this work reads two folders, Vertebrae (381,439,888 bytes) and Ribs (312,882,241 bytes). The word has no narrower form; the other five folders serve the paused Flux realism programme.
2. One CPU job, hpcworker's batch class, 16 CPUs, 64 GB, 24 hours: gold3-facts.sbatch. It builds its Python in the work folder (pixi, its downloads kept there too, under 0.8 GB), runs both repositories' tests, runs the two readings and the count's two steps side by side, compares them, takes the facts, writes the dataset's pages and builds the store with two CSV exports under $DATA_ROOT/_gold3_ct (a few MB). It writes nowhere else. Slurm requeues it on preemption, and a requeued run skips every finished step; a time-out is not requeued, and the first step that fails ends it.
3. Two reads with no job: the sha256 of the 3,194 fetched masks, and the sha256 and line count of TotalSegmentator's subject list in the grid home.

Not in this count, each its own word later: a second fetch, or a second job (a time-out, an out-of-memory end or a failed step does not license one); the Leipzig and Careggi CTs (45,207,300,328 bytes, a new url-route line); the grid index job (autoPET masks matched to held CTs, TotalSegmentator's rows, VerSe's sacrum); any SPINEPS or bordercall run (the bordercall pilot of 2 CPU jobs is approved and unsent, and belongs to its own word). Never: CT-RATE without the owner's terabytes, Radiopaedia by script, usage credits, a segmenter run, TotalSegmentator as a segmenter.

## 1. Where things are

| what | where |
| --- | --- |
| This page and the job script | SchwingNet, branch claude/project-thread-cne00q: docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md and gold3-facts.sbatch |
| The plan | the same branch: docs/research/gold3-ct/README.md, SPEC.md, BRIEF.md |
| Dataset records | the same branch: data/gold3-ct/members.json, verse.json, totalsegmentator.json; data/gold3-ct/enhance-pet/record.json, bucket.json (the listing with exact bytes), SHA256SUMS (the 3,194 masks the thread read), ct-details.json (CT-details.xlsx's rows), touch.json (the repair record's 3-D distances for 143 studies), facts-repaired.jsonl (the three repaired rows, until the facts are taken) |
| The dataset tool | the same branch: tools/gold3_ct.py (take-facts, build, query, stats, qa, export, page, check; standard library only) and tests/test_gold3_ct.py |
| The mask readers | bordercall, branch claude/project-thread-cne00q: holdings/enhance_facts.py (the first reading, reusing the count's own rules), holdings/enhance_facts_check.py (the second, written blind from SPEC.md, with `compare`), holdings/enhance_facts_cross.py (the first reading against the count's outputs and touch.json), tests under holdings/tests/ |
| The count | bordercall: holdings/count_enhance_pet.py, whose extents and ribs steps the job runs again |
| The draft pull requests | SchwingNet #437 and bordercall #17, both from claude/project-thread-cne00q; their bodies are the record |

SPEC.md and BRIEF.md speak of the thread's container. On the grid: /tmp/claude-0/enh/masks is $VERT and /tmp/claude-0/enh/ribs is $RIBS (step 6); CT-details.xlsx is ct-details.json; seed/extents.json is the job's $W/out/count/extents.json, and seed/ribs_contacts.json and seed/ribs_pairs.json are both in its $W/out/count/ribs.json, which tallies the lowest ribs' contacts for all 1,597; /mnt/project-files/enhance-pet-repair/touch.json is touch.json on the branch; the three repaired vertebra masks are not on the grid (bordercall keeps no mask in git), so their rows come from facts-repaired.jsonl, read in the thread's container by bordercall's holdings/enhance_facts.py at 782d531 and again, byte for byte, at the commit FACTS.json names, or from facts.jsonl where the thread has committed the facts already.

## 2. Open the session

1. Start a Beethoven worker on the grid and open its session in the home folder (Beethoven's New session, or the Claude project's own Work locally from the + menu, docs/memory/beethoven-worker-and-claude-projects.md).
2. Tell it: "Clone SchwingNet's branch claude/project-thread-cne00q into ~/work/gold3 with `mkdir -p ~/work/gold3 && cd ~/work/gold3 && git clone --branch claude/project-thread-cne00q https://github.com/OpenSpineConsortium/SchwingNet.git`, unless ~/work/gold3/SchwingNet is there already, then read ~/work/gold3/SchwingNet/docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md and follow it. Never check out, pull or edit ~/SchwingNet."
3. The session runs as a worker under the owner's login (docs/agents/WORKERS.md), changes nothing in bordercall, and in SchwingNet works only on the branch above, in the clone under ~/work/gold3.

## 3. How commands run here

- A Bash call keeps its working folder but no variable. So the work folder's env.sh holds every name the page uses, and every block from step 6 on starts with `. "$HOME/work/gold3/env.sh"`.
- The nodes run CentOS 7, whose python3 is 3.6, python 2.7 and git 1.8. No step runs Python outside the job; the session needs only git, find, ls, grep, sed, wc, sha256sum, squeue, sacct and hpcworker.
- Submit, estimate, stop: after the fetch word and after the job's submission, tell the owner the job's number, an estimate and what to say when it ends, and end the turn. Never sleep or poll. When the owner comes back, read the state once.
- A job's number is written to env.sh by the same call that sends it (steps 6.2 and 7.4), so a session cut short never leaves a job out there that env.sh does not name.
- Never work in ~/SchwingNet and never pull it: it is the gate's own checkout. The gate reads its own copy of the fetch word; the job runs from the work folder's clones.
- Never paste a path under the data root into a message or a commit, a failure's included. The job cuts them from what it prints; anything read elsewhere is cut by hand.

## 4. Coming back to this work

A session may end between the fetch and the job, or during the job, and a new one may be told the same thing. If `$HOME/work/gold3/env.sh` exists, this work has begun: never clone again, never delete or reset anything under ~/work/gold3, never write env.sh afresh, and never send the fetch word or queue the job again without the owner's word. Read where it stands, by the names env.sh holds and not their values (VERT and RIBS are paths under the data root), and carry on from there:

```
E="$HOME/work/gold3/env.sh"; sed 's/=.*//' "$E" | tr '\n' ' '; echo; grep -E '^(FETCH|JOB)=' "$E"
ls "$HOME/work/gold3/out" 2>/dev/null; ls "$HOME/work/gold3/gold3-facts.sbatch" 2>/dev/null
squeue -h -u "$USER" -o '%i %j %T %M' 2>/dev/null | grep gold3; sacct -X -n -S now-3days -o JobID,JobName%30,State 2>/dev/null | grep gold3
grep ' fetch:aws_enhance_pet_labels ' "$HOME/SchwingNet/grid/logs/GATE_JOBS.txt" 2>/dev/null | cut -d' ' -f1,2,4
```

With JOB in env.sh, go to step 7.6. With VERT and no JOB: if squeue or sacct lists a gold3 job, a submission went out that env.sh does not name; tell the owner its number and state and ask before anything else. If neither lists one but gold3-facts.sbatch is in the work folder, step 7.4 began and may or may not have queued: tell the owner what squeue and sacct printed and go on only on the owner's word. Otherwise step 7 from its first item (the hash check again, which is quick; the members.json line may be flipped already, which its grep shows). With FETCH and no VERT, step 6.4. With none of them: if the gate's job list (the last line above) names a fetch of aws_enhance_pet_labels, a fetch went out, this work's or an earlier one; tell the owner its number and date and ask before going on. Otherwise the owner's yes is still to come: print the count of step 0 again and wait.

## 5. The work folder, before the yes

1. Clone bordercall beside SchwingNet, and check that both clones carry this work's files:

```
cd "$HOME/work/gold3"
git clone --branch claude/project-thread-cne00q https://github.com/OpenSpineConsortium/bordercall.git
test -f SchwingNet/docs/checkpoints/2026-10-28-gold3-ct-grid/gold3-facts.sbatch && test -f bordercall/holdings/enhance_facts_cross.py && grep -q contacts_moved bordercall/holdings/enhance_facts_check.py && echo "clones carry this work"
```

Both repositories are private: if git cannot reach them with the owner's own credentials on the grid, stop and tell the owner exactly that; never ask for or handle a token. If the last line does not print, stop and tell the owner the branches are not yet pushed.

2. Find the gate's hpcworker and check it, then write env.sh, once:

```
HPCWORKER=$HOME/hpcworker/framework/bin/hpcworker
bash "$HPCWORKER" job version
grep -c '^aws_enhance_pet_labels|' "$HOME/SchwingNet/grid/run-platform-fetch.sh"
[ -e "$HOME/work/gold3/env.sh" ] || printf 'W=%q\nDATA_ROOT=%q\nHPCWORKER=%q\n' "$HOME/work/gold3" /rs/rs_grp_oschome/go2432/data "$HPCWORKER" > "$HOME/work/gold3/env.sh"
```

`job version` must print `HPCW-JOB version N interface ...` with N at 27 or later, since an older hpcworker hands the job its own environment and not the caller's, and the job needs W, VERT, RIBS and DATA_ROOT from the caller. The grep must print 1. If the file is missing or N is older, ask the owner; never install or update hpcworker.

3. Say which case this is: `ls "$HOME/work/gold3/SchwingNet/data/gold3-ct/enhance-pet/"`. With facts-repaired.jsonl and no facts.jsonl, the job writes the facts (case A). With facts.jsonl, the thread has committed facts read in its container, and the job only checks that the grid's reading gives them again and records that it does (case B). The thread pushes nothing under data/gold3-ct or docs/research/gold3-ct to this branch while the grid run may be under way, so the case does not change under the job.

4. See whether the labels have been fetched before, by any word:

```
. "$HOME/work/gold3/env.sh"; ls "$DATA_ROOT/aws_enhance_pet_labels" 2>/dev/null | head -n 5
grep ' fetch:aws_enhance_pet_labels ' "$HOME/SchwingNet/grid/logs/GATE_JOBS.txt" 2>/dev/null | cut -d' ' -f1,2,4
```

If either prints, say so with the count: the masks may be on the grid already, and the owner may answer that the fetch is not needed, in which case step 6.4 follows the yes in place of 6.1 to 6.3.

5. Print the count of step 0 and wait for the owner's yes.

## 6. The fetch, after the yes

1. Read the room: `. "$HOME/work/gold3/env.sh"; HPCWORKER="$HPCWORKER" bash "$HOME/SchwingNet/grid/gate.sh" status | sed -n '1,30p'`.
2. Send the word once, and record its job's number in the same call:

```
. "$HOME/work/gold3/env.sh"
if grep -q '^FETCH=' "$W/env.sh"; then echo "a fetch is recorded already: stop"; else
  out=$(HPCWORKER="$HPCWORKER" bash "$HOME/SchwingNet/grid/gate.sh" fetch aws_enhance_pet_labels 2>&1); printf '%s\n' "$out"
  id=$(printf '%s\n' "$out" | sed -n 's/^ *dp_aws_enhance_pet_labels: job \([0-9][0-9]*\).*/\1/p' | tail -n 1)
  [ -n "$id" ] && printf 'FETCH=%q\n' "$id" >> "$W/env.sh" && echo "recorded FETCH=$id"
fi
```

It prints the room, the line's stated size (2.5 GB, printed as "3 GB stated"), the job's number, with `(afterany:...)` when it waits for fetches already running, and the line recorded. With no recorded line, the gate refused or queued nothing: tell the owner what it printed and stop. The job reads the exact size from the bucket's listing when it starts, and is admitted or refused whole there; a refusal ends it with exit 4 having fetched nothing. Never send the word again while its job is queued or running, and never after a refusal.
3. Tell the owner the job's number; that 11.3 GB from the public bucket should take well under an hour once it starts, and that with `(afterany:...)` it starts only after those fetches end; and to tell you when `status` shows it ended. End the turn.
4. When the owner comes back, read `. "$HOME/work/gold3/env.sh"; HPCWORKER="$HPCWORKER" bash "$HOME/SchwingNet/grid/gate.sh" status | sed -n '1,40p'` once. If the job is still queued or running, say so and end the turn. If it was refused or failed, tell the owner what status says and stop. If it ended well, find the two folders, count them and record them, in one call:

```
. "$HOME/work/gold3/env.sh"
VERT=$(dirname "$(find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*/Vertebrae/0001.nii.gz' 2>/dev/null | head -n 1)")
RIBS=$(dirname "$(find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*/Ribs/0001.nii.gz' 2>/dev/null | head -n 1)")
nv=$(ls "$VERT" 2>/dev/null | grep -c 'nii.gz$'); nr=$(ls "$RIBS" 2>/dev/null | grep -c 'nii.gz$'); echo "$nv $nr"
if test -f "$VERT/0001.nii.gz" && test -f "$RIBS/0001.nii.gz" && [ "$(dirname "$VERT")" = "$(dirname "$RIBS")" ] && [ "$nv" = 1597 ] && [ "$nr" = 1597 ]; then
  echo found; grep -q '^VERT=' "$W/env.sh" || printf 'VERT=%q\nRIBS=%q\n' "$VERT" "$RIBS" >> "$W/env.sh"
fi
```

It must print 1597 1597, then found; anything else stops the work, and env.sh is left without VERT, so the way back comes here again.

## 7. The hashes, the record that the grid holds the masks, and the job

1. The grid's copy must be byte for byte the copy the thread read (sha256sum is fine on any node):

```
. "$HOME/work/gold3/env.sh"
cd "$(dirname "$VERT")" && sha256sum --quiet -c "$W/SchwingNet/data/gold3-ct/enhance-pet/SHA256SUMS" && echo "3194 masks match"
```

Any mismatch stops the work: tell the owner how many files, and change nothing.

2. Only then, members.json says the grid holds them. The job's pages read members.json, so this comes before the job:

```
. "$HOME/work/gold3/env.sh"; cd "$W/SchwingNet"
sed -i 's/^    "held": false,$/    "held": true,/' data/gold3-ct/members.json
grep -c '"held": false' data/gold3-ct/members.json; git diff --stat
```

It must print 0, then one file with one line changed.

3. TotalSegmentator's subject list, for the owner's message only; nothing of it is committed:

```
sha256sum "$HOME/model_night/ts_clean_subjects.txt"; wc -l < "$HOME/model_night/ts_clean_subjects.txt"
```

The hash should be 2f96f917292b85416d1b803230732624a3dde0bae7c2c29f54abc4f2a30dc1b7; say whether it is, and the line count. A missing file or another hash is reported, not a stop.

4. Copy the script into the work folder, let hpcworker check it, then queue it once and record its number, all in one call:

```
. "$HOME/work/gold3/env.sh"; cd "$W"
cp SchwingNet/docs/checkpoints/2026-10-28-gold3-ct-grid/gold3-facts.sbatch "$W/"
queue() { env W="$W" VERT="$VERT" RIBS="$RIBS" DATA_ROOT="$DATA_ROOT" GOLD3_BORDERCALL_COMMIT="$(cd bordercall && git rev-parse HEAD)" GOLD3_SCHWINGNET_COMMIT="$(cd SchwingNet && git rev-parse HEAD)" bash "$HPCWORKER" job submit --project schwingnet --name gold3_facts --class batch --dir "$W" "$@" -- gold3-facts.sbatch 2>&1; }
if grep -q '^JOB=' env.sh || squeue -h -u "$USER" -o '%j' | grep -q gold3; then echo "a job is recorded or queued already: stop"
elif queue --check; then
  out=$(queue); printf '%s\n' "$out"
  id=$(printf '%s\n' "$out" | sed -n 's/^HPCW-JOB submitted \([0-9][0-9]*\) .*/\1/p' | tail -n 1)
  [ -n "$id" ] && printf 'JOB=%q\n' "$id" >> env.sh && echo "recorded JOB=$id"
fi
```

It must end with the recorded line. A refused check prints hpcworker's reason and queues nothing; a submission with no recorded line, or the stop line, goes to the owner as it printed, and nothing is sent again.

5. Tell the owner the job's number, that it should take 8 to 14 hours once it starts and 24 at most, and to tell you when it has ended. End the turn.
6. When the owner comes back, read the job's state once, then its log:

```
. "$HOME/work/gold3/env.sh"
squeue -h -j "$JOB" -o '%T %M' 2>/dev/null; sacct -X -n -j "$JOB" -o State,ExitCode,Elapsed 2>/dev/null | head -n 3
bash "$HPCWORKER" job log --project schwingnet "$JOB" | tail -n 80
```

The state decides first. If squeue lists the job, or sacct says PENDING, RUNNING, REQUEUED, SUSPENDED or COMPLETING, it has not ended: tell the owner the state and the time so far, and end the turn (a queued job's log says no output yet, and a running one's ends on a step's starting line). If neither answers, say so and end the turn. Only for a job that has ended does the log say how: each step prints a starting and a finished line; a job that finished ends with GOLD3_FACTS_DONE, after the take-facts and store logs; a job that stopped itself ends with GOLD3_FACTS_STOPPED and its exit code, after a FAILED line naming the step with the last lines of its log ($W/out/<step>.log), paths under the data root already cut, and exit 69 means the node had no sandbox or no apptainer. A log with neither marker was ended by Slurm, and sacct's state names how: TIMEOUT, OUT_OF_MEMORY, NODE_FAIL, PREEMPTED or CANCELLED.
7. For a stop or a Slurm end, tell the owner which step and what its log or sacct says, and change nothing. Queuing it again is a second job, which needs the owner's word; if given, take the JOB line out of env.sh (`sed -i '/^JOB=/d' "$HOME/work/gold3/env.sh"`) and run step 7.4's block again, which skips every finished step and resumes both readings from their partial rows.

## 8. What the job holds to

Every step is a stop: the job ends at the first that fails, a failed reading included, and nothing reaches the clone before the readings agree.

1. environment and versions: Python 3.13 with numpy 2.5.4, scipy 1.18.1, nibabel 5.4.2 and pillow 13.0.0, the thread's versions, so every float rounds as there. The thread built this environment with pixi 0.81, the grid's, and both readings gave the container's bytes on six studies.
2. tests: bordercall's holdings tests and SchwingNet's tests/test_gold3_ct.py pass in that Python.
3. compare (agreement.json): the two readings agree on every study's label voxels, rib voxels, sternum voxels, distances to one 0.1 mm rounding step, and every rib's lead and tie. Contact counts may differ only as far as the second reading's audit of that rib explains: a voxel at the same distance from two labels (each reading takes scipy's nearest label over a box of its own) moves one count from one label to the other, and a voxel at the 3 mm limit may fall on either side; agreement.json's contacts_moved gives, for every rib whose counts differ, the counts moved and the counts the audit allows. Anything else is a fail.
4. cross (cross.json): the first reading gives the count's own results on all 1,597: voxels per label, head-foot extents to 0.05 mm and the grid, rib voxels with the sternum as label 27, and on each side the lowest rib with its contacts, lead and tie; and touch.json's 3-D distances, measured by the repair record's own touch.py, for its 143 studies. The count measures no distance.
5. take_facts. It first puts data/gold3-ct/enhance-pet back as the branch holds it, so a run cut short inside it starts again cleanly. Case A: it writes facts.jsonl (1,600 rows, the 1,597 and 1134r, 1283r, 1347r), facts-b.jsonl (1,597 rows) and FACTS.json (where and by what the rows were read, the repaired rows' own commit, and the hashes of SHA256SUMS and ct-details.json), and removes facts-repaired.jsonl. Case B: it prints `"reproduces": true` and adds this run to FACTS.json's reproduced_on; a reading that differs prints the ids, writes nothing and stops the job.
6. pages: stats, qa and page are written from the rows, and check prints current. check holds ENHANCE.PET to members.json's 1,557 gold 3, 3 gold 4 and 37 silver 3 and to the note's table, so the job ends here unless the rows give the note's numbers.
7. store: version 1 or later under $DATA_ROOT/_gold3_ct, the two CSV exports beside it, and the persons by member.

The thread then checks, from the pushed rows, the three studies it read by hand on 2026-10-28: 0001's lowest ribs meet label 19 with 108 contacts on the left and 121 on the right, and its 23-28, 24-28 and 23-24 distances are 15.3, 0.9 and 0.9 mm; in 0603 label 13 has two pieces and ribs 6 to 11 lead one label below their own; 0529 equals the row the container read.

## 9. Commit, push, and tell the owner

1. After GOLD3_FACTS_DONE, see what the job changed:

```
. "$HOME/work/gold3/env.sh"; cd "$W/SchwingNet"; git status --short
```

Case A: members.json, STATS.md, QA.md and page-data.json modified; facts-repaired.jsonl deleted; facts.jsonl, facts-b.jsonl and FACTS.json new. Case B: members.json, FACTS.json, STATS.md and page-data.json modified (QA.md holds no hashes and stays as it was). Anything else stops the work: tell the owner what, and commit nothing.

2. Commit and push, never to main and never with a force. In case A:

```
. "$HOME/work/gold3/env.sh"; cd "$W/SchwingNet"
git add -A data/gold3-ct docs/research/gold3-ct
git commit -m "Take ENHANCE.PET's mask facts read on the grid" -m "hpcworker job $JOB on the grid: both readings of the 1,597 published vertebra and rib masks, which hash to SHA256SUMS, agree but for contact counts their audit explains, and the first gives the count's own results and touch.json's distances. members.json says the grid holds the masks; the pages are written from the rows and check says current; the store is built on the lab volume."
git push -u origin claude/project-thread-cne00q
```

In case B, the same with the message `-m "Record that the grid's reading of ENHANCE.PET's masks gives the committed facts again" -m "hpcworker job $JOB on the grid read the 1,597 published vertebra and rib masks, which hash to SHA256SUMS, twice, and gave the committed facts and second reading row for row; FACTS.json's reproduced_on records it. members.json says the grid holds the masks; the pages are written again and check says current; the store is built on the lab volume."`.

If git has no name and e-mail on the grid, ask the owner which to use; never make one up. A fresh clone sets no pre-push hook, so CI's check on the draft pull request is the gate, and the thread reads it. If the push is refused because the branch moved, `git pull --no-rebase origin claude/project-thread-cne00q` and push again; if that merge conflicts, `git merge --abort`, stop, and tell the owner.

3. Tell the owner, in a few lines and with no path under the data root: the case; take_facts' and the store's lines from the job's log (the rows, or that the reading reproduces the thread's; the store's version and items; the persons by member); the TotalSegmentator list's hash and lines; and the pull request, https://github.com/OpenSpineConsortium/SchwingNet/pull/437. The thread "Finish scan import and tier counts" then checks CI and the three studies above, draws the reader pictures with holdings/enhance_views.py, publishes the private artifact from the page's data (a grid session has no Artifact tool), and finishes both pull requests.
4. Do not mark either pull request ready or merge it from the grid unless the owner says so in the session.
