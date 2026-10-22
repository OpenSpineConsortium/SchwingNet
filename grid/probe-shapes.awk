# What grid/gate.sh 'status' shows of the latency probe's log (issue #87): only the lines whose
# shape is the probe's own count, suffix, size, PNG dimension or meta-key line, each with its
# paths and file names taken out, so the answer #13 needs leaves the grid and no folder or file
# name under a bank does, which issue #80 found can carry a case's or a person's name. A case is
# named only as case<digits>, C-ArmLSpine's own case numbers. Every other line is dropped and the
# last line out says how many. Run as awk -f grid/probe-shapes.awk, with gawk 4.0 on the login
# node and mawk on CI, so no regular expression here uses a {n} interval.

function short(word) { return length(word) > 0 && length(word) <= 16 }
/^raw case[0-9]+: [0-9]+ files under / { print $1, $2, $3, $4; next }
/^bank case[0-9]+: [0-9]+ PNG frames under / { print $1, $2, $3, $4, $5; next }
/^  suffixes: \{(('(\.[a-z0-9]+|\(none\))': [0-9]+)(, )?)*\}$/ { print; next }
/^  commonest sizes in bytes: \[((\([0-9]+, [0-9]+\))(, )?)*\]$/ { print; next }
/^  frames with meta: [0-9]+$/ { print; next }
/^  first: .* [0-9]+x[0-9]+, [0-9]+-bit, colour type [0-9]+ \| last: / {
  match($0, /[0-9]+x[0-9]+, [0-9]+-bit, colour type [0-9]+/)
  print "  first frame:", substr($0, RSTART, RLENGTH); next
}
/^  meta keys: \[[a-z_', ]*\] \| view: [A-Za-z0-9_'{}:., -]* \| boxes: [0-9]+ \| box keys: (\[[a-z_', ]*\]|None) \| levels: \[[A-Za-z0-9', ]*\]$/ { print; next }
/^ +[0-9]+  \// {
  n = split($2, part, "/")
  if (part[n] ~ /^case[0-9]+$/) { print "  " $1 " files in " part[n]; next }
  if (n > 1 && part[n - 1] ~ /^case[0-9]+$/ && part[n] ~ /^[A-Za-z0-9_]+$/ && short(part[n])) { print "  " $1 " files in " part[n - 1] "/" part[n]; next }
}
/^SN_LATENCY probe start / { next }
{ dropped++ }
END { if (dropped) print "(" dropped " of its lines not shown: only the probe's own counts, suffixes, sizes and meta keys leave the grid)" }
