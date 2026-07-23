"""Immutable datasets and derived views for transition visualization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from schemas.registry import MeasurementContour
from transition_visualizer.invariant_model import InvariantVectorRecord
from transition_visualizer.request_route_model import (
    RequestLaneRecord,
    RouteEventRecord,
)
from transition_visualizer.scheduler_model import SchedulerSnapshot
from transition_visualizer.telemetry_model import (
    EventCounterSnapshot,
    TransitionTelemetryRecord,
)
from transition_visualizer.transition_model import (
    SourceRecordReference,
    TernaryStateValue,
    TransitionRecord,
)


__all__ = [
    "OBSERVATORY_DERIVED_LABEL",
    "TransitionViewModelError",
    "TransitionViewType",
    "TransitionVisualizerDataset",
    "TransitionVisualizerView",
    "ViewParameter",
    "ViewParameterValue",
    "ViewScalar",
    "VisualizerRecordType",
]


type ViewScalar = None | bool | int | str
type ViewParameterValue = ViewScalar | tuple[ViewScalar, ...]


OBSERVATORY_DERIVED_LABEL = "Observatory-derived view"


class TransitionViewModelError(ValueError):
    """Raised when a visualizer dataset or view violates its contract."""


class VisualizerRecordType(StrEnum):
    """Non-interchangeable record collections exposed by the mode."""

    STATE_VALUE = "state_value"
    TRANSITION = "transition"
    SCHEDULER_SNAPSHOT = "scheduler_snapshot"
    REQUEST_LANE = "request_lane"
    ROUTE_EVENT = "route_event"
    TRANSITION_TELEMETRY = "transition_telemetry"
    EVENT_COUNTER_SNAPSHOT = "event_counter_snapshot"
    INVARIANT_VECTOR = "invariant_vector"


class TransitionViewType(StrEnum):
    """Source-order-aware derived-view operations."""

    TICK_FILTER = "tick_filter"
    CELL_FILTER = "cell_filter"
    REQUEST_LANE_FILTER = "request_lane_filter"
    SCHEDULER_STATE_FILTER = "scheduler_state_filter"
    EVENT_TYPE_FILTER = "event_type_filter"
    SOURCE_ORDER_PRESERVING_PROJECTION = (
        "source_order_preserving_projection"
    )
    EXPLICITLY_SORTED_PROJECTION = "explicitly_sorted_projection"
    STATE_TRANSITION_PROJECTION = "state_transition_projection"
    TRACE_TO_ROUTE_CORRELATION = "trace_to_route_correlation"


_ORDER_PRESERVING_VIEW_TYPES = frozenset(
    {
        TransitionViewType.TICK_FILTER,
        TransitionViewType.CELL_FILTER,
        TransitionViewType.REQUEST_LANE_FILTER,
        TransitionViewType.SCHEDULER_STATE_FILTER,
        TransitionViewType.EVENT_TYPE_FILTER,
        TransitionViewType.SOURCE_ORDER_PRESERVING_PROJECTION,
    }
)


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TransitionViewModelError(
            f"{field_name} must be a string"
        )
    if not value or value != value.strip():
        raise TransitionViewModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise TransitionViewModelError(
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
        raise TransitionViewModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_uuid_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(values, tuple):
        raise TransitionViewModelError(
            f"{field_name} must be a tuple"
        )
    if not allow_empty and not values:
        raise TransitionViewModelError(
            f"{field_name} must not be empty"
        )
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise TransitionViewModelError(
            f"{field_name} must be unique"
        )


def _validate_record_tuple(
    values: tuple[object, ...],
    expected_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TransitionViewModelError(
            f"{field_name} must be a tuple"
        )
    if any(not isinstance(value, expected_type) for value in values):
        raise TransitionViewModelError(
            f"{field_name} contains an invalid record type"
        )


def _validate_view_scalar(
    value: ViewScalar,
    field_name: str,
) -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, str):
        _validate_text(value, field_name)
        return
    raise TransitionViewModelError(
        f"{field_name} contains an unsupported scalar"
    )


def _validate_parameter_value(
    value: ViewParameterValue,
    field_name: str,
) -> None:
    if isinstance(value, tuple):
        for item in value:
            _validate_view_scalar(item, field_name)
        return
    _validate_view_scalar(value, field_name)


def _unique_references(
    references: tuple[SourceRecordReference, ...],
) -> tuple[SourceRecordReference, ...]:
    result: list[SourceRecordReference] = []
    seen: set[str] = set()
    for reference in references:
        if reference.normalized_record_id not in seen:
            result.append(reference)
            seen.add(reference.normalized_record_id)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ViewParameter:
    """One immutable parameter recorded for a derived view."""

    name: str
    value: ViewParameterValue

    def __post_init__(self) -> None:
        _validate_text(self.name, "name")
        if any(character.isspace() for character in self.name):
            raise TransitionViewModelError(
                "parameter name must not contain whitespace"
            )
        _validate_parameter_value(self.value, self.name)


@dataclass(frozen=True, slots=True)
class TransitionVisualizerDataset:
    """Validated records from one trace dataset and one contour."""

    visualizer_dataset_id: str
    trace_dataset_id: str
    measurement_contour: MeasurementContour
    source_references: tuple[SourceRecordReference, ...]
    state_values: tuple[TernaryStateValue, ...] = ()
    transitions: tuple[TransitionRecord, ...] = ()
    scheduler_snapshots: tuple[SchedulerSnapshot, ...] = ()
    request_lanes: tuple[RequestLaneRecord, ...] = ()
    route_events: tuple[RouteEventRecord, ...] = ()
    telemetry_records: tuple[TransitionTelemetryRecord, ...] = ()
    counter_snapshots: tuple[EventCounterSnapshot, ...] = ()
    invariant_vectors: tuple[InvariantVectorRecord, ...] = ()
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.visualizer_dataset_id,
            "visualizer_dataset_id",
        )
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        if not isinstance(
            self.measurement_contour,
            MeasurementContour,
        ):
            raise TransitionViewModelError(
                "measurement_contour must be a MeasurementContour"
            )

        _validate_record_tuple(
            self.source_references,
            SourceRecordReference,
            "source_references",
        )
        if not self.source_references:
            raise TransitionViewModelError(
                "source_references must not be empty"
            )
        reference_ids = tuple(
            reference.normalized_record_id
            for reference in self.source_references
        )
        if len(set(reference_ids)) != len(reference_ids):
            raise TransitionViewModelError(
                "source references must identify unique records"
            )
        if any(
            reference.trace_dataset_id != self.trace_dataset_id
            for reference in self.source_references
        ):
            raise TransitionViewModelError(
                "source references must belong to one trace dataset"
            )

        record_contracts = (
            (
                self.state_values,
                TernaryStateValue,
                "state_values",
            ),
            (
                self.transitions,
                TransitionRecord,
                "transitions",
            ),
            (
                self.scheduler_snapshots,
                SchedulerSnapshot,
                "scheduler_snapshots",
            ),
            (
                self.request_lanes,
                RequestLaneRecord,
                "request_lanes",
            ),
            (
                self.route_events,
                RouteEventRecord,
                "route_events",
            ),
            (
                self.telemetry_records,
                TransitionTelemetryRecord,
                "telemetry_records",
            ),
            (
                self.counter_snapshots,
                EventCounterSnapshot,
                "counter_snapshots",
            ),
            (
                self.invariant_vectors,
                InvariantVectorRecord,
                "invariant_vectors",
            ),
        )
        for values, expected_type, field_name in record_contracts:
            _validate_record_tuple(
                values,
                expected_type,
                field_name,
            )
        if not any(values for values, _, _ in record_contracts):
            raise TransitionViewModelError(
                "visualizer dataset must contain at least one record"
            )

        all_record_ids = tuple(
            record_id
            for record_type in VisualizerRecordType
            for record_id in self.record_ids(record_type)
        )
        if len(set(all_record_ids)) != len(all_record_ids):
            raise TransitionViewModelError(
                "visualizer record identifiers must be globally unique"
            )

        used_references = self._all_record_references()
        available_reference_ids = set(reference_ids)
        if any(
            reference.normalized_record_id
            not in available_reference_ids
            for reference in used_references
        ):
            raise TransitionViewModelError(
                "every record source must appear in source_references"
            )
        if any(
            vector.qualification_contour
            is not self.measurement_contour
            for vector in self.invariant_vectors
        ):
            raise TransitionViewModelError(
                "invariant vectors must remain in the dataset contour"
            )

        _validate_uuid_tuple(
            self.validation_check_ids,
            "validation_check_ids",
            allow_empty=True,
        )

    @property
    def source_artifact_ids(self) -> tuple[str, ...]:
        """Return source artifacts in first-reference order."""

        return tuple(
            dict.fromkeys(
                reference.source_artifact_id
                for reference in self.source_references
            )
        )

    @property
    def normalized_record_ids(self) -> tuple[str, ...]:
        """Return normalized source records in retained order."""

        return tuple(
            reference.normalized_record_id
            for reference in self.source_references
        )

    def records(
        self,
        record_type: VisualizerRecordType,
    ) -> tuple[object, ...]:
        """Return one typed collection without combining record kinds."""

        if not isinstance(record_type, VisualizerRecordType):
            raise TransitionViewModelError(
                "record_type must be a VisualizerRecordType"
            )
        collections = {
            VisualizerRecordType.STATE_VALUE: self.state_values,
            VisualizerRecordType.TRANSITION: self.transitions,
            VisualizerRecordType.SCHEDULER_SNAPSHOT: (
                self.scheduler_snapshots
            ),
            VisualizerRecordType.REQUEST_LANE: self.request_lanes,
            VisualizerRecordType.ROUTE_EVENT: self.route_events,
            VisualizerRecordType.TRANSITION_TELEMETRY: (
                self.telemetry_records
            ),
            VisualizerRecordType.EVENT_COUNTER_SNAPSHOT: (
                self.counter_snapshots
            ),
            VisualizerRecordType.INVARIANT_VECTOR: (
                self.invariant_vectors
            ),
        }
        return collections[record_type]

    def record_ids(
        self,
        record_type: VisualizerRecordType,
    ) -> tuple[str, ...]:
        """Return record identifiers in retained collection order."""

        return tuple(
            self._record_id(record)
            for record in self.records(record_type)
        )

    def references_for_records(
        self,
        record_type: VisualizerRecordType,
        record_ids: tuple[str, ...],
    ) -> tuple[SourceRecordReference, ...]:
        """Return every source reference used by selected records."""

        _validate_uuid_tuple(
            record_ids,
            "record_ids",
            allow_empty=True,
        )
        records_by_id = {
            self._record_id(record): record
            for record in self.records(record_type)
        }
        if any(record_id not in records_by_id for record_id in record_ids):
            raise TransitionViewModelError(
                "selected record does not belong to the dataset"
            )
        references = tuple(
            reference
            for record_id in record_ids
            for reference in self._record_references(
                records_by_id[record_id]
            )
        )
        return _unique_references(references)

    def _all_record_references(
        self,
    ) -> tuple[SourceRecordReference, ...]:
        return _unique_references(
            tuple(
                reference
                for record_type in VisualizerRecordType
                for record in self.records(record_type)
                for reference in self._record_references(record)
            )
        )

    @staticmethod
    def _record_id(record: object) -> str:
        if isinstance(record, TernaryStateValue):
            return record.state_value_id
        if isinstance(record, TransitionRecord):
            return record.transition_record_id
        if isinstance(record, SchedulerSnapshot):
            return record.scheduler_snapshot_id
        if isinstance(record, RequestLaneRecord):
            return record.request_lane_record_id
        if isinstance(record, RouteEventRecord):
            return record.route_event_record_id
        if isinstance(record, TransitionTelemetryRecord):
            return record.telemetry_record_id
        if isinstance(record, EventCounterSnapshot):
            return record.counter_snapshot_id
        if isinstance(record, InvariantVectorRecord):
            return record.invariant_vector_record_id
        raise TransitionViewModelError(
            "unsupported visualizer record type"
        )

    @staticmethod
    def _record_references(
        record: object,
    ) -> tuple[SourceRecordReference, ...]:
        if isinstance(record, TernaryStateValue):
            return (record.source_reference,)
        if isinstance(record, TransitionRecord):
            return record.source_references
        if isinstance(record, SchedulerSnapshot):
            references = (
                record.source_reference,
                record.state.source_reference,
            )
            if record.mode is not None:
                references += (record.mode.source_reference,)
            return _unique_references(references)
        if isinstance(record, RequestLaneRecord):
            return (record.source_reference,)
        if isinstance(record, RouteEventRecord):
            return (record.source_reference,)
        if isinstance(record, TransitionTelemetryRecord):
            return _unique_references(
                (record.tick_reference,)
                + tuple(
                    reference
                    for value in record.values
                    for reference in value.source_references
                )
            )
        if isinstance(record, EventCounterSnapshot):
            return _unique_references(
                (record.source_reference,)
                + tuple(
                    value.source_reference
                    for value in record.counters
                )
            )
        if isinstance(record, InvariantVectorRecord):
            return _unique_references(
                (record.source_reference,)
                + tuple(
                    bit.source_reference for bit in record.bits
                )
            )
        raise TransitionViewModelError(
            "unsupported visualizer record type"
        )


@dataclass(frozen=True, slots=True)
class TransitionVisualizerView:
    """One labeled Observatory-derived selection or projection."""

    derived_view_id: str
    source_dataset: TransitionVisualizerDataset
    view_type: TransitionViewType
    record_type: VisualizerRecordType
    operation: str
    parameters: tuple[ViewParameter, ...]
    created_at: datetime
    registry_revision: str
    source_artifact_ids: tuple[str, ...]
    normalized_record_ids: tuple[str, ...]
    output_record_ids: tuple[str, ...]
    source_order_preserved: bool
    derived_label: str = OBSERVATORY_DERIVED_LABEL
    observatory_version: str | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.derived_view_id, "derived_view_id")
        if not isinstance(
            self.source_dataset,
            TransitionVisualizerDataset,
        ):
            raise TransitionViewModelError(
                "source_dataset must be a TransitionVisualizerDataset"
            )
        if not isinstance(self.view_type, TransitionViewType):
            raise TransitionViewModelError(
                "view_type must be a TransitionViewType"
            )
        if not isinstance(self.record_type, VisualizerRecordType):
            raise TransitionViewModelError(
                "record_type must be a VisualizerRecordType"
            )
        _validate_text(self.operation, "operation")

        if not isinstance(self.parameters, tuple):
            raise TransitionViewModelError(
                "parameters must be a tuple"
            )
        if any(
            not isinstance(parameter, ViewParameter)
            for parameter in self.parameters
        ):
            raise TransitionViewModelError(
                "parameters must contain ViewParameter values"
            )
        parameter_names = tuple(
            parameter.name for parameter in self.parameters
        )
        if len(set(parameter_names)) != len(parameter_names):
            raise TransitionViewModelError(
                "parameter names must be unique"
            )

        if not isinstance(self.created_at, datetime):
            raise TransitionViewModelError(
                "created_at must be a datetime"
            )
        if (
            self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise TransitionViewModelError(
                "created_at must be timezone-aware"
            )
        _validate_text(self.registry_revision, "registry_revision")
        _validate_uuid_tuple(
            self.source_artifact_ids,
            "source_artifact_ids",
            allow_empty=False,
        )
        _validate_uuid_tuple(
            self.normalized_record_ids,
            "normalized_record_ids",
            allow_empty=True,
        )
        _validate_uuid_tuple(
            self.output_record_ids,
            "output_record_ids",
            allow_empty=True,
        )
        if not isinstance(self.source_order_preserved, bool):
            raise TransitionViewModelError(
                "source_order_preserved must be a bool"
            )
        _validate_text(self.derived_label, "derived_label")
        if self.derived_label != OBSERVATORY_DERIVED_LABEL:
            raise TransitionViewModelError(
                "derived view requires the Observatory-derived label"
            )
        _validate_optional_text(
            self.observatory_version,
            "observatory_version",
        )

        dataset_artifact_ids = set(
            self.source_dataset.source_artifact_ids
        )
        if any(
            source_artifact_id not in dataset_artifact_ids
            for source_artifact_id in self.source_artifact_ids
        ):
            raise TransitionViewModelError(
                "view source artifact is outside the dataset"
            )
        dataset_record_ids = set(
            self.source_dataset.normalized_record_ids
        )
        if any(
            normalized_record_id not in dataset_record_ids
            for normalized_record_id in self.normalized_record_ids
        ):
            raise TransitionViewModelError(
                "view source record is outside the dataset"
            )

        available_output_ids = self.source_dataset.record_ids(
            self.record_type
        )
        available_output_set = set(available_output_ids)
        if any(
            output_record_id not in available_output_set
            for output_record_id in self.output_record_ids
        ):
            raise TransitionViewModelError(
                "view output record is outside its typed collection"
            )

        selected_references = (
            self.source_dataset.references_for_records(
                self.record_type,
                self.output_record_ids,
            )
        )
        selected_reference_ids = {
            reference.normalized_record_id
            for reference in selected_references
        }
        if not selected_reference_ids.issubset(
            set(self.normalized_record_ids)
        ):
            raise TransitionViewModelError(
                "normalized_record_ids omit selected record provenance"
            )
        selected_artifact_ids = {
            reference.source_artifact_id
            for reference in selected_references
        }
        if not selected_artifact_ids.issubset(
            set(self.source_artifact_ids)
        ):
            raise TransitionViewModelError(
                "source_artifact_ids omit selected record provenance"
            )

        if self.view_type in _ORDER_PRESERVING_VIEW_TYPES:
            if not self.source_order_preserved:
                raise TransitionViewModelError(
                    "filter and source-order projections must preserve order"
                )
        if (
            self.view_type
            is TransitionViewType.EXPLICITLY_SORTED_PROJECTION
            and self.source_order_preserved
        ):
            raise TransitionViewModelError(
                "explicitly sorted projection must record reordered output"
            )
        if self.source_order_preserved:
            output_positions = {
                record_id: index
                for index, record_id in enumerate(available_output_ids)
            }
            selected_positions = tuple(
                output_positions[record_id]
                for record_id in self.output_record_ids
            )
            if selected_positions != tuple(sorted(selected_positions)):
                raise TransitionViewModelError(
                    "output_record_ids do not preserve source order"
                )

        _validate_uuid_tuple(
            self.validation_check_ids,
            "validation_check_ids",
            allow_empty=True,
        )
