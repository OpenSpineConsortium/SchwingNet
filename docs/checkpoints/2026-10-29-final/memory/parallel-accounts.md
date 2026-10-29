---
name: parallel-accounts
description: greg's two other Claude accounts started 2026-10-27 22:20-22:28 UTC (spine-program datamining; bordercall model improvement), their handoff docs, what they hold, and that neither has left anything on GitHub
metadata:
  type: project
---

On 2026-10-27 greg moved two pieces of work to other Claude accounts in the organization, each with a handoff Claude Doc written by the thread "Flesh out Panjabi, rewrite in PyMC":

- 22:20 UTC, datamining: spine-program synthetic_spine/, a long table of every measurement in the 42 papers, read twice blind from the page (issue #237 first). Handoff: https://claude.ai/artifact/16VF366Ttc7uBsL4xMqxvx ("Handoff: every measurement in the 42 papers, read from the page"), with no paper numbers in it on purpose (readers stay blind). greg: "PLEASE DONT STOP DOING EXACTLY WHAT YOU ARE DOING". It plans a recorded literature search too (decision 5 of [[decisions-2026-10-28]]).
- 22:28 UTC, model improvement in bordercall, from greg's upload "Vertebral Labeling Graph Prior Art" (a machine-written review; numbers unverified). Handoff: https://claude.ai/artifact/VwwU3XA5QEaziHcnJDhucP ("Handoff: improving the naming model"). Its order: 1 what earlier labelling graphs already do (Meng 2021's graph reportedly has T13/L6 insert and bypass edges; VerSe labels L6=25 T13=28; profile HMMs are older); 2 anomalous places in the exact rule (TODO item 6); 3 model criticism and the abnormal body (7.2); 4 the CT-table estimator on synthetic columns (item 5, a Gaussian copula with an LKJ prior). greg's words of 23:55 UTC ("let the other move onto 4") may have sent it to item 4 first.

By 2026-10-28 21:25 UTC neither account had a branch, issue or pull request on GitHub, and #237 is unclaimed. Whether greg launched them is one of his open questions. Overlaps if they start: #237 meets spine-program #239 in synthetic_spine (README, HANDOFF, check script), which its handoff does not know; PR 20's placeholder L6 and T13 columns (chain.extended_table) are what the model account's item 2 replaces, and PR 20 holds requirements-schwingcheck.txt until it merges. The one-vertebra evaluation and the fixed-k NUTS review each account thinks the other holds.

**Why:** two other sessions may work beside this project; a later thread must not duplicate them or edit across the boundary.
**How to apply:** check bordercall's and spine-program's open PRs before touching files outside the named work; never take the model account's items 1 to 4 without greg's word. Related: [[item-p-state]], [[closed-papers-check]].
