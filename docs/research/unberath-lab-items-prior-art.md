# Seven Johns Hopkins (Unberath lab) items read against SchwingNet's two parts

Source: the thread "Compare SchwingNet against related work and patents", 2026-10-24, on the owner's
question of 2026-10-24 02:54 UTC ("thoughts on this? ... or this paper vs what im doing?") with seven
links. Read on 2026-10-24 from the sources in section 5. Confidential with the rest of this
repository: it says where the provisional's claims can and cannot rest, so nothing of it leaves
before the provisional is filed (30 October). Grades as in docs/research/xr-from-3d/README.md
section 3: Measured is this project's record, Published is shown in the source named, Inferred is
reasoned here. This is a factor list for patent counsel, not an opinion on patentability, validity
or infringement; what is cited and what is claimed are counsel's.

SchwingNet as the disclosure defines it: Part A, a segmenter-agnostic classifier that takes any CT
segmenter's output, discards its level names and flags transitional anatomy (L6, sacralised L5, T13)
from name-free features; Part B, a network that names vertebral levels from a single intraoperative
C-arm exposure with no registration to a preoperative scan, with, in the Fishman draft, chaining
overlapping C-arm images and commanding the next shot. The draft's claims themselves were not read
here (they are outside the repositories); where a factor turns on their wording it says so.

## 1. The finding in brief

- All seven come from one group: every item has Mathias Unberath (Johns Hopkins, ARCADE lab) as an
  author or inventor (Published, each source's author list).
- One family matters for the provisional: US 12,268,533 B2, a granted Johns Hopkins patent whose
  claim 1 covers taking an X-ray at a pose, predicting the quality of possible next X-rays, picking
  the best and causing the device to move there. It is prior art to, and a possible freedom-to-operate
  question for, any claim on commanding the next shot (section 3), and so is its narrower parent,
  US 11,992,348 B2, also granted. Their claims, not their abstracts, decide this.
- The read covered these seven items, plus what an adversarial review of this note found outside
  them. Two of those outside finds matter more than any of the seven but the patent family: Kausch et
  al. 2020, a CNN that chooses the next C-arm pose from one X-ray of the lumbar spine with no CT
  (section 3), and VERIDAH (Moeller et al., arXiv 2601.14066, January 2026), which labels vertebrae on
  CT and MRI with eleven or thirteen thoracic and four or six lumbar vertebrae, that is T13 and L6
  (section 4).
- None of the seven names vertebral levels, from one image or otherwise, and none touches transitional
  anatomy, so none of the seven reaches Part A or Part B's naming as such (Published, abstracts and the
  sections read; the two Springer full texts were not read). That says nothing of the field: the
  Fishman draft's note "No surveyed method addresses transitional spines at all" is contradicted by
  VERIDAH and by Kwak et al. 2025 (section 4) and should come out of the claims, as already asked, and
  not be repeated as a statement of fact.

## 2. Item by item

| Item | What it does | Part A | Part B | Risk for the provisional |
| --- | --- | --- | --- | --- |
| github.com/arcadelab/VertebralDiffusion | ten commits (2025-03-04 to 2025-03-20, author Rapuris; docs/research/vertebral-diffusion.md) of an unconditional 3D VQ-GAN plus DDPM generating 128^3 per-vertebra CT crops from NMDID; no paper, licence, weights or results (Published, read on 2026-10-22, benchmarks-to-beat.md section 8) | no classifier, no transitional anatomy | no X-ray, no naming | low; only against a claim on generating synthetic vertebrae or rare anatomy in 3D for training, where a public repository can count as a printed publication; its date is the commit's |
| arXiv 2610.28410 (Shen ... Unberath, 2026-10-20), MedicalMLOmni | a multi-agent AutoML framework that plans model training for medical imaging tasks from a natural-language request (Published, abstract via OpenAlex) | no | no | none for Parts A and B; it is closer to how SchwingNet is built (Symphony's agents) than to what SchwingNet claims, and the provisional does not claim the workflow (Inferred) |
| US 12,268,533 B2 (Johns Hopkins; Unberath, Zaech; priority 2019-09-05; granted 2025-04-08), continuation of US 11,992,348 B2 (granted 2024-05-28) | from one X-ray at a 6-DoF pose, predict the quality of next possible X-rays, pick the best, update the pose and move the device; the embodiment is C-arm cone-beam CT checking pedicle screws in spinal fusion, with a detectability index from local MTF, NPS and a task function (Published, claims 1 to 20 read from the granted PDF) | no | yes, for the next-shot element only; nothing on naming, counting or chaining | the one to put in front of counsel (section 3) |
| Cho, Taylor, Unberath, MICCAI 2026, LNCS 16889 pp. 110-118 (online 2026-09-25), "Human-AI Collaboration for 2D/3D Registration Quality Assurance" | a user study (N = 18): people judging 2D/3D registration quality alone, with AI and with explainable AI; both aided arms better than people alone (Published, abstract; full text paywalled, not read) | no | no; it is about the registration Part B does without | none on the abstract (full text not read); useful background that registration needs its own quality check, which supports why Part B's no-registration route matters (Inferred) |
| arXiv 2606.21414 (Rapuri, Ko, Killeen, Taylor, Unberath, 2026-06-19), "2D Versus 3D Diffusion for In Silico Training of Interventional X-ray AI Models" | synthetic X-rays from a 3D latent diffusion CT generator (then DRRs) or a 2D diffusion model conditioned on projected segmentations, to train pelvis landmark detection; tested on DeepFluoro's 366 real cadaver images, 6-fold (Published, HTML v1) | no | no naming; only training data | low; prior art only against a claim on training a fluoroscopy network on diffusion-generated or rendered X-rays, which DeepDRR and FluoroSAM already cover (fluoroscopy-list-prior-art.md, benchmarks-to-beat.md) |
| US 2025/0312119 A1 (Arthrex and Johns Hopkins; priority 2024-04-09; pending) | bone-cement fiducials that glow in near infrared, tracked by a visible plus NIR camera to locate anatomy or tools; shoulder embodiment (Published, claims 1, 15 and 21 summarised from Google Patents) | no | no; no X-ray at all | none |
| Cho, Do, Grupp, Armand, Taylor, Unberath, IJCARS 20(7):1521-1529, 2025 (online 2025-06-08) | uncertainty of single-view 2D/3D registration from posterior sampling, against its error, in simulated pelvis registrations (Published, abstract; full text paywalled, not read) | no | no; registration again | none on the abstract (full text not read); same background point as the MICCAI chapter |

## 3. US 12,268,533 B2 and the next-shot element

What its claims say (Published, the granted PDF, columns 16 to 19):

- Claim 1 (method), claim 8 (system) and claim 15 (medium) each recite: receive an X-ray image
  captured by a device at a position defined by a six-degree-of-freedom pose relative to an anatomy;
  process it to determine a predicted quality of next possible X-ray images; identify the one with the
  greatest predicted quality; update the 6-DoF pose from it; and cause the device to adjust to the new
  position.
- The continuation is broader than its parent. US 11,992,348's claim 1 requires a "C-arm cone-beam
  computed tomography (CBCT) device" and a "machine learning model"; US 12,268,533's independent
  claims say only "a device" and "processing ... the X-ray image", with neither word. The C-arm, the
  spine and the detectability index come back only in dependent claims (3, 4 to 7, 10 to 14, 17 to
  20).

Factors for counsel:

- As prior art: the family's publications (the parent's US 2022/0323025 A1 and the PCT application
  PCT/US2020/070500, filed 2020-09-04; '533's own pre-grant publication, which the adversarial review
  read on Google Patents as US 2024/0293090 A1 of 2024-09-05, a number to confirm) disclose a learned model reading one intraoperative X-ray and choosing and
  commanding the next C-arm pose, in spine surgery. An independent claim that adds "and command the
  next exposure" to Part B's naming would likely be argued obvious over Part B's naming plus this
  (Inferred). The next-shot element is better as a dependent claim, or tied to what only SchwingNet
  does: a next shot chosen from the named levels, such as the translation that keeps a named level in
  overlap while reaching the target level (Inferred; the draft's wording decides).
- Choosing the next C-arm pose from the anatomy in one X-ray, with no CT, is itself published:
  Kausch L, Thomas S, Kunze H, Privalov M, Vetter SY, Franke J, Mahnken AH, Maier-Hein L, Maier-Hein K,
  "Toward automatic C-arm positioning for standard projections in orthopedic surgery", IJCARS
  15(7):1095-1105, 2020-06-12, doi 10.1007/s11548-020-02204-0: a CNN trained on projections simulated
  from CT predicts pose updates from a single initial X-ray, with no patient-specific prior scan or
  registration equipment, applied iteratively, evaluated on the lumbar spine and the proximal femur
  (Published, abstract via OpenAlex). So "single image, no registration" is not new for positioning,
  and the next-shot element's distinction narrows to choosing the shot from named levels, overlap
  with the previous image and the distance to the target level (Inferred).
- What differs from '533: it scores views by predicted image quality for a fixed object
  (detectability of a screw); SchwingNet's next shot is chosen by anatomical coverage and identity
  (which level is where, how far to the target). '533 says nothing about naming, counting, transitional anatomy or chaining
  overlapping images (Published, by absence in the claims and the implementations listed in column
  15).
- As freedom to operate: both patents are granted and in force; the parent is narrower (a C-arm CBCT
  device and a machine learning model), but its last step, providing the C-arm data that causes it to
  adjust, reads on sending a pose to a motorised C-arm (Inferred from its claim 1). Its claim 1 does not limit "predicted
  quality" to image quality, so whether a SchwingNet product that picks a next C-arm pose by any score
  of candidate views and moves the device (or tells a robot to) falls inside it is a claim
  construction question for counsel, not settled here. A product that only shows the surgeon a
  suggestion, and never causes the device to move, may avoid the last step of claim 1, but a "go to"
  button on a motorised C-arm or a robot, or a pose sent to the C-arm's controller, may count, and
  divided and induced infringement are counsel's questions; display-only is not a safe harbour
  (Inferred from the claim's wording).
- Family: '533 (application 18/659,587) is itself the continuation of '348 (17/634,597); counsel can
  check the continuity data of 18/659,587 in Patent Center for any child still pending.

## 4. "No surveyed method addresses transitional spines at all"

- Against the seven items: it holds; none mentions L6, T13, sacralisation, lumbarisation or variant
  counts (Published, by absence in the abstracts and sections read; the two Springer items' full texts
  were not read).
- Against the wider literature, it does not, and the note should not be relied on as a statement of
  fact:
  - Kwak, Ro and Kang, "Automated Detection of Lumbosacral Transitional Vertebrae on Plain Lumbar
    Radiographs Using a Deep Learning Model", J Clin Med 2025;14(21):7671 (2025-10-29): a ResNet-50
    classifying LSTV present or absent on standing lateral radiographs, AUC 0.84 on 313 test images;
    no counting and no Castellvi type (Published, the MDPI page). It is diagnostic plain film, not
    intraoperative naming and not a name-free CT classifier, but it does address transitional spines.
  - VERIDAH: Moeller H, Schoen H, Graf R, Atad M, Molinier N, Sekuboyina A, ... Rueckert D, Kirschke
    JS, "VERIDAH: Solving Enumeration Anomaly Aware Vertebra Labeling across Imaging Sequences", arXiv
    2601.14066, 2026-01-20: multiple classification heads and a weighted sequence prediction label
    vertebrae on sagittal T2 MRI and CT with eleven or thirteen thoracic and four or six lumbar
    vertebrae; on CT 96.30 % of thoracic and 97.22 % of lumbar enumeration anomalies are found, 99.18 %
    of subjects fully correct; code and models public (Published, the arXiv abstract). The
    adversarial review read in its HTML that it takes vertebral centroids from an upstream localiser or
    segmenter, saying public models can localise through segmentation (to confirm in the paper). It
    predates Part A's conception (24 to 25 September 2026) and is the closest prior art to Part A this
    read found.
  - VerSe 2019 and 2020 (Sekuboyina et al.) label L6 and T13 where present, and the CT labellers
    trained on it emit those labels (Published in VerSe's papers; benchmarks-to-beat.md's VerSe row).
    That bears on Part A: a CT labeller that outputs an L6 label flags a transitional spine, though by
    naming, which is what Part A discards (Inferred).
- What survives, as far as this read goes: no item found names levels on a single intraoperative
  C-arm image with the transitional column taken into account. For Part A, what survives is narrow: a
  classifier that discards the upstream segmenter's level names and flags the transitional column
  from name-free features. VERIDAH takes an upstream source's vertebra locations, which carry no
  names, and enumerates anomalies from them, so counsel should read whether it already discloses
  that, and how Part A's features and output differ (a flag on the column, against a full labelling)
  (Inferred; a search, not a proof). The
  closer prior art for Part B's naming without CT remains CM Spine (Zeng et al. 2024) and Huang 2022
  (fluoroscopy-list-prior-art.md section 3), neither of which handles transitional spines as far as
  was read there.

## 5. Read

- Google Patents pages for US 12,268,533 B2, US 11,992,348 B2 and US 2025/0312119 A1 (metadata and
  claims through WebFetch); the claims of the two granted patents from their PDFs on
  patentimages.storage.googleapis.com, read page by page as images. US 2025/0312119's claims are a
  summary, not the text.
- arXiv 2606.21414 (abstract and HTML v1); arXiv 2610.28410 through OpenAlex (arxiv.org rate-limited
  its page); the Springer pages of the MICCAI 2026 chapter (doi 10.1007/978-3-032-38186-6_11) and the
  IJCARS article (doi 10.1007/s11548-025-03417-x), abstract and metadata only.
- The MDPI page of Kwak et al. 2025 (PMC's copy answered with a browser check); the OpenAlex record of
  Kausch et al. 2020; the arXiv abstract of VERIDAH (2601.14066).
- An adversarial review of this note by a second reader the same day, which checked the claims
  against the PDFs, found the parent patent's freedom-to-operate point, the display-only overstatement,
  the continuation's application number, the unread full texts and the two outside items; each is
  folded in above.
- This repository: benchmarks-to-beat.md section 8, fluoroscopy-list-prior-art.md, docs/project.md;
  the drafting note's wording from the ip-review files of the project's shared folder.

Not read: the Fishman draft's claims; the two Springer full texts; any continuation of US 12,268,533
still pending.
