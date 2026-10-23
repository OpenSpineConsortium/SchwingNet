# shellcheck shell=bash
# wsuquota with the lab volume after it (the owner's ask of 2026-10-23: "always print it when i type
# wsuquota"). WSU's wsuquota reads only the home directory. Sourced from ~/.bashrc, this wraps
# whatever wsuquota is in the owner's shell, an alias, a function or a command, so that typing it
# prints WSU's readout first and then the lab volume's, from grid/oschome-quota.sh, the reading the
# size rule decides by (grid/size-rule.sh). Sourcing it prints nothing; sourcing it again, as a
# second `source ~/.bashrc` does, wraps nothing twice.
#
#   echo 'source ~/SchwingNet/grid/wsuquota.bash' >> ~/.bashrc && source ~/.bashrc
#
# The gate brings ~/SchwingNet to main before every word, so the readout is always the merged one.

_SCHWINGNET_WSUQUOTA=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/oschome-quota.sh

# An alias or a function is kept as text to run, the alias's own text or the function under another
# name; a command is looked up when wsuquota is typed, on the PATH of that moment. The alias goes
# first, since it hides a function of the same name, and where the function is already this
# wrapper the original it holds stays.
if [ -n "${BASH_ALIASES[wsuquota]+set}" ]; then
  _schwingnet_wsuquota_original=${BASH_ALIASES[wsuquota]}
  unalias wsuquota
elif [ "$(type -t wsuquota)" = function ]; then
  case "$(declare -f wsuquota)" in
    *_schwingnet_wsuquota_inside*) ;;
    *) eval "$(declare -f wsuquota | sed '1s/^wsuquota /_schwingnet_wsuquota_function /')"
       _schwingnet_wsuquota_original=_schwingnet_wsuquota_function ;;
  esac
else
  _schwingnet_wsuquota_original=""
fi

# With the keyword function, so an alias of the name, were one still there, is not expanded in it.
function wsuquota {
  # An original that names wsuquota itself, as an alias adding a flag to the command does, reaches
  # the command and never this wrapper again.
  if [ -n "${_schwingnet_wsuquota_inside:-}" ]; then
    command wsuquota "$@"
    return
  fi
  local _schwingnet_wsuquota_inside=1 status=0
  if [ -n "${_schwingnet_wsuquota_original:-}" ]; then
    eval "$_schwingnet_wsuquota_original"' "$@"' || status=$?
    echo
  elif type -P wsuquota > /dev/null; then
    command wsuquota "$@" || status=$?
    echo
  fi
  if [ -f "$_SCHWINGNET_WSUQUOTA" ]; then
    bash "$_SCHWINGNET_WSUQUOTA" || status=$?
  else
    echo "The lab volume's readout is not there: $_SCHWINGNET_WSUQUOTA"
    status=1
  fi
  return "$status"
}
