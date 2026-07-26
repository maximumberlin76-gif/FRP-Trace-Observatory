"""Tests for immutable transition, route, and scheduler records."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from uuid import NAMESPACE_URL, uuid5

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)
from transition_visualizer import (
    CANONICAL_TERNARY_DOMAIN,
    CanonicalTernaryState,
    RecordOrigin,
    RequestAcceptanceStatus,
    RequestLaneRecord,
    RequestRouteModelError,
    RouteEventRecord,
    RouteLegClassification,
    RouteStatus,
    SchedulerField,
    SchedulerFieldValue,
    SchedulerMode,
    SchedulerModelError,
    SchedulerSnapshot,
    SchedulerState,
    SourceRecordReference,
    TernaryStateValue,
    TransitionClassification,
    TransitionModelError,
    TransitionRecord,
    classify_transition,
)


_SCHEMA_IDENTIFIER = "frp.m15.cycle_exact_reference_trace.v1.7.0"
_STATE_ENCODING = "frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0"
_SOURCE_SHA256 = "ef" * 32


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-transition-model-test:{label}"))


def _location(index: int, field_name: str) -> SourceLocation:
    return SourceLocation(
        json_path=f"$.trace[{index}].{field_name}",
        source_record_ordinal=index + 1,
    )


def _reference(
    index: int = 0,
    *,
    tick: int | None = None,
) -> SourceRecordReference:
    source_tick = index if tick is None else tick
    return SourceRecordReference(
        normalized_record_id=_record_id(f"source-{index}"),
        source_artifact_id=_record_id("source-artifact"),
        trace_dataset_id=_record_id("trace-dataset"),
        registry_binding_id=_record_id("registry-binding"),
        validation_report_id=_record_id("validation-report"),
        source_sha256=_SOURCE_SHA256,
        source_ordinal=index,
        tick=source_tick,
        validation_status=ValidationStatus.RECOGNIZED_VALID,
        source_locations=(_location(index, "tick"),),
        schema_identifier=_SCHEMA_IDENTIFIER,
    )


def _source_state(
    label: str,
    reference: SourceRecordReference,
    *,
    cell_id: int,
    state: CanonicalTernaryState,
) -> TernaryStateValue:
    return TernaryStateValue(
        state_value_id=_record_id(label),
        source_reference=reference,
        cell_id=cell_id,
        source_value=int(state),
        source_encoding="canonical_balanced_ternary",
        canonical_state=state,
        origin=RecordOrigin.UPSTREAM_SOURCE,
    )


def _scheduler_field(
    label: str,
    reference: SourceRecordReference,
    *,
    field: SchedulerField,
    value: SchedulerMode | SchedulerState,
) -> SchedulerFieldValue:
    return SchedulerFieldValue(
        scheduler_field_value_id=_record_id(label),
        source_reference=reference,
        field=field,
        source_value=value.value,
        normalized_value=value,
        source_location=_location(
            reference.source_ordinal,
            field.value,
        ),
        origin=RecordOrigin.UPSTREAM_SOURCE,
        published_name=(
            value.value if field is SchedulerField.STATE else None
        ),
    )


class CanonicalTransitionTests(unittest.TestCase):
    """Exercise the canonical domain and transition evidence."""

    def test_canonical_domain_uses_unsigned_positive_display(self) -> None:
        display_values = tuple(
            state.display_value for state in CanonicalTernaryState
        )

        self.assertEqual(CANONICAL_TERNARY_DOMAIN, (-1, 0, 1))
        self.assertEqual(display_values, ("-1", "0", "1"))
        self.assertNotIn("+1", display_values)

    def test_source_reference_requires_one_valid_contract(self) -> None:
        reference = _reference()

        self.assertEqual(reference.schema_identifier, _SCHEMA_IDENTIFIER)
        self.assertIsNone(reference.format_identifier)
        with self.assertRaisesRegex(
            TransitionModelError,
            "exactly one source contract identifier is required",
        ):
            replace(
                reference,
                format_identifier="frp.m15.vector.v1",
            )
        with self.assertRaisesRegex(
            TransitionModelError,
            "source records must be valid before visualization",
        ):
            replace(
                reference,
                validation_status=ValidationStatus.RECOGNIZED_INVALID,
            )

    def test_state_values_separate_source_and_normalized_origins(
        self,
    ) -> None:
        reference = _reference()
        source_state = _source_state(
            "source-state",
            reference,
            cell_id=0,
            state=CanonicalTernaryState.NEGATIVE,
        )
        normalized_state = TernaryStateValue(
            state_value_id=_record_id("normalized-state"),
            source_reference=reference,
            cell_id=1,
            source_value=3,
            source_encoding="two_bit_hardware_state",
            canonical_state=CanonicalTernaryState.NEGATIVE,
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            encoding_map_identifier=_STATE_ENCODING,
        )

        self.assertEqual(source_state.source_value, -1)
        self.assertEqual(normalized_state.source_value, 3)
        self.assertIs(
            normalized_state.canonical_state,
            CanonicalTernaryState.NEGATIVE,
        )
        with self.assertRaisesRegex(
            TransitionModelError,
            "normalized states require an encoding-map identifier",
        ):
            replace(
                normalized_state,
                encoding_map_identifier=None,
            )

        with self.assertRaisesRegex(
            TransitionModelError,
            "source-origin states must already use canonical values",
        ):
            replace(
                source_state,
                source_value=3,
            )

    def test_classification_follows_exact_state_pair(self) -> None:
        cases = (
            (
                CanonicalTernaryState.NEGATIVE,
                CanonicalTernaryState.NEUTRAL,
                TransitionClassification.POLARITY_TO_NEUTRAL,
            ),
            (
                CanonicalTernaryState.NEUTRAL,
                CanonicalTernaryState.POSITIVE,
                TransitionClassification.NEUTRAL_TO_POLARITY,
            ),
            (
                CanonicalTernaryState.NEGATIVE,
                CanonicalTernaryState.POSITIVE,
                TransitionClassification.OBSERVED_OPPOSITE_POLARITY,
            ),
        )
        for source_state, target_state, expected in cases:
            with self.subTest(
                source_state=source_state,
                target_state=target_state,
            ):
                self.assertIs(
                    classify_transition(source_state, target_state),
                    expected,
                )

    def test_route_legs_require_published_route_evidence(self) -> None:
        route_event_id = _record_id("pending-route")
        transition = TransitionRecord(
            transition_record_id=_record_id("neutralization"),
            source_references=(_reference(),),
            cell_id=0,
            source_tick=0,
            target_tick=0,
            source_state=CanonicalTernaryState.NEGATIVE,
            target_state=CanonicalTernaryState.NEUTRAL,
            classification=(
                TransitionClassification.POLARITY_TO_NEUTRAL
            ),
            route_leg=(
                RouteLegClassification.FIRST_LEG_NEUTRALIZATION
            ),
            origin=RecordOrigin.UPSTREAM_SOURCE,
            related_route_event_ids=(route_event_id,),
        )

        self.assertEqual(
            transition.related_route_event_ids,
            (route_event_id,),
        )

        with self.assertRaisesRegex(
            TransitionModelError,
            "route-leg classifications require route-event evidence",
        ):
            replace(
                transition,
                related_route_event_ids=(),
            )

        with self.assertRaisesRegex(
            TransitionModelError,
            "classification does not match the canonical state pair",
        ):
            replace(
                transition,
                classification=(
                    TransitionClassification.NEUTRAL_TO_POLARITY
                ),
            )

    def test_derived_transition_requires_derivation_record(self) -> None:
        transition = TransitionRecord(
            transition_record_id=_record_id("derived-transition"),
            source_references=(_reference(),),
            cell_id=0,
            source_tick=0,
            target_tick=1,
            source_state=CanonicalTernaryState.NEUTRAL,
            target_state=CanonicalTernaryState.POSITIVE,
            classification=(
                TransitionClassification.NEUTRAL_TO_POLARITY
            ),
            route_leg=RouteLegClassification.NON_ROUTE,
            origin=RecordOrigin.OBSERVATORY_DERIVED,
            derivation_record_id=_record_id("derivation"),
            derivation_operation=(
                "correlate adjacent validated source records"
            ),
        )

        self.assertEqual(
            transition.derivation_operation,
            "correlate adjacent validated source records",
        )
        with self.assertRaisesRegex(
            TransitionModelError,
            "derived transitions require a derivation record",
        ):
            replace(
                transition,
                derivation_record_id=None,
            )


class RequestRouteTests(unittest.TestCase):
    """Exercise request decisions and pending-route timing."""

    def test_request_decisions_remain_source_backed(self) -> None:
        reference = _reference()
        accepted = RequestLaneRecord(
            request_lane_record_id=_record_id("accepted-request"),
            source_reference=reference,
            lane_index=0,
            valid=True,
            acceptance_status=RequestAcceptanceStatus.ACCEPTED,
            origin=RecordOrigin.UPSTREAM_SOURCE,
            cell_id=0,
            source_target_state=1,
            canonical_target_state=CanonicalTernaryState.POSITIVE,
            scheduler_decision="accepted",
            decision_location=_location(0, "request_status"),
        )
        rejected = RequestLaneRecord(
            request_lane_record_id=_record_id("rejected-request"),
            source_reference=reference,
            lane_index=1,
            valid=True,
            acceptance_status=RequestAcceptanceStatus.REJECTED,
            origin=RecordOrigin.UPSTREAM_SOURCE,
            cell_id=1,
            source_target_state=-1,
            canonical_target_state=CanonicalTernaryState.NEGATIVE,
            rejection_reason="transition_capacity_deferral",
            capacity_decision="deferred",
            decision_location=_location(0, "request_status"),
        )

        self.assertIs(
            accepted.acceptance_status,
            RequestAcceptanceStatus.ACCEPTED,
        )
        self.assertEqual(
            rejected.rejection_reason,
            "transition_capacity_deferral",
        )

        with self.assertRaisesRegex(
            RequestRouteModelError,
            "invalid lanes cannot carry accepted or rejected status",
        ):
            replace(
                accepted,
                valid=False,
            )

        with self.assertRaisesRegex(
            RequestRouteModelError,
            "published decisions require a source location",
        ):
            replace(
                rejected,
                decision_location=None,
            )

    def test_normalized_request_target_requires_encoding_map(self) -> None:
        normalized = RequestLaneRecord(
            request_lane_record_id=_record_id("normalized-request"),
            source_reference=_reference(),
            lane_index=0,
            valid=True,
            acceptance_status=RequestAcceptanceStatus.NOT_RECORDED,
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            cell_id=0,
            source_target_state=3,
            canonical_target_state=CanonicalTernaryState.NEGATIVE,
            encoding_map_identifier=_STATE_ENCODING,
        )

        self.assertEqual(normalized.source_target_state, 3)
        with self.assertRaisesRegex(
            RequestRouteModelError,
            "normalized targets require an encoding-map identifier",
        ):
            replace(
                normalized,
                encoding_map_identifier=None,
            )

    def test_pending_and_applied_routes_enforce_ready_tick(self) -> None:
        pending = RouteEventRecord(
            route_event_record_id=_record_id("pending-route"),
            source_reference=_reference(0, tick=0),
            cell_id=0,
            source_target_state=1,
            canonical_target_state=CanonicalTernaryState.POSITIVE,
            ready_tick=1,
            route_status=RouteStatus.PENDING,
            origin=RecordOrigin.UPSTREAM_SOURCE,
        )
        applied = RouteEventRecord(
            route_event_record_id=_record_id("applied-route"),
            source_reference=_reference(1, tick=1),
            cell_id=0,
            source_target_state=1,
            canonical_target_state=CanonicalTernaryState.POSITIVE,
            ready_tick=1,
            route_status=RouteStatus.APPLIED,
            origin=RecordOrigin.UPSTREAM_SOURCE,
        )

        self.assertGreater(pending.ready_tick, pending.source_reference.tick)
        self.assertLessEqual(applied.ready_tick, applied.source_reference.tick)

        with self.assertRaisesRegex(
            RequestRouteModelError,
            "pending routes require a future ready_tick",
        ):
            replace(
                pending,
                ready_tick=0,
            )

        with self.assertRaisesRegex(
            RequestRouteModelError,
            "applied routes cannot precede ready_tick",
        ):
            replace(
                applied,
                ready_tick=2,
            )


class SchedulerRecordTests(unittest.TestCase):
    """Exercise scheduler state and mode bindings."""

    def test_snapshot_retains_registered_state_and_mode(self) -> None:
        reference = _reference()
        snapshot = SchedulerSnapshot(
            scheduler_snapshot_id=_record_id("scheduler-snapshot"),
            source_reference=reference,
            state=_scheduler_field(
                "scheduler-state",
                reference,
                field=SchedulerField.STATE,
                value=SchedulerState.BALANCE,
            ),
            mode=_scheduler_field(
                "scheduler-mode",
                reference,
                field=SchedulerField.MODE,
                value=SchedulerMode.BALANCE_COMMIT,
            ),
        )

        self.assertIs(snapshot.scheduler_state, SchedulerState.BALANCE)
        self.assertIs(
            snapshot.scheduler_mode,
            SchedulerMode.BALANCE_COMMIT,
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(snapshot, "mode", None)

    def test_normalized_scheduler_value_requires_encoding_map(
        self,
    ) -> None:
        reference = _reference()
        normalized = SchedulerFieldValue(
            scheduler_field_value_id=_record_id(
                "normalized-scheduler-state"
            ),
            source_reference=reference,
            field=SchedulerField.STATE,
            source_value=1,
            normalized_value=SchedulerState.BALANCE,
            source_location=_location(0, "scheduler_state"),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            encoding_map_identifier=_STATE_ENCODING,
        )

        self.assertEqual(normalized.source_value, 1)
        with self.assertRaisesRegex(
            SchedulerModelError,
            "normalized scheduler values require an encoding map",
        ):
            replace(
                normalized,
                encoding_map_identifier=None,
            )

        with self.assertRaisesRegex(
            SchedulerModelError,
            "scheduler state requires a SchedulerState value",
        ):
            replace(
                normalized,
                normalized_value=SchedulerMode.FREE,
            )


if __name__ == "__main__":
    unittest.main()
