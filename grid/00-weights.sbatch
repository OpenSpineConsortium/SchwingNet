#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
# The ImageNet ResNet-18 file the version 1 run starts from (issue #53): tools/train.py takes it as
# a file and never downloads one, so this job fetches it once onto the lab volume. torchvision names
# the file by the first eight hex digits of its sha256 (resnet18-f37072fd.pth), so the file is kept
# only when its digest starts with them, moved into place whole, and its digest written beside it
# as WEIGHTS.sha256, which is what the gate reads to know the file is ready.
set -uo pipefail
MODELS=${MODELS:-/rs/rs_grp_oschome/go2432/models}
NAME=resnet18-f37072fd.pth
URL=${WEIGHTS_URL:-https://download.pytorch.org/models/$NAME}
REPORT=logs/00-weights-STAGE-REPORT.md
mkdir -p logs "$MODELS"
report() { echo "- $*" | tee -a "$REPORT"; }
echo "# The ImageNet weights: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname)" > "$REPORT"
if [ -s "$MODELS/$NAME" ] && grep -q '^f37072fd' "$MODELS/$NAME.sha256" 2>/dev/null; then
  report "$MODELS/$NAME is there with its digest; nothing fetched"; echo "SN_WEIGHTS_RC=0"; exit 0
fi
part=$(mktemp "$MODELS/.$NAME.XXXXXX") || { report "FAILED: cannot write in $MODELS"; echo "SN_WEIGHTS_RC=1"; exit 1; }
trap 'rm -f "$part"' EXIT
if ! curl -fsSL --retry 3 -o "$part" "$URL"; then
  report "FAILED: could not fetch $URL"; echo "SN_WEIGHTS_RC=1"; exit 1
fi
digest=$(sha256sum "$part" | cut -d' ' -f1)
case "$digest" in
  f37072fd*) ;;
  *) report "FAILED: the file fetched has sha256 $digest, not the f37072fd... its name promises; nothing kept"
     echo "SN_WEIGHTS_RC=1"; exit 1 ;;
esac
chmod 644 "$part" && mv "$part" "$MODELS/$NAME" || { report "FAILED: could not move the file into place"; echo "SN_WEIGHTS_RC=1"; exit 1; }
echo "$digest" > "$MODELS/$NAME.sha256"
report "fetched $URL: $(du -h "$MODELS/$NAME" | cut -f1), sha256 $digest"
echo "SN_WEIGHTS_RC=0"
