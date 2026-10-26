#!/bin/bash
# venv_for PINS: a throwaway virtual environment holding PINS beside train-gpu's packages (torch among
# them), made once on the lab volume under a name that carries the pins and kept for a rerun, so the
# repository takes no new dependency and pixi.lock is never touched. Sourced by grid/bench.sbatch for
# a public model's package (#287) and by the pack stage of grid/anomaly.sbatch for FleXray's packager
# with thunderpack and nibabel (#391); a stage that runs from a copy of the code sources the copy's,
# whose box.sh sits beside this file. Standard library bash; no job header, since nothing here is a job.
venv_for() {  # venv_for PINS: a virtual environment holding PINS beside train-gpu's packages, made once
  local key venv box
  box=$(dirname "${BASH_SOURCE[0]}")/box.sh
  key=$(printf '%s' "$1" | sha256sum | cut -c1-12)
  venv=${LAB:-/rs/rs_grp_oschome}/go2432/.cache/bench/venv-$key
  if [ ! -f "$venv/READY" ]; then
    rm -rf "$venv"
    bash "$box" pixi run --locked -e train-gpu python -m venv --system-site-packages "$venv" || return 1
    # shellcheck disable=SC2086
    bash "$box" "$venv/bin/python" -m pip install --quiet $1 || return 1
    printf '%s\n' "$1" > "$venv/READY"
  fi
  echo "$venv"
}
