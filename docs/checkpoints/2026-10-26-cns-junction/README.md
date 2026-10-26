# The CNS junction checkpoint of 2026-10-26: bordercall, the slides and the unsent pilot

Source: the thread "Finish CNS slides with junction predictor" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written at 03:10 UTC on 2026-10-26 on the owner's words of 03:01 UTC ("push as much as possible now im running out of tokens then write a handoff for checkpointing asap") and 03:02 UTC ("makesure all files needed to continue in antoher account's new project are pushed to git"). The project-wide restart page is the #391 audit thread's; this page is the confidential companion for the junction work and stays in SchwingNet.

## 1. Where everything is

- OpenSpineConsortium/bordercall (private): the method (bordercall/), its tests (31), the recorded Panjabi runs (records/panjabi-2026-10-26/), the five figures with their CSVs, captions and FIGURES.md (records/panjabi-2026-10-26/figures/) and the six CNS slides as PowerPoint and PDF (slides/). Its HANDOFF.md opens with the table of what is where and the command that rebuilds each piece. Pull request #1 is merged; the pull request that adds the figures and slides is open from the branch claude/project-thread-7qoboa.
- The deck's template is the owner's CNS deck, held in spine-program at provisional_patent/wsu_tto/TTO_package_2026-09-25/followup/CNS2026_spine_talk_v10_2026-09-26_CNS_template_ACCME.pptx; bordercall does not hold it.
- Here, on main since #404: grid/gate.sh's word bordercall with the stages pilot and full, grid/bordercall.sbatch, tools/bordercall_corpus.py (the count from C2 over the census's existing SPINEPS masks, the ribs from the census's rib table, never a re-run and never TotalSegmentator), grid/bordercall/ (the bordercall package vendored at 6938a2e, held by tools/bordercall_vendor.py and check.sh), and the research note docs/research/bordercall-corpus.md. The memory line is docs/memory/bordercall-on-the-grid.md.
- The pass-through from a dispatch to the gate: symphony-template's grid-accounts.yml takes the word schwingnet-bordercall-STAGE (#495, merged 2026-10-26 03:08 UTC) and hpcworker's tools/grid_gate.sh passes schwingnet bordercall STAGE through (#50, its review section added 03:04 UTC and its check re-run; merge it before anything is sent, then send update).

## 2. The grid pilot, approved and unsent

The owner's count, 2026-10-25 23:56 UTC: two CPU jobs, a pilot of a few hundred countable cases, then the full corpus. Nothing has been sent. The order, each a dispatch of symphony-template's grid-accounts.yml with action job:

1. update, once hpcworker #50 is merged, so the gate's clones are at main.
2. schwingnet-status, once; the last status read was sent 2026-10-25 23:41 UTC (nothing live, 4,416 GB free). Never twice for one read.
3. schwingnet-bordercall-pilot. Read its report from the job log on symphony-template's branch grid. A pilot that reaches no countable case stops at bordercall's own refusal (sweep scores only countable records, and the report says countable 0): then stop and tell the owner, as the prompt says ("find a corpus that qualifies instead", never --allow-uncountable).
4. schwingnet-bordercall-full, only if the report says countable > 0 and the pilot ended well (bordercall_pilot_ended_well in grid/gate.sh). A third job of any kind needs the owner's word and count again.

What the pilot answers that the slides do not: the published T12/L1 answer (AUC 0.988, 95%, 97/36/50 by phenotype) against a count from C2 on real masks; the per-class tables with denominators; the rib arm beside the circular arm (bordercall's disagree); the sweep's winner with its typical-versus-worst gap.

## 3. What the slides claim, and what they do not

Every number on the six slides is read from records/panjabi-2026-10-26/ in bordercall, a predictor fitted to Panjabi's published tables and scored on synthetic columns drawn from them: no CT, no patient and no SPINEPS mask has been measured yet. In those records a window of eight bodies names C7/T1 exactly in 85.6 percent of 250 windows and within one level in 98.4 percent; T12/L1 is the hard junction, exact in the sixties and within one in the nineties; by class (500 windows each) C7/T1 is exact in 85.2 percent of every class and T12/L1 in 59.4 to 65.2 percent; a lumbosacral twin changes the call at either junction in 0.4 to 0.8 percent of 500, which is the robustness to lumbosacral anomalies the owner asked for. At a thirteenth thoracic body the count and the ribs name the junction one level apart and the shape cannot choose: the TLTV case is scored against both truths and is not solved.

## 4. The owner's rules from this thread

- Only full-spine C2-to-pelvis CTs are ground truth (00:16 UTC); nothing from the 802 CTSpinoPelvic1K columns is reported as a result.
- SPINEPS masks that already exist, never re-run, never TotalSegmentator (00:17 UTC).
- Figures in Benzel's style, with the code that makes every figure committed and runnable from recorded inputs (01:17 UTC).
- The OneDrive upload is stopped (02:48 and 02:55 UTC). junction_twins.pdf is the one verified copy in the owner's Documents/bordercall_figures and stays; nothing else is uploaded.
- The public deck: count-free naming from morphometry sat near Part A of the provisional and was left out of v12_public, so the owner checks with the TTO before showing these six slides.

## 5. Not known

The identifier map of a new corpus is assumed until printed and checked (bordercall's trap 1); only the lumbar measurements are validated against published norms (trap 2); every figure is synthetic until the pilot reports; and whether a rib on a nineteenth body is a thirteenth thoracic vertebra or a rib on L1 is settled only by the count from C2, which is what the pilot brings.
