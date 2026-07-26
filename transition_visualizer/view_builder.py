"""Deterministic read-only builders for transition visualizer views."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from transition_visualizer.invariant_model import InvariantVectorRecord
from transition_visualizer.request_route_model import (
    RequestAcceptanceStatus,
    RequestLaneRecord,
    RouteEventRecord,
    RouteStatus,
)
from transition_visualizer.scheduler_model import (
    SchedulerSnapshot,
    SchedulerState,
)
from transition_visualizer.telemetry_model import (
    EventCounterName,
    EventCounterSnapshot,
    TransitionTelemetryField,
    TransitionTelemetryRecord,
)
from transition_visualizer.transition_model import (
    CanonicalTernaryState,
    RouteLegClassification,
    SourceRecordReference,
    TernaryStateValue,
    TransitionClassification,
    TransitionRecord,
)
from transition_visualizer.view_model import (
    TransitionViewType,
    TransitionVisualizerDataset,
    TransitionVisualizerView,
    ViewParameter,
    VisualizerRecordType,
)


__all__ = [
    "EventTypeField",
    "TickField",
    "TransitionViewBuilder",
    "TransitionViewBuilderError",
    "ViewBuildContext",
]


class TransitionViewBuilderError(ValueError):
    """Raised when a derived-view operation is not well defined."""


class TickField(StrEnum):
    """Explicit tick fields available to deterministic filters."""

    SOURCE_TICK = "source_tick"
    TARGET_TICK = "target_tick"
    READY_TICK = "ready_tick"


class EventTypeField(StrEnum):
    """Registered event-classification fields kept distinct."""

    TRANSITION_CLASSIFICATION = "transition_classification"
    ROUTE_LEG = "route_leg"
    REQUEST_ACCEPTANCE_STATUS = "request_acceptance_status"
    ROUTE_STATUS = "route_status"
    TELEMETRY_FIELD = "telemetry_field"
    EVENT_COUNTER_NAME = "event_counter_name"


_CELL_RECORD_TYPES = frozenset(
    {
        VisualizerRecordType.STATE_VALUE,
        VisualizerRecordType.TRANSITION,
        VisualizerRecordType.REQUEST_LANE,
        VisualizerRecordType.ROUTE_EVENT,
    }
)

_EVENT_RECORD_TYPES = {
    EventTypeField.TRANSITION_CLASSIFICATION: (
        VisualizerRecordType.TRANSITION
    ),
    EventTypeField.ROUTE_LEG: VisualizerRecordType.TRANSITION,
    EventTypeField.REQUEST_ACCEPTANCE_STATUS: (
        VisualizerRecordType.REQUEST_LANE
    ),
    EventTypeField.ROUTE_STATUS: VisualizerRecordType.ROUTE_EVENT,
    EventTypeField.TELEMETRY_FIELD: (
        VisualizerRecordType.TRANSITION_TELEMETRY
    ),
    EventTypeField.EVENT_COUNTER_NAME: (
        VisualizerRecordType.EVENT_COUNTER_SNAPSHOT
    ),
}

_EVENT_VALUES = {
    EventTypeField.TRANSITION_CLASSIFICATION: frozenset(
        value.value for value in TransitionClassification
    ),
    EventTypeField.ROUTE_LEG: frozenset(
        value.value for value in RouteLegClassification
    ),
    EventTypeField.REQUEST_ACCEPTANCE_STATUS: frozenset(
        value.value for value in RequestAcceptanceStatus
    ),
    EventTypeField.ROUTE_STATUS: frozenset(
        value.value for value in RouteStatus
    ),
    EventTypeField.TELEMETRY_FIELD: frozenset(
        value.value for value in TransitionTelemetryField
    ),
    EventTypeField.EVENT_COUNTER_NAME: frozenset(
        value.value for value in EventCounterName
    ),
}


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TransitionViewBuilderError(
            f"{field_name} must be a string"
        )
    if not value or value != value.strip():
        raise TransitionViewBuilderError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise TransitionViewBuilderError(
            f"{field_name} must not contain NUL"
        )


def _validate_optional_text(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _validate_text(value, field_name)


def _validate_uuid(value: str, field_name: str) -> None:
    _validate_text(value, field_name)
    try:
        UUID(value)
    except (ValueError, AttributeError) as exc:
        raise TransitionViewBuilderError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_uuid_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(values, tuple):
        raise TransitionViewBuilderError(
            f"{field_name} must be a tuple"
        )
    if not allow_empty and not values:
        raise TransitionViewBuilderError(
            f"{field_name} must not be empty"
        )
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise TransitionViewBuilderError(
            f"{field_name} must not contain duplicates"
        )


def _validate_nonnegative_integer_tuple(
    values: tuple[int, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TransitionViewBuilderError(
            f"{field_name} must be a tuple"
        )
    if not values:
        raise TransitionViewBuilderError(
            f"{field_name} must not be empty"
        )
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        for value in values
    ):
        raise TransitionViewBuilderError(
            f"{field_name} must contain nonnegative integers"
        )
    if len(set(values)) != len(values):
        raise TransitionViewBuilderError(
            f"{field_name} must not contain duplicates"
        )


def _validate_string_tuple(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TransitionViewBuilderError(
            f"{field_name} must be a tuple"
        )
    if not values:
        raise TransitionViewBuilderError(
            f"{field_name} must not be empty"
        )
    for value in values:
        _validate_text(value, field_name)
    if len(set(values)) != len(values):
        raise TransitionViewBuilderError(
            f"{field_name} must not contain duplicates"
        )


def _unique_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _unique_references(
    references: tuple[SourceRecordReference, ...],
) -> tuple[SourceRecordReference, ...]:
    result: list[SourceRecordReference] = []
    seen: set[str] = set()
    for reference in references:
        if reference.normalized_record_id not in seen:
            seen.add(reference.normalized_record_id)
            result.append(reference)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ViewBuildContext:
    """Caller-supplied identity and timestamp for one derived view."""

    derived_view_id: str
    created_at: datetime
    registry_revision: str
    observatory_version: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.derived_view_id, "derived_view_id")
        if not isinstance(self.created_at, datetime):
            raise TransitionViewBuilderError(
                "created_at must be a datetime"
            )
        if (
            self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise TransitionViewBuilderError(
                "created_at must be timezone-aware"
            )
        _validate_text(self.registry_revision, "registry_revision")
        _validate_optional_text(
            self.observatory_version,
            "observatory_version",
        )
        _validate_uuid_tuple(
            self.validation_check_ids,
            "validation_check_ids",
            allow_empty=True,
        )


@dataclass(frozen=True, slots=True)
class TransitionViewBuilder:
    """Build one immutable derived view without changing source records."""

    source_dataset: TransitionVisualizerDataset
    context: ViewBuildContext

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_dataset,
            TransitionVisualizerDataset,
        ):
            raise TransitionViewBuilderError(
                "source_dataset must be a TransitionVisualizerDataset"
            )
        if not isinstance(self.context, ViewBuildContext):
            raise TransitionViewBuilderError(
                "context must be a ViewBuildContext"
            )

    def tick_filter(
        self,
        record_type: VisualizerRecordType,
        ticks: tuple[int, ...],
        *,
        tick_field: TickField = TickField.SOURCE_TICK,
    ) -> TransitionVisualizerView:
        """Select records by one explicit published tick field."""

        self._validate_record_type(record_type)
        _validate_nonnegative_integer_tuple(ticks, "ticks")
        if not isinstance(tick_field, TickField):
            raise TransitionViewBuilderError(
                "tick_field must be a TickField"
            )
        self._validate_tick_field(record_type, tick_field)

        tick_set = set(ticks)
        output_record_ids = self._select_record_ids(
            record_type,
            lambda record: self._record_tick(
                record,
                record_type,
                tick_field,
            )
            in tick_set,
        )
        return self._build_view(
            view_type=TransitionViewType.TICK_FILTER,
            record_type=record_type,
            operation="select records by exact published tick value",
            parameters=(
                ViewParameter("tick_field", tick_field.value),
                ViewParameter("ticks", ticks),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def cell_filter(
        self,
        record_type: VisualizerRecordType,
        cell_ids: tuple[int, ...],
    ) -> TransitionVisualizerView:
        """Select cell-addressed records without creating cell values."""

        self._validate_record_type(record_type)
        if record_type not in _CELL_RECORD_TYPES:
            raise TransitionViewBuilderError(
                "record_type does not publish a cell identifier"
            )
        _validate_nonnegative_integer_tuple(cell_ids, "cell_ids")

        cell_id_set = set(cell_ids)
        output_record_ids = self._select_record_ids(
            record_type,
            lambda record: self._record_cell_id(record) in cell_id_set,
        )
        return self._build_view(
            view_type=TransitionViewType.CELL_FILTER,
            record_type=record_type,
            operation="select records by exact published cell identifier",
            parameters=(ViewParameter("cell_ids", cell_ids),),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def request_lane_filter(
        self,
        lane_indices: tuple[int, ...],
    ) -> TransitionVisualizerView:
        """Select request-lane records by published lane index."""

        _validate_nonnegative_integer_tuple(
            lane_indices,
            "lane_indices",
        )
        lane_index_set = set(lane_indices)
        output_record_ids = self._select_record_ids(
            VisualizerRecordType.REQUEST_LANE,
            lambda record: (
                isinstance(record, RequestLaneRecord)
                and record.lane_index in lane_index_set
            ),
        )
        return self._build_view(
            view_type=TransitionViewType.REQUEST_LANE_FILTER,
            record_type=VisualizerRecordType.REQUEST_LANE,
            operation="select request records by published lane index",
            parameters=(
                ViewParameter("lane_indices", lane_indices),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def scheduler_state_filter(
        self,
        states: tuple[SchedulerState, ...],
    ) -> TransitionVisualizerView:
        """Select scheduler snapshots by registered normalized state."""

        if not isinstance(states, tuple) or not states:
            raise TransitionViewBuilderError(
                "states must be a nonempty tuple"
            )
        if any(not isinstance(state, SchedulerState) for state in states):
            raise TransitionViewBuilderError(
                "states must contain SchedulerState values"
            )
        if len(set(states)) != len(states):
            raise TransitionViewBuilderError(
                "states must not contain duplicates"
            )

        state_set = set(states)
        output_record_ids = self._select_record_ids(
            VisualizerRecordType.SCHEDULER_SNAPSHOT,
            lambda record: (
                isinstance(record, SchedulerSnapshot)
                and record.state.normalized_value in state_set
            ),
        )
        return self._build_view(
            view_type=TransitionViewType.SCHEDULER_STATE_FILTER,
            record_type=VisualizerRecordType.SCHEDULER_SNAPSHOT,
            operation=(
                "select scheduler snapshots by registered normalized state"
            ),
            parameters=(
                ViewParameter(
                    "scheduler_states",
                    tuple(state.value for state in states),
                ),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def event_type_filter(
        self,
        event_field: EventTypeField,
        event_values: tuple[str, ...],
    ) -> TransitionVisualizerView:
        """Select records using one registered event field."""

        if not isinstance(event_field, EventTypeField):
            raise TransitionViewBuilderError(
                "event_field must be an EventTypeField"
            )
        _validate_string_tuple(event_values, "event_values")
        allowed_values = _EVENT_VALUES[event_field]
        if any(value not in allowed_values for value in event_values):
            raise TransitionViewBuilderError(
                "event_values contain a value outside the registered field"
            )

        record_type = _EVENT_RECORD_TYPES[event_field]
        event_value_set = set(event_values)
        output_record_ids = self._select_record_ids(
            record_type,
            lambda record: bool(
                self._record_event_values(record, event_field)
                & event_value_set
            ),
        )
        return self._build_view(
            view_type=TransitionViewType.EVENT_TYPE_FILTER,
            record_type=record_type,
            operation="select records by exact registered event value",
            parameters=(
                ViewParameter("event_field", event_field.value),
                ViewParameter("event_values", event_values),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def source_order_projection(
        self,
        record_type: VisualizerRecordType,
        record_ids: tuple[str, ...],
    ) -> TransitionVisualizerView:
        """Project explicit records in their retained source order."""

        self._validate_record_type(record_type)
        _validate_uuid_tuple(
            record_ids,
            "record_ids",
            allow_empty=True,
        )
        available_ids = self.source_dataset.record_ids(record_type)
        available_set = set(available_ids)
        if any(record_id not in available_set for record_id in record_ids):
            raise TransitionViewBuilderError(
                "record_ids contain a record outside the typed collection"
            )
        selected_set = set(record_ids)
        output_record_ids = tuple(
            record_id
            for record_id in available_ids
            if record_id in selected_set
        )
        return self._build_view(
            view_type=(
                TransitionViewType.SOURCE_ORDER_PRESERVING_PROJECTION
            ),
            record_type=record_type,
            operation="project explicit records in retained source order",
            parameters=(ViewParameter("record_ids", record_ids),),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def record_id_sorted_projection(
        self,
        record_type: VisualizerRecordType,
        *,
        descending: bool = False,
    ) -> TransitionVisualizerView:
        """Project one typed collection in explicit record-id order."""

        self._validate_record_type(record_type)
        if not isinstance(descending, bool):
            raise TransitionViewBuilderError(
                "descending must be a bool"
            )
        output_record_ids = tuple(
            sorted(
                self.source_dataset.record_ids(record_type),
                reverse=descending,
            )
        )
        return self._build_view(
            view_type=(
                TransitionViewType.EXPLICITLY_SORTED_PROJECTION
            ),
            record_type=record_type,
            operation="sort records lexically by immutable record identifier",
            parameters=(
                ViewParameter("sort_key", "record_id"),
                ViewParameter("descending", descending),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=False,
        )

    def state_transition_projection(
        self,
        source_states: tuple[CanonicalTernaryState, ...],
        target_states: tuple[CanonicalTernaryState, ...],
    ) -> TransitionVisualizerView:
        """Select transitions by exact canonical source and target states."""

        self._validate_state_tuple(source_states, "source_states")
        self._validate_state_tuple(target_states, "target_states")
        source_state_set = set(source_states)
        target_state_set = set(target_states)
        output_record_ids = self._select_record_ids(
            VisualizerRecordType.TRANSITION,
            lambda record: (
                isinstance(record, TransitionRecord)
                and record.source_state in source_state_set
                and record.target_state in target_state_set
            ),
        )
        return self._build_view(
            view_type=TransitionViewType.STATE_TRANSITION_PROJECTION,
            record_type=VisualizerRecordType.TRANSITION,
            operation=(
                "select transitions by exact canonical state pair"
            ),
            parameters=(
                ViewParameter(
                    "source_states",
                    tuple(int(state) for state in source_states),
                ),
                ViewParameter(
                    "target_states",
                    tuple(int(state) for state in target_states),
                ),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
        )

    def trace_to_route_correlation(
        self,
        route_event_ids: tuple[str, ...],
    ) -> TransitionVisualizerView:
        """Select transitions with published links to route events."""

        _validate_uuid_tuple(
            route_event_ids,
            "route_event_ids",
            allow_empty=False,
        )
        available_route_ids = set(
            self.source_dataset.record_ids(
                VisualizerRecordType.ROUTE_EVENT
            )
        )
        if any(
            route_event_id not in available_route_ids
            for route_event_id in route_event_ids
        ):
            raise TransitionViewBuilderError(
                "route_event_ids contain an event outside the dataset"
            )

        route_event_id_set = set(route_event_ids)
        output_record_ids = self._select_record_ids(
            VisualizerRecordType.TRANSITION,
            lambda record: (
                isinstance(record, TransitionRecord)
                and bool(
                    set(record.related_route_event_ids)
                    & route_event_id_set
                )
            ),
        )
        return self._build_view(
            view_type=TransitionViewType.TRACE_TO_ROUTE_CORRELATION,
            record_type=VisualizerRecordType.TRANSITION,
            operation=(
                "select transitions with published route-event links"
            ),
            parameters=(
                ViewParameter("route_event_ids", route_event_ids),
            ),
            output_record_ids=output_record_ids,
            source_order_preserved=True,
            additional_record_groups=(
                (
                    VisualizerRecordType.ROUTE_EVENT,
                    route_event_ids,
                ),
            ),
        )

    def _build_view(
        self,
        *,
        view_type: TransitionViewType,
        record_type: VisualizerRecordType,
        operation: str,
        parameters: tuple[ViewParameter, ...],
        output_record_ids: tuple[str, ...],
        source_order_preserved: bool,
        additional_record_groups: tuple[
            tuple[VisualizerRecordType, tuple[str, ...]],
            ...,
        ] = (),
    ) -> TransitionVisualizerView:
        candidate_record_ids = self.source_dataset.record_ids(
            record_type
        )
        references = self.source_dataset.references_for_records(
            record_type,
            candidate_record_ids,
        )
        for additional_type, additional_ids in additional_record_groups:
            references += self.source_dataset.references_for_records(
                additional_type,
                additional_ids,
            )
        references = _unique_references(references)

        source_artifact_ids = _unique_strings(
            tuple(
                reference.source_artifact_id
                for reference in references
            )
        )
        if not source_artifact_ids:
            source_artifact_ids = (
                self.source_dataset.source_artifact_ids
            )
        normalized_record_ids = tuple(
            reference.normalized_record_id
            for reference in references
        )
        validation_check_ids = _unique_strings(
            self.source_dataset.validation_check_ids
            + self.context.validation_check_ids
        )

        return TransitionVisualizerView(
            derived_view_id=self.context.derived_view_id,
            source_dataset=self.source_dataset,
            view_type=view_type,
            record_type=record_type,
            operation=operation,
            parameters=parameters,
            created_at=self.context.created_at,
            registry_revision=self.context.registry_revision,
            source_artifact_ids=source_artifact_ids,
            normalized_record_ids=normalized_record_ids,
            output_record_ids=output_record_ids,
            source_order_preserved=source_order_preserved,
            observatory_version=self.context.observatory_version,
            validation_check_ids=validation_check_ids,
        )

    def _select_record_ids(
        self,
        record_type: VisualizerRecordType,
        predicate: Callable[[object], bool],
    ) -> tuple[str, ...]:
        if not callable(predicate):
            raise TransitionViewBuilderError(
                "predicate must be callable"
            )
        records = self.source_dataset.records(record_type)
        record_ids = self.source_dataset.record_ids(record_type)
        return tuple(
            record_id
            for record_id, record in zip(
                record_ids,
                records,
                strict=True,
            )
            if predicate(record)
        )

    @staticmethod
    def _validate_record_type(
        record_type: VisualizerRecordType,
    ) -> None:
        if not isinstance(record_type, VisualizerRecordType):
            raise TransitionViewBuilderError(
                "record_type must be a VisualizerRecordType"
            )

    @staticmethod
    def _validate_tick_field(
        record_type: VisualizerRecordType,
        tick_field: TickField,
    ) -> None:
        if (
            tick_field is TickField.TARGET_TICK
            and record_type is not VisualizerRecordType.TRANSITION
        ):
            raise TransitionViewBuilderError(
                "target_tick is available only for transition records"
            )
        if (
            tick_field is TickField.READY_TICK
            and record_type is not VisualizerRecordType.ROUTE_EVENT
        ):
            raise TransitionViewBuilderError(
                "ready_tick is available only for route-event records"
            )

    @staticmethod
    def _record_tick(
        record: object,
        record_type: VisualizerRecordType,
        tick_field: TickField,
    ) -> int:
        if tick_field is TickField.TARGET_TICK:
            if not isinstance(record, TransitionRecord):
                raise TransitionViewBuilderError(
                    "transition record required for target_tick"
                )
            return record.target_tick
        if tick_field is TickField.READY_TICK:
            if not isinstance(record, RouteEventRecord):
                raise TransitionViewBuilderError(
                    "route-event record required for ready_tick"
                )
            return record.ready_tick
        if isinstance(record, TransitionRecord):
            return record.source_tick
        if isinstance(record, TernaryStateValue):
            return record.source_reference.tick
        if isinstance(record, SchedulerSnapshot):
            return record.source_reference.tick
        if isinstance(record, RequestLaneRecord):
            return record.source_reference.tick
        if isinstance(record, RouteEventRecord):
            return record.source_reference.tick
        if isinstance(record, TransitionTelemetryRecord):
            return record.tick_reference.tick
        if isinstance(record, EventCounterSnapshot):
            return record.source_reference.tick
        if isinstance(record, InvariantVectorRecord):
            return record.source_reference.tick
        raise TransitionViewBuilderError(
            f"unsupported source tick for {record_type.value}"
        )

    @staticmethod
    def _record_cell_id(record: object) -> int | None:
        if isinstance(
            record,
            (
                TernaryStateValue,
                TransitionRecord,
                RequestLaneRecord,
                RouteEventRecord,
            ),
        ):
            return record.cell_id
        raise TransitionViewBuilderError(
            "record does not publish a cell identifier"
        )

    @staticmethod
    def _record_event_values(
        record: object,
        event_field: EventTypeField,
    ) -> frozenset[str]:
        if (
            event_field is EventTypeField.TRANSITION_CLASSIFICATION
            and isinstance(record, TransitionRecord)
        ):
            return frozenset({record.classification.value})
        if (
            event_field is EventTypeField.ROUTE_LEG
            and isinstance(record, TransitionRecord)
        ):
            return frozenset({record.route_leg.value})
        if (
            event_field is EventTypeField.REQUEST_ACCEPTANCE_STATUS
            and isinstance(record, RequestLaneRecord)
        ):
            return frozenset({record.acceptance_status.value})
        if (
            event_field is EventTypeField.ROUTE_STATUS
            and isinstance(record, RouteEventRecord)
        ):
            return frozenset({record.route_status.value})
        if (
            event_field is EventTypeField.TELEMETRY_FIELD
            and isinstance(record, TransitionTelemetryRecord)
        ):
            return frozenset(value.field.value for value in record.values)
        if (
            event_field is EventTypeField.EVENT_COUNTER_NAME
            and isinstance(record, EventCounterSnapshot)
        ):
            return frozenset(
                value.counter.value for value in record.counters
            )
        raise TransitionViewBuilderError(
            "record does not expose the requested event field"
        )

    @staticmethod
    def _validate_state_tuple(
        states: tuple[CanonicalTernaryState, ...],
        field_name: str,
    ) -> None:
        if not isinstance(states, tuple) or not states:
            raise TransitionViewBuilderError(
                f"{field_name} must be a nonempty tuple"
            )
        if any(
            not isinstance(state, CanonicalTernaryState)
            for state in states
        ):
            raise TransitionViewBuilderError(
                f"{field_name} must contain canonical ternary states"
            )
        if len(set(states)) != len(states):
            raise TransitionViewBuilderError(
                f"{field_name} must not contain duplicates"
            )
