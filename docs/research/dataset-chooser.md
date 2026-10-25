# The dataset chooser

Source: the thread "Fit datasets under the 20 TB cap", 2026-10-25. At 04:14 UTC the owner asked: "what id like ultimately is an automated process, deterministic if possible, for choosing datasets to use to both train a network and be able to test it with sufficient power on normal spines, in the fluoroscopic domain". At 04:15 they said every other experiment is secondary to it. Issue #291. The tool is tools/choose_data.py, its settings are data/choice/settings.json, and its output is data/choice/CHOICE.json. The evidence behind its rules is docs/research/final-dataset-recipe.md. Confidential with the rest of this repository.

## 1. What it does

The chooser reads five inputs and writes one file:

- the records under data/sources/;
- the licence classes in data/licences.json;
- the recipe the settings name, from data/recipes/;
- the frozen persons in data/splits/test-persons.json;
- the owner's settings.

The output carries the sha256 of every input. `python3 tools/choose_data.py check`, and the test tests/test_choose_data.py, fail when the committed file is not what the inputs give now. So the choice is deterministic: the same records, licences and settings always give the same sets. A changed record changes the choice in the pull request that changes the record, where it can be read.

## 2. The rules, in order

1. A set is a candidate only if it is held on the grid. Records that are not held are listed as the fill (rule 6).
2. A held set whose licence class the recipe does not take is excluded, with its reason. A licence the rule left unknown always excludes, because no recipe takes unknown (tools/licences.py). The owner's reading in data/licences.json is what admits such a set.
3. A set named in the settings' never_train is excluded with its reason. Today that is the two recorded demo sweeps.
4. The test is the held sets of the test groups (fluoroscopy) whose levels people read. They are counted by person, from the record's patients, subjects, people, persons, cases or specimens. Within each set:
   - frozen persons are taken out, because the transitional persons and the demo sweeps are tested on their own;
   - the settings' device persons go to training;
   - the rest are test.
   Which persons go to training is fixed by a hash, written in the output's assign line, with the salt of data/splits/rule.json, so the catalog can apply it.
5. The people the test needs are the least n whose Wilson interval at the expected accuracy is no wider than the half-width. Wilson is used because it holds near 0 and 100 percent, where the normal approximation asks for too few.
6. If the held test falls short, the fill lists the records not held, in the fill groups, with a person count, ranked by people, and marks where the running total closes the gap.
7. Training is every other held set the recipe takes, with a role read from the record:
   - render source, for CT with levels;
   - real device frames with levels;
   - real films with levels;
   - real frames with some levels or anchors;
   - appearance, for real frames with no levels.
   CT with no levels is excluded, since it gives neither truth nor renders with names.

## 3. Why these settings

- Power: a half-width of 0.05 at 95 percent confidence and an expected accuracy of 0.5. This is the storage feed's own power (spine-datasets storage.py), so the chooser and the storage panel ask for the same thing. By Wilson it needs 381 people, where the feed's normal approximation says 385. The output lists what other choices need: 83 people at an expected 0.95 with a half-width of 0.05, 215 at 0.95 with 0.03, and 1,064 at 0.5 with 0.03. The lateral accuracy measured on an unseen C-arm is 96.4 percent (state-of-knowledge.md row 1), so 0.95 is defensible. Choosing it is the owner's call, since it assumes the result before the test.
- Device persons: 12. A device's first ten to twelve frames reach 95 percent of the plateau (state-of-knowledge.md row 4). Set it to 0 to make the test zero-shot.
- Recipe: research-internal, the study's own network inside the project. With commercial, only open sets the owner has reviewed remain.

## 4. What it chooses today

On the records at the commit that adds it:

- The test holds 132 persons with normal spines, all from C-ArmLSpine: 149 cases, less the 5 frozen and the 12 kept for training. DeepFluoro's 6 specimens all go to training. Ljubljana gives no person count, so it is listed as uncounted.
- 381 are needed, so the test is short by 249. With 132 people the half-width reached at 0.5 is 0.084.
- The gap closes first at LUMOS (803 patients, not held). Its levels come only through a registration to its paired CT. After it come the embargoed COBRA cases, Vanderbilt's 146 and Huashan's 140.
- Training takes 16 sets and excludes 13. Twelve of the 13 are excluded for an unknown licence, among them BUU, CSXA and both NHANES II sets. Reading those licences is what most enlarges training.

Every test person is lumbar, from one device. The chooser can only say that the test is normal-spine lumbar fluoroscopy from one mobile C-arm until a cervical or thoracic fluoroscopy set with levels is held. The recipe note's gaps say none exists anywhere searched.

## 5. What it does not do

- It reads records, not images. A person count, a level-truth phrase or a licence line that is wrong in a record is wrong in the choice. The fix belongs in the record, and the choice follows in the same pull request.
- It does not call a spine normal from images. "Normal" means not among the frozen persons. In C-ArmLSpine that removes the three real L6 persons the archive names. An anomaly no record names stays in the test.
- It sets no ratio of synthetic to real frames inside training. That is the block sweep's samples block (#202).
- It does not move or fetch any data, and starts no grid job.
