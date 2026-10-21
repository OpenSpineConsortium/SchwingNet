# Request texts for the gated X-ray sets

Source: the thread "SchwingNet video demo plan", 2026-10-21, the owner's ask of 04:04 UTC. Written
by a research subagent in a cloud session from docs/research/xray-datasets-missing.md (read whole),
docs/research/data-access-requirements.md (who may act on what), spine-program's
01_carm_level_detection/docs/data_requests/FLUORO_VIDEO_REQUESTS_READY_2026-09-26.md (the voice of
the earlier letters) and data/sources/radiopaedia.json (how a non-commercial attestation is
recorded). Every portal named below was fetched on 2026-10-21 and every host answered ENOTFOUND
from this container (mrosonline.ucsf.edu, sofonline.ucsf.edu, bimcv.cipf.es,
hirl.daffodilvarsity.edu.bd, huggingface.co, stanfordaimi.azurewebsites.net; physionet.org and
arxiv.org are blocked by name), so no form field below was read from its page: the fields are what
such portals usually ask, marked "to confirm on the page", and the owner reads the real form before
pasting. Nothing here was sent.

## Rules every text follows

- Short and direct. The opening line is "I study the application of computer science to improving
  spinal health, and my current work needs ...", finished for each set.
- The affiliation is the Department of General Surgery, Wayne State University School of Medicine
  and the Detroit Medical Center, Detroit, Michigan, USA; never Neurosurgery.
- No text says or implies that a neural network, a model, machine learning, deep learning, AI or
  training is built or used (patent confidentiality). The work is described only as measuring and
  improving how reliably automated image-analysis methods recognise spinal anatomy (which vertebra
  is which, transitional variants included, the variants behind wrong-level errors) across
  modalities, devices and exposures, with results reported as per-image agreement with expert
  labels and confidence intervals. Before pasting, read each text once more for the banned words;
  the 2026-09-26 letters said "neural network" and "train", and nothing of theirs is reused here.
- De-identified imaging only, under Wayne State University's IRB determination HPR 2026-269, with
  HPR 2026-330 the supplement that covers PhysioNet's VinDr-SpineXR.
- The images stay on Wayne State's research computing storage, read only by the owner, never
  redistributed, deleted at the end of the project if the source asks.
- The owner signs any DUA, credits the source and quotes its agreement ID in any publication.
- The subject tag of any email is "[XR/CT Imaging Research]".
- Anything binding (a DUA signature, a fee, a credentialing attestation, a licence checkbox) is the
  owner's hand only; a session drafts text and nothing more.

The sender block used in every email:

```text
Gregory J. Schwing, MD, PhD
Department of General Surgery
Wayne State University School of Medicine / Detroit Medical Center
Detroit, Michigan, USA
go2432@wayne.edu
+1 504-994-0403
```

## Shared text blocks

The portals ask the same things under different labels, so the blocks are written once and each
section says which to paste where.

Project title (one line):

```text
Reliability of automated recognition of vertebral levels on spine radiographs across devices, exposures and anatomical variants
```

Lay summary or aims (the general form; MrOS and SOF have their own below):

```text
Wrong-level spine surgery happens when an image is read and the wrong vertebra is named, most often where the anatomy is transitional (a sixth lumbar vertebra, a sacralised L5, an eleventh or thirteenth rib pair) or the image is degraded. My current work measures, and sets out to improve, how reliably automated image-analysis methods recognise which vertebra is which on radiographs and fluoroscopy, and whether that reliability holds across modalities, imaging devices, exposure settings and anatomical variants. Each image is scored against expert labels and the results are reported as per-image agreement with confidence intervals, by device and by variant. The requested images add devices, exposure recipes and patient populations that the sets already held do not cover.
```

Data security and handling (every form that asks):

```text
The images will be stored on Wayne State University's research computing storage, which is access-controlled and backed up, in a directory readable by me alone. They will not be copied to a laptop, a cloud service or any third party, will not be redistributed, re-identified or linked to any other data about the same people, and will be deleted at the end of the project if the data provider asks. Only de-identified data are requested.
```

IRB status (every form that asks):

```text
Wayne State University's IRB has determined that this work on de-identified imaging is not human-subjects research (HPR 2026-269; supplement HPR 2026-330 for data obtained under PhysioNet agreements). The determination letters can be supplied.
```

Analysis plan (every form that asks; one paragraph):

```text
For each image the vertebrae in field are identified by an automated method and compared with expert labels at the level of each vertebra. The outputs are per-image agreement rates with 95 percent confidence intervals, stratified by imaging device, exposure, projection, patient age group and anatomical variant, and a table of the disagreements by cause. No clinical outcome is studied and no finding about any individual is produced.
```

Credit and publication (where a form asks how the source will be acknowledged):

```text
Any publication will credit the data source by name, cite its paper and quote the agreement or licence identifier under which the images were obtained, and will follow the source's publication rules.
```

## 1. MrOS lateral spine radiographs (UCSF)

Page to open: https://mrosonline.ucsf.edu/ (to confirm; the sweep names it as the study's data
request portal). MrOS Online is run by the San Francisco Coordinating Center; the images are not on
dbGaP, whose phs000373 holds genotypes. Expect an account to create first, then a "proposal" or
"analysis request" form; some cohort portals also ask for a short CV. To confirm on the page.

Fields the form is likely to ask, and the text for each:

- Proposal title: the shared title above, or the MrOS-specific one:

```text
Vertebral-level recognition on lateral spine radiographs of older men: reliability of automated identification across six clinical sites and two visits
```

- Background and aims:

```text
I study the application of computer science to improving spinal health, and my current work needs lateral thoracic and lumbar radiographs of older men in which each vertebra has already been named and graded by an expert. Wrong-level errors in spine care arise where the vertebra counted on an image is not the vertebra it was taken for, and they are commonest exactly where MrOS films are richest: osteoporotic spines with compression fractures, kyphosis and degenerative change, which is the anatomy an operating-room C-arm shows during vertebral augmentation and fixation. The Genant semi-quantitative grades of MrOS sit on named levels, so each film carries a per-vertebra level truth of a kind no other public radiograph set of this size has. The aim is to measure how reliably automated image-analysis methods recognise which vertebra is which on these films, across the six sites' devices and the two visits, and how the reliability changes with fracture grade, and to report per-image agreement with the expert labels and confidence intervals by site, visit and grade.
```

- Data requested (name the files, not the outcomes):

```text
The lateral thoracic and lumbar spine radiograph images from the baseline visit and the second spine-film visit, in the original or highest available resolution (DICOM where it exists); the vertebral-level reading tables for those films (the Genant semi-quantitative grade and any prevalent or incident fracture flag per vertebra, with the vertebra's name and any note of non-evaluable levels or transitional anatomy); and the image metadata (site, visit, acquisition date or interval, device or film type, and pixel spacing or calibration). No clinical outcome, questionnaire, laboratory, DXA or genotype variable is requested; a participant key is needed only to join the films to the reading tables and to keep the same man's two visits together.
```

- Analysis plan: the shared block.
- IRB status: the shared block.
- Data security: the shared block.
- Publication and acknowledgement: the shared block, plus the sentence "I will follow MrOS's
  publication and authorship policy and submit any manuscript for the required review."
- Funding: "No external funding; departmental support." (to confirm what the form wants.)

Binding, the owner's hand only: the MrOS data use agreement (an institutional signature is usual
for cohort data; Wayne State's sponsored programs office may have to countersign), any fee the
portal names (none is known; to confirm on the page), and the account itself.

What to expect back: a review by the MrOS publications or data committee, typically weeks; a
signed agreement; then a download link or a shipped drive for the images, since the film set is
large, and the reading tables as CSV with a data dictionary. Some cohort portals grant tabular data
through the site and ask for a separate request for images; if so, send the data-requested text
above as the image request.

## 2. SOF lateral spine radiographs (UCSF)

Page to open: https://sofonline.ucsf.edu/ (to confirm). The same coordinating centre as MrOS, so
expect the same shape of account, proposal form and agreement. To confirm on the page.

Fields and text: the same as MrOS with the cohort swapped. The aims paragraph:

```text
I study the application of computer science to improving spinal health, and my current work needs lateral thoracolumbar radiographs of older women in which each vertebra has already been named and graded by an expert. Wrong-level errors in spine care arise where the vertebra counted on an image is not the vertebra it was taken for, and they are commonest in osteoporotic spines with compression fractures, kyphosis and degenerative change, the anatomy an operating-room C-arm shows during vertebral augmentation and fixation; SOF's films, graded per vertebra on the Genant semi-quantitative scale over several visits, are the largest such resource for women. The aim is to measure how reliably automated image-analysis methods recognise which vertebra is which on these films across the study's sites, devices and visits, how the reliability changes with fracture grade and with the years between visits, and to report per-image agreement with the expert labels and confidence intervals by site, visit and grade. Together with the MrOS films, requested in parallel, the two cohorts cover both sexes on the same grading scale.
```

Data requested:

```text
The lateral thoracic and lumbar spine radiograph images from every visit at which spine films were taken, in the original or highest available resolution; the vertebral-level reading tables for those films (the Genant grade and any prevalent or incident fracture flag per named vertebra, with notes of non-evaluable levels or transitional anatomy); and the image metadata (site, visit, acquisition interval, device or film type, pixel spacing or calibration). No clinical outcome, questionnaire, laboratory, DXA or genotype variable is requested; a participant key only to join films to readings and to keep one woman's visits together.
```

Title: as MrOS with "older women" and "several visits". Analysis plan, IRB, security,
publication: the shared blocks.

Binding, the owner's hand only: the SOF data use agreement and any fee; to confirm on the page.

What to expect back: as MrOS. If the two portals share one account, say in each proposal that the
other is filed, so the committee reads them together.

## 3. Aariz cephalometric benchmark (by request to the authors)

Page to open: https://arxiv.org/abs/2302.07797 (Khalid, Fraz et al., "Aariz: a benchmark dataset
for automatic cephalometric landmark detection and CVM stage classification"); the paper's data
availability line names the request route, likely a Google form or an email to the corresponding
author at NUST (Muhammad Moazam Fraz) or Riphah International University. To confirm in the paper's
PDF, which this container cannot open; the CEPHA29 challenge page (ISBI 2023) may carry a form of
its own.

Route: email, unless the paper gives a form. Subject:

```text
[XR/CT Imaging Research] Request for the Aariz cephalogram dataset (1,000 films, 7 devices)
```

Body:

```text
Dear Professor Fraz and colleagues,

I study the application of computer science to improving spinal health, and my current work needs lateral films of the upper cervical spine from several devices and from children and adolescents, which no spine-specific public set provides. Your Aariz benchmark (arXiv:2302.07797; the CEPHA29 challenge) gives 1,000 lateral cephalograms from seven devices with a cervical vertebral maturation stage per film, and C2 to C4 lie in every image.

My work measures how reliably automated image-analysis methods recognise which vertebra is which, across modalities, devices and exposures, including the transitional variants that cause wrong-level errors in spine care. On your films the question is the top of the cervical count: whether C2, C3 and C4 are identified consistently across seven devices and across the maturation stages, reported as per-image agreement with expert labels and confidence intervals, by device and by stage.

I am writing to ask for the 1,000 cephalograms with the landmark and CVM annotations and the per-image device labels, under whatever research agreement you use. I am at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center. The images would be held on Wayne State's research computing storage, read by me alone, never redistributed, and deleted at the end of the project if you ask. The work is on de-identified imaging under a Wayne State IRB determination (HPR 2026-269). I will sign your agreement, cite the paper and the challenge, and quote the agreement in any publication.

With thanks,
```

followed by the sender block. Binding, the owner's hand only: the authors' agreement or a form's
checkbox, if any. Fee: none expected. What to expect back: an agreement to sign or a link; the
ISBI 2015 set (400 films, 19 landmarks) can be fetched openly meanwhile.

## 4. ReXGradient-160K (Hugging Face, gated)

Page to open: https://huggingface.co/datasets/rajpurkarlab/ReXGradient-160K, signed in to the
owner's Hugging Face account; the gate form sits above the file list.

Fields the gate is likely to ask (to confirm on the page): full name, affiliation and institutional
email, intended use (a text box), and a checkbox accepting the non-commercial data access and use
agreement; some gates add country and a "I agree not to redistribute" line. Text for the use box:

```text
I study the application of computer science to improving spinal health, and my current work needs chest radiographs from many sites, since a lateral chest film is a lateral thoracic spine from T1 to about L1 and a frontal film shows the thoracic spine behind the mediastinum. The work measures how reliably automated image-analysis methods recognise which vertebra is which across devices and exposure settings, reported as per-image agreement with expert labels and confidence intervals, by site. The 79 sites of ReXGradient-160K are the widest exposure coverage of any chest set. Non-commercial academic research at the Department of General Surgery, Wayne State University School of Medicine, on de-identified images under IRB determination HPR 2026-269; the images stay on Wayne State's research computing storage, read by me alone, and are not redistributed. The source and its agreement will be credited in any publication.
```

Binding, the owner's hand only: the agreement checkbox, which binds the person who ticks it. Read
the agreement's clauses on models, derivatives and outputs before ticking anything, as the
Radiopaedia record (data/sources/radiopaedia.json) records that same question for its licence;
whether such a clause touches this project is a question for the owner's lawyer, not for a session.
Fee: none. What to expect back: an instant or a reviewed approval (the Rajpurkar lab gates have
been reviewed by hand, days); then `huggingface-cli download` with the owner's token in a file on
the grid, as a job on the owner's word. Whether the studies include lateral views is read from the
metadata once approved.

## 5. PadChest (BIMCV, Alicante)

Page to open: https://bimcv.cipf.es/bimcv-projects/padchest/ ; the "Download" or "Request" link
there leads to a licence form (a web form, historically a Google form, then an emailed PDF to sign).
To confirm on the page.

Fields likely asked (to confirm): name, position, institution and department, institutional email,
a project title, a short description of the intended use, whether the use is commercial, and
acceptance of the PadChest licence (research use only, no redistribution, no re-identification,
citation of Bustos et al. 2020). Text for the description:

```text
I study the application of computer science to improving spinal health, and my current work needs chest radiographs with lateral and oblique projections from European devices, including film-era digitised plates. PadChest's 109 projections exercise what a spine-level reader must tolerate: an oblique or a lateral thoracic spine at chest exposure, where the thoracic levels are counted behind the heart and ribs. The work measures how reliably automated image-analysis methods recognise which vertebra is which across projections, devices and exposures, reported as per-image agreement with expert labels and confidence intervals, by projection and device. Non-commercial academic research at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center; de-identified images under IRB determination HPR 2026-269; stored on Wayne State's research computing storage, read by me alone, never redistributed; the source, its paper and the licence will be credited.
```

Project title: the shared title. Binding, the owner's hand only: the licence (a signature on a PDF
is likely), and the usual clause that the licensee answers for the images; read its clauses on
derivative works before signing, a lawyer question. Fee: none known; to confirm. What to expect
back: an approval email with download credentials for the BIMCV server, days to weeks; the images
are about 1 TB in PNG, fetched as a grid job.

## 6. CheXpert Plus (Stanford AIMI)

Page to open: https://stanfordaimi.azurewebsites.net/ , the CheXpert Plus entry (the entry's own
address is to confirm on the page); the owner's existing AIMI account, the one INSPECT and Merlin
need, covers it.

Fields likely asked (to confirm): the account's name and institution, a per-dataset research use
agreement with checkboxes (non-commercial, no redistribution, no re-identification, Stanford's
publication acknowledgement), and sometimes a one-line intended use. Text for the use line:

```text
Measuring how reliably automated image-analysis methods recognise which vertebra is which on frontal and lateral chest radiographs across the many devices of one centre; non-commercial research, Department of General Surgery, Wayne State University, de-identified images under IRB determination HPR 2026-269.
```

Binding, the owner's hand only: the research use agreement click-through, one per dataset. Read
its model and derivative clauses before accepting, a lawyer question. Fee: none. What to expect
back: a time-limited Azure Blob URL, fetched with AzCopy as a grid job on the owner's word; the
DICOM release is several terabytes, so the JPG-plus-DICOM choice is made before the fetch.

## 7. MIMIC-CXR-JPG (PhysioNet, credentialed)

Page to open: https://physionet.org/content/mimic-cxr-jpg/2.1.0/ (and
https://physionet.org/content/mimic-cxr/2.1.0/ for the DICOM). The owner already holds PhysioNet
credentialing (CITI training on file) and signed the VinDr-SpineXR agreement, so this needs only
the per-project step: on the record page, "Sign the data use agreement" for this dataset, which is
PhysioNet's standard credentialed health data agreement, plus, for MIMIC, the "Required training"
line, which the existing CITI course satisfies.

Fields: none beyond the agreement; the credentialing application already holds the reference and
the research summary. If PhysioNet asks for a project description on re-credentialing, paste the
shared aims block.

Binding, the owner's hand only: the DUA click, which attests to the terms for this dataset alone.
Fee: none. What to expect back: access at once; the files (about 570 GB of JPG) are fetched with
`wget --user` or the AWS mirror as a grid job on the owner's word, and the lateral share is read
from mimic-cxr-2.0.0-metadata.csv (ViewPosition) before anything else is downloaded. The IRB
supplement HPR 2026-330 names VinDr-SpineXR; whether it covers a second PhysioNet set or needs a
line added is a question for the IRB office before the images are read, not before the click.

## 8. VinDr-CXR and VinDr-PCXR (PhysioNet, credentialed)

Pages to open: https://physionet.org/content/vindr-cxr/1.0.0/ and
https://physionet.org/content/vindr-pcxr/1.0.0/ . The same as section 7: the credential and the
CITI training are already held, and the VinDr-SpineXR agreement already signed is the same
PhysioNet agreement form, so each of these two records needs only its own "Sign the data use
agreement" click.

Fields: none. Binding, the owner's hand only: the two DUA clicks. Fee: none. What to expect back:
immediate access; 18,000 adult and 9,125 pediatric frontal films from the same two Vietnamese
hospitals and devices as VinDr-SpineXR, fetched as grid jobs on the owner's word. The IRB
supplement question of section 7 applies.

## 9. KUB-StoneX (Daffodil International University HIRL)

Page to open: https://hirl.daffodilvarsity.edu.bd/dataset/ (the KUB-StoneX entry). The sweep read
it as public per the listing; whether the entry is a direct download, a Mendeley or figshare
record, or a request form could not be read from here. To confirm on the page.

If it is a direct download under a stated open licence: nothing to sign; a grid job on the
owner's word.

If it is a form, the fields likely asked (to confirm): name, institution, email, purpose. Text for
the purpose:

```text
I study the application of computer science to improving spinal health, and my current work needs frontal abdominal radiographs, since a kidney-ureter-bladder film is a frontal lumbar spine and pelvis at abdominal exposure, with the iliac crests and the sacrum in field. The work measures how reliably automated image-analysis methods recognise which vertebra is which on such films, including the lumbosacral transitional variants behind wrong-level errors, reported as per-image agreement with expert labels and confidence intervals. Non-commercial academic research, Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center; de-identified images under IRB determination HPR 2026-269; stored on Wayne State's research computing storage, read by me alone, never redistributed; the dataset and its paper will be credited.
```

If the entry gives only an email, send the same text under the subject
"[XR/CT Imaging Research] Request for the KUB-StoneX radiograph dataset" with the sender block.

Binding, the owner's hand only: any licence checkbox. Fee: none expected. What to expect back: a
download link; 2,570 films is small.

## The data platform's own gated sets and never-sent letters

Added on the owner's ask of 04:11 UTC the same day ("get all of them or say exactly what he must
do"). The cards are spinesurg-ct-nnunet's data_platform/sources.json at bf1432f (the seven gated
family-B sources, the three requests "drafted, not sent", BUU-LSPINE and the TotalSegmentator task
sets) and spine-program's 01_carm_level_detection/docs/handoff/LITERATURE_STATE.md section 2 (the
intraoperative sets A1 to A21); the old drafts are docs/data_requests/SX-Stitch_request.md and
docs/outreach/balgrist_data_request_2026-09-21.md in that clone (there is no fluoro_requests_eml
folder in git). Every old draft used words now excluded; the texts below keep
their facts and none of those words. Every author address in the old drafts is redacted in git, so
each is re-read from the paper's correspondence line, marked "to confirm", and no personal address
is written here. The same shared blocks apply.

## 10. Stanford AIMI Merlin and INSPECT (research-use agreement)

Pages to open, signed in to the owner's AIMI account:
https://stanfordaimi.azurewebsites.net/datasets/60b9c7ff-877b-48ce-96c3-0194c8205c40 (Merlin; the
same data are listed at https://stanford.redivis.com/datasets/exfv-e8h3kvfhs) and the INSPECT
entry on the same portal (its address to confirm on the page). Merlin is 25,494 abdominal CTs of
18,317 patients (Stanford ED 2012 to 2018); INSPECT about 19,400 CT pulmonary angiography
patients; the data platform ranks Merlin alone above the whole of its tier 1 for new transitional
spines (expected 1,260 people; ACQUISITION_PLAN.md section 7). These are CT, not X-ray, and go in
this file because the owner's ask covers every gated set.

Fields likely asked (to confirm on the page): the account's name, institution and email, a
per-dataset research use agreement with checkboxes (non-commercial, no redistribution, no
re-identification, Stanford's acknowledgement), sometimes an intended-use line. Text for the line:

```text
Measuring how reliably automated image-analysis methods recognise which vertebra is which in CT of the trunk, including the transitional lumbosacral and thoracolumbar variants behind wrong-level errors, across scanners and protocols; non-commercial research, Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center; de-identified images under IRB determination HPR 2026-269.
```

Binding, the owner's hand only: the two agreement click-throughs (one per dataset), each binding
the person who accepts; read the model and derivative clauses first, a lawyer question. Fee:
none. What to expect back: approval and a time-limited Azure Blob URL per dataset. That URL is a
credential: it goes into a mode-0600 file on the grid (under the owner's HOME or the Ceph data
root, never a job script, argv or `sbatch --export`), and an AzCopy Slurm job on the owner's word
reads it from the file, verifies against the portal's file list and records the fetch; a URL that
expires before the job runs is re-issued from the portal by the owner.

## 11. MAGIC-CT (Zenodo 18389015, DUA application)

Page to open: https://zenodo.org/records/18389015 (version 2, 2026; 562 patients with abdominal
or thoracic tumours, NRRD, 39.1 GB, 492 with reports; Nazarbayev University, Kazakhstan). The
files download without a gate, but the record's data use agreement asks for an application with
proof of completed human-subjects or HIPAA training, and binds the applicant to no
re-identification, no onward sharing, security, reporting any identifying information found to
the corresponding author, research use only, release of the code behind any disseminated result,
and either side ending the agreement. The contact the record names is maxim.popov@nu.edu.kz.

Route: email to that address with the owner's CITI certificate attached (the one PhysioNet's
credentialing holds; the owner downloads it from CITI, never a session). Subject:

```text
[XR/CT Imaging Research] MAGIC-CT data use application (Zenodo 18389015)
```

Body:

```text
Dear Dr Popov and colleagues,

I study the application of computer science to improving spinal health, and my current work needs trunk CT from scanners and populations outside North America and Western Europe, in which the vertebral column is in field end to end. MAGIC-CT's 562 patients, with the spine incidental to the tumour imaging, add a Central Asian population and scanner protocols no other collection I hold covers.

My work measures how reliably automated image-analysis methods recognise which vertebra is which, including the transitional variants at the thoracolumbar and lumbosacral junctions that cause wrong-level errors in spine care, and reports per-image agreement with expert labels and confidence intervals, by scanner and by variant. I use the images only for that; no tumour or clinical question is studied and no finding about any individual is produced.

This is my application under the data use agreement on the record. I accept its terms: no re-identification, no onward sharing, secure storage, reporting to you any identifying information I find, research use only, release of the code behind any result I disseminate, and either side's right to end the agreement. My proof of human-subjects training is attached (CITI Program, Wayne State University). I am at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center; the work is on de-identified imaging under Wayne State IRB determination HPR 2026-269. The data will be held on Wayne State's research computing storage, read by me alone, and deleted if you ask. I will cite the record and quote the agreement in any publication.

With thanks,
```

followed by the sender block. Binding, the owner's hand only: the application and its attached
certificate, which the owner sends from the owner's own mailbox. Fee: none. What to expect back:
an acknowledgement; then the 39.1 GB is fetched to Ceph as a Slurm job on the owner's word and
checked against the record's checksums. The "release of the code" clause is read against the
patent position before the application goes, a lawyer question.

## 12. TVGH-SpineXR (IEEE DataPort, doi:10.21227/x6bb-7r75)

Page to open: https://doi.org/10.21227/x6bb-7r75 (https://ieee-dataport.org/documents/tvgh-spinexr),
signed in to an IEEE account (free). The listing describes T1 to L5 per-vertebra level labels,
masks and end-plates on Taipei Veterans General Hospital spine radiographs; nothing of it has
been seen, since the page answers 403 to a session. Whether the record is open access, a
subscription item or by request is read there first: an open record needs only the account; a
subscription record is a fee the owner decides on; a by-request record shows an "Access request"
box.

Text for the access request box (to confirm on the page):

```text
I study the application of computer science to improving spinal health, and my current work needs spine radiographs with per-vertebra level labels from a Taiwanese centre, since the sets I hold with such labels come from Thailand, Vietnam, the United States and Europe and the question is whether automated image-analysis methods recognise which vertebra is which as reliably on new devices and populations. Your T1 to L5 labels and masks are exactly the truth needed; results are reported as per-image agreement with those labels and confidence intervals, by level and by device. Non-commercial academic research at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center; de-identified images under IRB determination HPR 2026-269; held on Wayne State's research computing storage, read by me alone, never redistributed; the dataset, its paper and its DOI will be cited.
```

Binding, the owner's hand only: the IEEE account, any licence checkbox on the record, and a
subscription fee if the record is one (IEEE DataPort subscriptions are priced per year; the
amount is read on the page). What to expect back: a download link, or the depositor's answer to
the request, days to weeks.

## 13. SX-Stitch intraoperative C-arm series (Li et al., arXiv:2409.05681)

The set: 1,032 intraoperative C-arm spinal images at 512, 1024 and 1920 pixels, in consecutive
overlapping series from one patient at 20 to 90 percent overlap, with vertebra masks; the only
published collection of overlapping intraoperative C-arm frames of the spine. Corresponding
authors: Jinqian Liang (Peking Union Medical College Hospital) and Wei Liu (Department of
Mechanical and Energy Engineering, Southern University of Science and Technology). No email is
printed in the arXiv version, so the addresses come from the SUSTech and PUMCH directories, to
confirm; the paper's data statement says no datasets were generated, so the inventory judges
success unlikely. Route: email. Subject:

```text
[XR/CT Imaging Research] Request for the SX-Stitch intraoperative C-arm image series
```

Body:

```text
Dear Professor Liu and Dr Liang,

I study the application of computer science to improving spinal health, and my current work needs real intraoperative C-arm images of the spine taken as consecutive overlapping exposures of one patient, which no public set provides. Your SX-Stitch paper (arXiv:2409.05681) describes 1,032 such images in overlapping series at 20 to 90 percent overlap, with vertebra masks.

My work measures how reliably automated image-analysis methods recognise which vertebra is which on intraoperative images, where a limited field often holds no landmark and the level must be carried from one exposure to the next; wrong-level errors arise exactly there. Every number I have so far comes from single radiographs and from simulated series, and your set would let the same measurement be reported on real intraoperative series, as per-image agreement with your masks and confidence intervals.

I am writing to ask whether the series could be shared for non-commercial research: the images grouped by patient in acquisition order, any vertebra masks or level labels that exist, and the terms you require. I am at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center. The images would be held on Wayne State's research computing storage, read by me alone, never redistributed, and deleted at the end of the project if you ask; the work is on de-identified imaging under Wayne State IRB determination HPR 2026-269. I will sign a data use agreement through Wayne State on your terms, cite SX-Stitch in any publication, and share my results on your series with you before publication.

With thanks,
```

followed by the sender block. Binding, the owner's hand only: the DUA, if one is offered. Fee:
none expected. What to expect back: most likely a refusal or silence; a yes brings a Chinese
institutional agreement and a transfer by link.

## 14. Balgrist ex-vivo lumbar CT plus C-arm (Jecklin et al.)

State on 2026-10-21: the letter of 2026-09-21 was sent on 2026-10-20; sascha.jecklin@balgrist.ch
bounced, while Philipp Fuernstahl's address and the group address rocs@balgrist.ch received it;
the resend through the ROCS contact form at https://rocs.balgrist.ch/en/contact is pending. The
set: 13 whole-torso cadaver specimens plus six validation specimens, CT with real mobile C-arm
images (Siemens Cios Spin, Ziehm Vision, Ziehm Vision FD) and fiducial-based projection matrices
(Medical Image Analysis 2024, arXiv:2401.16027; a 2025 Scientific Reports follow-up); restricted
for pending patents. The sent letter used words now excluded; the form text below
does not, and if the group answers the first letter the owner's reply uses this wording.

Form fields likely asked (to confirm on the page): name, email, institution, subject, message.
Message:

```text
I study the application of computer science to improving spinal health, and my current work needs real mobile C-arm images of the lumbar spine inside an intact torso, paired with the same specimen's CT and the projection geometry, from more than one device. Your ex-vivo set (Jecklin et al., Medical Image Analysis 2024, and the 2025 Scientific Reports follow-up) is the only one I have found that offers this on three C-arms.

My work measures how reliably automated image-analysis methods recognise which vertebra is which on intraoperative images across devices and exposures, and how closely simulated images from CT reproduce what each real C-arm records, reported as per-image agreement with CT-derived labels and confidence intervals, by device. I wrote to Dr Fuernstahl and the group address on 20 October 2026 (the message to Dr Jecklin bounced) and am repeating the request here. I am asking for the CT volumes, every real X-ray as the C-arm exported it (original DICOM with headers where they exist), the projection matrix for each image and the device that took it, for the 13 specimens, the six validation specimens and the Scientific Reports specimens if separate.

I am at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center. I understand the set is restricted for pending patents and will work under whatever data transfer agreement Balgrist requires, through Wayne State: research use only, no redistribution, storage on Wayne State's research computing, read by me alone, no attempt to identify donors; the work is under Wayne State IRB determination HPR 2026-269. I will cite both papers, acknowledge the group as you judge right, and share any result on your specimens before submission. go2432@wayne.edu, +1 504-994-0403.
```

Binding, the owner's hand only: the data transfer agreement, which Wayne State's institutional
official may countersign. Fee: none expected. What to expect back: an answer from the group
address, weeks; then a Swiss agreement and a transfer by link.

## 15. The intraoperative sets the literature names, drafted nowhere, never sent

LITERATURE_STATE.md section 2 lists every labelled intraoperative set as request-only or
unreleased. One short letter each, all by email, each with the subject
"[XR/CT Imaging Research] Request for <set>" and the sender block, each ending with the same
closing paragraph:

```text
I am at the Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center. The images would be held on Wayne State's research computing storage, read by me alone, never redistributed, and deleted at the end of the project if you ask; the work is on de-identified imaging under Wayne State IRB determination HPR 2026-269. I will sign a data use agreement on your terms, cite your work and quote the agreement in any publication, and share my results on your images with you before publication.
```

Every one of these measures the same thing, said once here and once in each letter: how reliably
automated image-analysis methods recognise which vertebra is which on real intraoperative images,
reported as per-image agreement with expert or CT-derived labels and confidence intervals.

### 15a. LevelCheck clinical cohort (Johns Hopkins, Siewerdsen group)

178 patients with preoperative CT and 398 intraoperative radiographs (De Silva et al., Spine
2016), plus Ketcha et al. 2017's 24 thoracolumbar patients with 61 Carestream DRX-1 radiographs,
and the 62-image reader set of Manbachi et al. 2018. Neither paper has a data statement; the
route is a DUA with the PI. Jeffrey Siewerdsen has been at MD Anderson (Surgical Data Science)
since 2022; copy the JHU co-authors still there (Ali Uneri, Wojciech Zbijewski, J. Webster
Stayman), addresses from the institutional directories, to confirm.

```text
Dear Professor Siewerdsen and colleagues,

I study the application of computer science to improving spinal health, and my current work needs real intraoperative radiographs of the spine for which the correct level of each vertebra is already known from the same patient's labelled preoperative CT. The LevelCheck clinical cohort (De Silva et al., Spine 2016: 178 CTs and 398 radiographs; Ketcha et al. 2017; the 62 reader images of Manbachi et al. 2018) is the only collection of that kind and size described in the literature, and the hard cases in it, transitional anatomy and degraded images, are exactly where wrong-level errors happen.

My work measures how reliably automated image-analysis methods recognise which vertebra is which on such images from image content alone, reported as per-image agreement with the levels your registration placed and confidence intervals, by level and by anatomical variant; the result would sit beside the surgeon error rates your group measured. I am writing to ask whether the de-identified radiographs with their level labels (and the CTs, if the agreement allows) could be shared under a data use agreement with Johns Hopkins or MD Anderson, and what terms you require.
```

### 15b. Vanderbilt intraoperative THA fluoroscopy (Chan et al., J Arthroplasty 2025)

146 living patients, 161 anterior-approach hips, 336 AP frames with eight bony landmarks
including midline L5/S1 and both sacroiliac joints, plus 84 cup frames; AP only; the C-arm is
not reported; no data statement, code only at github.com/vine-lab-vu/Label-Augmentation
(doi:10.1016/j.arth.2025.01.032). Write to the corresponding author named on the paper
(Vanderbilt Orthopaedic Surgery and Computer Science), to confirm.

```text
Dear Dr Chan and colleagues,

I study the application of computer science to improving spinal health, and my current work needs real intraoperative frames of the pelvis on which the lumbosacral junction has been marked by an expert, since the sacrum and L5 are the anchors from which lumbar levels are counted and the lumbosacral transitional variants are the commonest cause of a wrong count. Your fluoroscopy set (J Arthroplasty 2025;40:2092) marks midline L5/S1 and both sacroiliac joints on 336 intraoperative frames from 146 patients.

My work measures how reliably automated image-analysis methods find those anchors and name the vertebrae above them on real intraoperative images, reported as per-image agreement with your landmarks and confidence intervals. I am writing to ask whether the de-identified frames with the bony landmarks could be shared under a data use agreement with Vanderbilt, and what terms you require; the cup landmarks are not needed.
```

### 15c. Huashan Hospital, Fudan University (Shao et al. 2024)

140 living lumbar patients (January 2020 to December 2023) with preoperative CT and
intraoperative AP and lateral films of L1 to L5; the device is unnamed; two co-authors are from
Shanghai Maestro Surgical Robotics; no data statement. Write to the corresponding author (Jiang
Jianyuan, Huashan Hospital, Department of Orthopaedics), address from the paper's correspondence
line, to confirm.

```text
Dear Professor Jiang and colleagues,

I study the application of computer science to improving spinal health, and my current work needs real intraoperative lumbar images of living patients paired with the same patient's preoperative CT, so that the correct level of each vertebra on the intraoperative image can be established from the CT. Your series of 140 patients with preoperative CT and intraoperative anteroposterior and lateral films (Shao et al. 2024) is the largest of that kind I have found.

My work measures how reliably automated image-analysis methods recognise which vertebra is which on intraoperative images, including the transitional variants that cause wrong-level errors, reported as per-image agreement with CT-derived labels and confidence intervals, by device and by variant. I am writing to ask whether the de-identified films and CTs could be shared under a data use agreement, and, to judge fit, the make and model of the C-arm, whether the films exist as DICOM with headers, and how many frames each patient has.
```

### 15d. PUMCH stitching series (Liu et al., Eur Spine J 2026)

43 scoliosis patients, four to six overlapping prone AP exposures each on a Philips Zenition 70;
the shift between shots estimated, not recorded; no labels stated; "No datasets were generated or
analysed", so the inventory judged asking unlikely to succeed. Write to the corresponding author
at Peking Union Medical College Hospital (Department of Orthopaedics), to confirm; if the
SX-Stitch letter (section 13) goes to Dr Liang at PUMCH, one letter can carry both asks.

```text
Dear Dr Liang and colleagues,

I study the application of computer science to improving spinal health, and my current work needs intraoperative C-arm exposures of one patient taken in overlapping sequence along the spine, since naming a level on an exposure that holds no landmark depends on carrying the count from the exposures before it. Your stitching series (Eur Spine J 2026: 43 scoliosis patients, four to six overlapping prone exposures each on a Philips Zenition 70) is one of two such collections described anywhere; the other is SX-Stitch from your group and SUSTech, which I am asking for in the same way.

My work measures how reliably automated image-analysis methods carry a vertebra's identity from one exposure to the next and name each vertebra, reported as per-image agreement with expert labels and confidence intervals. I am writing to ask whether the de-identified series, grouped by patient in acquisition order, could be shared under a data use agreement, and what terms you require.
```

### 15e. NIT Warangal and NIMS Hyderabad (2D-3D-sci-registration)

Nine living patients and 51 AP and lateral C-arm sets in the repository's README (at most 49
unique frames), a Ziehm C-arm, preoperative CT with level-named L1 to L5 centroids; the 60
centroid files and 54 overlay PNGs (the real frame at 8 bits beside a DRR) are public on the
repository, the CT and raw X-rays "available upon reasonable request". Write to the authors named
on the repository and the manuscript (National Institute of Technology Warangal; Nizam's
Institute of Medical Sciences, Hyderabad), to confirm.

```text
Dear colleagues,

I study the application of computer science to improving spinal health, and my current work needs real intraoperative C-arm images of the lumbar spine with the level of each vertebra established from the same patient's CT. Your 2D-3D-sci-registration repository publishes level-named L1 to L5 centroid files and overlay images for nine patients on a Ziehm C-arm, and says the CT and the raw X-rays are available on reasonable request.

My work measures how reliably automated image-analysis methods recognise which vertebra is which on intraoperative images across devices, reported as per-image agreement with CT-derived labels and confidence intervals. I am writing to ask for the raw anteroposterior and lateral frames at their original bit depth and size, the preoperative CTs and the projection geometry behind the overlays, for the nine patients and the two of the manuscript, under whatever agreement you require.
```

### 15f. CM Spine (208 intraoperative lumbar G-arm images)

208 intraoperative lumbar G-arm images with vertebra detection labels, attributed to the Chinese
Academy of Sciences by an unverified AI-generated summary; the only record of a route is a Google
Drive file id (1r9wX1802gkU4-EQHMMlyAlEiWXGWLhhJ) described only as "intraoperative", whose
download on 2026-09-01 left an empty directory, and whether that file was CM Spine is known only
by its name. There is no paper, no author and no address on record, so no letter can be sent
yet. The owner's steps: open the Drive file in a browser signed in to the owner's Google account
(the id above, as drive.google.com/file/d/<id>/view) and read what it is and who shared it; if a
paper or a sharer's name is found, a letter of the shape of 15c goes to that author with
"208 intraoperative lumbar G-arm images with vertebra labels" as the set; if the file is gone,
the record is closed as untraceable. Nothing to sign until a source exists.

## 16. TotalSegmentator task sets: an overlap question to the authors (Basel)

The three Zenodo task sets (liver_lesions, record 20272572, 842 CT; pleural_pericard_effusion,
600 CT; hip_implant, record 20272031, 71 CT; CC BY 4.0, published 2026-05-18) are open and need
no request to fetch; what is not known is whether their subjects are among the public v2 and v3
releases already held (doi:10.5281/zenodo.10047292), which decides whether they add people or
only repeat them, since the platform counts a person once. One email to Jakob Wasserthal
(University Hospital Basel, Department of Radiology), the corresponding author of the
TotalSegmentator papers, address from the paper's correspondence line, to confirm. Subject:

```text
[XR/CT Imaging Research] TotalSegmentator task data: overlap with the v2 and v3 releases?
```

Body:

```text
Dear Dr Wasserthal,

I study the application of computer science to improving spinal health, and my current work counts every CT subject once across the collections it reads, so that an agreement measured on one person is never counted twice. I hold the public TotalSegmentator v2 and v3 releases and am about to add the three task datasets you published on Zenodo in May 2026 (liver_lesions, 842 CT; pleural_pericard_effusion, 600 CT; hip_implant, 71 CT). Could you tell me whether the subjects of those three sets overlap the v2 and v3 subjects, and, if they do, whether a subject map or a shared identifier exists, or whether the file names can be matched? If no map exists, a yes or no on overlap is enough for me to treat them conservatively. Thank you for the datasets; they are credited in everything built on them.

With thanks,
```

followed by the sender block. Binding: nothing; the sets are CC BY 4.0 and the fetch is a grid
job on the owner's word. What to expect back: a one-line answer, or none, in which case the
platform treats the three sets as overlapping (no new people) until shown otherwise.

## 17. BUU-LSPINE, the full release of 3,600 patients (EULA form)

Page to open: https://services.informatics.buu.ac.th/spine/ (Klinwichit et al., Applied Sciences
2023;13:8646; Burapha University). The release is reached through a Google Form with an end user
licence agreement: no licence in the open-source sense, acknowledgement required, no
re-identification, never redistribute. The platform's card records the 3,600 release as on disk
already (3,600 AP and 3,604 lateral films under buu_full), so the form was filled once; the
registry's own record says the licence is unread by the owner and that nothing built on the
films leaves the grid until it is. The owner's step is therefore to open the form, read the EULA
in full, and either file it again under the text below so the project's acceptance is on record,
or record the earlier acceptance's date and wording in data/sources/buu_lspine.json.

Fields likely asked (to confirm on the form): name, email, institution, country, purpose, the
release wanted (400, 2000 or 3600), agreement to the EULA. Purpose:

```text
Measuring how reliably automated image-analysis methods recognise which lumbar vertebra is which on anteroposterior and lateral radiographs, including the four- and six-lumbar transitional spines your L4L6 sheet records, which cause wrong-level errors in spine care; results reported as per-image agreement with your end-plate labels and confidence intervals. Non-commercial academic research, Department of General Surgery, Wayne State University School of Medicine and the Detroit Medical Center, Detroit, USA; de-identified images under IRB determination HPR 2026-269; held on Wayne State's research computing storage, read by me alone, never redistributed; the dataset and its paper (Applied Sciences 2023;13:8646) are acknowledged in any publication.
```

Binding, the owner's hand only: the EULA checkbox, and the reading of its clauses on derivative
works and models before ticking, a lawyer question as for Radiopaedia. Fee: none. What to expect
back: a download link by email; the 18.5 GB release is already on the grid, so nothing is fetched
unless the files differ.

## Order and what is not known

Value first among the X-ray sets: MrOS and SOF (per-vertebra level truth on the anatomy the
C-arm sees), then Aariz (C2 to C4 on seven devices), then the three PhysioNet clicks (held
credential, no new agreement form), then ReXGradient, PadChest and CheXpert Plus (laterals in
volume), then KUB-StoneX and TVGH-SpineXR. Among the intraoperative letters: LevelCheck, Huashan,
the Balgrist form, Vanderbilt, NIT Warangal, SX-Stitch with PUMCH, then CM Spine once a source
exists. Among the CT gates: Merlin and INSPECT (two clicks), MAGIC-CT (one application), the
TotalSegmentator question (one email), BUU-LSPINE (one form, for the record).

The owner's hand only, complete:

- Accounts to create or sign in to: MrOS Online, SOF Online, Hugging Face, Stanford AIMI,
  PhysioNet (held), IEEE DataPort, Google (for the BUU form and the CM Spine Drive file).
- Attestations and click-through agreements: ReXGradient-160K's gate; PadChest's licence;
  CheXpert Plus, Merlin and INSPECT on the AIMI portal (three); MIMIC-CXR-JPG, VinDr-CXR and
  VinDr-PCXR on PhysioNet (three); TVGH-SpineXR's record terms; BUU-LSPINE's EULA; any Aariz or
  KUB-StoneX form checkbox.
- Signatures: the MrOS and SOF data use agreements (institutional countersignature likely); the
  PadChest licence if it is a PDF; the MAGIC-CT application with the CITI certificate; the data
  use or transfer agreements that LevelCheck (JHU or MD Anderson), Vanderbilt, Huashan, PUMCH,
  SX-Stitch, NIT Warangal and Balgrist may offer.
- Fees: none known; to confirm on the MrOS and SOF portals and on TVGH-SpineXR's IEEE DataPort
  record (a subscription item is priced per year).
- Letters sent from the owner's own mailbox after the owner approves each: Aariz, MAGIC-CT,
  SX-Stitch, LevelCheck, Vanderbilt, Huashan, PUMCH, NIT Warangal, TotalSegmentator, and
  KUB-StoneX if it is an email; the Balgrist form.
- Grid jobs on the owner's word and number: every fetch once access is granted (AzCopy for
  Merlin and INSPECT from the mode-0600 URL file, wget for PhysioNet, huggingface-cli for
  ReXGradient, the BIMCV server for PadChest, Zenodo for MAGIC-CT and the TotalSegmentator task
  sets).
- Lawyer questions before any tick: the model, derivative and code-release clauses of
  ReXGradient, PadChest, the AIMI agreements, MAGIC-CT and the BUU EULA.
- IRB office question before any PhysioNet set other than VinDr-SpineXR is read: whether HPR
  2026-330 covers it or needs a line.

Not known, since no portal page was read: the real field names and the presence of a fee on the
MrOS and SOF portals, the Aariz request route (form or email) and address, whether PadChest's
form is still a Google form, the CheXpert Plus and INSPECT entries' addresses on the AIMI
portal, whether HIRL's entry is a download or a form, TVGH-SpineXR's access type, every author
address in section 15 (redacted in git, re-read from each paper), what the CM Spine Drive file
is, whether the TotalSegmentator task subjects overlap, the date and wording of the BUU EULA
once accepted, and whether HPR 2026-330 covers PhysioNet sets other than VinDr-SpineXR. Each is
read by the owner on the page, or asked of the IRB office, before the text is pasted.
