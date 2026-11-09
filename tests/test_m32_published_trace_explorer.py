"""Compare M32 Trace Explorer results with the published JSON records."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from artifact_auditor.m32_published_boundary_intake import (
    M32_SOURCE_COMMIT,
    validate_m32_published_boundary,
)
from trace_explorer.m32_published_trace_explorer import explore_m32_trace


BUNDLE_PATH = "artifacts/m32/exports/m32-deterministic-rtl-trace-bundle.json"
CLI = "trace_explorer.m32_published_trace_explorer"
SIZES = {"7/1": (16, 192), "1/7": (17, 204)}


class PublishedExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get("FRP_M32_UPSTREAM_ROOT")
        if not root:
            raise unittest.SkipTest("Requires the M32 publication tree")
        cls.boundary = validate_m32_published_boundary(Path(root))
        raw = (Path(root) / BUNDLE_PATH).read_bytes()
        cls.digest = hashlib.sha256(raw).hexdigest()
        cls.traces = {t["scheduler_mode"]: t["records"] for t in json.loads(raw)["traces"]}

    def check_view(self, view, mode, ticks, count):
        self.assertEqual(view["scheduler_mode"], mode)
        self.assertEqual(view["source_commit"], M32_SOURCE_COMMIT)
        self.assertEqual(view["bundle_sha256"], self.digest)
        self.assertEqual(view["selected_tick_count"], len(ticks))
        self.assertEqual(view["selected_record_count"], count)
        self.assertEqual(json.dumps(view["ticks"], default=dict, sort_keys=True),
                         json.dumps(ticks, sort_keys=True))

    def test_whole_modes_preserve_all_record_fields_and_order(self):
        self.assertEqual(set(self.traces), set(SIZES))
        for mode, (tick_count, record_count) in SIZES.items():
            with self.subTest(mode=mode):
                ticks = self.traces[mode]
                self.assertEqual([t["source_tick"] for t in ticks], list(range(tick_count)))
                self.check_view(explore_m32_trace(self.boundary, mode), mode, ticks, record_count)

    def test_every_tick_matches_its_own_mode_and_coordinate(self):
        for mode, ticks in self.traces.items():
            for tick in ticks:
                coordinate = tick["source_tick"]
                with self.subTest(mode=mode, source_tick=coordinate):
                    view = explore_m32_trace(self.boundary, mode, coordinate)
                    self.check_view(view, mode, [tick], 12)

    def test_invalid_coordinates_are_rejected(self):
        for mode, tick in (("7/1", 16), ("1/7", 17), ("7/1", -1),
                           ("1/7", False), ("1/7", 1.0), ("7/1", "0"), ("invalid", 0)):
            with self.subTest(mode=mode, source_tick=tick):
                with self.assertRaises(ValueError):
                    explore_m32_trace(self.boundary, mode, tick)

    def run_cli(self, mode, *args):
        repo = os.environ.get("FRP_M31_UPSTREAM_ROOT")
        commit = os.environ.get("FRP_PUBLICATION")
        if not repo or not commit:
            self.skipTest("Requires the FRP Git checkout and publication commit")
        return subprocess.run([
            sys.executable, "-m", CLI, "--upstream-root", repo,
            "--publication-commit", commit, "--scheduler-mode", mode, *args,
        ], capture_output=True, text=True, check=False)

    def test_cli_full_mode_and_last_tick_preserve_provenance(self):
        for mode, (size, count) in SIZES.items():
            ticks = self.traces[mode]
            for args, expected, records in (
                ((), ticks, count),
                (("--source-tick", str(size - 1)), ticks[-1:], 12),
            ):
                with self.subTest(mode=mode, args=args):
                    run = self.run_cli(mode, *args)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    view = json.loads(run.stdout)
                    self.assertEqual(view["publication_commit"], os.environ["FRP_PUBLICATION"])
                    self.check_view(view, mode, expected, records)

    def test_cli_reports_absent_tick_without_emitting_a_trace(self):
        run = self.run_cli("7/1", "--source-tick", "16")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(run.stdout, "")
        self.assertIn("No source tick 16 in mode 7/1", run.stderr)


if __name__ == "__main__":
    unittest.main()
