"""What a step asks Slurm for, and what Slurm answers: pure text, no scheduler call.

The grid rules (spine-program CLAUDE.md, rule 7; docs/setup/grid.md) hold here as text the
runner writes: every job has a wall time, the command runs through pixi's locked environment,
and nothing secret is on the script's lines, since the scheduler keeps a copy of every script it
is given. The script names no partition, QoS, GPU request or log: hpcworker's job submit queues
it with those from the site profile, in the run directory, and writes its output to the
project's log folder (issue #77).
"""

import re

from beartype import beartype
from beethoven_qa.contracts import ensure, require

from schwingnet.flow import JobSpec

SUBMITTED = re.compile(r"^HPCW-JOB submitted (\d+) \S+ ([A-Za-z0-9_.,-]+)/([A-Za-z0-9_.-]+) log ", re.MULTILINE)
SECRET_SHAPES = re.compile(r"(?i)(token|secret|password|api[_-]?key)\s*=")


@beartype
@require(lambda hours: 0 < hours <= 168, "a wall time is under a week")
@ensure(lambda result: re.fullmatch(r"\d{2,3}:\d{2}:00", result) is not None, "HH:MM:00")
def wall_time(hours: float) -> str:
    """Slurm's HH:MM:SS for a wall time in hours, rounded up to the minute."""
    minutes = int(hours * 60 + 0.999999)
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


@beartype
@require(lambda checkout: checkout.startswith("/"), "the checkout is absolute")
@require(lambda checkout: "\n" not in checkout and " " not in checkout, "a plain path")
@ensure(lambda result: result.startswith("#!/bin/bash\n"), "a bash script")
@ensure(lambda result: "#SBATCH --time=" in result, "every job has a wall time")
@ensure(lambda result: all(f"#SBATCH --{word}" not in result for word in ("partition", "qos", "gres", "output")), "placement is hpcworker's")
@ensure(lambda result: SECRET_SHAPES.search(result) is None, "no secret on a script's lines")
@ensure(lambda result: result.endswith("\n"), "ends with a newline")
def sbatch_script(job: JobSpec, checkout: str) -> str:
    """The script one step is submitted as, in the run directory: what it needs, never where."""
    lines = [
        "#!/bin/bash",
        f"#SBATCH --cpus-per-task={job.cpus}",
        f"#SBATCH --mem={job.memory_gb}G",
        f"#SBATCH --time={wall_time(job.hours)}",
        "set -euo pipefail",
        f"cd {checkout}",
        f"exec pixi run --locked -e {job.environment} {job.command}",
    ]
    return "\n".join(lines) + "\n"


@beartype
@ensure(lambda result: result is None or result[0].isdigit(), "a job id is digits")
@ensure(lambda result: result is None or (result[1] != "" and result[2] != "none"), "the placement hpcworker gave")
def submitted_of(answer: str) -> tuple[str, str, str | None] | None:
    """The job id, partition and QoS hpcworker's job submit printed, or None when it queued nothing.

    Its line is "HPCW-JOB submitted <id> <name> <partition>/<qos> log <path>", the QoS "none"
    where the class has none.
    """
    found = SUBMITTED.search(answer)
    if found is None:
        return None
    qos = found.group(3)
    return found.group(1), found.group(2), None if qos == "none" else qos


@beartype
@require(lambda text: re.fullmatch(r"(\d+-)?\d{1,2}:\d{2}:\d{2}", text) is not None, "D-HH:MM:SS")
@ensure(lambda result: result >= 0, "seconds are never negative")
def elapsed_seconds(text: str) -> int:
    """Seconds from sacct's Elapsed column, written D-HH:MM:SS or HH:MM:SS."""
    days = 0
    if "-" in text:
        day_text, text = text.split("-", 1)
        days = int(day_text)
    hours, minutes, seconds = (int(part) for part in text.split(":"))
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


FINISHED = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"})


@beartype
@ensure(lambda result, state: result == (state.split()[0] in FINISHED if state.strip() else False))
def is_finished(state: str) -> bool:
    """Whether a sacct State means the job is over; CANCELLED by 1234 counts as over."""
    words = state.split()
    return bool(words) and words[0] in FINISHED
