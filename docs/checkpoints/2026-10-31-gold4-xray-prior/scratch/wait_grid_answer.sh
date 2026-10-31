#!/bin/bash
# wait_grid_answer.sh JOB REQUEST [TRIES]: wait until symphony-template's grid branch holds the answer
# to REQUEST in logs/job-JOB.json, then print it.
job=$1 request=$2 tries=${3:-40}
repo=/home/claude/symphony-template
for i in $(seq 1 "$tries"); do
  git -C "$repo" fetch -q origin +refs/heads/grid:refs/remotes/origin/grid 2>/dev/null
  if git -C "$repo" show "origin/grid:logs/job-$job.json" 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if d.get('request')==sys.argv[1] else 1)" "$request"; then
    git -C "$repo" show "origin/grid:logs/job-$job.json" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('at', d.get('at'), 'rc', d.get('rc'), 'request', d.get('request'))
print('\n'.join(d.get('lines', [])))"
    exit 0
  fi
  sleep 15
done
echo "no answer for $request after $tries tries"
exit 1
