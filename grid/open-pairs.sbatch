#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=1-00:00:00
# One open paired set of the paired CT and X-ray survey of 2026-11-01 (spine-datasets #183 to #186),
# fetched as a list of series rather than a whole collection. grid/series_select.py writes the
# manifest of the selection SELECTION into the landing's meta folder (once: a requeued job keeps
# the list it was admitted for), the owner's size rule admits what the route will land before a
# byte does (grid/size-rule.sh: grid/fetch_size.py idc for an IDC list, series_select.py size for
# an NBIA one, idc_headers.py --size for headers), and then ROUTE fetches it:
#   idc      spinesurg-ct-nnunet's slurm/acquisition_fetch.sh idc: s5cmd from IDC's public bucket,
#            each series verified by its instance count
#   nbia     acquisition_fetch.sh nbia: NBIA's getImage, one zip a series, unpacked and verified by
#            its instance count
#   headers  grid/idc_headers.py: each instance's header from IDC's public bucket by a range
#            request, kept up to its Pixel Data
# The landing is $DATA/$ID with a README.yaml as grid/platform-fetch.sbatch writes one; the fetch's
# state is $DATA/$ID/fetch (verified.jsonl, failed.jsonl). CODE is the SchwingNet checkout whose
# grid/ scripts run; REPO is the one whose grid/logs the size rule reads for the fetches the gate
# sent, the owner's ~/SchwingNet unless set.
#   ID=tcia_ctc_localizers ROUTE=idc SELECTION=ctc_localizers LICENCE="CC BY 3.0" \
#     hpcworker job submit --project schwingnet --name dp_fetch_tcia_ctc_localizers --class batch \
#     --dir <folder> -- <checkout>/grid/open-pairs.sbatch
set -uo pipefail
ID=${ID:?the landing id}
ROUTE=${ROUTE:?idc, nbia or headers}
SELECTION=${SELECTION:?a selection of grid/series_select.py}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
CODE=${CODE:-$HOME/SchwingNet}
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
ACQ_ENV=${ACQ_ENV:-/rs/rs_grp_oschome/go2432/envs/acq}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
LICENCE=${LICENCE:-not recorded}
PY=$ACQ_ENV/bin/python
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-/rs/rs_grp_oschome/go2432/tmp}
# acquisition_fetch.sh's own floor stops a fetch part-way under 5 TB free; the size rule replaces it.
export FLOOR_TB=0
mkdir -p logs "$TMPDIR" "$DATA/$ID/raw" "$DATA/$ID/meta"
echo "OPEN_PAIRS start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} restart ${SLURM_RESTART_COUNT:-0}: $ID via $ROUTE $SELECTION"
if [ ! -f "$DATA/$ID/README.yaml" ]; then
  {
    echo "# What this folder is (data_platform/LAYOUT.md); written by SchwingNet grid/open-pairs.sbatch, job ${SLURM_JOB_ID:-}, $(date '+%F')"
    echo "source_ids: [$ID]"
    echo "licence: \"$LICENCE\""
    echo "access: \"open\""
    echo "restricted: false"
    echo "roles: {raw: as downloaded, fetch: the fetcher's state (verified.jsonl, failed.jsonl), meta: the series manifest and the size rule's files}"
    echo "fetched_by: \"open-pairs.sbatch $ROUTE $SELECTION\""
    [ "$ROUTE" != headers ] || echo "note: \"DICOM headers only, each instance cut before its Pixel Data (grid/idc_headers.py); no image is here\""
  } > "$DATA/$ID/README.yaml"
fi
# shellcheck source=grid/size-rule.sh
. "$CODE/grid/size-rule.sh"
RULE_PYTHON=$PY
CURL=curl
manifest=$DATA/$ID/meta/$SELECTION.csv
case "$SELECTION" in
  ctc_masked) from=(--labels "$DATA/ctspine1k") ;;
  sbu_abdominal_films) from=(--held "$DATA/idc/raw/covid_19_ny_sbu") ;;
  sbu_localizers) from=(--held "$DATA/idc/raw/covid_19_ny_sbu" --fetched "$DATA/covid19_ny_sbu_films/raw/covid_19_ny_sbu") ;;
  cmb_*) from=(--held "$DATA/idc/raw/cmb_mml") ;;
  *) from=() ;;
esac
if [ ! -s "$manifest" ]; then
  "$PY" "$CODE/grid/series_select.py" "$SELECTION" ${from[@]+"${from[@]}"} --out "$manifest" || { echo "OPEN_PAIRS_RC=1 no manifest"; exit 1; }
fi
rc=0
case "$ROUTE" in
  idc)
    if size_and_admit "$ID" "$PY" "$CODE/grid/fetch_size.py" idc --manifest "$manifest" --landing "$DATA/$ID"; then
      bash "$SSN/slurm/acquisition_fetch.sh" idc --collection "$ID" --root "$DATA" --manifest "$manifest" --batch 50; rc=$?
    else rc=4; fi ;;
  nbia)
    if size_and_admit "$ID" "$PY" "$CODE/grid/series_select.py" size --manifest "$manifest" --landing "$DATA/$ID"; then
      bash "$SSN/slurm/acquisition_fetch.sh" nbia --collection "$ID" --root "$DATA" --manifest "$manifest"; rc=$?
    else rc=4; fi ;;
  headers)
    if size_and_admit "$ID" "$PY" "$CODE/grid/idc_headers.py" --manifest "$manifest" --landing "$DATA/$ID" --size; then
      "$PY" "$CODE/grid/idc_headers.py" --manifest "$manifest" --landing "$DATA/$ID"; rc=$?
    else rc=4; fi ;;
  *) echo "unknown route $ROUTE"; rc=64 ;;
esac
echo "landing: $(find "$DATA/$ID/raw" -type f | wc -l) files, $(du -sb "$DATA/$ID/raw" | cut -f1) bytes under raw/"
echo "OPEN_PAIRS_RC=$rc $(date '+%F %T')"
exit $rc
