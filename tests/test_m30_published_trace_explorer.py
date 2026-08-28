"""Tests for the exact read-only M30 published Trace Explorer dataset."""

from __future__ import annotations

import os
import unittest
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from typing import Any

from artifact_auditor.audit_report import SourceLocation, ValidationStatus
from artifact_auditor.m30_published_auditor import (
    audit_m30_published_archive,
)
from schemas.m30_published_registry import PublishedMeasurementContour
from schemas.registry import ObservatoryMode
from trace_explorer.m30_published_trace_explorer import (
    M30PublishedTraceError,
    build_m30_published_trace_dataset,
    explore_m30_published_archive,
)


_ARCHIVE_ENVIRONMENT_VARIABLE = "FRP_M30_ARCHIVE_PATH"


def _plain_json_value(value: Any) -> Any:
    """Return a mutable JSON-shaped projection for exact value comparison."""

    if isinstance(value, Mapping):
        return {
            str(key): _plain_json_value(member)
            for key, member in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_plain_json_value(member) for member in value]
    return value


class PublishedTraceExplorerGuardTests(unittest.TestCase):
    """Exercise the dedicated M6-to-M7 public type boundary."""

    def test_builder_requires_exact_m6_batch_type(self) -> None:
        for value in (None, "batch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M30PublishedTraceError,
                    "audit_batch must be PublishedAuditBatch",
                ):
                    build_m30_published_trace_dataset(value)


@unittest.skipUnless(
    os.environ.get(_ARCHIVE_ENVIRONMENT_VARIABLE),
    f"{_ARCHIVE_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM30PublishedTraceExplorerIntegrationTests(unittest.TestCase):
    """Exercise the M16 projection against the exact published archive."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.archive_path = os.environ[_ARCHIVE_ENVIRONMENT_VARIABLE]
        cls.audit_batch = audit_m30_published_archive(cls.archive_path)
        cls.dataset = build_m30_published_trace_dataset(cls.audit_batch)

    def test_dataset_is_green_and_retains_exact_source_identity(self) -> None:
        self.assertIs(
            self.dataset.audit_batch.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(
            self.dataset.member_id,
            "m16-fpga-preparation-execution-trace",
        )
        self.assertEqual(
            self.dataset.dispatch.member.registration.schema_identifier,
            "frp.m16.fpga_preparation_execution_trace.v2.1.0",
        )
        self.assertEqual(
            self.dataset.dispatch.member.registration.raw_sha256,
            "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f",
        )

    def test_m6_report_and_m5_trace_route_share_exact_m4_member(self) -> None:
        self.assertIs(
            self.dataset.dispatch,
            self.audit_batch.dispatch_batch.dispatch_for(
                "m16-fpga-preparation-execution-trace",
                ObservatoryMode.TRACE_EXPLORER,
            ),
        )
        self.assertIs(
            self.dataset.audit_report,
            self.audit_batch.report_for_member(
                "m16-fpga-preparation-execution-trace"
            ),
        )
        self.assertIs(
            self.dataset.dispatch.member,
            self.dataset.audit_report.dispatch.member,
        )
        self.assertIs(
            self.dataset.dispatch.source_artifact,
            self.dataset.audit_report.dispatch.source_artifact,
        )

    def test_registry_contains_only_one_trace_explorer_route(self) -> None:
        routes = self.audit_batch.dispatch_batch.dispatches_for_mode(
            ObservatoryMode.TRACE_EXPLORER
        )
        self.assertEqual(len(routes), 1)
        self.assertEqual(
            tuple(route.member_id for route in routes),
            ("m16-fpga-preparation-execution-trace",),
        )
        self.assertNotIn("m27-telemetry-semantics", self.dataset.member_id)

    def test_complete_record_cell_and_request_inventory_is_retained(self) -> None:
        self.assertEqual(self.dataset.record_count, 4)
        self.assertEqual(self.dataset.cell_snapshot_count, 32)
        self.assertEqual(self.dataset.request_count, 8)
        self.assertEqual(
            tuple(record.sequence for record in self.dataset.records),
            (0, 1, 2, 3),
        )

    def test_dataset_identifier_and_digest_are_deterministic(self) -> None:
        self.assertEqual(
            self.dataset.trace_dataset_id,
            "4191b36e-9168-5fc7-a4b5-cbc3b480136f",
        )
        self.assertEqual(
            self.dataset.dataset_sha256,
            "4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd",
        )

    def test_source_record_digest_is_retained_exactly(self) -> None:
        self.assertEqual(
            self.dataset.source_record_digest,
            "4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57",
        )
        self.assertEqual(
            self.dataset.source_record_digest,
            self.dataset.dispatch.parsed_artifact.root["summary"][
                "record_digest"
            ],
        )

    def test_record_identifier_and_digest_ledger_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                (record.trace_record_id, record.source_record_sha256)
                for record in self.dataset.records
            ),
            (
                (
                    "c9f48870-584d-5622-8e17-e4096322b9a9",
                    "c7d1c6a3422c7578e559a04b252fe55b8889243ebbfd130b0aed290020033287",
                ),
                (
                    "812912bc-951a-56cb-86c8-6f49d7c7c56d",
                    "a9abe9c939d1ccdd1abc884c55f6e398f5443c491124ebd6faa54c627bc696d6",
                ),
                (
                    "92a09ab0-fc1c-5d4c-b25d-09234776c3ed",
                    "941d6efaadc31981d1e74f41a78a90f2e990bcfa6966a8e0ba62971377260767",
                ),
                (
                    "e803d9d8-1714-581a-a9d2-ea012cd42bde",
                    "7cfcf363d8f2cd5730b99cddfd761c82e02812bb04f2b912fa913f804e54de99",
                ),
            ),
        )

    def test_every_projection_round_trips_to_exact_source_record(self) -> None:
        source_records = self.dataset.dispatch.parsed_artifact.root["records"]
        self.assertEqual(
            [record.source_payload() for record in self.dataset.records],
            _plain_json_value(source_records),
        )

    def test_every_record_retains_exact_source_coordinates(self) -> None:
        for sequence, record in enumerate(self.dataset.records):
            with self.subTest(sequence=sequence):
                self.assertEqual(
                    record.source_location,
                    SourceLocation(
                        json_path=f"$.records[{sequence}]",
                        array_index=sequence,
                        package_member=(
                            "artifacts/m19/execution/"
                            "m16-fpga-preparation-execution-trace.json"
                        ),
                        source_record_ordinal=sequence + 1,
                    ),
                )

    def test_execution_epoch_declarations_and_order_are_exact(self) -> None:
        self.assertEqual(
            tuple(epoch.source_payload() for epoch in self.dataset.epochs),
            (
                {"epoch": 0, "mode": "free", "record_count": 3},
                {"epoch": 1, "mode": "1/7", "record_count": 1},
            ),
        )
        self.assertEqual(
            tuple(record.execution_epoch for record in self.dataset.records),
            (0, 0, 0, 1),
        )

    def test_observed_scheduler_modes_do_not_synthesize_missing_7_1(self) -> None:
        self.assertEqual(
            self.dataset.observed_scheduler_modes,
            ("free", "1/7"),
        )
        self.assertNotIn("7/1", self.dataset.observed_scheduler_modes)

    def test_scheduler_snapshots_retain_exact_mode_state_and_ticks(self) -> None:
        self.assertEqual(
            tuple(
                (
                    record.scheduler.mode,
                    record.scheduler.state,
                    record.scheduler.ticks_before,
                    record.scheduler.ticks_after,
                )
                for record in self.dataset.records
            ),
            (
                ("free", "free", 0, 1),
                ("free", "free", 1, 2),
                ("free", "free", 2, 3),
                ("1/7", "excite", 0, 1),
            ),
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

    def test_opposite_request_uses_active_neutral_then_pending_completion(self) -> None:
        first_leg = self.dataset.records[1].cells[0]
        completion = self.dataset.records[2].cells[0]
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

    def test_request_lane_order_and_acceptance_are_exact(self) -> None:
        for record in self.dataset.records:
            self.assertEqual(
                tuple(request.lane for request in record.requests),
                (0, 1),
            )
        self.assertEqual(
            tuple(
                (
                    record.requests[0].valid,
                    record.requests[0].cell_index,
                    record.requests[0].target_state,
                    record.requests[0].accepted,
                )
                for record in self.dataset.records
            ),
            (
                (True, 0, 1, True),
                (True, 0, -1, True),
                (False, 0, 0, False),
                (True, 1, 1, True),
            ),
        )

    def test_transition_capacity_and_switch_load_relations_are_exact(self) -> None:
        for record in self.dataset.records:
            with self.subTest(sequence=record.sequence):
                self.assertEqual(record.capacity_limit, 2)
                self.assertEqual(record.accepted_changes, 1)
                self.assertEqual(record.capacity_remaining, 1)
                self.assertFalse(record.capacity_exhausted)
                self.assertEqual(record.switch_load_numerator, 1)
                self.assertEqual(record.switch_load_denominator, 8)
                self.assertEqual(record.switch_load_q16, 8192)

    def test_event_totals_are_exact_and_forbidden_events_remain_zero(self) -> None:
        self.assertEqual(
            self.dataset.event_totals,
            (
                ("actual_direct_events", 0),
                ("neutral_routed_events", 1),
                ("prevented_direct_events", 1),
                ("queue_overflow_events", 0),
                ("requested_direct_events", 1),
                ("reserved_state_events", 0),
            ),
        )

    def test_all_ten_invariant_flags_remain_ordered_and_passing(self) -> None:
        expected = (
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
        for record in self.dataset.records:
            self.assertEqual(record.invariant_names, expected)
            self.assertTrue(record.invariant_all_pass)

    def test_measurement_contours_remain_explicitly_separate(self) -> None:
        self.assertIs(
            self.dataset.measurement_contour,
            PublishedMeasurementContour.M16_FPGA_PREPARATION_EXECUTION,
        )
        self.assertEqual(
            self.dataset.m15_correlation_status,
            "not_evaluated_in_m19",
        )
        self.assertEqual(
            self.dataset.physical_measurement_availability,
            "not_in_scope",
        )
        self.assertEqual(
            self.dataset.physical_measurement_correlation_status,
            "not_evaluated",
        )

    def test_repeated_archive_projection_is_byte_deterministic(self) -> None:
        repeated = explore_m30_published_archive(self.archive_path)
        self.assertEqual(repeated.dataset_sha256, self.dataset.dataset_sha256)
        self.assertEqual(
            repeated.trace_dataset_id,
            self.dataset.trace_dataset_id,
        )
        self.assertEqual(
            tuple(record.source_payload() for record in repeated.records),
            tuple(record.source_payload() for record in self.dataset.records),
        )

    def test_dataset_and_nested_records_are_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset, "dataset_sha256", "0" * 64)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.records[0], "sequence", 4)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.dataset.records[0].cells[0], "cell_id", 7)

    def test_direct_opposite_cell_mutation_is_rejected(self) -> None:
        cell = self.dataset.records[0].cells[0]
        with self.assertRaisesRegex(
            M30PublishedTraceError,
            "direct opposite",
        ):
            replace(
                cell,
                retained_state_before=-1,
                retained_state_after=1,
            )

    def test_valid_but_tampered_projection_is_rejected_by_source_binding(self) -> None:
        record = self.dataset.records[0]
        tampered_cell = replace(
            record.cells[0],
            phase_derived_target=0,
        )
        tampered_record = replace(
            record,
            cells=(tampered_cell,) + record.cells[1:],
        )
        with self.assertRaisesRegex(
            M30PublishedTraceError,
            "projected record differs",
        ):
            replace(
                self.dataset,
                records=(tampered_record,) + self.dataset.records[1:],
            )

    def test_wrong_source_record_digest_is_rejected(self) -> None:
        record = replace(
            self.dataset.records[0],
            source_record_sha256="0" * 64,
        )
        with self.assertRaisesRegex(
            M30PublishedTraceError,
            "projected record source digest mismatch",
        ):
            replace(
                self.dataset,
                records=(record,) + self.dataset.records[1:],
            )

    def test_synthetic_7_1_observation_is_rejected(self) -> None:
        synthetic = replace(self.dataset.epochs[1], mode="7/1")
        with self.assertRaisesRegex(
            M30PublishedTraceError,
            "record scheduler mode differs",
        ):
            replace(
                self.dataset,
                epochs=(self.dataset.epochs[0], synthetic),
            )

    def test_published_measurement_contour_alias_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedTraceError,
            "measurement contour was replaced or aliased",
        ):
            replace(
                self.dataset,
                measurement_contour=(
                    PublishedMeasurementContour.M27_LONG_RUN_TELEMETRY_SEMANTICS
                ),
            )

    def test_invented_record_source_coordinate_is_rejected(self) -> None:
        record = replace(
            self.dataset.records[0],
            source_location=SourceLocation(
                json_path="$.records[1]",
                array_index=0,
                package_member=(
                    "artifacts/m19/execution/"
                    "m16-fpga-preparation-execution-trace.json"
                ),
                source_record_ordinal=1,
            ),
        )
        with self.assertRaisesRegex(
            M30PublishedTraceError,
            "record source coordinate changed",
        ):
            replace(
                self.dataset,
                records=(record,) + self.dataset.records[1:],
            )


if __name__ == "__main__":
    unittest.main()
