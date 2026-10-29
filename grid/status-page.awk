# What grid/gate.sh 'status' shows of its sections in the room of one page (issue #252): the page
# reaches the gate as 400 lines and 64 KiB at most, and its sections together can hold twice that
# on the grid, so a cut at the page's end once took the newest jobs, every failed job's log and
# every stage report, which come after the space, the sweeps and the sample manifest. Each section
# is made whole first and then handed lines and bytes in the order a reader needs them: the space,
# the sweeps' progress, the benchmarks' (the DRR domain-gap study's PROGRESS.txt) and the launched
# flows' (flows/stage_progress.py), the newest
# jobs, the failed jobs' logs newest first, the newest run's latency, the stage reports newest first
# with the sample manifest among them by its date, the newest run and the latency probe. Every
# section keeps its place on the page. One handed fewer
# lines than it holds keeps its heading and says how many lines it left out: the job list, a
# failed job's log and a stage report keep their last lines, which are their newest, and the rest
# their first, which for the manifest are its largest groups. One that cannot keep even its
# heading is named on the page's last line, so no section leaves the page unsaid.
# A section starts at each line that does not start with a space (its heading, "## ..."); its
# other lines are indented. Run as awk -v lines=<page lines> -v bytes=<page bytes>
# -v samples_after=<stage reports newer than the manifest> -f grid/status-page.awk, with LC_ALL=C
# so that length counts bytes, gawk 4.0 on the login node and mawk on CI.

function kind_of(heading) {
  if (heading ~ /^## SAMPLES-STAGE-REPORT\.md \(/) return "manifest"
  if (heading ~ /STAGE-REPORT\.md \(/) return "report"
  if (heading ~ /^## space on the lab volume/) return "space"
  if (heading ~ /^## sweep [a-z0-9_]*, /) return "sweep"
  if (heading ~ /^## bench [a-z0-9_]*, progress \(/) return "bench"
  if (heading ~ /^## flow [a-z0-9_]+ [A-Za-z0-9_.-]+, progress \(/) return "flow"
  if (heading ~ /^## the gate's newest jobs/ || heading ~ /^no job submitted by the gate/) return "jobs"
  if (heading ~ /^## [0-9]/) return "failed"
  if (heading ~ /^## latency of the newest run/) return "latency"
  if (heading ~ /^## newest run:/) return "run"
  if (heading ~ /^## the latency probe/) return "probe"
  return "other"
}
# The order the kinds are handed room in; a failed job's log goes newest first, the reverse of the
# page's id order, and the stage reports as the page shows them, newest first. A benchmark's
# progress is a live view as a sweep's is, so it is handed room at the sweeps' rank, and so is a
# launched flow's progress page in short lines.
function rank_of(kind) {
  if (kind == "space") return 1
  if (kind == "sweep" || kind == "bench" || kind == "flow") return 2
  if (kind == "jobs") return 3
  if (kind == "failed") return 4
  if (kind == "latency") return 5
  if (kind == "report" || kind == "manifest") return 6
  if (kind == "run" || kind == "other") return 7
  return 8
}
function queue(b) { order[++queued] = b }
function queue_rank(r,    b, reports, manifest_queued) {
  if (r == 4) {
    for (b = blocks; b >= 1; b--) if (rank[b] == r) queue(b)
    return
  }
  reports = 0
  for (b = 1; b <= blocks; b++) {
    if (rank[b] != r || kind[b] == "manifest") continue
    if (kind[b] == "report" && reports++ == samples_after + 0 && manifest) { queue(manifest); manifest_queued = 1 }
    queue(b)
  }
  if (r == 6 && manifest && !manifest_queued) queue(manifest)
}
function size_of(n) { return length(line[n]) + 1 }
# How many of block b's lines fit in most_lines lines and most_bytes bytes, taken as its style
# keeps them: its first lines, or its heading and then its last lines; 0 when not even its heading fits.
function fitting(b, most_lines, most_bytes,    n, used, taken) {
  if (most_lines < 1 || size_of(first[b]) > most_bytes) return 0
  used = size_of(first[b]); taken = 1
  if (tail_style[b]) {
    for (n = last[b]; n > first[b] && taken < most_lines && used + size_of(n) <= most_bytes; n--) { used += size_of(n); taken++ }
  } else {
    for (n = first[b] + 1; n <= last[b] && taken < most_lines && used + size_of(n) <= most_bytes; n++) { used += size_of(n); taken++ }
  }
  return taken
}
function bytes_kept(b, k,    n, used) {
  used = size_of(first[b])
  if (tail_style[b]) { for (n = last[b]; n > last[b] - (k - 1); n--) used += size_of(n) }
  else { for (n = first[b] + 1; n < first[b] + k; n++) used += size_of(n) }
  return used
}
function note_of(b) {
  return "  (" left_out[b] " " (tail_style[b] ? "earlier" : "more") " line" (left_out[b] == 1 ? "" : "s") \
    " of this section not shown, for want of room on the page)"
}
function plural(count, one, many) { return count == 1 ? one : count " " many }
function unsaid(    k, said, phrase) {
  said = ""
  for (k = 1; k <= 11; k++) {
    if (!dropped[names[k]]) continue
    if (names[k] == "space") phrase = "the space on the lab volume"
    else if (names[k] == "sweep") phrase = plural(dropped["sweep"], "one sweep's progress", "sweeps' progress")
    else if (names[k] == "bench") phrase = plural(dropped["bench"], "one benchmark's progress", "benchmarks' progress")
    else if (names[k] == "jobs") phrase = "the job list"
    else if (names[k] == "failed") phrase = plural(dropped["failed"], "one failed job's log", "failed jobs' logs")
    else if (names[k] == "latency") phrase = "the newest run's latency"
    else if (names[k] == "report") phrase = plural(dropped["report"], "one stage report", "stage reports")
    else if (names[k] == "manifest") phrase = "the sample manifest"
    else if (names[k] == "run") phrase = "the newest run"
    else if (names[k] == "probe") phrase = "the latency probe"
    else phrase = plural(dropped["other"], "one other section", "other sections")
    said = said (said == "" ? "" : ", ") phrase
  }
  return said
}
{
  if (blocks == 0 || ($0 != "" && substr($0, 1, 1) != " ")) { blocks++; first[blocks] = NR }
  line[NR] = $0
  last[blocks] = NR
  size[blocks] += length($0) + 1
}
END {
  split("space sweep bench jobs failed latency report manifest run probe other", names, " ")
  for (b = 1; b <= blocks; b++) {
    kind[b] = kind_of(line[first[b]])
    rank[b] = rank_of(kind[b])
    tail_style[b] = (kind[b] == "jobs" || kind[b] == "failed" || kind[b] == "report")
    if (kind[b] == "manifest") manifest = b
  }
  for (r = 1; r <= 8; r++) queue_rank(r)
  # The page's last line, which names a section that found no room, is held back from the start.
  room_lines = lines - 1; room_bytes = bytes - 320
  for (i = 1; i <= queued; i++) {
    b = order[i]
    whole = last[b] - first[b] + 1
    if (whole <= room_lines && size[b] <= room_bytes) {
      kept[b] = whole; room_lines -= whole; room_bytes -= size[b]
      continue
    }
    # a section cut short spends one line, and at most 160 bytes, on saying so
    kept[b] = fitting(b, room_lines - 1, room_bytes - 160)
    if (kept[b] == 0) { dropped[kind[b]]++; continue }
    left_out[b] = whole - kept[b]
    room_lines -= kept[b] + 1
    room_bytes -= bytes_kept(b, kept[b]) + length(note_of(b)) + 1
  }
  for (b = 1; b <= blocks; b++) {
    if (!kept[b]) continue
    print line[first[b]]
    if (!left_out[b]) { for (n = first[b] + 1; n <= last[b]; n++) print line[n]; continue }
    if (tail_style[b]) {
      print note_of(b)
      for (n = last[b] - (kept[b] - 2); n <= last[b]; n++) if (n > first[b]) print line[n]
    } else {
      for (n = first[b] + 1; n < first[b] + kept[b]; n++) print line[n]
      print note_of(b)
    }
  }
  said = unsaid()
  if (said != "") print "## not shown, for want of room on the page (" lines " lines and " int(bytes / 1024) " KiB): " said
}
