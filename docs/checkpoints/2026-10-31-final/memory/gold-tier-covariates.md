---
name: gold-tier-covariates
description: greg's 2026-10-31 00:45 UTC rule - every encoding of the gold tier carries all available metadata (header, supplements), per-person covariates preferred, cohort distributions otherwise
metadata:
  type: feedback
  modified: 2026-10-31T00:47:50.462Z
---

greg, 2026-10-31 00:45 UTC: "please dont forget any metadata available when encoding the gold tier which is found in either the dicom/nifti header or the supplementals of the paper ect, even if its just a distribution, but prefer finding sample size covariates". He quoted UPF's cohort table as an example: 50% M, height 1.72 +/- 0.22 m, weight 86 +/- 23 kg, sagittal GAP classes (7 aligned, 15 moderate, 20 severe), scoliosis classes.

- Per person first: sex, age (already joined to the gold tier morphometry rows by SchwingNet's `morphometry covariates` grid word), height and weight (DICOM PatientSize and PatientWeight, Type 3, kept under TCIA's Retain Patient Characteristics), scanner and kernel. The grid's sample index (samples.sqlite) holds each file's header and sidecar rows.
- A cohort distribution (a paper's mean and SD, the 39 papers' strata in bordercall synthval/covariates.py) enters as a population-level constraint, not per person.
- UPF's Descriptive_List.xlsx (Zenodo 8108354) should hold its 42 patients' values individually.

**Why:** the latent prior is to be conditional on covariates, so a phantom can be drawn for a given sex, age and build.
**How to apply:** no encoding run, prior fit or decoder training on the gold tier leaves out a covariate that is on hand.

Related: [[phantom-templates-open-models]]
