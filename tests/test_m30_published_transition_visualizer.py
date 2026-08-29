"""Tests for the exact read-only M30 full-core Transition Visualizer."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m30_archive_intake import M30ArchiveIntakeError
from artifact_auditor.m30_published_auditor import (
    audit_m30_published_archive,
)
from schemas.registry import ObservatoryMode
from transition_visualizer.m30_published_transition_visualizer import (
    M30FullCoreTraceEvidence,
    M30PublishedVisualizerError,
    PublishedCoreTraceSource,
    PublishedTransitionFrame,
    build_m30_published_transition_visualizer,
    load_m30_full_core_trace_evidence,
    visualize_m30_published_archive,
)


_ARCHIVE_ENVIRONMENT_VARIABLE = "FRP_M30_ARCHIVE_PATH"


def _plain_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json_value(member)
            for key, member in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_plain_json_value(member) for member in value]
    return value


class PublishedTransitionVisualizerGuardTests(unittest.TestCase):
    """Exercise the explicit M6 plus full-core M8 type boundary."""

    def test_builder_requires_exact_m6_batch_type(self) -> None:
        for value in (None, "batch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M30PublishedVisualizerError,
                    "audit_batch must be PublishedAuditBatch",
                ):
                    build_m30_published_transition_visualizer(value, None)

    def test_builder_requires_exact_full_core_evidence_type(self) -> None:
        class PassingBatch:
            overall_status = ValidationStatus.RECOGNIZED_VALID

        with self.assertRaisesRegex(
            M30PublishedVisualizerError,
            "audit_batch must be PublishedAuditBatch",
        ):
            build_m30_published_transition_visualizer(
                PassingBatch(),  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
            )

    def test_loader_rejects_non_m30_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "not-m30.tar.gz")
            path.write_bytes(b"not an FRP archive")
            with self.assertRaises(M30ArchiveIntakeError):
                load_m30_full_core_trace_evidence(path)


@unittest.skipUnless(
    os.environ.get(_ARCHIVE_ENVIRONMENT_VARIABLE),
    f"{_ARCHIVE_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM30PublishedTransitionVisualizerIntegrationTests(unittest.TestCase):
    """Exercise the complete two-trace M8 projection."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.archive_path = Path(
            os.environ[_ARCHIVE_ENVIRONMENT_VARIABLE]
        )
        cls.audit_batch = audit_m30_published_archive(cls.archive_path)
        cls.evidence = load_m30_full_core_trace_evidence(cls.archive_path)
        cls.dataset = build_m30_published_transition_visualizer(
            cls.audit_batch,
            cls.evidence,
        )

    def test_complete_chain_is_green(self) -> None:
        self.assertIs(
            self.dataset.audit_batch.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(self.dataset.audit_batch.failed_check_count, 0)
        self.assertEqual(
            self.evidence.archive_validation.archive_sha256,
            "05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa",
        )

    def test_full_core_evidence_identity_is_deterministic(self) -> None:
        self.assertEqual(
            self.evidence.evidence_id,
            "7c935011-c734-5f6b-b312-dc476ad99724",
        )
        self.assertEqual(
            self.evidence.evidence_sha256,
            "b481d787fdef17992ed3236b4a7b1b142634b944ebb0048f4b77d3def089edd2",
        )

    def test_retained_member_inventory_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                retained.member.path
                for retained in self.evidence.archive_validation.retained_members
            ),
            (
                "artifacts/m19/execution/m16-fpga-preparation-execution-trace.json",
                "artifacts/m19/execution/m16-rtl-execution-trace.json",
                "artifacts/m28/exports/m28-observatory-canonical-trace-bundle.json",
                "artifacts/m28/fixtures/m28-observatory-fixture-manifest.json",
            ),
        )

    def test_two_measurement_contours_remain_separate(self) -> None:
        self.assertEqual(
            tuple(source.dataset_id for source in self.evidence.trace_sources),
            (
                "m16-rtl-execution",
                "m16-fpga-preparation-execution",
            ),
        )
        self.assertEqual(
            tuple(
                source.measurement_contour
                for source in self.evidence.trace_sources
            ),
            (
                "m16_rtl_execution",
                "m16_fpga_preparation_execution",
            ),
        )
        self.assertEqual(
            len(
                {
                    source.measurement_contour
                    for source in self.evidence.trace_sources
                }
            ),
            2,
        )

    def test_direct_trace_raw_identities_are_exact(self) -> None:
        self.assertEqual(
            tuple(
                (
                    source.source_path,
                    source.retained_member.member.byte_length,
                    source.raw_sha256,
                )
                for source in self.evidence.trace_sources
            ),
            (
                (
                    "artifacts/m19/execution/m16-rtl-execution-trace.json",
                    152109,
                    "d7945e0d2b5aaa05c5fff2e4e60d3b984017f7e4ae1984c55920368a110020bd",
                ),
                (
                    "artifacts/m19/execution/m16-fpga-preparation-execution-trace.json",
                    9013,
                    "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f",
                ),
            ),
        )

    def test_trace_source_identifiers_are_dataset_specific(self) -> None:
        self.assertEqual(
            tuple(
                source.trace_source_id
                for source in self.evidence.trace_sources
            ),
            (
                "4a80e8e1-55cf-5010-b9ed-d3fa559f1549",
                "166d7316-cd41-5289-b70a-e3af5ec37415",
            ),
        )

    def test_complete_record_and_frame_inventory_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                len(source.records)
                for source in self.evidence.trace_sources
            ),
            (96, 4),
        )
        self.assertEqual(self.dataset.trace_record_count, 100)
        self.assertEqual(len(self.dataset.transition_frames), 800)
        self.assertEqual(len(self.dataset.telemetry_semantics), 6)

    def test_execution_epoch_declarations_are_exact(self) -> None:
        self.assertEqual(
            tuple(
                tuple(epoch.source_payload() for epoch in source.epochs)
                for source in self.evidence.trace_sources
            ),
            (
                (
                    {"epoch": 0, "mode": "free", "record_count": 16},
                    {"epoch": 1, "mode": "7/1", "record_count": 64},
                    {"epoch": 2, "mode": "1/7", "record_count": 16},
                ),
                (
                    {"epoch": 0, "mode": "free", "record_count": 3},
                    {"epoch": 1, "mode": "1/7", "record_count": 1},
                ),
            ),
        )

    def test_source_record_digests_are_exact(self) -> None:
        self.assertEqual(
            tuple(
                source.source_record_digest
                for source in self.evidence.trace_sources
            ),
            (
                "3f730a3d088e4d75fdd1631dd234878a6acd3a7561cb463e19c815096c04fe6a",
                "4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57",
            ),
        )

    def test_first_identical_source_records_remain_distinct_by_dataset(self) -> None:
        rtl_first = self.evidence.trace_sources[0].records[0]
        fpga_first = self.evidence.trace_sources[1].records[0]
        self.assertEqual(
            rtl_first.source_record_sha256,
            fpga_first.source_record_sha256,
        )
        self.assertNotEqual(
            rtl_first.trace_record_id,
            fpga_first.trace_record_id,
        )

    def test_bundle_raw_and_embedded_identities_are_exact(self) -> None:
        bundle = self.evidence.canonical_bundle
        self.assertEqual(
            bundle.content_sha256,
            "9774e80d00c628193d5656608f2b1f830a05f960abadb83d9c4840f262ca07ed",
        )
        self.assertEqual(bundle.source_artifact.byte_length, 511783)
        self.assertEqual(
            bundle.root["bundle_digest"],
            "34d09ed25c5d5f85f26dc5430a12e58c7abccfaa5f9850e15efb84f302d76d51",
        )
        self.assertEqual(bundle.root["record_count"], 196)

    def test_bundle_routes_both_m16_traces_to_all_modes(self) -> None:
        datasets = self.evidence.canonical_bundle.root["datasets"][:2]
        for dataset in datasets:
            self.assertEqual(
                tuple(dataset["observatory_modes"]),
                (
                    "artifact_auditor",
                    "ternary_transition_visualizer",
                    "trace_explorer",
                ),
            )

    def test_bundle_records_equal_direct_trace_records(self) -> None:
        datasets = self.evidence.canonical_bundle.root["datasets"][:2]
        for source, dataset in zip(
            self.evidence.trace_sources,
            datasets,
            strict=True,
        ):
            self.assertEqual(
                _plain_json_value(dataset["records"]),
                [record.source_payload() for record in source.records],
            )

    def test_fixture_manifest_identity_is_exact(self) -> None:
        manifest = self.evidence.fixture_manifest
        self.assertEqual(
            manifest.content_sha256,
            "5d1be27e20a6a5978cb75e1185b9360621a92eb116b7a712fa5d6b813d0951fe",
        )
        self.assertEqual(manifest.source_artifact.byte_length, 5720)
        self.assertEqual(
            manifest.root["fixture_set_digest"],
            "c72be639b95b96917341d3800d2ee25a55a03e2156cd1d7f504825025053429a",
        )
        self.assertEqual(
            manifest.root["manifest_digest"],
            "42cc4416622c0e4050ac080ab9d11e595a97f00cd553484f3d97b4ae1a0ac591",
        )

    def test_fixture_manifest_requires_unchanged_upstream_bytes(self) -> None:
        fixtures = self.evidence.fixture_manifest.root["fixtures"][:2]
        for fixture in fixtures:
            self.assertEqual(
                fixture["copy_requirement"],
                "unchanged_upstream_bytes",
            )
            self.assertIn(
                "ternary_transition_visualizer",
                fixture["observatory_modes"],
            )

    def test_m7_fpga_projection_is_cross_linked_exactly(self) -> None:
        fpga = self.evidence.source_for_dataset(
            "m16-fpga-preparation-execution"
        )
        self.assertEqual(
            [
                record.source_payload()
                for record in self.dataset.trace_dataset.records
            ],
            [record.source_payload() for record in fpga.records],
        )
        self.assertEqual(
            tuple(
                record.source_record_sha256
                for record in self.dataset.trace_dataset.records
            ),
            tuple(
                record.source_record_sha256 for record in fpga.records
            ),
        )

    def test_m5_visualizer_routes_are_exact(self) -> None:
        self.assertIs(
            self.dataset.m16_dispatch,
            self.audit_batch.dispatch_batch.dispatch_for(
                "m16-fpga-preparation-execution-trace",
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ),
        )
        self.assertIs(
            self.dataset.m27_dispatch,
            self.audit_batch.dispatch_batch.dispatch_for(
                "m27-telemetry-semantics",
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ),
        )
        self.assertEqual(
            self.dataset.m16_dispatch.dispatch_sha256,
            "204c63f20db49a7d946b0963058db148fe43bb715c353c74ac4f6b203e4e792f",
        )
        self.assertEqual(
            self.dataset.m27_dispatch.dispatch_sha256,
            "b17c84a8adc66205f75d8ae81053b181ba585647e8a5e29764f0d6ec062d4d21",
        )

    def test_immutable_kernel_is_complete(self) -> None:
        self.assertEqual(
            self.dataset.observed_ternary_domain,
            (-1, 0, 1),
        )
        self.assertEqual(
            self.dataset.canonical_temporal_scheduler_modes,
            ("1/7", "7/1"),
        )
        self.assertEqual(
            self.dataset.observed_scheduler_modes,
            ("free", "7/1", "1/7"),
        )

    def test_scheduler_mode_record_counts_are_exact(self) -> None:
        self.assertEqual(
            self.dataset.scheduler_mode_record_counts,
            (
                ("free", 19),
                ("1/7", 17),
                ("7/1", 64),
            ),
        )

    def test_scheduler_state_record_counts_are_exact(self) -> None:
        self.assertEqual(
            self.dataset.scheduler_state_record_counts,
            (
                ("free", 19),
                ("balance", 56),
                ("commit", 8),
                ("excite", 3),
                ("neutralize", 14),
            ),
        )

    def test_transition_classification_counts_are_exact(self) -> None:
        self.assertEqual(
            self.dataset.transition_classification_counts,
            (
                ("same_state_retention", 783),
                ("polarity_to_neutral_transition", 5),
                ("neutral_to_polarity_transition", 12),
            ),
        )

    def test_active_neutral_route_leg_counts_are_exact(self) -> None:
        self.assertEqual(
            self.dataset.route_leg_counts,
            (
                ("non_route_transition", 790),
                ("first_leg_neutralization", 5),
                ("pending_route_completion", 5),
            ),
        )

    def test_no_direct_opposite_transition_is_present(self) -> None:
        for frame in self.dataset.transition_frames:
            self.assertNotIn(
                (
                    frame.retained_state_before,
                    frame.retained_state_after,
                ),
                ((-1, 1), (1, -1)),
            )

    def test_every_route_leg_preserves_active_neutral_semantics(self) -> None:
        for frame in self.dataset.transition_frames:
            if frame.route_leg == "first_leg_neutralization":
                self.assertEqual(frame.retained_state_after, 0)
                self.assertIn(frame.pending_route_after, (-1, 1))
            elif frame.route_leg == "pending_route_completion":
                self.assertEqual(frame.retained_state_before, 0)
                self.assertEqual(
                    frame.retained_state_after,
                    frame.pending_route_before,
                )
                self.assertEqual(frame.pending_route_after, 0)

    def test_frame_source_order_is_rtl_then_fpga(self) -> None:
        self.assertEqual(
            tuple(
                dict.fromkeys(
                    frame.source_dataset_id
                    for frame in self.dataset.transition_frames
                )
            ),
            (
                "m16-rtl-execution",
                "m16-fpga-preparation-execution",
            ),
        )
        self.assertTrue(
            all(
                frame.source_dataset_id == "m16-rtl-execution"
                for frame in self.dataset.transition_frames[:768]
            )
        )
        self.assertTrue(
            all(
                frame.source_dataset_id
                == "m16-fpga-preparation-execution"
                for frame in self.dataset.transition_frames[768:]
            )
        )

    def test_every_frame_has_exact_source_coordinates(self) -> None:
        for frame in self.dataset.transition_frames:
            self.assertEqual(
                frame.source_location,
                SourceLocation(
                    json_path=(
                        f"$.records[{frame.sequence}]."
                        f"retained_state_after[{frame.cell_id}]"
                    ),
                    array_index=frame.cell_id,
                    package_member=frame.source_path,
                    source_record_ordinal=frame.sequence + 1,
                ),
            )

    def test_frame_digest_ledger_boundaries_are_exact(self) -> None:
        first = self.dataset.transition_frames[0]
        last = self.dataset.transition_frames[-1]
        self.assertEqual(
            (first.transition_frame_id, first.frame_sha256),
            (
                "d36fc08f-e0e9-5b2a-8682-bae3b8e5cc51",
                "80606611666d5240b8b44ed3ba46f5339e5955ca999f2265019662017f1304b2",
            ),
        )
        self.assertEqual(
            (last.transition_frame_id, last.frame_sha256),
            (
                "6bb526dc-c168-5d2b-9907-b1fc744d7076",
                "86bb40733efa5049c662578584c9d236bec2ab38d8c3a9c4fc0c22e3ed01f0f5",
            ),
        )

    def test_m27_semantic_inventory_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                item.telemetry_id
                for item in self.dataset.telemetry_semantics
            ),
            (
                "switching_load_q16",
                "thermal_state_proxy_q16",
                "transition_pressure_q16",
                "global_phase_coherence_q30",
                "coherence_capacity_q16",
                "stability_margin_q16",
            ),
        )
        self.assertEqual(
            self.dataset.semantics_digest,
            "4c3cbbf7e23bf9645d84c6affa009dffc339a1277ee6fc482fd43ba946863599",
        )

    def test_m27_interpretation_boundary_remains_nonphysical(self) -> None:
        self.assertEqual(
            dict(self.dataset.interpretation_boundary),
            {
                "all_values_are_dimensionless": True,
                "all_values_are_model_derived": True,
                "physical_measurements_published": False,
                "physical_units_published": False,
                "unsupported_physical_interpretation": "prohibited",
            },
        )

    def test_dataset_identity_is_deterministic(self) -> None:
        self.assertEqual(
            self.dataset.dataset_sha256,
            "7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b",
        )
        self.assertEqual(
            self.dataset.visualizer_dataset_id,
            "68de3476-2e03-5506-93ea-062c3744e90d",
        )
        second = visualize_m30_published_archive(self.archive_path)
        self.assertEqual(second.dataset_sha256, self.dataset.dataset_sha256)
        self.assertEqual(
            second.visualizer_dataset_id,
            self.dataset.visualizer_dataset_id,
        )

    def test_models_are_frozen(self) -> None:
        values = (
            (self.evidence, "evidence_sha256"),
            (self.evidence.trace_sources[0], "source_record_digest"),
            (self.dataset, "dataset_sha256"),
            (self.dataset.transition_frames[0], "frame_sha256"),
            (
                self.dataset.telemetry_semantics[0],
                "source_record_sha256",
            ),
        )
        for value, field in values:
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field, "0" * 64)

    def test_tampered_frame_is_rejected(self) -> None:
        frame = self.dataset.transition_frames[0]
        with self.assertRaises(M30PublishedVisualizerError):
            replace(frame, retained_state_after=-1)

    def test_tampered_trace_source_digest_is_rejected(self) -> None:
        source = self.evidence.trace_sources[0]
        with self.assertRaisesRegex(
            M30PublishedVisualizerError,
            "source record digest changed",
        ):
            replace(source, source_record_digest="0" * 64)

    def test_tampered_full_core_evidence_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedVisualizerError,
            "evidence_sha256",
        ):
            replace(self.evidence, evidence_sha256="0" * 64)

    def test_tampered_dataset_frame_inventory_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedVisualizerError,
            "exactly 800 frames",
        ):
            replace(
                self.dataset,
                transition_frames=self.dataset.transition_frames[:-1],
            )

    def test_public_result_types_are_exact(self) -> None:
        self.assertIsInstance(self.evidence, M30FullCoreTraceEvidence)
        self.assertTrue(
            all(
                isinstance(source, PublishedCoreTraceSource)
                for source in self.evidence.trace_sources
            )
        )
        self.assertTrue(
            all(
                isinstance(frame, PublishedTransitionFrame)
                for frame in self.dataset.transition_frames
            )
        )

    def test_cli_reports_complete_kernel_and_counts(self) -> None:
        result = subprocess.run(
            (
                sys.executable,
                "-m",
                "transition_visualizer.m30_published_transition_visualizer",
                "--archive",
                str(self.archive_path),
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "FRP Observatory M8 full-core Transition Visualizer: PASS",
            result.stdout,
        )
        for line in (
            "trace_sources=2",
            "trace_records=100",
            "transition_frames=800",
            "balanced_ternary_notation=-1/0/1",
            "active_neutral_state=0",
            "temporal_scheduler_modes=1/7,7/1",
            "observed_scheduler_modes=free,7/1,1/7",
            "observed_ternary_domain=-1/0/1",
        ):
            with self.subTest(line=line):
                self.assertIn(line, result.stdout)

    def test_one_byte_archive_tamper_is_rejected_before_projection(self) -> None:
        raw = bytearray(self.archive_path.read_bytes())
        raw[-17] ^= 1
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory, "tampered-m30.tar.gz")
            tampered.write_bytes(raw)
            with self.assertRaises(M30ArchiveIntakeError):
                visualize_m30_published_archive(tampered)


if __name__ == "__main__":
    unittest.main()
