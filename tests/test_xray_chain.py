"""The X-ray fetch chain under grid/: the fetch list is read and planned without the network, a
run is refused on the login node, a synthetic raw folder becomes a bank in the builders' format,
every Slurm script parses, and the submit scripts print three dependent submissions in a dry run.
Standard library only, so the required check runs it; the ingest round trip of a bank, which
needs pydantic, is tests/schwingnet/test_bank.py."""

import importlib.util
import io
import fnmatch
import hashlib
import json
import os
import struct
import subprocess
import sys
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"
SBATCH_FILES = ("01-fetch.sbatch", "02-bank-ingest.sbatch", "03-catalog.sbatch", "platform-fetch.sbatch")
SCRIPTS = ("run-xray-chain.sh", "run-platform-fetch.sh", "size-rule.sh", "oschome-quota.sh", "wsuquota.bash")
GB = 1000 ** 3

# Stand-ins for what the size rule reads (#160), so no test reaches CephFS or Slurm. getfattr answers
# from FAKE_XATTRS, a file of "<folder> <attribute> <value>" lines in which a folder ending /* answers
# for every folder under it not named, the folder * for every folder not named otherwise, and an
# attribute given no value is not there, as on a folder with no quota, and a ~ in a value is a NUL,
# as getfattr may print one where CephFS's value ends, and a ^ a line break; squeue lists the job ids in
# FAKE_QUEUE, or fails where FAKE_SQUEUE_FAILS is set; the size reader says on stderr what it was
# asked, prints FAKE_SIZE and ends with FAKE_SIZE_RC; stat, used where a test names it as STAT, gives
# a folder's size and device from its lines "<folder> stat.size <bytes>" and "<folder> stat.dev <n>" in
# FAKE_XATTRS, else the real stat's, a link followed only under -L, as stat follows one, and a mount's
# kind as FAKE_FS_KIND, ceph unless set.
STAND_INS = {
    "getfattr": """#!/bin/bash
name=""; folder=""
while [ $# -gt 0 ]; do case "$1" in -n) name=$2; shift 2 ;; -*) shift ;; *) folder=$1; shift ;; esac; done
value=$(awk -v f="$folder" -v n="$name" '$2 == n && $1 == f { exact = $3; named = 1 }
  $2 == n && $1 ~ /[/][*]$/ && index(f, substr($1, 1, length($1) - 1)) == 1 { under = $3 }
  $2 == n && $1 == "*" { any = $3 }
  END { printf "%s", (named ? exact : (under != "" ? under : any)) }' "${FAKE_XATTRS:-/dev/null}")
[ -n "$value" ] || { echo "$folder: $name: No such attribute" >&2; exit 1; }
printf '%s' "$value" | tr '~^' '\\000\\n'
""",
    "squeue": """#!/bin/bash
[ -z "${FAKE_SQUEUE_FAILS:-}" ] || { echo "slurm_load_jobs error: Socket timed out" >&2; exit 1; }
cat "${FAKE_QUEUE:-/dev/null}" 2>/dev/null
exit 0
""",
    "sizer": """#!/bin/bash
echo "sizer: $*" >&2
printf '%s\\n' "${FAKE_SIZE:-no exact size; the test gave none}"
exit "${FAKE_SIZE_RC:-0}"
""",
    "stat": """#!/bin/bash
kind=""; format=""; folder=""; follow=""
while [ $# -gt 0 ]; do
  case "$1" in -f) kind=1; shift ;; -L) follow=-L; shift ;; -c) format=$2; shift 2 ;; *) folder=$1; shift ;; esac
done
[ -z "$kind" ] || { echo "${FAKE_FS_KIND:-ceph}"; exit 0; }
[ -z "$follow" ] || [ ! -L "$folder" ] || folder=$(readlink "$folder")
case "$format" in %s) key=stat.size ;; %d) key=stat.dev ;; *) key="" ;; esac
value=$(awk -v f="$folder" -v k="$key" '$1 == f && $2 == k { value = $3 } END { printf "%s", value }' "${FAKE_XATTRS:-/dev/null}")
[ -n "$value" ] || exec stat $follow -c "$format" "$folder"
echo "$value"
""",
}


class Volume:
    """A lab volume of a test's own: the stand-ins, its CephFS attributes, Slurm's queue and a data
    root on it."""

    def __init__(self, folder, quota=None, used=None):
        folder = Path(folder)
        self.tools = folder / "tools"
        self.tools.mkdir()
        for name, text in STAND_INS.items():
            (self.tools / name).write_text(text, encoding="utf-8")
            (self.tools / name).chmod(0o755)
        self.path = folder / "volume"
        self.data = self.path / "data"
        self.data.mkdir(parents=True)
        self.xattrs = folder / "xattrs"
        self.xattrs.write_text("", encoding="utf-8")
        self.queue = folder / "queue"
        self.queue.write_text("", encoding="utf-8")
        if quota is not None:
            self.attribute(self.path, "ceph.quota.max_bytes", quota)
        if used is not None:
            self.attribute(self.path, "ceph.dir.rbytes", used)
        # every landing reads as holding nothing until a test says otherwise
        self.attribute(f"{self.data}/*", "ceph.dir.rbytes", 0)

    def attribute(self, folder, name, value):
        with self.xattrs.open("a", encoding="utf-8") as handle:
            handle.write(f"{folder} {name} {value}\n")

    def live(self, *jobs):
        self.queue.write_text("".join(f"{job}\n" for job in jobs), encoding="utf-8")

    def meta(self, source, name, line):
        folder = self.data / source / "meta"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(line + "\n", encoding="utf-8")

    def admitted(self, source, job, need, base=0, landed=None):
        """A fetch of SOURCE the rule admitted as JOB when its landing held BASE, and what it holds now."""
        self.meta(source, "SIZE", f"admitted {job} {need} {base} 2026-10-23T12:00:00Z {need}")
        if landed is not None:
            self.attribute(self.data / source, "ceph.dir.rbytes", landed)

    def env(self, **extra):
        env = dict(GETFATTR=str(self.tools / "getfattr"), SQUEUE=str(self.tools / "squeue"),
                   SIZER=str(self.tools / "sizer"), FAKE_XATTRS=str(self.xattrs), FAKE_QUEUE=str(self.queue),
                   VOLUME=str(self.path), DATA_ROOT=str(self.data), USER="go2432")
        env.update(extra)
        return env


def volume_in(test, quota=None, used=None):
    import tempfile
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return Volume(tmp.name, quota, used)


def repo_copy(test):
    """A copy of the checkout's grid/, whose logs a test may write."""
    import shutil
    import tempfile
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    repo = Path(tmp.name) / "SchwingNet"
    shutil.copytree(GRID, repo / "grid", ignore=shutil.ignore_patterns("logs", "LAST_*"))
    (repo / "grid" / "logs").mkdir()
    return repo


def gate_jobs(repo, *lines):
    """grid/gate.sh's own list of what it submitted: (job, word, what) lines."""
    with (repo / "grid" / "logs" / "GATE_JOBS.txt").open("a", encoding="utf-8") as out:
        for job, word, what in lines:
            out.write(f"{job} {word} {what} 2026-10-23T09:00:00Z\n")


def shown(out):
    """What the gate word status keeps of a job's log (grid/gate.sh)."""
    return subprocess.run(["awk", "-f", str(GRID / "shape-words.awk"), "-f", str(GRID / "log-shapes.awk")],
                          input=out, capture_output=True, text=True, timeout=60).stdout


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def png(width, height, seed):
    raw = bytes(((x * 7 + y * 3 + seed) % 256) for y in range(height) for x in range(width + 1))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def run_tool(tool, argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = tool.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_raw(raw):
    """A raw copy in the NIH ChestX-ray14 layout: images/<patient 8 digits>_<n>.png, and a YOLO
    label folder beside it for the box test."""
    (raw / "images_001" / "images").mkdir(parents=True)
    (raw / "labels").mkdir()
    for index, (patient, follow) in enumerate([("00000001", "000"), ("00000001", "001"), ("00000002", "000")]):
        (raw / "images_001" / "images" / f"{patient}_{follow}.png").write_bytes(png(40, 30, index))
    (raw / "labels" / "00000001_000.txt").write_text("0 0.5 0.5 0.5 0.5\n1 0.2 0.2 0.1 0.1\n", encoding="utf-8")


def recipe_of(tmp, labels=None):
    return {
        "id": "nih_chestxray14", "raw": str(tmp / "raw"), "bank": str(tmp / "bank"),
        "images": ["**/images/*.png"], "format": "png",
        "person": {"regex": r"(?P<case>\d{8})_\d{3}\.png$"},
        "view": {"lat_from_ap_deg": 0.0, "gantry_deg": None},
        "device": {"make": None, "model": None, "detector": None},
        "split": "train", "labels": labels, "synthetic": False,
    }


class FetchListTest(unittest.TestCase):
    def test_every_entry_has_what_a_person_and_the_job_need(self):
        data = json.loads((GRID / "fetch-xray.json").read_text(encoding="utf-8"))
        ids = []
        for entry in data["open"] + data["credentialed"]:
            for key in ("id", "route", "source", "dest", "size_gb", "checksum", "confirm", "licence"):
                self.assertIn(key, entry, entry.get("id"))
            self.assertEqual(entry["dest"], f"{data['data_root']}/{entry['id']}/raw")
            self.assertTrue((ROOT / "data" / "registry" / f"{entry['id']}.json").is_file(), entry["id"])
            self.assertTrue((GRID / "banks" / f"{entry['id']}.json").is_file(), entry["id"])
            ids.append(entry["id"])
        self.assertEqual(len(ids), len(set(ids)))
        for entry in data["credentialed"]:
            self.assertTrue(entry.get("credentialed"))

    def test_the_dry_run_plans_every_entry_and_fetches_nothing(self):
        tool = load("fetch_sources")
        code, out, _ = run_tool(tool, ["--credentialed"])
        self.assertEqual(code, 0)
        data = json.loads((GRID / "fetch-xray.json").read_text(encoding="utf-8"))
        for entry in data["open"] + data["credentialed"]:
            self.assertIn(f"== {entry['id']} -> {entry['dest']}", out)
        self.assertIn("skip: record number needed", out)
        self.assertIn("== nih_chestxray14", out)
        self.assertIn("nihcc.box.com/shared/static/i28rlmbvmfjbl8p2n3ril0pptcmcu9d1.gz", out)
        self.assertIn("SHA-1 piece checked against https://academictorrents.com/", out)
        self.assertIn("zenodo-get --record 8115942", out)
        self.assertIn("fallback: ", out)
        self.assertIn("<login from ~/.netrc>", out)
        self.assertIn("dry run:", out)
        code, out, _ = run_tool(tool, ["--only", "cathaction,fracatlas"])
        self.assertEqual(out.count("== "), 2)
        self.assertIn("envs/acq/bin/python", out)
        code, _, err = run_tool(tool, ["--only", "mimic_cxr_jpg"])
        self.assertEqual(code, 2)
        self.assertIn("add --credentialed", err)
        code, _, err = run_tool(tool, ["--only", "nothing_of_that_name"])
        self.assertEqual(code, 2)
        self.assertIn("no entry named", err)

    def test_a_run_is_refused_on_the_login_node_and_outside_a_job(self):
        tool = load("fetch_sources")
        with mock.patch.object(tool.socket, "gethostname", return_value="warrior.grid.wayne.edu"):
            code, _, err = run_tool(tool, ["--run"])
        self.assertEqual(code, 3)
        self.assertIn("login node", err)
        env = {k: v for k, v in os.environ.items() if k != "SLURM_JOB_ID"}
        with mock.patch.object(tool.socket, "gethostname", return_value="wsu123"), mock.patch.dict(os.environ, env, clear=True):
            code, _, err = run_tool(tool, ["--run"])
        self.assertEqual(code, 3)
        self.assertIn("outside a Slurm job", err)

    def test_a_token_file_must_be_private(self):
        tool = load("fetch_sources")
        with mock.patch.dict(os.environ, {"TMPDIR": os.environ.get("TMPDIR", "/tmp")}):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "credentials.env"
                path.write_text("KAGGLE_API_TOKEN=abc\n", encoding="utf-8")
                path.chmod(0o644)
                with self.assertRaises(tool.FetchError):
                    tool.kaggle_token(path)
                path.chmod(0o600)
                self.assertEqual(tool.kaggle_token(path), "abc")
                netrc = Path(tmp) / "netrc"
                netrc.write_text("machine physionet.org login someone password hidden\n", encoding="utf-8")
                netrc.chmod(0o600)
                self.assertEqual(tool.netrc_login("physionet.org", netrc), "someone")


class BankTest(unittest.TestCase):
    def test_a_raw_folder_becomes_a_bank_and_a_rerun_writes_nothing(self):
        import tempfile
        tool = load("bank")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_raw(tmp / "raw")
            recipe = tmp / "recipe.json"
            labels = {"kind": "yolo", "labels_dir": "labels", "classes": {"0": "T12", "1": None}}
            recipe.write_text(json.dumps(recipe_of(tmp, labels)), encoding="utf-8")
            code, out, _ = run_tool(tool, ["--recipe", str(recipe)])
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out)["frames"], 3)
            self.assertFalse((tmp / "bank").exists())
            code, out, _ = run_tool(tool, ["--recipe", str(recipe), "--run"])
            self.assertEqual(code, 0, out)
            counts = json.loads(out)
            self.assertEqual((counts["written"], counts["persons"], counts["boxes"]), (3, 2, 2))
            stems = sorted(p.stem for p in (tmp / "bank" / "images" / "train").glob("*.png"))
            self.assertEqual(stems, ["images_001_images_00000001_000", "images_001_images_00000001_001",
                                     "images_001_images_00000002_000"])
            meta = json.loads((tmp / "bank" / "meta" / (stems[0] + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(meta["case"], "00000001")
            self.assertEqual([b["level"] for b in meta["boxes"]], ["T12", None])
            self.assertEqual(meta["boxes"][0]["box"], [10.0, 7.5, 30.0, 22.5])
            self.assertEqual((tmp / "bank" / "images" / "train" / (stems[0] + ".png")).read_bytes(),
                             (tmp / "raw" / "images_001" / "images" / "00000001_000.png").read_bytes())
            code, out, _ = run_tool(tool, ["--recipe", str(recipe), "--run"])
            self.assertEqual(json.loads(out)["kept"], 3)
            (tmp / "raw" / "images_001" / "images" / "00000002_000.png").write_bytes(png(40, 30, 99))
            code, _, err = run_tool(tool, ["--recipe", str(recipe), "--run"])
            self.assertEqual(code, 2)
            self.assertIn("other bytes", err)

    def test_a_recipe_still_to_confirm_or_in_dicom_stops_with_the_reason(self):
        import tempfile
        tool = load("bank")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_raw(tmp / "raw")
            recipe = recipe_of(tmp)
            recipe["view"]["lat_from_ap_deg"] = "to confirm: AP or lateral"
            path = tmp / "r.json"
            path.write_text(json.dumps(recipe), encoding="utf-8")
            code, _, err = run_tool(tool, ["--recipe", str(path)])
            self.assertEqual(code, 2)
            self.assertIn("still to confirm: view.lat_from_ap_deg", err)
            recipe = recipe_of(tmp)
            recipe["format"], recipe["images"] = "dcm", ["**/*.png"]
            path.write_text(json.dumps(recipe), encoding="utf-8")
            code, _, err = run_tool(tool, ["--recipe", str(path), "--run"])
            self.assertEqual(code, 2)
            self.assertTrue("pydicom" in err or "DICOM" in err or "pixel" in err, err)

    def test_every_shipped_recipe_is_well_formed(self):
        tool = load("bank")
        for path in sorted((GRID / "banks").glob("*.json")):
            recipe = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(recipe["id"], path.stem)
            for key in tool.REQUIRED:
                self.assertIn(key, recipe, path.name)
            self.assertEqual(recipe["split"], "train", path.name)
            self.assertTrue(recipe["bank"].startswith("/rs/rs_grp_oschome/go2432/data/" + path.stem + "/"), path.name)
            if path.stem == "pengwin_task2_xrays":
                self.assertTrue(recipe["synthetic"])


class SlurmScriptsTest(unittest.TestCase):
    def test_every_script_parses(self):
        for name in SBATCH_FILES + SCRIPTS:
            done = subprocess.run(["bash", "-n", str(GRID / name)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, f"{name}: {done.stderr}")
        # issue #77: where a job runs is hpcworker's job submit's, from the site profile, so a header
        # holds only what the job needs
        for name in SBATCH_FILES:
            text = (GRID / name).read_text(encoding="utf-8")
            for line in ("#SBATCH --cpus-per-task=8", "#SBATCH --mem=24G"):
                self.assertIn(line, text, name)
            for word in ("partition", "qos", "requeue", "gres", "output", "job-name"):
                self.assertNotIn(f"#SBATCH --{word}", text, name)

    def setUp(self):
        import tempfile
        # a home of the test's own, so the gated sources' token and link files are the test's, never the runner's
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        self.home = Path(home.name)

    def dry_run(self, script, *args, free="9000G", quota=None, used=None, volume=None, repo=ROOT, **extra):
        volume = volume or volume_in(self, quota, used)
        # df -B1 --output=avail, in bytes, as size-rule.sh asks it where the volume has no quota
        df = volume.tools / "df"
        df.write_text(f"#!/bin/bash\necho Avail\necho {int(free.rstrip('G')) * GB}\n", encoding="utf-8")
        df.chmod(0o755)
        env = dict(os.environ, SCHWINGNET=str(repo), HPCW_DRY="1", DF=str(df), HOME=str(self.home),
                   **volume.env(**extra))
        done = subprocess.run(["bash", str(repo / "grid" / script), *args], env=env, capture_output=True, text=True,
                              timeout=60)
        Path(repo / "grid" / "LAST_RUN.txt").unlink(missing_ok=True)
        return done.returncode, done.stdout + done.stderr

    def test_the_chain_submits_three_dependent_jobs_in_a_dry_run(self):
        code, out = self.dry_run("run-xray-chain.sh", "--only", "cathaction,fracatlas")
        self.assertEqual(code, 0, out)
        self.assertIn("would submit: hpcworker job submit --project schwingnet --name xr_fetch --class batch", out)
        self.assertIn("-- 01-fetch.sbatch", out)
        self.assertIn("--name xr_bank --class batch --dir " + str(ROOT / "grid") + " --after DRY_xr_fetch:any -- 02-bank-ingest.sbatch", out)
        self.assertIn("--after DRY_xr_bank:any -- 03-catalog.sbatch", out)
        self.assertIn("size budget: 2 entries, 14.2 GB stated, counted as 15 GB;", out)
        self.assertIn("no size stated for: fracatlas", out)
        self.assertIn("ETA:", out)
        code, out = self.dry_run("run-xray-chain.sh", free="10G")
        self.assertEqual(code, 3)
        self.assertIn("refusing to submit", out)
        code, out = self.dry_run("run-xray-chain.sh", "--only", "mimic_cxr_jpg")
        self.assertEqual(code, 64)
        self.assertIn("credentialed list", out)
        code, out = self.dry_run("run-xray-chain.sh", "--only", "no_such_set")
        self.assertEqual(code, 64)
        self.assertIn("nothing to submit", out)
        self.assertNotIn("would submit", out)

    def test_the_full_nlst_runs_only_when_named_on_the_owners_yes(self):
        code, out = self.dry_run("run-platform-fetch.sh")
        self.assertNotIn("idc_nlst", out)
        code, out = self.dry_run("run-platform-fetch.sh", "--gated")
        self.assertNotIn("idc_nlst: job", out)
        code, out = self.dry_run("run-platform-fetch.sh", "--only", "idc_nlst")
        self.assertEqual(code, 0, out)
        self.assertIn("idc_nlst: job DRY_dp_fetch_idc_nlst", out)
        self.assertIn("11140 GB stated", out)
        code, out = self.dry_run("run-platform-fetch.sh", "--gated-ids")
        self.assertIn("idc_nlst", out.split())

    def test_the_platform_chain_keeps_ct_rate_and_nlst_apart(self):
        code, out = self.dry_run("run-platform-fetch.sh")
        self.assertEqual(code, 0, out)
        self.assertIn("aws_stoic2021: job DRY_dp_fetch_aws_stoic2021", out)
        self.assertIn("--after DRY_dp_fetch_aws_stoic2021:any -- platform-fetch.sbatch", out)
        self.assertNotIn("ID=hf_ct_rate ROUTE=hf-token", out.split("Not submitted")[0])
        self.assertIn("ID=hf_ct_rate", out.split("Not submitted")[1])
        self.assertNotIn("idc_nlst", out)
        self.assertNotIn("rsna_rspect_pe: job", out)
        # a gated source whose token or link file is not in place is left out, the rest still go in
        code, out = self.dry_run("run-platform-fetch.sh", "--gated")
        self.assertEqual(code, 0, out)
        self.assertIn("rsna_rspect_pe: left out: there is no ~/.fluorocap/credentials.env", out)
        self.assertNotIn("rsna_rspect_pe: job", out)
        self.assertIn("aws_stoic2021: job", out)
        for path in (".fluorocap/credentials.env", ".hf/token.env", ".rsna/ratic_link", ".redivis/token.env",
                     ".zenodo/token.env"):
            secret = self.home / path
            secret.parent.mkdir(parents=True, exist_ok=True)
            secret.write_text("KEY=value\n", encoding="utf-8")
            secret.chmod(0o600)
        code, out = self.dry_run("run-platform-fetch.sh", "--gated")
        self.assertIn("rsna_rspect_pe: job", out)
        self.assertNotIn("left out", out)

    def test_the_budgets_read_the_room_under_the_quota_not_the_pool(self):
        # On CephFS df reports the whole pool, 5,881,937 GB free on 2026-10-23 under a quota of
        # 21,991 GB, so a budget read from df never refused (#160). The use is the test's own.
        pool, quota = "5881937G", 21991 * GB
        code, out = self.dry_run("run-platform-fetch.sh", "--only", "idc_nlst", free=pool, quota=quota, used=13146 * GB)
        self.assertEqual(code, 0, out)
        self.assertIn("11140 GB stated", out)
        self.assertIn("has 8845 GB free under its quota, 0 GB of it owed to 0 running fetches", out)
        self.assertIn("idc_nlst: job DRY_dp_fetch_idc_nlst", out)
        # nothing is refused at submit: each job decides by the size its source states when it starts
        code, out = self.dry_run("run-platform-fetch.sh", "--only", "idc_nlst", free=pool, quota=quota, used=19000 * GB)
        self.assertEqual(code, 0, out)
        self.assertIn("has 2991 GB free under its quota", out)
        self.assertIn("each job starts its fetch only if the exact size its source states fits the room then", out)
        self.assertIn("idc_nlst: job DRY_dp_fetch_idc_nlst", out)
        # the X-ray chain is refused at submit when its stated sizes pass the room, with no margin:
        # 14.2 GB stated, counted as 15, does not fit in 14 GB and does in 15, so the quota can be
        # filled to the GB, and a fraction is never cut off to make a chain fit
        code, out = self.dry_run("run-xray-chain.sh", "--only", "cathaction,fracatlas", free=pool, quota=quota,
                                 used=21977 * GB)
        self.assertEqual(code, 3, out)
        self.assertIn("has 14 GB free under its quota, 0 GB of it owed to 0 running fetches", out)
        self.assertIn("refusing to submit: 15 GB exceeds the room the quota has left", out)
        self.assertNotIn("would submit", out)
        code, out = self.dry_run("run-xray-chain.sh", "--only", "cathaction,fracatlas", free=pool, quota=quota,
                                 used=21976 * GB)
        self.assertEqual(code, 0, out)
        self.assertIn("would submit", out)

    def test_the_xray_chain_leaves_room_for_what_the_running_fetches_still_owe(self):
        volume = volume_in(self, quota=21991 * GB, used=21900 * GB)
        # admitted with 100 GB to land, and 20 GB of it landed since: it still owes 80 of the 91 free
        volume.admitted("hf_big", 7001, need=100 * GB, base=0, landed=20 * GB)
        volume.live(7001)
        only = ("--only", "cathaction,fracatlas")
        code, out = self.dry_run("run-xray-chain.sh", *only, volume=volume)
        self.assertEqual(code, 3, out)
        self.assertIn("has 91 GB free under its quota, 80 GB of it owed to 1 running fetch", out)
        self.assertIn("refusing to submit", out)
        # ended, it owes nothing
        volume.live()
        code, out = self.dry_run("run-xray-chain.sh", *only, volume=volume)
        self.assertEqual(code, 0, out)
        self.assertIn("0 GB of it owed to 0 running fetches", out)
        # an X-ray fetch sent before its size was kept states none, so nothing is sent beside it
        repo = repo_copy(self)
        gate_jobs(repo, (7002, "start", "xr_fetch"))
        volume.live(7002)
        code, out = self.dry_run("run-xray-chain.sh", *only, volume=volume, repo=repo)
        self.assertEqual(code, 3, out)
        self.assertIn("refusing to submit: the running fetch of xray_chain states no size", out)
        # one sent since is counted at the sizes its list stated
        (repo / "grid" / "logs" / "XRAY_SIZES.txt").write_text(f"7002 {80 * GB} 2026-10-23T09:00:00Z\n", encoding="utf-8")
        code, out = self.dry_run("run-xray-chain.sh", *only, volume=volume, repo=repo)
        self.assertEqual(code, 3, out)
        self.assertIn("80 GB of it owed to 1 running fetch", out)
        (repo / "grid" / "logs" / "XRAY_SIZES.txt").write_text(f"7002 {70 * GB} 2026-10-23T09:00:00Z\n", encoding="utf-8")
        code, out = self.dry_run("run-xray-chain.sh", *only, volume=volume, repo=repo)
        self.assertEqual(code, 0, out)
        self.assertIn("70 GB of it owed to 1 running fetch", out)
        # and where squeue does not answer, what the running fetches owe is not known
        code, out = self.dry_run("run-xray-chain.sh", *only, volume=volume, FAKE_SQUEUE_FAILS="1")
        self.assertEqual(code, 2, out)
        self.assertIn("squeue did not answer; nothing was queued", out)
        self.assertNotIn("would submit", out)
        # the platform script only reports it, since its jobs decide when they start
        code, out = self.dry_run("run-platform-fetch.sh", "--only", "aws_stoic2021", volume=volume,
                                 FAKE_SQUEUE_FAILS="1")
        self.assertEqual(code, 0, out)
        self.assertIn("what the running fetches owe not read (squeue did not answer)", out)

    def test_a_job_sent_by_the_platform_script_is_marked_queued(self):
        volume = volume_in(self, quota=21991 * GB, used=13146 * GB)
        repo = repo_copy(self)
        log = Path(volume.tools) / "submitted.log"
        env = dict(os.environ, SCHWINGNET=str(repo), HOME=str(self.home), HPCWORKER=str(ROOT / "tests" / "fakes" / "hpcworker"),
                   HPCW_LOG=str(log), **volume.env())
        env.pop("HPCW_DRY", None)
        done = subprocess.run(["bash", str(repo / "grid" / "run-platform-fetch.sh"), "--only", "aws_stoic2021,zenodo_lumos"],
                              env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("aws_stoic2021: job 101", done.stdout)
        self.assertEqual((volume.data / "aws_stoic2021" / "meta" / "QUEUED").read_text(encoding="utf-8").split()[0], "101")
        self.assertEqual((volume.data / "zenodo_lumos" / "meta" / "QUEUED").read_text(encoding="utf-8").split()[0], "102")

    def test_the_xray_chain_holds_the_size_check_until_its_sizes_are_recorded(self):
        import fcntl
        volume = volume_in(self, quota=21991 * GB, used=13146 * GB)
        repo = repo_copy(self)
        env = dict(os.environ, SCHWINGNET=str(repo), HOME=str(self.home), HPCWORKER=str(ROOT / "tests" / "fakes" / "hpcworker"),
                   HPCW_LOG=str(volume.tools / "submitted.log"), **volume.env(SIZE_RULE_WAIT="1"))
        env.pop("HPCW_DRY", None)
        sizes = repo / "grid" / "logs" / "XRAY_SIZES.txt"

        def submit():
            return subprocess.run(["bash", str(repo / "grid" / "run-xray-chain.sh"), "--only", "cathaction"],
                                  env=env, capture_output=True, text=True, timeout=60)

        # while a fetch job decides, the chain waits its turn and queues nothing when it does not come
        with open(volume.data / ".size-rule.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            done = submit()
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("refusing to submit: another fetch held the size check for 1 seconds; nothing was queued", done.stdout)
        self.assertFalse(sizes.exists())
        # its turn come, it is sent and counted at its stated sum rounded up, before the next decision
        done = submit()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        job, need = sizes.read_text(encoding="utf-8").split()[:2]
        self.assertEqual((job, need), ("101", str(15 * GB)))

    def test_a_volume_with_no_quota_is_read_with_df_and_an_unread_quota_refuses(self):
        code, out = self.dry_run("run-platform-fetch.sh", "--only", "idc_nlst", free="9000G")
        self.assertEqual(code, 0, out)
        self.assertIn("has 9000 GB free by df (no quota on it)", out)
        # a quota whose use cannot be read is never replaced by the pool's figure
        for script, only in (("run-platform-fetch.sh", "idc_nlst"), ("run-xray-chain.sh", "cathaction")):
            code, out = self.dry_run(script, "--only", only, free="5881937G", quota=21991 * GB)
            self.assertEqual(code, 2, out)
            self.assertIn("cannot read the free space", out)
            self.assertNotIn("would submit", out)

    def test_the_two_kaggle_datasets_run_only_when_named(self):
        code, out = self.dry_run("run-platform-fetch.sh", "--gated")
        self.assertNotIn("kaggle_fracture_multiregion", out)
        code, out = self.dry_run("run-platform-fetch.sh", "--gated-ids")
        self.assertIn("kaggle_fracture_multiregion", out.split())
        self.assertIn("kaggle_scoliosis_yolov5", out.split())
        secret = self.home / ".fluorocap/credentials.env"
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text("KEY=value\n", encoding="utf-8")
        secret.chmod(0o600)
        code, out = self.dry_run("run-platform-fetch.sh", "--only", "kaggle_scoliosis_yolov5")
        self.assertEqual(code, 0, out)
        self.assertIn("kaggle_scoliosis_yolov5: job DRY_dp_fetch_kaggle_scoliosis_yolov5", out)
        self.assertIn("kaggle-dataset", out)


if __name__ == "__main__":
    unittest.main()


class FigshareRouteTest(unittest.TestCase):
    """The figshare route, written for Aariz and KUB-StoneX (#40): the article's public API
    lists each file with its download URL, size and md5, which http-get verifies; the run can be
    sent to another data root and allowed outside a Slurm job; a zip that came is unpacked."""

    ARTICLE = {
        "id": 27986417, "is_embargoed": False, "download_disabled": False,
        "license": {"name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
        "files": [
            {"name": "Aariz.zip", "size": 2098209792, "computed_md5": "e0bd645bca6759abdae4f199d841bda6",
             "download_url": "https://ndownloader.figshare.com/files/51041642", "is_link_only": False},
            {"name": "readme.txt", "size": 12, "computed_md5": None,
             "download_url": "https://ndownloader.figshare.com/files/1", "is_link_only": False},
            {"name": "elsewhere", "download_url": "https://example.org/x", "is_link_only": True},
        ],
    }

    def opener(self, article):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return lambda url, timeout=0: Response(json.dumps(article).encode("utf-8"))

    def test_the_two_entries_are_listed_and_planned_through_the_api(self):
        data = json.loads((GRID / "fetch-xray.json").read_text(encoding="utf-8"))
        entries = {e["id"]: e for e in data["open"]}
        for name, article in (("aariz", 27986417), ("kub_stonex", 32049369)):
            self.assertEqual(entries[name]["route"], "figshare")
            self.assertEqual(entries[name]["api"], f"https://api.figshare.com/v2/articles/{article}")
            self.assertTrue(entries[name]["unpack"])
            self.assertIn("CC BY 4.0", entries[name]["licence"])
        tool = load("fetch_sources")
        code, out, _ = run_tool(tool, ["--only", "aariz,kub_stonex"])
        self.assertEqual(code, 0)
        self.assertIn("figshare: list https://api.figshare.com/v2/articles/27986417", out)
        self.assertIn("and unpack each zip there", out)
        self.assertIn("size: 20.8 GB", out)

    def test_the_api_listing_becomes_http_get_commands_with_md5_and_size(self):
        tool = load("fetch_sources")
        files = tool.figshare_files("https://api.figshare.com/v2/articles/27986417", self.opener(self.ARTICLE))
        self.assertEqual([f["name"] for f in files], ["Aariz.zip", "readme.txt"])
        entry = {"id": "aariz", "dest": "/data/aariz/raw", "route": "figshare", "api": "x"}
        command = tool.http_command("py", "helper.py", files[0]["url"], "/data/aariz/raw/Aariz.zip", entry,
                                   {"md5": files[0]["md5"]}, files[0]["size"])
        self.assertEqual(command[2:], ["http-get", "--url", "https://ndownloader.figshare.com/files/51041642",
                                       "--dest", "/data/aariz/raw/Aariz.zip", "--state", "/data/aariz/fetch-state",
                                       "--md5", "e0bd645bca6759abdae4f199d841bda6", "--bytes", "2098209792"])
        command = tool.http_command("py", "helper.py", files[1]["url"], "/data/aariz/raw/readme.txt", entry,
                                   {"md5": files[1]["md5"]}, files[1]["size"])
        self.assertNotIn("--md5", command)
        self.assertIn("--bytes", command)
        with self.assertRaises(tool.FetchError):
            tool.figshare_files("x", self.opener(dict(self.ARTICLE, is_embargoed=True)))
        with self.assertRaises(tool.FetchError):
            tool.figshare_files("x", self.opener(dict(self.ARTICLE, files=[])))

        def refused(url, timeout=0):
            raise tool.urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

        with self.assertRaises(tool.FetchError) as caught:
            tool.figshare_files("https://api.figshare.com/v2/articles/1", refused)
        self.assertIn("api.figshare.com", str(caught.exception))
        self.assertIn("403", str(caught.exception))

    def test_another_data_root_and_a_run_outside_slurm(self):
        tool = load("fetch_sources")
        code, out, _ = run_tool(tool, ["--only", "aariz,fracatlas", "--data-root", "/scratch/xr"])
        self.assertEqual(code, 0, out)
        self.assertIn("== aariz -> /scratch/xr/aariz/raw", out)
        self.assertIn("--dest /scratch/xr/fracatlas/raw --state /scratch/xr/fracatlas/fetch-state", out)
        self.assertNotIn("/rs/rs_grp_oschome/go2432/data/fracatlas", out)
        with self.assertRaises(tool.FetchError):
            tool.relocate([{"id": "x", "dest": "/elsewhere/x/raw"}], "/rs/data", "/scratch")
        self.assertIsNone(tool.refuse_unless_job(outside_slurm=True))
        env = {k: v for k, v in os.environ.items() if k != "SLURM_JOB_ID"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIn("outside a Slurm job", tool.refuse_unless_job())
        with mock.patch.object(tool.socket, "gethostname", return_value="warrior.grid.wayne.edu"):
            self.assertIn("login node", tool.refuse_unless_job(outside_slurm=True))
        settings = mock.Mock(outside_slurm=True, netrc="~/.netrc")
        plan = {"commands": [["py", "r.py", "zenodo-get", "--record", "1"], ["kaggle", "datasets", "download"]]}
        commands, _ = tool.expand_plan({"id": "x", "dest": "/d/x/raw"}, plan, "py", "r.py", settings)
        self.assertEqual(commands[0][-1], "--outside-slurm")
        self.assertNotIn("--outside-slurm", commands[1])
        self.assertEqual(tool.reacquire_path({"reacquire": "/no/such/reacquire.py"}, None), tool.REACQUIRE_COPY)
        self.assertTrue(tool.REACQUIRE_COPY.is_file())

    def test_a_zip_that_came_is_unpacked_once_and_never_outside_the_raw_folder(self):
        import tempfile
        import zipfile
        tool = load("fetch_sources")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            with zipfile.ZipFile(raw / "Set.zip", "w") as archive:
                archive.writestr("Set/Images/a.png", png(8, 8, 1))
                archive.writestr("Set/Images/b.png", png(8, 8, 2))
                archive.writestr("Set/empty/", b"")
            self.assertEqual(tool.unpack_archives(raw), ["Set/Images/a.png", "Set/Images/b.png"])
            self.assertEqual((raw / "Set" / "Images" / "a.png").read_bytes(), png(8, 8, 1))
            self.assertTrue((raw / "Set.zip").is_file())
            self.assertEqual(tool.unpack_archives(raw), [])
            with zipfile.ZipFile(raw / "Bad.zip", "w") as archive:
                archive.writestr("../outside.png", png(8, 8, 3))
            with self.assertRaises(tool.FetchError):
                tool.unpack_archives(raw)
            self.assertFalse((Path(tmp) / "outside.png").exists())
            records, total = tool.file_records(raw)
            self.assertEqual(len(records), 4)

    def test_every_stage_script_takes_a_data_root(self):
        for name in ("01-fetch.sbatch", "02-bank-ingest.sbatch", "03-catalog.sbatch"):
            text = (GRID / name).read_text(encoding="utf-8")
            self.assertIn("DATA_ROOT", text, name)
            self.assertIn("_tmp", text, name)
        self.assertIn("--supersedes latest", (GRID / "02-bank-ingest.sbatch").read_text(encoding="utf-8"))
        self.assertIn("--drop-superseded", (GRID / "03-catalog.sbatch").read_text(encoding="utf-8"))
        self.assertIn('BANKS=${BANKS:-$REPO/grid/banks}', (GRID / "02-bank-ingest.sbatch").read_text(encoding="utf-8"))


def bencode(value):
    if isinstance(value, int):
        return b"i%de" % value
    if isinstance(value, bytes):
        return b"%d:%s" % (len(value), value)
    if isinstance(value, str):
        return bencode(value.encode("utf-8"))
    if isinstance(value, list):
        return b"l" + b"".join(bencode(v) for v in value) + b"e"
    return b"d" + b"".join(bencode(k) + bencode(value[k]) for k in sorted(value)) + b"e"


def torrent_of(files, piece_length=16):
    """A multi-file .torrent of (name, bytes) pairs in order, as Academic Torrents serves one."""
    joined = b"".join(data for _, data in files)
    pieces = b"".join(hashlib.sha1(joined[i:i + piece_length]).digest() for i in range(0, len(joined), piece_length))
    info = {"name": "ChestXray-NIHCC", "piece length": piece_length, "pieces": pieces,
            "files": [{"length": len(data), "path": [name]} for name, data in files]}
    return bencode({"announce": "http://tracker.invalid/", "info": info})


class NextcloudRouteTest(unittest.TestCase):
    """The nextcloud route, written for PadChest's B2DROP share (2026-10-22): the public share is
    listed by WebDAV with its token as the user, folders walked, and each file fetched through the
    share's own download link with the size WebDAV states; no log carries the share's link."""

    SHARE = "https://b2drop.example.org/nextcloud/s/SHARE-Token_1"

    @staticmethod
    def folder(base, entries):
        rows = [f"<d:response><d:href>{base}/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/>"
                "</d:resourcetype></d:prop></d:propstat></d:response>"]
        for name, size in entries:
            kind = "<d:collection/>" if size is None else ""
            length = "" if size is None else f"<d:getcontentlength>{size}</d:getcontentlength>"
            rows.append(f"<d:response><d:href>{base}/{name}{'/' if size is None else ''}</d:href><d:propstat><d:prop>"
                        f"<d:resourcetype>{kind}</d:resourcetype>{length}</d:prop></d:propstat></d:response>")
        return ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">' + "".join(rows) + "</d:multistatus>").encode()

    def opener(self, asked):
        answers = {
            "/nextcloud/public.php/webdav/": self.folder("/nextcloud/public.php/webdav", [("Images", None), ("PADCHEST%20labels.csv", 12)]),
            "/nextcloud/public.php/webdav/Images": self.folder("/nextcloud/public.php/webdav/Images", [("0.zip", 2000), ("1.zip", 3000)]),
        }

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def answer(request, timeout=0):
            asked.append((request.get_method(), request.full_url, request.headers))
            path = request.full_url.split("b2drop.example.org", 1)[1]
            return Response(answers[path])

        return answer

    def test_the_share_is_walked_and_each_file_has_its_download_link_and_size(self):
        tool = load("fetch_sources")
        asked = []
        files = tool.nextcloud_files(self.SHARE, self.opener(asked))
        self.assertEqual([(f["name"], f["size"]) for f in files],
                         [("PADCHEST labels.csv", 12), ("Images/0.zip", 2000), ("Images/1.zip", 3000)])
        self.assertEqual(files[1]["url"], "https://b2drop.example.org/nextcloud/s/SHARE-Token_1/download?path=%2FImages&files=0.zip")
        self.assertEqual(files[0]["url"], "https://b2drop.example.org/nextcloud/s/SHARE-Token_1/download?path=%2F&files=PADCHEST+labels.csv")
        method, _, headers = asked[0]
        self.assertEqual(method, "PROPFIND")
        self.assertEqual(headers["Depth"], "1")
        self.assertEqual(headers["Authorization"], "Basic U0hBUkUtVG9rZW5fMTo=")
        entry = {"id": "padchest", "dest": "/data/padchest/raw", "route": "nextcloud", "share": self.SHARE}
        command = tool.http_command("py", "helper.py", files[1]["url"], "/data/padchest/raw/Images/0.zip", entry, None,
                                    files[1]["size"])
        self.assertEqual(command[-2:], ["--bytes", "2000"])
        self.assertNotIn("--md5", command)

    def test_a_link_that_is_no_share_and_an_empty_share_fail_by_name(self):
        tool = load("fetch_sources")
        with self.assertRaises(tool.FetchError):
            tool.nextcloud_files("https://b2drop.example.org/nextcloud/index.php/apps/files")
        empty_cm = lambda request, timeout=0: type("R", (io.BytesIO,), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})(self.folder("/nextcloud/public.php/webdav", []))
        with self.assertRaises(tool.FetchError):
            tool.nextcloud_files(self.SHARE, empty_cm)

    def test_a_share_behind_index_php_lists_at_the_root_and_downloads_behind_index_php(self):
        tool = load("fetch_sources")
        root, pages, token = tool.nextcloud_share("https://b2drop.example.org/index.php/s/COVID-Share_1")
        self.assertEqual((root, pages, token), ("https://b2drop.example.org", "https://b2drop.example.org/index.php", "COVID-Share_1"))
        asked = []
        listing = self.folder("/public.php/webdav", [("part1.tgz", 10)])

        def answer(request, timeout=0):
            asked.append(request.full_url)
            return type("R", (io.BytesIO,), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})(listing)

        files = tool.nextcloud_files("https://b2drop.example.org/index.php/s/COVID-Share_1", answer)
        self.assertEqual(asked, ["https://b2drop.example.org/public.php/webdav/"])
        self.assertEqual(files[0]["url"], "https://b2drop.example.org/index.php/s/COVID-Share_1/download?path=%2F&files=part1.tgz")

    def test_padchest_is_listed_through_its_share_and_the_dry_run_never_prints_the_link(self):
        data = json.loads((GRID / "fetch-xray.json").read_text(encoding="utf-8"))
        entry = {e["id"]: e for e in data["open"]}["padchest"]
        self.assertEqual(entry["route"], "nextcloud")
        self.assertTrue(entry["share"].startswith("https://b2drop.bsc.es/nextcloud/s/"))
        tool = load("fetch_sources")
        code, out, _ = run_tool(tool, ["--only", "padchest"])
        self.assertEqual(code, 0, out)
        self.assertIn("nextcloud: list the entry's share by WebDAV", out)
        self.assertNotIn("b2drop", out)


class TorrentAndTarTest(unittest.TestCase):
    """NIH ChestX-ray14's bytes are checked against the Academic Torrents release (#44), since its
    Box page publishes no checksum, and its .tar.gz archives are opened in place for the bank."""

    files = [("README_ChestXray.pdf", b"readme" * 7), ("images_001.tar.gz", bytes(range(200)) * 3),
             ("images_002.tar.gz", b"second archive" * 9)]

    def write(self, dest, names):
        dest.mkdir(parents=True, exist_ok=True)
        for name, data in self.files:
            if name in names:
                (dest / name).write_bytes(data)

    def test_present_files_pass_and_partial_pieces_are_left_out(self):
        import tempfile
        tool = load("fetch_sources")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "raw"
            self.write(dest, {"images_001.tar.gz", "images_002.tar.gz"})
            counts = tool.verify_torrent(dest, torrent_of(self.files), ["images_001.tar.gz", "images_002.tar.gz"])
            self.assertEqual(counts["files_matched"], 2)
            with self.assertRaisesRegex(tool.FetchError, "images_013.tar.gz: not checked"):
                tool.verify_torrent(dest, torrent_of(self.files), ["images_001.tar.gz", "images_013.tar.gz"])
            self.assertGreater(counts["pieces_checked"], 40)
            self.assertLess(counts["pieces_checked"], counts["pieces_in_torrent"])

    def test_a_wrong_length_or_a_changed_byte_fails_by_name(self):
        import tempfile
        tool = load("fetch_sources")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "raw"
            self.write(dest, {"images_001.tar.gz"})
            (dest / "images_002.tar.gz").write_bytes(b"<html>an error page</html>")
            with self.assertRaisesRegex(tool.FetchError, "images_002.tar.gz: 26 bytes"):
                tool.verify_torrent(dest, torrent_of(self.files))
            (dest / "images_002.tar.gz").unlink()
            data = bytearray(self.files[1][1])
            data[300] ^= 1
            (dest / "images_001.tar.gz").write_bytes(bytes(data))
            with self.assertRaisesRegex(tool.FetchError, "does not match its SHA-1"):
                tool.verify_torrent(dest, torrent_of(self.files))

    def test_nothing_checked_is_a_failure(self):
        import tempfile
        tool = load("fetch_sources")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "raw"
            dest.mkdir()
            with self.assertRaisesRegex(tool.FetchError, "nothing was verified"):
                tool.verify_torrent(dest, torrent_of(self.files))

    def test_the_torrent_is_used_only_under_the_infohash_its_address_names(self):
        import io
        import tempfile
        tool = load("fetch_sources")
        torrent = torrent_of(self.files)
        info = torrent[torrent.index(b"4:info") + 6:-1]
        good = hashlib.sha1(info).hexdigest()

        def opener(body):
            return lambda url, timeout: io.BytesIO(body)

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "release.torrent").write_bytes(b"<html>an error page</html>")
            url = f"https://academictorrents.com/download/{good}.torrent"
            self.assertEqual(tool.fetch_torrent(url, state, opener(torrent)), torrent)
            self.assertEqual((state / "release.torrent").read_bytes(), torrent)
            other = f"https://academictorrents.com/download/{'0' * 40}.torrent"
            fresh = Path(tmp) / "fresh"
            fresh.mkdir()
            with self.assertRaisesRegex(tool.FetchError, "its infohash is"):
                tool.fetch_torrent(other, fresh, opener(torrent))
            self.assertFalse((fresh / "release.torrent").exists())

    def test_a_tar_gz_is_unpacked_once_and_never_outside_the_raw_folder(self):
        import io
        import tarfile
        import tempfile
        tool = load("fetch_sources")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()

            def archive(path, members):
                with tarfile.open(path, "w:gz") as opened:
                    for name, data in members:
                        info = tarfile.TarInfo(name)
                        info.size = len(data)
                        opened.addfile(info, io.BytesIO(data))

            archive(raw / "images_001.tar.gz", [("images/00000001_000.png", png(8, 8, 1)),
                                                ("images/00000002_000.png", png(8, 8, 2))])
            self.assertEqual(sorted(tool.unpack_archives(raw)),
                             ["images/00000001_000.png", "images/00000002_000.png"])
            self.assertEqual(tool.unpack_archives(raw), [])
            archive(raw / "images_002.tar.gz", [("../escape.png", png(8, 8, 3))])
            with self.assertRaisesRegex(tool.FetchError, "outside"):
                tool.unpack_archives(raw)

    def test_the_nih_entry_fetches_twelve_archives_and_names_the_torrent(self):
        data = json.loads((GRID / "fetch-xray.json").read_text(encoding="utf-8"))
        entry = next(e for e in data["open"] if e["id"] == "nih_chestxray14")
        self.assertEqual(entry["route"], "http")
        self.assertEqual(len(entry["urls"]), 12)
        self.assertEqual(len(set(entry["urls"])), 12)
        self.assertEqual(entry["names"][0], "images_001.tar.gz")
        self.assertTrue(entry["unpack"])
        self.assertIn("557481faacd824c83fbf57dcf7b6da9383b3235a", entry["torrent"])


# Stands in for the acq environment's python: it prints each argument it was given and, run as
# reacquire.py hf-get, writes hf-get's summary with FAKE_FILES files verified.
FAKE_PYTHON = """#!/bin/bash
state=""
while [ $# -gt 0 ]; do
  case "$1" in --state) state=$2; shift 2 ;; *) printf 'arg: %s\\n' "$1"; shift ;; esac
done
[ -n "$state" ] || exit 0
mkdir -p "$state"
verified=false; [ "${FAKE_FILES:-0}" -gt 0 ] && verified=true
printf '{\\n "repo": "a/b",\\n "files": %s,\\n "failed": 0,\\n "all_verified": %s\\n}' "${FAKE_FILES:-0}" "$verified" > "$state/hf_a_b.json"
echo "hf a/b@0123: ${FAKE_FILES:-0} files, 0 failed"
"""

# Stands in for spinesurg-ct-nnunet's slurm/acquisition_fetch.sh: what it was asked, and its floor.
FAKE_ACQUISITION_FETCH = """#!/bin/bash
echo "acquisition_fetch: FLOOR_TB=${FLOOR_TB:-unset} $*"
"""


def run_fetch_job(tmp, volume, route, args, source="hf_example", **extra):
    """grid/platform-fetch.sbatch run as job 900 on the volume, with stand-ins for the acq
    environment's python and spinesurg-ct-nnunet's fetcher."""
    acq = tmp / "acq" / "bin"
    acq.mkdir(parents=True, exist_ok=True)
    (acq / "python").write_text(FAKE_PYTHON, encoding="utf-8")
    (acq / "python").chmod(0o755)
    slurm = tmp / "ssn" / "slurm"
    slurm.mkdir(parents=True, exist_ok=True)
    (slurm / "acquisition_fetch.sh").write_text(FAKE_ACQUISITION_FETCH, encoding="utf-8")
    token = tmp / "token.env"
    token.write_text("HF_TOKEN=not-a-token\n", encoding="utf-8")
    token.chmod(0o600)
    work = tmp / "work"
    work.mkdir(exist_ok=True)
    # a file the pattern would name, were this shell to expand it
    (work / "0043_new_ct_tri-here").write_text("", encoding="utf-8")
    env = dict(os.environ, ID=source, ROUTE=route, ARGS=args, TOKEN_FILE=str(token), ACQ_ENV=str(tmp / "acq"),
               SSN=str(tmp / "ssn"), TMPDIR_OVERRIDE=str(tmp / "tmp"), SCHWINGNET=str(ROOT), SLURM_JOB_ID="900",
               **volume.env(**extra))
    done = subprocess.run(["bash", str(GRID / "platform-fetch.sbatch")], cwd=work, env=env,
                          capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


HF_ARGS = "--repo a/b --include *0043_new_ct_tri*"


class HuggingFaceRouteTest(unittest.TestCase):
    """The hf-token route of grid/platform-fetch.sbatch (#158). reacquire.py hf-get reads --include
    as a glob, as fnmatch and huggingface_hub's allow_patterns do, never as the regular expression
    the acq and zenodo routes take, and it ends 0 having verified no file when the glob matches
    none: FluoroSeg, ReXGradient-160K and CADS each ended so on 2026-10-23, COMPLETED with nothing
    fetched. The job now fails by name on such a run, and the glob reaches hf-get as written."""

    @staticmethod
    def hf_token_args():
        text = (GRID / "run-platform-fetch.sh").read_text(encoding="utf-8")
        rows = (line.split("|") for line in text.splitlines())
        return {row[0]: row[5].split() for row in rows if len(row) > 5 and row[1] == "hf-token"}

    def test_no_hf_token_line_gives_hf_get_a_pattern_that_matches_nothing(self):
        lines = self.hf_token_args()
        self.assertLessEqual({"hf_cads_unique", "hf_rexgradient_160k", "hf_fluoroseg", "hf_ct_rate"}, set(lines))
        for source, args in lines.items():
            if "--include" in args:
                self.assertNotEqual(args[args.index("--include") + 1], ".", source)
        # the owner chose these whole, which is no --include at all
        for whole in ("hf_rexgradient_160k", "hf_fluoroseg", "hf_ct_rate"):
            self.assertNotIn("--include", lines[whole], whole)
        cads = lines["hf_cads_unique"]
        pattern = cads[cads.index("--include") + 1]
        # CT-TRI's folder in the Hugging Face tree of 2026-09-23 (data/reproduce/sources.json)
        self.assertTrue(fnmatch.fnmatch("0043_new_ct_tri/images/s0001.nii.gz", pattern))
        self.assertFalse(fnmatch.fnmatch("0001_visceral_gc/images/s0001.nii.gz", pattern))

    def run_job(self, files, **extra):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        volume = Volume(tmp.name, quota=21991 * GB, used=13146 * GB)
        extra.setdefault("FAKE_SIZE", f"{50 * GB} {50 * GB} 3 files listed by the hub")
        return run_fetch_job(Path(tmp.name), volume, "hf-token", HF_ARGS, FAKE_FILES=str(files), **extra)

    def test_a_fetch_that_verified_no_file_fails_by_name_and_status_shows_why(self):
        code, out = self.run_job(files=0)
        self.assertEqual(code, 3, out)
        self.assertIn("arg: *0043_new_ct_tri*", out)
        self.assertIn("DP_FETCH_RC=3", out)
        self.assertIn("hf_example: nothing fetched; the include pattern matched no file at ", shown(out))

    def test_a_fetch_that_verified_files_passes_and_its_glob_reaches_the_size_reader_as_written(self):
        code, out = self.run_job(files=2)
        self.assertEqual(code, 0, out)
        self.assertIn("arg: *0043_new_ct_tri*", out)
        self.assertIn("sizer: hf --repo a/b --include *0043_new_ct_tri* --dest ", out)
        self.assertIn("DP_FETCH_RC=0", out)
        self.assertNotIn("nothing fetched", out)


class SizeRuleTest(unittest.TestCase):
    """The owner's size rule of 2026-10-23 (#160): "make sure any datasets that are selected for
    storage know exactly how much space they will require and block those which would cause
    overflow, all or nothing datasets". A fetch reads its exact size from its source before a byte
    comes and starts only when what it still has to land fits in the room under the volume's quota
    left after what every admitted fetch still running has yet to land; there is no floor and no
    margin, and no fetch is stopped part-way."""

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        # The quota of 2026-10-23, 21,991 GB, with a use of the test's own: 13,146 GB leaves 8,845
        self.volume = Volume(self.tmp, quota=21991 * GB, used=13146 * GB)

    def fetch(self, need_gb, route="hf-token", args=HF_ARGS, **extra):
        extra.setdefault("FAKE_SIZE", f"{need_gb * GB} {need_gb * GB} 3 files listed by the hub")
        return run_fetch_job(self.tmp, self.volume, route, args, FAKE_FILES="2", **extra)

    def rule(self, call, repo=ROOT, **extra):
        """One function of grid/size-rule.sh, called in bash with the volume's stand-ins."""
        env = dict(os.environ, REPO=str(repo), DATA=str(self.volume.data), **self.volume.env(**extra))
        done = subprocess.run(["bash", "-c", f'. "{repo}/grid/size-rule.sh"; {call}'], env=env,
                              capture_output=True, text=True, timeout=60)
        return done.returncode, done.stdout.strip()

    def test_a_fetch_that_fits_is_admitted_and_its_admission_recorded(self):
        code, out = self.fetch(2650)
        self.assertEqual(code, 0, out)
        self.assertIn("hf_example: admitted; it needs 2650 gb of its 2650 gb by 3 files listed by the hub and 8845 gb "
                      "is free under the quota after 0 gb owed to 0 running fetches at ", shown(out))
        self.assertIn("arg: *0043_new_ct_tri*", out)
        state, job, need, base = (self.volume.data / "hf_example" / "meta" / "SIZE").read_text(encoding="utf-8").split()[:4]
        self.assertEqual((state, job, need, base), ("admitted", "900", str(2650 * GB), "0"))

    def test_a_fetch_that_would_overflow_lands_nothing_and_status_shows_why(self):
        code, out = self.fetch(8846)
        self.assertEqual(code, 4, out)
        self.assertNotIn("arg:", out)
        self.assertIn("DP_FETCH_RC=4", out)
        self.assertIn("hf_example: refused for space; it needs 8846 gb of its 8846 gb by 3 files listed by the hub and "
                      "only 8845 gb is free under the quota after 0 gb owed to 0 running fetches at ", shown(out))
        meta = self.volume.data / "hf_example" / "meta"
        self.assertFalse((meta / "SIZE").exists())
        self.assertEqual((meta / "REFUSED").read_text(encoding="utf-8").split()[:3], ["900", str(8846 * GB), str(8845 * GB)])
        # the quota is filled to the byte: exactly the room is admitted
        code, out = self.fetch(8845)
        self.assertEqual(code, 0, out)

    def test_what_running_fetches_still_owe_is_kept_for_them(self):
        # admitted with 3,000 GB to land when its landing held 1,000 GB, and grown by 500 since:
        # it still owes 2,500 GB; a fetch admitted but no longer running owes nothing
        self.volume.admitted("hf_other", 777, need=3000 * GB, base=1000 * GB, landed=1500 * GB)
        self.volume.admitted("hf_ended", 555, need=9000 * GB)
        self.volume.live(777, 900)
        code, out = self.fetch(6346)
        self.assertEqual(code, 4, out)
        self.assertIn("only 6345 gb is free under the quota after 2500 gb owed to 1 running fetch at ", shown(out))
        code, out = self.fetch(6345)
        self.assertEqual(code, 0, out)
        self.assertIn("6345 gb is free under the quota after 2500 gb owed to 1 running fetch at ", shown(out))

    def test_a_requeued_job_keeps_its_admission_and_another_job_decides_anew(self):
        # job 900 was admitted to land 5,000 GB into an empty landing, landed 3,000 and was
        # preempted. Requeued under its own id, it goes on under its admission without asking its
        # source again; deciding anew would count the 3,000 twice and could leave them stranded.
        self.volume.admitted("hf_example", 900, need=5000 * GB, base=0, landed=3000 * GB)
        self.volume.live(900)
        code, out = self.fetch(9000, SLURM_RESTART_COUNT="1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("sizer:", out)
        self.assertIn("arg: *0043_new_ct_tri*", out)
        self.assertIn("hf_example: admitted already; job 900 restarted and keeps the room it was given at ", shown(out))
        # a job that has not been restarted decides, even under an id an old admission names, as
        # one Slurm hands out again once its counter wraps
        code, out = self.fetch(9000)
        self.assertEqual(code, 4, out)
        self.assertIn("sizer:", out)
        # the admission another job holds is no admission of this one's: it decides by the room left
        # after the 2,000 GB that job still owes
        self.volume.admitted("hf_example", 777, need=5000 * GB, base=0, landed=3000 * GB)
        self.volume.live(777, 900)
        code, out = self.fetch(6846, SLURM_RESTART_COUNT="1")
        self.assertEqual(code, 4, out)
        self.assertIn("only 6845 gb is free under the quota after 2000 gb owed to 1 running fetch at ", shown(out))
        self.assertEqual((self.volume.data / "hf_example" / "meta" / "SIZE").read_text(encoding="utf-8").split()[1], "777")

    def test_a_landing_whose_bytes_cannot_be_read_is_refused(self):
        # the growth of a landing is measured from what it held when its fetch was admitted, so an
        # unread start would count every byte already there as the fetch's own
        self.volume.attribute(self.volume.data / "hf_example", "ceph.dir.rbytes", "")
        code, out = self.fetch(1)
        self.assertEqual(code, 4, out)
        self.assertNotIn("arg:", out)
        self.assertIn("hf_example: refused; what its landing holds could not be read at ", shown(out))
        self.assertFalse((self.volume.data / "hf_example" / "meta" / "SIZE").exists())

    def test_a_volume_no_reader_can_read_or_on_a_fuse_mount_is_never_read_with_df(self):
        # df gives the whole Ceph pool on the lab volume; it answers only for a mount that names a
        # kind other than CephFS, and never in the place of attributes no reader could read
        tools = self.volume.tools
        (tools / "df").write_text(f"#!/bin/bash\necho Avail\necho {5881937 * GB}\n", encoding="utf-8")
        (tools / "df").chmod(0o755)
        bare = self.tmp / "bare"
        bare.mkdir()
        missing = str(self.tmp / "no-such-tool")
        tools_for = dict(GETFATTR=missing, DF=str(tools / "df"), STAT=str(tools / "stat"))
        call = f'volume_free_bytes "{bare}"'
        for kind, said in (("ext2/ext3", (0, f"{5881937 * GB} df")), ("xfs", (0, f"{5881937 * GB} df")),
                           ("ceph", (1, "")), ("fuseblk", (1, "")), ("fuse", (1, "")), ("", (1, ""))):
            (tools / "stat").write_text(f"#!/bin/bash\necho '{kind}'\n", encoding="utf-8")
            (tools / "stat").chmod(0o755)
            # with no getfattr, Python reads the attributes, and a folder with none is read by df
            self.assertEqual(self.rule(call, XATTR_PYTHON=sys.executable, **tools_for), said, kind)
            # with no Python that runs either, nothing is read and nothing is asked of df
            self.assertEqual(self.rule(call, XATTR_PYTHON=missing, **tools_for), (1, ""), kind)

    def test_a_refusal_never_overwrites_an_admission_that_still_runs(self):
        self.volume.admitted("hf_example", 777, need=8000 * GB)
        self.volume.live(777, 900)
        code, out = self.fetch(1000)
        self.assertEqual(code, 4, out)
        self.assertEqual((self.volume.data / "hf_example" / "meta" / "SIZE").read_text(encoding="utf-8").split()[1], "777")

    def test_a_source_whose_size_is_not_known_exactly_is_refused(self):
        code, out = self.fetch(0, FAKE_SIZE="no exact size; no file of the repository matches the include pattern",
                               FAKE_SIZE_RC="3")
        self.assertEqual(code, 4, out)
        self.assertNotIn("arg:", out)
        self.assertIn("hf_example: refused; no exact size; no file of the repository matches the include pattern at ",
                      shown(out))
        for said, rc in (("", "0"), ("the source did not answer; http 503", "2"), ("12 twelve", "0")):
            code, out = self.fetch(0, FAKE_SIZE=said, FAKE_SIZE_RC=rc)
            self.assertEqual(code, 4, out)
            self.assertNotIn("arg:", out)

    def test_nothing_is_admitted_while_what_the_running_fetches_owe_is_unknown(self):
        code, out = self.fetch(1, FAKE_SQUEUE_FAILS="1")
        self.assertEqual(code, 4, out)
        self.assertIn("hf_example: refused; the queue of slurm could not be read so what the running fetches owe is "
                      "not known at ", shown(out))
        self.volume.meta("hf_other", "SIZE", "admitted 777 unknown 0 2026-10-23T12:00:00Z unknown")
        self.volume.live(777)
        code, out = self.fetch(1)
        self.assertEqual(code, 4, out)
        # status keeps a line of plain words alone, so the id's underscores read as spaces
        self.assertIn("hf_example: refused; the running fetch of hf other states no size so nothing is admitted beside "
                      "it at ", shown(out))

    def test_a_fetch_waits_its_turn_for_the_size_check(self):
        import fcntl
        with open(self.volume.data / ".size-rule.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            code, out = self.fetch(1, SIZE_RULE_WAIT="1")
        self.assertEqual(code, 4, out)
        self.assertIn("hf_example: refused; another fetch held the size check for 1 seconds at ", shown(out))

    def test_every_route_that_downloads_asks_the_rule_first(self):
        # acquisition_fetch.sh's own floor would stop a fetch part-way; the rule runs it with none
        code, out = self.fetch(10, route="acq", args="zenodo --collection zenodo_lumos --record 18173664 --include .",
                               source="zenodo_lumos")
        self.assertEqual(code, 0, out)
        self.assertIn(f"sizer: acq zenodo --collection zenodo_lumos --record 18173664 --include . --data-root {self.volume.data}", out)
        self.assertIn("acquisition_fetch: FLOOR_TB=0 zenodo --collection zenodo_lumos", out)
        code, out = self.fetch(9000, route="acq", args="zenodo --collection zenodo_lumos --record 18173664 --include .",
                               source="zenodo_lumos")
        self.assertEqual(code, 4, out)
        self.assertNotIn("acquisition_fetch:", out)
        # routes with no size reader yet are refused, so no dataset lands without its size known
        for route in ("gdown", "kaggle", "kaggle-dataset", "redivis"):
            # an id as the data platform writes one, and the route's name in the plain words status keeps
            source, words = "x_" + route.replace("-", "_"), route.replace("-", " ")
            code, out = self.fetch(1, route=route, args="anything", source=source)
            self.assertEqual(code, 4, f"{route}: {out}")
            self.assertIn(f"{source}: refused; no exact size; the {words} route has no size reader yet at ", shown(out))

    def test_the_rule_counts_the_fetches_the_gate_sent_before_it(self):
        repo = repo_copy(self)
        # the full NLST, sent before the rule, counted at its line's 11,139.6 GB less what landed
        gate_jobs(repo, (40711959, "fetch:idc_nlst", "dp_idc_nlst"))
        self.volume.attribute(self.volume.data / "idc_nlst", "ceph.dir.rbytes", 1000 * GB)
        (self.volume.data / "idc_nlst").mkdir()
        self.volume.live(40711959)
        self.assertEqual(self.rule('owed_by_running ""', repo=repo), (0, f"{10139600 * 10**6} 1"))
        # sent under the rule and not started, it decides for itself when it starts
        self.volume.meta("idc_nlst", "QUEUED", "40711959 2026-10-23T12:00:00Z")
        self.assertEqual(self.rule('owed_by_running ""', repo=repo), (0, "0 0"))
        # a line that states no size cannot be counted, nor an X-ray fetch sent before its size was kept
        gate_jobs(repo, (41, "fetch:rsna_ratic_abdominal_trauma", "dp_rsna_ratic_abdominal_trauma"), (42, "start", "xr_fetch"))
        self.volume.live(40711959, 41, 42)
        self.assertEqual(self.rule('owed_by_running ""', repo=repo), (0, "0 0 rsna_ratic_abdominal_trauma xray_chain"))
        # an X-ray fetch is counted whole at the sizes its list stated when it was sent
        (repo / "grid" / "logs" / "XRAY_SIZES.txt").write_text(f"42 {1534 * GB} 2026-10-23T09:00:00Z\n", encoding="utf-8")
        self.volume.live(42)
        self.assertEqual(self.rule('owed_by_running ""', repo=repo), (0, f"{1534 * GB} 1"))
        # what the job itself is never counts against it
        self.assertEqual(self.rule('owed_by_running 42', repo=repo), (0, "0 0"))

    def test_running_fetches_are_counted_even_where_the_caller_globs_nothing(self):
        # the hf-token route decides under set -f, so its pattern reaches hf-get as written
        self.volume.admitted("hf_other", 777, need=3000 * GB)
        self.volume.live(777)
        self.assertEqual(self.rule('set -f; owed_by_running ""; [ -o noglob ] && echo still-off'),
                         (0, f"{3000 * GB} 1\nstill-off"))
        code, out = self.fetch(6000)
        self.assertEqual(code, 4, out)
        self.assertIn("only 5845 gb is free under the quota after 3000 gb owed to 1 running fetch at ", shown(out))


    def test_a_value_is_read_up_to_its_first_nul_and_only_as_a_count(self):
        # On 2026-10-23 getfattr in the owner's shell printed the volume's ceph.dir.rbytes as 48
        # digits, and bash's arithmetic wraps such a number without a word: the use read as less
        # than nothing and the room as 2.5 EB, so every fetch would have been admitted. A value ends
        # at its first NUL, and what is then no count of at most 18 digits is no reading at all.
        quota, path = 21990232555520, self.volume.path
        self.volume.attribute(path, "ceph.quota.max_bytes", quota)
        self.volume.attribute(path, "ceph.dir.rbytes", "16574438800856~3119603013828275240916436124852417")
        self.assertEqual(self.rule(f'volume_free_bytes "{path}"'), (0, f"{quota - 16574438800856} quota"))
        # nor is a value that holds a line break, nor one bash's arithmetic would read as a sum or a base
        for value in ("165744388008563119603013828275240916436124852417", "1000000000000000000", "12abc", "-5",
                      "0123", "~123", "1657^4438800856", "5+5", "16#ff"):
            self.volume.attribute(path, "ceph.dir.rbytes", value)
            self.assertEqual(self.rule(f'volume_free_bytes "{path}"'), (1, ""), value)
        code, out = self.fetch(1)
        self.assertEqual(code, 4, out)
        self.assertNotIn("arg:", out)
        self.assertIn("hf_example: refused; the room under the quota could not be read at ", shown(out))
        # 18 digits is a count, and the sum of a few of them still holds in bash's arithmetic
        self.volume.attribute(path, "ceph.dir.rbytes", "999999999999999999")
        self.assertEqual(self.rule(f'xattr_digits ceph.dir.rbytes "{path}"'), (0, "999999999999999999"))
        self.assertEqual(self.rule(f'xattr_digits ceph.dir.rbytes "{path}"; echo $(( 999999999999999999 * 9 ))'),
                         (0, "999999999999999999\n8999999999999999991"))

    def test_a_size_reader_or_a_record_that_gives_no_count_admits_nothing(self):
        # a size past 18 digits, an admission whose figures are no count and a stated size too
        # large for bash's arithmetic are each no size, never a figure that wraps
        code, out = self.fetch(0, FAKE_SIZE="99999999999999999999 99999999999999999999 by a broken source")
        self.assertEqual(code, 4, out)
        self.assertNotIn("arg:", out)
        self.assertIn("hf_example: refused; the size reader gave no size at ", shown(out))
        # a link's length with a leading zero, which bash's arithmetic reads as octal
        code, out = self.fetch(0, FAKE_SIZE="0123 123 the link answers")
        self.assertEqual(code, 4, out)
        self.assertIn("hf_example: refused; the size reader gave no size at ", shown(out))
        unsized = "hf_example: refused; the running fetch of {} states no size so nothing is admitted beside it at "
        for record in ("admitted 777 99999999999999999999 0 2026-10-23T12:00:00Z 1",
                       "admitted 777 3000 abc 2026-10-23T12:00:00Z 3000"):
            self.volume.meta("hf_other", "SIZE", record)
            self.volume.live(777)
            code, out = self.fetch(1)
            self.assertEqual(code, 4, record)
            self.assertIn(unsized.format("hf other"), shown(out), record)
        # two admissions that each fit in a count but not together: the sum would wrap
        for job in (777, 778):
            self.volume.meta(f"hf_big{job}", "SIZE", f"admitted {job} 600000000000000000 0 2026-10-23T12:00:00Z 1")
        self.volume.meta("hf_other", "SIZE", "admitted 777 0 0 2026-10-23T12:00:00Z 0")
        self.volume.live(777, 778)
        code, out = self.fetch(1)
        self.assertEqual(code, 4, out)
        self.assertIn(unsized.format("hf big778"), shown(out))
        # an X-ray fetch whose recorded size is no count is no size, and nothing is admitted beside it
        repo = repo_copy(self)
        (repo / "grid" / "logs" / "XRAY_SIZES.txt").write_text("501 99999999999999999999 2026-10-23T09:00:00Z\n",
                                                               encoding="utf-8")
        self.volume.live(501)
        self.assertEqual(self.rule('owed_by_running ""', repo=repo), (0, "0 0 xray_chain"))
        # a line whose stated size is past a count says no size either
        repo = repo_copy(self)
        script = repo / "grid" / "run-platform-fetch.sh"
        script.write_text(script.read_text(encoding="utf-8").replace("idc_nlst|idc|11139.6|", "idc_nlst|idc|99999999999|"),
                          encoding="utf-8")
        gate_jobs(repo, (40711959, "fetch:idc_nlst", "dp_idc_nlst"))
        self.volume.live(40711959)
        self.assertEqual(self.rule('owed_by_running ""', repo=repo), (0, "0 0 idc_nlst"))

    def test_python_reads_a_value_up_to_its_first_nul_where_no_getfattr_runs(self):
        folder = self.tmp / "landing"
        folder.mkdir()
        try:
            os.setxattr(folder, "user.rbytes", b"16574438800856\x003119603013828")
            os.setxattr(folder, "user.long", b"165744388008563119603013828275240916436124852417")
            os.setxattr(folder, "user.broken", b"1657\n4438800856")
        except OSError as error:
            self.skipTest(f"this filesystem keeps no user attributes: {error}")
        tools = dict(GETFATTR=str(self.tmp / "no-such-tool"), XATTR_PYTHON=sys.executable)
        self.assertEqual(self.rule(f'xattr_digits user.rbytes "{folder}"', **tools), (0, "16574438800856"))
        self.assertEqual(self.rule(f'xattr_digits user.long "{folder}"', **tools), (3, ""))
        self.assertEqual(self.rule(f'xattr_digits user.broken "{folder}"', **tools), (3, ""))
        self.assertEqual(self.rule(f'xattr_digits user.none "{folder}"', **tools), (0, ""))
        # and the whole value for xattr_whole, which takes nothing after a NUL but NULs
        os.setxattr(folder, "user.ended", b"16574438800856\x00")
        self.assertEqual(self.rule(f'xattr_whole user.ended "{folder}"', **tools), (0, "16574438800856"))
        for name in ("user.rbytes", "user.long", "user.broken", "user.none"):
            self.assertEqual(self.rule(f'xattr_whole {name} "{folder}"', **tools), (0, ""), name)


class QuotaReadoutTest(unittest.TestCase):
    """grid/oschome-quota.sh, the owner's readout of the lab volume in the layout of WSU's wsuquota,
    which reads only the home directory (2026-10-23), from the same reading the size rule decides by."""

    def readout(self, volume, **extra):
        env = dict(os.environ, SCHWINGNET=str(ROOT), **volume.env(**extra))
        done = subprocess.run(["bash", str(GRID / "oschome-quota.sh")], env=env, capture_output=True, text=True,
                              timeout=60)
        return done.returncode, done.stdout

    def test_the_readout_is_wsuquotas_layout_with_what_the_rule_leaves_a_new_fetch(self):
        volume = volume_in(self, quota=21990232555520, used=13146 * GB)
        volume.attribute(volume.path, "ceph.dir.rfiles", 7008826)
        volume.admitted("hf_fluoroseg", 777, need=2650 * GB, base=0, landed=600 * GB)
        volume.live(777)
        code, out = self.readout(volume)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines(), [
            f"Lab Volume Disk Usage, {volume.path} (CephFS quota; 1 gb = 10^9 bytes)",
            "Used  = 59.78%  13146.00gb",
            "Free  = 40.22%  8844.23gb",
            "Total =         21990.23gb",
            "File Count =    7008826",
            "[" + "#" * 57 + "-" * 39 + "]",
            "Owed  =         2050.00gb still to land for 1 running fetch",
            "Room  =         6794.23gb for a new fetch, which lands whole or not at all",
        ])

    def test_a_file_limit_is_shown_where_the_quota_sets_one(self):
        volume = volume_in(self, quota=1000 * GB, used=250 * GB)
        volume.attribute(volume.path, "ceph.dir.rfiles", 4000)
        code, out = self.readout(volume)
        self.assertNotIn("File Limit", out)
        volume.attribute(volume.path, "ceph.quota.max_files", 5000)
        code, out = self.readout(volume)
        self.assertEqual(code, 0, out)
        self.assertIn("File Count =    4000\nFile Limit =    5000, which the size rule does not count\n", out)

    def test_an_unknown_owed_is_said_and_an_unread_quota_ends_2(self):
        volume = volume_in(self, quota=1000 * GB, used=250 * GB)
        code, out = self.readout(volume, FAKE_SQUEUE_FAILS="1")
        self.assertEqual(code, 0, out)
        self.assertIn("Used  = 25.00%  250.00gb", out)
        self.assertIn("[" + "#" * 24 + "-" * 72 + "]", out)
        self.assertIn("Owed  =         not known; squeue did not answer, so the size rule admits no fetch now", out)
        self.assertNotIn("Room", out)
        code, out = self.readout(volume_in(self, quota=1000 * GB))
        self.assertEqual(code, 2, out)
        self.assertIn("The CephFS quota or its use could not be read", out)

    def test_a_value_after_a_nul_is_left_out_and_one_that_is_no_count_is_named(self):
        # The owner's paste of 2026-10-23: the quota read whole, the use and the file count as 48
        # and 25 digits. Cut at a NUL the readout is the volume's; with none it takes nothing for a
        # count, says which attribute it was and ends 2, so no wrapped figure is shown or decided by.
        volume = volume_in(self, quota=21990232555520, used="16574438800856~3119603013828275240916436124852417")
        volume.attribute(volume.path, "ceph.dir.rfiles", "23636422~12733507223600077")
        code, out = self.readout(volume)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[1:6], [
            "Used  = 75.37%  16574.44gb",
            "Free  = 24.63%  5415.79gb",
            "Total =         21990.23gb",
            "File Count =    23636422",
            "[" + "#" * 72 + "-" * 24 + "]",
        ])
        volume.attribute(volume.path, "ceph.dir.rfiles", "2363642212733507223600077")
        code, out = self.readout(volume)
        self.assertEqual(code, 0, out)
        self.assertIn("File Count =    not read; ceph.dir.rfiles reads as no count, 25 characters up to its first NUL "
                      "where a count has at most 18 digits\n", out)
        volume.attribute(volume.path, "ceph.dir.rbytes", "165744388008563119603013828275240916436124852417")
        # stat here gives a folder's entry count as its size, as the kernel client does without its
        # rbytes option, which the data root shows, so stat cannot stand in for the attribute (#170);
        # and the volume's one entry is not the nine stat counts, so neither can its entries (#172)
        volume.attribute(volume.data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(volume.data, "stat.size", 87)
        volume.attribute(volume.path, "stat.size", 9)
        code, out = self.readout(volume, STAT=str(volume.tools / "stat"))
        self.assertEqual(code, 2, out)
        self.assertEqual(out.splitlines()[1:], [
            "The CephFS quota or its use could not be read, so the size rule admits no fetch:",
            "  ceph.quota.max_bytes reads 21990232555520",
            "  ceph.dir.rbytes reads as no count, 48 characters up to its first NUL where a count has at most 18 digits",
            "  getfattr gives it as 48 bytes, 165744388008563119603013828275240916436124852417",
            "  stat gives the volume's size as 9 and the data root's as 87 on a mount it calls ceph, where the data "
            "root's ceph.dir.rbytes is 14062000000000",
            "  its own 1 entry, 1 of them a folder, hold 14062000000000 where they read, and stat gives the volume's "
            "size as 9, not 1, so the listing may leave some out",
        ])

    def rule(self, volume, call, **extra):
        """One function of grid/size-rule.sh, called in bash with the volume's stand-ins."""
        env = dict(os.environ, DATA=str(volume.data))
        env.update(volume.env(**extra))
        done = subprocess.run(["bash", "-c", f'. "{GRID / "size-rule.sh"}"; {call}'], env=env, capture_output=True,
                              text=True, timeout=60)
        return done.returncode, done.stdout.strip()

    def test_a_use_that_is_no_count_is_read_by_stat_where_the_mount_gives_a_folders_rbytes(self):
        # The status word's answer of 2026-10-23 (#170): the volume's ceph.dir.rbytes is 48 digits on
        # the login node, where warrior kills Python by name, while the data root's reads clean. Where
        # stat gives the data root's attribute as its size, the volume's size is its use, read by a
        # path that does not pass through getxattr; the readout says so and shows what getfattr gave.
        volume = volume_in(self, quota=21990232555520, used="165744388008563119603013828275240916436124852417")
        volume.attribute(volume.path, "ceph.dir.rfiles", "2363642212733507223600077")
        volume.attribute(volume.data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(volume.data, "stat.size", 14062 * GB)
        volume.attribute(volume.path, "stat.size", 16574438800856)
        stat = str(volume.tools / "stat")
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[1:], [
            "Used  = 75.37%  16574.44gb",
            "Free  = 24.63%  5415.79gb",
            "Total =         21990.23gb",
            "File Count =    not read; ceph.dir.rfiles reads as no count, 25 characters up to its first NUL "
            "where a count has at most 18 digits",
            "[" + "#" * 72 + "-" * 24 + "]",
            "Used is the volume's size by stat, since its ceph.dir.rbytes reads as no count, 48 characters up to its "
            "first NUL where a count has at most 18 digits; getfattr gives it as 48 bytes, "
            "165744388008563119603013828275240916436124852417",
            "On this mount stat gives a folder's ceph.dir.rbytes as its size: the data root's size by stat, "
            "14062000000000, matches its own ceph.dir.rbytes read before and after",
            "Owed  =         0.00gb still to land for 0 running fetches",
            "Room  =         5415.79gb for a new fetch, which lands whole or not at all",
        ])
        # the size rule decides by the same figure, and by the attribute wherever that is a count
        room = 21990232555520 - 16574438800856
        self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat), (0, f"{room} quota"))
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, "16574438800856 stat"))
        volume.attribute(volume.path, "ceph.dir.rbytes", 16000 * GB)
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, f"{16000 * GB} attribute"))
        # a count below the data root's 14062 GB is no reading of the volume that holds it
        volume.attribute(volume.path, "ceph.dir.rbytes", 13146 * GB)
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, "16574438800856 stat"))

    def test_stat_stands_in_only_on_the_data_roots_mount_and_only_with_a_count(self):
        volume = volume_in(self, quota=21990232555520, used="165744388008563119603013828275240916436124852417")
        volume.attribute(volume.data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(volume.data, "stat.size", 14062 * GB)
        stat = str(volume.tools / "stat")
        # a size that is no count, as a negative one or one past 18 digits, is no reading
        for size in ("-1", "1657443880085631196", ""):
            volume.attribute(volume.path, "stat.size", size or "x")
            code, out = self.readout(volume, STAT=stat)
            self.assertEqual(code, 2, out)
            self.assertIn("The CephFS quota or its use could not be read, so the size rule admits no fetch:", out)
            self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (3, ""), size)
            self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat), (1, ""), size)
        # a data root off the volume shows nothing of the volume's mount
        import tempfile
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        volume.attribute(elsewhere.name, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(elsewhere.name, "stat.size", 14062 * GB)
        volume.attribute(volume.path, "stat.size", 16574438800856)
        code, out = self.readout(volume, STAT=stat, DATA_ROOT=elsewhere.name)
        self.assertEqual(code, 2, out)
        self.assertIn("\n  stat gives the volume's size as 16574438800856 on a mount it calls ceph, and the data root, "
                      "its links and any .. resolved, is no folder inside the volume, so it shows nothing of the "
                      "volume's mount\n", out)
        # nor does one whose own attribute cannot be read
        volume.attribute(volume.data, "ceph.dir.rbytes", "")
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 2, out)
        self.assertIn("\n  stat gives the volume's size as 16574438800856 and the data root's as 14062000000000 on a "
                      "mount it calls ceph, where the data root's ceph.dir.rbytes is unread\n", out)

    def test_stat_is_trusted_only_between_two_readings_of_the_data_roots_attribute(self):
        # A fetch landing between the readings moves the data root's attribute: its size by stat counts
        # when it lies between the reading before and the one after, in either order, and not outside.
        volume = volume_in(self, quota=21990232555520)
        readings = volume.tools / "readings"
        twice = volume.tools / "getfattr-readings"
        twice.write_text('#!/bin/bash\nhead -n 1 "$READINGS" | tr -d "\\n"\nsed -i 1d "$READINGS"\n', encoding="utf-8")
        twice.chmod(0o755)
        stat = str(volume.tools / "stat")
        low, high = 100 * GB, 300 * GB
        cases = [(low, high, low, True), (low, high, 200 * GB, True), (low, high, high, True),
                 (high, low, 200 * GB, True), (low, high, low - 1, False), (low, high, high + 1, False),
                 (low, low, low, True), (low, low, 87, False),
                 # an empty or near-empty data root holds about as many bytes as entries, so on a mount
                 # that gives a folder's entry count it would prove what is not so: under a gigabyte, nothing
                 (0, 0, 0, False), (1, 1, 1, False), (GB - 1, GB - 1, GB - 1, False), (GB, GB, GB, True)]
        for first, second, size, trusted in cases:
            readings.write_text(f"{first}\n{second}\n", encoding="utf-8")
            volume.attribute(volume.data, "stat.size", size)
            said = self.rule(volume, 'stat_gives_rbytes "$VOLUME"', STAT=stat, GETFATTR=str(twice),
                             READINGS=str(readings))
            # what it gives is the lower reading, the least the data root, and so the volume, holds
            self.assertEqual(said, (0, str(min(first, second))) if trusted else (1, ""), (first, second, size))
            self.assertEqual(readings.read_text(encoding="utf-8"), "", "the attribute is read twice")

    def test_a_volume_that_is_a_link_is_read_by_stat_through_it_and_never_below_its_data_root(self):
        # On the grid /rs/rs_grp_oschome is a link into /.rs/volumes, whose own size is the length of
        # the path it holds: stat follows it, and a size below the data root's is no reading at all.
        import tempfile
        volume = volume_in(self, quota=21990232555520)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        link = Path(tmp.name) / "rs_grp_oschome"
        link.symlink_to(volume.path)
        data = f"{link}/data"
        volume.attribute(link, "ceph.quota.max_bytes", 21990232555520)
        volume.attribute(link, "ceph.dir.rbytes", "165744388008563119603013828275240916436124852417")
        volume.attribute(data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(data, "stat.size", 14062 * GB)
        volume.attribute(volume.path, "stat.size", 16574438800856)
        stat = str(volume.tools / "stat")
        code, out = self.readout(volume, STAT=stat, VOLUME=str(link), DATA_ROOT=data)
        self.assertEqual(code, 0, out)
        self.assertIn("\nUsed  = 75.37%  16574.44gb\n", out)
        self.assertIn("\nUsed is the volume's size by stat, since its ceph.dir.rbytes reads as no count", out)
        # the folder the link names holds less than the data root: no reading, and no fetch admitted
        volume.attribute(volume.path, "stat.size", 14062 * GB - 1)
        code, out = self.readout(volume, STAT=stat, VOLUME=str(link), DATA_ROOT=data)
        self.assertEqual(code, 2, out)
        self.assertIn("\n  stat gives the volume's size as 14061999999999 and the data root's as 14062000000000 on a "
                      "mount it calls ceph, where the data root's ceph.dir.rbytes is 14062000000000\n", out)
        self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat, VOLUME=str(link), DATA=data),
                         (1, ""))

    def test_a_count_below_the_data_roots_is_no_reading_of_the_volume(self):
        # The volume holds the data root, so a count of its use below the data root's is cut short,
        # as a NUL after its fourth digit would leave it: stat reads the use where it can, and where
        # it cannot nothing is admitted, never a room of almost the whole quota.
        volume = volume_in(self, quota=21990232555520, used="1657~4438800856")
        volume.attribute(volume.data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(volume.data, "stat.size", 14062 * GB)
        volume.attribute(volume.path, "stat.size", 16574438800856)
        stat = str(volume.tools / "stat")
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 0, out)
        self.assertIn("\nUsed  = 75.37%  16574.44gb\n", out)
        self.assertIn("\nUsed is the volume's size by stat, since its ceph.dir.rbytes reads 1657, less than the data "
                      "root's 14062000000000 inside it, so it is no reading of the volume; getfattr gives it as 15 "
                      "bytes, 1657\\0004438800856\n", out)
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, "16574438800856 stat"))
        # on a mount that gives a folder's entry count, and with fewer entries than it counts, nothing
        volume.attribute(volume.data, "stat.size", 87)
        volume.attribute(volume.path, "stat.size", 9)
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 2, out)
        self.assertEqual(out.splitlines()[1:], [
            "The CephFS quota or its use could not be read, so the size rule admits no fetch:",
            "  ceph.quota.max_bytes reads 21990232555520",
            "  ceph.dir.rbytes reads 1657, less than the data root's 14062000000000 inside it, so it is no reading "
            "of the volume",
            "  getfattr gives it as 15 bytes, 1657\\0004438800856",
            "  stat gives the volume's size as 9 and the data root's as 87 on a mount it calls ceph, where the data "
            "root's ceph.dir.rbytes is 14062000000000",
            "  its own 1 entry, 1 of them a folder, hold 14062000000000 where they read, and stat gives the volume's "
            "size as 9, not 1, so the listing may leave some out",
        ])
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (3, ""))
        self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat), (1, ""))

    def test_only_a_data_root_inside_the_volume_on_its_mount_and_of_a_gigabyte_shows_what_stat_gives(self):
        # The case the proof exists for: a mount that gives a folder's entry count as its size, here 9
        # for the volume. An empty data root has as many bytes as entries, none, and taken as proof
        # would read the use as 9 bytes and leave the whole quota free; a sibling of the volume, a ..
        # out of it or a folder on another mount says nothing of the volume's own mount, so each is
        # refused even where it holds terabytes and its size by stat matches them.
        volume = volume_in(self, quota=21990232555520, used="165744388008563119603013828275240916436124852417")
        volume.attribute(volume.path, "stat.size", 9)
        stat = str(volume.tools / "stat")
        for held in (0, 1):
            volume.attribute(volume.data, "ceph.dir.rbytes", held)
            volume.attribute(volume.data, "stat.size", held)
            code, out = self.readout(volume, STAT=stat)
            self.assertEqual(code, 2, out)
            self.assertIn(f"\n  stat gives the volume's size as 9 and the data root's as {held} on a mount it calls "
                          f"ceph, where the data root's ceph.dir.rbytes is {held}\n", out)
            self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat), (1, ""))
        volume.attribute(volume.path, "stat.size", 16574438800856)
        sibling = volume.path.parent / f"{volume.path.name}2" / "data"
        sibling.mkdir(parents=True)
        dotdot = f"{volume.path}/../{volume.path.name}2/data"
        for data in (str(sibling), dotdot):
            volume.attribute(data, "ceph.dir.rbytes", 14062 * GB)
            volume.attribute(data, "stat.size", 14062 * GB)
            code, out = self.readout(volume, STAT=stat, DATA_ROOT=data)
            self.assertEqual(code, 2, out)
            self.assertIn("\n  stat gives the volume's size as 16574438800856 on a mount it calls ceph, and the data "
                          "root, its links and any .. resolved, is no folder inside the volume, so it shows nothing "
                          "of the volume's mount\n", out)
            self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat, DATA=data), (1, ""))
        # one inside the volume, on another device and so another mount
        volume.attribute(volume.data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(volume.data, "stat.size", 14062 * GB)
        volume.attribute(volume.path, "stat.dev", 2049)
        volume.attribute(volume.data, "stat.dev", 77)
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 2, out)
        self.assertIn("\n  stat gives the volume's size as 16574438800856 on a mount it calls ceph, device 2049, and "
                      "the data root lies on device 77, another mount, so it shows nothing of the volume's\n", out)
        self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat), (1, ""))
        # on the volume's own device it shows stat gives a folder's bytes, and the volume's size is its use
        volume.attribute(volume.data, "stat.dev", 2049)
        self.assertEqual(self.rule(volume, 'stat_gives_rbytes "$VOLUME"', STAT=stat), (0, str(14062 * GB)))
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, "16574438800856 stat"))
        # a data root that is not there shows nothing, nor do devices stat gives as no number
        code, out = self.readout(volume, STAT=stat, DATA_ROOT=str(volume.path / "gone"))
        self.assertEqual(code, 2, out)
        self.assertIn("\n  stat gives the volume's size as 16574438800856 on a mount it calls ceph, with no data root "
                      "to show what stat gives a folder on the volume's mount\n", out)
        volume.attribute(volume.path, "stat.dev", "x")
        volume.attribute(volume.data, "stat.dev", "x")
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (3, ""))

    def test_an_unread_quota_is_named_where_stat_reads_the_use(self):
        # Where the use reads and the quota does not, the readout names the quota alone as the cause.
        volume = volume_in(self, used="165744388008563119603013828275240916436124852417")
        volume.attribute(volume.data, "ceph.dir.rbytes", 14062 * GB)
        volume.attribute(volume.data, "stat.size", 14062 * GB)
        volume.attribute(volume.path, "stat.size", 16574438800856)
        code, out = self.readout(volume, STAT=str(volume.tools / "stat"))
        self.assertEqual(code, 2, out)
        self.assertEqual(out.splitlines()[1:], [
            "The CephFS quota or its use could not be read, so the size rule admits no fetch:",
            "  ceph.quota.max_bytes reads as not there",
            "  its use reads 16574438800856 as the volume's size by stat",
        ])

    def grid_volume(self):
        """The lab volume as the status word of 2026-10-23 17:15 UTC found it (#172): its own
        ceph.dir.rbytes and ceph.dir.rfiles no count, a mount that gives a folder's entry count as its
        size (the volume 3, the data root 126), and three entries whose attributes read, a hidden
        file among them, with the data root two folders down."""
        volume = volume_in(self, quota=21990232555520, used="165744388008563119603013828275240916436124852417")
        volume.attribute(volume.path, "ceph.dir.rfiles", "2363642212733507223600077")
        volume.data.rmdir()
        home, shared = volume.path / "go2432", volume.path / "shared"
        volume.data = home / "data"
        volume.data.mkdir(parents=True)
        shared.mkdir()
        (volume.path / ".keep").write_text("0123456789", encoding="utf-8")
        volume.attribute(home, "ceph.dir.rbytes", 14200 * GB)
        volume.attribute(shared, "ceph.dir.rbytes", 136 * GB)
        volume.attribute(volume.data, "ceph.dir.rbytes", 14061320335387)
        volume.attribute(volume.data, "stat.size", 126)
        volume.attribute(volume.path, "stat.size", 3)
        return volume

    def test_where_stat_gives_entry_counts_the_use_is_the_sum_of_what_the_volumes_own_entries_hold(self):
        # Each folder by its ceph.dir.rbytes, which reads below the volume, and the file by its size:
        # every entry read whole, as many as stat counts, the sum no less than the data root's.
        volume = self.grid_volume()
        stat = str(volume.tools / "stat")
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[1:], [
            "Used  = 65.19%  14336.00gb",
            "Free  = 34.81%  7654.23gb",
            "Total =         21990.23gb",
            "File Count =    not read; ceph.dir.rfiles reads as no count, 25 characters up to its first NUL "
            "where a count has at most 18 digits",
            "[" + "#" * 62 + "-" * 34 + "]",
            "Used is the sum of what the volume's own entries hold, since its ceph.dir.rbytes reads as no count, "
            "48 characters up to its first NUL where a count has at most 18 digits; getfattr gives it as 48 bytes, "
            "165744388008563119603013828275240916436124852417",
            "Each of its 3 entries, 2 of them folders, read whole on the volume's mount, a folder by its "
            "ceph.dir.rbytes and a file or link by its size: stat gives the volume's size as 3, its count of "
            "entries, and the sum is no less than the data root's ceph.dir.rbytes, 14061320335387",
            "Owed  =         0.00gb still to land for 0 running fetches",
            "Room  =         7654.23gb for a new fetch, which lands whole or not at all",
        ])
        used = 14200 * GB + 136 * GB + 10
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, f"{used} entries"))
        self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat),
                         (0, f"{21990232555520 - used} quota"))
        # the hf-token route decides under set -f, which must leave no entry unlisted
        self.assertEqual(self.rule(volume, 'set -f; volume_used "$VOLUME"', STAT=stat), (0, f"{used} entries"))
        # NULs after the digits end the value; anything after a NUL but NULs is no count
        volume.attribute(volume.path / "shared", "ceph.dir.rbytes", "136000000000~~")
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, f"{used} entries"))
        # a link is counted by its own size, the length of the path it holds, as CephFS counts it
        (volume.path / "latest").symlink_to("go2432")
        volume.attribute(volume.path, "stat.size", 4)
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, f"{used + 6} entries"))
        self.assertEqual(self.rule(volume, 'entries_census "$VOLUME"', STAT=stat), (0, f"4 2 0 0 {used + 6}"))
        # a name may hold a line break, and is still one entry
        (volume.path / "two\nlines").write_text("12345", encoding="utf-8")
        volume.attribute(volume.path, "stat.size", 5)
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, f"{used + 11} entries"))
        # where the quota cannot be read, the readout names it and the sum it read
        volume.attribute(volume.path, "ceph.quota.max_bytes", "")
        code, out = self.readout(volume, STAT=stat)
        self.assertEqual(code, 2, out)
        self.assertEqual(out.splitlines()[1:], [
            "The CephFS quota or its use could not be read, so the size rule admits no fetch:",
            "  ceph.quota.max_bytes reads as not there",
            f"  its use reads {used + 11} as the sum of what its own entries hold",
        ])

    def test_the_sum_of_the_entries_admits_nothing_where_one_is_left_out_or_cut_short(self):
        # All or nothing, as the size rule is: each way the sum could read less than the volume holds
        # is refused, and the readout says which in counts, naming no entry.
        volume = self.grid_volume()
        stat = str(volume.tools / "stat")
        shared = volume.path / "shared"
        held = "its own 3 entries, 2 of them folders, hold"

        def refused(words, **extra):
            code, out = self.readout(volume, STAT=stat, **extra)
            self.assertEqual(code, 2, out)
            self.assertIn(f"\n  {words}\n", out)
            self.assertEqual(self.rule(volume, 'volume_used "$VOLUME" 2>&1', STAT=stat, **extra), (3, ""), words)
            self.assertEqual(self.rule(volume, 'volume_free_bytes "$VOLUME"', STAT=stat, **extra), (1, ""), words)

        # a folder whose attribute holds digits after a NUL, a z, no digits at all, or is not there
        for value in ("136~000000000", "136z", "165744388008563119603013828275240916436124852417", ""):
            volume.attribute(shared, "ceph.dir.rbytes", value)
            refused(f"{held} {14200 * GB + 10} where they read, and 1 reads no count, so their sum is no reading "
                    "of it")
        volume.attribute(shared, "ceph.dir.rbytes", 136 * GB)
        # more entries than the listing shows
        volume.attribute(volume.path, "stat.size", 4)
        refused(f"{held} {14336 * GB + 10} where they read, and stat gives the volume's size as 4, not 3, so the "
                "listing may leave some out")
        volume.attribute(volume.path, "stat.size", 3)
        # a folder mounted from elsewhere, which hides what the volume holds under it
        for folder in (volume.path, volume.data, volume.path / "go2432", volume.path / ".keep"):
            volume.attribute(folder, "stat.dev", 2049)
        volume.attribute(shared, "stat.dev", 77)
        refused(f"{held} {14200 * GB + 10} where they read, and 1 lies on another mount, which hides what the "
                "volume holds under it, so their sum is no reading of it")
        # an entry whose device stat gives as no number reads no count; the volume's, nothing is summed
        volume.attribute(shared, "stat.dev", "x")
        refused(f"{held} {14200 * GB + 10} where they read, and 1 reads no count, so their sum is no reading of it")
        volume.attribute(shared, "stat.dev", 2049)
        volume.attribute(volume.path, "stat.dev", "x")
        refused("its own entries cannot be summed, since stat gives it no device")
        volume.attribute(volume.path, "stat.dev", 2049)
        # a sum below the data root's, which one of the entries holds
        volume.attribute(volume.path / "go2432", "ceph.dir.rbytes", 100 * GB)
        refused(f"{held} {236 * GB + 10} where they read, less than the data root's 14061320335387 inside it, so "
                "their sum is no reading of it")
        # a sum past 18 digits, which bash would wrap
        volume.attribute(volume.path / "go2432", "ceph.dir.rbytes", 999999999999999000)
        refused(f"{held} 999999999999999010 where they read, and 1 reads no count, so their sum is no reading of it")
        volume.attribute(volume.path / "go2432", "ceph.dir.rbytes", 14200 * GB)
        # no data root inside the volume on its mount to check the sum against
        import tempfile
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        refused(f"{held} {14336 * GB + 10} where they read, with no data root inside it on its mount whose "
                "ceph.dir.rbytes reads, to show their sum leaves none short", DATA_ROOT=elsewhere.name,
                DATA=elsewhere.name)
        # and with all of it as it was, the sum reads again
        self.assertEqual(self.rule(volume, 'volume_used "$VOLUME"', STAT=stat), (0, f"{14336 * GB + 10} entries"))

    def test_the_fetch_job_admits_by_the_sum_under_its_set_f(self):
        # platform-fetch.sbatch decides an hf-token fetch under set -f, so its include pattern reaches
        # hf-get as written; the entries are listed all the same, and the room is what their sum leaves.
        volume = self.grid_volume()
        volume.attribute(f"{volume.data}/*", "ceph.dir.rbytes", 0)
        stat = str(volume.tools / "stat")
        tmp = volume.path.parent

        def fetch(need_gb):
            return run_fetch_job(tmp, volume, "hf-token", HF_ARGS, STAT=stat, FAKE_FILES="2",
                                 FAKE_SIZE=f"{need_gb * GB} {need_gb * GB} 3 files listed by the hub")

        code, out = fetch(7655)
        self.assertEqual(code, 4, out)
        self.assertIn("hf_example: refused for space; it needs 7655 gb of its 7655 gb by 3 files listed by the hub and "
                      "only 7654 gb is free under the quota after 0 gb owed to 0 running fetches at ", shown(out))
        code, out = fetch(7654)
        self.assertEqual(code, 0, out)
        self.assertIn("hf_example: admitted; it needs 7654 gb of its 7654 gb by 3 files listed by the hub and 7655 gb "
                      "is free under the quota after 0 gb owed to 0 running fetches at ", shown(out))

    def test_an_empty_folder_or_one_with_no_device_has_no_sum(self):
        volume = volume_in(self, quota=1000 * GB)
        empty = volume.path / "empty"
        empty.mkdir()
        self.assertEqual(self.rule(volume, f'entries_words "{empty}"'),
                         (0, "its folder lists no entry to sum, as one that cannot be read lists none"))
        self.assertEqual(self.rule(volume, f'entries_census "{empty}"'), (0, "0 0 0 0 0"))
        self.assertEqual(self.rule(volume, f'use_by_entries "{empty}"'), (1, ""))
        gone = volume.path / "gone"
        self.assertEqual(self.rule(volume, f'entries_words "{gone}"'),
                         (0, "its own entries cannot be summed, since stat gives it no device"))
        self.assertEqual(self.rule(volume, f'use_by_entries "{gone}"'), (1, ""))

    def test_a_whole_reading_takes_nothing_after_a_nul_but_nuls(self):
        # xattr_whole reads every byte, where xattr_value stops at the first NUL
        volume = volume_in(self)
        folder = volume.path / "landing"
        folder.mkdir()
        for value, whole, cut in (("16574438800856", "16574438800856", "16574438800856"),
                                  ("16574438800856~~", "16574438800856", "16574438800856"),
                                  ("1657~4438800856", "", "1657"), ("1657~~4", "", "1657"),
                                  ("1657z", "", ""), ("1657^", "", "1657"), ("~1657", "", ""), ("01657", "", ""),
                                  ("9" * 19, "", ""), ("", "", "")):
            volume.attribute(folder, "user.rbytes", value)
            self.assertEqual(self.rule(volume, f'xattr_whole user.rbytes "{folder}"'), (0, whole), value)
            self.assertEqual(self.rule(volume, f'xattr_digits user.rbytes "{folder}"')[1], cut, value)

    def test_every_byte_getfattr_gives_is_shown_where_the_use_is_no_count(self):
        # past the first NUL, a line break and a backslash as octal escapes, so the readout names what
        # the reading rule refused
        volume = volume_in(self, quota=1000 * GB, used="1657^4438800856~~")
        code, out = self.readout(volume, STAT=str(volume.tools / "stat"))
        self.assertEqual(code, 2, out)
        self.assertIn("\n  getfattr gives it as 17 bytes, 1657\\0124438800856\\000\\000\n", out)
        volume.attribute(volume.path, "ceph.dir.rbytes", "12\\34")
        code, out = self.readout(volume, STAT=str(volume.tools / "stat"))
        self.assertIn("\n  getfattr gives it as 5 bytes, 12\\13434\n", out)
        volume.attribute(volume.path, "ceph.dir.rbytes", "7" * 100)
        code, out = self.readout(volume, STAT=str(volume.tools / "stat"))
        self.assertIn("\n  getfattr gives it as 100 bytes, " + "7" * 96 + " and more\n", out)


class WsuquotaTest(unittest.TestCase):
    """grid/wsuquota.bash, sourced from the owner's ~/.bashrc: wsuquota prints WSU's home-directory
    readout as it did and the lab volume's after it, whatever wsuquota was in that shell (2026-10-23:
    "always print it when i type wsuquota")."""

    HOOK = f'source "{GRID / "wsuquota.bash"}"'

    def setUp(self):
        import tempfile
        self.volume = volume_in(self, quota=1000 * GB, used=250 * GB)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name)
        # WSU's command, as it stands on the login node's PATH
        (self.bin / "wsuquota").write_text('#!/bin/bash\necho "Home Directory Disk Usage" "$@"\n', encoding="utf-8")
        (self.bin / "wsuquota").chmod(0o755)

    def typed(self, *lines, command=True):
        """LINES as an interactive shell's ~/.bashrc runs them, then wsuquota typed at its prompt."""
        script = "\n".join(("shopt -s expand_aliases",) + lines + ("echo SOURCED", "wsuquota"))
        env = dict(os.environ, SCHWINGNET=str(ROOT), **self.volume.env())
        if command:
            env["PATH"] = f"{self.bin}:{env['PATH']}"
        done = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=60)
        return done.returncode, done.stdout, done.stderr

    def lab(self):
        return f"Lab Volume Disk Usage, {self.volume.path} (CephFS quota; 1 gb = 10^9 bytes)"

    def test_wsus_command_prints_first_and_the_lab_volume_after_it(self):
        code, out, err = self.typed(self.HOOK)
        self.assertEqual((code, err), (0, ""), out)
        # sourcing it printed nothing
        self.assertEqual(out.splitlines()[:5], ["SOURCED", "Home Directory Disk Usage", "", self.lab(),
                                                "Used  = 25.00%  250.00gb"])

    def test_an_alias_or_a_function_is_wrapped_once_however_often_bashrc_runs(self):
        for made in ('alias wsuquota="echo Home Directory Disk Usage"', "wsuquota() { echo Home Directory Disk Usage; }"):
            # a second `source ~/.bashrc` makes the alias or the function again before the hook
            code, out, err = self.typed(made, self.HOOK, made, self.HOOK, command=False)
            self.assertEqual((code, err), (0, ""), made)
            self.assertEqual(out.splitlines()[:4], ["SOURCED", "Home Directory Disk Usage", "", self.lab()], made)
            self.assertEqual(out.count("Disk Usage"), 2, out)
            code, out, err = self.typed(made, self.HOOK, self.HOOK, command=False)
            self.assertEqual(out.count("Disk Usage"), 2, out)

    def test_an_alias_that_names_the_command_reaches_it_once(self):
        code, out, err = self.typed('alias wsuquota="wsuquota --all"', self.HOOK)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(out.splitlines()[:4], ["SOURCED", "Home Directory Disk Usage --all", "", self.lab()])

    def test_with_no_wsuquota_the_lab_volume_alone_prints(self):
        code, out, err = self.typed(self.HOOK, command=False)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(out.splitlines()[:2], ["SOURCED", self.lab()])
        # a command is looked up when wsuquota is typed, so one that comes on the PATH later is run
        code, out, err = self.typed(self.HOOK, f'PATH="{self.bin}:$PATH"', command=False)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(out.splitlines()[:4], ["SOURCED", "Home Directory Disk Usage", "", self.lab()])

    def test_a_shell_that_redefines_cd_or_pwd_still_finds_the_readout(self):
        # Many a ~/.bashrc makes cd print or list; the hook runs neither, from a path or a bare name.
        noisy = ('cd() { builtin cd "$@" && echo CD; }', 'alias pwd="echo PWD"')
        for folder, sourced in ((GRID.parent, "source grid/wsuquota.bash"), (GRID, "source ./wsuquota.bash"),
                                (GRID, ". wsuquota.bash")):
            code, out, err = self.typed(*noisy, f'builtin cd "{folder}"', sourced, "builtin cd /")
            self.assertEqual((code, err), (0, ""), sourced + out)
            self.assertEqual(out.splitlines()[:4], ["SOURCED", "Home Directory Disk Usage", "", self.lab()], sourced)
            self.assertFalse({"CD", "PWD"} & set(out.splitlines()), out)

    def test_an_original_function_keeps_its_own_variables_and_its_exit(self):
        # An owner's function may set status, as many do; the wrapper's own names never meet it, and
        # its exit comes back after the lab volume has printed.
        for made, exit_code in (("wsuquota() { status=ok; echo Home Directory Disk Usage; }", 0),
                                ("wsuquota() { echo Home Directory Disk Usage; return 3; }", 3)):
            code, out, err = self.typed(made, self.HOOK, command=False)
            self.assertEqual((code, err), (exit_code, ""), made + out)
            self.assertEqual(out.splitlines()[:5], ["SOURCED", "Home Directory Disk Usage", "", self.lab(),
                                                    "Used  = 25.00%  250.00gb"], made)

    def test_an_exported_function_is_wrapped_in_a_child_shell_too(self):
        # A function the owner exported stays exported once the hook redefines it, so a child shell
        # runs the wrapper, and with it what the wrapper runs.
        made = "wsuquota() { echo Home Directory Disk Usage; }"
        code, out, err = self.typed(made, "export -f wsuquota", self.HOOK, "bash -c wsuquota", command=False)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(out.splitlines()[:3], ["Home Directory Disk Usage", "", self.lab()])
        self.assertEqual(out.count(self.lab()), 2, out)
        self.assertEqual(out.count("Home Directory Disk Usage"), 2, out)

    def test_a_hook_whose_readout_is_gone_says_so(self):
        import shutil
        lone = self.bin / "lone"
        lone.mkdir()
        shutil.copy(GRID / "wsuquota.bash", lone)
        code, out, err = self.typed(f'source "{lone / "wsuquota.bash"}"')
        self.assertEqual(code, 1, out + err)
        self.assertIn("Home Directory Disk Usage\n\nThe lab volume's readout is not there: "
                      f"{lone / 'oschome-quota.sh'}\n", out)
