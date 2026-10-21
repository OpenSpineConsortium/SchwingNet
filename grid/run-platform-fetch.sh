#!/bin/bash
# Submit the data platform's unfetched sources (spinesurg-ct-nnunet data_platform/sources.json at
# bf1432f: 23 planned, 7 gated, 3 requested, 1 not acquired, 2 on disk with an unknown state,
# 1 empty) as one chain of Slurm jobs, one job per source through grid/platform-fetch.sbatch,
# each submitted --dependency=afterany on the one before, so a source that fails strands nothing
# behind it (bash 4.2; the login node runs only sbatch, df and this script). Every landing goes to
# /rs/rs_grp_oschome/go2432/data/<source id>/raw with a README.yaml. The gated sources run only
# when named with --only and their token or link file is in place; CT-RATE (21.3 TB) and NLST full
# (2.3 TB) are never in the chain: their lines are printed at the end for the owner to run or skip.
#
#   bash grid/run-platform-fetch.sh                       # the open chain, in the order below
#   bash grid/run-platform-fetch.sh --only aws_stoic2021,zenodo_lumos
#   bash grid/run-platform-fetch.sh --gated               # the open chain plus the granted gated sources
#   SBATCH=echo bash grid/run-platform-fetch.sh           # dry run
#
# The size budget comes first: the stated size of every source in the chain (from the cards'
# "GB catalogue" and the records) summed against df on /rs/rs_grp_oschome minus a 1 TB margin;
# a source with no stated size counts as 0 and is named. The margin is 5 TB because
# acquisition_fetch.sh stops its own job when less than 5 TB is free (--floor-tb 5).
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SBATCH=${SBATCH:-sbatch}
DF=${DF:-df}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
# 5 TB, not 1: acquisition_fetch.sh stops its own job under 5 TB free (--floor-tb 5).
MARGIN_GB=${MARGIN_GB:-5000}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
ONLY=""; GATED=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY=$2; shift 2 ;;
    --gated) GATED=1; shift ;;
    *) echo "unknown argument $1"; exit 64 ;;
  esac
done
mkdir -p "$REPO/grid/logs"
export SCHWINGNET="$REPO" DATA_ROOT

# id|route|size_gb (0 = not stated)|licence|access|args|extra environment (VAR=value, space-separated)
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
hf_cads_unique|hf-token|123.3|per component; CT-TRI under CADS terms|gated|--repo mrmrx/CADS-dataset --repo-type dataset --include CT-TRI/*|TOKEN_FILE=~/.hf/token.env NOTE=parts CT-TRI and VISCERAL only; VISCERAL is a second run with --include VISCERAL*
rsna_ratic_abdominal_trauma|curl-link|0|RSNA terms, non-commercial, no redistribution|gated|ratic.zip|LINK_FILE=~/.rsna/ratic_link NOTE=the presigned link is good until 2026-10-28 02:38 UTC
rsna_rspect_pe|kaggle|0|RSNA terms, non-commercial research|gated|rsna-str-pulmonary-embolism-detection|TOKEN_FILE=~/.fluorocap/credentials.env
"
# Never in the chain: the owner's own lines, printed at the end.
APART="
hf_ct_rate|hf-token|21300|CC BY-NC-SA 4.0|gated|--repo ibrahimhamamci/CT-RATE --repo-type dataset --include .|TOKEN_FILE=~/.hf/token.env NOTE=21.3 TB; the owner's TB number first
idc_nlst|idc|2305|CC BY 4.0|open|nlst|NOTE=24,713 subjects, 2.3 TB; refused as it stands by the stopping rule
"

wanted() {  # wanted ID: whether this run takes the source
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$1,"*) return 0 ;; esac
  return 1
}
TABLE="$OPEN"
[ "$GATED" = 0 ] || TABLE="$OPEN$GATED_LIST"
[ -z "$ONLY" ] || TABLE="$OPEN$GATED_LIST"

total_gb=0; unknown=""; n=0
while IFS='|' read -r id route size licence access args extra; do
  [ -n "$id" ] || continue
  wanted "$id" || continue
  n=$((n + 1))
  if [ "$size" = 0 ]; then unknown="$unknown $id"; else total_gb=$(awk -v a="$total_gb" -v b="$size" 'BEGIN { printf "%d", a + b + 0.999 }'); fi
done <<< "$TABLE"
free_gb=$("$DF" -BG --output=avail "$VOLUME" 2>/dev/null | tail -n 1 | tr -dc '0-9')
[ -n "$free_gb" ] || { echo "cannot read the free space of $VOLUME with df"; exit 2; }
echo "size budget: $n sources, $total_gb GB stated; $VOLUME has $free_gb GB free, margin $MARGIN_GB GB"
[ -z "$unknown" ] || echo "no size stated for:${unknown} (counted as 0)" | sed "s/for: */for: /"
if [ "$total_gb" -gt $(( free_gb - MARGIN_GB )) ]; then
  echo "refusing to submit: $total_gb GB exceeds the free space minus the margin; free room or narrow with --only"
  exit 3
fi

previous=""; ids=""; n=0
while IFS='|' read -r id route size licence access args extra; do
  [ -n "$id" ] || continue
  wanted "$id" || continue
  dep=""; [ -z "$previous" ] || dep="--dependency=afterany:$previous"
  # The job reads its settings from the environment: --export's own comma grammar would cut the
  # arguments, so each is exported for this one submission and unset after.
  export ID="$id" ROUTE="$route" ARGS="$args" LICENCE="$licence" ACCESS="$access"
  unset NOTE TOKEN_FILE LINK_FILE
  for pair in $extra; do
    case "$pair" in NOTE=*) export NOTE="${extra#*NOTE=}" ;; TOKEN_FILE=*|LINK_FILE=*) export "$pair" ;; esac
  done
  if [ "$SBATCH" != sbatch ]; then
    n=$((n + 1)); job="DRY$n"
    echo "would submit: sbatch --parsable -D $REPO/grid --job-name=dp_fetch_$id $dep --export=ALL $REPO/grid/platform-fetch.sbatch (ID=$id ROUTE=$route ARGS='$args'${NOTE:+ NOTE=...})"
  else
    # shellcheck disable=SC2086
    job=$("$SBATCH" --parsable -D "$REPO/grid" --job-name="dp_fetch_$id" $dep --export=ALL "$REPO/grid/platform-fetch.sbatch") || { echo "sbatch failed for $id"; exit 1; }
    job=$(echo "$job" | tail -n 1 | cut -d';' -f1)
  fi
  echo "$id: job $job${dep:+ ($dep)} $route ${size}GB"
  previous=$job; ids="$ids $id=$job"
done <<< "$TABLE"
echo "$(date '+%F %T') platform chain:$ids size_gb=$total_gb" | tee -a "$REPO/grid/LAST_RUN.txt"
echo "ETA: network-bound, about 1 hour per 20 GB, so about $(( total_gb / 20 + 1 )) hours for $total_gb GB in one chain of 4-day jobs requeued on preemption; watch with squeue -u \$USER and the logs under $REPO/grid/logs/dp_fetch_*"
echo
echo "Not submitted, the owner's own lines (each one job; run or skip):"
while IFS='|' read -r id route size licence access args extra; do
  [ -n "$id" ] || continue
  echo "  ID=$id ROUTE=$route ARGS='$args' LICENCE='$licence' ACCESS=$access ${extra%%NOTE=*}sbatch -D $REPO/grid --job-name=dp_fetch_$id --export=ALL $REPO/grid/platform-fetch.sbatch   # ${size} GB; ${extra#*NOTE=}"
done <<< "$APART"
