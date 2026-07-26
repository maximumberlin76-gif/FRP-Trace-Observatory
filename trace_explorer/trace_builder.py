"""Deterministic read-only construction of Trace Explorer datasets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from re import fullmatch
from typing import Final, cast
from uuid import UUID, uuid5

from artifact_auditor.audit_report import (
    AuditReport,
    CheckOutcome,
    SourceLocation,
    ValidationCategory,
    ValidationStatus,
)
from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
)
from parsers.json_artifact import JsonValue, ParsedJsonArtifact
from parsers.m15_vector import (
    M15VectorArtifact,
    M15VectorRow,
    M15VectorTraceKind,
)
from schemas.registry import MeasurementContour, ObservatoryMode
from transition_visualizer.request_route_model import (
    RequestAcceptanceStatus,
    RequestLaneRecord,
    RouteEventRecord,
    RouteStatus,
)
from transition_visualizer.scheduler_model import (
    SchedulerField,
    SchedulerFieldValue,
    SchedulerMode,
    SchedulerSnapshot,
    SchedulerState,
)
from transition_visualizer.telemetry_model import (
    EventCounterName,
    EventCounterSnapshot,
    EventCounterValue,
    TransitionTelemetryField,
    TransitionTelemetryRecord,
    TransitionTelemetryValue,
)
from transition_visualizer.transition_model import (
    CanonicalTernaryState,
    RecordOrigin,
    SourceRecordReference,
    TernaryStateValue,
)

from .trace_model import (
    AggregationClassification,
    CellTraceRecord,
    OrderingValidationStatus,
    RequestBundle,
    TernaryStateSnapshot,
    TickRecord,
    TraceCompletenessStatus,
    TraceDataset,
    TraceFamily,
    TraceField,
    TraceFieldValue,
    TraceTelemetrySnapshot,
)


__all__ = [
    "TraceBuilderError",
    "TraceDatasetBuilder",
    "build_trace_dataset",
]


_STRUCTURED_OUTPUT_SCHEMA: Final = "frp.structured_output.v1.7.0"
_CYCLE_EXACT_SCHEMA: Final = (
    "frp.m15.cycle_exact_reference_trace.v1.7.0"
)
_M15_VECTOR_FORMAT: Final = "frp.m15.vector.v1"
_STATE_ENCODING_BINDING: Final = (
    "frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0"
)

_VALID_REPORT_STATUSES: Final = frozenset(
    {
        ValidationStatus.RECOGNIZED_VALID,
        ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
    }
)

_STATE_CODE_MAP: Final = {
    0: CanonicalTernaryState.NEUTRAL,
    1: CanonicalTernaryState.POSITIVE,
    3: CanonicalTernaryState.NEGATIVE,
}
_RESERVED_STATE_CODE: Final = 2

_SCHEDULER_MODE_CODE_MAP: Final = {
    0: SchedulerMode.FREE,
    1: SchedulerMode.BALANCE_COMMIT,
    2: SchedulerMode.EXCITE_NEUTRALIZE,
}
_SCHEDULER_STATE_CODE_MAP: Final = {
    0: SchedulerState.FREE,
    1: SchedulerState.BALANCE,
    2: SchedulerState.COMMIT,
    3: SchedulerState.EXCITE,
    4: SchedulerState.NEUTRALIZE,
}

_JSON_TELEMETRY_FIELDS: Final = frozenset(
    {
        "pending_route_count",
        "switch_load_q16",
        "heat_global_q16",
        "global_phase_coherence_q30",
        "C_q16",
        "P_q16",
        "C_minus_P_q16",
    }
)
_VECTOR_TELEMETRY_FIELDS: Final = frozenset(
    {
        "PENDING_ROUTE_COUNT",
        "SWITCH_LOAD_Q",
        "HEAT_GLOBAL_Q",
        "COHERENCE_GLOBAL_Q",
        "C_Q",
        "P_Q",
        "C_MINUS_P_Q",
    }
)

_JSON_CELL_FIELDS: Final = (
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
)
_VECTOR_CELL_FIELDS: Final = (
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
)

_JSON_EVENT_COUNTERS: Final = {
    "requested_direct_events": EventCounterName.REQUESTED_DIRECT_EVENTS,
    "prevented_direct_events": EventCounterName.PREVENTED_DIRECT_EVENTS,
    "neutral_routed_events": EventCounterName.NEUTRAL_ROUTED_EVENTS,
    "neutralized_conflicts": EventCounterName.NEUTRALIZED_CONFLICTS,
    "actual_direct_events": EventCounterName.ACTUAL_DIRECT_EVENTS,
    "reserved_state_events": EventCounterName.RESERVED_STATE_EVENTS,
    "queue_overflow_events": EventCounterName.QUEUE_OVERFLOW_EVENTS,
}
_VECTOR_EVENT_COUNTERS: Final = {
    "REQUESTED_DIRECT_EVENTS": EventCounterName.REQUESTED_DIRECT_EVENTS,
    "PREVENTED_DIRECT_EVENTS": EventCounterName.PREVENTED_DIRECT_EVENTS,
    "NEUTRAL_ROUTED_EVENTS": EventCounterName.NEUTRAL_ROUTED_EVENTS,
    "NEUTRALIZED_CONFLICTS": EventCounterName.NEUTRALIZED_CONFLICTS,
    "ACTUAL_DIRECT_EVENTS": EventCounterName.ACTUAL_DIRECT_EVENTS,
}

_UNIT_BY_FIELD: Final = {
    "switch_load_q16": "S32Q16",
    "heat_global_q16": "S32Q16",
    "global_phase_coherence_q30": "S32Q30",
    "C_q16": "S32Q16",
    "P_q16": "S32Q16",
    "C_minus_P_q16": "S32Q16",
    "frequency_target_q16": "S32Q16",
    "frequency_current_q16": "S32Q16",
    "frequency_lag_q16": "S32Q16",
    "generated_power_q16": "S32Q16",
    "heat_q16": "S32Q16",
    "thermal_overload_q16": "S32Q16",
    "gamma_noise_state_q16": "S32Q16",
    "gamma_effective_word": "GAMMA_S32",
    "thermal_node_factor_q30": "S32Q30",
    "coupling_field_q16": "S32Q16",
    "SWITCH_LOAD_Q": "S32Q16",
    "HEAT_GLOBAL_Q": "S32Q16",
    "COHERENCE_GLOBAL_Q": "S32Q30",
    "C_Q": "S32Q16",
    "P_Q": "S32Q16",
    "C_MINUS_P_Q": "S32Q16",
    "FREQUENCY_TARGET_Q": "S32Q16",
    "FREQUENCY_CURRENT_Q": "S32Q16",
    "FREQUENCY_LAG_Q": "S32Q16",
    "GENERATED_POWER_Q": "S32Q16",
    "HEAT_Q": "S32Q16",
    "THERMAL_OVERLOAD_Q": "S32Q16",
    "GAMMA_NOISE_STATE_Q": "S32Q16",
    "GAMMA_EFFECTIVE_WORD": "GAMMA_S32",
    "THERMAL_NODE_FACTOR_Q": "S32Q30",
    "COUPLING_FIELD_Q": "S32Q16",
}

_CUMULATIVE_FIELDS: Final = frozenset(
    set(_JSON_EVENT_COUNTERS) | set(_VECTOR_EVENT_COUNTERS)
)
_CURRENT_TICK_FIELDS: Final = frozenset(
    {
        "changes",
        "CHANGES",
        "pending_route_count",
        "PENDING_ROUTE_COUNT",
    }
)

_PRIMARY_VECTOR_KINDS: Final = frozenset(
    {
        M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
        M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
        M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
        M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
        M15VectorTraceKind.FULL_CORRELATION_VECTORS,
    }
)

_DISPLAY_MODES_BY_FAMILY: Final = {
    TraceFamily.STRUCTURED_PROCESSOR_TICK: (
        ObservatoryMode.TRACE_EXPLORER,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ),
    TraceFamily.CYCLE_EXACT_REFERENCE: (
        ObservatoryMode.TRACE_EXPLORER,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ),
    TraceFamily.M15_PRIMARY_VECTOR: (
        ObservatoryMode.TRACE_EXPLORER,
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ),
    TraceFamily.M15_PER_CELL_VECTOR: (
        ObservatoryMode.TRACE_EXPLORER,
    ),
    TraceFamily.M15_PENDING_ROUTE: (
        ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ),
}

_DECIMAL_PATTERN: Final = r"-?[0-9]+"
_HEX_PATTERN: Final = r"[0-9A-F]+"


class TraceBuilderError(ValueError):
    """Raised when an audited artifact cannot form a trace dataset."""


def _validate_uuid(value: str, field_name: str) -> UUID:
    if not isinstance(value, str):
        raise TraceBuilderError(f"{field_name} must be a string")
    try:
        return UUID(value)
    except (ValueError, AttributeError) as exc:
        raise TraceBuilderError(
            f"{field_name} must be a valid UUID"
        ) from exc


def _require_mapping(
    value: JsonValue | object,
    json_path: str,
) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise TraceBuilderError(f"{json_path} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise TraceBuilderError(
            f"{json_path} must contain string member names"
        )
    return cast(Mapping[str, JsonValue], value)


def _require_array(
    value: JsonValue | object,
    json_path: str,
) -> tuple[JsonValue, ...]:
    if not isinstance(value, tuple):
        raise TraceBuilderError(f"{json_path} must be an array")
    return value


def _require_integer(value: object, source_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceBuilderError(f"{source_path} must be an integer")
    return value


def _require_nonnegative_integer(
    value: object,
    source_path: str,
) -> int:
    integer = _require_integer(value, source_path)
    if integer < 0:
        raise TraceBuilderError(
            f"{source_path} must be nonnegative"
        )
    return integer


def _require_string(value: object, source_path: str) -> str:
    if not isinstance(value, str):
        raise TraceBuilderError(f"{source_path} must be a string")
    if not value or value != value.strip() or "\x00" in value:
        raise TraceBuilderError(
            f"{source_path} must be nonempty without outer whitespace"
        )
    return value


def _trace_field_value(
    value: object,
    source_path: str,
) -> TraceFieldValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise TraceBuilderError(f"{source_path} must be finite")
        return value
    if isinstance(value, tuple):
        return tuple(
            _trace_field_value(
                item,
                f"{source_path}[{index}]",
            )
            for index, item in enumerate(value)
        )
    raise TraceBuilderError(
        f"{source_path} cannot be represented as one trace field"
    )


def _parse_decimal(text: str, source_path: str) -> int:
    if not isinstance(text, str) or fullmatch(
        _DECIMAL_PATTERN,
        text,
    ) is None:
        raise TraceBuilderError(
            f"{source_path} must use canonical decimal integer text"
        )
    return int(text, 10)


def _parse_nonnegative_decimal(
    text: str,
    source_path: str,
) -> int:
    value = _parse_decimal(text, source_path)
    if value < 0:
        raise TraceBuilderError(
            f"{source_path} must be nonnegative"
        )
    return value


def _parse_hex(text: str, source_path: str) -> int:
    if not isinstance(text, str) or fullmatch(
        _HEX_PATTERN,
        text,
    ) is None:
        raise TraceBuilderError(
            f"{source_path} must use uppercase hexadecimal text"
        )
    return int(text, 16)


def _aggregation_for_field(
    field_name: str,
) -> AggregationClassification | None:
    if field_name in _CUMULATIVE_FIELDS:
        return AggregationClassification.CUMULATIVE
    if field_name in _CURRENT_TICK_FIELDS:
        return AggregationClassification.CURRENT_TICK
    return None


def _vector_encoding(field_name: str) -> str:
    if field_name in {
        "SCHED_MODE",
        "SCHED_STATE",
        "REQ_VALID_MASK",
        "STATES_PACKED",
        "STATE_CODE",
        "TARGET_STATE_CODE",
        "PHASE_WORD",
    }:
        return "uppercase_hex_text"
    if field_name in {"REQ_CELL_IDS", "REQ_TARGET_STATES"}:
        return "comma_separated_uppercase_hex_text"
    if field_name == "GAMMA_NOISE_TARGETS_Q":
        return "comma_separated_decimal_text"
    if field_name == "ROUTE_STATUS":
        return "utf8_text"
    return "decimal_text"


def _decode_state_code(
    code: int,
    source_path: str,
) -> CanonicalTernaryState:
    if code == _RESERVED_STATE_CODE:
        raise TraceBuilderError(
            f"{source_path} contains the reserved ternary code"
        )
    try:
        return _STATE_CODE_MAP[code]
    except KeyError as exc:
        raise TraceBuilderError(
            f"{source_path} contains an unknown ternary code"
        ) from exc


def _decode_scheduler_mode(
    code: int,
    source_path: str,
) -> SchedulerMode:
    try:
        return _SCHEDULER_MODE_CODE_MAP[code]
    except KeyError as exc:
        raise TraceBuilderError(
            f"{source_path} contains an unknown scheduler mode code"
        ) from exc


def _decode_scheduler_state(
    code: int,
    source_path: str,
) -> SchedulerState:
    try:
        return _SCHEDULER_STATE_CODE_MAP[code]
    except KeyError as exc:
        raise TraceBuilderError(
            f"{source_path} contains an unknown scheduler state code"
        ) from exc


def _route_status(value: str, source_path: str) -> RouteStatus:
    try:
        return RouteStatus(value)
    except ValueError as exc:
        raise TraceBuilderError(
            f"{source_path} contains an unsupported route status"
        ) from exc


def _nondecreasing(values: tuple[int, ...]) -> bool:
    return all(
        current <= following
        for current, following in zip(values, values[1:], strict=False)
    )


@dataclass(frozen=True, slots=True)
class _IdentifierFactory:
    namespace: UUID

    def make(self, role: str, *parts: object) -> str:
        name = ":".join(
            (role, *(str(part) for part in parts))
        )
        return str(uuid5(self.namespace, name))


@dataclass(slots=True)
class _BuildSession:
    dispatched_artifact: DispatchedArtifact
    audit_report: AuditReport
    trace_family: TraceFamily
    trace_dataset_id: str
    normalized_artifact_id: str
    identifiers: _IdentifierFactory
    source_references: list[SourceRecordReference] = field(
        default_factory=list
    )

    def add_source_reference(
        self,
        *,
        tick: int,
        source_locations: tuple[SourceLocation, ...],
        role: str,
    ) -> SourceRecordReference:
        ordinal = len(self.source_references)
        registration = self.dispatched_artifact.registration
        record = registration.compatibility_record
        if record is None or self.audit_report.registry_binding_id is None:
            raise TraceBuilderError(
                "trace construction requires an exact registry binding"
            )

        schema_identifier = None
        format_identifier = None
        if self.dispatched_artifact.classification is (
            ArtifactClassification.JSON
        ):
            schema_identifier = record.identifier
        elif self.dispatched_artifact.classification is (
            ArtifactClassification.M15_VECTOR
        ):
            format_identifier = record.identifier
        else:
            raise TraceBuilderError(
                "unsupported artifact classification for trace records"
            )

        reference = SourceRecordReference(
            normalized_record_id=self.identifiers.make(
                "source-record",
                ordinal,
                role,
            ),
            source_artifact_id=(
                self.dispatched_artifact.source_artifact.source_artifact_id
            ),
            trace_dataset_id=self.trace_dataset_id,
            registry_binding_id=self.audit_report.registry_binding_id,
            validation_report_id=self.audit_report.audit_report_id,
            source_sha256=(
                self.dispatched_artifact.source_artifact.content_sha256
            ),
            source_ordinal=ordinal,
            tick=tick,
            validation_status=self.audit_report.overall_status,
            source_locations=source_locations,
            schema_identifier=schema_identifier,
            format_identifier=format_identifier,
        )
        self.source_references.append(reference)
        return reference


def _check_ids(
    report: AuditReport,
    *categories: ValidationCategory,
) -> tuple[str, ...]:
    selected = set(categories)
    return tuple(
        check.check_id
        for check in report.checks
        if not selected or check.category in selected
    )


def _json_location(
    json_path: str,
    *,
    array_index: int | None = None,
    source_record_ordinal: int | None = None,
) -> SourceLocation:
    return SourceLocation(
        json_path=json_path,
        array_index=array_index,
        source_record_ordinal=source_record_ordinal,
    )


def _vector_location(
    row: M15VectorRow,
    *,
    column: str | None = None,
    source_record_ordinal: int | None = None,
) -> SourceLocation:
    return SourceLocation(
        line_number=row.line_number,
        vector_column=column,
        source_record_ordinal=source_record_ordinal,
    )


def _json_encoding(value: object) -> str:
    if value is None:
        return "json_null"
    if isinstance(value, bool):
        return "json_boolean"
    if isinstance(value, (int, Decimal)):
        return "json_number"
    if isinstance(value, str):
        return "json_string"
    if isinstance(value, tuple):
        return "json_array"
    raise TraceBuilderError(
        "unsupported JSON value for trace-field encoding"
    )


def _json_trace_field(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    *,
    role: str,
    field_name: str,
    value: object,
    source_location: SourceLocation,
) -> TraceField:
    return TraceField(
        trace_field_id=session.identifiers.make(
            "json-trace-field",
            role,
            source_reference.source_ordinal,
            field_name,
        ),
        source_reference=source_reference,
        field_name=field_name,
        value=_trace_field_value(
            value,
            source_location.json_path or field_name,
        ),
        source_location=source_location,
        source_encoding=_json_encoding(value),
        unit=_UNIT_BY_FIELD.get(field_name),
        aggregation=_aggregation_for_field(field_name),
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TYPE,
            ValidationCategory.ALLOWED_VALUE,
        ),
    )


def _vector_trace_field(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    *,
    role: str,
    field_name: str,
    raw_value: str,
    source_location: SourceLocation,
) -> TraceField:
    return TraceField(
        trace_field_id=session.identifiers.make(
            "vector-trace-field",
            role,
            source_reference.source_ordinal,
            field_name,
        ),
        source_reference=source_reference,
        field_name=field_name,
        value=raw_value,
        source_location=source_location,
        source_encoding=_vector_encoding(field_name),
        unit=_UNIT_BY_FIELD.get(field_name),
        aggregation=_aggregation_for_field(field_name),
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TYPE,
            ValidationCategory.ALLOWED_VALUE,
        ),
    )


def _row_values(
    artifact: M15VectorArtifact,
    row: M15VectorRow,
) -> Mapping[str, str]:
    return dict(zip(artifact.columns, row.fields, strict=True))


def _require_member(
    mapping: Mapping[str, JsonValue],
    member: str,
    json_path: str,
) -> JsonValue:
    if member not in mapping:
        raise TraceBuilderError(
            f"{json_path} is missing required member {member}"
        )
    return mapping[member]


def _configuration_integer(
    configuration: Mapping[str, JsonValue],
    field_name: str,
) -> int:
    return _require_nonnegative_integer(
        _require_member(
            configuration,
            field_name,
            "$.configuration",
        ),
        f"$.configuration.{field_name}",
    )


def _metadata_integer(
    artifact: M15VectorArtifact,
    field_name: str,
) -> int:
    try:
        value = artifact.metadata_value(field_name)
    except KeyError as exc:
        raise TraceBuilderError(
            f"vector metadata is missing {field_name}"
        ) from exc
    return _require_nonnegative_integer(
        value,
        f"metadata.{field_name}",
    )


def _normalized_state_value(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    *,
    role: str,
    cell_id: int,
    source_value: int | str,
    state_code: int,
    source_encoding: str,
) -> TernaryStateValue:
    return TernaryStateValue(
        state_value_id=session.identifiers.make(
            "ternary-state-value",
            role,
            source_reference.source_ordinal,
            cell_id,
        ),
        source_reference=source_reference,
        cell_id=cell_id,
        source_value=source_value,
        source_encoding=source_encoding,
        canonical_state=_decode_state_code(
            state_code,
            f"{role}.cell[{cell_id}]",
        ),
        origin=RecordOrigin.OBSERVATORY_NORMALIZED,
        encoding_map_identifier=_STATE_ENCODING_BINDING,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TERNARY_DOMAIN,
        ),
    )


def _decoded_packed_states(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    *,
    packed_value: int,
    cell_count: int,
    role: str,
) -> tuple[TernaryStateValue, ...]:
    if packed_value < 0 or packed_value >= (1 << (2 * cell_count)):
        raise TraceBuilderError(
            f"{role} packed state is outside the configured width"
        )
    return tuple(
        _normalized_state_value(
            session,
            source_reference,
            role=role,
            cell_id=cell_id,
            source_value=(packed_value >> (2 * cell_id)) & 3,
            state_code=(packed_value >> (2 * cell_id)) & 3,
            source_encoding="packed_two_bit_cell_code",
        )
        for cell_id in range(cell_count)
    )


def _human_state_string(
    cell_states: tuple[TernaryStateValue, ...],
) -> str:
    symbols = {
        CanonicalTernaryState.NEGATIVE: "M",
        CanonicalTernaryState.NEUTRAL: "N",
        CanonicalTernaryState.POSITIVE: "P",
    }
    return "".join(
        symbols[state.canonical_state] for state in cell_states
    )


def _ordering_status(
    report: AuditReport,
    *,
    local_order_valid: bool,
) -> OrderingValidationStatus:
    ordering_checks = tuple(
        check
        for check in report.checks
        if check.category is ValidationCategory.ORDERING
    )
    if not ordering_checks:
        return OrderingValidationStatus.NOT_EVALUATED
    if any(
        check.outcome is not CheckOutcome.PASS
        for check in ordering_checks
    ):
        return OrderingValidationStatus.NOT_EVALUATED
    if not local_order_valid:
        raise TraceBuilderError(
            "local source-order verification contradicts the audit report"
        )
    return OrderingValidationStatus.VALIDATED_SOURCE_ORDER


def _eligible_modes(
    trace_family: TraceFamily,
    *,
    ordering_status: OrderingValidationStatus,
    completeness_status: TraceCompletenessStatus,
    state_domain_valid: bool,
) -> tuple[ObservatoryMode, ...]:
    modes = [ObservatoryMode.ARTIFACT_AUDITOR]
    if (
        ordering_status
        is OrderingValidationStatus.VALIDATED_SOURCE_ORDER
        and completeness_status
        is TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT
        and state_domain_valid
    ):
        modes.extend(_DISPLAY_MODES_BY_FAMILY[trace_family])
    return tuple(modes)


def _json_configuration_fields(
    session: _BuildSession,
    configuration: Mapping[str, JsonValue],
) -> tuple[TraceField, ...]:
    if not configuration:
        raise TraceBuilderError(
            "$.configuration must not be empty"
        )
    reference = session.add_source_reference(
        tick=0,
        source_locations=(
            _json_location("$.configuration"),
        ),
        role="configuration",
    )
    return tuple(
        _json_trace_field(
            session,
            reference,
            role="configuration",
            field_name=field_name,
            value=value,
            source_location=_json_location(
                f"$.configuration.{field_name}"
            ),
        )
        for field_name, value in configuration.items()
    )


def _vector_configuration_fields(
    session: _BuildSession,
    artifact: M15VectorArtifact,
) -> tuple[TraceField, ...]:
    first_entry = artifact.metadata_entries[0]
    reference = session.add_source_reference(
        tick=0,
        source_locations=(
            SourceLocation(
                line_number=first_entry.line_number,
                vector_column=first_entry.key,
            ),
        ),
        role="metadata",
    )
    return tuple(
        TraceField(
            trace_field_id=session.identifiers.make(
                "vector-metadata-field",
                entry.key,
            ),
            source_reference=reference,
            field_name=entry.key,
            value=_trace_field_value(
                entry.value,
                f"metadata.{entry.key}",
            ),
            source_location=SourceLocation(
                line_number=entry.line_number,
                vector_column=entry.key,
            ),
            source_encoding="json_metadata_value",
            aggregation=None,
            validation_check_ids=_check_ids(
                session.audit_report,
                ValidationCategory.STRUCTURE,
                ValidationCategory.TYPE,
                ValidationCategory.ALLOWED_VALUE,
            ),
        )
        for entry in artifact.metadata_entries
    )


def _json_scheduler_snapshot(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    row: Mapping[str, JsonValue],
    row_path: str,
) -> SchedulerSnapshot:
    mode_code = _require_nonnegative_integer(
        _require_member(row, "scheduler_mode", row_path),
        f"{row_path}.scheduler_mode",
    )
    state_code = _require_nonnegative_integer(
        _require_member(row, "scheduler_state", row_path),
        f"{row_path}.scheduler_state",
    )
    published_name = _require_string(
        _require_member(row, "scheduler_state_name", row_path),
        f"{row_path}.scheduler_state_name",
    )
    mode = _decode_scheduler_mode(
        mode_code,
        f"{row_path}.scheduler_mode",
    )
    state = _decode_scheduler_state(
        state_code,
        f"{row_path}.scheduler_state",
    )
    if published_name != state.value:
        raise TraceBuilderError(
            f"{row_path}.scheduler_state_name contradicts its code"
        )
    check_ids = _check_ids(
        session.audit_report,
        ValidationCategory.SCHEDULER_RELATION,
    )
    return SchedulerSnapshot(
        scheduler_snapshot_id=session.identifiers.make(
            "scheduler-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        state=SchedulerFieldValue(
            scheduler_field_value_id=session.identifiers.make(
                "scheduler-field",
                source_reference.source_ordinal,
                "state",
            ),
            source_reference=source_reference,
            field=SchedulerField.STATE,
            source_value=state_code,
            normalized_value=state,
            source_location=_json_location(
                f"{row_path}.scheduler_state"
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            encoding_map_identifier=_STATE_ENCODING_BINDING,
            published_name=published_name,
            validation_check_ids=check_ids,
        ),
        mode=SchedulerFieldValue(
            scheduler_field_value_id=session.identifiers.make(
                "scheduler-field",
                source_reference.source_ordinal,
                "mode",
            ),
            source_reference=source_reference,
            field=SchedulerField.MODE,
            source_value=mode_code,
            normalized_value=mode,
            source_location=_json_location(
                f"{row_path}.scheduler_mode"
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            encoding_map_identifier=_STATE_ENCODING_BINDING,
            validation_check_ids=check_ids,
        ),
        validation_check_ids=check_ids,
    )


def _json_request_bundle(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    row: Mapping[str, JsonValue],
    row_path: str,
    request_lane_count: int,
) -> RequestBundle:
    valid_mask = _require_nonnegative_integer(
        _require_member(row, "request_valid_mask", row_path),
        f"{row_path}.request_valid_mask",
    )
    cell_values = _require_array(
        _require_member(row, "request_cell_ids", row_path),
        f"{row_path}.request_cell_ids",
    )
    target_values = _require_array(
        _require_member(row, "request_target_states", row_path),
        f"{row_path}.request_target_states",
    )
    if (
        len(cell_values) != request_lane_count
        or len(target_values) != request_lane_count
    ):
        raise TraceBuilderError(
            f"{row_path} request arrays do not match request_lanes"
        )
    if valid_mask >= (1 << request_lane_count):
        raise TraceBuilderError(
            f"{row_path}.request_valid_mask exceeds request_lanes"
        )

    cell_ids = tuple(
        _require_nonnegative_integer(
            value,
            f"{row_path}.request_cell_ids[{index}]",
        )
        for index, value in enumerate(cell_values)
    )
    target_codes = tuple(
        _require_nonnegative_integer(
            value,
            f"{row_path}.request_target_states[{index}]",
        )
        for index, value in enumerate(target_values)
    )
    check_ids = _check_ids(
        session.audit_report,
        ValidationCategory.TERNARY_DOMAIN,
        ValidationCategory.TRANSITION_CAPACITY,
    )
    lanes = tuple(
        RequestLaneRecord(
            request_lane_record_id=session.identifiers.make(
                "request-lane",
                source_reference.source_ordinal,
                lane_index,
            ),
            source_reference=source_reference,
            lane_index=lane_index,
            valid=bool(valid_mask & (1 << lane_index)),
            acceptance_status=(
                RequestAcceptanceStatus.NOT_RECORDED
                if valid_mask & (1 << lane_index)
                else RequestAcceptanceStatus.NOT_APPLICABLE
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            cell_id=cell_ids[lane_index],
            source_target_state=target_codes[lane_index],
            canonical_target_state=_decode_state_code(
                target_codes[lane_index],
                (
                    f"{row_path}.request_target_states"
                    f"[{lane_index}]"
                ),
            ),
            encoding_map_identifier=_STATE_ENCODING_BINDING,
            validation_check_ids=check_ids,
        )
        for lane_index in range(request_lane_count)
    )
    return RequestBundle(
        request_bundle_id=session.identifiers.make(
            "request-bundle",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        request_valid_mask=valid_mask,
        source_cell_ids=cell_ids,
        source_target_states=target_codes,
        request_lane_count=request_lane_count,
        request_lanes=lanes,
        request_encoding_binding=_STATE_ENCODING_BINDING,
        source_locations=(
            _json_location(f"{row_path}.request_valid_mask"),
            _json_location(f"{row_path}.request_cell_ids"),
            _json_location(f"{row_path}.request_target_states"),
        ),
        validation_check_ids=check_ids,
    )


def _json_state_snapshot(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    row: Mapping[str, JsonValue],
    row_path: str,
    cell_count: int,
) -> TernaryStateSnapshot:
    packed = _require_nonnegative_integer(
        _require_member(row, "states_packed", row_path),
        f"{row_path}.states_packed",
    )
    packed_hex = _require_string(
        _require_member(row, "states_packed_hex", row_path),
        f"{row_path}.states_packed_hex",
    )
    if (
        fullmatch(_HEX_PATTERN, packed_hex) is None
        or int(packed_hex, 16) != packed
    ):
        raise TraceBuilderError(
            f"{row_path}.states_packed_hex contradicts states_packed"
        )
    human_state = _require_string(
        _require_member(row, "states_human", row_path),
        f"{row_path}.states_human",
    )
    cell_states = _decoded_packed_states(
        session,
        source_reference,
        packed_value=packed,
        cell_count=cell_count,
        role=row_path,
    )
    if human_state != _human_state_string(cell_states):
        raise TraceBuilderError(
            f"{row_path}.states_human contradicts states_packed"
        )
    check_ids = _check_ids(
        session.audit_report,
        ValidationCategory.TERNARY_DOMAIN,
    )
    return TernaryStateSnapshot(
        state_snapshot_id=session.identifiers.make(
            "state-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        packed_integer=packed,
        packed_hex=packed_hex,
        human_state=human_state,
        cell_states=cell_states,
        state_encoding_binding=_STATE_ENCODING_BINDING,
        state_domain_valid=True,
        validation_check_ids=check_ids,
    )


def _json_trace_telemetry(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    row: Mapping[str, JsonValue],
    row_path: str,
) -> TraceTelemetrySnapshot | None:
    fields = tuple(
        _json_trace_field(
            session,
            source_reference,
            role="telemetry",
            field_name=field_name,
            value=value,
            source_location=_json_location(
                f"{row_path}.{field_name}"
            ),
        )
        for field_name, value in row.items()
        if field_name in _JSON_TELEMETRY_FIELDS
    )
    if not fields:
        return None
    return TraceTelemetrySnapshot(
        telemetry_snapshot_id=session.identifiers.make(
            "trace-telemetry-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        fields=fields,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.ALLOWED_VALUE,
            ValidationCategory.TRANSITION_CAPACITY,
        ),
    )


def _json_transition_telemetry(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    row: Mapping[str, JsonValue],
    row_path: str,
) -> TransitionTelemetryRecord | None:
    available = (
        (
            "changes",
            TransitionTelemetryField.CURRENT_TICK_CHANGES,
        ),
        (
            "switch_load_q16",
            TransitionTelemetryField.SWITCH_LOAD,
        ),
    )
    values = tuple(
        TransitionTelemetryValue(
            telemetry_value_id=session.identifiers.make(
                "transition-telemetry-value",
                source_reference.source_ordinal,
                field_name,
            ),
            field=telemetry_field,
            value=_require_nonnegative_integer(
                row[field_name],
                f"{row_path}.{field_name}",
            ),
            origin=RecordOrigin.UPSTREAM_SOURCE,
            source_references=(source_reference,),
            source_locations=(
                _json_location(f"{row_path}.{field_name}"),
            ),
            source_field_name=field_name,
            validation_check_ids=_check_ids(
                session.audit_report,
                ValidationCategory.TRANSITION_CAPACITY,
            ),
        )
        for field_name, telemetry_field in available
        if field_name in row
    )
    if not values:
        return None
    return TransitionTelemetryRecord(
        telemetry_record_id=session.identifiers.make(
            "transition-telemetry-record",
            source_reference.source_ordinal,
        ),
        tick_reference=source_reference,
        values=values,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TRANSITION_CAPACITY,
        ),
    )


def _json_event_counters(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    row: Mapping[str, JsonValue],
    row_path: str,
) -> EventCounterSnapshot | None:
    counters = tuple(
        EventCounterValue(
            counter_value_id=session.identifiers.make(
                "event-counter-value",
                source_reference.source_ordinal,
                field_name,
            ),
            counter=counter,
            value=_require_nonnegative_integer(
                row[field_name],
                f"{row_path}.{field_name}",
            ),
            source_reference=source_reference,
            source_location=_json_location(
                f"{row_path}.{field_name}"
            ),
            origin=RecordOrigin.UPSTREAM_SOURCE,
            accumulation_classification="cumulative",
            validation_check_ids=_check_ids(
                session.audit_report,
                ValidationCategory.INVARIANT_VECTOR,
                ValidationCategory.QUALIFICATION_EVIDENCE,
            ),
        )
        for field_name, counter in _JSON_EVENT_COUNTERS.items()
        if field_name in row
    )
    if not counters:
        return None
    return EventCounterSnapshot(
        counter_snapshot_id=session.identifiers.make(
            "event-counter-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        counters=counters,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.INVARIANT_VECTOR,
            ValidationCategory.QUALIFICATION_EVIDENCE,
        ),
    )


@dataclass(frozen=True, slots=True)
class _TickAssembly:
    tick_record: TickRecord
    state_snapshot: TernaryStateSnapshot
    request_bundle: RequestBundle
    scheduler_snapshot: SchedulerSnapshot
    transition_telemetry: TransitionTelemetryRecord | None
    trace_telemetry: TraceTelemetrySnapshot | None
    event_counters: EventCounterSnapshot | None


def _json_tick_assembly(
    session: _BuildSession,
    row_value: JsonValue,
    *,
    row_index: int,
    cell_count: int,
    request_lane_count: int,
) -> _TickAssembly:
    row_path = f"$.trace[{row_index}]"
    row = _require_mapping(row_value, row_path)
    tick = _require_nonnegative_integer(
        _require_member(row, "tick", row_path),
        f"{row_path}.tick",
    )
    source_location = _json_location(
        row_path,
        array_index=row_index,
        source_record_ordinal=row_index + 1,
    )
    source_reference = session.add_source_reference(
        tick=tick,
        source_locations=(source_location,),
        role=f"tick-{row_index}",
    )
    source_fields = tuple(
        _json_trace_field(
            session,
            source_reference,
            role="tick",
            field_name=field_name,
            value=value,
            source_location=_json_location(
                f"{row_path}.{field_name}",
                array_index=row_index,
                source_record_ordinal=row_index + 1,
            ),
        )
        for field_name, value in row.items()
    )
    scheduler = _json_scheduler_snapshot(
        session,
        source_reference,
        row,
        row_path,
    )
    requests = _json_request_bundle(
        session,
        source_reference,
        row,
        row_path,
        request_lane_count,
    )
    states = _json_state_snapshot(
        session,
        source_reference,
        row,
        row_path,
        cell_count,
    )
    transition_telemetry = _json_transition_telemetry(
        session,
        source_reference,
        row,
        row_path,
    )
    trace_telemetry = _json_trace_telemetry(
        session,
        source_reference,
        row,
        row_path,
    )
    counters = _json_event_counters(
        session,
        source_reference,
        row,
        row_path,
    )
    changes = _require_nonnegative_integer(
        _require_member(row, "changes", row_path),
        f"{row_path}.changes",
    )
    record = TickRecord(
        tick_record_id=session.identifiers.make(
            "tick-record",
            source_reference.source_ordinal,
        ),
        trace_dataset_id=session.trace_dataset_id,
        source_reference=source_reference,
        source_location=source_location,
        source_ordinal=source_reference.source_ordinal,
        tick=tick,
        source_fields=source_fields,
        scheduler_snapshot_id=scheduler.scheduler_snapshot_id,
        request_bundle_id=requests.request_bundle_id,
        state_snapshot_id=states.state_snapshot_id,
        transition_telemetry_id=(
            transition_telemetry.telemetry_record_id
            if transition_telemetry is not None
            else None
        ),
        telemetry_snapshot_id=(
            trace_telemetry.telemetry_snapshot_id
            if trace_telemetry is not None
            else None
        ),
        event_counter_snapshot_id=(
            counters.counter_snapshot_id
            if counters is not None
            else None
        ),
        changes=changes,
        validation_check_ids=_check_ids(
            session.audit_report,
        ),
    )
    return _TickAssembly(
        tick_record=record,
        state_snapshot=states,
        request_bundle=requests,
        scheduler_snapshot=scheduler,
        transition_telemetry=transition_telemetry,
        trace_telemetry=trace_telemetry,
        event_counters=counters,
    )


def _json_cell_record(
    session: _BuildSession,
    row_value: JsonValue,
    *,
    row_index: int,
) -> CellTraceRecord:
    row_path = f"$.cell_trace[{row_index}]"
    row = _require_mapping(row_value, row_path)
    tick = _require_nonnegative_integer(
        _require_member(row, "tick", row_path),
        f"{row_path}.tick",
    )
    cell_id = _require_nonnegative_integer(
        _require_member(row, "cell_id", row_path),
        f"{row_path}.cell_id",
    )
    source_location = _json_location(
        row_path,
        array_index=row_index,
        source_record_ordinal=row_index + 1,
    )
    source_reference = session.add_source_reference(
        tick=tick,
        source_locations=(source_location,),
        role=f"cell-{row_index}",
    )
    fields = tuple(
        _json_trace_field(
            session,
            source_reference,
            role="cell",
            field_name=field_name,
            value=_require_member(row, field_name, row_path),
            source_location=_json_location(
                f"{row_path}.{field_name}",
                array_index=row_index,
                source_record_ordinal=row_index + 1,
            ),
        )
        for field_name in _JSON_CELL_FIELDS
    )
    state_code = _require_nonnegative_integer(
        _require_member(row, "state_code", row_path),
        f"{row_path}.state_code",
    )
    canonical_state = _normalized_state_value(
        session,
        source_reference,
        role=row_path,
        cell_id=cell_id,
        source_value=state_code,
        state_code=state_code,
        source_encoding="integer_state_code",
    )
    return CellTraceRecord(
        cell_trace_record_id=session.identifiers.make(
            "cell-trace-record",
            source_reference.source_ordinal,
        ),
        trace_dataset_id=session.trace_dataset_id,
        source_reference=source_reference,
        source_location=source_location,
        source_ordinal=source_reference.source_ordinal,
        tick=tick,
        cell_id=cell_id,
        fields=fields,
        canonical_state=canonical_state,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TYPE,
            ValidationCategory.TERNARY_DOMAIN,
            ValidationCategory.ORDERING,
        ),
    )


def _canonical_source_state(
    value: object,
    source_path: str,
) -> CanonicalTernaryState:
    integer = _require_integer(value, source_path)
    try:
        return CanonicalTernaryState(integer)
    except ValueError as exc:
        raise TraceBuilderError(
            f"{source_path} is outside the canonical ternary domain"
        ) from exc


def _json_route_event(
    session: _BuildSession,
    row_value: JsonValue,
    *,
    row_index: int,
) -> RouteEventRecord:
    row_path = f"$.route_events[{row_index}]"
    row = _require_mapping(row_value, row_path)
    tick = _require_nonnegative_integer(
        _require_member(row, "tick", row_path),
        f"{row_path}.tick",
    )
    source_location = _json_location(
        row_path,
        array_index=row_index,
        source_record_ordinal=row_index + 1,
    )
    source_reference = session.add_source_reference(
        tick=tick,
        source_locations=(source_location,),
        role=f"route-{row_index}",
    )
    source_target = _require_integer(
        _require_member(row, "target_state", row_path),
        f"{row_path}.target_state",
    )
    return RouteEventRecord(
        route_event_record_id=session.identifiers.make(
            "route-event-record",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        cell_id=_require_nonnegative_integer(
            _require_member(row, "cell_id", row_path),
            f"{row_path}.cell_id",
        ),
        source_target_state=source_target,
        canonical_target_state=_canonical_source_state(
            source_target,
            f"{row_path}.target_state",
        ),
        ready_tick=_require_nonnegative_integer(
            _require_member(row, "ready_tick", row_path),
            f"{row_path}.ready_tick",
        ),
        route_status=_route_status(
            _require_string(
                _require_member(row, "route_status", row_path),
                f"{row_path}.route_status",
            ),
            f"{row_path}.route_status",
        ),
        origin=RecordOrigin.UPSTREAM_SOURCE,
        route_index=row_index,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TERNARY_DOMAIN,
            ValidationCategory.PENDING_ROUTE,
            ValidationCategory.ORDERING,
        ),
    )


def _json_collections_present(
    root: Mapping[str, JsonValue],
    trace_family: TraceFamily,
) -> bool:
    required = (
        ("trace", "cell_trace", "route_events")
        if trace_family is TraceFamily.STRUCTURED_PROCESSOR_TICK
        else ("trace", "route_events")
    )
    return all(member in root for member in required)


def _json_local_order_valid(
    *,
    tick_records: tuple[TickRecord, ...] | None,
    cell_records: tuple[CellTraceRecord, ...] | None,
    route_events: tuple[RouteEventRecord, ...] | None,
    steps: int,
    cell_count: int,
    trace_family: TraceFamily,
) -> bool:
    if tick_records is None:
        return False
    tick_order = tuple(record.tick for record in tick_records)
    valid = tick_order == tuple(range(steps))
    if (
        trace_family is TraceFamily.STRUCTURED_PROCESSOR_TICK
        and cell_records is not None
    ):
        observed = tuple(
            (record.tick, record.cell_id)
            for record in cell_records
        )
        expected = tuple(
            (tick, cell_id)
            for tick in range(steps)
            for cell_id in range(cell_count)
        )
        valid = valid and observed == expected
    if route_events is not None:
        valid = valid and _nondecreasing(
            tuple(
                event.source_reference.tick
                for event in route_events
            )
        )
    return valid


def _build_json_dataset(
    session: _BuildSession,
    artifact: ParsedJsonArtifact,
) -> TraceDataset:
    root = artifact.root
    configuration = _require_mapping(
        _require_member(root, "configuration", "$"),
        "$.configuration",
    )
    configuration_fields = _json_configuration_fields(
        session,
        configuration,
    )
    cell_count = _configuration_integer(
        configuration,
        "cells",
    )
    request_lane_count = _configuration_integer(
        configuration,
        "request_lanes",
    )
    steps = _configuration_integer(configuration, "steps")
    collections_present = _json_collections_present(
        root,
        session.trace_family,
    )

    tick_records: tuple[TickRecord, ...] | None = None
    state_snapshots: tuple[TernaryStateSnapshot, ...] | None = None
    request_bundles: tuple[RequestBundle, ...] | None = None
    scheduler_snapshots: tuple[SchedulerSnapshot, ...] | None = None
    transition_telemetry: (
        tuple[TransitionTelemetryRecord, ...] | None
    ) = None
    trace_telemetry: tuple[TraceTelemetrySnapshot, ...] | None = None
    event_counters: tuple[EventCounterSnapshot, ...] | None = None
    cell_records: tuple[CellTraceRecord, ...] | None = None
    route_events: tuple[RouteEventRecord, ...] | None = None

    if "trace" in root:
        trace_values = _require_array(root["trace"], "$.trace")
        assemblies = tuple(
            _json_tick_assembly(
                session,
                row,
                row_index=index,
                cell_count=cell_count,
                request_lane_count=request_lane_count,
            )
            for index, row in enumerate(trace_values)
        )
        tick_records = tuple(
            assembly.tick_record for assembly in assemblies
        )
        state_snapshots = tuple(
            assembly.state_snapshot for assembly in assemblies
        )
        request_bundles = tuple(
            assembly.request_bundle for assembly in assemblies
        )
        scheduler_snapshots = tuple(
            assembly.scheduler_snapshot for assembly in assemblies
        )
        transition_telemetry = tuple(
            assembly.transition_telemetry
            for assembly in assemblies
            if assembly.transition_telemetry is not None
        )
        trace_telemetry = tuple(
            assembly.trace_telemetry
            for assembly in assemblies
            if assembly.trace_telemetry is not None
        )
        event_counters = tuple(
            assembly.event_counters
            for assembly in assemblies
            if assembly.event_counters is not None
        )

    if "cell_trace" in root:
        cell_values = _require_array(
            root["cell_trace"],
            "$.cell_trace",
        )
        cell_records = tuple(
            _json_cell_record(
                session,
                row,
                row_index=index,
            )
            for index, row in enumerate(cell_values)
        )

    if "route_events" in root:
        route_values = _require_array(
            root["route_events"],
            "$.route_events",
        )
        route_events = tuple(
            _json_route_event(
                session,
                row,
                row_index=index,
            )
            for index, row in enumerate(route_values)
        )

    completeness = (
        TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT
        if collections_present
        else TraceCompletenessStatus.REQUIRED_COLLECTIONS_MISSING
    )
    local_order_valid = (
        _json_local_order_valid(
            tick_records=tick_records,
            cell_records=cell_records,
            route_events=route_events,
            steps=steps,
            cell_count=cell_count,
            trace_family=session.trace_family,
        )
        if collections_present
        else False
    )
    ordering = _ordering_status(
        session.audit_report,
        local_order_valid=local_order_valid,
    )
    domain_valid = all(
        snapshot.state_domain_valid
        for snapshot in state_snapshots or ()
    )
    has_normalized_states = bool(
        state_snapshots or cell_records
    )
    measurement_contour = cast(
        MeasurementContour,
        session.audit_report.measurement_contour,
    )
    return TraceDataset(
        trace_dataset_id=session.trace_dataset_id,
        normalized_artifact_id=session.normalized_artifact_id,
        trace_family=session.trace_family,
        measurement_contour=measurement_contour,
        source_references=tuple(session.source_references),
        configuration_fields=configuration_fields,
        ordering_validation=ordering,
        completeness_status=completeness,
        eligible_modes=_eligible_modes(
            session.trace_family,
            ordering_status=ordering,
            completeness_status=completeness,
            state_domain_valid=domain_valid,
        ),
        schema_identifier=artifact.declared_schema_identifier,
        kind=artifact.declared_kind,
        state_encoding_binding=(
            _STATE_ENCODING_BINDING
            if has_normalized_states
            else None
        ),
        tick_records=tick_records,
        cell_records=cell_records,
        state_snapshots=state_snapshots,
        request_bundles=request_bundles,
        scheduler_snapshots=scheduler_snapshots,
        route_events=route_events,
        transitions=None,
        transition_telemetry_records=transition_telemetry,
        telemetry_snapshots=trace_telemetry,
        event_counter_snapshots=event_counters,
        package_record_ids=None,
        digest_record_ids=None,
        ordering_validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.ORDERING,
        ),
        validation_check_ids=_check_ids(session.audit_report),
    )


def _vector_scheduler_snapshot(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    values: Mapping[str, str],
    row: M15VectorRow,
) -> SchedulerSnapshot:
    mode_raw = values["SCHED_MODE"]
    state_raw = values["SCHED_STATE"]
    mode = _decode_scheduler_mode(
        _parse_hex(mode_raw, "SCHED_MODE"),
        "SCHED_MODE",
    )
    state = _decode_scheduler_state(
        _parse_hex(state_raw, "SCHED_STATE"),
        "SCHED_STATE",
    )
    check_ids = _check_ids(
        session.audit_report,
        ValidationCategory.SCHEDULER_RELATION,
    )
    return SchedulerSnapshot(
        scheduler_snapshot_id=session.identifiers.make(
            "scheduler-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        state=SchedulerFieldValue(
            scheduler_field_value_id=session.identifiers.make(
                "scheduler-field",
                source_reference.source_ordinal,
                "state",
            ),
            source_reference=source_reference,
            field=SchedulerField.STATE,
            source_value=state_raw,
            normalized_value=state,
            source_location=_vector_location(
                row,
                column="SCHED_STATE",
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            encoding_map_identifier=_STATE_ENCODING_BINDING,
            validation_check_ids=check_ids,
        ),
        mode=SchedulerFieldValue(
            scheduler_field_value_id=session.identifiers.make(
                "scheduler-field",
                source_reference.source_ordinal,
                "mode",
            ),
            source_reference=source_reference,
            field=SchedulerField.MODE,
            source_value=mode_raw,
            normalized_value=mode,
            source_location=_vector_location(
                row,
                column="SCHED_MODE",
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            encoding_map_identifier=_STATE_ENCODING_BINDING,
            validation_check_ids=check_ids,
        ),
        validation_check_ids=check_ids,
    )


def _split_vector_list(
    value: str,
    source_path: str,
) -> tuple[str, ...]:
    if value == "":
        return ()
    items = tuple(value.split(","))
    if any(not item for item in items):
        raise TraceBuilderError(
            f"{source_path} contains an empty list item"
        )
    return items


def _vector_request_bundle(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    values: Mapping[str, str],
    row: M15VectorRow,
    request_lane_count: int,
) -> RequestBundle:
    valid_mask_raw = values["REQ_VALID_MASK"]
    valid_mask = _parse_hex(valid_mask_raw, "REQ_VALID_MASK")
    cell_items = _split_vector_list(
        values["REQ_CELL_IDS"],
        "REQ_CELL_IDS",
    )
    target_items = _split_vector_list(
        values["REQ_TARGET_STATES"],
        "REQ_TARGET_STATES",
    )
    if (
        len(cell_items) != request_lane_count
        or len(target_items) != request_lane_count
    ):
        raise TraceBuilderError(
            "vector request arrays do not match request_lanes"
        )
    if valid_mask >= (1 << request_lane_count):
        raise TraceBuilderError(
            "REQ_VALID_MASK exceeds request_lanes"
        )
    cell_ids = tuple(
        _parse_hex(item, f"REQ_CELL_IDS[{index}]")
        for index, item in enumerate(cell_items)
    )
    target_codes = tuple(
        _parse_hex(item, f"REQ_TARGET_STATES[{index}]")
        for index, item in enumerate(target_items)
    )
    check_ids = _check_ids(
        session.audit_report,
        ValidationCategory.TERNARY_DOMAIN,
        ValidationCategory.TRANSITION_CAPACITY,
    )
    lanes = tuple(
        RequestLaneRecord(
            request_lane_record_id=session.identifiers.make(
                "request-lane",
                source_reference.source_ordinal,
                lane_index,
            ),
            source_reference=source_reference,
            lane_index=lane_index,
            valid=bool(valid_mask & (1 << lane_index)),
            acceptance_status=(
                RequestAcceptanceStatus.NOT_RECORDED
                if valid_mask & (1 << lane_index)
                else RequestAcceptanceStatus.NOT_APPLICABLE
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            cell_id=cell_ids[lane_index],
            source_target_state=target_items[lane_index],
            canonical_target_state=_decode_state_code(
                target_codes[lane_index],
                f"REQ_TARGET_STATES[{lane_index}]",
            ),
            encoding_map_identifier=_STATE_ENCODING_BINDING,
            validation_check_ids=check_ids,
        )
        for lane_index in range(request_lane_count)
    )
    return RequestBundle(
        request_bundle_id=session.identifiers.make(
            "request-bundle",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        request_valid_mask=valid_mask_raw,
        source_cell_ids=cell_ids,
        source_target_states=target_items,
        request_lane_count=request_lane_count,
        request_lanes=lanes,
        request_encoding_binding=_STATE_ENCODING_BINDING,
        source_locations=(
            _vector_location(row, column="REQ_VALID_MASK"),
            _vector_location(row, column="REQ_CELL_IDS"),
            _vector_location(row, column="REQ_TARGET_STATES"),
        ),
        validation_check_ids=check_ids,
    )


def _vector_state_snapshot(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    values: Mapping[str, str],
    cell_count: int,
) -> TernaryStateSnapshot:
    packed_raw = values["STATES_PACKED"]
    packed = _parse_hex(packed_raw, "STATES_PACKED")
    cell_states = _decoded_packed_states(
        session,
        source_reference,
        packed_value=packed,
        cell_count=cell_count,
        role="STATES_PACKED",
    )
    return TernaryStateSnapshot(
        state_snapshot_id=session.identifiers.make(
            "state-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        packed_integer=packed,
        packed_hex=packed_raw,
        cell_states=cell_states,
        state_encoding_binding=_STATE_ENCODING_BINDING,
        state_domain_valid=True,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TERNARY_DOMAIN,
        ),
    )


def _vector_trace_telemetry(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    values: Mapping[str, str],
    row: M15VectorRow,
) -> TraceTelemetrySnapshot | None:
    fields = tuple(
        _vector_trace_field(
            session,
            source_reference,
            role="telemetry",
            field_name=field_name,
            raw_value=raw_value,
            source_location=_vector_location(
                row,
                column=field_name,
            ),
        )
        for field_name, raw_value in values.items()
        if field_name in _VECTOR_TELEMETRY_FIELDS
    )
    if not fields:
        return None
    return TraceTelemetrySnapshot(
        telemetry_snapshot_id=session.identifiers.make(
            "trace-telemetry-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        fields=fields,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.ALLOWED_VALUE,
            ValidationCategory.TRANSITION_CAPACITY,
        ),
    )


def _vector_transition_telemetry(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    values: Mapping[str, str],
    row: M15VectorRow,
) -> TransitionTelemetryRecord | None:
    field_name = "SWITCH_LOAD_Q"
    if field_name not in values:
        return None
    value = TransitionTelemetryValue(
        telemetry_value_id=session.identifiers.make(
            "transition-telemetry-value",
            source_reference.source_ordinal,
            field_name,
        ),
        field=TransitionTelemetryField.SWITCH_LOAD,
        value=_parse_nonnegative_decimal(
            values[field_name],
            field_name,
        ),
        origin=RecordOrigin.OBSERVATORY_NORMALIZED,
        source_references=(source_reference,),
        source_locations=(
            _vector_location(row, column=field_name),
        ),
        source_field_name=field_name,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TRANSITION_CAPACITY,
        ),
    )
    return TransitionTelemetryRecord(
        telemetry_record_id=session.identifiers.make(
            "transition-telemetry-record",
            source_reference.source_ordinal,
        ),
        tick_reference=source_reference,
        values=(value,),
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TRANSITION_CAPACITY,
        ),
    )


def _vector_event_counters(
    session: _BuildSession,
    source_reference: SourceRecordReference,
    values: Mapping[str, str],
    row: M15VectorRow,
) -> EventCounterSnapshot | None:
    counters = tuple(
        EventCounterValue(
            counter_value_id=session.identifiers.make(
                "event-counter-value",
                source_reference.source_ordinal,
                field_name,
            ),
            counter=counter,
            value=_parse_nonnegative_decimal(
                values[field_name],
                field_name,
            ),
            source_reference=source_reference,
            source_location=_vector_location(
                row,
                column=field_name,
            ),
            origin=RecordOrigin.OBSERVATORY_NORMALIZED,
            accumulation_classification="cumulative",
            validation_check_ids=_check_ids(
                session.audit_report,
                ValidationCategory.INVARIANT_VECTOR,
                ValidationCategory.QUALIFICATION_EVIDENCE,
            ),
        )
        for field_name, counter in _VECTOR_EVENT_COUNTERS.items()
        if field_name in values
    )
    if not counters:
        return None
    return EventCounterSnapshot(
        counter_snapshot_id=session.identifiers.make(
            "event-counter-snapshot",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        counters=counters,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.INVARIANT_VECTOR,
            ValidationCategory.QUALIFICATION_EVIDENCE,
        ),
    )


def _vector_tick_assembly(
    session: _BuildSession,
    artifact: M15VectorArtifact,
    row: M15VectorRow,
    *,
    row_index: int,
    cell_count: int,
    request_lane_count: int,
) -> _TickAssembly:
    values = _row_values(artifact, row)
    tick = _parse_nonnegative_decimal(values["TICK"], "TICK")
    source_location = _vector_location(
        row,
        source_record_ordinal=row_index + 1,
    )
    source_reference = session.add_source_reference(
        tick=tick,
        source_locations=(source_location,),
        role=f"tick-{row_index}",
    )
    source_fields = tuple(
        _vector_trace_field(
            session,
            source_reference,
            role="tick",
            field_name=field_name,
            raw_value=raw_value,
            source_location=_vector_location(
                row,
                column=field_name,
                source_record_ordinal=row_index + 1,
            ),
        )
        for field_name, raw_value in values.items()
    )
    scheduler = _vector_scheduler_snapshot(
        session,
        source_reference,
        values,
        row,
    )
    requests = _vector_request_bundle(
        session,
        source_reference,
        values,
        row,
        request_lane_count,
    )
    states = _vector_state_snapshot(
        session,
        source_reference,
        values,
        cell_count,
    )
    transition_telemetry = _vector_transition_telemetry(
        session,
        source_reference,
        values,
        row,
    )
    trace_telemetry = _vector_trace_telemetry(
        session,
        source_reference,
        values,
        row,
    )
    counters = _vector_event_counters(
        session,
        source_reference,
        values,
        row,
    )
    record = TickRecord(
        tick_record_id=session.identifiers.make(
            "tick-record",
            source_reference.source_ordinal,
        ),
        trace_dataset_id=session.trace_dataset_id,
        source_reference=source_reference,
        source_location=source_location,
        source_ordinal=source_reference.source_ordinal,
        tick=tick,
        source_fields=source_fields,
        scheduler_snapshot_id=scheduler.scheduler_snapshot_id,
        request_bundle_id=requests.request_bundle_id,
        state_snapshot_id=states.state_snapshot_id,
        transition_telemetry_id=(
            transition_telemetry.telemetry_record_id
            if transition_telemetry is not None
            else None
        ),
        telemetry_snapshot_id=(
            trace_telemetry.telemetry_snapshot_id
            if trace_telemetry is not None
            else None
        ),
        event_counter_snapshot_id=(
            counters.counter_snapshot_id
            if counters is not None
            else None
        ),
        changes=None,
        validation_check_ids=_check_ids(session.audit_report),
    )
    return _TickAssembly(
        tick_record=record,
        state_snapshot=states,
        request_bundle=requests,
        scheduler_snapshot=scheduler,
        transition_telemetry=transition_telemetry,
        trace_telemetry=trace_telemetry,
        event_counters=counters,
    )


def _vector_cell_record(
    session: _BuildSession,
    artifact: M15VectorArtifact,
    row: M15VectorRow,
    *,
    row_index: int,
) -> CellTraceRecord:
    values = _row_values(artifact, row)
    tick = _parse_nonnegative_decimal(values["TICK"], "TICK")
    cell_id = _parse_nonnegative_decimal(
        values["CELL_ID"],
        "CELL_ID",
    )
    source_location = _vector_location(
        row,
        source_record_ordinal=row_index + 1,
    )
    source_reference = session.add_source_reference(
        tick=tick,
        source_locations=(source_location,),
        role=f"cell-{row_index}",
    )
    fields = tuple(
        _vector_trace_field(
            session,
            source_reference,
            role="cell",
            field_name=field_name,
            raw_value=values[field_name],
            source_location=_vector_location(
                row,
                column=field_name,
                source_record_ordinal=row_index + 1,
            ),
        )
        for field_name in _VECTOR_CELL_FIELDS
    )
    state_raw = values["STATE_CODE"]
    canonical_state = _normalized_state_value(
        session,
        source_reference,
        role=f"vector-cell[{row_index}]",
        cell_id=cell_id,
        source_value=state_raw,
        state_code=_parse_hex(state_raw, "STATE_CODE"),
        source_encoding="uppercase_hex_text",
    )
    return CellTraceRecord(
        cell_trace_record_id=session.identifiers.make(
            "cell-trace-record",
            source_reference.source_ordinal,
        ),
        trace_dataset_id=session.trace_dataset_id,
        source_reference=source_reference,
        source_location=source_location,
        source_ordinal=source_reference.source_ordinal,
        tick=tick,
        cell_id=cell_id,
        fields=fields,
        canonical_state=canonical_state,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TYPE,
            ValidationCategory.TERNARY_DOMAIN,
            ValidationCategory.ORDERING,
        ),
    )


def _vector_route_event(
    session: _BuildSession,
    artifact: M15VectorArtifact,
    row: M15VectorRow,
    *,
    row_index: int,
) -> RouteEventRecord:
    values = _row_values(artifact, row)
    tick = _parse_nonnegative_decimal(values["TICK"], "TICK")
    source_location = _vector_location(
        row,
        source_record_ordinal=row_index + 1,
    )
    source_reference = session.add_source_reference(
        tick=tick,
        source_locations=(source_location,),
        role=f"route-{row_index}",
    )
    target_raw = values["TARGET_STATE_CODE"]
    return RouteEventRecord(
        route_event_record_id=session.identifiers.make(
            "route-event-record",
            source_reference.source_ordinal,
        ),
        source_reference=source_reference,
        cell_id=_parse_nonnegative_decimal(
            values["CELL_ID"],
            "CELL_ID",
        ),
        source_target_state=target_raw,
        canonical_target_state=_decode_state_code(
            _parse_hex(target_raw, "TARGET_STATE_CODE"),
            "TARGET_STATE_CODE",
        ),
        ready_tick=_parse_nonnegative_decimal(
            values["READY_TICK"],
            "READY_TICK",
        ),
        route_status=_route_status(
            values["ROUTE_STATUS"],
            "ROUTE_STATUS",
        ),
        origin=RecordOrigin.OBSERVATORY_NORMALIZED,
        route_index=_parse_nonnegative_decimal(
            values["ROUTE_INDEX"],
            "ROUTE_INDEX",
        ),
        encoding_map_identifier=_STATE_ENCODING_BINDING,
        validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.TERNARY_DOMAIN,
            ValidationCategory.PENDING_ROUTE,
            ValidationCategory.ORDERING,
        ),
    )


def _vector_primary_order_valid(
    tick_records: tuple[TickRecord, ...],
    trace_steps: int,
) -> bool:
    return tuple(
        record.tick for record in tick_records
    ) == tuple(range(trace_steps))


def _vector_cell_order_valid(
    cell_records: tuple[CellTraceRecord, ...],
    *,
    trace_steps: int,
    cell_count: int,
) -> bool:
    observed = tuple(
        (record.tick, record.cell_id)
        for record in cell_records
    )
    expected = tuple(
        (tick, cell_id)
        for tick in range(trace_steps)
        for cell_id in range(cell_count)
    )
    return observed == expected


def _vector_route_order_valid(
    route_events: tuple[RouteEventRecord, ...],
) -> bool:
    indexes = tuple(
        event.route_index for event in route_events
    )
    observed = tuple(
        (
            event.source_reference.tick,
            event.cell_id,
            event.ready_tick,
            event.route_status.value,
        )
        for event in route_events
    )
    return (
        indexes == tuple(range(len(route_events)))
        and observed == tuple(sorted(observed))
    )


def _build_vector_dataset(
    session: _BuildSession,
    artifact: M15VectorArtifact,
) -> TraceDataset:
    configuration_fields = _vector_configuration_fields(
        session,
        artifact,
    )
    cell_count = _metadata_integer(artifact, "cells")
    request_lane_count = _metadata_integer(
        artifact,
        "request_lanes",
    )
    trace_steps = _metadata_integer(artifact, "trace_steps")

    tick_records: tuple[TickRecord, ...] | None = None
    state_snapshots: tuple[TernaryStateSnapshot, ...] | None = None
    request_bundles: tuple[RequestBundle, ...] | None = None
    scheduler_snapshots: tuple[SchedulerSnapshot, ...] | None = None
    transition_telemetry: (
        tuple[TransitionTelemetryRecord, ...] | None
    ) = None
    trace_telemetry: tuple[TraceTelemetrySnapshot, ...] | None = None
    event_counters: tuple[EventCounterSnapshot, ...] | None = None
    cell_records: tuple[CellTraceRecord, ...] | None = None
    route_events: tuple[RouteEventRecord, ...] | None = None

    if session.trace_family is TraceFamily.M15_PRIMARY_VECTOR:
        assemblies = tuple(
            _vector_tick_assembly(
                session,
                artifact,
                row,
                row_index=index,
                cell_count=cell_count,
                request_lane_count=request_lane_count,
            )
            for index, row in enumerate(artifact.rows)
        )
        tick_records = tuple(
            assembly.tick_record for assembly in assemblies
        )
        state_snapshots = tuple(
            assembly.state_snapshot for assembly in assemblies
        )
        request_bundles = tuple(
            assembly.request_bundle for assembly in assemblies
        )
        scheduler_snapshots = tuple(
            assembly.scheduler_snapshot for assembly in assemblies
        )
        transition_telemetry = tuple(
            assembly.transition_telemetry
            for assembly in assemblies
            if assembly.transition_telemetry is not None
        )
        trace_telemetry = tuple(
            assembly.trace_telemetry
            for assembly in assemblies
            if assembly.trace_telemetry is not None
        )
        event_counters = tuple(
            assembly.event_counters
            for assembly in assemblies
            if assembly.event_counters is not None
        )
        local_order_valid = _vector_primary_order_valid(
            tick_records,
            trace_steps,
        )
    elif session.trace_family is TraceFamily.M15_PER_CELL_VECTOR:
        cell_records = tuple(
            _vector_cell_record(
                session,
                artifact,
                row,
                row_index=index,
            )
            for index, row in enumerate(artifact.rows)
        )
        local_order_valid = _vector_cell_order_valid(
            cell_records,
            trace_steps=trace_steps,
            cell_count=cell_count,
        )
    else:
        route_events = tuple(
            _vector_route_event(
                session,
                artifact,
                row,
                row_index=index,
            )
            for index, row in enumerate(artifact.rows)
        )
        local_order_valid = _vector_route_order_valid(
            route_events,
        )

    ordering = _ordering_status(
        session.audit_report,
        local_order_valid=local_order_valid,
    )
    completeness = (
        TraceCompletenessStatus.REQUIRED_COLLECTIONS_PRESENT
    )
    domain_valid = all(
        snapshot.state_domain_valid
        for snapshot in state_snapshots or ()
    )
    has_normalized_states = bool(
        state_snapshots or cell_records or route_events
    )
    measurement_contour = cast(
        MeasurementContour,
        session.audit_report.measurement_contour,
    )
    return TraceDataset(
        trace_dataset_id=session.trace_dataset_id,
        normalized_artifact_id=session.normalized_artifact_id,
        trace_family=session.trace_family,
        measurement_contour=measurement_contour,
        source_references=tuple(session.source_references),
        configuration_fields=configuration_fields,
        ordering_validation=ordering,
        completeness_status=completeness,
        eligible_modes=_eligible_modes(
            session.trace_family,
            ordering_status=ordering,
            completeness_status=completeness,
            state_domain_valid=domain_valid,
        ),
        kind=artifact.declared_trace_kind,
        format_identifier=artifact.format_identifier,
        state_encoding_binding=(
            _STATE_ENCODING_BINDING
            if has_normalized_states
            else None
        ),
        tick_records=tick_records,
        cell_records=cell_records,
        state_snapshots=state_snapshots,
        request_bundles=request_bundles,
        scheduler_snapshots=scheduler_snapshots,
        route_events=route_events,
        transitions=None,
        transition_telemetry_records=transition_telemetry,
        telemetry_snapshots=trace_telemetry,
        event_counter_snapshots=event_counters,
        package_record_ids=None,
        digest_record_ids=None,
        ordering_validation_check_ids=_check_ids(
            session.audit_report,
            ValidationCategory.ORDERING,
        ),
        validation_check_ids=_check_ids(session.audit_report),
    )


def _trace_family(
    dispatched_artifact: DispatchedArtifact,
) -> TraceFamily:
    parsed = dispatched_artifact.parsed_artifact
    if isinstance(parsed, ParsedJsonArtifact):
        identity = (
            parsed.declared_schema_identifier,
            parsed.declared_kind,
        )
        if identity == (_STRUCTURED_OUTPUT_SCHEMA, "demo"):
            return TraceFamily.STRUCTURED_PROCESSOR_TICK
        if identity == (
            _CYCLE_EXACT_SCHEMA,
            "cycle_exact_reference_trace",
        ):
            return TraceFamily.CYCLE_EXACT_REFERENCE
        raise TraceBuilderError(
            "registered JSON artifact is not a supported trace family"
        )
    if not isinstance(parsed, M15VectorArtifact):
        raise TraceBuilderError(
            "trace construction requires parsed JSON or M15 vector data"
        )
    trace_kind = parsed.recognized_trace_kind
    if trace_kind in _PRIMARY_VECTOR_KINDS:
        return TraceFamily.M15_PRIMARY_VECTOR
    if trace_kind is M15VectorTraceKind.CELL_TRACE:
        return TraceFamily.M15_PER_CELL_VECTOR
    if trace_kind is M15VectorTraceKind.PENDING_ROUTES:
        return TraceFamily.M15_PENDING_ROUTE
    raise TraceBuilderError(
        "registered M15 vector has no supported trace family"
    )


def _validate_audit_binding(
    dispatched_artifact: DispatchedArtifact,
    audit_report: AuditReport,
) -> None:
    if not isinstance(dispatched_artifact, DispatchedArtifact):
        raise TraceBuilderError(
            "dispatched_artifact must be a DispatchedArtifact"
        )
    if not isinstance(audit_report, AuditReport):
        raise TraceBuilderError(
            "audit_report must be an AuditReport"
        )
    source = dispatched_artifact.source_artifact
    if not source.verify_integrity():
        raise TraceBuilderError(
            "source artifact integrity verification failed"
        )
    if (
        dispatched_artifact.registration.status
        is not RegistrationStatus.REGISTERED
    ):
        raise TraceBuilderError(
            "trace construction requires a registered artifact"
        )
    record = dispatched_artifact.compatibility_record
    if record is None:
        raise TraceBuilderError(
            "registered dispatch is missing compatibility metadata"
        )
    if audit_report.overall_status not in _VALID_REPORT_STATUSES:
        raise TraceBuilderError(
            "trace construction requires a valid audit report"
        )
    if (
        audit_report.source_artifact_id
        != source.source_artifact_id
        or audit_report.source_sha256 != source.content_sha256
        or audit_report.source_byte_length != source.byte_length
        or audit_report.source_filename != source.source_filename
        or audit_report.source_path != source.source_path
        or audit_report.loaded_at != source.loaded_at
    ):
        raise TraceBuilderError(
            "audit report does not describe the dispatched source"
        )
    if (
        audit_report.detected_format
        is not dispatched_artifact.classification
        or audit_report.registry_binding_id is None
        or audit_report.matched_registry_identifier
        != record.identifier
        or audit_report.matched_registry_kind
        != record.artifact_kind
        or audit_report.measurement_contour
        is not record.measurement_contour
    ):
        raise TraceBuilderError(
            "audit report registry binding does not match dispatch"
        )
    if (
        audit_report.declared_kind
        != dispatched_artifact.registration.declared_kind
    ):
        raise TraceBuilderError(
            "audit report kind does not match dispatch"
        )
    expected_schema = (
        record.identifier
        if dispatched_artifact.classification
        is ArtifactClassification.JSON
        else None
    )
    if audit_report.declared_schema_identifier != expected_schema:
        raise TraceBuilderError(
            "audit report schema identity does not match dispatch"
        )
    _validate_uuid(
        audit_report.registry_binding_id,
        "registry_binding_id",
    )


def _new_session(
    dispatched_artifact: DispatchedArtifact,
    audit_report: AuditReport,
    trace_family: TraceFamily,
) -> _BuildSession:
    source_namespace = _validate_uuid(
        dispatched_artifact.source_artifact.source_artifact_id,
        "source_artifact_id",
    )
    trace_dataset_id = str(
        uuid5(
            source_namespace,
            (
                "trace-dataset:"
                f"{audit_report.audit_report_id}:"
                f"{trace_family.value}"
            ),
        )
    )
    normalized_artifact_id = str(
        uuid5(
            source_namespace,
            (
                "normalized-trace-artifact:"
                f"{audit_report.audit_report_id}:"
                f"{trace_family.value}"
            ),
        )
    )
    return _BuildSession(
        dispatched_artifact=dispatched_artifact,
        audit_report=audit_report,
        trace_family=trace_family,
        trace_dataset_id=trace_dataset_id,
        normalized_artifact_id=normalized_artifact_id,
        identifiers=_IdentifierFactory(UUID(trace_dataset_id)),
    )


@dataclass(frozen=True, slots=True)
class TraceDatasetBuilder:
    """Build one immutable trace view from one successfully audited source."""

    def build(
        self,
        dispatched_artifact: DispatchedArtifact,
        audit_report: AuditReport,
    ) -> TraceDataset:
        """Construct a deterministic read-only dataset without execution."""

        _validate_audit_binding(dispatched_artifact, audit_report)
        trace_family = _trace_family(dispatched_artifact)
        session = _new_session(
            dispatched_artifact,
            audit_report,
            trace_family,
        )
        parsed = dispatched_artifact.parsed_artifact
        try:
            if isinstance(parsed, ParsedJsonArtifact):
                return _build_json_dataset(session, parsed)
            if isinstance(parsed, M15VectorArtifact):
                return _build_vector_dataset(session, parsed)
        except TraceBuilderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise TraceBuilderError(
                f"trace dataset construction failed: {exc}"
            ) from exc
        raise TraceBuilderError(
            "trace construction requires a parsed supported artifact"
        )


def build_trace_dataset(
    dispatched_artifact: DispatchedArtifact,
    audit_report: AuditReport,
) -> TraceDataset:
    """Build one deterministic trace dataset from an audit result."""

    return TraceDatasetBuilder().build(
        dispatched_artifact,
        audit_report,
    )
