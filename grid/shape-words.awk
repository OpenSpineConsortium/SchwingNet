# The words grid/log-shapes.awk and grid/report-shapes.awk share (issue #80): which messages may be
# shown, and the system phrases a withheld line is still named by. Loaded first with awk -f, before
# either script; gawk 4.0 on the login node and mawk on CI read it, so no regular expression here
# uses a {n} interval, which mawk 1.3 does not read.

# A message is shown only when it can carry no value read from a file: no path, no quoted value,
# no run of five or more digits (a date, a UID's part, a person's number, a job's id) and no long
# run of hex digits.
function message_is_plain(text) {
  if (text ~ /[\/\\]/) return 0
  if (text ~ /["'`]/) return 0
  if (text ~ /[0-9][0-9][0-9][0-9][0-9]/) return 0
  if (text ~ /[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]/) return 0
  return 1
}

# The phrase of a few system messages a line holds, or "" when it holds none of them.
function system_phrase(line,    n, i, phrases) {
  n = split("Killed|No space left on device|Disk quota exceeded|Permission denied|Segmentation fault|Out of memory|oom_kill|oom-kill|Exceeded job memory limit|DUE TO TIME LIMIT|DUE TO PREEMPTION|DUE TO NODE FAILURE|CANCELLED AT|Job step aborted|Socket timed out|Invalid qos specification|Invalid partition", phrases, "|")
  for (i = 1; i <= n; i++) {
    if (index(line, phrases[i]) > 0) return phrases[i]
  }
  return ""
}
