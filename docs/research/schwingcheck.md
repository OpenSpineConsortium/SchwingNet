# SchwingCheck: the white paper, its records and the segmentation-free device

The thread "Finish CNS slides with junction predictor", 2026-10-26 and 2026-10-27, confidential-method,
from the owner's asks of 26 October 21:18 UTC (a white paper comparing the method with LevelCheck in
provable statistics, with the spec of a randomized browser study of surgeons) and 27 October 03:15 UTC
(add it to the textbook, with diagrams of SchwingNet, SchwingCheck and a device that reads the
measurements with no segmentation). The paper is the Claude Doc
https://claude.ai/artifact/4VwMe9CKMX87s4jiEJBpRE, which the owner rewrote into three pathways.

Where things are:

- The paper, revision 188, is chapter 36 of the textbook
  (docs/textbook/36-schwingcheck-an-explainable-bayesian-check-on-vertebral-labels.md), whole, with
  its five figures under docs/textbook/figures/36/, drawn by tools/schwingcheck_figures.py from
  tools/schwingcheck_records.json, which copies each number from the record it names.
- The same text and every computation behind it are in OpenSpineConsortium/bordercall, private:
  docs/SCHWINGCHECK_LEVELCHECK.md at 6ceb475, records/exact-2026-10-26/ (the exact rule, at 00f969f)
  and records/whitepaper-2026-10-26/ (the second opinion, the latency, the anomalous columns counted
  from C2, the power of the two-arm and three-arm reader studies), with HANDOFF.md step 11.

What this session found that the paper does not say:

- Each of SchwingCheck's seven measures is a distance between landmarks or from a landmark to a
  line, so none needs an outline. SchwingNet's corner detector places four landmarks per body
  today; three are new, the medial borders of the two pedicles on an AP view and the spinolaminar
  point on a lateral (chapter 36, figure 36.4).
- A device that places seven landmark types in one pose pass and turns their distances into
  millimetres would replace SchwingCheck2D's segmentation step. Only the corner detector (6.8 ms
  per image, hardware not named) and the posterior (13.6 ms median for three bodies on four CPUs)
  exist and are timed; they are not one end-to-end time (figure 36.5).

Open, in the order a test would settle them: the rule on real spines (the existing SPINEPS masks of
full-spine CTs counted from C2, the bordercall pilot, unsent until the owner's word); anomalous
places in the rule; a landmark head for the three new landmarks with its error in millimetres; and
whether the shared size factor absorbs a wrong magnification.
