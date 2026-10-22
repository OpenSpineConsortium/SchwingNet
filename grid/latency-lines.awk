# What grid/gate.sh 'status' shows of the newest run's latency work (issue #99): one line for each
# JSON file tools/latency.py and tools/sweep.py write into the run directory (onnx/parity-*.json,
# latency/<arm>.json, evaluate/latency.json, sweep/<name>/summary.json), built only from the keys
# named here, so the timing and the parity reach a session through the gate and no path, file
# name or other value does. A text value is shown only where it is plain words (an arm, a runtime,
# a device such as "NVIDIA H200"); the video is named by its suffix alone. The tools write JSON
# with an indent of one, which this reads by its indentation: a key at one space is the file's
# own, at two spaces it belongs to the object above it, at three to an accuracy group.
# Run as awk -f grid/latency-lines.awk <files>, with gawk 4.0 on the login node and mawk on CI,
# so no regular expression here uses a {n} interval.

function plain(text) { return (text ~ /^[A-Za-z0-9 (),._+-]+$/ && length(text) <= 48) ? text : "<withheld>" }
function ms(value) { return (value ~ /^-?[0-9.eE+-]+$/) ? sprintf("%.1f", value) : "?" }
function int_of(value) { return (value ~ /^[0-9]+$/) ? value : "?" }
function yes(value) { return value == "true" ? "yes" : (value == "false" ? "no" : "?") }
function value_of(line) {
  sub(/^ *"[^"]*": */, "", line)
  sub(/,$/, "", line)
  if (line ~ /^".*"$/) line = substr(line, 2, length(line) - 2)
  return line
}
function key_of(line) {
  sub(/^ *"/, "", line)
  sub(/".*/, "", line)
  return line
}
function reset() { split("", top); split("", correct); split("", total); groups = ""; obj = ""; group = "" }
function flush(file,    kind, n, list, i, g) {
  if (file == "") return
  if (file ~ /\/onnx\/parity-[^\/]*\.json$/) {
    print "parity " plain(top["runtime"]) " on " plain(top["device"]) ": " int_of(top["crops"]) " crops of " int_of(top["persons"]) " persons (" int_of(top["witness_frames"]) " witness frames), max difference " top["max_abs_probability_difference"] + 0 ", labels equal " yes(top["labels_equal"]) ", passed " yes(top["passed"])
  } else if (file ~ /\/latency\/[^\/]*\.json$/) {
    print "arm " plain(top["arm"]) " on " plain(top["device"]) ": " int_of(top["frames"]) " frames, p50 " ms(top["ms_per_frame_median"]) " ms, p95 " ms(top["ms_per_frame_p95"]) " ms, p99 " ms(top["ms_per_frame_p99"]) " ms, within the " ms(top["budget_ms"]) " ms budget " yes(top["within_budget"])
  } else if (file ~ /\/evaluate\/latency\.json$/) {
    print "headline: " plain(top["arm"]) " on " plain(top["device"]) ", p50 " ms(top["ms_per_frame_median"]) " ms, p95 " ms(top["ms_per_frame_p95"]) " ms"
  } else if (file ~ /\/sweep\/[^\/]*\/summary\.json$/) {
    video = top["video"]
    sub(/.*\./, "", video)
    print "sweep " plain(top["name"]) ": " int_of(top["frames"]) " frames, " plain(top["runtime"]) " on " plain(top["device"]) ", boxes " plain(top["box_source"]) ", p50 " ms(top["latency_ms.p50"]) " ms, p95 " ms(top["latency_ms.p95"]) " ms, within budget " yes(top["within_budget"]) ", video " (top["video"] == "" ? "none" : plain(video))
    n = split(groups, list, "\034")
    for (i = 2; i <= n; i++) {
      g = list[i]
      print "  accuracy " plain(g) ": " int_of(correct[g]) "/" int_of(total[g])
    }
  }
}
FNR == 1 { flush(current); reset(); current = FILENAME }
/^ "[^"]*": \{$/ { obj = key_of($0); next }
/^ \},?$/ { obj = ""; next }
/^ "[^"]*": / { top[key_of($0)] = value_of($0); next }
obj == "accuracy" && /^  "[^"]*": \{$/ { group = key_of($0); groups = groups "\034" group; next }
obj == "accuracy" && /^   "(correct|total)": / { if (key_of($0) == "correct") correct[group] = value_of($0); else total[group] = value_of($0); next }
obj != "" && /^  "[^"]*": / { top[obj "." key_of($0)] = value_of($0); next }
END { flush(current) }
