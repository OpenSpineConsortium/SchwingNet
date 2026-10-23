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
SCRIPTS = ("run-xray-chain.sh", "run-platform-fetch.sh")


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

    def dry_run(self, script, *args, free="9000G"):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df = Path(tmp) / "df"
            df.write_text(f"#!/bin/bash\necho Avail\necho {free}\n", encoding="utf-8")
            df.chmod(0o755)
            env = dict(os.environ, SCHWINGNET=str(ROOT), HPCW_DRY="1", DF=str(df), HOME=str(self.home))
            done = subprocess.run(["bash", str(GRID / script), *args], env=env, capture_output=True, text=True,
                                  timeout=60)
            Path(ROOT / "grid" / "LAST_RUN.txt").unlink(missing_ok=True)
        return done.returncode, done.stdout + done.stderr

    def test_the_chain_submits_three_dependent_jobs_in_a_dry_run(self):
        code, out = self.dry_run("run-xray-chain.sh", "--only", "cathaction,fracatlas")
        self.assertEqual(code, 0, out)
        self.assertIn("would submit: hpcworker job submit --project schwingnet --name xr_fetch --class batch", out)
        self.assertIn("-- 01-fetch.sbatch", out)
        self.assertIn("--name xr_bank --class batch --dir " + str(ROOT / "grid") + " --after DRY_xr_fetch:any -- 02-bank-ingest.sbatch", out)
        self.assertIn("--after DRY_xr_bank:any -- 03-catalog.sbatch", out)
        self.assertIn("size budget: 2 entries, 14 GB stated", out)
        self.assertIn("no size stated for: fracatlas", out)
        self.assertIn("ETA:", out)
        code, out = self.dry_run("run-xray-chain.sh", free="5010G")
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
        self.assertIn("2305 GB stated", out)
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


class HuggingFaceRouteTest(unittest.TestCase):
    """The hf-token route of grid/platform-fetch.sbatch (#158). reacquire.py hf-get reads --include
    as a glob, as fnmatch and huggingface_hub's allow_patterns do, never as the regular expression
    the acq and zenodo routes take, and it ends 0 having verified no file when the glob matches
    none: FluoroSeg, ReXGradient-160K and CADS each ended so on 2026-10-23, COMPLETED with nothing
    fetched. The job now fails by name on such a run, and the glob reaches hf-get as written."""

    # Stands in for the acq environment's python running reacquire.py hf-get: it prints each
    # argument it was given and writes hf-get's summary with FAKE_FILES files verified.
    FAKE_PYTHON = """#!/bin/bash
state=""
while [ $# -gt 0 ]; do
  case "$1" in --state) state=$2; shift 2 ;; *) printf 'arg: %s\\n' "$1"; shift ;; esac
done
mkdir -p "$state"
verified=false; [ "${FAKE_FILES:-0}" -gt 0 ] && verified=true
printf '{\\n "repo": "a/b",\\n "files": %s,\\n "failed": 0,\\n "all_verified": %s\\n}' "${FAKE_FILES:-0}" "$verified" > "$state/hf_a_b.json"
echo "hf a/b@0123: ${FAKE_FILES:-0} files, 0 failed"
"""

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

    def run_job(self, tmp, files):
        acq = tmp / "acq" / "bin"
        acq.mkdir(parents=True)
        (acq / "python").write_text(self.FAKE_PYTHON, encoding="utf-8")
        (acq / "python").chmod(0o755)
        token = tmp / "token.env"
        token.write_text("HF_TOKEN=not-a-token\n", encoding="utf-8")
        token.chmod(0o600)
        work = tmp / "work"
        work.mkdir()
        # a file the pattern would name, were this shell to expand it
        (work / "0043_new_ct_tri-here").write_text("", encoding="utf-8")
        env = dict(os.environ, ID="hf_example", ROUTE="hf-token", ARGS="--repo a/b --include *0043_new_ct_tri*",
                   TOKEN_FILE=str(token), ACQ_ENV=str(tmp / "acq"), SSN=str(tmp / "ssn"),
                   DATA_ROOT=str(tmp / "data"), TMPDIR_OVERRIDE=str(tmp / "tmp"), SCHWINGNET=str(ROOT),
                   FAKE_FILES=str(files))
        done = subprocess.run(["bash", str(GRID / "platform-fetch.sbatch")], cwd=work, env=env,
                              capture_output=True, text=True, timeout=60)
        return done.returncode, done.stdout + done.stderr

    def test_a_fetch_that_verified_no_file_fails_by_name_and_status_shows_why(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_job(Path(tmp), files=0)
        self.assertEqual(code, 3, out)
        self.assertIn("arg: *0043_new_ct_tri*", out)
        self.assertIn("DP_FETCH_RC=3", out)
        # what the gate word status keeps of the log (grid/gate.sh)
        shown = subprocess.run(["awk", "-f", str(GRID / "shape-words.awk"), "-f", str(GRID / "log-shapes.awk")],
                               input=out, capture_output=True, text=True, timeout=60).stdout
        self.assertIn("hf_example: nothing fetched; the include pattern matched no file at ", shown)

    def test_a_fetch_that_verified_files_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_job(Path(tmp), files=2)
        self.assertEqual(code, 0, out)
        self.assertIn("arg: *0043_new_ct_tri*", out)
        self.assertIn("DP_FETCH_RC=0", out)
        self.assertNotIn("nothing fetched", out)
