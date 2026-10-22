# What grid/gate.sh 'status' shows of a stage report (issue #80). The reports are the stages' own
# lines, but some embed a tool's last line ("refused: <what ingest.py said>") and every one names
# paths on the volume, whose folders under a bank can carry a case's or a person's name. So every
# path is cut to the folder it starts under: <data root: carmlspine> for one under the data root,
# <runs>, <models> and <repo> for the others, <path> for any other; and the reason after a
# "refused:" or "FAILED:" is kept only where it holds no value (shape-words.awk), else withheld.
# grid/redact.sed runs on what this keeps, as a second net.
# Run as awk -v data=<data root> -v runs=<runs> -v models=<models> -v repo=<repo>
# -f grid/shape-words.awk -f grid/report-shapes.awk, with gawk 4.0 on the login node and mawk on CI.

# The text with every path that starts with PREFIX cut to NAME, and for the data root to the first
# folder under it, by index and not by a regular expression, since a prefix is a path, not a pattern.
function cut_paths(text, prefix, name,    at, rest, top, out) {
  if (prefix == "") return text
  out = ""
  while ((at = index(text, prefix)) > 0) {
    rest = substr(text, at + length(prefix))
    if (rest != "" && substr(rest, 1, 1) !~ /[\/ \t:;,)"']/) { out = out substr(text, 1, at + length(prefix) - 1); text = rest; continue }
    sub(/^\//, "", rest)
    top = rest
    sub(/[\/ \t:;,)"'].*/, "", top)
    sub(/^[^ \t:;,)"']*/, "", rest)
    out = out substr(text, 1, at - 1) (name == "data" && top != "" ? "<data root: " top ">" : "<" name ">")
    text = rest
  }
  return out text
}
# A reason is judged after the cuts, so the folders they name stay readable, but a cut that left
# a <path> (a relative path such as <person>/<file> keeps its first part before it) or any file
# name, which a bank's or an ingest's refusal quotes, withholds it all.
function reason_is_plain(text) {
  if (index(text, "<path>") > 0) return 0
  if (text ~ /[A-Za-z0-9_-]\.[A-Za-z][A-Za-z0-9]*/) return 0
  return message_is_plain(text)
}
# Every other path is cut whole, but a count such as 21/21 or 1/27 (digits on both sides of the
# slash and nothing else) is a fraction and stays.
function cut_other_paths(text,    out, piece, before) {
  out = ""
  while (match(text, /\/[A-Za-z0-9._~+-][^ \t:;,)"'|]*/)) {
    piece = substr(text, RSTART, RLENGTH)
    before = substr(text, 1, RSTART - 1)
    if (before ~ /(^|[^A-Za-z0-9_.\/-])[0-9]+$/ && piece ~ /^\/[0-9]+\.?$/) out = out before piece
    else out = out before "<path>"
    text = substr(text, RSTART + RLENGTH)
  }
  return out text
}
{
  line = $0
  line = cut_paths(line, data, "data")
  line = cut_paths(line, runs, "runs")
  line = cut_paths(line, models, "models")
  line = cut_paths(line, repo, "repo")
  line = cut_other_paths(line)
  if (match(line, /(refused|FAILED):/)) {
    head = substr(line, 1, RSTART + RLENGTH - 1)
    reason = substr(line, RSTART + RLENGTH)
    if (!reason_is_plain(reason)) line = head " <reason withheld: it can quote a value; the whole report stays on the grid>"
  }
  print line
}
