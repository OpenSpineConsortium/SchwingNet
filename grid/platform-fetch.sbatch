#!/bin/bash
#SBATCH --job-name=dp_fetch
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=4-00:00:00
#SBATCH --output=logs/%x_%j.out
# One source of the data platform's unfetched list (grid/run-platform-fetch.sh submits one job
# per source, chained with afterany). The job writes the landing's README.yaml once
# (data_platform/LAYOUT.md: what the folder is, its source id, licence, access and roles; never
# overwritten), then runs the route named in the environment:
#   acq      spinesurg-ct-nnunet's slurm/acquisition_fetch.sh with ARGS (zenodo, s3, hf: md5 or LFS sha256 or count verified)
#   idc      grid/idc_manifest.py writes the collection's manifest from idc-index, then acquisition_fetch.sh idc on it
#   verify   reacquire.py --verify ID (a copy whose state on disk is unknown; no re-fetch)
#   gdown    gdown FILE_ID into a scratch folder under the landing, then file(1) on what came
#   probe    curl -sI on URL: says whether a login is asked, fetches nothing
#   hf-token reacquire.py hf-get with HF_TOKEN read from TOKEN_FILE (mode 0600) into the environment
#   curl-link curl on a presigned link read from LINK_FILE (mode 0600) through a curl config, never on a command line
#   kaggle   kaggle competitions download with KAGGLE_API_TOKEN read from TOKEN_FILE
#   note     print NOTE and exit 0 (a step that needs a repository or a hand step not on the grid yet)
# Secrets are read from files into this job's environment or a mode-0600 config and never echoed.
set -uo pipefail
ID=${ID:?the source id}
ROUTE=${ROUTE:?the route}
ARGS=${ARGS:-}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
ACQ_ENV=${ACQ_ENV:-/rs/rs_grp_oschome/go2432/envs/acq}
LICENCE=${LICENCE:-not recorded}
ACCESS=${ACCESS:-open}
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR" "$DATA/$ID/raw" "$DATA/$ID/meta"
echo "DP_FETCH start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} restart ${SLURM_RESTART_COUNT:-0}: $ID via $ROUTE $ARGS"
if [ ! -f "$DATA/$ID/README.yaml" ]; then
  {
    echo "# What this folder is (data_platform/LAYOUT.md); written by SchwingNet grid/platform-fetch.sbatch, job ${SLURM_JOB_ID:-}, $(date '+%F')"
    echo "source_ids: [$ID]"
    echo "licence: \"$LICENCE\""
    echo "access: \"$ACCESS\""
    echo "restricted: $([ "$ACCESS" = open ] && echo false || echo true)"
    echo "roles: {raw: as downloaded, fetch: the fetcher's state (verified.jsonl, failed.jsonl), meta: manifests and FETCH.json}"
    echo "fetched_by: \"$ROUTE $ARGS\""
    [ -z "${NOTE:-}" ] || echo "note: \"$NOTE\""
  } > "$DATA/$ID/README.yaml"
fi
load_token() {  # load_token VAR FILE: the variable from a KEY=value line of a 0600 file, never printed
  local file mode
  file=$(eval echo "$2")
  [ -f "$file" ] || { echo "no token file $file"; return 1; }
  mode=$(stat -c %a "$file")
  [ "$mode" = 600 ] || [ "$mode" = 400 ] || { echo "$file is mode $mode; chmod 600 it"; return 1; }
  local value
  value=$(grep "^$1=" "$file" | head -n 1 | cut -d= -f2- | tr -d '"'"'")
  [ -n "$value" ] || value=$(head -n 1 "$file")
  export "$1=$value"
}
rc=0
case "$ROUTE" in
  acq)
    # shellcheck disable=SC2086
    bash "$SSN/slurm/acquisition_fetch.sh" $ARGS; rc=$? ;;
  idc)
    export PATH=$ACQ_ENV/bin:$PATH
    manifest=$DATA/$ID/meta/idc_$ARGS.csv
    python "$REPO/grid/idc_manifest.py" --collection "$ARGS" --out "$manifest" && \
      bash "$SSN/slurm/acquisition_fetch.sh" idc --collection "$ID" --manifest "$manifest" --batch 50; rc=$? ;;
  verify)
    python3 "$SSN/data_platform/reacquire/reacquire.py" --verify "$ID"; rc=$? ;;
  gdown)
    export PATH=$ACQ_ENV/bin:$PATH
    scratch=$DATA/$ID/raw/gdown_$(date '+%F')
    mkdir -p "$scratch" && cd "$scratch" && gdown "$ARGS"; rc=$?
    file "$scratch"/* 2>/dev/null | tee "$DATA/$ID/meta/file_report.txt" ;;
  probe)
    curl -sSIL --max-time 60 "$ARGS" | tee "$DATA/$ID/meta/probe_$(date '+%F').txt" | grep -i "^HTTP\|location\|www-authenticate" ; rc=0 ;;
  hf-token)
    load_token HF_TOKEN "${TOKEN_FILE:?}" || exit 2
    # shellcheck disable=SC2086
    python3 "$SSN/data_platform/reacquire/reacquire.py" hf-get $ARGS --dest "$DATA/$ID/raw" --state "$DATA/$ID/meta/fetch-state"; rc=$? ;;
  curl-link)
    link_file=$(eval echo "${LINK_FILE:?}")
    [ "$(stat -c %a "$link_file")" = 600 ] || { echo "$link_file must be mode 600"; exit 2; }
    cfg=/dev/shm/${USER}_${ID}_$$.curl; umask 077
    { echo "url = \"$(head -n 1 "$link_file")\""; echo "output = \"$DATA/$ID/raw/$ARGS\""; echo "continue-at = -"; echo "location"; echo "fail"; } > "$cfg"
    curl -sS -K "$cfg"; rc=$?; rm -f "$cfg" ;;
  kaggle)
    load_token KAGGLE_API_TOKEN "${TOKEN_FILE:-~/.fluorocap/credentials.env}" || exit 2
    "${KAGGLE_BIN:-$HOME/mambaforge/envs/spineps/bin/kaggle}" competitions download -c "$ARGS" -p "$DATA/$ID/raw"; rc=$? ;;
  note)
    echo "NOTE for $ID: ${NOTE:-see grid/README.md}"; rc=0 ;;
  *) echo "unknown route $ROUTE"; rc=64 ;;
esac
find "$DATA/$ID/raw" -type f -newer "$DATA/$ID/README.yaml" 2>/dev/null | wc -l | sed "s/^/files newer than the landing's README.yaml: /"
echo "DP_FETCH_RC=$rc $(date '+%F %T')"
exit $rc
