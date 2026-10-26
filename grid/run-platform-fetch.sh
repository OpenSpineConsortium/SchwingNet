#!/bin/bash
# Submit the data platform's unfetched sources (spinesurg-ct-nnunet data_platform/sources.json at
# bf1432f: 23 planned, 7 gated, 3 requested, 1 not acquired, 2 on disk with an unknown state,
# 1 empty) as one chain of Slurm jobs, one job per source through grid/platform-fetch.sbatch,
# each submitted --dependency=afterany on the one before, so a source that fails strands nothing
# behind it, each queued through hpcworker's job submit as a batch job (grid/hpcw.sh; bash 4.2; the
# login node runs only hpcworker, getfattr, squeue, df and this script). Every landing goes to
# /rs/rs_grp_oschome/go2432/data/<source id>/raw with a README.yaml. The gated sources run only
# when named with --only and their token or link file is in place; the full NLST (11.1 TB) runs only
# when named with --only, on the owner's yes of 2026-10-22; CT-RATE (21.3 TB) is never in the chain:
# its line is printed at the end for the owner to run or skip.
#
#   bash grid/run-platform-fetch.sh                       # the open chain, in the order below
#   bash grid/run-platform-fetch.sh --only aws_stoic2021,zenodo_lumos
#   bash grid/run-platform-fetch.sh --gated               # the open chain plus the granted gated sources
#   bash grid/run-platform-fetch.sh --gated-ids           # the granted gated ids, one a line (grid/gate.sh's fetch)
#   bash grid/run-platform-fetch.sh --stated idc_nlst     # the GB a source's line states (grid/size-rule.sh)
#   HPCW_DRY=1 bash grid/run-platform-fetch.sh            # dry run
#
# Each fetch is admitted or refused whole by the owner's size rule of 2026-10-23 when its job
# starts (grid/size-rule.sh, issue #160): its exact size, read from the source, must fit in the room
# left under the volume's CephFS quota after what the running fetches still owe, with no floor and
# no margin. Nothing is refused here, since a stated size is a guess and a chain holds sources of
# every size; the budget line says what the lines state, what the quota has left and what the
# running fetches owe, and each submitted job is marked queued, so an earlier job does not count it.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
ONLY=""; GATED=0; GATED_IDS=0; STATED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2 ;;
    --gated) GATED=1; shift ;;
    --gated-ids) GATED_IDS=1; shift ;;
    --stated) STATED=$2; shift 2 ;;
    *) echo "unknown argument $1"; exit 64 ;;
  esac
done

# id|route|size_gb (0 = not stated)|licence|access|args|extra environment (VAR=value, space-separated)
# An hf-token line's args go to reacquire.py hf-get, whose --include is a glob (fnmatch, as huggingface_hub's
# allow_patterns), never the regular expression the acq and zenodo routes read: "." there matches no file,
# and a whole repository is no --include at all (issue #158).
# The order is the chain's: small and spine-first, the large chest and whole-body sets after,
# so the spine CTs are on disk whatever the night brings; lidc_idri last among the open ones.
OPEN="
aws_stoic2021|acq|240|CC BY-NC 4.0|open|s3 --collection aws_stoic2021 --bucket s3://stoic2021-training/data/mha --include \.mha$|
idc_spine_mets_ct_seg|idc|17.2|CC BY 4.0|open|spine_mets_ct_seg|
idc_spinal_multiple_myeloma_seg|idc|33.8|CC BY 4.0|open|spinal_multiple_myeloma_seg|
zenodo_medpelvis3d|acq|15.1|CC BY 4.0|open|zenodo --collection zenodo_medpelvis3d --record 21757686 --include .|
zenodo_lumvbcanseg|acq|10.08|CC BY 4.0|open|zenodo --collection zenodo_lumvbcanseg --record 8181250 --include .|
zenodo_lumos|acq|46.4|not recorded on the card; to confirm on the record|open|zenodo --collection zenodo_lumos --record 18173664 --include .|NOTE=the version record 18173664 (18173663 is the concept DOI); the 1,620 radiographs are banked by grid/banks/lumos.json from this landing
zenodo_ts_task_hip_implant|acq|9.03|CC BY 4.0|open|zenodo --collection zenodo_ts_task_hip_implant --record 20272031 --include .|NOTE=overlap with TotalSegmentator v2/v3 not yet asked of the authors; out of every split until answered
zenodo_ts_task_pleural_effusion|acq|8.99|CC BY 4.0|open|zenodo --collection zenodo_ts_task_pleural_effusion --record 20272295 --include .|NOTE=overlap with TotalSegmentator v2/v3 not yet asked of the authors; out of every split until answered
zenodo_ts_task_liver_lesions|acq|38.87|CC BY 4.0|open|zenodo --collection zenodo_ts_task_liver_lesions --record 20272572 --include .|NOTE=overlap with TotalSegmentator v2/v3 not yet asked of the authors; out of every split until answered
zenodo_tmtv_benchmark|acq|6.85|CC BY 4.0|open|zenodo --collection zenodo_tmtv_benchmark --record 13255214 --include \.zip$|
tcia_ct_colonography|verify|0|CC BY 3.0|open|tcia_ct_colonography|
cm_spine_drive_file|gdown|0|not recorded|open|1r9wX1802gkU4-EQHMMlyAlEiWXGWLhhJ|
scidb_enhance_pet_1_6k|probe|0|CC BY 4.0|open|https://doi.org/10.57760/sciencedb.34150|NOTE=a probe only: if no login is asked, the record's file list goes into a plain http fetch (286 GB stated) in a later line
verse19_20_missing|note|0|CC BY-SA 4.0|open||NOTE=10 VerSe20 series never downloaded (verse020 112 139 141 151 202 235 251 257 290): the osf_verse route needs the VerSeFusion clone on the grid (its slurm/download_raw.sh with DATA_DIR and RAW_DIR); run reacquire.py --grid verse19_20 once that clone is there
idc_cptac_luad|idc|7|CC BY 4.0|open|cptac_luad|
idc_cptac_lscc|idc|8.3|CC BY 4.0|open|cptac_lscc|
idc_midrc_ricord_1b|idc|7|CC BY-NC 4.0|open|midrc_ricord_1b|
idc_prostate_anatomical_edge_cases|idc|16.6|CC BY 4.0|open|prostate_anatomical_edge_cases|
idc_ldct_and_projection_data|idc|16.5|CC BY 4.0|open|ldct_and_projection_data|
idc_nsclc_radiomics|idc|25.8|CC BY-NC 3.0|open|nsclc_radiomics|
idc_nsclc_radiogenomics|idc|28|CC BY 3.0|open|nsclc_radiogenomics|
zenodo_unitochest|acq|84.07|CC BY 4.0|open|zenodo --collection zenodo_unitochest --record 5797912 --include .|
zenodo_vsd_fullbody|acq|116.3|CC BY-NC-SA|open|zenodo --collection zenodo_vsd_fullbody --record 8270365 --include .|
hf_abdomenatlas2_0_mini|acq|620.4|CC BY-NC-SA 4.0|open|hf --collection hf_abdomenatlas2_0_mini --repo AbdomenAtlas/AbdomenAtlas2.0Mini --include .|NOTE=the id map against 3.0 Mini is a later step
idc_lidc_idri|idc|123.3|CC BY 3.0|open|lidc_idri|
"
# Granted gated sources: the token or link in a mode-0600 file the owner writes, read by the job.
GATED_LIST="
hf_cads_unique|hf-token|123.3|per component; CT-TRI under CADS terms|gated|--repo mrmrx/CADS-dataset --repo-type dataset --include *0043_new_ct_tri/*|TOKEN_FILE=~/.hf/token.env NOTE=parts CT-TRI and VISCERAL only, folders 0043_new_ct_tri and 0001 and 0002 of the tree of 2026-09-23 (data/reproduce/sources.json); VISCERAL is a second run with --include *000[12]_visceral*
rsna_ratic_abdominal_trauma|curl-link|0|RSNA terms, non-commercial, no redistribution|gated|ratic.zip|LINK_FILE=~/.rsna/ratic_link NOTE=the presigned link is good until 2026-10-28 02:38 UTC
rsna_rspect_pe|kaggle|981|RSNA terms, non-commercial research|gated|rsna-str-pulmonary-embolism-detection|TOKEN_FILE=~/.fluorocap/credentials.env NOTE=980.24 GB and 1,937,450 files on the competition's data page, read by the owner on 2026-10-23
hf_rexgradient_160k|hf-token|156|ReXGradient-160K data access and use agreement, non-commercial, no redistribution|gated|--repo rajpurkarlab/ReXGradient-160K --repo-type dataset|TOKEN_FILE=~/.hf/token.env NOTE=the whole repository, about 156 GB, on the owner's choice of 2026-10-22 knowing clause A.5 limits a download to the part the project needs
aimi_ol3i|redivis|4.3|Stanford AIMI research use agreement, non-commercial|gated|--max-gb 10 --files aimi.ol3i_opportunistic_l3_ct_slices_for_ischemic_heart_disease_risk_assessment:asvh:v1_0.ol3i:n1y3 --csv aimi.ol3i_opportunistic_l3_ct_slices_for_ischemic_heart_disease_risk_assessment:asvh:v1_0.clinical_data:2cqm|TOKEN_FILE=~/.redivis/token.env NOTE=the L3 CT slices in one file and the clinical table, on the owner's choice of 2026-10-22
chexpert_plus|redivis|0|Stanford AIMI research use agreement, non-commercial|gated|--max-gb 3000 --files aimi.chexpert_plus:5yyj:v1_0.png_train:s6cj --files aimi.chexpert_plus:5yyj:v1_0.png_valid:41v9 --files aimi.chexpert_plus:5yyj:v1_0.chexpert_labels:pmec --files aimi.chexpert_plus:5yyj:v1_0.radgraph_xl_annotations:8wdv --csv aimi.chexpert_plus:5yyj:v1_0.df_chexpert_plus_240401:bavj|TOKEN_FILE=~/.redivis/token.env NOTE=the PNGs, labels, RadGraph-XL annotations and reports, no DICOM, on the owner's choice of 2026-10-22; refuses before downloading above 3000 GB listed
zenodo_magic_ct|zenodo-token|39.1|CC BY 4.0 on the record, under its data use agreement (non-commercial)|gated|--record 18389015 --max-gb 50|TOKEN_FILE=~/.zenodo/token.env NOTE=MAGIC-CT, 21 files, each md5-checked against the record; the owner's approved access of 2026-10-22
"
# The owner's yes, one source at a time: never in the chain, fetched only when grid/gate.sh's fetch
# names it. The full NLST is here since the owner lifted the stopping rule on 2026-10-22 ("yes
# please add this"), choosing what the volume holds by its tally (status) and not by a yield rule.
OWNER_LIST="
idc_nlst|idc|11139.6|CC BY 4.0|open|nlst|NOTE=26,254 people and 203,111 CT series, 11,139,589 MB by idc-index 25.0.5 (series_size_MB, a byte count; the card's 2.3 TB was wrong, issue #160); the owner's yes of 2026-10-22
ipcai2025_robotic_xray_drive|gdown|0.85|not stated on the file; to ask the authors|open|1pV8qaW4kHGI8wrDWc6wVWS4za5XRWsXA|NOTE=202410191.zip, the data of arXiv 2412.08020 (Killeen and others, language-controlled robotic C-arm; the cadaver study's X-rays), shared with the owner by its author on 2026-10-22 and readable by anyone with the link
fluorosam_weights_drive|gdown|1.0|per arcadelab/fluorosam; not stated on the file|open|1lJqVIuVFbdc9Bcmj17ac_cha-gW827Q6|NOTE=fluorosam_model_weights.pth, 1,002,351,026 bytes, the weights the FluoroSAM repository's README links, readable by anyone with the link; asked for by the 3D-to-X-ray work on 2026-10-22 as its comparison row
kaggle_fracture_multiregion|kaggle-dataset|0.51|not stated; merged from three other Kaggle uploads, to map back by hand|gated|bmadushanirodrigo/fracture-multi-region-x-ray-data|TOKEN_FILE=~/.fluorocap/credentials.env NOTE=507,724,147 bytes and 10,580 images by Kaggle's dataset API on 2026-10-22; fetched to explore on the owner's yes of 2026-10-23, out of every split until its sources and licences are read (spine-datasets #23)
kaggle_scoliosis_yolov5|kaggle-dataset|0.26|MIT in the licence field, CC BY 4.0 in the description|gated|salmankey/scoliosis-yolov5-annotated-spine-x-ray-dataset|TOKEN_FILE=~/.fluorocap/credentials.env NOTE=251,996,951 bytes by Kaggle's dataset API on 2026-10-22; fetched to explore on the owner's yes of 2026-10-23, every image hash-checked against the AASCE copy before any use (spine-datasets #24)
hf_flexray_weights|hf-token|0|weights CC-BY-NC-4.0, code MIT; a benchmark row only, never in a SchwingNet network|gated|--repo VictorButoi/flexray --repo-type model|TOKEN_FILE=~/.hf/token.env NOTE=FleXray's open weights (MIT CSAIL, arXiv 2609.26756), every member with its checksums, for the bench word's two FleXray jobs; the owner's yes of 2026-10-25 (#287)
hf_xvr_models|hf-token|3.7|MIT; a benchmark row only|gated|--repo eigenvivek/xvr --repo-type model|TOKEN_FILE=~/.hf/token.env NOTE=xvr's published registration models (arXiv 2503.16309), 3.7 GB by its README, for bench xvr_deepfluoro; the owner's yes of 2026-10-25 (#287)
hf_xvr_data|hf-token|4.8|CC-BY-NC-ND-4.0; read-only, a benchmark row only|gated|--repo eigenvivek/xvr-data --repo-type dataset --include deepfluoro/*|TOKEN_FILE=~/.hf/token.env NOTE=xvr's DeepFluoro folder alone of its 4.8 GB data, what bench xvr_deepfluoro reads; the owner's yes of 2026-10-25 (#287)
hf_fluoroseg|hf-token|2650|FluoroSeg data use terms, accepted by the owner on 2026-10-22|gated|--repo benjamindkilleen/fluoroseg --repo-type dataset|TOKEN_FILE=~/.hf/token.env NOTE=the whole set, about 2.65 TB of simulated X-rays with masks, on the owner's yes of 2026-10-22 (12.6 TB free of the 22 TB quota at the time, 6.8 TB of it promised to queued fetches)
hf_flexray_data|hf-token|19|CC-BY-NC-4.0 as a collection; a comparison row only, never in a SchwingNet network|gated|--repo VictorButoi/flexray-data --repo-type dataset --include FluXray/*|TOKEN_FILE=~/.hf/token.env NOTE=the FluXray folder alone (the enhanced DRRs at 256 pixels, their masks, samples.csv with each pose), what realism's stats, lora and eval stages compare against and what the DRR domain-gap study reads (#401); not yet the owner's yes
hf_flux2_klein_4b|hf-token|0|Apache-2.0|open|--repo black-forest-labs/FLUX.2-klein-4B --repo-type model|TOKEN_FILE=~/.hf/token.env NOTE=FLUX.2 klein 4B, distilled, the open-licensed edit model realism's edit stage runs where the 9B is not landed; the size is read from the hub by the size rule; not yet the owner's yes
hf_flux2_klein_9b|hf-token|0|FLUX Non-Commercial License; the model FluXray was made with, a reproduction row only|gated|--repo black-forest-labs/FLUX.2-klein-9B --repo-type model|TOKEN_FILE=~/.hf/token.env NOTE=FLUX.2 klein 9B, distilled, the edit the paper names (flux.2-klein-9b, 4 steps, guidance 1.0); the owner accepts its licence on the model page under the token's account first, or the hub refuses the download; not yet the owner's yes
hf_flux2_klein_base_4b|hf-token|0|Apache-2.0|open|--repo black-forest-labs/FLUX.2-klein-base-4B --repo-type model|TOKEN_FILE=~/.hf/token.env NOTE=FLUX.2 klein base 4B, undistilled, the base the LoRA plan trains on (schwingnet.realism.DEFAULT_BASE), so the adapter is the project's to keep; not yet the owner's yes
hf_flux2_klein_base_9b|hf-token|0|FLUX Non-Commercial License|gated|--repo black-forest-labs/FLUX.2-klein-base-9B --repo-type model|TOKEN_FILE=~/.hf/token.env NOTE=FLUX.2 klein base 9B, undistilled, a base the LoRA plan may name instead (--base klein-base-9b); the owner accepts its licence on the hub first; not yet the owner's yes
aws_enhance_pet_ct|acq|177|CC BY 4.0 (Leipzig, Careggi, UC Davis) and CC BY-NC 4.0 (autoPET, Tuebingen) by site; the strictest binds the set|open|s3 --collection aws_enhance_pet_ct --bucket s3://enhance-pet-1-6k/imaging-data/images/CT --include \.nii\.gz$|NOTE=ENHANCE.PET 1.6k's 1,683 CTs as NIfTI (about 105 MB each, 177 GB; the public bucket lists them unsigned), the CTs FleXray's MOOSE training set and FluXray were rendered from, so realism's edit stage renders the same anatomy at the same poses; not yet the owner's yes
aws_enhance_pet_labels|acq|2.5|CC BY 4.0 (Leipzig, Careggi, UC Davis) and CC BY-NC 4.0 (autoPET, Tuebingen) by site; the strictest binds the set|open|s3 --collection aws_enhance_pet_labels --bucket s3://enhance-pet-1-6k/imaging-data/ground-truth --include \.nii\.gz$|NOTE=ENHANCE.PET 1.6k's ground truth, seven folders of label maps (Vertebrae, Ribs and Peripheral-Bones among them, about 200 KB each), the exact masks realism's render writes with each DRR; the label dictionary is the committed copy grid/enhance-pet-labels.json; not yet the owner's yes
"
# Never in the chain: the owner's own lines, printed at the end.
APART="
hf_ct_rate|hf-token|21300|CC BY-NC-SA 4.0|gated|--repo ibrahimhamamci/CT-RATE --repo-type dataset|TOKEN_FILE=~/.hf/token.env NOTE=21.3 TB; the owner's TB number first
"

if [ "$GATED_IDS" = 1 ]; then
  sed -n 's/^\([a-z0-9_]*\)|.*/\1/p' <<< "$GATED_LIST$OWNER_LIST"
  exit 0
fi
if [ -n "$STATED" ]; then
  case "$STATED" in *[!a-z0-9_]*) echo "unknown id $STATED"; exit 64 ;; esac
  sed -n "s/^$STATED|[^|]*|\([^|]*\)|.*/\1/p" <<< "$OPEN$GATED_LIST$OWNER_LIST$APART" | head -n 1
  exit 0
fi
mkdir -p "$REPO/grid/logs"
export SCHWINGNET="$REPO" DATA_ROOT

secret_file_problem() {  # secret_file_problem EXTRA: why a gated source's token or link file cannot be read yet, or nothing
  # Checked on the login node, before anything is queued, so a missing file is one line now and not
  # a failed job later; the file's text is never read here, only that it is there and the owner's alone.
  local pair file mode
  for pair in $1; do
    case "$pair" in TOKEN_FILE=*|LINK_FILE=*) ;; *) continue ;; esac
    file=${pair#*=}
    file=${file/#\~/$HOME}
    [ -f "$file" ] || { echo "there is no ${pair#*=} on the grid account; the owner writes it, mode 600 (grid/README.md)"; return; }
    mode=$(stat -c %a "$file")
    [ "$mode" = 600 ] || [ "$mode" = 400 ] || { echo "${pair#*=} is mode $mode, readable by others; it must be mode 600"; return; }
  done
}

wanted() {  # wanted ID: whether this run takes the source
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$1,"*) return 0 ;; esac
  return 1
}
TABLE="$OPEN"
[ "$GATED" = 0 ] || TABLE="$OPEN$GATED_LIST"
[ -z "$ONLY" ] || TABLE="$OPEN$GATED_LIST$OWNER_LIST"

total_gb=0; unknown=""; n=0; missing=""
while IFS='|' read -r id route size licence access args extra; do
  [ -n "$id" ] || continue
  wanted "$id" || continue
  if [ "$access" = gated ]; then
    problem=$(secret_file_problem "${extra%%NOTE=*}")
    [ -z "$problem" ] || { echo "$id: left out: $problem"; missing="$missing $id"; continue; }
  fi
  n=$((n + 1))
  if [ "$size" = 0 ]; then unknown="$unknown $id"; else total_gb=$(awk -v a="$total_gb" -v b="$size" 'BEGIN { printf "%d", a + b + 0.999 }'); fi
done <<< "$TABLE"
DATA=$DATA_ROOT
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
# What the running fetches owe first and the room after it, in the order a fetch job's decision
# reads them (grid/size-rule.sh, admit_fetch, #180); this line only reports them, since each job
# decides when it starts.
if owed=$(owed_by_running ""); then
  read -r owed_bytes owed_n owed_unsized <<< "$owed"
  owed="$(gb_up "$owed_bytes") GB of it owed to $(running_fetches "$owed_n")${owed_unsized:+, and the running fetch of $owed_unsized states no size}"
else
  owed="what the running fetches owe not read (squeue did not answer)"
fi
read -r free_gb free_from <<< "$(volume_free_gb "$VOLUME")"
if [ -z "$free_gb" ]; then
  why=$(room_unread_words "$VOLUME" "neither its CephFS quota nor df answered")
  echo "cannot read the free space of $VOLUME: $why"
  exit 2
fi
echo "size budget: $n sources, $total_gb GB stated; $VOLUME has $free_gb GB $(free_space_words "$free_from"), $owed"
echo "each job starts its fetch only if the exact size its source states fits the room then; one that does not lands nothing (grid/size-rule.sh)"
[ -z "$unknown" ] || echo "no size stated on the line for:${unknown} (the job reads it from the source)" | sed "s/for: */for: /"
if [ "$n" = 0 ] && [ -n "$missing" ]; then
  echo "refusing to submit: the token or link file of${missing} is not in place (above); nothing was queued"
  exit 2
fi

# shellcheck source=grid/hpcw.sh
. "$REPO/grid/hpcw.sh"
previous=""; ids=""
while IFS='|' read -r id route size licence access args extra; do
  [ -n "$id" ] || continue
  wanted "$id" || continue
  case " $missing " in *" $id "*) continue ;; esac
  # The first job waits on DEPEND where grid/gate.sh gives one (the X-ray fetch: X-ray before CT);
  # each later one on the job before it.
  dep=${DEPEND:-}
  [ -z "$previous" ] || dep="afterany:$previous"
  hpcw_after "$dep" || exit 1
  # The job reads its settings from the environment, which job submit hands it: --export's own
  # comma grammar would cut the arguments, so each is exported for this one submission.
  export ID="$id" ROUTE="$route" ARGS="$args" LICENCE="$licence" ACCESS="$access"
  unset NOTE TOKEN_FILE LINK_FILE
  for pair in $extra; do
    case "$pair" in NOTE=*) export NOTE="${extra#*NOTE=}" ;; TOKEN_FILE=*|LINK_FILE=*) export "$pair" ;; esac
  done
  [ -z "${HPCW_DRY:-}" ] || echo "would submit $id: ROUTE=$route ARGS='$args'${NOTE:+ NOTE=...}"
  job=$(hpcw_submit "dp_fetch_$id" batch ${HPCW_AFTER[@]+"${HPCW_AFTER[@]}"} -- platform-fetch.sbatch) || { echo "hpcworker refused the fetch of $id"; exit 1; }
  # Queued under the size rule: a fetch admitted before this one starts does not count it.
  [ -n "${HPCW_DRY:-}" ] || mark_queued "$id" "$job"
  echo "$id: job $job${dep:+ ($dep)} $route ${size}GB"
  previous=$job; ids="$ids $id=$job"
done <<< "$TABLE"
echo "$(date '+%F %T') platform chain:$ids size_gb=$total_gb" | tee -a "$REPO/grid/LAST_RUN.txt"
echo "ETA: network-bound, about 1 hour per 20 GB, so about $(( total_gb / 20 + 1 )) hours for $total_gb GB in one chain of 4-day jobs requeued on preemption; watch with the gate word status"
echo
echo "Not submitted, the owner's own lines (each one job; run or skip):"
while IFS='|' read -r id route size licence access args extra; do
  [ -n "$id" ] || continue
  echo "  ID=$id ROUTE=$route ARGS='$args' LICENCE='$licence' ACCESS=$access ${extra%%NOTE=*}hpcworker job submit --project schwingnet --name dp_fetch_$id --class batch --dir $REPO/grid -- platform-fetch.sbatch   # ${size} GB; ${extra#*NOTE=}"
done <<< "$APART"
