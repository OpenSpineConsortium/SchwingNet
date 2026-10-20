# SchwingNet real-time video demo: plan for the CNS talk

Thread "SchwingNet video demo plan", 2026-10-20. A plan only: nothing was created, run, committed or spent.
Confidential (SchwingNet internals, numbers held from publication pending the technology-transfer office), so it
lives in this private repository and nowhere public; written as a plan only, before anything was created, run or spent,
and brought here unchanged by SchwingNet#6, with the owner's answers of the same day appended as section 8. Every number names the file it comes from in OpenSpineConsortium/spine-program
(`01/` = `01_carm_level_detection/`).

## 0. What the files say, before any plan

Four things in the request differ from the record. Each changes the plan, so they come first.

1. **The talk is on Monday 2 November, not 11 November.** CNS 2026 runs 31 Oct to 4 Nov in Washington DC; Greg's
   mini-oral 66629 is session MP4SP1, Mon 2 Nov, 5:21 PM (`07_plain_film_level_id/docs/handoff/MANUSCRIPTS.md` row 13).
   The plan below works back from 2 Nov, with 11 Nov kept as the date for anything after the talk.
2. **A public SchwingNet demo is a public disclosure.** As far as `provisional_patent/README.md` shows, nothing is filed;
   the counsel package WSU 26-1902 is dated today. The handoff says to use only the CT-only public deck v12 for the CNS
   talk (`07_plain_film_level_id/docs/handoff/README.md` line 285). Showing SchwingNet naming vertebrae on video at CNS
   needs the provisional filed, or counsel's written OK, before 2 Nov. That is Greg's and counsel's decision, and the
   demo work below is reversible either way: the private video is made and only shown if the gate clears.
3. **97 % is naming, not detection.** On the held-out C-arm (C-ArmLSpine, never seen in training):
   - naming, lateral, zero-shot: 595 / 617 = 96.4 % [92.3, 98.4]; fine-tuned five-fold 97.4 % (`01/STATUS.md` A2.1, A3.1);
     the count from the detected sacrum 97.0 % (A4.7);
   - naming, AP, zero-shot: 276 / 631 = 43.7 % (a one-level cranial shift; A2.2, A2.8);
   - detection recall at confidence 0.74: 231 / 287 = 80.5 % [74.1, 86.8]; 93.9 % on the repaired denominator
     (A6.1, A6.5); the pre-stated 97 % detection target is met by no held-out cell (A6.13).
4. **The detectors are not trained on synthetics alone, and the record says synthetics alone fail.**
   - `rx_lodo_carmlspine_1024` trained on real COBRA Elekta and DeepFluoro frames plus styled renders (`01/README.md`;
     `01/docs/MODEL_CARD.md` section 3.1: 5,408 synthetic and 896 real entries).
   - The naming detector `detector_v5z_final` trained on real plain films (CSXA among them; `01/docs/CINE_DEMO_BUILD_PLAN_2026-09-26.md` section 6).
   - A renders-only detector reads 0.3 % (1 / 287) at 0.74 and 31.7 % at 0.25 on C-ArmLSpine (A6.12); with no frame of
     the device, 7.0 % (A8.1). XRSpinoPelvic1K found the same on film: a DRR-only pelvis class fires on 0 of 40 real
     films, and mixing DRRs in made real-film accuracy worse (`xrspinopelvic1k/docs/RESULTS.md` lines 127-164).
   - What synthetic data does carry is the **level encoder**: zero-shot lateral naming at 96.4 % on a device it never saw.
     So the justification to write is "synthetic training transfers for naming, and detection needs real frames of
     other devices", which the record supports, and not "detection trained on synthetics", which it contradicts.
   - If Greg means a newer model this record does not hold, its name and its result file are what the plan needs.

## 1. What plays on stage

**Recommended: a recorded overlay of a real C-arm sweep, with measured latency on screen.**

- Source: C-ArmLSpine case134 and case39 raw CBCT projection sweeps, 301 frames each at 1024 x 1024, about 10.3 fps,
  CC BY 4.0, on the grid at `/rs/rs_grp_oschome/go2432/data/carmlspine/unpacked/C-ArmLSpine`. They are real
  continuous C-arm motion from lateral through oblique to AP, licence-clean for slides, with a paired CBCT that gives
  box truth by registration (`01/docs/CINE_DEMO_BUILD_PLAN_2026-09-26.md` section 3).
- Overlay: boxes coloured by track, level name and probability, "?" where the stack abstains; a frame counter, the
  gantry angle and the measured per-frame compute time in the corner. Rendered by `cine_eval.py video` (exists).
- The claim the slide may make, word for word from the build plan: "Per-frame compute on <GPU>, models resident,
  batch 1, excluding acquisition, DICOM decode and display: p50 X ms, p95 Y ms", and "real-time at 10 fps" only if the
  end-to-end p95 is under 97 ms. The tracker is causal, so the recording is what a live run would have shown.
- What the audience sees going wrong is shown, not cut: naming holds on the lateral arc and collapses toward AP (43.7 %
  zero-shot). That is the honest picture and a good slide: the stop signal and the abstain "?" carry it.
- Alternative B, a live run on a laptop GPU at the podium, is not recommended: no laptop latency exists, the CPU path
  took 3.35 s per frame for the encoder alone (`01/docs/MODEL_CARD.md` section 6.3), and an FP16 or TensorRT arm changes
  the outputs and needs its own parity and accuracy run.
- Other clips held on the grid (Neurosurgical Focus MP4s, PMC CC BY clips) have no labels and are mostly saved stills
  under overlays (`data_mining/CATALOG.md` lines 98-99); at most a qualitative second clip, never a number.

## 2. The workflow, as a Beethoven research study

beethoven-research's settled first study is "vertebral body detection on real fluoroscopy under domain shift"
(its `CLAUDE.md`), which is this work. The workflow follows its REFORMS layer: a locked environment, every run hashed,
the split level declared before anything is scored, intervals clustered by person.

| step | what | exists? | gate before the next step |
|---|---|---|---|
| W0 | SchwingNet repository from symphony-template, private; beethoven-qa vendored | no | `bash scripts/check.sh` and the beethoven-qa gate green on an empty package |
| W1 | Bring in the untracked tools as the record: `cine_eval.py`, `cine_latency.py`, `level_prototype.py`, `eval_gate.py`, `patient_keys.py` (copies in `01/code/`) | written, untracked in spinesurg-ct-nnunet | byte-equal to the 01 copies; listed as legacy (section 4) |
| W2 | Register the stack's weights with sha256 (`model_registry.py register`), as 01's S0 asks | not done | every weight the demo loads has a registry line |
| W3 | Split check: the demo cases are disjoint from every training set at person level (`beethoven_research.splits` plus `eval_gate.carry_proto`) | tools exist | gate passes with no `--not-held-out` |
| W4 | Inference over both sweeps with `level_prototype.py --dump-posterior --dump-corners` and the three weights passed explicitly (the defaults load the wrong encoder) | case134 export exists; case39 needs poses (4 GPU shards) | outputs keyed and gated |
| W5 | `cine_eval.py track`, `score --bins lat_signed_deg`, `video` | code exists, self-test tier 1 | self-test passes; contact sheet looked at by a person |
| W6 | `cine_latency.py` on one named GPU, parity first (boxes equal, names and abstain flags identical, posterior difference below 1e-5 on 50 frames) | written, never run | no latency number unless parity passes |
| W7 | The justification and anomaly measurements (sections 3 and 5) | partly | each with its interval and n |
| W8 | One slide set from the result files only, every number with its file | no | Greg reads it; the disclosure gate (section 0.2) |

## 3. Justifying the synthetic training

The defensible argument, with what already exists and what one short run adds:

- **Held-out device, held out three ways.** The device is absent from the training frames, the render poses and the
  style terms (`MODEL_CARD.md` 3.1). This is the strongest point and it exists.
- **The ablation ladder on one real test set**, already measured (A6.9 to A6.12, A8.2): renders only 0.3 %; other
  devices' real frames plus renders 80.5 %; plus 24 frames of the device 84.0 %, plateau about 82 to 85 %, 95 % of it by
  10 to 12 frames. Shown as one figure, it answers "why synthetic" (it supplies naming and the angles no real set
  covers) and "why not only synthetic" (detection needs real frames) at once.
- **Naming from synthetic, measured where it matters**: zero-shot 96.4 % lateral against fine-tuned 97.4 %, paired
  difference +1.0 [-1.9, 4.0] (A3.7). Synthetic training reaches the fine-tuned figure on lateral views; it does not on AP.
- **Per-angle breakdown on the sweeps (new, W5):** accuracy against gantry angle shows where the synthetic coverage
  holds and where it breaks, on continuous real motion.
- **Precedent to cite**, to be verified before it goes on a slide: SyntheX (Gao et al., Nature Machine Intelligence
  2023), realistic simulated X-ray training matching real-data training for X-ray-guided interventions; DeepDRR.
- Not claimable from the record: any synthetic:real ratio (none was ever swept; `01/TODO.md` C5), and anything on a
  device or C-arm at the hospital.

## 4. What Beethoven.QA says about the tools the demo would run

I ran beethoven-qa's code standards (`python -m beethoven_qa standards all --base none`, its own source at 85f0e1c,
tools from PyPI) over `cine_eval.py`, `cine_latency.py`, `level_prototype.py` and `eval_gate.py`:

- readability: 107 findings over the limits (functions of 100 to 310 lines; `level_prototype.main` has cyclomatic
  complexity 56);
- design: 2 (the `Tracker` class WMC 51; `eval_gate.Store` LCOM4 2);
- security: 4 of medium severity: three `torch.load` calls without `weights_only` (CWE-502) and one fixed temp path;
- contracts: none on any public function, so none of the four meets beethoven-qa's definition of done;
- duplication and supply chain did not run (jscpd and zizmor were not installed); coverage found no tests in the copy.

What follows for the plan: the legacy tools are taken as they are, listed under `[tool.beethoven-qa.unproven]` with the
reason "the reported pipeline; changing it breaks parity with the paper", and never refactored before the talk, since a
refactor would void the parity gate. New code in the SchwingNet repository (the score glue, the anomaly strata, the
slide figures) is written to the definition of done: icontract on every public function, CrossHair with Z3 over the
metric functions (IoU, matching, Wilson interval, tracker update), and the three `torch.load` calls get
`weights_only=True` checked against parity before W6.

## 5. Measuring accuracy on anomalous spines

What exists today: no transitional accuracy on any real image with a human read; 7 at-risk persons with a frame, none
verified; the sample frozen for a claim is 35 error-free at-risk persons (`01/STATUS.md` E.14). So by 2 Nov the honest
deliverable is a measured case series plus a synthetic arm with exact truth, labelled as such.

| stratum | real frames, by 2 Nov | synthetic arm, exact truth |
|---|---|---|
| transitional (L6, T13, sacralised L5, four lumbar) | C-ArmLSpine case42, case121, case136 (never-seen L6; one labeller's read), case139, case44; a second reader's blind read makes it a two-reader case series | CTSP transitional subtypes (194 persons, frozen G3 split, `02_transitional_naming_truth/results/paper2/rare_class/`), held-out persons only, rendered as stills or a sweep |
| ordinary (control) | the rest of C-ArmLSpine, same metrics | same renderer, matched ordinary cases |
| scoliosis, hardware, fracture | not stratified in any file read; a person tags the held-out C-ArmLSpine frames once | none planned |

Reported per stratum: detection recall at 0.74 with the 0.25 curve, exact naming, within-one, abstain and stop rates
beside every accuracy (the stop signal caught 5 of 6 erring frames, A5.3), Wilson intervals on persons. The synthetic
arm is never pooled with the real one, and the slide says which is which.

## 6. Order of work and what it spends

| when | work | spends |
|---|---|---|
| on go | W0 to W3, the QA config, the second reader's sheet | nothing |
| next | case39 pose array (4 GPU shards, about 20 min each, estimated); inference on 602 sweep frames | grid GPU, needs Greg's word |
| next | W5 score and video; W6 latency, one GPU job | grid GPU, needs Greg's word |
| next | synthetic anomaly arm: renders for held-out transitional persons | grid CPU/GPU, size set by Greg |
| by 30 Oct | slides from result files; Greg's read; disclosure gate | nothing |

No Claude token run, API key or usage credit is involved; the grid jobs run under Greg's own allocation through the
existing Beethoven route (the session submits only what Greg approves, with the number of jobs named).

## 7. Decisions that are Greg's

1. Is the talk date 2 Nov (as recorded) or 11 Nov?
2. Disclosure: show SchwingNet publicly only after the provisional is filed (recommended), or keep the demo private?
3. Which model does "trained exclusively on synthetics" mean? The plan assumes the level encoder (section 0.4).
4. Demo form: recorded sweep with measured latency (recommended) or live laptop?
5. Repository: private `OpenSpineConsortium/SchwingNet` from symphony-template (recommended), or under Greg's account?
6. Grid spend: approve the GPU jobs in section 6, and how many synthetic anomaly cases.
7. Second reader for the transitional case series: who?

## 8. The owner's answers (2026-10-20, the thread)

1. The talk is on 2 November. Anything after it keeps 11 November.
2. The provisional will be filed by 30 October; at CNS the talk shows what SchwingNet can do, not how it does it. The
   demo is made in private and shown only after the filing; nothing of the method goes on a slide.
3. The owner asked why the level encoder is trained only on synthetics. Section 0.4 is the answer the record gives: the
   encoder's fluoroscopy is synthetic because no labelled real intraoperative fluoroscopy exists for training
   (C-ArmLSpine, 296 frames, is the test set and stays held out), while its bank also holds real plain films (CSXA, BUU,
   NHANES, FluoroCap) and DRRs; the detectors are trained on real frames plus renders, and renders alone fail.
4. The demo is the recorded sweep (section 1).
5. The repository is this one, OpenSpineConsortium/SchwingNet, private, made by the owner from symphony-template.
6. The goal between now and 2 November is a better SchwingNet, trained through this framework with beethoven-qa and the
   research pipeline so every number can be backed, on the owner's H200 allocation with the dataset already on the grid;
   what "better" means (which measure, by how much, which model is the baseline) is still the owner's to say, and no
   grid job is submitted before the owner gives the word and the number (section 6).
7. The senior second transitional reader is Dr Tech, neuroradiologist at Corewell (section 5).
8. Beethoven and Symphony: the owner develops both and asked for whatever compatibility the work needs. The result is
   symphony-template#280 and beethoven-qa 6.0.0 (symphony-template's docs/research/beethoven-and-symphony.md); this
   repository takes beethoven-qa under issue #5.
