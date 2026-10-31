# Conception timeline: vertebral level from limited-field projection images

Prepared 2026-10-31 for Gregory J. Schwing's own counsel, from the git history of his repositories. Confidential. Not legal advice; facts and their sources only.

Subject: U.S. provisional 64/188,238 (WSU Tech ID 26-1901, docket 66174-0372), filed about 2026-10-30 by Fishman Stewart PLLC for Wayne State University as applicant-assignee, sole inventor Gregory John Schwing, with a government-interest statement naming NIH F30 5F30GM147909.

## What the claims cover

All 26 claims are the overlapping-sweep method: overlapping limited-field exposures linked by image content, consecutive naming anchored on a landmark, a confidence from the lowest probability and a link margin, and, when the confidence fails, a commanded displacement in millimetres derived from the patient's own vertebral spacing. The CT transitional-anatomy classifier appears in the description only, not in the claims.

## Timeline

Source key: S = Gregory-Schwing-MD-PhD/spinesurg-ct-nnunet (private), branch L6_Class, commit hash and committer timestamp (EDT). P = OpenSpineConsortium/spine-program (private), a copy of his records.

| Date | Event | Source |
|---|---|---|
| 2026-04-18 | spinesurg-ct-nnunet first commit; the CT lumbosacral-transitional segmentation work (nnU-Net), 17 commits before June | S 5ec2f61 |
| 2026-05-26 | Hugging Face Space gregoryschwingmdphd/CTSpinoPelvic1K-review created (app.py, carm.py, viewport.py), public until 2026-09-18 | S docs/DISCLOSURE_MEMO.md section 2 |
| 2026-05-31 | NIH F30 5F30GM147909 ended | S docs/RESUME_2026-09-22_PM.md line 397 |
| (date to supply) | Graduation (MD) | not in the repositories |
| 2026-06-30 | WSU Libraries stop serving DMC/Tenet-sponsored residents (implies DMC/Tenet residency status) | P 01_carm_level_detection/docs/handoff/context/wsu-library-access-cutoff.md |
| 2026-08-22 | Convention-free label scheme (the naming decoder's basis) | S 817fc1a |
| 2026-09-13 | FluoroCap: single-image level naming on published fluoroscopy figures | S cc59e71 |
| 2026-09-14 | spinesurg-ct-nnunet switched to private at his request | P 01_carm_level_detection/memory/fluorocap-repo-private.md |
| 2026-09-15 | level_prototype.py: single image in, every vertebra named | S fd2976b |
| 2026-09-17 | External essay Feasibility_FOV says single limited-field naming is ill-posed (author not stated) | P docs/external_reports/README.md |
| 2026-09-17 22:11 | First record of the claimed invention: tools/sweep_map.py, "a virtual full-spine map from overlapping frames", linking restricted to the commanded step | S 6984446 |
| 2026-09-17 22:15 | Sweep protocol document; the word margin first appears | S fdccbb6 |
| 2026-09-18 | External report MULTI_XR, "Deep Serial Fluoroscopic Mapping" (author not stated) | P docs/external_reports/README.md |
| 2026-09-18 16:52 | Public Hugging Face Spaces found open and closed; the exposure recorded element by element. The sweep aspects (A, B, D, E) were absent from the exposed text. | S 345c187; DISCLOSURE_MEMO.md section 3 |
| 2026-09-18 16:57 | Technical invention disclosure and confidential counsel memorandum written | S df26da0 |
| 2026-09-18 21:52 | "The loop closes: a commanded displacement in millimetres, and a mark that stays on the bone" | S 76fc1d1 |
| 2026-09-18 22:08 | Guided acquisition loop documented, with console | S 06d28fd |
| 2026-09-19 | End rule for the sweep; fiducial_walk.py (persistent digital marker), needle_confirm.py | S 8aac5b7, 7dc6f70, bd0eee2 |
| 2026-09-20 | link_probe.py (link margin probe) | S ab903a4 |
| 2026-09-22 | WSU Technology Commercialization asks for the disclosure form; it is filled with funding = Yes (NIH F30), external affiliation DMC/Tenet = Yes, and a "DMC IP clause" left to confirm. His recorded statement: the work began at the end of his M4 year under NIH support. | S docs/RESUME_2026-09-22_PM.md line 397 |
| 2026-09-25 | Disclosure submitted (title names Part A, the CT flag, and Part B, single-exposure C-arm naming). The office asked for inventor, Chair and Dean signatures. An MOU was left unsigned pending clarification. | P 01_carm_level_detection/docs/handoff/MANUSCRIPTS.md section 15 |
| 2026-10-30 | Provisional filed; WSU as applicant-assignee; F30 named | ADS and cover sheet |

## Points for counsel

1. Every claimed element is first recorded 2026-09-17 to 2026-09-20, three and a half months after the F30 ended. No record before 2026-09-17 shows the overlapping sweep.
2. The broader programme began during the F30, and his own 2026-09-22 statement and the disclosure form say so. The CT work (April to May) and the single-image naming feed the description. The claims are the sweep.
3. All the computing ran on the WSU grid under his AccessID. The commits carry his med.wayne.edu address. Check the terms of the grid or guest account.
4. The disclosure form answers "external affiliation DMC/Tenet = Yes" and names a DMC IP clause. A residency agreement with Tenet/DMC may make its own claim and needs reading.
5. Documents to get: the signed disclosure form (the copy he signed, in particular any page-8 acknowledgement), the unsigned MOU, the grid or guest-account terms, the Tenet/DMC residency agreement, and the WSU IP policy in force.
6. Earlier public surfaces (the Hugging Face Spaces, CNS abstracts, AACA, NeurIPS, Zenodo, arXiv) and the GitHub purge list are recorded in S docs/DISCLOSURE_MEMO.md and docs/disclosure_forensics.json.
