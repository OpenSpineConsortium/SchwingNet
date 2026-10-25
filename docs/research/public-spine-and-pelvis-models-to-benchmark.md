# Public spine and pelvis X-ray models to benchmark against the record

Source: the thread "Compare lab's X-ray learning to SchwingNet", 2026-10-25, issue #283. It answers the owner's ask, with the uploaded PDF "Synthetic X-Ray Vertebrae Detection" (titled inside "Advanced Computational Frameworks for Vertebral Body Detection and 2D/3D Registration"), to "directly download public weights or reconstruct the training process and code and data and benchmark against any of these models/datasets which are relevant, particularly spine and pelvis models, draw any ideas from this document, and see if there are any similar findings in this theme". It follows [arcade-lab-x-ray-learning-against-schwingnet.md](arcade-lab-x-ray-learning-against-schwingnet.md), whose five benchmarks it makes concrete. Nothing here has been fetched or run. Every fetch and job below waits for the owner's word and count, and each fetch reads its exact size first under the size rule.

## 1. What can be fetched today

The models and data that the PDF names, with what was read on 2026-10-25. Hugging Face is closed to the cloud container, so the reads came from the model cards, the project pages and PyPI. The grid reads the exact sizes itself before any byte lands.

| Model or data | Who | What it gives | Where, size, licence | Relevance |
|---|---|---|---|---|
| FleXray weights | Butoi and others, MIT CSAIL, arXiv 2609.26756 | A 2D UNet with 60 structures plus background at 256 x 256. One channel per vertebra, C1 to C7, T1 to T12, L1 to L5 and the sacrum, plus the hips, the femurs and the ribs. Five members that differ only in their share of generatively edited DRRs (0, 0.25, 0.375 the flagship, 0.5, 0.75). | Hugging Face `VictorButoi/flexray`. Safetensors plus an fp16 ONNX export per member, with SHA-256 checksums in each member's folder. Size not stated. Weights CC-BY-NC-4.0, code MIT, `pip install flexray` (wheel 358,184 bytes, Python 3.10 or later). | The highest. It is the first open model that names a vertebral level from one real radiograph, so it is a direct comparison for the level stage. |
| FleXray data | the same | The training data, DRRs and edited DRRs. | `VictorButoi/flexray-data`; size not read | Only for rebuilding its training, which section 3 does not recommend |
| xvr models | Gopalakrishnan and others, MIT, arXiv 2503.16309 | Patient-specific pose regressors for 2D/3D registration, trained in minutes on renders of that patient's CT, then refined by a differentiable renderer | Hugging Face `eigenvivek/xvr`, 3.7 GB by the README; code MIT, installed from GitHub (not on PyPI) | Pelvis (DeepFluoro) and spine (Ljubljana), both held on the grid |
| xvr data | the same | DeepFluoro, the femur set and Ljubljana as xvr reads them, with fiducials | Hugging Face `eigenvivek/xvr-data`, 4.8 GB by the README; CC-BY-NC-ND-4.0 | For running xvr exactly as published. Our own copies of DeepFluoro and Ljubljana stay the truth. |
| DiffDRR | Gopalakrishnan, MIT | A differentiable renderer in PyTorch | PyPI `diffdrr` 0.6.1, wheel 34,805,004 bytes, MIT | A tool, not a benchmark. It is what xvr renders with. |
| DeepDRR | Unberath, Killeen and others, JHU | The physics renderer that SyntheX and FluoroSAM train on | PyPI `deepdrr` 1.2.2, GPL-3.0 | The renderer comparison of the earlier note's benchmark 5 |
| FluoroSAM weights | Killeen and others, JHU | Text-prompted segmentation | `fluorosam_weights_drive`, 1,002,351,026 bytes, already a fetch word in grid/run-platform-fetch.sh | Waits on #163: gdown has no size reader |
| The digital twin's frames | Killeen and others, arXiv 2412.08020 | 80 real cadaver frames, mid-femur to T2 | `ipcai2025_robotic_xray_drive`, 0.85 GB | Waits on #163 |

These are held already and need no fetch:

- DeepFluoro: 366 frames from 6 cadavers, at /rs/rs_grp_oschome/go2432/data/deepfluoro_h5 and deepfluoro_vendor (data/sources/deepfluoro.json).
- Ljubljana 2D-3D-GS: 18 frames of one cadaver, L1 to L5, with CT and pose, at /rs/rs_grp_oschome/go2432/data/ljubljana, read-only under its ND licence (data/sources/ljubljana_2d3d_gs.json).
- C-ArmLSpine: data/sources/carmlspine.json.

The PDF's other methods have no weights we could find, so they are left out:

- LXPose (Taylor and Francis, 10.1080/24699322.2026.2684372)
- XPos3R (arXiv 2609.10733)
- DIRN (arXiv 2210.07611)
- Spine-DART (arXiv 2512.05803)

None of them names a level. They would have to be rebuilt from their papers, and they measure pose, not level. That is Inferred from the abstracts and the PDF; their repositories were not searched one by one.

Licence: FleXray's weights are non-commercial, and xvr's data are non-commercial with no derivatives. Both go in data/licences.json as `non-commercial`. Both are benchmark rows only and never feed a SchwingNet network, which the provisional and any licence of it must stay clear of (tools/licences.py).

## 2. The benchmark, as jobs to count

The owner would be asked for three fetches and three GPU jobs. Each job writes RUN.json and a ledger row, gives each number its Wilson interval, and uses the test part of no SchwingNet split for choosing anything. The models run as published, with no tuning.

Fetches, as fetch words added to the owner's list in grid/run-platform-fetch.sh. The hf-token route already reads exact sizes before landing.

1. `hf_flexray_weights`: `--repo VictorButoi/flexray`, every member. Size unknown until the grid reads it; five UNets of this width are likely under 2 GB in all (Inferred).
2. `hf_xvr_models`: `--repo eigenvivek/xvr`, 3.7 GB reported.
3. `hf_xvr_data`: `--repo eigenvivek/xvr-data --repo-type dataset`, 4.8 GB reported.

About 10 GB in all, against a quota that had 12.6 TB free on 2026-10-22 before the queued fetches.

GPU jobs, each one Slurm job of class gpu through grid/hpcw.sh. Each runs in a throwaway environment holding `flexray` or xvr, apart from the pinned environments. That keeps the repository free of a new dependency, and the job's script, not the package, is what lands here.

1. FleXray zero-shot on C-ArmLSpine.
   - Inputs: the 617 lateral frames of A2.1 and the 631 AP frames of A2.2, flagship member and the ensemble.
   - Each truth box gets the level whose mask covers most of it, and a body with no mask over half of it counts as undetected.
   - Scoring is the reported stack's own: over detected bodies, and again with the undetected counted wrong (A2.6).
   - This is the measurement that settles section 6's contradiction. It tests whether a model trained on renders and real radiographs, asked for levels by channel rather than by prompt, names them from one frame as the reported stack does (96.4 percent lateral, 43.7 percent AP), or fails as FluoroSAM did on the twin (Dice 0.16 to 0.25).
2. FleXray on DeepFluoro, for the pelvis and femurs.
   - Its paper reports Dice 0.916 there against 0.866 for nnU-Net.
   - Reproducing that number shows our install runs the model as published, so a poor score in job 1 is the model's and not ours.
   - It is also the pelvis row the owner asked for.
3. xvr on DeepFluoro and Ljubljana.
   - The aim is to reproduce the median TRE: 1.1 mm on DeepFluoro and about 0.9 mm on Ljubljana, as the PDF tables it from the xvr paper.
   - Then project the CT's level labels through each recovered Ljubljana pose. That gives up to 90 level boxes of exact truth on real frames, the bank data/sources/ljubljana_2d3d_gs.json says has not been built.
   - That bank is the first real set where the level truth comes from geometry and not from a reader.

What the jobs would not do: train or fine-tune anything, fetch FleXray's training data, or score on SchwingNet's own held-out test part beyond C-ArmLSpine. C-ArmLSpine is already the reported stack's zero-shot set.

## 3. Download or rebuild

Download in each case where weights exist. Rebuilding FleXray's training would need its data (size unread) and its FLUX.2 editing pass. That is a large GPU spend to reproduce a model whose weights are published with checksums, and it answers no question that the published weights do not. Rebuilding is worth it only for a method with no weights that names a level. None of the PDF's methods does: LXPose, XPos3R, DIRN and Spine-DART measure pose or shape. FluoroSAM has weights, and they wait only on #163.

## 4. Ideas the PDF gives, set against this record

1. Masks per structure, not one label per pixel.
   - The PDF's third insight is that a projection overlaps structures, so a pixel can be L4 and a rib and the bowel at once. FleXray uses one sigmoid channel per structure for that reason.
   - The reported stack detects boxes and assigns a level per box, which already allows overlap. The idea matters for any segmentation head this project adds, and for the prior head of #228, whose projected level map should be multi-label where bodies overlap in AP (Inferred).
2. A model per patient beside the general one.
   - xvr trains on one patient's own CT renders in minutes and reaches millimetres where general models do not.
   - Where a preoperative CT exists, a level map projected from it at a recovered pose gives the levels by geometry. That is the counting prior's strongest form (docs/research/xr-from-3d/), and job 3 measures it on real frames.
3. Generative editing of DRRs.
   - FleXray's FluXray share is a measured knob. The paper ships five members from 0 to 0.75, so its effect on our frames can be read by running all five in job 1, at no training cost.
   - That is a free ablation of the question the calibrated renderer asks of realism (docs/research/drr-realism-against-our-results.md).
4. Rare pathology made in simulation.
   - The PDF cites the vertebroplasty policy (arXiv 2511.03882), tested on unseen CTs with fractures.
   - This project's synthetic anomaly arm (docs/project.md, Scope) has the same purpose, and keeps it apart from the real arm, as this project requires.
5. Metrics.
   - The PDF's mTRE and mean projection distance are registration measures. A level's own measure stays the level named per body, with intervals.
   - Job 3 reports both, so a pose error can be read as a level error. As a rough guide, an error of about one vertebral height, some 25 to 35 mm in the lumbar spine, is a wrong level (Inferred from typical anatomy).

## 5. Findings like ours

- FleXray, outside the JHU lab, beats FluoroSAM on held-out real spine radiographs. Its Cobb-angle MAE on AASCE is 5.13 degrees against 31.8 for FluoroSAM, and the Cobb angle is computed from each vertebra's mask. That points toward this record, not the twin's reading: one radiograph carries enough to tell vertebrae apart when the model is asked per vertebra (Published, FleXray's project page). AASCE is coronal full-spine radiography, not lateral fluoroscopy, so job 1 is still needed.
- FleXray's finding that a share of real radiographs and edited DRRs beats DRRs alone matches the earlier note's finding that the lab reaches parity only with real-like rendering plus heavy randomisation. It also matches this record's encoder, whose only intraoperative appearance came from renders (Reported).
- xvr's patient-specific results agree with the counting argument of section 6 of the earlier note. Level identity comes cheaply from geometry once there is an anchor. The twin's prompt had none.

## 6. Errors in the PDF, to keep out of anything that cites it

- DiffDRR and xvr are Vivek Gopalakrishnan's, at MIT with Golland and Dalca. They are not Unberath's or Killeen's, and "Vivek and colleagues" uses his given name as a surname.
- FleXray is MIT CSAIL's (Butoi and others), not the JHU lab's.
- The PDF's FleXray few-shot figure is "1 percent, 13 real cases, AP50 of 5 percent". FleXray's own page gives two different figures:
  - Dice 0.898 against 0.869 with 1 percent of MTDDH;
  - AP50 23.2 percent against 7.4 percent with 10 percent of BTXRD.
  
  The PDF's figure matches neither.
- The PDF calls Ljubljana an rDSA set. Ljubljana's group has two 2D/3D sets: the cerebral angiography one, and the spine 2D-3D-GS this repository holds. The PDF's metric table does not say which one its xvr row is.
- "Definitively solved the data bottleneck" and "true zero-shot Sim2Real generalization" overstate the record. The twin's own Table 1 gives Dice 0.16 to 0.25 per lumbar level on real frames, and FleXray finds FluoroSAM's Cobb error near 32 degrees off its own benchmark.

## 7. What was read

Read on 2026-10-25:

- FleXray's model card on Hugging Face, its project page flexray.csail.mit.edu and its GitHub README;
- xvr's GitHub README and one file page of xvr-data;
- PyPI's records for flexray, diffdrr and deepdrr (xvr is not on PyPI);
- the uploaded PDF in full;
- this repository's data/sources records for DeepFluoro, Ljubljana and C-ArmLSpine, and grid/run-platform-fetch.sh.

Not read:

- the exact file sizes on Hugging Face, which is closed to the container;
- FleXray's MODEL_ZOO.md and label_names.json;
- LXPose's, XPos3R's and Spine-DART's repositories.
