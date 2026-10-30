# Draft: asking FleXray's author for what the FluXray reproduction still lacks

Drafted 2026-10-29 in the thread "Reproduce the FluXray dataset" on greg's request of 15:11 UTC. Nothing has been sent. Two versions follow, an e-mail and a GitHub issue, over one numbered list of what the paper (arXiv 2609.26756v2), the package (flexray 1.0.2) and the Hugging Face releases (VictorButoi/flexray, VictorButoi/flexray-data) do not record. The list was built by reading all three against the reproduction; every item is something the code had to guess or stand in for.

## Before sending: four things only greg decides

1. The address. No e-mail address of Victor Butoi has been verified from an institutional page or a paper; the package names only "FleXray contributors" and https://victorbutoi.github.io/. Take the corresponding author's address from the first page of the paper's PDF or from that homepage before sending, as the letter rule asks.
2. E-mail or issue. The e-mail goes from the Wayne State Outlook under the [XR/CT Imaging Research] tag and reaches one person privately. The issue at https://github.com/VictorButoi/FleXray/issues is public under greg's GitHub login for as long as the repository exists, and every answer is public too. Recommendation: the e-mail, with the issue held back unless there is no answer in two weeks, since the issue can be opened later but not made private afterwards.
3. What the letter reveals. Either version says that we are reproducing FluXray's generation, which means running FLUX.2 over DRRs ourselves, and asks for training seeds and an unreleased segmentation network. That is about their pipeline, and neither version names SchwingNet, this repository, fluoroscopy, vertebral levels or anything we build or train; but a reader can infer that the asker generates X-ray images with a diffusion model. The standing rule for letters is that no external text implies that a model or training is built or used on our side; this ask cannot be made without that inference, so greg decides whether it is acceptable here.
4. Length. The letter rule asks for a short e-mail. The e-mail body below is short and carries the six asks that matter most; the full numbered list is offered as an attachment or as the issue. Trim the list if that is still too much.

## E-mail version

Subject: [XR/CT Imaging Research] FluXray reproduction: the settings and seeds the paper does not record

Dear Dr. Butoi,

I study the application of computer science to improving spinal health, and my current work needs a faithful reproduction of the FluXray dataset and of the FleXray training run your paper describes (arXiv 2609.26756v2), so that what I measure against FluXray is measured against the same generation and not a stand-in. I have built the reproduction from the paper's appendix, flexray 1.0.2 and the two Hugging Face releases, and I would be grateful for whatever of the following you can share, in any form, including a pointer to a file in the repository I have missed.

1. The script that ran FLUX.2 klein-9B over the raw DRRs, with the seeds it used, the exact prompt string and the pipeline call (dtype, image size, how the DRR entered the pipeline and how the result was converted to grey).
2. The raw-only U-Net that scored the paired filter, its weights and config, and the exact soft Dice it was scored with (which channels, how the background was handled); or, failing the weights, the list of the 5,667 samples the filter dropped.
3. The map from FluXray's subject ids to ENHANCE.PET's study numbers, and which CTs were used (FluXray names 1,597 subjects; ENHANCE.PET 1.6k holds 1,683).
4. The raw rendering settings not in the appendix: the HU window, the air clamp, the ray samples, the pose convention and isocentre, the label source and MOOSE version, the threshold the projected masks were made with, and how the 1024-pixel renders were brought to 256.
5. The training seeds beyond base.yml's 40: whether each ensemble member, the data loaders and the online DRR sampler were seeded and with what; the per-member data mixture and splits; the batch size and workers the config leaves as '?'; the epochs actually run and how the checkpoint was chosen.
6. The hardware, precision and package versions the released weights were trained with, and the ONNX export settings.

A full numbered list of what I could not recover is attached, in case it is easier to answer against. Thank you for releasing FleXray and FluXray so completely; the gaps above are the last ones.

With kind regards,

Gregory Schwing, MD, PhD
General Surgery, Wayne State University School of Medicine / Detroit Medical Center

## GitHub issue version

Title: Reproducing FluXray and the FleXray training run: the settings, seeds and weights the paper does not record

Body:

I am reproducing the FluXray dataset and the FleXray training run from the paper (arXiv 2609.26756v2), flexray 1.0.2 and the Hugging Face releases (VictorButoi/flexray, VictorButoi/flexray-data), so that a measurement against FluXray is a measurement against the same generation. The numbered list below is everything I could not recover from those three sources; each item is something my reproduction had to guess or stand in for. Pointers to files I have missed are as welcome as answers.

(the full list follows, as under "The full list" below)

Thank you for releasing FleXray and FluXray so completely; these are the last gaps.

## The full list (the attachment of the e-mail, the body of the issue)

The FluXray generation (the paper's appendix on the data engine):

1. The edit script itself: the code that ran FLUX.2 klein-9B over the raw DRRs.
2. The seeds the edits were drawn with (one per image, one per run, or none), and the generator used.
3. The exact prompt string, character for character, and any negative prompt.
4. The pipeline call: the dtype, whether the DRR entered as 8-bit or float and as grey or RGB, the height and width passed, the scheduler, the number of steps and guidance as called (the appendix gives 4 steps and guidance 1.0), the Hugging Face revision of the model and the versions of diffusers, transformers and torch.
5. How the edited image was converted back to grey, and whether the 1024-pixel edits and the raw 1024-pixel renders still exist and could be released.
6. The stored size: how the 1024-pixel images were brought to 256 (the resize filter), whether the 0.05 intensity floor was applied before or after the resize, and how the 256-pixel masks were made (projected at 256, or resized from 1024 and with what rule).

The paired filter:

7. The raw-only U-Net that scored the filter: its weights, config and training data, since the released members were trained on enhanced DRRs and real X-rays too.
8. The exact soft Dice definition the filter used (which channels, the background's handling, smoothing, whether empty labels were ignored, whether the model's own background channel or one minus the foreground was scored).
9. The pose grouping (what counted as one pose group), the quantile and the sign of the rule as applied (the appendix's 2 x median - q0.98), and whether the cut-off was computed per pose over all subjects at once.
10. The identities of the 5,667 dropped samples, which would let the filter be checked without the U-Net.

The CTs and the raw renders:

11. Which ENHANCE.PET 1.6k CTs were used, and the map from FluXray's subject ids to ENHANCE.PET's study numbers (FluXray names 1,597 subjects; the release holds 1,683).
12. The label source: whether the masks came from ENHANCE.PET's own truth, from MOOSE, or both; the MOOSE version and models; and how labels were merged into the 61 channels of the released model.
13. The raw rendering settings: the HU window and the air clamp, the number of ray samples, the form the volume was passed in (HU, attenuation, resampled spacing), the nanodrr version and the orientation convention.
14. The pose convention and the isocentre: the frame the 90 poses' rotations and translations are expressed in, and whether the isocentre was the volume's centre or a landmark.
15. The threshold the projected masks were made with (flexray's camera runtime defaults to 0.0, the render request to 0.5).

The training run:

16. The subject-level splits (train, validation, test) for FluXray and for each dataset the released members saw.
17. The per-member data mixture: which datasets each ensemble member was trained on and in what proportion.
18. The seeds: base.yml gives seed 40; whether each member had its own, whether the data loaders, the augmentation and the online DRR sampler were seeded, and with what.
19. The batch size and number of workers, which base.yml leaves as '?'.
20. The epochs actually run (base.yml says 2000 with 500 iterations each), how the released checkpoint was chosen (last, best validation, which metric) and the ONNX export settings.
21. The hardware, the precision (bfloat16, float16 or float32, and whether mixed) and the versions of torch and the package at training time.
22. The other training streams the released weights saw (MOOSE 3.0, ElbowCT, RSNAFrac, PedsCT, HANSeg, ShoulderCT and the real X-ray sets) with the same questions, where they differ.
