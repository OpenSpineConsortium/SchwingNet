---
name: phantom-templates-open-models
description: The phantom shape decoders - greg's 2026-10-31 words clearing Meng 2020 and UPF whatever their licence, and training his own decoder on the gold tier masks (test reserve out); VerSe 2019 leakage; the meshes branch
metadata:
  type: project
  modified: 2026-10-31T00:47:45.024Z
---

greg, 2026-10-31, thread "Train on randomized spine phantoms":
- 00:09 UTC: "i dont care about licenses use these if they help", meaning Meng et al. 2020 (non-commercial, gitlab.inria.fr/spine/spine_model) and the UPF thoracolumbar repository (CC BY 4.0, Zenodo 8108354 and 10994164).
- 00:37 UTC: replace the seven hand-picked measures with latent variable encoding and a mesh decoder. The seven measures become a check on decoded meshes, not the generator. The zone-wise warp of bordercall #55 stays as the fallback.
- 00:46 UTC, decision card: "Yes, train on the gold tier". His own decoder trains on the gold tier masks, with the 584-person latent-prior test reserve (SchwingNet data/splits/latent-prior-test-reserve.json) held out. This supersedes the earlier reading "gold tier masks are never templates". Meng's model is the first decoder until his is trained.

Plan: fit one shared vertebra template to every gold tier vertebra on the grid (dense correspondence, the same landmark on every level). His decoder starts as a PCA over those fits. The latent prior is fit jointly across levels, per population, conditional on covariates (see [[gold-tier-covariates]]).

- Fetching: this container's proxy refuses zenodo.org and gitlab.inria.fr. bordercall's .github/workflows/meshes.yml runs on GitHub's runner and commits to the branch `meshes`. Modes: list, upf, meng (bordercall #62).
- Meng's repo holds vertebra_smpl_v10.pkl (1.1 GB), a ppca pkl (729 MB), a 10 MB metadata pkl and demo code. Its pca_variances.txt drops sevenfold after mode 10. It has separate meshes per bone (no cross-level correspondence), C1 to L5 only, no sacrum.
- Leakage: Meng's model was trained on the 80 VerSe 2019 CTs. No VerSe 2019 person may test a network trained on Meng-based phantoms. A decoder trained on gold tier masks has seen those persons, so the test reserve stays out of its training.
- The IVD site (ivd.spineview.upf.edu, Zenodo 8325042): 169 lumbar discs, for per-level disc height and wedge later.
- UPF's code: BCPD++ (github.com/ohirose/bcpd) is worth adapting for carrying landmarks across meshes. SOS-hex and SpineViewer are not.

**Why:** a later thread must not re-ask greg about licences or the gold tier's role.
**How to apply:** tag Meng-derived phantoms with the VerSe 2019 origin. Keep the test reserve out of every decoder and prior fit.

Related: [[correlation-prior-2026-10-30]], [[gold-tier-covariates]]
