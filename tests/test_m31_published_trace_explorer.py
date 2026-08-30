"""Tests for the exact read-only FRP M31 published Trace Explorer."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m31_published_auditor import (
    audit_m31_published_documents,
)
from artifact_auditor.m31_published_boundary_intake import (
    M31PublishedDocumentRole,
)
from schemas.m31_published_registry import M31PublishedMeasurementContour
from schemas.registry import ObservatoryMode
from trace_explorer.m31_published_trace_explorer import (
    M31PublishedTraceError,
    build_m31_published_trace_dataset,
    explore_m31_published_documents,
)


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
_LATER_LOADED_AT = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)

_ACTIVE_ZERO_ROLES = (
    "conflict_neutralization",
    "temporal_separation",
    "balancing",
    "damping",
    "transition_buffering",
    "switching_load_distribution",
    "retained_transition_continuity",
    "pending_route_completion_preparation",
    "stabilization",
)
_EVENT_TOTALS = (
    ("actual_direct_events", 0),
    ("neutral_routed_events", 5),
    ("prevented_direct_events", 5),
    ("queue_overflow_events", 0),
    ("requested_direct_events", 5),
    ("reserved_state_events", 0),
)
_TRANSITION_TOTALS = (
    ("active_zero_to_polarity", 12),
    ("direct_opposite", 0),
    ("polarity_to_active_zero", 5),
    ("retained_same", 783),
)
_SCHEDULER_MODE_COUNTS = (
    ("free", 19),
    ("7/1", 64),
    ("1/7", 17),
)
_SCHEDULER_STATE_COUNTS = (
    ("balance", 56),
    ("commit", 8),
    ("excite", 3),
    ("free", 19),
    ("neutralize", 14),
)
_INVARIANT_NAMES = (
    "state_domain_valid",
    "scheduler_counts_valid",
    "request_lane_order_valid",
    "pending_polarity_valid",
    "active_neutral_valid",
    "transition_capacity_valid",
    "state_update_valid",
    "no_actual_direct_events",
    "no_reserved_state",
    "no_queue_overflow",
)
_CONTOUR_IDENTITIES = (
    (
        "artifacts/m19/execution/m16-rtl-execution-trace.json",
        "d7945e0d2b5aaa05c5fff2e4e60d3b984017f7e4ae1984c55920368a110020bd",
        "frp.m16.rtl_execution_trace.v2.1.0",
        "m16_rtl_execution_trace",
        "rtl",
        96,
        "3f730a3d088e4d75fdd1631dd234878a6acd3a7561cb463e19c815096c04fe6a",
        "23a0af37356389dc6ffd4ab2bac4a0cf64a418583ed43195b44193dacc3c4600",
        "ee01676e-76f9-5197-9ed9-e80d9b5187a1",
    ),
    (
        "artifacts/m19/execution/"
        "m16-fpga-preparation-execution-trace.json",
        "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f",
        "frp.m16.fpga_preparation_execution_trace.v2.1.0",
        "m16_fpga_preparation_execution_trace",
        "fpga_preparation",
        4,
        "4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57",
        "3e06ba60c8fb3bab08eabd83b9a3d83dee0176c6a682bb2825d2bba9d62dee94",
        "9bc92fca-0db1-57ae-8951-398a7f059336",
    ),
)


def _plain_json_value(value: Any) -> Any:
    """Return a mutable JSON-shaped value for lossless comparison."""

    if isinstance(value, Mapping):
        return {
            str(key): _plain_json_value(member)
            for key, member in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_plain_json_value(member) for member in value]
    return value


class M31PublishedTraceExplorerGuardTests(unittest.TestCase):
    """Exercise the dedicated M17-to-M18 public type boundary."""

    def test_builder_requires_exact_m31_audit_batch_type(self) -> None:
        for value in (None, "batch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M31PublishedTraceError,
                    "audit_batch must be M31PublishedAuditBatch",
                ):
                    build_m31_published_trace_dataset(value)


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM31PublishedTraceExplorerIntegrationTests(unittest.TestCase):
    """Exercise both trace contours against the exact FRP M31 publication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.audit_batch = audit_m31_published_documents(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        cls.dataset = build_m31_published_trace_dataset(cls.audit_batch)

    def test_dataset_is_green_and_retains_exact_m31_identity(self) -> None:
        self.assertIs(
            self.dataset.audit_batch.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(self.dataset.audit_batch.failed_check_count, 0)
        self.assertEqual(
            self.dataset.registry_revision,
            "m31-published-boundary-v1",
        )
        self.assertEqual(
            self.dataset.evidence_raw_sha256,
            "bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42",
        )

    def test_auditor_and_trace_route_share_exact_evidence_document(self) -> None:
        expected_report = self.audit_batch.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        expected_dispatch = self.audit_batch.dispatch_batch.dispatch_for(
            M31PublishedDocumentRole.EVIDENCE,
            ObservatoryMode.TRACE_EXPLORER,
        )
        self.assertIs(self.dataset.audit_report, expected_report)
        self.assertIs(self.dataset.dispatch, expected_dispatch)
        self.assertIs(
            self.dataset.dispatch.document,
            self.dataset.audit_report.dispatch.document,
        )
        self.assertIs(
            self.dataset.dispatch.source_artifact,
            self.dataset.audit_report.dispatch.source_artifact,
        )

    def test_registry_contains_only_one_m31_trace_explorer_route(self) -> None:
        routes = self.audit_batch.dispatch_batch.dispatches_for_mode(
            ObservatoryMode.TRACE_EXPLORER
        )
        self.assertEqual(len(routes), 1)
        self.assertIs(routes[0], self.dataset.dispatch)
        self.assertIs(
            routes[0].document.identity.role,
            M31PublishedDocumentRole.EVIDENCE,
        )

    def test_two_trace_contours_remain_distinct_and_source_ordered(self) -> None:
        self.assertEqual(self.dataset.trace_contour_count, 2)
        self.assertEqual(
            tuple(contour.contour_index for contour in self.dataset.contours),
            (0, 1),
        )
        self.assertEqual(
            tuple(contour.source_path for contour in self.dataset.contours),
            tuple(identity[0] for identity in _CONTOUR_IDENTITIES),
        )
        self.assertEqual(len({id(contour) for contour in self.dataset.contours}), 2)

    def test_contour_identity_ledger_is_exact(self) -> None:
        observed = tuple(
            (
                contour.source_path,
                contour.raw_sha256,
                contour.schema_identifier,
                contour.trace_kind,
                contour.layer,
                contour.record_count,
                contour.source_record_digest,
                contour.contour_sha256,
                contour.trace_contour_id,
            )
            for contour in self.dataset.contours
        )
        self.assertEqual(observed, _CONTOUR_IDENTITIES)

    def test_complete_record_cell_and_request_inventory_is_retained(self) -> None:
        self.assertEqual(self.dataset.record_count, 100)
        self.assertEqual(self.dataset.cell_snapshot_count, 800)
        self.assertEqual(self.dataset.request_count, 200)
        self.assertEqual(self.dataset.invariant_pass_record_count, 100)
        self.assertEqual(
            tuple(contour.record_count for contour in self.dataset.contours),
            (96, 4),
        )

    def test_dataset_identifier_and_digest_are_exact(self) -> None:
        self.assertEqual(
            self.dataset.trace_dataset_id,
            "0f0f0f7e-0409-5e7b-8c76-2f72bb954321",
        )
        self.assertEqual(
            self.dataset.dataset_sha256,
            "ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff",
        )

    def test_record_identifier_ledger_is_unique_and_source_bound(self) -> None:
        record_ids = tuple(
            record.trace_record_id for record in self.dataset.records
        )
        self.assertEqual(len(record_ids), 100)
        self.assertEqual(len(set(record_ids)), 100)
        self.assertEqual(
            (
                self.dataset.contours[0].records[0].trace_record_id,
                self.dataset.contours[0].records[-1].trace_record_id,
                self.dataset.contours[1].records[0].trace_record_id,
                self.dataset.contours[1].records[-1].trace_record_id,
            ),
            (
                "b54aba36-8149-5cd1-b825-c2939219ee8d",
                "2ed5afd1-3f9b-5288-8bc9-e0608c071269",
                "ca01480c-17f2-5c79-8cfe-019ae1c0ae5f",
                "5be37ced-fa7d-5395-bf28-8ff417a8989f",
            ),
        )

    def test_every_projection_round_trips_to_exact_source_record(self) -> None:
        for contour in self.dataset.contours:
            source_records = contour.parsed_artifact.root["records"]
            with self.subTest(source_path=contour.source_path):
                self.assertEqual(
                    [record.source_payload() for record in contour.records],
                    _plain_json_value(source_records),
                )

    def test_every_record_retains_source_local_sequence_and_coordinates(self) -> None:
        for contour in self.dataset.contours:
            self.assertEqual(
                tuple(record.sequence for record in contour.records),
                tuple(range(contour.record_count)),
            )
            for sequence, record in enumerate(contour.records):
                with self.subTest(
                    source_path=contour.source_path,
                    sequence=sequence,
                ):
                    self.assertEqual(
                        record.source_location,
                        SourceLocation(
                            json_path=f"$.records[{sequence}]",
                            array_index=sequence,
                            package_member=contour.source_path,
                            source_record_ordinal=sequence + 1,
                        ),
                    )

    def test_execution_epoch_declarations_remain_source_local(self) -> None:
        self.assertEqual(
            tuple(
                tuple(epoch.source_payload() for epoch in contour.epochs)
                for contour in self.dataset.contours
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

    def test_scheduler_modes_and_states_match_published_counts(self) -> None:
        self.assertEqual(
            self.dataset.observed_scheduler_modes,
            ("free", "7/1", "1/7"),
        )
        self.assertEqual(
            self.dataset.scheduler_mode_counts,
            _SCHEDULER_MODE_COUNTS,
        )
        self.assertEqual(
            self.dataset.scheduler_state_counts,
            _SCHEDULER_STATE_COUNTS,
        )
        self.assertEqual(
            self.dataset.published_scheduler_mode_counts,
            _SCHEDULER_MODE_COUNTS,
        )
        self.assertEqual(
            self.dataset.published_scheduler_state_counts,
            _SCHEDULER_STATE_COUNTS,
        )

    def test_all_states_routes_and_targets_remain_exactly_minus1_0_1(self) -> None:
        self.assertEqual(self.dataset.observed_ternary_domain, (-1, 0, 1))
        for record in self.dataset.records:
            for cell in record.cells:
                self.assertIn(cell.phase_derived_target, (-1, 0, 1))
                self.assertIn(cell.retained_state_before, (-1, 0, 1))
                self.assertIn(cell.retained_state_after, (-1, 0, 1))
                self.assertIn(cell.pending_route_before, (-1, 0, 1))
                self.assertIn(cell.pending_route_after, (-1, 0, 1))
            for request in record.requests:
                self.assertIn(request.target_state, (-1, 0, 1))

    def test_active_zero_roles_and_observation_inventory_are_exact(self) -> None:
        self.assertEqual(self.dataset.active_zero_roles, _ACTIVE_ZERO_ROLES)
        self.assertEqual(
            self.dataset.active_zero_after_observation_count,
            702,
        )

    def test_opposite_requests_use_active_zero_then_pending_completion(self) -> None:
        for contour_index in (0, 1):
            first_leg = self.dataset.contours[contour_index].records[1].cells[0]
            completion = self.dataset.contours[contour_index].records[2].cells[0]
            with self.subTest(contour_index=contour_index):
                self.assertEqual(
                    (
                        first_leg.retained_state_before,
                        first_leg.retained_state_after,
                        first_leg.pending_route_after,
                    ),
                    (1, 0, -1),
                )
                self.assertTrue(first_leg.neutral_routed)
                self.assertEqual(
                    (
                        completion.retained_state_before,
                        completion.pending_route_before,
                        completion.retained_state_after,
                        completion.pending_route_after,
                    ),
                    (0, -1, -1, 0),
                )

    def test_no_projected_cell_contains_direct_opposite_transition(self) -> None:
        for record in self.dataset.records:
            for cell in record.cells:
                self.assertNotIn(
                    (
                        cell.retained_state_before,
                        cell.retained_state_after,
                    ),
                    ((-1, 1), (1, -1)),
                )

    def test_request_lane_order_and_acceptance_inventory_are_exact(self) -> None:
        for record in self.dataset.records:
            self.assertEqual(
                tuple(request.lane for request in record.requests),
                (0, 1),
            )
        lane_zero = Counter(
            (
                record.requests[0].valid,
                record.requests[0].accepted,
                record.requests[0].rejected,
            )
            for record in self.dataset.records
        )
        lane_one = Counter(
            (
                record.requests[1].valid,
                record.requests[1].accepted,
                record.requests[1].rejected,
            )
            for record in self.dataset.records
        )
        self.assertEqual(
            lane_zero,
            Counter(
                {
                    (False, False, False): 82,
                    (True, True, False): 11,
                    (True, False, True): 7,
                }
            ),
        )
        self.assertEqual(
            lane_one,
            Counter(
                {
                    (False, False, False): 99,
                    (True, True, False): 1,
                }
            ),
        )

    def test_transition_capacity_and_switch_load_distributions_are_exact(self) -> None:
        capacity = Counter(
            (
                record.capacity_limit,
                record.accepted_changes,
                record.capacity_remaining,
                record.capacity_exhausted,
            )
            for record in self.dataset.records
        )
        switch_load = Counter(
            (
                record.switch_load_numerator,
                record.switch_load_denominator,
                record.switch_load_q16,
            )
            for record in self.dataset.records
        )
        self.assertEqual(
            capacity,
            Counter(
                {
                    (2, 0, 2, False): 84,
                    (2, 1, 1, False): 15,
                    (2, 2, 0, True): 1,
                }
            ),
        )
        self.assertEqual(
            switch_load,
            Counter(
                {
                    (0, 8, 0): 84,
                    (1, 8, 8192): 15,
                    (2, 8, 16384): 1,
                }
            ),
        )

    def test_event_totals_are_exact_and_forbidden_events_remain_zero(self) -> None:
        self.assertEqual(self.dataset.event_totals, _EVENT_TOTALS)
        self.assertEqual(self.dataset.published_event_totals, _EVENT_TOTALS)
        for record in self.dataset.records:
            self.assertEqual(record.event_count("actual_direct_events"), 0)
            self.assertEqual(record.event_count("reserved_state_events"), 0)
            self.assertEqual(record.event_count("queue_overflow_events"), 0)

    def test_retained_transition_totals_are_exact(self) -> None:
        self.assertEqual(
            self.dataset.retained_transition_totals,
            _TRANSITION_TOTALS,
        )
        self.assertEqual(
            self.dataset.published_transition_totals,
            _TRANSITION_TOTALS,
        )

    def test_all_ten_invariant_flags_remain_ordered_and_passing(self) -> None:
        for record in self.dataset.records:
            self.assertEqual(record.invariant_names, _INVARIANT_NAMES)
            self.assertTrue(record.invariant_all_pass)

    def test_measurement_boundaries_remain_explicitly_separate(self) -> None:
        self.assertIs(
            self.dataset.measurement_contour,
            M31PublishedMeasurementContour
            .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE,
        )
        for contour in self.dataset.contours:
            with self.subTest(source_path=contour.source_path):
                self.assertEqual(
                    contour.m15_correlation_status,
                    "not_evaluated_in_m19",
                )
                self.assertEqual(
                    contour.physical_measurement_availability,
                    "not_in_scope",
                )
                self.assertEqual(
                    contour.physical_measurement_correlation_status,
                    "not_evaluated",
                )

    def test_each_contour_retains_exact_captured_provenance_bytes(self) -> None:
        boundary_sources = (
            self.audit_batch.dispatch_batch.registry_validation
            .boundary.provenance_sources
        )
        for contour in self.dataset.contours:
            matches = tuple(
                source
                for source in boundary_sources
                if source.source_path == contour.source_path
            )
            with self.subTest(source_path=contour.source_path):
                self.assertEqual(len(matches), 1)
                self.assertIs(contour.provenance_source, matches[0])
                self.assertIs(
                    contour.parsed_artifact.source_artifact,
                    matches[0].source_artifact,
                )
                self.assertTrue(matches[0].source_artifact.verify_integrity())

    def test_publication_contract_is_exactly_read_only_and_one_way(self) -> None:
        contract = dict(
            self.dataset.dispatch.parsed_artifact.root[
                "observatory_publication_contract"
            ]
        )
        self.assertEqual(
            contract,
            {
                "direction": "upstream_published_bytes_to_downstream",
                "downstream_metric_normalization": "forbidden",
                "downstream_repository": "FRP-Trace-Observatory",
                "downstream_role": "read_only_validation_and_visualization",
                "downstream_semantic_reimplementation": "forbidden",
                "downstream_source_mutation": "forbidden",
                "downstream_writeback": "forbidden",
                "m29_boundary_confirmed": True,
                "published_contours_must_remain_separate": True,
                "upstream_repository": "FRP",
            },
        )

    def test_repeated_projection_is_deterministic_across_loaded_at(self) -> None:
        repeated = explore_m31_published_documents(
            self.upstream_root,
            loaded_at=_LATER_LOADED_AT,
        )
        self.assertNotEqual(
            repeated.audit_batch.dispatch_batch.registry_validation
            .boundary.loaded_at,
            self.dataset.audit_batch.dispatch_batch.registry_validation
            .boundary.loaded_at,
        )
        self.assertEqual(repeated.dataset_sha256, self.dataset.dataset_sha256)
        self.assertEqual(
            repeated.trace_dataset_id,
            self.dataset.trace_dataset_id,
        )
        self.assertEqual(
            tuple(contour.contour_sha256 for contour in repeated.contours),
            tuple(
                contour.contour_sha256 for contour in self.dataset.contours
            ),
        )
        self.assertEqual(
            tuple(record.trace_record_id for record in repeated.records),
            tuple(record.trace_record_id for record in self.dataset.records),
        )

    def test_command_line_summary_is_exact(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "trace_explorer.m31_published_trace_explorer",
                "--upstream-root",
                str(self.upstream_root),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        lines = completed.stdout.splitlines()
        self.assertIn(
            "FRP Observatory M31 published Trace Explorer: PASS",
            lines,
        )
        self.assertIn("trace_contours=2", lines)
        self.assertIn("records=100", lines)
        self.assertIn("active_zero_after_observations=702", lines)
        self.assertIn("observed_ternary_domain=-1/0/1", lines)
        self.assertIn("source_execution=forbidden", lines)
        self.assertIn("downstream_writeback=forbidden", lines)

    def test_dataset_and_nested_projection_values_are_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset, "dataset_sha256", "0" * 64)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.contours[0], "contour_index", 1)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.records[0], "sequence", 1)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.records[0].cells[0], "cell_id", 1)

    def test_direct_opposite_cell_mutation_is_rejected(self) -> None:
        cell = self.dataset.records[0].cells[0]
        with self.assertRaisesRegex(M31PublishedTraceError, "direct opposite"):
            replace(
                cell,
                retained_state_before=-1,
                retained_state_after=1,
            )

    def test_invalid_request_cannot_be_relabelled_as_accepted(self) -> None:
        invalid = next(
            request
            for record in self.dataset.records
            for request in record.requests
            if not request.valid
        )
        with self.assertRaisesRegex(M31PublishedTraceError, "invalid request"):
            replace(invalid, accepted=True)

    def test_scheduler_tick_relation_cannot_be_changed(self) -> None:
        scheduler = self.dataset.records[0].scheduler
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "ticks_after must equal ticks_before plus one",
        ):
            replace(scheduler, ticks_after=scheduler.ticks_before + 2)

    def test_valid_but_tampered_cell_is_rejected_by_source_binding(self) -> None:
        contour = self.dataset.contours[0]
        record = contour.records[0]
        cell = record.cells[0]
        replacement_target = 0 if cell.phase_derived_target != 0 else 1
        tampered_cell = replace(
            cell,
            phase_derived_target=replacement_target,
        )
        tampered_record = replace(
            record,
            cells=(tampered_cell,) + record.cells[1:],
        )
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "projected record differs from exact retained source",
        ):
            replace(
                contour,
                records=(tampered_record,) + contour.records[1:],
            )

    def test_wrong_source_record_digest_is_rejected(self) -> None:
        contour = self.dataset.contours[0]
        tampered_record = replace(
            contour.records[0],
            source_record_sha256="0" * 64,
        )
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "projected record source digest mismatch",
        ):
            replace(
                contour,
                records=(tampered_record,) + contour.records[1:],
            )

    def test_trace_contours_cannot_be_swapped_or_merged(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "trace contour source order changed",
        ):
            replace(
                self.dataset,
                contours=tuple(reversed(self.dataset.contours)),
            )
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "trace contour source order changed",
        ):
            replace(
                self.dataset,
                contours=(self.dataset.contours[0], self.dataset.contours[0]),
            )

    def test_synthetic_scheduler_epoch_is_rejected(self) -> None:
        contour = self.dataset.contours[1]
        synthetic_epoch = replace(contour.epochs[1], mode="7/1")
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "record scheduler mode differs from its source epoch",
        ):
            replace(
                contour,
                epochs=(contour.epochs[0], synthetic_epoch),
            )

    def test_measurement_contour_alias_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "M31 evidence contour was replaced or aliased",
        ):
            replace(
                self.dataset,
                measurement_contour=(
                    M31PublishedMeasurementContour.FORMAL_SCHEMA_DEFINITION
                ),
            )

    def test_invented_record_source_coordinate_is_rejected(self) -> None:
        contour = self.dataset.contours[0]
        record = replace(
            contour.records[0],
            source_location=SourceLocation(
                json_path="$.records[1]",
                array_index=0,
                package_member=contour.source_path,
                source_record_ordinal=1,
            ),
        )
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "record source coordinate changed",
        ):
            replace(
                contour,
                records=(record,) + contour.records[1:],
            )

    def test_forged_dataset_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "dataset_sha256 does not bind exact M31 evidence and traces",
        ):
            replace(self.dataset, dataset_sha256="0" * 64)

    def test_active_zero_roles_cannot_be_relabelled(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "active-zero role declaration changed",
        ):
            replace(
                self.dataset,
                active_zero_roles=self.dataset.active_zero_roles[:-1],
            )

    def test_published_event_totals_cannot_be_normalized(self) -> None:
        altered = tuple(
            (name, value + (1 if name == "neutral_routed_events" else 0))
            for name, value in self.dataset.published_event_totals
        )
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "published event totals changed",
        ):
            replace(self.dataset, published_event_totals=altered)

    def test_unknown_event_counter_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedTraceError,
            "unknown event counter",
        ):
            self.dataset.records[0].event_count("invented_event")


if __name__ == "__main__":
    unittest.main()
