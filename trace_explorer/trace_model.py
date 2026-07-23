"""Immutable source-linked records for Trace Explorer datasets."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from artifact_auditor.audit_report import SourceLocation
from parsers.m15_vector import M15VectorTraceKind
from schemas.registry import MeasurementContour, ObservatoryMode
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
    RecordOrigin,
    SourceRecordReference,
    SourceStateValue,
    TernaryStateValue,
    TransitionRecord,
)


__all__ = [
    "AggregationClassification",
    "CellTraceRecord",
    "OrderingValidationStatus",
    "RequestBundle",
    "TernaryStateSnapshot",
    "TickRecord",
    "TraceCompletenessStatus",
    "TraceDataset",
    "TraceFamily",
    "TraceField",
    "TraceFieldValue",
    "TraceModelError",
    "TraceScalar",
    "TraceTelemetrySnapshot",
]


type TraceScalar = None | bool | int | Decimal | str
type TraceFieldValue = TraceScalar | tuple[TraceFieldValue, ...]


_STRUCTURED_OUTPUT_SCHEMA: Final = "frp.structured_output.v1.7.0"
_CYCLE_EXACT_SCHEMA: Final = (
    "frp.m15.cycle_exact_reference_trace.v1.7.0"
)
_M15_VECTOR_FORMAT: Final = "frp.m15.vector.v1"

_STRUCTURED_CELL_FIELDS: Final = frozenset(
    {
        "state_code",
        "phase_word",
        "frequency_target_q16",
        "frequency_current_q16",
        "frequency_lag_q16",
        "generated_power_q16",
        "heat_q16",
        "thermal_overload_q16",
        "gamma_noise_state_q16",
        "gamma_effective_word",
        "thermal_node_factor_q30",
        "coupling_field_q16",
    }
)
_M15_VECTOR_CELL_FIELDS: Final = frozenset(
    {
        "STATE_CODE",
        "PHASE_WORD",
        "FREQUENCY_TARGET_Q",
        "FREQUENCY_CURRENT_Q",
        "FREQUENCY_LAG_Q",
        "GENERATED_POWER_Q",
        "HEAT_Q",
        "THERMAL_OVERLOAD_Q",
        "GAMMA_NOISE_STATE_Q",
        "GAMMA_EFFECTIVE_WORD",
        "THERMAL_NODE_FACTOR_Q",
        "COUPLING_FIELD_Q",
    }
)
_TICK_LINK_FIELDS: Final = (
    "scheduler_snapshot_id",
    "request_bundle_id",
    "state_snapshot_id",
    "transition_telemetry_id",
    "telemetry_snapshot_id",
    "event_counter_snapshot_id",
)


class TraceModelError(ValueError):
    """Raised when a trace record violates the read-only model."""


class TraceFamily(StrEnum):
    """Registered trace roles without replacing upstream identifiers."""

    STRUCTURED_PROCESSOR_TICK = "structured_processor_tick_trace"
    CYCLE_EXACT_REFERENCE = "cycle_exact_reference_trace"
    M15_PRIMARY_VECTOR = "m15_primary_vector_trace"
    M15_PER_CELL_VECTOR = "m15_per_cell_vector_trace"
    M15_PENDING_ROUTE = "m15_pending_route_trace"


class OrderingValidationStatus(StrEnum):
    """Recorded validation state for source collection ordering."""

    VALIDATED_SOURCE_ORDER = "validated_source_order"
    INVALID_SOURCE_ORDER = "invalid_source_order"
    NOT_EVALUATED = "not_evaluated"


class TraceCompletenessStatus(StrEnum):
    """Availability of collections required by one trace family."""

    REQUIRED_COLLECTIONS_PRESENT = "required_collections_present"
    REQUIRED_COLLECTIONS_MISSING = "required_collections_missing"


class AggregationClassification(StrEnum):
    """Registered aggregation scopes kept separate in Trace Explorer."""

    INSTANTANEOUS = "instantaneous"
    CURRENT_TICK = "current_tick"
    CUMULATIVE = "cumulative"
    FINAL_SUMMARY = "final_summary"
    MINIMUM_SUMMARY = "minimum_summary"
    MAXIMUM_SUMMARY = "maximum_summary"
    PACKAGE_AGGREGATE = "package_aggregate"


_PRIMARY_VECTOR_KINDS: Final = frozenset(
    {
        M15VectorTraceKind.KERNEL_TRANSITION_VECTORS.value,
        M15VectorTraceKind.SCHEDULER_FREE_VECTORS.value,
        M15VectorTraceKind.SCHEDULER_7_1_VECTORS.value,
        M15VectorTraceKind.SCHEDULER_1_7_VECTORS.value,
        M15VectorTraceKind.FULL_CORRELATION_VECTORS.value,
    }
)
_FAMILY_CONTOURS: Final = MappingProxyType(
    {
        TraceFamily.STRUCTURED_PROCESSOR_TICK: (
            MeasurementContour.STRUCTURED_OUTPUT
        ),
        TraceFamily.CYCLE_EXACT_REFERENCE: (
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        TraceFamily.M15_PRIMARY_VECTOR: (
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        TraceFamily.M15_PER_CELL_VECTOR: (
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        TraceFamily.M15_PENDING_ROUTE: (
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
    }
)
_FAMILY_ALLOWED_MODES: Final = MappingProxyType(
    {
        TraceFamily.STRUCTURED_PROCESSOR_TICK: frozenset(
            {
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            }
        ),
        TraceFamily.CYCLE_EXACT_REFERENCE: frozenset(
            {
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            }
        ),
        TraceFamily.M15_PRIMARY_VECTOR: frozenset(
            {
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            }
        ),
        TraceFamily.M15_PER_CELL_VECTOR: frozenset(
            {
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TRACE_EXPLORER,
            }
        ),
        TraceFamily.M15_PENDING_ROUTE: frozenset(
            {
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            }
        ),
    }
)


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TraceModelError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise TraceModelError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if "\x00" in value:
        raise TraceModelError(f"{field_name} must not contain NUL")


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
        raise TraceModelError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _validate_nonnegative_integer(
    value: int,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceModelError(f"{field_name} must be an integer")
    if value < 0:
        raise TraceModelError(f"{field_name} must be nonnegative")


def _validate_optional_uuid(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _validate_uuid(value, field_name)


def _validate_unique_uuids(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TraceModelError(f"{field_name} must be a tuple")
    for value in values:
        _validate_uuid(value, field_name)
    if len(set(values)) != len(values):
        raise TraceModelError(f"{field_name} must be unique")


def _validate_source_state(
    value: SourceStateValue,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TraceModelError(
            f"{field_name} must be an integer or string"
        )
    if isinstance(value, str):
        _validate_text(value, field_name)


def _validate_field_value(
    value: TraceFieldValue,
    field_name: str,
) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise TraceModelError(f"{field_name} must be finite")
        return
    if isinstance(value, tuple):
        for item in value:
            _validate_field_value(item, field_name)
        return
    raise TraceModelError(
        f"{field_name} contains an unsupported value type"
    )


def _validate_locations(
    value: tuple[SourceLocation, ...],
    field_name: str,
) -> None:
    if not isinstance(value, tuple):
        raise TraceModelError(f"{field_name} must be a tuple")
    if not value:
        raise TraceModelError(f"{field_name} must not be empty")
    if any(not isinstance(item, SourceLocation) for item in value):
        raise TraceModelError(
            f"{field_name} must contain SourceLocation values"
        )


def _validate_reference(
    value: SourceRecordReference,
    field_name: str,
) -> None:
    if not isinstance(value, SourceRecordReference):
        raise TraceModelError(
            f"{field_name} must be a SourceRecordReference"
        )


def _validate_fields(
    fields: tuple[TraceField, ...],
    *,
    allow_empty: bool,
    field_name: str,
) -> None:
    if not isinstance(fields, tuple):
        raise TraceModelError(f"{field_name} must be a tuple")
    if not allow_empty and not fields:
        raise TraceModelError(f"{field_name} must not be empty")
    if any(not isinstance(field, TraceField) for field in fields):
        raise TraceModelError(
            f"{field_name} must contain TraceField records"
        )
    names = tuple(field.field_name for field in fields)
    if len(set(names)) != len(names):
        raise TraceModelError(
            f"{field_name} must contain unique field names"
        )


def _require_source_record(
    actual: SourceRecordReference,
    expected: SourceRecordReference,
    field_name: str,
) -> None:
    if actual.normalized_record_id != expected.normalized_record_id:
        raise TraceModelError(
            f"{field_name} must reference the parent source record"
        )


def _source_ordinals(
    records: Iterable[
        TickRecord
        | CellTraceRecord
        | TernaryStateSnapshot
        | RequestBundle
        | SchedulerSnapshot
        | RouteEventRecord
        | TransitionTelemetryRecord
        | TraceTelemetrySnapshot
        | EventCounterSnapshot
    ],
) -> tuple[int, ...]:
    ordinals: list[int] = []
    for record in records:
        if isinstance(record, TickRecord | CellTraceRecord):
            ordinals.append(record.source_ordinal)
        elif isinstance(record, TransitionTelemetryRecord):
            ordinals.append(record.tick_reference.source_ordinal)
        elif isinstance(record, TraceTelemetrySnapshot):
            ordinals.append(record.source_reference.source_ordinal)
        else:
            ordinals.append(record.source_reference.source_ordinal)
    return tuple(ordinals)


def _strictly_increasing(values: tuple[int, ...]) -> bool:
    return all(
        current < following
        for current, following in zip(values, values[1:], strict=False)
    )


@dataclass(frozen=True, slots=True)
class TraceField:
    """One exact published field with immutable source provenance."""

    trace_field_id: str
    source_reference: SourceRecordReference
    field_name: str
    value: TraceFieldValue
    source_location: SourceLocation
    source_encoding: str | None = None
    unit: str | None = None
    aggregation: AggregationClassification | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_field_id, "trace_field_id")
        _validate_reference(self.source_reference, "source_reference")
        _validate_text(self.field_name, "field_name")
        if any(character.isspace() for character in self.field_name):
            raise TraceModelError(
                "field_name must not contain whitespace"
            )
        _validate_field_value(self.value, "value")
        if not isinstance(self.source_location, SourceLocation):
            raise TraceModelError(
                "source_location must be a SourceLocation"
            )
        _validate_optional_text(
            self.source_encoding,
            "source_encoding",
        )
        _validate_optional_text(self.unit, "unit")
        if (
            self.aggregation is not None
            and not isinstance(
                self.aggregation,
                AggregationClassification,
            )
        ):
            raise TraceModelError(
                "aggregation must be an AggregationClassification or None"
            )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class TernaryStateSnapshot:
    """Retained state representations for one source trace record."""

    state_snapshot_id: str
    source_reference: SourceRecordReference
    packed_integer: int | None = None
    packed_hex: str | None = None
    human_state: str | None = None
    cell_states: tuple[TernaryStateValue, ...] | None = None
    state_encoding_binding: str | None = None
    reserved_state_observations: tuple[SourceStateValue, ...] = ()
    state_domain_valid: bool = True
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.state_snapshot_id, "state_snapshot_id")
        _validate_reference(self.source_reference, "source_reference")
        if self.packed_integer is not None:
            _validate_nonnegative_integer(
                self.packed_integer,
                "packed_integer",
            )
        _validate_optional_text(self.packed_hex, "packed_hex")
        _validate_optional_text(self.human_state, "human_state")
        _validate_optional_text(
            self.state_encoding_binding,
            "state_encoding_binding",
        )

        if self.cell_states is not None:
            if not isinstance(self.cell_states, tuple):
                raise TraceModelError("cell_states must be a tuple or None")
            if not self.cell_states:
                raise TraceModelError(
                    "present cell_states must not be empty"
                )
            if any(
                not isinstance(state, TernaryStateValue)
                for state in self.cell_states
            ):
                raise TraceModelError(
                    "cell_states must contain TernaryStateValue records"
                )
            cell_ids = tuple(
                state.cell_id for state in self.cell_states
            )
            if len(set(cell_ids)) != len(cell_ids):
                raise TraceModelError(
                    "cell_states must identify unique cells"
                )
            for state in self.cell_states:
                _require_source_record(
                    state.source_reference,
                    self.source_reference,
                    "cell_states",
                )
            normalized_bindings = {
                state.encoding_map_identifier
                for state in self.cell_states
                if state.origin is RecordOrigin.OBSERVATORY_NORMALIZED
            }
            if normalized_bindings:
                if self.state_encoding_binding is None:
                    raise TraceModelError(
                        "normalized cell states require a snapshot binding"
                    )
                if normalized_bindings != {
                    self.state_encoding_binding
                }:
                    raise TraceModelError(
                        "cell states must use the snapshot encoding binding"
                    )

        if (
            self.packed_integer is None
            and self.packed_hex is None
            and self.human_state is None
            and self.cell_states is None
        ):
            raise TraceModelError(
                "a state snapshot requires one published representation"
            )

        if not isinstance(
            self.reserved_state_observations,
            tuple,
        ):
            raise TraceModelError(
                "reserved_state_observations must be a tuple"
            )
        for value in self.reserved_state_observations:
            _validate_source_state(
                value,
                "reserved_state_observations",
            )
        if not isinstance(self.state_domain_valid, bool):
            raise TraceModelError("state_domain_valid must be a bool")
        if (
            self.state_domain_valid
            and self.reserved_state_observations
        ):
            raise TraceModelError(
                "valid state domains cannot contain reserved observations"
            )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class RequestBundle:
    """Published request arrays and their ordered lane normalization."""

    request_bundle_id: str
    source_reference: SourceRecordReference
    request_valid_mask: int | str
    source_cell_ids: tuple[int, ...]
    source_target_states: tuple[SourceStateValue, ...]
    request_lane_count: int
    request_lanes: tuple[RequestLaneRecord, ...]
    request_encoding_binding: str
    source_locations: tuple[SourceLocation, ...]
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.request_bundle_id, "request_bundle_id")
        _validate_reference(self.source_reference, "source_reference")
        if isinstance(self.request_valid_mask, int):
            _validate_nonnegative_integer(
                self.request_valid_mask,
                "request_valid_mask",
            )
        else:
            _validate_text(
                self.request_valid_mask,
                "request_valid_mask",
            )
        _validate_nonnegative_integer(
            self.request_lane_count,
            "request_lane_count",
        )
        _validate_text(
            self.request_encoding_binding,
            "request_encoding_binding",
        )

        if not isinstance(self.source_cell_ids, tuple):
            raise TraceModelError("source_cell_ids must be a tuple")
        for cell_id in self.source_cell_ids:
            _validate_nonnegative_integer(cell_id, "source_cell_ids")
        if not isinstance(self.source_target_states, tuple):
            raise TraceModelError(
                "source_target_states must be a tuple"
            )
        for state in self.source_target_states:
            _validate_source_state(state, "source_target_states")

        expected_count = self.request_lane_count
        if (
            len(self.source_cell_ids) != expected_count
            or len(self.source_target_states) != expected_count
        ):
            raise TraceModelError(
                "source request arrays must match request_lane_count"
            )

        if not isinstance(self.request_lanes, tuple):
            raise TraceModelError("request_lanes must be a tuple")
        if any(
            not isinstance(lane, RequestLaneRecord)
            for lane in self.request_lanes
        ):
            raise TraceModelError(
                "request_lanes must contain RequestLaneRecord values"
            )
        if len(self.request_lanes) != expected_count:
            raise TraceModelError(
                "request_lanes must match request_lane_count"
            )
        if tuple(
            lane.lane_index for lane in self.request_lanes
        ) != tuple(range(expected_count)):
            raise TraceModelError(
                "request_lanes must preserve zero-based lane order"
            )

        for lane in self.request_lanes:
            _require_source_record(
                lane.source_reference,
                self.source_reference,
                "request_lanes",
            )
            source_cell = self.source_cell_ids[lane.lane_index]
            source_target = self.source_target_states[lane.lane_index]
            if lane.cell_id is not None and lane.cell_id != source_cell:
                raise TraceModelError(
                    "lane cell_id does not match the source array"
                )
            if (
                lane.source_target_state is not None
                and lane.source_target_state != source_target
            ):
                raise TraceModelError(
                    "lane target does not match the source array"
                )
            if (
                lane.origin is RecordOrigin.OBSERVATORY_NORMALIZED
                and lane.encoding_map_identifier
                != self.request_encoding_binding
            ):
                raise TraceModelError(
                    "normalized lanes must use the bundle encoding binding"
                )

        _validate_locations(
            self.source_locations,
            "source_locations",
        )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class TraceTelemetrySnapshot:
    """Published heat, coherence, pressure, and related trace fields."""

    telemetry_snapshot_id: str
    source_reference: SourceRecordReference
    fields: tuple[TraceField, ...]
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.telemetry_snapshot_id,
            "telemetry_snapshot_id",
        )
        _validate_reference(self.source_reference, "source_reference")
        _validate_fields(
            self.fields,
            allow_empty=False,
            field_name="fields",
        )
        for field in self.fields:
            _require_source_record(
                field.source_reference,
                self.source_reference,
                "fields",
            )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    def field_named(self, field_name: str) -> TraceField | None:
        """Return one present field without synthesizing a value."""

        _validate_text(field_name, "field_name")
        return next(
            (
                field
                for field in self.fields
                if field.field_name == field_name
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class CellTraceRecord:
    """One source per-cell row with separately retained state decoding."""

    cell_trace_record_id: str
    trace_dataset_id: str
    source_reference: SourceRecordReference
    source_location: SourceLocation
    source_ordinal: int
    tick: int
    cell_id: int
    fields: tuple[TraceField, ...]
    canonical_state: TernaryStateValue | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(
            self.cell_trace_record_id,
            "cell_trace_record_id",
        )
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        _validate_reference(self.source_reference, "source_reference")
        if not isinstance(self.source_location, SourceLocation):
            raise TraceModelError(
                "source_location must be a SourceLocation"
            )
        _validate_nonnegative_integer(
            self.source_ordinal,
            "source_ordinal",
        )
        _validate_nonnegative_integer(self.tick, "tick")
        _validate_nonnegative_integer(self.cell_id, "cell_id")
        if (
            self.trace_dataset_id
            != self.source_reference.trace_dataset_id
        ):
            raise TraceModelError(
                "trace_dataset_id must match the source reference"
            )
        if (
            self.source_ordinal
            != self.source_reference.source_ordinal
            or self.tick != self.source_reference.tick
        ):
            raise TraceModelError(
                "cell record order and tick must match source provenance"
            )

        _validate_fields(
            self.fields,
            allow_empty=False,
            field_name="fields",
        )
        field_names = frozenset(
            field.field_name for field in self.fields
        )
        if field_names not in (
            _STRUCTURED_CELL_FIELDS,
            _M15_VECTOR_CELL_FIELDS,
        ):
            raise TraceModelError(
                "cell fields must match one registered per-cell contract"
            )
        for field in self.fields:
            _require_source_record(
                field.source_reference,
                self.source_reference,
                "fields",
            )

        if self.canonical_state is not None:
            if not isinstance(
                self.canonical_state,
                TernaryStateValue,
            ):
                raise TraceModelError(
                    "canonical_state must be a TernaryStateValue or None"
                )
            _require_source_record(
                self.canonical_state.source_reference,
                self.source_reference,
                "canonical_state",
            )
            if self.canonical_state.cell_id != self.cell_id:
                raise TraceModelError(
                    "canonical_state must identify the cell record cell"
                )
            source_field_name = (
                "state_code"
                if "state_code" in field_names
                else "STATE_CODE"
            )
            source_value = next(
                field.value
                for field in self.fields
                if field.field_name == source_field_name
            )
            if self.canonical_state.source_value != source_value:
                raise TraceModelError(
                    "canonical_state must preserve the source state value"
                )

        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )


@dataclass(frozen=True, slots=True)
class TickRecord:
    """One source processor-tick row and its normalized record links."""

    tick_record_id: str
    trace_dataset_id: str
    source_reference: SourceRecordReference
    source_location: SourceLocation
    source_ordinal: int
    tick: int
    source_fields: tuple[TraceField, ...] = ()
    scheduler_snapshot_id: str | None = None
    request_bundle_id: str | None = None
    state_snapshot_id: str | None = None
    transition_telemetry_id: str | None = None
    telemetry_snapshot_id: str | None = None
    event_counter_snapshot_id: str | None = None
    changes: int | None = None
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.tick_record_id, "tick_record_id")
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        _validate_reference(self.source_reference, "source_reference")
        if not isinstance(self.source_location, SourceLocation):
            raise TraceModelError(
                "source_location must be a SourceLocation"
            )
        _validate_nonnegative_integer(
            self.source_ordinal,
            "source_ordinal",
        )
        _validate_nonnegative_integer(self.tick, "tick")
        if (
            self.trace_dataset_id
            != self.source_reference.trace_dataset_id
        ):
            raise TraceModelError(
                "trace_dataset_id must match the source reference"
            )
        if (
            self.source_ordinal
            != self.source_reference.source_ordinal
            or self.tick != self.source_reference.tick
        ):
            raise TraceModelError(
                "tick order and value must match source provenance"
            )

        _validate_fields(
            self.source_fields,
            allow_empty=True,
            field_name="source_fields",
        )
        for field in self.source_fields:
            _require_source_record(
                field.source_reference,
                self.source_reference,
                "source_fields",
            )
        for field_name in _TICK_LINK_FIELDS:
            _validate_optional_uuid(
                getattr(self, field_name),
                field_name,
            )
        if self.changes is not None:
            _validate_nonnegative_integer(self.changes, "changes")
            source_changes = next(
                (
                    field.value
                    for field in self.source_fields
                    if field.field_name in {"changes", "CHANGES"}
                ),
                self.changes,
            )
            if source_changes != self.changes:
                raise TraceModelError(
                    "changes must match its retained source field"
                )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

  @dataclass(frozen=True, slots=True)
class TraceDataset:
    """One immutable, source-ordered trace normalization boundary."""

    trace_dataset_id: str
    normalized_artifact_id: str
    trace_family: TraceFamily
    measurement_contour: MeasurementContour
    source_references: tuple[SourceRecordReference, ...]
    configuration_fields: tuple[TraceField, ...]
    ordering_validation: OrderingValidationStatus
    completeness_status: TraceCompletenessStatus
    eligible_modes: tuple[ObservatoryMode, ...]
    schema_identifier: str | None = None
    kind: str | None = None
    format_identifier: str | None = None
    state_encoding_binding: str | None = None
    tick_records: tuple[TickRecord, ...] | None = None
    cell_records: tuple[CellTraceRecord, ...] | None = None
    state_snapshots: tuple[TernaryStateSnapshot, ...] | None = None
    request_bundles: tuple[RequestBundle, ...] | None = None
    scheduler_snapshots: tuple[SchedulerSnapshot, ...] | None = None
    route_events: tuple[RouteEventRecord, ...] | None = None
    transitions: tuple[TransitionRecord, ...] | None = None
    transition_telemetry_records: (
        tuple[TransitionTelemetryRecord, ...] | None
    ) = None
    telemetry_snapshots: tuple[TraceTelemetrySnapshot, ...] | None = None
    event_counter_snapshots: (
        tuple[EventCounterSnapshot, ...] | None
    ) = None
    package_record_ids: tuple[str, ...] | None = None
    digest_record_ids: tuple[str, ...] | None = None
    ordering_validation_check_ids: tuple[str, ...] = ()
    validation_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uuid(self.trace_dataset_id, "trace_dataset_id")
        _validate_uuid(
            self.normalized_artifact_id,
            "normalized_artifact_id",
        )
        if not isinstance(self.trace_family, TraceFamily):
            raise TraceModelError(
                "trace_family must be a TraceFamily"
            )
        if not isinstance(
            self.measurement_contour,
            MeasurementContour,
        ):
            raise TraceModelError(
                "measurement_contour must be a MeasurementContour"
            )
        if (
            self.measurement_contour
            is not _FAMILY_CONTOURS[self.trace_family]
        ):
            raise TraceModelError(
                "measurement_contour does not match trace_family"
            )
        self._validate_contract_identity()
        self._validate_source_references()

        _validate_fields(
            self.configuration_fields,
            allow_empty=False,
            field_name="configuration_fields",
        )
        self._validate_collection_types()
        self._validate_parent_bindings()
        self._validate_source_coverage()
        self._validate_record_id_uniqueness()
        self._validate_ordering()
        self._validate_tick_links()
        self._validate_state_encoding_bindings()
        self._validate_completeness()
        self._validate_eligibility()

        _validate_unique_uuids(
            self.ordering_validation_check_ids,
            "ordering_validation_check_ids",
        )
        _validate_unique_uuids(
            self.validation_check_ids,
            "validation_check_ids",
        )

    def _validate_contract_identity(self) -> None:
        _validate_optional_text(
            self.schema_identifier,
            "schema_identifier",
        )
        _validate_optional_text(self.kind, "kind")
        _validate_optional_text(
            self.format_identifier,
            "format_identifier",
        )
        _validate_optional_text(
            self.state_encoding_binding,
            "state_encoding_binding",
        )

        if self.trace_family is TraceFamily.STRUCTURED_PROCESSOR_TICK:
            expected = (
                self.schema_identifier == _STRUCTURED_OUTPUT_SCHEMA
                and self.kind == "demo"
                and self.format_identifier is None
            )
        elif self.trace_family is TraceFamily.CYCLE_EXACT_REFERENCE:
            expected = (
                self.schema_identifier == _CYCLE_EXACT_SCHEMA
                and self.kind == "cycle_exact_reference_trace"
                and self.format_identifier is None
            )
        elif self.trace_family is TraceFamily.M15_PRIMARY_VECTOR:
            expected = (
                self.schema_identifier is None
                and self.kind in _PRIMARY_VECTOR_KINDS
                and self.format_identifier == _M15_VECTOR_FORMAT
            )
        elif self.trace_family is TraceFamily.M15_PER_CELL_VECTOR:
            expected = (
                self.schema_identifier is None
                and self.kind == M15VectorTraceKind.CELL_TRACE.value
                and self.format_identifier == _M15_VECTOR_FORMAT
            )
        else:
            expected = (
                self.schema_identifier is None
                and self.kind == M15VectorTraceKind.PENDING_ROUTES.value
                and self.format_identifier == _M15_VECTOR_FORMAT
            )
        if not expected:
            raise TraceModelError(
                "upstream identity does not match trace_family"
            )

    def _validate_source_references(self) -> None:
        if not isinstance(self.source_references, tuple):
            raise TraceModelError("source_references must be a tuple")
        if not self.source_references:
            raise TraceModelError(
                "source_references must not be empty"
            )
        if any(
            not isinstance(reference, SourceRecordReference)
            for reference in self.source_references
        ):
            raise TraceModelError(
                "source_references must contain SourceRecordReference values"
            )
        record_ids = tuple(
            reference.normalized_record_id
            for reference in self.source_references
        )
        if len(set(record_ids)) != len(record_ids):
            raise TraceModelError(
                "source_references must identify unique source records"
            )
        if any(
            reference.trace_dataset_id != self.trace_dataset_id
            for reference in self.source_references
        ):
            raise TraceModelError(
                "source references must belong to this trace dataset"
            )

        artifact_ids = {
            reference.source_artifact_id
            for reference in self.source_references
        }
        digests = {
            reference.source_sha256
            for reference in self.source_references
        }
        if len(artifact_ids) != 1 or len(digests) != 1:
            raise TraceModelError(
                "a trace dataset must retain one source artifact identity"
            )

        for reference in self.source_references:
            if self.schema_identifier is not None:
                if (
                    reference.schema_identifier
                    != self.schema_identifier
                    or reference.format_identifier is not None
                ):
                    raise TraceModelError(
                        "source schema binding does not match the dataset"
                    )
            elif (
                reference.format_identifier
                != self.format_identifier
                or reference.schema_identifier is not None
            ):
                raise TraceModelError(
                    "source format binding does not match the dataset"
                )

    def _validate_collection_types(self) -> None:
        collections = (
            ("tick_records", self.tick_records, TickRecord),
            ("cell_records", self.cell_records, CellTraceRecord),
            (
                "state_snapshots",
                self.state_snapshots,
                TernaryStateSnapshot,
            ),
            ("request_bundles", self.request_bundles, RequestBundle),
            (
                "scheduler_snapshots",
                self.scheduler_snapshots,
                SchedulerSnapshot,
            ),
            ("route_events", self.route_events, RouteEventRecord),
            ("transitions", self.transitions, TransitionRecord),
            (
                "transition_telemetry_records",
                self.transition_telemetry_records,
                TransitionTelemetryRecord,
            ),
            (
                "telemetry_snapshots",
                self.telemetry_snapshots,
                TraceTelemetrySnapshot,
            ),
            (
                "event_counter_snapshots",
                self.event_counter_snapshots,
                EventCounterSnapshot,
            ),
        )
        for field_name, values, expected_type in collections:
            if values is None:
                continue
            if not isinstance(values, tuple):
                raise TraceModelError(
                    f"{field_name} must be a tuple or None"
                )
            if any(
                not isinstance(value, expected_type)
                for value in values
            ):
                raise TraceModelError(
                    f"{field_name} contains an invalid record type"
                )

        for field_name in ("package_record_ids", "digest_record_ids"):
            values = getattr(self, field_name)
            if values is not None:
                _validate_unique_uuids(values, field_name)

    def _validate_parent_bindings(self) -> None:
        for field in self.configuration_fields:
            if (
                field.source_reference.trace_dataset_id
                != self.trace_dataset_id
            ):
                raise TraceModelError(
                    "configuration fields must belong to this dataset"
                )
        for record in self.tick_records or ():
            if record.trace_dataset_id != self.trace_dataset_id:
                raise TraceModelError(
                    "tick records must belong to this dataset"
                )
        for record in self.cell_records or ():
            if record.trace_dataset_id != self.trace_dataset_id:
                raise TraceModelError(
                    "cell records must belong to this dataset"
                )

    def _all_used_references(
        self,
    ) -> tuple[SourceRecordReference, ...]:
        references: list[SourceRecordReference] = []
        references.extend(
            field.source_reference
            for field in self.configuration_fields
        )
        for record in self.tick_records or ():
            references.append(record.source_reference)
            references.extend(
                field.source_reference
                for field in record.source_fields
            )
        for record in self.cell_records or ():
            references.append(record.source_reference)
            references.extend(
                field.source_reference for field in record.fields
            )
            if record.canonical_state is not None:
                references.append(
                    record.canonical_state.source_reference
                )
        for snapshot in self.state_snapshots or ():
            references.append(snapshot.source_reference)
            references.extend(
                state.source_reference
                for state in snapshot.cell_states or ()
            )
        for bundle in self.request_bundles or ():
            references.append(bundle.source_reference)
            references.extend(
                lane.source_reference
                for lane in bundle.request_lanes
            )
        for snapshot in self.scheduler_snapshots or ():
            references.append(snapshot.source_reference)
            references.append(snapshot.state.source_reference)
            if snapshot.mode is not None:
                references.append(snapshot.mode.source_reference)
        references.extend(
            event.source_reference
            for event in self.route_events or ()
        )
        for transition in self.transitions or ():
            references.extend(transition.source_references)
        for record in self.transition_telemetry_records or ():
            references.append(record.tick_reference)
            for value in record.values:
                references.extend(value.source_references)
        for snapshot in self.telemetry_snapshots or ():
            references.append(snapshot.source_reference)
            references.extend(
                field.source_reference for field in snapshot.fields
            )
        for snapshot in self.event_counter_snapshots or ():
            references.append(snapshot.source_reference)
            references.extend(
                counter.source_reference
                for counter in snapshot.counters
            )
        return tuple(references)

    def _validate_source_coverage(self) -> None:
        registered = {
            reference.normalized_record_id: reference
            for reference in self.source_references
        }
        for reference in self._all_used_references():
            expected = registered.get(reference.normalized_record_id)
            if expected is None:
                raise TraceModelError(
                    "every used source record must be registered"
                )
            if reference != expected:
                raise TraceModelError(
                    "source record metadata must match its registered value"
                )

              def _owned_record_ids(self) -> tuple[str, ...]:
        record_ids: list[str] = [self.trace_dataset_id]
        record_ids.extend(
            field.trace_field_id
            for field in self.configuration_fields
        )
        for record in self.tick_records or ():
            record_ids.append(record.tick_record_id)
            record_ids.extend(
                field.trace_field_id
                for field in record.source_fields
            )
        for record in self.cell_records or ():
            record_ids.append(record.cell_trace_record_id)
            record_ids.extend(
                field.trace_field_id for field in record.fields
            )
            if record.canonical_state is not None:
                record_ids.append(
                    record.canonical_state.state_value_id
                )
        for snapshot in self.state_snapshots or ():
            record_ids.append(snapshot.state_snapshot_id)
            record_ids.extend(
                state.state_value_id
                for state in snapshot.cell_states or ()
            )
        for bundle in self.request_bundles or ():
            record_ids.append(bundle.request_bundle_id)
            record_ids.extend(
                lane.request_lane_record_id
                for lane in bundle.request_lanes
            )
        for snapshot in self.scheduler_snapshots or ():
            record_ids.append(snapshot.scheduler_snapshot_id)
            record_ids.append(snapshot.state.scheduler_field_value_id)
            if snapshot.mode is not None:
                record_ids.append(
                    snapshot.mode.scheduler_field_value_id
                )
        record_ids.extend(
            event.route_event_record_id
            for event in self.route_events or ()
        )
        record_ids.extend(
            transition.transition_record_id
            for transition in self.transitions or ()
        )
        for record in self.transition_telemetry_records or ():
            record_ids.append(record.telemetry_record_id)
            record_ids.extend(
                value.telemetry_value_id for value in record.values
            )
        for snapshot in self.telemetry_snapshots or ():
            record_ids.append(snapshot.telemetry_snapshot_id)
            record_ids.extend(
                field.trace_field_id for field in snapshot.fields
            )
        for snapshot in self.event_counter_snapshots or ():
            record_ids.append(snapshot.counter_snapshot_id)
            record_ids.extend(
                counter.counter_value_id
                for counter in snapshot.counters
            )
        record_ids.extend(self.package_record_ids or ())
        record_ids.extend(self.digest_record_ids or ())
        return tuple(record_ids)

    def _validate_record_id_uniqueness(self) -> None:
        record_ids = (
            (self.normalized_artifact_id,)
            + tuple(
                reference.normalized_record_id
                for reference in self.source_references
            )
            + self._owned_record_ids()
        )
        for record_id in record_ids:
            _validate_uuid(record_id, "record_id")
        if len(set(record_ids)) != len(record_ids):
            raise TraceModelError(
                "all owned and referenced record IDs must be unique"
            )

    def _ordered_collections(
        self,
    ) -> tuple[
        tuple[
            str,
            tuple[
                TickRecord
                | CellTraceRecord
                | TernaryStateSnapshot
                | RequestBundle
                | SchedulerSnapshot
                | RouteEventRecord
                | TransitionTelemetryRecord
                | TraceTelemetrySnapshot
                | EventCounterSnapshot,
                ...,
            ],
        ],
        ...,
    ]:
        collections = (
            ("tick_records", self.tick_records),
            ("cell_records", self.cell_records),
            ("state_snapshots", self.state_snapshots),
            ("request_bundles", self.request_bundles),
            ("scheduler_snapshots", self.scheduler_snapshots),
            ("route_events", self.route_events),
            (
                "transition_telemetry_records",
                self.transition_telemetry_records,
            ),
            ("telemetry_snapshots", self.telemetry_snapshots),
            (
                "event_counter_snapshots",
                self.event_counter_snapshots,
            ),
        )
        return tuple(
            (field_name, values)
            for field_name, values in collections
            if values is not None
        )

    def _validate_ordering(self) -> None:
        if not isinstance(
            self.ordering_validation,
            OrderingValidationStatus,
        ):
            raise TraceModelError(
                "ordering_validation must be an OrderingValidationStatus"
            )
        if (
            self.ordering_validation
            is not OrderingValidationStatus.VALIDATED_SOURCE_ORDER
        ):
            return
        for field_name, values in self._ordered_collections():
            ordinals = _source_ordinals(values)
            if not _strictly_increasing(ordinals):
                raise TraceModelError(
                    f"{field_name} must preserve validated source order"
                )

    def _tick_link_maps(self) -> Mapping[str, Mapping[str, object]]:
        return MappingProxyType(
            {
                "scheduler_snapshot_id": {
                    item.scheduler_snapshot_id: item
                    for item in self.scheduler_snapshots or ()
                },
                "request_bundle_id": {
                    item.request_bundle_id: item
                    for item in self.request_bundles or ()
                },
                "state_snapshot_id": {
                    item.state_snapshot_id: item
                    for item in self.state_snapshots or ()
                },
                "transition_telemetry_id": {
                    item.telemetry_record_id: item
                    for item in self.transition_telemetry_records or ()
                },
                "telemetry_snapshot_id": {
                    item.telemetry_snapshot_id: item
                    for item in self.telemetry_snapshots or ()
                },
                "event_counter_snapshot_id": {
                    item.counter_snapshot_id: item
                    for item in self.event_counter_snapshots or ()
                },
            }
        )

    def _link_source_reference(
        self,
        linked: object,
    ) -> SourceRecordReference:
        if isinstance(linked, TransitionTelemetryRecord):
            return linked.tick_reference
        if isinstance(
            linked,
            (
                SchedulerSnapshot,
                RequestBundle,
                TernaryStateSnapshot,
                TraceTelemetrySnapshot,
                EventCounterSnapshot,
            ),
        ):
            return linked.source_reference
        raise TraceModelError("unsupported tick-link record type")

    def _validate_tick_links(self) -> None:
        link_maps = self._tick_link_maps()
        observed_links = {
            field_name: set() for field_name in _TICK_LINK_FIELDS
        }
        for tick_record in self.tick_records or ():
            for field_name in _TICK_LINK_FIELDS:
                record_id = getattr(tick_record, field_name)
                if record_id is None:
                    continue
                linked = link_maps[field_name].get(record_id)
                if linked is None:
                    raise TraceModelError(
                        f"{field_name} does not resolve in this dataset"
                    )
                linked_reference = self._link_source_reference(linked)
                _require_source_record(
                    linked_reference,
                    tick_record.source_reference,
                    field_name,
                )
                observed_links[field_name].add(record_id)

        for field_name, records in link_maps.items():
            if set(records) != observed_links[field_name]:
                raise TraceModelError(
                    f"{field_name} collection contains an unlinked record"
                )

    def _state_encoding_identifiers(self) -> tuple[str, ...]:
        identifiers: list[str] = []
        for snapshot in self.state_snapshots or ():
            if snapshot.state_encoding_binding is not None:
                identifiers.append(snapshot.state_encoding_binding)
            for state in snapshot.cell_states or ():
                if state.origin is RecordOrigin.OBSERVATORY_NORMALIZED:
                    if state.encoding_map_identifier is not None:
                        identifiers.append(
                            state.encoding_map_identifier
                        )
        for record in self.cell_records or ():
            state = record.canonical_state
            if (
                state is not None
                and state.origin is RecordOrigin.OBSERVATORY_NORMALIZED
                and state.encoding_map_identifier is not None
            ):
                identifiers.append(state.encoding_map_identifier)
        for bundle in self.request_bundles or ():
            for lane in bundle.request_lanes:
                if (
                    lane.origin is RecordOrigin.OBSERVATORY_NORMALIZED
                    and lane.encoding_map_identifier is not None
                ):
                    identifiers.append(
                        lane.encoding_map_identifier
                    )
        for event in self.route_events or ():
            if (
                event.origin is RecordOrigin.OBSERVATORY_NORMALIZED
                and event.encoding_map_identifier is not None
            ):
                identifiers.append(event.encoding_map_identifier)
        return tuple(identifiers)

    def _validate_state_encoding_bindings(self) -> None:
        identifiers = self._state_encoding_identifiers()
        if not identifiers:
            return
        if self.state_encoding_binding is None:
            raise TraceModelError(
                "normalized state values require a dataset binding"
            )
        if any(
            identifier != self.state_encoding_binding
            for identifier in identifiers
        ):
            raise TraceModelError(
                "normalized state values must use the dataset binding"
            )

    def _required_collections_present(self) -> bool:
        if self.trace_family is TraceFamily.STRUCTURED_PROCESSOR_TICK:
            return (
                self.tick_records is not None
                and self.cell_records is not None
                and self.route_events is not None
            )
        if self.trace_family is TraceFamily.CYCLE_EXACT_REFERENCE:
            return (
                self.tick_records is not None
                and self.route_events is not None
            )
        if self.trace_family is TraceFamily.M15_PRIMARY_VECTOR:
            return self.tick_records is not None
        if self.trace_family is TraceFamily.M15_PER_CELL_VECTOR:
            return self.cell_records is not None
        return self.route_events is not None

    def _validate_completeness(self) -> None:
        if not isinstance(
            self.completeness_status,
            TraceCompletenessStatus,
        ):
            raise TraceModelError(
                "completeness_status must be a TraceCompletenessStatus"
            )
        expected = (
            TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT
            if self._required_collections_present()
            else TraceCompletenessStatus.REQUIRED_COLLECTIONS_MISSING
        )
        if self.completeness_status is not expected:
            raise TraceModelError(
                "completeness_status does not match collection presence"
            )

    def _validate_eligibility(self) -> None:
        if not isinstance(self.eligible_modes, tuple):
            raise TraceModelError("eligible_modes must be a tuple")
        if not self.eligible_modes:
            raise TraceModelError("eligible_modes must not be empty")
        if any(
            not isinstance(mode, ObservatoryMode)
            for mode in self.eligible_modes
        ):
            raise TraceModelError(
                "eligible_modes must contain ObservatoryMode values"
            )
        if len(set(self.eligible_modes)) != len(self.eligible_modes):
            raise TraceModelError("eligible_modes must be unique")
        if ObservatoryMode.ARTIFACT_AUDITOR not in self.eligible_modes:
            raise TraceModelError(
                "trace datasets must remain available to Artifact Auditor"
            )
        allowed_modes = _FAMILY_ALLOWED_MODES[self.trace_family]
        if any(
            mode not in allowed_modes for mode in self.eligible_modes
        ):
            raise TraceModelError(
                "eligible_modes contains a mode unsupported by this family"
            )

        display_modes = {
            ObservatoryMode.TRACE_EXPLORER,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
        }
        has_display_mode = any(
            mode in display_modes for mode in self.eligible_modes
        )
        display_ready = (
            self.ordering_validation
            is OrderingValidationStatus.VALIDATED_SOURCE_ORDER
            and self.completeness_status
            is TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT
            and all(
                snapshot.state_domain_valid
                for snapshot in self.state_snapshots or ()
            )
        )
        if has_display_mode and not display_ready:
            raise TraceModelError(
                "display modes require valid order, domain, and collections"
            )

    @property
    def tick_record_ids(self) -> tuple[str, ...] | None:
        """Return ordered tick IDs, preserving collection absence."""

        if self.tick_records is None:
            return None
        return tuple(
            record.tick_record_id for record in self.tick_records
        )

    @property
    def cell_record_ids(self) -> tuple[str, ...] | None:
        """Return ordered cell IDs, preserving collection absence."""

        if self.cell_records is None:
            return None
        return tuple(
            record.cell_trace_record_id for record in self.cell_records
        )

    @property
    def route_event_ids(self) -> tuple[str, ...] | None:
        """Return ordered route-event IDs, preserving absence."""

        if self.route_events is None:
            return None
        return tuple(
            event.route_event_record_id for event in self.route_events
        )

    @property
    def request_lane_records(
        self,
    ) -> tuple[RequestLaneRecord, ...] | None:
        """Return lanes in bundle and source order without reordering."""

        if self.request_bundles is None:
            return None
        return tuple(
            lane
            for bundle in self.request_bundles
            for lane in bundle.request_lanes
        )

    @property
    def request_lane_record_ids(self) -> tuple[str, ...] | None:
        """Return ordered request-lane IDs, preserving absence."""

        records = self.request_lane_records
        if records is None:
            return None
        return tuple(
            record.request_lane_record_id for record in records
        )

    @property
    def transition_record_ids(self) -> tuple[str, ...] | None:
        """Return ordered transition IDs, preserving absence."""

        if self.transitions is None:
            return None
        return tuple(
            transition.transition_record_id
            for transition in self.transitions
        )

    @property
    def record_counts(self) -> Mapping[str, int | None]:
        """Return observed sizes without replacing absence with zero."""

        collections = {
            "tick_records": self.tick_records,
            "cell_records": self.cell_records,
            "route_events": self.route_events,
            "request_lane_records": self.request_lane_records,
            "transitions": self.transitions,
            "scheduler_snapshots": self.scheduler_snapshots,
            "state_snapshots": self.state_snapshots,
            "transition_telemetry_records": (
                self.transition_telemetry_records
            ),
            "telemetry_snapshots": self.telemetry_snapshots,
            "event_counter_snapshots": self.event_counter_snapshots,
        }
        return MappingProxyType(
            {
                field_name: (
                    None if values is None else len(values)
                )
                for field_name, values in collections.items()
            }
        )

 
