# What else does what the packaged framework would do

Source: the thread "Build plug-and-play training experiment framework", 2026-10-25, answering the owner's questions of 05:12 UTC ("are there any analogues to what i would provide? do they charge? are they better or worse?") and 09:04 UTC ("How Claude intrinsic to the workflow differ from using the AI scientist with one of those analogs"). Prices were read from the vendors' pages or the named sources on 2026-10-25, unless a line gives another date. It landed with the pull request of #252, before the account that wrote it handed over; #293 is where the framework is packaged.

## Short answer

No single product does all of it. Most of the pieces exist separately, and most of those are free:

- The engines and the imaging frameworks are open source.
- The experiment trackers charge companies but are free for academic research.
- Platforms that manage imaging data or host the pipeline engine are sold by quote.

What is distinctive is the combination, and one piece in particular: a proof, before real training, that every combination of blocks the rules allow runs on every dataset held. Even that idea has prior art: a granted SAS patent covers validating a machine-learning system's hyperparameters with a covering array (below).

On quality, the big frameworks are far more proven and much broader. This one is narrower and has not run on the grid yet. Its advantages are by design, and none of them is measured.

## What the package would hold (issue #293)

1. Training blocks you swap by name, with a check that reads a catalog and trains nothing to say which combinations work.
2. Covering plans that train every option and every interacting pair of options, on synthetic and real data, annotated and unannotated.
3. A versioned, content-addressed data catalog with splits keyed by person, leak checks and licence classes.
4. Metaflow pipelines for bank, catalog and sweep, with Metaflow's native resume and run folders named by configuration.
5. A record for every number: its interval, its commit, its catalog hash, witness frames, W&B, and the experiments page.
6. Claude in the loop through GitHub: experiments requested by issue, the research loop, and results read into the textbook, all under the lab's rules.

## Analogues, piece by piece

| Piece | Closest analogues | What they charge |
|---|---|---|
| 1, 2: blocks and the combination proof | nnU-Net and MONAI Auto3DSeg, which configure themselves rather than let you swap parts; MONAI Bundles, configs that can be shared. For the proof itself: SAS's patented covering-array validation (US 11,074,483) and the combinatorial-testing literature. No packaged tool for training configurations was found. | MONAI and nnU-Net are free (Apache 2.0). The patent is SAS's, and JMP, SAS's paid statistics software, lists it among its patents. |
| 3: the data catalog | Flywheel (a commercial imaging data platform with containerised "gears"); Kaapana (DKFZ, open source: PACS, Airflow workflows on Kubernetes, deployed at all 36 German university hospitals through RACOON) | Flywheel publishes no price: free trial, then sold by quote. Kaapana is free. |
| 4: pipelines with resume | Metaflow itself; Outerbounds, the managed Metaflow, which Anaconda bought (announced 2026-04-29); ZenML, Kedro and Flyte are similar engines | Metaflow is free (Apache 2.0, and Anaconda says it stays so). Outerbounds is now sold as Anaconda's platform, "contact sales". |
| 5: tracking, sweeps, live views | Weights & Biases (now sold through CoreWeave), Comet, ClearML, MLflow; Neptune.ai is gone (OpenAI bought it, and its hosted app shut down on 2026-03-04) | W&B: free for 5 seats; Pro from $60 a month; academic free (up to 100 seats, 200 GB, unlimited tracked hours). Comet: free for 1 user; Pro $39 per user a month; academic free Pro. ClearML: free self-hosted; Pro $15 per user a month plus usage (ZenML's summary, 2025-06-15). MLflow: free. |
| 6: AI that runs the research | Sakana's The AI Scientist (open source, idea to paper); AIDE, Agent Laboratory and similar agents | The software is free. The AI Scientist's authors report about $15 of model cost per paper. |

## Better or worse

Where the analogues are better:

- **Proven.** nnU-Net and MONAI have years of benchmarks and large communities, and nnU-Net is a baseline that is hard to beat. This framework has run only on a CPU in a container. The grid smoke will be its first real test.
- **Broader.** They cover 3D segmentation and many modalities. This one is built for 2D X-ray classification on one Slurm grid, through Beethoven's runner.
- **Polished.** W&B, Comet and ClearML have dashboards, team features and support. This framework uses W&B for its live views rather than replacing it.
- **Better at data management.** Flywheel and Kaapana handle DICOM, PACS, de-identification and federated work at hospital scale. The catalog here is a research catalog on one volume.
- **Maintained by others.** This one has one owner, no community and no support, and it is not yet importable (#293).

Where this framework is better, by design and not yet measured:

- **One identity across every piece.** Blocks, the proof, the catalog, resume, the record and Claude all share one run identity. With the analogues, the same work means gluing four or five tools together.
- **The proof that every allowed combination runs on every dataset** before a GPU hour goes to real training. None of the analogues offers this for training configurations, and the self-configuring frameworks decide the configuration for you instead.
- **A stricter record per number.** Every number carries its Wilson interval, commit and catalog hash, and is reproduced by a command. The trackers record what you log, not a contract on what a number means.
- **Claude inside the lab's rules.** Claude works under the claims, the size rule and the owner's word before grid jobs. The research agents run unsupervised in a sandbox, and their papers are judged mainly by their own AI reviewer.
- **No seats to pay for.** It runs on your own grid. The Claude part needs a Claude subscription and GitHub.

## Claude in the workflow beside the AI Scientist on a tracker

The owner asked how Claude built into this workflow differs from running Sakana's The AI Scientist with one of the analogues, such as W&B or MLflow. The difference is who sets the question and who grades the answer.

- **The question.** The AI Scientist starts from a code template, invents its own ideas, writes the code, runs it and writes the paper in one unsupervised loop. Here the research loop (.github/workflows/research.yml) takes the next item from the textbook's ranked claims, one at a time, and every change it makes lands as a pull request that the required check has to pass.
- **The grading.** Its papers are scored mainly by its own AI reviewer. Here a number counts only when it comes from a recorded run: the fixed real witness frames, Wilson intervals, a folder named by its code and catalog, and a command that reproduces it.
- **The rules.** It knows nothing of the size rule, the data use agreements, confidentiality before the filing or the claim protocol, so it would have to be sandboxed and policed by hand. Here those rules are written into the code and the gate, and the images never leave the grid.
- **Cost.** It runs on API keys, about $15 of model cost per paper by its authors' count. Here Claude runs on the owner's subscription, with no API billing.
- **Where it is better.** It explores many new ideas on its own, checks them against the literature and drafts a whole paper. This workflow trades that freedom for results that can be trusted and reproduced, so it is slower to wander into something new.

Neither has been run against the other on this data, so these are differences by design, not measured ones.

## Prior art to know about

- US Patent 11,074,483, "Tool for hyperparameter validation", is assigned to SAS Institute Inc. and was granted on 2021-07-27 (inventors Morgan, Lekivetz, King and Jones). It claims validating a system's response, a machine-learning system with hyperparameters among its factors, by building a covering array of strength t over the factors, running the resulting test suite and reporting the deviation from a specified result.
- That is close to the block smoke: a covering array over the blocks, each row run, and the outcome set against the check's prediction.
- So the covering-array smoke is not new. Whether the patent matters for using or selling the package is a question for the patent attorney, alongside the WSU rights question. This note is not a legal reading.

## What the market pattern suggests

- The engines and imaging frameworks are free.
- Money comes from hosting, compute, support and enterprise compliance (Outerbounds, Flywheel, the trackers' paid tiers).
- Academic research is usually free.

A package like this one would fit that pattern as a free core, with any paid part being hosting or support. Any decision to charge waits on the filing, the WSU rights question and the patent question.

## Sources

- Weights & Biases pricing (wandb.ai/site/pricing redirects to https://coreweave.com/forge-pricing), read 2026-10-25.
- Comet pricing: https://comet.com/site/?p=3968, read 2026-10-25.
- ClearML pricing summary: https://www.zenml.io/blog/clearml-pricing (2025-06-15).
- Neptune's shutdown: https://www.infoworld.com/article/4101200/openai-to-acquire-ai-training-tracker-neptune.html (2025-12-04).
- Anaconda and Outerbounds: https://www.opensourceforu.com/2026/05/metaflow-at-the-core-as-anaconda-acquires-outerbounds/ (2026-05-04); outerbounds.com/pricing redirects to https://www.anaconda.com/pricing.
- Metaflow sharing (2.16 and later): https://docs.metaflow.org/metaflow/composing-flows/introduction.
- MONAI Model Zoo: https://cdn.jsdelivr.net/gh/Project-MONAI/model-zoo@dev/README.md.
- Kaapana: https://kaapana.readthedocs.io/en/master/intro_kaapana.html.
- Flywheel listing: https://www.capterra.com/p/250450/Flywheel/.
- The AI Scientist: https://aiagentindex.mit.edu/2024/the-ai-scientist.
- US 11,074,483: https://community.jmp.com/t5/Patents/Tool-for-hyperparameter-validation/ta-p/928144 and https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11074483.
