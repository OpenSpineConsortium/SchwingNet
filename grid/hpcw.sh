# shellcheck shell=bash
# How every SchwingNet grid job reaches Slurm (issue #77): hpcworker's `job submit`, the lab's one
# tested way of queueing a job (framework 27 and later, interface 2), never sbatch lines written
# here. The owner's order of 2026-10-21: a project's job names a class, cpu, batch or gpu, and the
# site profile hpcworker publishes gives the partitions, the QoS, the account and the GPU request,
# since SchwingNet's own guess at the GPU QoS was refused (issue #74) while Beethoven had known it
# for weeks. So no script here carries a partition, QoS, gres, requeue or output line; its #SBATCH
# lines keep only the time, CPUs and memory it needs, which job submit honours.
#
# Sourced by grid/gate.sh and the run-*.sh scripts, which set REPO first. HPCWORKER names the
# hpcworker to run: the gate's clone hands it to gate.sh, and by hand it is found on PATH. A job's
# output goes to hpcworker's log folder for the project, read back with `job log`, and every job
# is one line of the project's ledger. HPCW_DRY=1 prints each submission and queues nothing.
HPCW_PROJECT=schwingnet

hpcw_found() {  # the hpcworker HPCWORKER names, else the one on PATH
  if [ -n "${HPCWORKER:-}" ]; then
    [ -f "$HPCWORKER" ] && { echo "$HPCWORKER"; return 0; }
    echo "hpcw: HPCWORKER names $HPCWORKER, which is not there" >&2; return 1
  fi
  command -v hpcworker 2>/dev/null && return 0
  echo "hpcw: no hpcworker: the grid gate hands its own as HPCWORKER, else put hpcworker on PATH" >&2
  return 1
}

hpcw_bin() {  # the hpcworker to run, framework 27 or later, or a refusal on stderr
  # Framework 27 brought --partition, --no-requeue and the caller's own environment for the job;
  # an older one refuses those options or hands the job hpcworker's environment, without RUN or PART.
  local bin said framework
  bin=$(hpcw_found) || return 1
  said=$(bash "$bin" job version 2>/dev/null)
  framework=$(printf '%s\n' "$said" | sed -n 's/^HPCW-JOB version \([0-9][0-9]*\) interface .*/\1/p' | head -n 1)
  [ -n "$framework" ] && [ "$framework" -ge 27 ] \
    || { echo "hpcw: $bin is framework ${framework:-unknown}; job submit needs 27 or later (the gate word update brings it)" >&2; return 1; }
  echo "$bin"
}

hpcw() {  # hpcw VERB [ARG...]: one hpcworker job call (the gate's clone keeps the file 0644, so through bash)
  local bin
  bin=$(hpcw_bin) || return 1
  bash "$bin" job "$@"
}

HPCW_AFTER=()
hpcw_after() {  # hpcw_after DEPS: sbatch's dependency text (afterok:1,afterany:2:3) as job submit's --after
  # options, into HPCW_AFTER; anything else is refused, so no job is ever queued without its wait
  local one kind ids id
  HPCW_AFTER=()
  for one in ${1//,/ }; do
    kind=${one%%:*} ids=${one#*:}
    case "$kind" in
      afterok) kind=ok ;;
      afterany) kind=any ;;
      *) echo "hpcw: $one is neither afterok nor afterany; nothing was queued" >&2; HPCW_AFTER=(); return 1 ;;
    esac
    for id in ${ids//:/ }; do
      [[ $id =~ ^[0-9]+$|^DRY_ ]] || { echo "hpcw: $one names no job id; nothing was queued" >&2; HPCW_AFTER=(); return 1; }
      HPCW_AFTER+=(--after "$id:$kind")
    done
  done
}

hpcw_is_array() {  # hpcw_is_array [job submit options...] -- ...: whether the options ask for an array
  while [ $# -gt 0 ] && [ "$1" != -- ]; do [ "$1" = --array ] && return 0; shift; done
  return 1
}

hpcw_submit() {  # hpcw_submit NAME CLASS [K=V...] [job submit options...] -- SCRIPT [ARG...]: the job id on stdout
  # K=V pairs reach the job's environment (job submit hands it the caller's), never --export's comma
  # grammar, which would cut a value that holds a comma. Each shape is asked with --check first, so
  # a job the scheduler would refuse is never queued and the reason comes back whole.
  local name=$1 class=$2 envs=() out id
  shift 2
  while [ $# -gt 0 ] && [[ $1 =~ ^[A-Z_][A-Z0-9_]*= ]]; do envs+=("$1"); shift; done
  # SBATCH=echo was the dry run before issue #77; with hpcworker on PATH it would now queue for real
  if [ -n "${SBATCH:-}" ] && [ -z "${HPCW_DRY:-}" ]; then
    echo "hpcw: SBATCH is no longer read; HPCW_DRY=1 is the dry run, so nothing was queued" >&2; return 1
  fi
  if [ -n "${HPCW_DRY:-}" ]; then
    echo "would submit: ${envs[*]+${envs[*]} }hpcworker job submit --project $HPCW_PROJECT --name $name --class $class --dir $REPO/grid $*" >&2
    echo "DRY_$name"
    return 0
  fi
  local bin call
  bin=$(hpcw_bin) || return 1
  call=(job submit --project "$HPCW_PROJECT" --name "$name" --class "$class" --dir "$REPO/grid")
  # An array is not asked first: whether Slurm's --test-only takes --array is not measured on the
  # grid, and a refusal there would stop every array word; its submission answers the same way.
  if ! hpcw_is_array "$@"; then
    out=$(env ${envs[@]+"${envs[@]}"} bash "$bin" "${call[@]}" --check "$@" 2>&1) \
      || { echo "hpcworker refused $name: $(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')" >&2; return 1; }
  fi
  out=$(env ${envs[@]+"${envs[@]}"} bash "$bin" "${call[@]}" "$@" 2>&1)
  id=$(printf '%s\n' "$out" | sed -n 's/^HPCW-JOB submitted \([0-9][0-9]*\) .*/\1/p' | tail -n 1)
  [ -n "$id" ] || { echo "hpcworker refused $name: $(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')" >&2; return 1; }
  echo "$id"
}
