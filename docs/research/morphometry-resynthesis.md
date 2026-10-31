# Morphometry resynthesis before the reruns

Source: the thread "Run morphometry on gold tier 3 masks" of the claude.ai project symphony_3, 2026-10-30 and 31, written on the owner's word of 2026-10-30 23:56 UTC ("it was just integrating all the screens i did on morphometrics code, Prs and lit searches with the current code base"). It sets the owner's morphometry screens, bordercall's pull requests and the literature notes beside the engine as it now stands, and decides whether the held count of 14:33 UTC (enhance, verse, covariates) can be sent. Confidential, this repository only. Aggregates only; no mask, CT, path or per-study row.

## The code it is checked against

The engine is bordercall's morphometry/ and morphoview/ at 9c85de1 (pull request #49), vendored here under grid/bordercall/ with code stamp 1cee7ea83e4c28db under --lines. bordercall's main has moved to 0525fd9 since, but `git diff 9c85de1 0525fd9 -- morphometry morphoview` is empty: #50, #59, #60 and #61 changed schwingcheck, the demos and the naming study, not the engine. So the vendored copy is the current code, and the rerun measures with it.

## What each piece found, and where it stands now

| Piece | What it found | Standing on 9c85de1 |
| --- | --- | --- |
| The run over 229 thin-slice ENHANCE.PET studies (bordercall research_notes/morphometry/README.md) | 228 measured, one stopped; the masks lie on the bone's edge to a few tenths of a millimetre; medians move under 0.9 mm on 3 and 5 mm slices | Made on the engine before #44; its rows are what the rerun replaces |
| Four measures wrong by construction (same note, handoff.md) | Interpedicular distance at L4, L5 and the neck read across the canal; pedicle width and height in the neck, C7 and T1; mid-disc height 1.35 mm short in the neck and upper thorax; the pedicle's sagittal angle stepped with the raster | Reworked by #44 (pedicle.py, canal.py, body.py), merged as ee495d5; checked only on study 0004's traces, so the rerun is their first test on real spines |
| Each measure's line and frame (#47) and the two cameras held to one geometry (#49) | All 150 lines drawn at C5, T1, T8, L3, L4 and L5 of study 0004 matched the rows; morphoview and autoanatomist/project.py agree but for the half-pixel centre convention | In the engine; the rerun writes lines.csv and frames.csv beside the rows |
| The bounds card of the synthetic validation (#38, still an open draft on bordercall) on the old rows | Body and end-plate steps pass; pedicles and canal fail (L5 near 27 mm against about 15, T10 to T12 and L3 down); discs fail at L4-L5 and T10 to T12 | The pedicle and canal failures are the four defects #44 reworked; the disc failures at L4-L5 and T10 to T12 are not explained by any change and may be age, which the covariates join can test |
| Tan 2004 as a stratum and a population register (#43); the clinical reread's data fixes (#39); the archive decision (#46) | Strata and subgroup analysis by any variable; the reread's comparison rerun; the archive left as it was | Outside the engine; read the new rows once they exist. Archived code is not run |
| Plan for latent shape priors against explainable measurements (#45) | Stage 1 exports the explainable measures per vertebra | Waits for the new rows |
| The correlation prior (#50) and phantoms drawn jointly from it (#59) | `python -m schwingcheck.correlation fit --rows rows.csv` fits correlations across levels and measures from real spines; the phantom generator draws from it | The fit on the old rows would carry the four defects into every phantom, so it waits for the new rows |
| The census of every measure in hand (#35, still an open draft on bordercall) | One tool over Panjabi's table, the clinical reread's series and a table in the gold tier 3 schema, with its record and report plan | Outside the engine (schwingcheck/census.py); it reads rows, so it takes the new rows once merged |
| The literature (morphometry-beyond-the-42-papers.md, bordercall's paper tables) | The naming rule rests on Panjabi's twelve spines; nothing published gives within-person correlations of his measures from C2 to L5 in hundreds of people; that has to be measured on the lab's own masks | The rerun over ENHANCE.PET, VerSe and the admitted TotalSegmentator subjects is that measurement |

Open pull requests checked on 2026-10-31: bordercall #35, #38 and #42 (a README rewrite) are unmerged, and none of them touches morphometry/ or morphoview/; SchwingNet's open #416, #420 and #468 carry no morphometry code. So the rerun's code is the whole of the engine either way.

## The sacrum

The owner's rule of 2026-10-30 22:58 UTC is one full sacrum mask and no S1 class. The engine already holds to it: ENHANCE.PET's maps carry one sacrum label, VerSe's one, and screening's TotalSegmentator stacker writes both vertebrae_S1 and sacrum into VerSe's sacrum id, so the two are united. pelvis.py's "S1 plate" is the top face of that one mask, not a class. Nothing to change.

## Decision

Nothing the screens, the pull requests or the literature found is left unfixed in the engine except the disc readings at L4-L5 and T10 to T12, which no code change explains and which the age covariate tests. So the three jobs go as counted: `morphometry enhance` and `morphometry verse` on the engine of 9c85de1, then `morphometry covariates` once both report. After them: the old rows against the new, plotted per measure and level; #38's card scored again; #50's prior fitted on the new rows, and #59's phantoms drawn from it.
