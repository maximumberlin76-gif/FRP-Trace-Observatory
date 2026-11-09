"""Verify M32 cell timelines against the pinned FRP publication."""

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
from transition_visualizer.m32_published_transition_visualizer import cell_timeline


BUNDLE = "artifacts/m32/exports/m32-deterministic-rtl-trace-bundle.json"
FIELDS = (
    "source_tick", "retained_state_value", "state_changed", "active_zero",
    "pending_active", "pending_target_value", "first_route_leg", "second_route_leg",
)


class PublishedTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get("FRP_M32_UPSTREAM_ROOT")
        if not root:
            raise unittest.SkipTest("Requires the M32 publication tree")
        cls.boundary = validate_m32_published_boundary(Path(root))
        raw = (Path(root) / BUNDLE).read_bytes()
        cls.digest = hashlib.sha256(raw).hexdigest()
        cls.traces = json.loads(raw)["traces"]

    def test_all_timelines_match_the_published_cells(self):
        for trace in self.traces:
            mode = trace["scheduler_mode"]
            expected = {}
            for tick in trace["records"]:
                for cell in tick["cells"]:
                    rows = expected.setdefault(cell["source_cell"], [])
                    row = {key: cell[key] for key in FIELDS}
                    row["previous_retained_state"] = rows[-1]["retained_state_value"] if rows else None
                    rows.append(row)

            for index, rows in expected.items():
                with self.subTest(mode=mode, cell=index):
                    view = cell_timeline(self.boundary, mode, index)
                    self.assertEqual(view["source_commit"], M32_SOURCE_COMMIT)
                    self.assertEqual(view["bundle_sha256"], self.digest)
                    self.assertEqual(view["scheduler_mode"], mode)
                    self.assertEqual(view["source_cell"], index)
                    self.assertEqual(json.dumps(view["timeline"], sort_keys=True),
                                     json.dumps(rows, sort_keys=True))

    def test_opposite_request_waits_at_active_zero_until_second_leg(self):
        for mode, first, second in (("7/1", 9, 15), ("1/7", 10, 16)):
            with self.subTest(mode=mode):
                rows = cell_timeline(self.boundary, mode, 0)["timeline"]
                by_tick = {row["source_tick"]: row for row in rows}
                self.assertEqual([r["source_tick"] for r in rows if r["first_route_leg"]], [first])
                self.assertEqual([r["source_tick"] for r in rows if r["second_route_leg"]], [second])
                self.assertEqual(by_tick[first]["previous_retained_state"], 1)
                for tick in range(first, second):
                    row = by_tick[tick]
                    self.assertEqual(row["retained_state_value"], 0)
                    self.assertTrue(row["active_zero"])
                    self.assertTrue(row["pending_active"])
                    self.assertEqual(row["pending_target_value"], -1)
                end = by_tick[second]
                self.assertEqual((end["previous_retained_state"], end["retained_state_value"]), (0, -1))
                self.assertFalse(end["pending_active"])

    def test_invalid_cell_or_mode_is_rejected(self):
        for mode, cell in (("7/1", -1), ("1/7", 8), ("7/1", True),
                           ("1/7", 0.0), ("7/1", "0"), ("invalid", 0)):
            with self.subTest(mode=mode, cell=cell):
                with self.assertRaises(ValueError):
                    cell_timeline(self.boundary, mode, cell)

    def test_cli_exports_selected_cell_and_rejects_absent_cell(self):
        repo = os.environ.get("FRP_M31_UPSTREAM_ROOT")
        sha = os.environ.get("FRP_PUBLICATION")
        if not repo or not sha:
            self.skipTest("Requires the FRP checkout and publication commit")
        command = [
            sys.executable, "-m", "transition_visualizer.m32_published_transition_visualizer",
            "--upstream-root", repo, "--publication-commit", sha,
        ]
        for mode, cell in (("7/1", 0), ("1/7", 7)):
            with self.subTest(mode=mode, cell=cell):
                output = subprocess.check_output(
                    command + ["--scheduler-mode", mode, "--source-cell", str(cell)], text=True
                )
                expected = cell_timeline(self.boundary, mode, cell)
                self.assertEqual(json.loads(output), {**expected, "publication_commit": sha})

        failed = subprocess.run(command + ["--scheduler-mode", "1/7", "--source-cell", "8"],
                                capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(failed.stdout, "")
        self.assertIn("Cell 8 absent", failed.stderr)


if __name__ == "__main__":
    unittest.main()
