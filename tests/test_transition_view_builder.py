"""Tests for deterministic transition visualizer view construction."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)
from schemas.registry import MeasurementContour
from transition_visualizer import (
    OBSERVATORY_DERIVED_LABEL,
    CanonicalTernaryState,
    EventTypeField,
    RecordOrigin,
    RequestAcceptanceStatus,
    RequestLaneRecord,
    RouteEventRecord,
    RouteLegClassification,
    RouteStatus,
    SchedulerField,
    SchedulerFieldValue,
    SchedulerMode,
    SchedulerSnapshot,
    SchedulerState,
    SourceRecordReference,
    TickField,
    TransitionClassification,
    TransitionRecord,
    TransitionViewBuilder,
    TransitionViewBuilderError,
    TransitionViewType,
    TransitionVisualizerDataset,
    ViewBuildContext,
    VisualizerRecordType,
)


_SCHEMA_IDENTIFIER = "frp.m15.cycle_exact_reference_trace.v1.7.0"
_SOURCE_SHA256 = "cd" * 32


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-transition-view-test:{label}"))


def _location(index: int, field_name: str) -> SourceLocation:
    return SourceLocation(
        json_path=f"$.trace[{index}].{field_name}",
        source_record_ordinal=index + 1,
    )


def _source_reference(
    index: int,
    tick: int,
) -> SourceRecordReference:
    return SourceRecordReference(
        normalized_record_id=_record_id(f"source-{index}"),
        source_artifact_id=_record_id("source-artifact"),
        trace_dataset_id=_record_id("trace-dataset"),
        registry_binding_id=_record_id("registry-binding"),
        validation_report_id=_record_id("validation-report"),
        source_sha256=_SOURCE_SHA256,
        source_ordinal=index,
        tick=tick,
        validation_status=ValidationStatus.RECOGNIZED_VALID,
        source_locations=(_location(index, "tick"),),
        schema_identifier=_SCHEMA_IDENTIFIER,
    )


def _route_events(
    references: tuple[SourceRecordReference, ...],
) -> tuple[RouteEventRecord, ...]:
    return (
        RouteEventRecord(
            route_event_record_id=_record_id("route-pending"),
            source_reference=references[0],
            cell_id=0,
            source_target_state=1,
            canonical_target_state=CanonicalTernaryState.POSITIVE,
            ready_tick=1,
            route_status=RouteStatus.PENDING,
            origin=RecordOrigin.UPSTREAM_SOURCE,
            route_index=0,
            related_transition_ids=(
                _record_id("transition-neutralization"),
            ),
        ),
        RouteEventRecord(
            route_event_record_id=_record_id("route-applied"),
            source_reference=references[1],
            cell_id=0,
            source_target_state=1,
            canonical_target_state=CanonicalTernaryState.POSITIVE,
            ready_tick=1,
            route_status=RouteStatus.APPLIED,
            origin=RecordOrigin.UPSTREAM_SOURCE,
            route_index=0,
            related_transition_ids=(
                _record_id("transition-completion"),
            ),
        ),
    )


def _transitions(
    references: tuple[SourceRecordReference, ...],
) -> tuple[TransitionRecord, ...]:
    return (
        TransitionRecord(
            transition_record_id=(
                _record_id("transition-neutralization")
            ),
            source_references=(references[0],),
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
            related_route_event_ids=(
                _record_id("route-pending"),
            ),
        ),
        TransitionRecord(
            transition_record_id=_record_id("transition-completion"),
            source_references=(references[1],),
            cell_id=0,
            source_tick=1,
            target_tick=1,
            source_state=CanonicalTernaryState.NEUTRAL,
            target_state=CanonicalTernaryState.POSITIVE,
            classification=(
                TransitionClassification.NEUTRAL_TO_POLARITY
            ),
            route_leg=(
                RouteLegClassification.PENDING_ROUTE_COMPLETION
            ),
            origin=RecordOrigin.UPSTREAM_SOURCE,
            related_route_event_ids=(
                _record_id("route-applied"),
            ),
        ),
        TransitionRecord(
            transition_record_id=_record_id("transition-retention"),
            source_references=(references[1],),
            cell_id=1,
            source_tick=1,
            target_tick=1,
            source_state=CanonicalTernaryState.NEUTRAL,
            target_state=CanonicalTernaryState.NEUTRAL,
            classification=(
                TransitionClassification.SAME_STATE_RETENTION
            ),
            route_leg=RouteLegClassification.NON_ROUTE,
            origin=RecordOrigin.UPSTREAM_SOURCE,
        ),
    )


def _request_lanes(
    references: tuple[SourceRecordReference, ...],
) -> tuple[RequestLaneRecord, ...]:
    return (
        RequestLaneRecord(
            request_lane_record_id=_record_id("request-accepted"),
            source_reference=references[0],
            lane_index=0,
            valid=True,
            acceptance_status=RequestAcceptanceStatus.ACCEPTED,
            origin=RecordOrigin.UPSTREAM_SOURCE,
            cell_id=0,
            source_target_state=1,
            canonical_target_state=CanonicalTernaryState.POSITIVE,
            decision_location=_location(0, "request_status"),
        ),
        RequestLaneRecord(
            request_lane_record_id=_record_id("request-rejected"),
            source_reference=references[1],
            lane_index=1,
            valid=True,
            acceptance_status=RequestAcceptanceStatus.REJECTED,
            origin=RecordOrigin.UPSTREAM_SOURCE,
            cell_id=1,
            source_target_state=-1,
            canonical_target_state=CanonicalTernaryState.NEGATIVE,
            rejection_reason="scheduler_deferral",
            scheduler_decision="deferred",
            decision_location=_location(1, "request_status"),
        ),
    )


def _scheduler_field(
    reference: SourceRecordReference,
    *,
    index: int,
    field: SchedulerField,
    value: SchedulerMode | SchedulerState,
) -> SchedulerFieldValue:
    return SchedulerFieldValue(
        scheduler_field_value_id=_record_id(
            f"scheduler-{index}-{field.value}"
        ),
        source_reference=reference,
        field=field,
        source_value=value.value,
        normalized_value=value,
        source_location=_location(index, field.value),
        origin=RecordOrigin.UPSTREAM_SOURCE,
        published_name=(
            value.value if field is SchedulerField.STATE else None
        ),
    )


def _scheduler_snapshots(
    references: tuple[SourceRecordReference, ...],
) -> tuple[SchedulerSnapshot, ...]:
    states = (
        SchedulerState.BALANCE,
        SchedulerState.COMMIT,
    )
    return tuple(
        SchedulerSnapshot(
            scheduler_snapshot_id=_record_id(
                f"scheduler-snapshot-{index}"
            ),
            source_reference=reference,
            state=_scheduler_field(
                reference,
                index=index,
                field=SchedulerField.STATE,
                value=states[index],
            ),
            mode=_scheduler_field(
                reference,
                index=index,
                field=SchedulerField.MODE,
                value=SchedulerMode.BALANCE_COMMIT,
            ),
        )
        for index, reference in enumerate(references)
    )


def _dataset() -> TransitionVisualizerDataset:
    references = (
        _source_reference(0, 0),
        _source_reference(1, 1),
    )
    return TransitionVisualizerDataset(
        visualizer_dataset_id=_record_id("visualizer-dataset"),
        trace_dataset_id=_record_id("trace-dataset"),
        measurement_contour=(
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        source_references=references,
        transitions=_transitions(references),
        scheduler_snapshots=_scheduler_snapshots(references),
        request_lanes=_request_lanes(references),
        route_events=_route_events(references),
        validation_check_ids=(_record_id("dataset-check"),),
    )


def _builder() -> TransitionViewBuilder:
    return TransitionViewBuilder(
        source_dataset=_dataset(),
        context=ViewBuildContext(
            derived_view_id=_record_id("derived-view"),
            created_at=datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
            registry_revision="v1.8.0-audit",
            observatory_version="0.1.0",
            validation_check_ids=(_record_id("context-check"),),
        ),
    )


class TransitionViewBuilderTests(unittest.TestCase):
    """Exercise source-preserving filters and projections."""

    def test_tick_and_cell_filters_preserve_source_order(self) -> None:
        builder = _builder()
        transitions_before = builder.source_dataset.transitions
        tick_view = builder.tick_filter(
            VisualizerRecordType.TRANSITION,
            (1,),
        )
        cell_view = builder.cell_filter(
            VisualizerRecordType.TRANSITION,
            (1,),
        )

        self.assertEqual(
            tick_view.output_record_ids,
            (
                _record_id("transition-completion"),
                _record_id("transition-retention"),
            ),
        )
        self.assertEqual(
            cell_view.output_record_ids,
            (_record_id("transition-retention"),),
        )
        self.assertTrue(tick_view.source_order_preserved)
        self.assertIs(
            tick_view.view_type,
            TransitionViewType.TICK_FILTER,
        )
        self.assertEqual(
            tick_view.derived_label,
            OBSERVATORY_DERIVED_LABEL,
        )
        self.assertIs(
            builder.source_dataset.transitions,
            transitions_before,
        )
        self.assertIs(tick_view.source_dataset, builder.source_dataset)
        with self.assertRaises(FrozenInstanceError):
            setattr(tick_view, "source_order_preserved", False)

    def test_request_and_scheduler_filters_keep_types_separate(
        self,
    ) -> None:
        builder = _builder()
        request_view = builder.request_lane_filter((1,))
        scheduler_view = builder.scheduler_state_filter(
            (SchedulerState.COMMIT,)
        )

        self.assertIs(
            request_view.record_type,
            VisualizerRecordType.REQUEST_LANE,
        )
        self.assertEqual(
            request_view.output_record_ids,
            (_record_id("request-rejected"),),
        )
        self.assertIs(
            scheduler_view.record_type,
            VisualizerRecordType.SCHEDULER_SNAPSHOT,
        )
        self.assertEqual(
            scheduler_view.output_record_ids,
            (_record_id("scheduler-snapshot-1"),),
        )

    def test_event_and_state_filters_use_registered_values(self) -> None:
        builder = _builder()
        event_view = builder.event_type_filter(
            EventTypeField.REQUEST_ACCEPTANCE_STATUS,
            (RequestAcceptanceStatus.REJECTED.value,),
        )
        state_view = builder.state_transition_projection(
            (CanonicalTernaryState.NEUTRAL,),
            (CanonicalTernaryState.POSITIVE,),
        )

        self.assertEqual(
            event_view.output_record_ids,
            (_record_id("request-rejected"),),
        )
        self.assertEqual(
            state_view.output_record_ids,
            (_record_id("transition-completion"),),
        )
        parameters = {
            parameter.name: parameter.value
            for parameter in state_view.parameters
        }
        self.assertEqual(parameters["source_states"], (0,))
        self.assertEqual(parameters["target_states"], (1,))

    def test_projection_records_explicit_order_semantics(self) -> None:
        builder = _builder()
        transition_ids = builder.source_dataset.record_ids(
            VisualizerRecordType.TRANSITION
        )
        source_view = builder.source_order_projection(
            VisualizerRecordType.TRANSITION,
            tuple(reversed(transition_ids)),
        )
        sorted_view = builder.record_id_sorted_projection(
            VisualizerRecordType.TRANSITION,
            descending=True,
        )

        self.assertEqual(
            source_view.output_record_ids,
            transition_ids,
        )
        self.assertTrue(source_view.source_order_preserved)
        self.assertEqual(
            sorted_view.output_record_ids,
            tuple(sorted(transition_ids, reverse=True)),
        )
        self.assertFalse(sorted_view.source_order_preserved)
        self.assertIs(
            sorted_view.view_type,
            TransitionViewType.EXPLICITLY_SORTED_PROJECTION,
        )

    def test_route_correlation_retains_published_provenance(self) -> None:
        builder = _builder()
        pending_route_id = _record_id("route-pending")
        view = builder.trace_to_route_correlation(
            (pending_route_id,)
        )

        self.assertEqual(
            view.output_record_ids,
            (_record_id("transition-neutralization"),),
        )
        self.assertEqual(
            view.source_artifact_ids,
            (_record_id("source-artifact"),),
        )
        self.assertEqual(
            view.normalized_record_ids,
            (
                _record_id("source-0"),
                _record_id("source-1"),
            ),
        )
        self.assertEqual(
            view.validation_check_ids,
            (
                _record_id("dataset-check"),
                _record_id("context-check"),
            ),
        )

    def test_invalid_filter_contracts_are_rejected(self) -> None:
        builder = _builder()

        with self.assertRaisesRegex(
            TransitionViewBuilderError,
            "target_tick is available only for transition records",
        ):
            builder.tick_filter(
                VisualizerRecordType.ROUTE_EVENT,
                (1,),
                tick_field=TickField.TARGET_TICK,
            )

        with self.assertRaisesRegex(
            TransitionViewBuilderError,
            "outside the registered field",
        ):
            builder.event_type_filter(
                EventTypeField.ROUTE_STATUS,
                ("scheduler_deferral",),
            )

        with self.assertRaisesRegex(
            TransitionViewBuilderError,
            "event outside the dataset",
        ):
            builder.trace_to_route_correlation(
                (_record_id("unknown-route"),)
            )

        with self.assertRaisesRegex(
            TransitionViewBuilderError,
            "source_states must not contain duplicates",
        ):
            builder.state_transition_projection(
                (
                    CanonicalTernaryState.NEUTRAL,
                    CanonicalTernaryState.NEUTRAL,
                ),
                (CanonicalTernaryState.POSITIVE,),
            )


if __name__ == "__main__":
    unittest.main()
