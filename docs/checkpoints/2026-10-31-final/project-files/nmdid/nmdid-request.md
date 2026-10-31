# NMDID: the steps and a draft research request

Source: the thread "Catalogue online whole-spine CT data", 2026-10-31, the owner's word of 01:10 UTC to start with NMDID's metadata file. The site (nmdid.unm.edu) refused this thread's container, so every step here is the owner's, from his own browser; the facts about the site are from its home page as fetched outside the container on 2026-10-31. Confidential, like the rest of SchwingNet.

## Steps

1. Register at nmdid.unm.edu with the Wayne State address; the site wants an institutional e-mail and gives a username and password.
2. Log in and search the metadata with no filter but the scan type. A search returns at most 1,000 records, so take it in slices (for example by death year, 2010 to 2017, then by age band where a year passes 1,000) and download each slice as CSV.
3. Put the CSVs in the project's files under nmdid/ (or on the grid under the data root, landing nmdid_metadata). The next thread joins them, counts who has height, weight, age and sex, and writes the inclusion rule into the request below. The CSV holds no image and is small.
4. Read the Data Use Agreement the site links before signing; the data platform's record (excluded_nmdid in data/reproduce/sources.json) says it forbids derivative works. The owner's word of 2026-10-31 is that licences do not decide which data is used; the signature is his.
5. Send the research request below from the site's form once the inclusion rule is filled in. The images wait for the committee's approval and for the owner's okay to fetch, then go to the grid under the size rule, a few TB at a time.

## Draft research request

Written to the project's rule for dataset letters: short, the agreed opening line, and nothing that says or implies a model, a neural network, machine learning, AI or training. Fill the brackets from the metadata.

Title: Variation in vertebral number and form along the whole spine

I study the application of computer science to improving spinal health, and my current work needs whole-body CT in which the spine is seen from the second cervical vertebra to the sacrum, with the age, sex, height and weight of each person.

Inclusion: decedents whose whole-body CT shows the spine from C2 to the sacrum, [all years, 2010 to 2017], about [N] persons by the metadata. Exclusion: [advanced decomposition, decomposition score above X; none otherwise].

Planned research: to measure, level by level, the size and shape of each vertebra from C2 to the sacrum, and how those measures vary together along the spine and with age, sex and body size, including people whose spine has more or fewer vertebrae than usual (transitional and numbering variants).

Hypotheses: the measures of neighbouring vertebrae vary together far more than chance allows; that joint variation differs by sex and body size; and transitional spines differ from the usual count in measurable ways at the levels next to the transition.

Expected results: reference tables of vertebral measures by level, sex, age and body size, with the correlation between levels, and the rate and form of numbering variants in an unselected population.

Benefits: wrong-level spine surgery follows from miscounting vertebrae on intraoperative imaging, most often in people with numbering variants; population reference data on how the spine varies, drawn from an unselected population rather than a clinic's, makes counting safer.

Data handling: images held on Wayne State University's research computing grid under the PI's account, not shared, not redistributed, and kept for the term the agreement sets.

Gregory Schwing, MD, PhD
General Surgery, Wayne State University School of Medicine / Detroit Medical Center
