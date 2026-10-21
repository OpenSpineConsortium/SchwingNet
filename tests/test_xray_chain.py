"""The X-ray fetch chain under grid/: the fetch list is read and planned without the network, a
run is refused on the login node, a synthetic raw folder becomes a bank in the builders' format,
every Slurm script parses, and the submit scripts print three dependent submissions in a dry run.
Standard library only, so the required check runs it; the ingest round trip of a bank, which
needs pydantic, is tests/schwingnet/test_bank.py."""

import importlib.util
import io
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
        self.assertIn("zenodo-get --record 8115942", out)
        self.assertIn("fallback: ", out)
        self.assertIn("<login from ~/.netrc>", out)
        self.assertIn("dry run:", out)
        code, out, _ = run_tool(tool, ["--only", "lumos,fracatlas"])
        self.assertEqual(out.count("== "), 2)
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
            self.assertIn("pydicom", err)

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
        for name in SBATCH_FILES:
            text = (GRID / name).read_text(encoding="utf-8")
            for line in ("#SBATCH --partition=reqp", "#SBATCH --qos=requeue", "#SBATCH --requeue",
                         "#SBATCH --cpus-per-task=8", "#SBATCH --mem=24G", "#SBATCH --output=logs/"):
                self.assertIn(line, text, name)

    def dry_run(self, script, *args, free="5000G"):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            df = Path(tmp) / "df"
            df.write_text(f"#!/bin/bash\necho Avail\necho {free}\n", encoding="utf-8")
            df.chmod(0o755)
            env = dict(os.environ, SCHWINGNET=str(ROOT), SBATCH="echo", DF=str(df))
            done = subprocess.run(["bash", str(GRID / script), *args], env=env, capture_output=True, text=True,
                                  timeout=60)
            Path(ROOT / "grid" / "LAST_RUN.txt").unlink(missing_ok=True)
        return done.returncode, done.stdout + done.stderr

    def test_the_chain_submits_three_dependent_jobs_in_a_dry_run(self):
        code, out = self.dry_run("run-xray-chain.sh", "--only", "lumos,fracatlas")
        self.assertEqual(code, 0, out)
        self.assertIn("would submit: sbatch --parsable -D", out)
        self.assertIn("01-fetch.sbatch", out)
        self.assertIn("--dependency=afterany:DRY1 --export=ALL", out)
        self.assertIn("--dependency=afterany:DRY2 --export=ALL", out)
        self.assertIn("size budget: 2 entries, 46 GB stated", out)
        self.assertIn("no size stated for: fracatlas", out)
        self.assertIn("ETA:", out)
        code, out = self.dry_run("run-xray-chain.sh", free="1030G")
        self.assertEqual(code, 3)
        self.assertIn("refusing to submit", out)

    def test_the_platform_chain_keeps_ct_rate_and_nlst_apart(self):
        code, out = self.dry_run("run-platform-fetch.sh")
        self.assertEqual(code, 0, out)
        self.assertIn("aws_stoic2021: job DRY1", out)
        self.assertIn("--dependency=afterany:DRY1", out)
        self.assertNotIn("ID=hf_ct_rate ROUTE=hf-token", out.split("Not submitted")[0])
        self.assertIn("ID=hf_ct_rate", out.split("Not submitted")[1])
        self.assertIn("ID=idc_nlst", out.split("Not submitted")[1])
        self.assertNotIn("rsna_rspect_pe: job", out)
        code, out = self.dry_run("run-platform-fetch.sh", "--gated")
        self.assertIn("rsna_rspect_pe: job", out)


if __name__ == "__main__":
    unittest.main()
