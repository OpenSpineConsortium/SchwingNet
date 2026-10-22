# What grid/gate.sh 'status' keeps of the log of a job that can read a DICOM header, a person key
# made from one or a credential (issue #80): only lines whose shape says they carry none, so the
# owner reads why a job failed through the gate and nothing of a patient or a sign-in leaves the
# grid. Every other line is counted and withheld; the last line out is "#withheld <count>".
# Run as awk -f grid/shape-words.awk -f grid/log-shapes.awk, with gawk 4.0 on the login node
# (CentOS 7) and mawk on CI, so no regular expression here uses a {n} interval, which mawk 1.3 does
# not read. grid/redact.sed runs on what this keeps, as a second net.
#
# Kept: a Python traceback's frames (the code's own file, line and source, never a value), its
# exception line with the message only for the types whose message names types and attributes
# alone, and then only where it holds no path, quoted value or long run of digits; the stages'
# start and _RC= lines; Slurm's own errors by their phrase; wget's and curl's status lines; the
# stages' section headers by id; and a line holding one of a few system phrases, as that phrase.
function keep(line) { print substr(line, 1, 200) }
function exception_type(line,    name) {
  name = line
  sub(/:.*/, "", name)
  sub(/.*\./, "", name)
  return name
}
# An AttributeError, a NameError and an import error quote names from the code, 'get' or 'torch',
# never values, so any quoted name is no value to them; the other types may quote only Python's
# own type names. Anything else quoted, a path or a long run of digits withholds the message.
function unquote_names(text, type) {
  if (type == "AttributeError" || type == "NameError" || type == "UnboundLocalError" || type == "ImportError" || type == "ModuleNotFoundError")
    gsub(/'[A-Za-z_][A-Za-z0-9_.]*'/, "NAME", text)
  else
    gsub(/'(str|int|float|bool|bytes|list|dict|tuple|set|frozenset|NoneType|object|type|function|module|Path|PosixPath)'/, "NAME", text)
  return text
}
BEGIN {
  safe = " AttributeError ImportError ModuleNotFoundError NameError UnboundLocalError RecursionError"
  safe = safe " MemoryError NotImplementedError ZeroDivisionError IndexError TypeError StopIteration "
  withheld = 0
  source = 0
}
{
  line = $0
  sub(/[ \t]+$/, "", line)
  after_frame = source
  source = 0
  if (line == "") next
  if (line ~ /^Traceback \(most recent call last\):$/ ||
      line == "During handling of the above exception, another exception occurred:" ||
      line == "The above exception was the direct cause of the following exception:") { keep(line); next }
  if (line ~ /^  File "[^"]*\.py", line [0-9]+, in [A-Za-z_<][A-Za-z0-9_<>.]*$/ ||
      line ~ /^  File "<[a-z]+>", line [0-9]+, in [A-Za-z_<][A-Za-z0-9_<>.]*$/) { keep(line); source = 1; next }
  if (after_frame && line ~ /^    [^ ]/) { keep(line); next }
  if (line ~ /^[ \t]*[~^][~^ ]*$/) { keep(line); next }
  if (line ~ /^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception|Exit|Interrupt|Warning|Failure)(:|$)/) {
    name = line; sub(/:.*/, "", name)
    message = line; sub(/^[^:]*:[ ]*/, "", message)
    if (index(line, ":") == 0) keep(line)
    else if (index(safe, " " exception_type(line) " ") > 0 && message_is_plain(unquote_names(message, exception_type(line)))) keep(line)
    else keep(name ": <message withheld>")
    next
  }
  if (line ~ /^[A-Z][A-Z0-9_]*_RC=-?[0-9]+$/ || line ~ /^[A-Z][A-Z0-9_]*_RC=-?[0-9]+ [0-9][0-9: -]*$/) { keep(line); next }
  if (match(line, /^[A-Z][A-Z0-9_]* start [0-9][0-9-]* [0-9][0-9:]* on [A-Za-z0-9._-]+ job [0-9]*/)) {
    keep(substr(line, 1, RLENGTH)); next
  }
  if (line ~ /^[A-Z][A-Z0-9_]* lock [0-9][0-9-]* [0-9][0-9:]*$/) { keep(line); next }
  if (line ~ /^(slurmstepd|srun): error: /) {
    # Slurm's own errors name the node, the job and the time; only the phrase is kept.
    name = line; sub(/:.*/, "", name)
    phrase = system_phrase(line)
    keep(name ": error: " (phrase == "" ? "<message withheld>" : "[" phrase "]"))
    next
  }
  if (line ~ /^(HTTP|Proxy) request sent, awaiting response\.\.\. [0-9][0-9][0-9]( [A-Za-z -]*)?$/ ||
      line ~ /^([0-9][0-9: -]* )?ERROR [0-9][0-9][0-9]: [A-Za-z -]*\.?$/ ||
      line == "Authorization failed." || line == "Username/Password Authentication Failed.") { keep(line); next }
  if (line ~ /^curl: \([0-9]+\) / && line !~ /[\/?=@]/) { keep(line); next }
  if (match(line, /^== [a-z0-9_]+/)) { keep(substr(line, 1, RLENGTH)); next }
  if (match(line, /^[a-z0-9_]+: [a-z][a-z0-9 ;]* at [0-9][0-9TZ:. +-]*/)) { keep(substr(line, 1, RLENGTH)); next }
  phrase = system_phrase(line)
  if (phrase != "") { keep("[a line with: " phrase "]"); next }
  withheld++
}
END { print "#withheld " withheld }
