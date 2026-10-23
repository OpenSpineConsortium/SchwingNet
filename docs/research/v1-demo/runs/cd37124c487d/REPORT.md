# Report of run cd37124c487d

Written by `python3 tools/report.py write` from this folder's files and data/reporting/study.json; do not edit by hand. Commit cf0d3f03d5d9, clean tree, catalog 5adfe5ec5715 version 1, stage level, seed 1, 4 epochs, started 2026-10-21T13:41:11Z in local mode.

Complete: **no**; missing 48: CLAIM 1, CLAIM 2, CLAIM 3, CLAIM 4, CLAIM 5, CLAIM 6, CLAIM 7, CLAIM 8, CLAIM 10, CLAIM 11, CLAIM 12, CLAIM 13, CLAIM 14, CLAIM 15, CLAIM 16, CLAIM 17, CLAIM 18, CLAIM 21, CLAIM 30, CLAIM 31, CLAIM 33, CLAIM 34, CLAIM 35, CLAIM 36, CLAIM 40, CLAIM 41, CLAIM 42, CLAIM 43, CLAIM 44, REFORMS 1a, REFORMS 1b, REFORMS 1c, REFORMS 2a, REFORMS 3a, REFORMS 3b, REFORMS 3c, REFORMS 3f, REFORMS 3g, REFORMS 4a, REFORMS 4b, REFORMS 5b, REFORMS 5e, REFORMS 5f, REFORMS 6a, REFORMS 6c, REFORMS 7c, REFORMS 8a, REFORMS 8b.

A met item quotes the file that shows it; a declared one is the owner's sentence in data/reporting/study.json, which the code checks is there but cannot judge; a missing one is work to do before the numbers are published (`python3 tools/report.py check --run <folder> --complete`).

## Data and licences

Not recorded: the run folder holds no PROVENANCE.json (tools/licences.py provenance writes it), so which sources the run read and under which licence is unknown, and so is whether the network may be used commercially.

## CLAIM 2024

44 items: 15 met by the run's files, 0 declared, 0 not applicable, 29 missing.

| item | section | asks | answered by | state | evidence |
|---|---|---|---|---|---|
| 1 | Title or abstract | Identification as a study of AI methodology, specifying the category of technology used (eg, deep learning) | declared (title) | missing | needs the owner's answer under "title" in data/reporting/study.json |
| 2 | Abstract | Summary of study design, methods, results, and conclusions | declared (abstract) | missing | needs the owner's answer under "abstract" in data/reporting/study.json |
| 3 | Introduction | Scientific and/or clinical background, including the intended use and role of the AI approach | declared (background) | missing | needs the owner's answer under "background" in data/reporting/study.json |
| 4 | Introduction | Study aims, objectives, and hypotheses | declared (aims) | missing | needs the owner's answer under "aims" in data/reporting/study.json |
| 5 | Methods: study design | Prospective or retrospective study | declared (study_design) | missing | needs the owner's answer under "study_design" in data/reporting/study.json |
| 6 | Methods: study design | Study goal | declared (study_goal) | missing | needs the owner's answer under "study_goal" in data/reporting/study.json |
| 7 | Methods: data | Data sources | code (data_sources) | missing | needs PROVENANCE.json, from tools/licences.py provenance |
| 8 | Methods: data | Inclusion and exclusion criteria | declared (inclusion_exclusion) | missing | needs the owner's answer under "inclusion_exclusion" in data/reporting/study.json |
| 9 | Methods: data | Data preprocessing | code (transforms) | met | train/MODEL.md: torchvision resnet18, 27-way head, crops 64x64, pad 0.15. |
| 10 | Methods: data | Selection of data subsets | code (recipe) | missing | needs PROVENANCE.json, from tools/licences.py provenance |
| 11 | Methods: data | De-identification methods | declared (deidentification) | missing | needs the owner's answer under "deidentification" in data/reporting/study.json |
| 12 | Methods: data | How missing data were handled | code (missing_data) | missing | needs missing.json, which no step writes yet: missing fields per class from the catalog |
| 13 | Methods: data | Image acquisition protocol | declared (acquisition) | missing | needs the owner's answer under "acquisition" in data/reporting/study.json |
| 14 | Methods: reference standard | Definition of method(s) used to obtain reference standard | declared (reference_standard) | missing | needs the owner's answer under "reference_standard" in data/reporting/study.json |
| 15 | Methods: reference standard | Rationale for choosing the reference standard | declared (reference_standard_rationale) | missing | needs the owner's answer under "reference_standard_rationale" in data/reporting/study.json |
| 16 | Methods: reference standard | Source of reference standard annotations | declared (annotation_source) | missing | needs the owner's answer under "annotation_source" in data/reporting/study.json |
| 17 | Methods: reference standard | Annotation of test set | declared (test_annotation) | missing | needs the owner's answer under "test_annotation" in data/reporting/study.json |
| 18 | Methods: reference standard | Measures of inter- and intrarater variability of features described by the annotators | declared (rater_variability) | missing | needs the owner's answer under "rater_variability" in data/reporting/study.json |
| 19 | Methods: data partitions | How data were assigned to partitions | code (split_rule) | met | persons assigned to train, validation and test by the catalog's salted person hash, catalog 5adfe5ec5715 version 1 (RUN.json); the test part is read only by the evaluator |
| 20 | Methods: data partitions | Level at which partitions are disjoint | code (split_disjoint) | met | disjoint by person and by frame sha256: no person and no frame in two parts (split-check.json) |
| 21 | Methods: testing data | Intended sample size | declared (intended_sample_size) | missing | needs the owner's answer under "intended_sample_size" in data/reporting/study.json |
| 22 | Methods: model | Detailed description of model | code (model) | met | train/MODEL.md: torchvision resnet18, 27-way head, crops 64x64, pad 0.15. |
| 23 | Methods: model | Software libraries, frameworks, and packages | code (software) | met | the locked pixi environments of pixi.lock at commit cf0d3f03d5d9 |
| 24 | Methods: model | Initialization of model parameters | code (initialization) | met | from scratch, no parent weights (RUN.json); MODEL.md: none (from scratch). |
| 25 | Methods: training | Details of training approach | code (training) | met | stage level, 4 epochs, seed 1; 2728 training crops from 34 persons (train/checkpoint.json) |
| 26 | Methods: training | Method of selecting the final model | code (model_selection) | met | the epoch of best validation accuracy, epoch 4: 0.996 (0.985 to 0.999, n=472); no test row read in training (train/checkpoint.json) |
| 27 | Methods: training | Ensembling techniques | code (ensembling) | met | none: one network for the level stage (RUN.json) |
| 28 | Methods: evaluation | Metrics of model performance | code (metrics) | met | accuracy over 10 strata on the test part (evaluate/results.json) |
| 29 | Methods: evaluation | Statistical measures of significance and uncertainty | code (uncertainty) | met | a 95 percent Wilson interval on every row from its correct and n, persons counted per row (evaluate/results.json, evaluate/results.md) |
| 30 | Methods: evaluation | Robustness or sensitivity analysis | declared (robustness) | missing | needs the owner's answer under "robustness" in data/reporting/study.json |
| 31 | Methods: evaluation | Methods for explainability or interpretability | declared (explainability) | missing | needs the owner's answer under "explainability" in data/reporting/study.json |
| 32 | Methods: evaluation | Evaluation on internal data | code (internal_evaluation) | met | held-out test part of the same catalog: 431 crops, 119 frames, 5 persons (evaluate/results.json) |
| 33 | Methods: evaluation | Testing on external data | declared (external_evaluation) | missing | needs the owner's answer under "external_evaluation" in data/reporting/study.json |
| 34 | Methods: evaluation | Clinical trial registration | declared (trial_registration) | missing | needs the owner's answer under "trial_registration" in data/reporting/study.json |
| 35 | Results: data | Numbers of patients or examinations included and excluded | code (exclusions) | missing | needs exclusions.json, which no step writes yet: the ingest and bank builders' excluded and unreadable samples with their reasons |
| 36 | Results: data | Demographic and clinical characteristics of cases in each partition | code (covariates) | missing | needs covariates.json, which no step writes yet: age, sex, pathology and device per part (tools/covariates.py's census) |
| 37 | Results: model performance | Performance metrics and measures of statistical uncertainty | code (performance) | met | accuracy 430/431 on all levels with its interval, and every stratum beside it (evaluate/results.md) |
| 38 | Results: model performance | Estimates of diagnostic performance and their precision | code (performance) | met | accuracy 430/431 on all levels with its interval, and every stratum beside it (evaluate/results.md) |
| 39 | Results: model performance | Failure analysis of incorrectly classified cases | code (failure_analysis) | met | the confusion matrix and the per-level accuracy (evaluate/confusion.png, evaluate/per-level.png) |
| 40 | Discussion | Study limitations | declared (limitations) | missing | needs the owner's answer under "limitations" in data/reporting/study.json |
| 41 | Discussion | Implications for practice, including intended use and/or clinical role | declared (implications) | missing | needs the owner's answer under "implications" in data/reporting/study.json |
| 42 | Other information | Provide a reference to the full study protocol or to additional technical details | declared (protocol) | missing | needs the owner's answer under "protocol" in data/reporting/study.json |
| 43 | Other information | Statement about the availability of software, trained model, and/or data | declared (availability) | missing | needs the owner's answer under "availability" in data/reporting/study.json |
| 44 | Other information | Sources of funding and other support; role of funders | declared (funding) | missing | needs the owner's answer under "funding" in data/reporting/study.json |

## REFORMS

32 items: 13 met by the run's files, 0 declared, 0 not applicable, 19 missing.

| item | section | asks | answered by | state | evidence |
|---|---|---|---|---|---|
| 1a | Study goals | Population the claim is about | declared (population) | missing | needs the owner's answer under "population" in data/reporting/study.json |
| 1b | Study goals | Why that population | declared (population_rationale) | missing | needs the owner's answer under "population_rationale" in data/reporting/study.json |
| 1c | Study goals | Why machine learning | declared (ml_rationale) | missing | needs the owner's answer under "ml_rationale" in data/reporting/study.json |
| 2a | Computational reproducibility | Dataset with link or DOI | code (data_sources) | missing | needs PROVENANCE.json, from tools/licences.py provenance |
| 2b | Computational reproducibility | Code | code (code_state) | met | commit cf0d3f03d5d974d84e7d026a993ba14503664878 from a clean tree (RUN.json); the run is refused from a dirty one |
| 2c | Computational reproducibility | Computing infrastructure | code (compute) | met | local mode: split-check on runner, 0 GPU, 1 s, exit 0; train on local, 0 GPU, 99 s, exit 0; evaluate on local, 0 GPU, 19 s, exit 0 (RUN.json jobs) |
| 2d | Computational reproducibility | README with instructions | code (reproduce) | met | at commit cf0d3f03d5d9: python tools/flow.py run --catalog <catalog sha256 5adfe5ec5715> --mode local --stage level --epochs 4 --seed 1 --out <runs> |
| 2e | Computational reproducibility | Reproduction script | code (reproduce) | met | at commit cf0d3f03d5d9: python tools/flow.py run --catalog <catalog sha256 5adfe5ec5715> --mode local --stage level --epochs 4 --seed 1 --out <runs> |
| 3a | Data quality | Data sources per split | code (data_per_split) | missing | needs PROVENANCE.json, from tools/licences.py provenance |
| 3b | Data quality | Sampling frame | declared (sampling_frame) | missing | needs the owner's answer under "sampling_frame" in data/reporting/study.json |
| 3c | Data quality | Why the dataset fits the task | declared (fitness_rationale) | missing | needs the owner's answer under "fitness_rationale" in data/reporting/study.json |
| 3d | Data quality | Outcome variable and its statistics | code (outcome_counts) | met | test crops per level: L1 53, L2 66, L3 79, L4 86, L5 60, T11 15, T12 33, sacrum 39 (evaluate/results.json) |
| 3e | Data quality | Sample size and outcome frequencies | code (sample_size) | met | train 2728 crops from 34 persons, validation 472 from 6, test 431 from 5 (train/checkpoint.json, evaluate/results.json) |
| 3f | Data quality | Missing data, by class | code (missing_data) | missing | needs missing.json, which no step writes yet: missing fields per class from the catalog |
| 3g | Data quality | Representativeness | declared (representativeness) | missing | needs the owner's answer under "representativeness" in data/reporting/study.json |
| 4a | Data preprocessing | Excluded samples, with the reason | code (exclusions) | missing | needs exclusions.json, which no step writes yet: the ingest and bank builders' excluded and unreadable samples with their reasons |
| 4b | Data preprocessing | Corrupt samples | code (exclusions) | missing | needs exclusions.json, which no step writes yet: the ingest and bank builders' excluded and unreadable samples with their reasons |
| 4c | Data preprocessing | All transforms, from raw data to the model's input | code (transforms) | met | train/MODEL.md: torchvision resnet18, 27-way head, crops 64x64, pad 0.15. |
| 5a | Modeling | All models trained | code (models_trained) | met | run cd37124c487d; every run of the flow, failed ones too, has its row in LEDGER.md beside the runs |
| 5b | Modeling | Why these model types | declared (model_rationale) | missing | needs the owner's answer under "model_rationale" in data/reporting/study.json |
| 5c | Modeling | Evaluation method and splits | code (split_rule) | met | persons assigned to train, validation and test by the catalog's salted person hash, catalog 5adfe5ec5715 version 1 (RUN.json); the test part is read only by the evaluator |
| 5d | Modeling | How the reported model was chosen | code (model_selection) | met | the epoch of best validation accuracy, epoch 4: 0.996 (0.985 to 0.999, n=472); no test row read in training (train/checkpoint.json) |
| 5e | Modeling | Hyperparameter tuning | declared (tuning) | missing | needs the owner's answer under "tuning" in data/reporting/study.json |
| 5f | Modeling | Appropriate baselines | declared (baselines) | missing | needs the owner's answer under "baselines" in data/reporting/study.json |
| 6a | Data leakage | Preprocessing fit on training data only | declared (preprocessing_fit) | missing | needs the owner's answer under "preprocessing_fit" in data/reporting/study.json |
| 6b | Data leakage | Dependencies and duplicates across splits | code (split_disjoint) | met | disjoint by person and by frame sha256: no person and no frame in two parts (split-check.json) |
| 6c | Data leakage | Each feature legitimate | declared (feature_legitimacy) | missing | needs the owner's answer under "feature_legitimacy" in data/reporting/study.json |
| 7a | Metrics and uncertainty | All metrics | code (metrics) | met | accuracy over 10 strata on the test part (evaluate/results.json) |
| 7b | Metrics and uncertainty | Uncertainty and how it was computed | code (uncertainty) | met | a 95 percent Wilson interval on every row from its correct and n, persons counted per row (evaluate/results.json, evaluate/results.md) |
| 7c | Metrics and uncertainty | Statistical tests and their assumptions | declared (statistical_tests) | missing | needs the owner's answer under "statistical_tests" in data/reporting/study.json |
| 8a | Generalizability and limitations | External validity | declared (external_validity) | missing | needs the owner's answer under "external_validity" in data/reporting/study.json |
| 8b | Generalizability and limitations | Where the findings will not hold | declared (non_generalization) | missing | needs the owner's answer under "non_generalization" in data/reporting/study.json |
