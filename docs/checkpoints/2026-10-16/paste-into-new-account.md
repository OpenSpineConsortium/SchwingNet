# What to paste into the new account's Project, 2026-10-16

Source: the thread "Checkpointing all threads", 2026-10-16 at 19:40 UTC, on the owner's ask at 19:33 UTC for an updated handoff to paste as the new Project's prompt, instructions and goal. The three blocks below are that handoff, brought up to the moment every thread had pushed its work and stopped and symphony-template#117 had merged handoff.md, memory.md and owner-todo.md beside this file. When you make the new Project (handoff.md, part 1, "Moving to another account or a new Project"), copy the goal into the Project's goal field and the instructions into its instructions field, then send the prompt as the first message in its chat.

## 1. Prompt: the first message in the new Project's chat

```
Pick up Symphony where the last Project stopped on 2026-10-16 at about 19:40 UTC. Every thread pushed its work, intermediate or final, research and state included, and stopped, and the handoff merged as symphony-template#117. Before anything else, read docs/checkpoints/2026-10-16/handoff.md in OpenSpineConsortium/symphony-template and the files beside it: memory.md (the last Project's memory; save it as this Project's memory) and owner-todo.md (my own steps, each with its link and what to click). Each open pull request begins its description with a "Checkpoint 2026-10-16" section saying exactly where its thread stopped; it is newer than the handoff where they differ.

First land what the last threads left open in symphony-template, where still open: #119 (the protocol thread's state and plan) and draft #123 (the token wizard's probes, fuzz and mutants). Bring main in by merge, run bash scripts/check.sh, and merge each once green.

Then start one thread per workstream below, at most three at once, each reading its part of handoff.md (part 2) first, starting from the brief given there, and attaching the repositories it needs with push access:
1. Protocol fixes after 0.5.0 in symphony-protocol (part 2.1): review and merge draft #42 (F22) first, then finish #41 (F23), #43 (F25), #44 (F26) and the findings with no pull request yet (F24, F27) toward 0.5.1, by the plan in docs/research/protocol-fixes-after-0-5-0/README.md; vendoring into the template waits until I publish 0.5.0; never the release or its approval gate.
2. The curse-of-coordination full run in coordbench (part 2.3): merge draft #27 once green, then resume the full run where it stopped (179 of 215 runs done, 36 paused) by bench/cooperbench/results/curse-of-coordination-notes/README.md, then record the full run by pull request; no bench run beyond what I already chose.
3. Symphony beyond cooperation in symphony-template (part 2.4): fix the review's findings on draft #116 (step 2, PROFILE.json) and land it, then step 3.
The others wait on me (part 2 says what each needs): the grant's submission, the 0.5.0 approval, the control panel's sign-in steps, Beethoven's store submission, the grid's three steps and the flowbench pilot. Start each one's thread when I send what it waits on or ask for it.

Rules
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
```

## 2. Instructions: the Project's instructions field

Your instructions as the last Project had them, word for word, then your two conventions from 2026-10-16, each on a line of its own that you can delete. If the new account should run no adversarial reviews, as you asked at 19:15 UTC while short of usage, also delete the sentence "Run an adversarial review before each substantive pull request."

```
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
Commit what you find, intermediate or final, under docs/research/ in symphony-template with its line in docs/research/README.md, by pull request, before you stop.
Put every manual step for me in the reply's own text, numbered, never only on a card, in a widget or in a file.
```

## 3. Goal: the Project's goal field

```
Build Symphony, OpenSpineConsortium's open coordination product for Claude Code, and prove that it works. Symphony lets many Claude sessions, routines and GitHub Actions workers share one repository without stepping on each other: the claim protocol as a library (symphony-protocol), the template that keeps a Claude project as files in a repository (symphony-template), the two GitHub Apps and the one-press front door, the plugin, and the control panel on openspineconsortium.com. The proof is measured: replicate CooperBench's curse of coordination and remove it with Symphony's protocol (coordbench), benchmark agentic workflows (flowbench), and go beyond cooperation against MAST's failure modes. This Project also carries my related work: the AIDaS spine grant (spine-program), the Beethoven extension and Symphony on the WSU grid. Done for now means the protocol fixes released as 0.5.1 and vendored into the template, the open pull requests landed, and the full coordination run recorded with its results.
```
