# REFORMS compliance checklist

Oct 3, 2026 · @greg

## Summary

All 32 REFORMS items can be tied to a gate, but only 20 can be verified by code; the other 12 can only be required as a written field the gate refuses to see empty. None of these gates exists yet: both repositories today are the Remote Control launcher (hpcworker framework 11, extension 12.0.0) and contain no Hydra, run hashing, splitting, CI, CodeCarbon, LaTeX or archiving code.

Each gate fires at one of four points, and the checklist below names which:

- **Before dispatch**: the run is refused before `sbatch` (dirty tree, missing config, no split key).
- **After the run**: the run finishes but is stamped non-compliant in its manifest (no CI, leakage check failed).
- **Before publish**: the manuscript build, Zenodo deposit or Hugging Face push is refused.
- **Declared**: a human-written field in the run manifest must be non-empty; the code checks presence, not truth.

The item list is taken from the REFORMS paper itself ([Kapoor et al., arXiv 2308.07832](https://arxiv.org/pdf/2308.07832); module names confirmed on [reforms.cs.princeton.edu](https://reforms.cs.princeton.edu/)). The goal text's mapping comes from "02-Autonomous AI HPC Architecture" in the Beethoven-notebook folder.

## Who owns what

The gates split three ways, because the framework is held to bash 4.2 and Python 3.6 standard library (the CentOS 7 login node) while most gates need Hydra, MONAI, W&B and CodeCarbon, which only the container can carry.

| Owner | Takes | Why there |
| --- | --- | --- |
| **hpcworker** (`framework/`) | Run manifest and Run ID, clean-tree refusal, environment and compute record, the gate runner that reads the manifest, publish lock | Stdlib-only, runs inside the job, already renders job files from the site profile; `docs/ARCHITECTURE.md` section 2 reserves workflow-engine templates beside `jobs/` |
| **hpcworker** (`jobs/build_image.sbatch`, the lab's image) | Pinned Hydra, MONAI, W&B, CodeCarbon, LaTeX in the shared worker image | The image is the lab's shared "gas"; the job must not install packages at run time |
| **New repo, proposed `beethoven-research`** | Python package plus project template: Hydra config schema, group-level splitter, leakage checks, bootstrap CIs, HU calibration, MetaTensor checks, LaTeX macro writer, Zenodo and Hugging Face card builders | Modern Python, domain code, versioned with the science rather than with the launcher |
| **beethoven-extension** | A read-only checklist view per run, and the human "Publish" approval | The panel only reads files the job writes (contract); it never holds a Zenodo or Hugging Face token |

The seam is one new contract file per run, `reforms.json` (item id, state, evidence path), written by the gate runner and read by the panel; it goes into `docs/V12_CONTRACT.md` and `extension/src/core/contract.ts` together.

## Checklist

One row per REFORMS item. "Research" is the proposed `beethoven-research` repository; "Declared" means a field in the study's `study.yaml` that the gate requires non-empty but cannot judge.

| Item | REFORMS asks for | Automated gate | Fires | Check | Owner |
| --- | --- | --- | --- | --- | --- |
| 1a | Population the claim is about | `study.population` present | Before dispatch | Declared | Research schema, hpcworker runner |
| 1b | Why that population | `study.population_rationale` present | Before dispatch | Declared | Research schema |
| 1c | Why ML | `study.ml_rationale` present | Before dispatch | Declared | Research schema |
| 2a | Dataset with link or DOI | Input tree hashed (sha256 per file, Merkle root) into the manifest; manuscript build refuses an empty dataset DOI macro | Before publish | Code | hpcworker (hash), Research (Zenodo deposit) |
| 2b | Code | Clean-tree refusal: `git status --porcelain` empty and HEAD reachable on the remote, else no `sbatch` | Before dispatch | Code | hpcworker |
| 2c | Computing infrastructure | Job writes node, partition, GPU model, image digest, `sacct` elapsed and CodeCarbon kWh into the manifest | After the run | Code | hpcworker (record), image (CodeCarbon) |
| 2d | README with instructions | README generated from the manifest; gate checks it names the reproduce command | Before publish | Code | Research template |
| 2e | Reproduction script | `reproduce.sh` regenerated from the Run IDs; gate dry-renders it and compares job files to the originals | Before publish | Code | hpcworker |
| 3a | Data sources per split | Source paths and hashes recorded per split | After the run | Code | hpcworker |
| 3b | Sampling frame | `data.sampling_frame` present | Before dispatch | Declared | Research schema |
| 3c | Why the dataset fits the task | `data.fitness_rationale` present | Before dispatch | Declared | Research schema |
| 3d | Outcome variable and statistics | Label summary computed and written by the prep step | After the run | Code | Research |
| 3e | Sample size, outcome frequencies | Counts per split per class, at patient and image level | After the run | Code | Research |
| 3f | Missing data by class | Missing-field rates per class, including absent DICOM tags | After the run | Code | Research |
| 3g | Representativeness | `data.representativeness` present | Before dispatch | Declared | Research schema |
| 4a | Excluded samples, with reason | Prep emits `exclusions.csv`; gate fails unless input = kept + excluded | After the run | Code | Research |
| 4b | Corrupt samples | Unreadable DICOM or missing RescaleSlope/RescaleIntercept goes to `exclusions.csv`, never silently dropped | After the run | Code | Research |
| 4c | All transforms, raw to input | Transforms live only in Hydra config; HU calibration asserted; MetaTensor `applied_operations` saved per sample | After the run | Code | Research |
| 5a | All models trained | Resolved Hydra config saved per Run ID, including failed and swept runs | After the run | Code | hpcworker (store), Research (config) |
| 5b | Why these model types | `model.rationale` present | Before dispatch | Declared | Research schema |
| 5c | Evaluation method and splits | Split file (with group key) hashed into the Run ID; no split file, no dispatch | Before dispatch | Code | Research (splitter), hpcworker (hash) |
| 5d | How the reported model was chosen | Selection metric and split in config; gate fails if selection read the test split | After the run | Code | Research |
| 5e | Hyperparameter tuning | Every sweep trial's Run ID logged, not only the winner | After the run | Code | Research |
| 5f | Appropriate baselines | At least one baseline in config, and its run exists | Before publish | Declared | Research schema |
| 6a | Preprocessing fit on training data only | Fitted transforms carry the split they were fit on; anything other than train fails | After the run | Code | Research |
| 6b | Dependencies and duplicates across splits | Split by PatientID or StudyInstanceUID; gate asserts zero group overlap and zero identical pixel hashes across splits | Before dispatch | Code | Research |
| 6c | Each feature legitimate | `features.legitimacy` present per feature group | Before dispatch | Declared | Research schema |
| 7a | All metrics | Metrics listed in config are all logged; macros are written only from logged values | Before publish | Code | Research |
| 7b | Uncertainty and how computed | Bootstrap CI per reported metric, resampled by patient, with resample count recorded; macro writer refuses a metric with no CI | Before publish | Code | Research |
| 7c | Statistical tests and assumptions | `stats.tests` with justification present | Before publish | Declared | Research schema |
| 8a | External validity | `limits.external_validity` present; an external site in config is evaluated and reported separately | Before publish | Declared | Research schema |
| 8b | Where findings won't hold | `limits.non_generalization` present | Before publish | Declared | Research schema |

The goal's other gates sit inside these rows: run hashing is 2b and 5c, the clean tree is 2b, the patient-level split is 6b, bootstrapped CIs are 7b, CodeCarbon is 2c, LaTeX macros carry 7a and 7b, Zenodo carries 2a, and Hugging Face cards repeat 5a and 7b for the weights. Energy reporting is not a REFORMS item; it rides on 2c as an addition.

## Conflicts and open questions

Four parts of the goal text collide with rules already in `CLAUDE.md` or with how the cluster works; the checklist above assumes the fixes listed.

- **Run ID must not hash volatile Slurm variables.** Hashing `SLURM_JOB_ID` or node names makes every rerun a new ID, which defeats 2e. Proposed: hash config, commit SHA, image digest, lockfile and split file; record Slurm variables beside the ID, not in it.
- **Zenodo and Hugging Face publishing are permanent and outward.** A DOI cannot be withdrawn. The gates prepare a draft deposition and card; the publish action waits for the student's click in the panel, never the agent.
- **Tokens.** Zenodo and Hugging Face tokens fall under the no-secrets-on-argv rule: a mode-0600 file the job reads, never in `sbatch --export`, logs or the manifest, and never in the extension.
- **LiteLLM key rotation is out.** Rotating several accounts' keys breaks "one person, one account" and the no-credentials rule; it is not part of this checklist.

Open questions for greg:

- [ ] New repository `beethoven-research`, or a `research/` folder in hpcworker?
- [ ] Metaflow, or the framework's own job chaining? A workflow engine cannot run on the login node, so Metaflow's scheduler would itself have to run inside a job.
- [ ] Does the interactive Remote Control worker launch gated runs, or only headless `claude -p` jobs?

## Build order

Start with the two gates that need no ML libraries, since every later gate writes into the manifest they create.

1. hpcworker: run manifest, Run ID and clean-tree refusal (2b, 2c, 3a, 5a, 5c), stdlib only, with tests in `framework/tests/`.
2. hpcworker: `reforms.json` in the contract, and the gate runner that fills it from the manifest.
3. Image: pin Hydra, MONAI, W&B and CodeCarbon in `jobs/build_image.sbatch`.
4. Research: `study.yaml` schema (all 12 declared items) and the group-level splitter with overlap and duplicate checks (6b).
5. Research: data-prep reporting (3d to 4c) and fitted-transform tagging (6a).
6. Research: bootstrap CIs and the LaTeX macro writer (7a, 7b), then `reproduce.sh` and README (2d, 2e).
7. Extension: read-only checklist view per run, then the Publish approval that releases the Zenodo and Hugging Face drafts (2a).
