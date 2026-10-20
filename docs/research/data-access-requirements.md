# What each dataset not held needs, and who can act

Source: the thread "SchwingNet video demo plan", 2026-10-20, the owner's ask ("research the requirements for each dataset I don't currently have and obtain them, through forms, emails and the rest", then "one at a time so I can approve"). The 33 sources below are every record under data/sources/ whose reach is GET, GATED or EMBARGOED; the inventory (datasets-inventory.md) quotes each record's steps, and this note says what the steps need, who can act, and what the research could not reach. The letters themselves are spine-program's 01_carm_level_detection/docs/data_requests/ (FLUORO_VIDEO_REQUESTS_READY_2026-09-26.md, requests 1 to 14; balgrist_data_request_2026-09-21.md; SX-Stitch_request.md), written and never sent; every address in them is redacted in git under spine-program's rule 12, and the .eml drafts that carried them were not in git and are not on the owner's Desktop (looked 2026-10-20), so each address is re-read from its public page when the request is put to the owner.

What the cloud session can and cannot reach (2026-10-20): web search answers, but every host page tried was refused by name (PMC, arXiv, Zenodo, IEEE DataPort, Hugging Face, PhysioNet, TalkBank, RSNA MIRA, Stanford AIMI, the university and clinic sites), so a licence line or an address that only a page shows is marked "to confirm on the page". Radiopaedia was not fetched by choice: its terms bar automated access.

## Who acts

Four kinds of step, by who may take them:

- A letter: a session can draft it in the owner's Gmail and send it once the owner approves that one letter, since sent mail cannot be recalled. The letters introduce the owner as a surgeon-scientist at Wayne State and sign go2432@wayne.edu; the owner chooses whether they go from Gmail or from the Wayne State address.
- A web form with no signature: a session can fill it only with a browser; from this session there is none, so the text is given to the owner to paste.
- An account, a click-through or signed agreement, a credentialing attestation, a fee: the owner's own hand, always. An agreement binds the person who accepts it.
- A plain download: a Slurm job on the grid, which runs only on the owner's word and number, as the project's rule for every grid job.

## The requests, in the order they are put to the owner

Value first (per-frame level truth, then lumbar, then volume), as the 2026-09-26 sheet ordered them, with what each needs.

| # | Source | Route | Needs | Who acts |
|---|---|---|---|---|
| 1 | Bournemouth cervical and lumbar QF (Branney, Breen) | request 1, e-mail to 4 addresses (BORDaR 385 contact, the 2021 and 2024 correspondence lines) | a UK data-sharing agreement follows, which Wayne State's institutional official signs | owner approves the letter; the agreement is the owner's and WSU's |
| 2 | Maastricht UMC+ / Zuyderland cervical and lumbar cine | request 2, e-mail to 4 addresses (the 2026 and 2020 correspondence lines) | a GDPR data transfer agreement under the Dutch WMO framework | as 1 |
| 3 | Inselspital Bern dynamic myelography DICOM (Dobrocky) | request 3, e-mail to the corresponding author (the team page neurorad.insel.ch/en/about-us/our-team carries a "Contact by Email" link; insel.ch addresses are firstname.lastname) | a Swiss data transfer agreement, perhaps KEK Bern | as 1 |
| 4 | Pittsburgh videofluoroscopic swallow corpus (Sejdic, Coyle) | request 4, e-mail; jcoyle@pitt.edu confirmed by Pitt's directory, Sejdic's current address to confirm (North York General or U of T) | a University of Pittsburgh data use agreement | as 1 |
| 5 | Balgrist ex-vivo lumbar CT plus C-arm (Jecklin, Fuernstahl) | the 2026-09-21 letter, e-mail to rocs@balgrist.ch (the ROCS group address) or the authors once confirmed on the article's first page | a data transfer agreement; the set is restricted for pending patents | as 1 |
| 6 | SX-Stitch intraoperative C-arm series (Liu, Liang) | the 2026-09-19 letter; no e-mail printed in the arXiv version, the SUSTech and PUMCH directories give them | unlikely to succeed (the paper's data statement) | as 1 |
| 7 | Seattle Science Foundation, 12 videos | request 5, e-mail; the address is hidden from scripts, to confirm in the footer of seattlesciencefoundation.org | permission and whether the labs were cadaveric | as 1 |
| 8 | Mayfield Brain and Spine kyphoplasty series | request 6, e-mail to the address on mayfieldclinic.com/contact.htm (the site routes general enquiries through its People directory) | HIPAA de-identification | as 1 |
| 9 | DMX Imaging | request 7, e-mail to the mailto on dmxworks.com | a vendor; perhaps an NDA | as 1 |
| 10 | Jefferson (Hines) DRG video | request 11, e-mail to the 2020 correspondence line, to confirm | which licence applies | as 1 |
| 11 | DARADIA vertebroplasty video | request 14, e-mail to info@daradia.com (verified 2026-09-26) | consent status | as 1 |
| 12 | Konica Minolta DDR sequences | request 10, e-mail or the web form (Radiography; Email and Contact Number required) | likely an NDA or a pointer to a site | as 1, or the owner pastes the form |
| 13 | The Procedure Guide (Puranik) | request 9, the contact form only (First name, Last name, Email, Message) | whether CC BY-NC-SA covers the clips | the owner pastes; no browser here |
| 14 | MTFI (Mohanty) lumbar coupling video | request 12, the address on mtfi.net's Contact Us page (hidden from scripts) or WhatsApp +91 99016 59074 | low value | as 1 once the owner copies the address |
| 15 | Christopher Faubel (ThePainSource) | request 13 by fax or phone; no e-mail published | low value | the owner |
| 16 | Radiopaedia, seven cases | the licence application at radiopaedia.org/licence; request 8 is the project text | a fee reported as USD 250, non-commercial only; nothing automated | the owner, since it is a fee and an application in the owner's name |
| 17 | VinDr-SpineXR | PhysioNet credentialing (CITI training on file) and the data use agreement on the record page; then an IRB determination before any training reads it | credentialing and a signed agreement | the owner |
| 18 | CT-RATE | the gate form on the Hugging Face page (name, institution, e-mail, terms) | a click-through agreement, non-commercial | the owner, on the owner's Hugging Face account |
| 19 | CADS | one checkbox on the Hugging Face page; CT-TRI's and VISCERAL's terms for derived labels | a click-through agreement | the owner |
| 20 | Stanford AIMI Merlin and INSPECT | the AIMI portal's research use agreement, one per dataset; a time-limited Azure Blob URL follows, fetched with AzCopy as a job | an agreement, non-commercial | the owner; the fetch is a grid job |
| 21 | RSNA RATIC | a MIRA account (controlled access) or Kaggle; RSNA's terms | an agreement, non-commercial, no redistribution | the owner |
| 22 | RSNA RSPECT | a Kaggle account and the competition rules; the Kaggle API token in a file | an agreement | the owner |
| 23 | MAGIC-CT | Zenodo record 18389015 (found 2026-10-20; the manifest had no address): labelled CC0 yet carrying a data use agreement (no re-identification, no onward sharing, either side may end it); contact maxim.popov@nu.edu.kz; 39.1 GB, 562 patients, 492 with reports | the agreement; an application with proof of human-subjects or HIPAA training where the record asks | the owner; the fetch is a grid job |
| 24 | TVGH-SpineXR | IEEE DataPort doi:10.21227/x6bb-7r75 (found in spine-program's landscape note); an IEEE account; open, subscription or by request to confirm on the page | a sign-in | the owner |
| 25 | DysphagiaBank (UNM corpus) | registration on dysphagia.talkbank.org, non-commercial terms; the corpus page lists 7 participants where the scan counted about 53 | a registration | the owner |
| 26 | LUMOS | Zenodo record 18173664, 46.4 GB; licence line to confirm on the page | nothing to sign if the licence is open | a grid job on the owner's word |
| 27 | IRI-VFI pediatric interventional sequences | IEEE DataPort doi:10.21227/v4kg-zp42 (found 2026-10-20): 1,357 sequences, 95,308 images, Children's Hospital of Chongqing Medical University, ChiCTR2200058971; licence and access type to confirm on the page | an IEEE account | the owner reads the terms; the fetch is a grid job |
| 28 | Coronary angiography sets | XCAD at github.com/AISIGSJTU/SSVS; CADICA (Universidad de Malaga, arXiv:2402.00570); ARCADE (Scientific Data 2024); AngioCAD by name; each licence read first | nothing to sign where the licence allows research use | grid jobs on the owner's word |
| 29 | Neurosurgical Focus: Video | browser downloads from PMC (a proof-of-work gate stops scripts); CC BY 4.0; AANS reserves TDM and AI-training rights in a footer | attribution; the AANS footer is a lawyer's question for training | the owner's browser, or a session with one |
| 30 | Veterinary pig CBCT (Goswami 2020) | IEEE DataPort open access, an IEEE account, no agreement; or the seven zips in spine-program's archive | nothing to sign | a grid job on the owner's word |
| 31 | COBRA2026 embargoed cases | nothing to do until 2032-03-01 | time | nobody |
| 32 | Bern myelography published videos | already held under CC BY; request 3 above asks for the DICOM | see 3 | see 3 |
| 33 | Bournemouth lumbar QF | part of request 1 | see 1 | see 1 |

Rows 32 and 33 are the records bern_myelography and bournemouth_lumbar_qf, which the same two letters cover; the table counts every unheld record once.

## Read once before the first letter goes

The 2026-09-26 sheet's cautions still hold: every letter says the use is non-commercial academic evaluation, so a frame that might validate a product needs a commercial licence instead; letters 1 to 3 say "we would not train on it"; letters 1 to 4 offer co-authorship; the letters to YouTube uploaders say copies were saved for screening and will be deleted on request; and the IRB question (whether de-identified data under a data use agreement is covered by the existing not-human-participants determination) is asked before the files arrive.

## What is still unknown

- The addresses for requests 1 to 4, 7, 8, 9, 10 and 14: redacted in git, their pages unreachable from the cloud session; each is re-read on its page when its request is put to the owner, or confirmed by the owner.
- The licence lines of LUMOS, IRI-VFI and TVGH-SpineXR, and whether the two DataPort records are open or subscription: to read on the page.
- Whether the owner's Gmail may send as the Wayne State address the letters sign; the owner's choice.
