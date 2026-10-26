#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=4-00:00:00
# One source of the data platform's unfetched list (grid/run-platform-fetch.sh submits one job
# per source, chained with afterany). The job writes the landing's README.yaml once
# (data_platform/LAYOUT.md: what the folder is, its source id, licence, access and roles; never
# overwritten), then runs the route named in the environment:
#   acq      spinesurg-ct-nnunet's slurm/acquisition_fetch.sh with ARGS (zenodo, s3, hf: md5 or LFS sha256 or count verified)
#   idc      grid/idc_manifest.py writes the collection's manifest from idc-index, then acquisition_fetch.sh idc on it
#   verify   reacquire.py --verify ID (a copy whose state on disk is unknown; no re-fetch)
#   gdown    gdown FILE_ID into a scratch folder under the landing, then file(1) on what came
#   probe    curl -sI on URL: says whether a login is asked, fetches nothing
#   hf-token reacquire.py hf-get with HF_TOKEN read from TOKEN_FILE (mode 0600) into the environment; its
#            --include is a glob, and a run that verified no file fails here with exit 3 (issue #158)
#   curl-link curl on a presigned link read from LINK_FILE (mode 0600) through a curl config, never on a command line
#   url      curl on each public URL in ARGS (a release's assets), following redirects, each landed as raw/<its name>,
#            resumed where part of it is there and left alone where it is whole; no token and no config, since nothing is secret
#   kaggle   kaggle competitions download with KAGGLE_API_TOKEN read from TOKEN_FILE
#   kaggle-dataset kaggle datasets download of OWNER/NAME in ARGS, the same token; a plain dataset has no rules to accept
#   redivis  grid/redivis_fetch.py ARGS with REDIVIS_API_TOKEN read from TOKEN_FILE, in REDIVIS_ENV, a
#            venv the job makes once from the acq environment's Python with the pinned redivis client
#   zenodo-token grid/zenodo_fetch.py ARGS with ZENODO_TOKEN read from TOKEN_FILE: a record that opens only to
#            the owner's approved account, each file md5-checked against the record
#   note     print NOTE and exit 0 (a step that needs a repository or a hand step not on the grid yet)
# Before a route downloads a byte, the owner's size rule decides (grid/size-rule.sh, issue #160): the
# exact size of what it will land, read from the source (grid/fetch_size.py; for curl-link and url a one-byte
# range request, url's summed over its URLs), must fit in the room left under the volume's quota after what the running fetches
# still owe, or the job ends with exit 4 having fetched nothing; no floor stops a fetch part-way, so
# acquisition_fetch.sh runs with FLOOR_TB=0, and a job Slurm requeues keeps the admission it was
# given. kaggle, kaggle-dataset, gdown and redivis have no size reader yet and are refused the
# same way, so no dataset lands without its size known.
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
    echo "existing_subfolders_kept: \"the acquisition sub-layout (raw/, fetch/, meta/)\""
    echo "index_adapter: \"\"                # the db/build_index.py adapter that reads this folder; none written yet"
    echo "index_skip: []"
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
hf_verified_files() {  # hf_verified_files STATE: whether hf-get's summary in STATE verified at least one file
  # hf-get ends 0 when its --include matches nothing, having verified no file (all_verified false); on
  # 2026-10-23 FluoroSeg, ReXGradient-160K and CADS each ended so, COMPLETED with nothing fetched.
  local summary
  summary=$(ls -1t "$1"/hf_*.json 2>/dev/null | head -n 1)
  [ -n "$summary" ] && grep -q '"all_verified": true' "$summary"
}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
# acquisition_fetch.sh's own floor stops a fetch part-way under 5 TB free; the size rule replaces it.
export FLOOR_TB=0
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
# The size reader, the Python that reads the quota's attributes and curl are the job's own; a test
# stands in for them only where it sets SIZE_RULE_STAND_INS=yes, as for the size rule's own tools
# (grid/size-rule.sh, #180), since the job inherits the environment it was sent from. A compute node
# may have no getfattr and no python3 on the job's PATH; the acq environment's Python reads the
# quota's attributes there, so the rule never goes without them. It is named after the rule is
# sourced, which names its own.
if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then
  SIZER=${SIZER:-$ACQ_ENV/bin/python $REPO/grid/fetch_size.py}
  RULE_PYTHON=${XATTR_PYTHON:-$ACQ_ENV/bin/python}
  CURL=${CURL:-curl}
else
  SIZER="$ACQ_ENV/bin/python $REPO/grid/fetch_size.py"
  RULE_PYTHON=$ACQ_ENV/bin/python
  CURL=curl
fi
# The two size readers below are called by name through size_and_admit, which shellcheck cannot follow.
# shellcheck disable=SC2329
link_size() {  # link_size LINK_FILE OUTPUT: "<total bytes> <bytes still to land> the link answers", from a one-byte range request
  local cfg total have=0
  cfg=/dev/shm/${USER}_${ID}_size_$$.curl
  ( umask 077; { echo "url = \"$(head -n 1 "$1")\""; echo "range = 0-0"; echo "output = /dev/null"; echo "location"; echo "fail"; } > "$cfg" )
  total=$("$CURL" -sS -K "$cfg" -D - | tr -d '\r' | sed -n 's/^[Cc]ontent-[Rr]ange: bytes 0-0\/\([0-9][0-9]*\)$/\1/p' | tail -n 1)
  rm -f "$cfg"
  [ -n "$total" ] || { echo "no exact size; the link answers no range request with its length"; return 3; }
  is_count "$total" || { echo "no exact size; the length the link answers is no count"; return 3; }
  [ ! -f "$2" ] || have=$(stat -c %s "$2")
  echo "$total $(( total > have ? total - have : 0 )) the link answers"
}
# shellcheck disable=SC2329
url_length() {  # url_length URL: the length a URL answers to a one-byte range request, after its redirects; empty when none
  "$CURL" -sS -L --fail -r 0-0 -o /dev/null -D - "$1" | tr -d '\r' | sed -n 's/^[Cc]ontent-[Rr]ange: bytes 0-0\/\([0-9][0-9]*\)$/\1/p' | tail -n 1
}
landed_size() {  # landed_size URL: the bytes of raw/<its name> that are there, 0 where none
  local file=$DATA/$ID/raw/${1##*/}
  if [ -f "$file" ]; then stat -c %s "$file"; else echo 0; fi
}
# shellcheck disable=SC2329
urls_size() {  # urls_size URL...: "<total bytes> <bytes still to land> the links answer", every URL's length read first, less what is landed
  local url size have total=0 need=0
  for url in "$@"; do
    size=$(url_length "$url")
    [ -n "$size" ] || { echo "no exact size; ${url##*/} answers no range request with its length"; return 3; }
    is_count "$size" || { echo "no exact size; the length ${url##*/} answers is no count"; return 3; }
    have=$(landed_size "$url")
    total=$(( total + size ))
    need=$(( need + (size > have ? size - have : 0) ))
  done
  echo "$total $need the links answer"
}
fetch_url() {  # fetch_url URL: curl into raw/<its name>, resumed from what is there, left alone when it is whole
  local name=${1##*/} size
  size=$(url_length "$1")
  [ "$(landed_size "$1")" != "$size" ] || { echo "$name: landed whole already"; return 0; }
  "$CURL" -sS -L --fail --continue-at - -o "$DATA/$ID/raw/$name" "$1" || { echo "$name: curl ended with exit $?"; return 1; }
  echo "$name: landed $(landed_size "$1") bytes"
}
# shellcheck disable=SC2329
no_size_reader() {  # the size reader of a route that has none yet: no size, so the rule refuses it
  echo "no exact size; the $ROUTE route has no size reader yet"
  return 3
}
rc=0
case "$ROUTE" in
  acq)
    # shellcheck disable=SC2086
    if size_and_admit "$ID" $SIZER acq $ARGS --data-root "$DATA"; then
      bash "$SSN/slurm/acquisition_fetch.sh" $ARGS; rc=$?
    else rc=4; fi ;;
  idc)
    export PATH=$ACQ_ENV/bin:$PATH
    manifest=$DATA/$ID/meta/idc_$ARGS.csv
    # shellcheck disable=SC2086
    if ! python "$REPO/grid/idc_manifest.py" --collection "$ARGS" --out "$manifest"; then rc=1
    elif size_and_admit "$ID" $SIZER idc --manifest "$manifest" --landing "$DATA/$ID"; then
      bash "$SSN/slurm/acquisition_fetch.sh" idc --collection "$ID" --manifest "$manifest" --batch 50; rc=$?
    else rc=4; fi ;;
  verify)
    python3 "$SSN/data_platform/reacquire/reacquire.py" --verify "$ID"; rc=$? ;;
  gdown)
    if size_and_admit "$ID" no_size_reader; then
      export PATH=$ACQ_ENV/bin:$PATH
      scratch=$DATA/$ID/raw/gdown_$(date '+%F')
      mkdir -p "$scratch" && cd "$scratch" && gdown "$ARGS"; rc=$?
      file "$scratch"/* 2>/dev/null | tee "$DATA/$ID/meta/file_report.txt"
    else rc=4; fi ;;
  probe)
    curl -sSIL --max-time 60 "$ARGS" | tee "$DATA/$ID/meta/probe_$(date '+%F').txt" | grep -i "^HTTP\|location\|www-authenticate" ; rc=0 ;;
  hf-token)
    load_token HF_TOKEN "${TOKEN_FILE:?}" || exit 2
    # hf-get imports huggingface_hub, which the acq environment holds and the repository's lock does not.
    # Its --include glob is hf-get's to match against the repository, so this shell expands no pattern.
    set -f
    # shellcheck disable=SC2086
    if size_and_admit "$ID" $SIZER hf $ARGS --dest "$DATA/$ID/raw"; then
      "$ACQ_ENV/bin/python" "$SSN/data_platform/reacquire/reacquire.py" hf-get $ARGS --dest "$DATA/$ID/raw" --state "$DATA/$ID/meta/fetch-state"; rc=$?
    else rc=4; fi
    set +f
    if [ "$rc" = 0 ] && ! hf_verified_files "$DATA/$ID/meta/fetch-state"; then
      # In the shape grid/log-shapes.awk keeps, so the gate word status shows why.
      echo "$ID: nothing fetched; the include pattern matched no file at $(date -u '+%FT%TZ')"
      rc=3
    fi ;;
  curl-link)
    link_file=$(eval echo "${LINK_FILE:?}")
    [ "$(stat -c %a "$link_file")" = 600 ] || { echo "$link_file must be mode 600"; exit 2; }
    if size_and_admit "$ID" link_size "$link_file" "$DATA/$ID/raw/$ARGS"; then
      cfg=/dev/shm/${USER}_${ID}_$$.curl; umask 077
      { echo "url = \"$(head -n 1 "$link_file")\""; echo "output = \"$DATA/$ID/raw/$ARGS\""; echo "continue-at = -"; echo "location"; echo "fail"; } > "$cfg"
      "$CURL" -sS -K "$cfg"; rc=$?; rm -f "$cfg"
    else rc=4; fi ;;
  url)
    # Every URL's length is read before a byte lands, so one that answers none refuses the whole row.
    # shellcheck disable=SC2086
    if size_and_admit "$ID" urls_size $ARGS; then
      for url in $ARGS; do fetch_url "$url" || rc=1; done
    else rc=4; fi ;;
  kaggle)
    if size_and_admit "$ID" no_size_reader; then
      load_token KAGGLE_API_TOKEN "${TOKEN_FILE:-~/.fluorocap/credentials.env}" || exit 2
      "${KAGGLE_BIN:-$HOME/mambaforge/envs/spineps/bin/kaggle}" competitions download -c "$ARGS" -p "$DATA/$ID/raw"; rc=$?
    else rc=4; fi ;;
  kaggle-dataset)
    if size_and_admit "$ID" no_size_reader; then
      load_token KAGGLE_API_TOKEN "${TOKEN_FILE:-~/.fluorocap/credentials.env}" || exit 2
      "${KAGGLE_BIN:-$HOME/mambaforge/envs/spineps/bin/kaggle}" datasets download -d "$ARGS" -p "$DATA/$ID/raw"; rc=$?
    else rc=4; fi ;;
  redivis)
    if size_and_admit "$ID" no_size_reader; then
      load_token REDIVIS_API_TOKEN "${TOKEN_FILE:-~/.redivis/token.env}" || exit 2
      renv=${REDIVIS_ENV:-/rs/rs_grp_oschome/go2432/envs/redivis}
      # Under a lock, so two Redivis fetches starting together never build the environment at once.
      (
        flock 9
        "$renv/bin/python" -c 'import redivis' 2>/dev/null ||
          { "$ACQ_ENV/bin/python" -m venv "$renv" && "$renv/bin/pip" install -q "redivis==${REDIVIS_VERSION:-0.21.1}"; }
      ) 9> "$renv.lock" || exit 2
      # shellcheck disable=SC2086
      "$renv/bin/python" "$REPO/grid/redivis_fetch.py" --dest "$DATA/$ID/raw" --manifest "$DATA/$ID/meta" $ARGS; rc=$?
    else rc=4; fi ;;
  zenodo-token)
    load_token ZENODO_TOKEN "${TOKEN_FILE:-~/.zenodo/token.env}" || exit 2
    # shellcheck disable=SC2086
    if size_and_admit "$ID" $SIZER zenodo-token $ARGS --dest "$DATA/$ID/raw"; then
      python3 "$REPO/grid/zenodo_fetch.py" --dest "$DATA/$ID/raw" --manifest "$DATA/$ID/meta" $ARGS; rc=$?
    else rc=4; fi ;;
  note)
    echo "NOTE for $ID: ${NOTE:-see grid/README.md}"; rc=0 ;;
  *) echo "unknown route $ROUTE"; rc=64 ;;
esac
find "$DATA/$ID/raw" -type f -newer "$DATA/$ID/README.yaml" 2>/dev/null | wc -l | sed "s/^/files newer than the landing's README.yaml: /"
echo "DP_FETCH_RC=$rc $(date '+%F %T')"
exit $rc
