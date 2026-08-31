"""End-to-end qualification for the complete read-only FRP M31 route."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from artifact_auditor.audit_report import ValidationStatus
from artifact_auditor.m31_published_auditor import (
    audit_m31_published_documents,
)
from artifact_auditor.m31_published_boundary_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M31_PUBLISHED_DOCUMENT_IDENTITIES,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedDocumentRole,
)
from schemas.registry import ObservatoryMode
from trace_explorer.m31_published_trace_explorer import (
    build_m31_published_trace_dataset,
    explore_m31_published_documents,
)
from transition_visualizer.m31_published_transition_visualizer import (
    build_m31_published_transition_visualizer,
    visualize_m31_published_documents,
)


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
_LATER_LOADED_AT = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)

_REPORT_SHA256 = (
    "5f18fd174e02f19adcac1809624a2c205b94ae6c226e05a20eaac4f896c6bb36",
    "e7c6163954973aa60994d2fa76f6f7edfdc6429fcbb397cf7e403a4e64f2f130",
    "e0ef32073524cd41ea2cf0b7b273ef3c63c61080e5ff72ae9e5432a81609d652",
    "5374a6b6e0def38ae5a50bb216c9be0396f6139f4a07e982b47e86b719414b53",
)
_BATCH_SHA256 = (
    "3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591"
)
_TRACE_DATASET_ID = "0f0f0f7e-0409-5e7b-8c76-2f72bb954321"
_TRACE_DATASET_SHA256 = (
    "ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff"
)
_VISUALIZER_DATASET_ID = "63a1feb9-1835-579e-ab00-eec4569e8ff3"
_VISUALIZER_DATASET_SHA256 = (
    "0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304"
)
_TRACE_DISPATCH_SHA256 = (
    "f34b867fabcaab51515ecca39f2eb7287f52aa218d3ac48596a1481326009630"
)
_VISUALIZER_DISPATCH_SHA256 = (
    "ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8"
)
_TRANSITION_COUNTS = (
    ("active_zero_to_polarity", 12),
    ("direct_opposite", 0),
    ("polarity_to_active_zero", 5),
    ("retained_same", 783),
)
_ROUTE_COUNTS = (
    ("non_route_transition", 790),
    ("first_leg_to_active_zero", 5),
    ("pending_route_completion", 5),
)
_THERMAL_CONTOURS = (
    (
        "historical_release_benchmark",
        "historical",
        "8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140",
    ),
    (
        "current_comparative_baseline",
        "current",
        "c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add",
    ),
    (
        "current_hardware_sensitivity",
        "current",
        "9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0",
    ),
    (
        "current_thermal_profile",
        "current",
        "1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee",
    ),
)
_PUBLICATION_CONTRACT = (
    ("direction", "upstream_published_bytes_to_downstream"),
    ("downstream_metric_normalization", "forbidden"),
    ("downstream_repository", "FRP-Trace-Observatory"),
    ("downstream_role", "read_only_validation_and_visualization"),
    ("downstream_semantic_reimplementation", "forbidden"),
    ("downstream_source_mutation", "forbidden"),
    ("downstream_writeback", "forbidden"),
    ("m29_boundary_confirmed", True),
    ("published_contours_must_remain_separate", True),
    ("upstream_repository", "FRP"),
)


def _git_status(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(completed.stdout.splitlines())


def _source_snapshot(root: Path, paths: tuple[str, ...]):
    return tuple(
        (
            relative,
            len((root / relative).read_bytes()),
            hashlib.sha256((root / relative).read_bytes()).hexdigest(),
        )
        for relative in paths
    )


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM31PublishedObservatoryEndToEndTests(unittest.TestCase):
    """Close the exact M31 boundary through every Observatory consumer."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        if _git_status(cls.upstream_root):
            raise AssertionError("FRP upstream must begin clean")

        cls.audit_batch = audit_m31_published_documents(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        cls.trace_dataset = build_m31_published_trace_dataset(
            cls.audit_batch
        )
        cls.visualizer_dataset = build_m31_published_transition_visualizer(
            cls.audit_batch
        )
        cls.boundary = (
            cls.audit_batch.dispatch_batch.registry_validation.boundary
        )
        cls.source_paths = tuple(
            dict.fromkeys(
                tuple(
                    identity.source_path
                    for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
                )
                + tuple(
                    source.source_artifact.source_path
                    for source in cls.boundary.provenance_sources
                )
            )
        )
        cls.source_snapshot = _source_snapshot(
            cls.upstream_root,
            cls.source_paths,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if _source_snapshot(cls.upstream_root, cls.source_paths) != (
            cls.source_snapshot
        ):
            raise AssertionError("FRP source bytes changed during qualification")
        if _git_status(cls.upstream_root):
            raise AssertionError("FRP upstream changed during qualification")

    def test_boundary_retains_exact_publication_inventory(self) -> None:
        self.assertEqual(
            self.boundary.registry_revision,
            M31_PUBLISHED_REGISTRY_REVISION,
        )
        self.assertEqual(self.boundary.loaded_at, _EXACT_LOADED_AT)
        self.assertEqual(len(self.boundary.documents), 4)
        self.assertEqual(len(self.boundary.provenance_sources), 12)
        self.assertEqual(self.boundary.m30_archive_member_count, 10)
        self.assertEqual(
            self.boundary.m30_archive_sha256,
            FRP_M30_ARCHIVE_SHA256,
        )

    def test_registry_exposes_only_the_six_exact_mode_routes(self) -> None:
        registry = self.audit_batch.dispatch_batch.registry_validation
        routes = tuple(
            (route.registration.role, route.mode)
            for route in registry.routes
        )
        self.assertEqual(
            routes,
            (
                (
                    M31PublishedDocumentRole.FORMAL_SCHEMA,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    M31PublishedDocumentRole.EVIDENCE,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    M31PublishedDocumentRole.EVIDENCE,
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ),
                (
                    M31PublishedDocumentRole.EVIDENCE,
                    ObservatoryMode.TRACE_EXPLORER,
                ),
                (
                    M31PublishedDocumentRole.MANIFEST,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    M31PublishedDocumentRole.QUALIFICATION,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
            ),
        )
        self.assertEqual(registry.artifact_auditor_route_count, 4)
        self.assertEqual(registry.trace_explorer_route_count, 1)
        self.assertEqual(
            registry.ternary_transition_visualizer_route_count,
            1,
        )

    def test_dispatch_batch_binds_every_route_once(self) -> None:
        dispatch_batch = self.audit_batch.dispatch_batch
        self.assertEqual(dispatch_batch.published_document_count, 4)
        self.assertEqual(dispatch_batch.total_dispatch_count, 6)
        self.assertEqual(
            len(
                dispatch_batch.dispatches_for_mode(
                    ObservatoryMode.ARTIFACT_AUDITOR
                )
            ),
            4,
        )
        self.assertEqual(
            dispatch_batch.dispatch_for(
                M31PublishedDocumentRole.EVIDENCE,
                ObservatoryMode.TRACE_EXPLORER,
            ).dispatch_sha256,
            _TRACE_DISPATCH_SHA256,
        )
        self.assertEqual(
            dispatch_batch.dispatch_for(
                M31PublishedDocumentRole.EVIDENCE,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ).dispatch_sha256,
            _VISUALIZER_DISPATCH_SHA256,
        )

    def test_artifact_auditor_closes_all_four_documents(self) -> None:
        self.assertIs(
            self.audit_batch.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(self.audit_batch.failed_check_count, 0)
        self.assertEqual(self.audit_batch.total_check_count, 47)
        self.assertEqual(len(self.audit_batch.reports), 4)
        self.assertEqual(
            tuple(report.role for report in self.audit_batch.reports),
            tuple(M31PublishedDocumentRole),
        )

    def test_auditor_digest_chain_is_exact(self) -> None:
        self.assertEqual(self.audit_batch.batch_sha256, _BATCH_SHA256)
        self.assertEqual(
            tuple(report.report_sha256 for report in self.audit_batch.reports),
            _REPORT_SHA256,
        )

    def test_trace_explorer_closes_both_execution_contours(self) -> None:
        trace = self.trace_dataset
        self.assertEqual(trace.trace_dataset_id, _TRACE_DATASET_ID)
        self.assertEqual(trace.dataset_sha256, _TRACE_DATASET_SHA256)
        self.assertEqual(trace.trace_contour_count, 2)
        self.assertEqual(trace.record_count, 100)
        self.assertEqual(trace.cell_snapshot_count, 800)
        self.assertEqual(trace.request_count, 200)
        self.assertEqual(trace.invariant_pass_record_count, 100)

    def test_transition_visualizer_closes_all_source_cells(self) -> None:
        visualizer = self.visualizer_dataset
        self.assertEqual(
            visualizer.visualizer_dataset_id,
            _VISUALIZER_DATASET_ID,
        )
        self.assertEqual(
            visualizer.dataset_sha256,
            _VISUALIZER_DATASET_SHA256,
        )
        self.assertEqual(visualizer.transition_frame_count, 800)
        self.assertEqual(visualizer.thermal_contour_count, 4)

    def test_all_consumers_share_one_exact_audit_batch(self) -> None:
        self.assertIs(self.trace_dataset.audit_batch, self.audit_batch)
        self.assertIs(self.visualizer_dataset.audit_batch, self.audit_batch)
        self.assertIs(
            self.visualizer_dataset.trace_dataset.audit_batch,
            self.audit_batch,
        )
        self.assertIs(
            self.trace_dataset.audit_report,
            self.audit_batch.report_for_role(
                M31PublishedDocumentRole.EVIDENCE
            ),
        )
        self.assertIs(
            self.visualizer_dataset.audit_report,
            self.trace_dataset.audit_report,
        )

    def test_all_three_mode_dispatches_share_exact_evidence_bytes(self) -> None:
        dispatch_batch = self.audit_batch.dispatch_batch
        evidence_dispatches = tuple(
            dispatch_batch.dispatch_for(
                M31PublishedDocumentRole.EVIDENCE,
                mode,
            )
            for mode in (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            )
        )
        evidence_document = evidence_dispatches[0].document
        self.assertTrue(
            all(
                dispatch.document is evidence_document
                for dispatch in evidence_dispatches
            )
        )
        self.assertEqual(
            {
                dispatch.document.identity.raw_sha256
                for dispatch in evidence_dispatches
            },
            {
                "bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42"
            },
        )

    def test_visualizer_trace_projection_is_digest_identical(self) -> None:
        embedded = self.visualizer_dataset.trace_dataset
        self.assertEqual(embedded, self.trace_dataset)
        self.assertEqual(embedded.trace_dataset_id, _TRACE_DATASET_ID)
        self.assertEqual(embedded.dataset_sha256, _TRACE_DATASET_SHA256)
        self.assertEqual(
            tuple(contour.contour_sha256 for contour in embedded.contours),
            tuple(
                contour.contour_sha256
                for contour in self.trace_dataset.contours
            ),
        )

    def test_every_visualizer_frame_binds_one_exact_trace_cell(self) -> None:
        expected = []
        for contour in self.trace_dataset.contours:
            for record in contour.records:
                for cell in record.cells:
                    expected.append(
                        (
                            contour.trace_contour_id,
                            contour.contour_sha256,
                            record.trace_record_id,
                            record.source_record_sha256,
                            record.sequence,
                            cell.cell_id,
                            cell.phase_derived_target,
                            cell.retained_state_before,
                            cell.retained_state_after,
                            cell.pending_route_before,
                            cell.pending_route_after,
                            cell.accepted,
                            cell.accepted_change,
                            cell.neutral_routed,
                        )
                    )
        observed = [
            (
                frame.trace_contour_id,
                frame.trace_contour_sha256,
                frame.trace_record_id,
                frame.source_record_sha256,
                frame.sequence,
                frame.cell_id,
                frame.phase_derived_target,
                frame.retained_state_before,
                frame.retained_state_after,
                frame.pending_route_before,
                frame.pending_route_after,
                frame.accepted,
                frame.accepted_change,
                frame.neutral_routed,
            )
            for frame in self.visualizer_dataset.transition_frames
        ]
        self.assertEqual(observed, expected)

    def test_every_frame_retains_exact_source_coordinates(self) -> None:
        for frame in self.visualizer_dataset.transition_frames:
            with self.subTest(frame=frame.transition_frame_id):
                self.assertEqual(
                    frame.source_location.package_member,
                    frame.source_path,
                )
                self.assertEqual(
                    frame.source_location.source_record_ordinal,
                    frame.sequence + 1,
                )
                self.assertEqual(
                    frame.source_location.json_path,
                    f"$.records[{frame.sequence}].retained_state_after[{frame.cell_id}]",
                )

    def test_transition_counts_agree_across_all_layers(self) -> None:
        self.assertEqual(
            self.trace_dataset.retained_transition_totals,
            _TRANSITION_COUNTS,
        )
        self.assertEqual(
            self.visualizer_dataset.transition_classification_counts,
            _TRANSITION_COUNTS,
        )
        observed = Counter(
            frame.transition_classification
            for frame in self.visualizer_dataset.transition_frames
        )
        self.assertEqual(
            tuple((name, observed[name]) for name, _ in _TRANSITION_COUNTS),
            _TRANSITION_COUNTS,
        )

    def test_opposite_polarities_use_only_active_zero_routes(self) -> None:
        self.assertEqual(
            self.visualizer_dataset.core_declaration.opposite_transition_routes,
            ((-1, 0, 1), (1, 0, -1)),
        )
        self.assertEqual(
            self.visualizer_dataset.route_leg_counts,
            _ROUTE_COUNTS,
        )
        self.assertFalse(
            any(
                frame.retained_state_before == -frame.retained_state_after
                and frame.retained_state_before != 0
                for frame in self.visualizer_dataset.transition_frames
            )
        )

    def test_balanced_ternary_domain_and_active_zero_are_exact(self) -> None:
        core = self.visualizer_dataset.core_declaration
        self.assertEqual(self.trace_dataset.observed_ternary_domain, (-1, 0, 1))
        self.assertEqual(core.balanced_ternary_notation, "-1/0/1")
        self.assertEqual(core.semantic_values, (-1, 0, 1))
        self.assertEqual(core.active_neutral_state, 0)
        self.assertEqual(core.zero_role, "active_computational_state")
        self.assertFalse(core.classical_bit_addition_primary_mechanism)

    def test_active_zero_evidence_agrees_across_views(self) -> None:
        self.assertEqual(
            self.trace_dataset.active_zero_after_observation_count,
            702,
        )
        self.assertEqual(
            self.visualizer_dataset.active_zero_after_observation_count,
            702,
        )
        self.assertEqual(
            self.visualizer_dataset.active_zero_roles,
            self.trace_dataset.active_zero_roles,
        )
        self.assertEqual(len(self.trace_dataset.active_zero_roles), 9)

    def test_temporal_scheduler_modes_remain_exact(self) -> None:
        self.assertEqual(
            self.visualizer_dataset.core_declaration.temporal_scheduler_modes,
            ("1/7", "7/1"),
        )
        self.assertEqual(
            self.trace_dataset.observed_scheduler_modes,
            ("free", "7/1", "1/7"),
        )
        self.assertEqual(
            self.trace_dataset.scheduler_mode_counts,
            (("free", 19), ("7/1", 64), ("1/7", 17)),
        )

    def test_four_thermal_contours_remain_separate(self) -> None:
        observed = tuple(
            (
                contour.contour_name,
                contour.contour_group,
                contour.payload_sha256,
            )
            for contour in self.visualizer_dataset.thermal_contours
        )
        self.assertEqual(observed, _THERMAL_CONTOURS)
        self.assertEqual(
            Counter(contour.contour_group for contour in self.visualizer_dataset.thermal_contours),
            Counter({"historical": 1, "current": 3}),
        )

    def test_no_thermal_panel_claims_physical_temperature(self) -> None:
        self.assertEqual(
            self.visualizer_dataset.physical_temperature_measurement_count,
            0,
        )
        self.assertTrue(
            all(
                not contour.physical_temperature_measurement
                for contour in self.visualizer_dataset.thermal_contours
            )
        )
        self.assertIn(
            ("thermal_proxy_is_not_physical_temperature", True),
            self.visualizer_dataset.evidence_boundaries,
        )

    def test_one_way_publication_contract_is_retained_exactly(self) -> None:
        self.assertEqual(
            self.visualizer_dataset.publication_contract,
            _PUBLICATION_CONTRACT,
        )
        contract = dict(self.visualizer_dataset.publication_contract)
        self.assertEqual(contract["downstream_metric_normalization"], "forbidden")
        self.assertEqual(contract["downstream_semantic_reimplementation"], "forbidden")
        self.assertEqual(contract["downstream_source_mutation"], "forbidden")
        self.assertEqual(contract["downstream_writeback"], "forbidden")

    def test_fresh_trace_entrypoint_is_identity_deterministic(self) -> None:
        fresh = explore_m31_published_documents(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        self.assertEqual(fresh.trace_dataset_id, _TRACE_DATASET_ID)
        self.assertEqual(fresh.dataset_sha256, _TRACE_DATASET_SHA256)
        self.assertEqual(
            tuple(
                (
                    contour.trace_contour_id,
                    contour.contour_sha256,
                    contour.source_record_digest,
                    tuple(
                        record.source_record_sha256
                        for record in contour.records
                    ),
                )
                for contour in fresh.contours
            ),
            tuple(
                (
                    contour.trace_contour_id,
                    contour.contour_sha256,
                    contour.source_record_digest,
                    tuple(
                        record.source_record_sha256
                        for record in contour.records
                    ),
                )
                for contour in self.trace_dataset.contours
            ),
        )

    def test_fresh_visualizer_entrypoint_is_identity_deterministic(self) -> None:
        fresh = visualize_m31_published_documents(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        self.assertEqual(
            fresh.visualizer_dataset_id,
            _VISUALIZER_DATASET_ID,
        )
        self.assertEqual(fresh.dataset_sha256, _VISUALIZER_DATASET_SHA256)
        self.assertEqual(
            tuple(frame.frame_sha256 for frame in fresh.transition_frames),
            tuple(
                frame.frame_sha256
                for frame in self.visualizer_dataset.transition_frames
            ),
        )

    def test_load_timestamp_does_not_change_evidence_identities(self) -> None:
        later_audit = audit_m31_published_documents(
            self.upstream_root,
            loaded_at=_LATER_LOADED_AT,
        )
        later_trace = build_m31_published_trace_dataset(later_audit)
        later_visualizer = build_m31_published_transition_visualizer(
            later_audit
        )
        self.assertEqual(later_audit.batch_sha256, _BATCH_SHA256)
        self.assertEqual(later_trace.dataset_sha256, _TRACE_DATASET_SHA256)
        self.assertEqual(
            later_visualizer.dataset_sha256,
            _VISUALIZER_DATASET_SHA256,
        )
        self.assertEqual(
            later_audit.dispatch_batch.registry_validation.boundary.loaded_at,
            _LATER_LOADED_AT,
        )

    def test_public_cli_chain_reports_all_three_modes_green(self) -> None:
        checks = (
            (
                "artifact_auditor.m31_published_auditor",
                "FRP Observatory M31 published Artifact Auditor: PASS",
                ("audit_reports=4", "validation_checks=47", "failed_checks=0"),
            ),
            (
                "trace_explorer.m31_published_trace_explorer",
                "FRP Observatory M31 published Trace Explorer: PASS",
                ("trace_contours=2", "records=100", "cell_snapshots=800"),
            ),
            (
                "transition_visualizer.m31_published_transition_visualizer",
                "FRP Observatory M31 published Transition Visualizer: PASS",
                (
                    "transition_frames=800",
                    "thermal_contours=4",
                    "balanced_ternary_notation=-1/0/1",
                ),
            ),
        )
        for module, heading, expected_lines in checks:
            with self.subTest(module=module):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        module,
                        "--upstream-root",
                        str(self.upstream_root),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                output = completed.stdout.splitlines()
                self.assertIn(heading, output)
                for expected in expected_lines:
                    self.assertIn(expected, output)
                for boundary in (
                    "source_execution=forbidden",
                    "metric_normalization=forbidden",
                    "semantic_reimplementation=forbidden",
                    "source_mutation=forbidden",
                    "downstream_writeback=forbidden",
                ):
                    self.assertIn(boundary, output)

    def test_all_upstream_publication_bytes_remain_exact(self) -> None:
        self.assertEqual(
            _source_snapshot(self.upstream_root, self.source_paths),
            self.source_snapshot,
        )

    def test_upstream_repository_remains_clean(self) -> None:
        self.assertEqual(_git_status(self.upstream_root), ())


if __name__ == "__main__":
    unittest.main()
