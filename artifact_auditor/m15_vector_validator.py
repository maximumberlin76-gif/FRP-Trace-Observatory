"""Read-only validation for registered FRP M15 vector text artifacts.

This module validates only text artifacts that declare
``frp.m15.vector.v1``. The M15 trigonometric lookup-table text has no such
declaration and remains outside this registered validator.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
)
from parsers.m15_vector import (
    CELL_TRACE_COLUMNS,
    M15_VECTOR_FORMAT_VERSION,
    M15_VECTOR_PRODUCER_METADATA_ORDER,
    PRIMARY_VECTOR_COLUMNS,
    ROUTE_TRACE_COLUMNS,
    M15VectorArtifact,
    M15VectorRow,
    M15VectorTraceKind,
    expected_columns_for_trace_kind,
)

from .audit_report import CheckOutcome, SourceLocation, ValidationCategory
from .validation_core import ValidationCheckSpec


__all__ = [
    "M15VectorValidation",
    "M15VectorValidationError",
    "validate_m15_vector",
]


type DecodedValue = int | str | tuple[int, ...]
type DecodedRow = dict[str, DecodedValue]
type DecodedRows = tuple[tuple[M15VectorRow, DecodedRow], ...]


_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_UPSTREAM_RULE = "frp_prototype_v1_7_0.py"
_SCHEDULER_CODES = {"free": 0, "7/1": 1, "1/7": 2}
_TRACE_SCHEDULERS = {
    M15VectorTraceKind.KERNEL_TRANSITION_VECTORS: "free",
    M15VectorTraceKind.PENDING_ROUTES: "free",
    M15VectorTraceKind.SCHEDULER_FREE_VECTORS: "free",
    M15VectorTraceKind.SCHEDULER_7_1_VECTORS: "7/1",
    M15VectorTraceKind.SCHEDULER_1_7_VECTORS: "1/7",
}
_PRIMARY_KINDS = frozenset(
    {
        M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
        M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
        M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
        M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
        M15VectorTraceKind.FULL_CORRELATION_VECTORS,
    }
)
_FIXED_SIXTEEN_STEP_KINDS = frozenset(
    {
        M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
        M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
        M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
    }
)
_KERNEL_STEP_KINDS = frozenset(
    {
        M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
        M15VectorTraceKind.PENDING_ROUTES,
    }
)
_TERNARY_CODES = frozenset({0, 1, 3})
_POLARITY_CODES = frozenset({1, 3})
_COUNTER_COLUMNS = (
    "REQUESTED_DIRECT_EVENTS",
    "PREVENTED_DIRECT_EVENTS",
    "NEUTRAL_ROUTED_EVENTS",
    "NEUTRALIZED_CONFLICTS",
    "ACTUAL_DIRECT_EVENTS",
)
_PRIMARY_SIGNED_COLUMNS = (
    "SWITCH_LOAD_Q",
    "HEAT_GLOBAL_Q",
    "C_Q",
    "P_Q",
    "C_MINUS_P_Q",
)
_CELL_SIGNED_COLUMNS = (
    "FREQUENCY_TARGET_Q",
    "FREQUENCY_CURRENT_Q",
    "FREQUENCY_LAG_Q",
    "GENERATED_POWER_Q",
    "HEAT_Q",
    "THERMAL_OVERLOAD_Q",
    "GAMMA_NOISE_STATE_Q",
    "GAMMA_EFFECTIVE_WORD",
    "COUPLING_FIELD_Q",
)


class M15VectorValidationError(ValueError):
    """Raised when a validator input violates routing invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: object) -> bool:
    return _integer(value) or (
        isinstance(value, Decimal) and value.is_finite()
    )


def _signed_32(value: DecodedValue) -> bool:
    return _integer(value) and -(1 << 31) <= value < (1 << 31)


def _decimal(text: str) -> int | None:
    if not text:
        return None
    if text == "0":
        return 0
    digits = text[1:] if text.startswith("-") else text
    if not digits or digits.startswith("0"):
        return None
    if not digits.isascii() or not digits.isdigit():
        return None
    return int(text)


def _fixed_decimal(text: str, width: int) -> int | None:
    if (
        len(text) != width
        or not text.isascii()
        or not text.isdigit()
    ):
        return None
    return int(text)


def _hexadecimal(text: str, width: int) -> int | None:
    if len(text) != width or any(
        character not in "0123456789ABCDEF" for character in text
    ):
        return None
    return int(text, 16)


def _csv(
    text: str,
    count: int,
    decoder: Callable[[str], int | None],
) -> tuple[int, ...] | None:
    parts = text.split(",")
    if len(parts) != count:
        return None
    decoded = tuple(decoder(part) for part in parts)
    if any(value is None for value in decoded):
        return None
    return decoded  # type: ignore[return-value]


def _route_status(text: str) -> str | None:
    return text if text in {"pending", "applied"} else None


def _metadata(artifact: M15VectorArtifact, key: str) -> object:
    try:
        return artifact.metadata_value(key)
    except KeyError:
        return None


def _expected_lanes(cells: int, fraction: int | Decimal) -> int | None:
    try:
        return max(1, int(round(cells * float(fraction))))
    except (OverflowError, ValueError):
        return None


def _location(
    artifact: M15VectorArtifact,
    *,
    row: M15VectorRow | None = None,
    column: str | None = None,
    metadata_key: str | None = None,
) -> SourceLocation:
    if row is not None:
        return SourceLocation(
            line_number=row.line_number,
            vector_column=column,
        )
    if metadata_key is not None:
        for entry in artifact.metadata_entries:
            if entry.key == metadata_key:
                return SourceLocation(line_number=entry.line_number)
    return SourceLocation(
        line_number=artifact.column_header_line_number,
        vector_column=column,
    )


def _spec(
    code: str,
    category: ValidationCategory,
    valid: bool,
    location: SourceLocation,
) -> ValidationCheckSpec:
    relation = "matches" if valid else "does not match"
    return ValidationCheckSpec(
        check_code=code,
        category=category,
        outcome=CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        message=(
            f"The {code.replace('_', ' ')} {relation} the registered "
            "upstream vector contract."
        ),
        source_locations=(location,),
        upstream_rule_reference=_UPSTREAM_RULE,
    )


def _specs(
    artifact: M15VectorArtifact,
    results: tuple[
        tuple[str, ValidationCategory, bool, str | None], ...
    ],
    *,
    row: M15VectorRow | None = None,
) -> tuple[ValidationCheckSpec, ...]:
    return tuple(
        _spec(
            code,
            category,
            valid,
            _location(artifact, row=row, column=column),
        )
        for code, category, valid, column in results
    )


def _decode_rows(
    artifact: M15VectorArtifact,
    expected_columns: tuple[str, ...],
    decoders: dict[
        str,
        Callable[[str], DecodedValue | None],
    ],
) -> DecodedRows | None:
    if artifact.columns != expected_columns or frozenset(decoders) != frozenset(
        expected_columns
    ):
        return None
    decoded_rows: list[tuple[M15VectorRow, DecodedRow]] = []
    for row in artifact.rows:
        decoded: DecodedRow = {}
        for index, column in enumerate(expected_columns):
            value = decoders[column](row.fields[index])
            if value is None:
                return None
            decoded[column] = value
        decoded_rows.append((row, decoded))
    return tuple(decoded_rows)


def _parsed(
    dispatched: DispatchedArtifact,
) -> tuple[M15VectorArtifact, M15VectorTraceKind | None]:
    if not isinstance(dispatched, DispatchedArtifact):
        raise M15VectorValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    parsed = dispatched.parsed_artifact
    record = dispatched.compatibility_record
    if (
        dispatched.classification is not ArtifactClassification.M15_VECTOR
        or dispatched.registration.status
        is not RegistrationStatus.REGISTERED
        or not isinstance(parsed, M15VectorArtifact)
        or record is None
        or record.identifier != M15_VECTOR_FORMAT_VERSION
        or record.artifact_kind is not None
    ):
        raise M15VectorValidationError(
            "artifact is not a registered M15 vector text artifact"
        )
    return parsed, parsed.recognized_trace_kind


def _common_specs(
    artifact: M15VectorArtifact,
    trace_kind: M15VectorTraceKind | None,
) -> tuple[ValidationCheckSpec, ...]:
    metadata_keys = tuple(
        entry.key for entry in artifact.metadata_entries
    )
    metadata_order = metadata_keys == M15_VECTOR_PRODUCER_METADATA_ORDER
    identity = (
        _metadata(artifact, "format_version")
        == M15_VECTOR_FORMAT_VERSION
        and _metadata(artifact, "frp_version") == _VERSION
        and _metadata(artifact, "milestone") == _MILESTONE
        and _metadata(artifact, "scalar_format") == "S32Q16"
        and _metadata(artifact, "unit_format") == "S32Q30"
        and _metadata(artifact, "phase_format") == "PHASE_U32"
    )
    trace_kind_allowed = bool(
        trace_kind is not None
        and _metadata(artifact, "trace_kind") == trace_kind.value
    )

    cells = _metadata(artifact, "cells")
    depth = _metadata(artifact, "hierarchy_depth")
    lanes = _metadata(artifact, "request_lanes")
    fraction = _metadata(artifact, "transition_fraction")
    alpha = _metadata(artifact, "fractal_alpha")
    beta = _metadata(artifact, "thermal_beta")
    steps = _metadata(artifact, "trace_steps")
    topology = bool(
        _integer(cells)
        and cells >= 2
        and cells & (cells - 1) == 0
        and _integer(depth)
        and depth == cells.bit_length() - 1
        and _integer(lanes)
        and 0 < lanes <= cells
        and _number(fraction)
        and Decimal("0.01") <= Decimal(fraction) <= Decimal(1)
        and lanes == _expected_lanes(cells, fraction)
        and _number(alpha)
        and Decimal(alpha) > 0
        and _number(beta)
        and Decimal(beta) > 0
        and _integer(steps)
        and steps >= 0
        and _integer(_metadata(artifact, "seed"))
    )
    if topology and trace_kind in _FIXED_SIXTEEN_STEP_KINDS:
        topology = steps == 16
    if topology and trace_kind in _KERNEL_STEP_KINDS:
        topology = steps >= 16

    scheduler = _metadata(artifact, "scheduler_mode")
    expected_scheduler = _TRACE_SCHEDULERS.get(trace_kind)
    scheduler_relation = scheduler in _SCHEDULER_CODES and (
        expected_scheduler is None or scheduler == expected_scheduler
    )
    expected_columns = (
        expected_columns_for_trace_kind(trace_kind)
        if trace_kind is not None
        else None
    )
    columns = bool(
        expected_columns is not None
        and artifact.columns == expected_columns
        and _metadata(artifact, "column_definition") == expected_columns
    )

    if not _integer(cells) or not _integer(steps):
        row_count = False
    elif trace_kind in _PRIMARY_KINDS:
        row_count = len(artifact.rows) == steps
    elif trace_kind is M15VectorTraceKind.CELL_TRACE:
        row_count = len(artifact.rows) == cells * steps
    else:
        row_count = trace_kind is M15VectorTraceKind.PENDING_ROUTES

    return (
        _spec(
            "m15_vector_metadata_order",
            ValidationCategory.STRUCTURE,
            metadata_order,
            _location(artifact, metadata_key="format_version"),
        ),
        _spec(
            "m15_vector_metadata_identity",
            ValidationCategory.IDENTITY,
            identity,
            _location(artifact, metadata_key="format_version"),
        ),
        _spec(
            "m15_vector_trace_kind",
            ValidationCategory.ALLOWED_VALUE,
            trace_kind_allowed,
            _location(artifact, metadata_key="trace_kind"),
        ),
        _spec(
            "m15_vector_topology_metadata",
            ValidationCategory.TYPE,
            topology,
            _location(artifact, metadata_key="cells"),
        ),
        _spec(
            "m15_vector_scheduler_metadata",
            ValidationCategory.SCHEDULER_RELATION,
            scheduler_relation,
            _location(artifact, metadata_key="scheduler_mode"),
        ),
        _spec(
            "m15_vector_column_contract",
            ValidationCategory.STRUCTURE,
            columns,
            _location(artifact),
        ),
        _spec(
            "m15_vector_row_count",
            ValidationCategory.STRUCTURE,
            row_count,
            _location(artifact),
        ),
    )


def _primary_decoders(
    cells: int,
    lanes: int,
) -> dict[str, Callable[[str], DecodedValue | None]]:
    decoders: dict[
        str,
        Callable[[str], DecodedValue | None],
    ] = {column: _decimal for column in PRIMARY_VECTOR_COLUMNS}
    lane_width = max(1, (lanes + 3) // 4)
    cell_width = max(1, ((cells - 1).bit_length() + 3) // 4)
    state_width = max(1, (2 * cells + 3) // 4)
    decoders.update(
        {
            "TICK": lambda value: _fixed_decimal(value, 8),
            "SCHED_MODE": lambda value: _hexadecimal(value, 1),
            "SCHED_STATE": lambda value: _hexadecimal(value, 1),
            "REQ_VALID_MASK": lambda value: _hexadecimal(
                value,
                lane_width,
            ),
            "REQ_CELL_IDS": lambda value: _csv(
                value,
                lanes,
                lambda item: _hexadecimal(item, cell_width),
            ),
            "REQ_TARGET_STATES": lambda value: _csv(
                value,
                lanes,
                lambda item: _hexadecimal(item, 1),
            ),
            "GAMMA_NOISE_TARGETS_Q": lambda value: _csv(
                value,
                cells,
                _decimal,
            ),
            "STATES_PACKED": lambda value: _hexadecimal(
                value,
                state_width,
            ),
        }
    )
    return decoders


def _scheduler_state(mode: str, tick: int) -> int:
    if mode == "7/1":
        return 2 if (tick + 1) % 8 == 0 else 1
    if mode == "1/7":
        return 3 if tick % 8 == 0 else 4
    return 0


def _saturated_difference(left: int, right: int) -> int:
    return max(-(1 << 31), min((1 << 31) - 1, left - right))


def _primary_specs(
    artifact: M15VectorArtifact,
    trace_kind: M15VectorTraceKind,
) -> tuple[ValidationCheckSpec, ...]:
    cells = _metadata(artifact, "cells")
    lanes = _metadata(artifact, "request_lanes")
    steps = _metadata(artifact, "trace_steps")
    scheduler = _metadata(artifact, "scheduler_mode")
    if not _integer(cells) or not _integer(lanes):
        rows = None
    else:
        rows = _decode_rows(
            artifact,
            PRIMARY_VECTOR_COLUMNS,
            _primary_decoders(cells, lanes),
        )
    values = rows or ()
    encoded = rows is not None
    field_values = bool(
        encoded
        and _integer(cells)
        and _integer(lanes)
        and all(
            row["RESET_N"] in {0, 1}
            and row["AUTO_TARGETS_ENABLE"] in {0, 1}
            and row["GAMMA_UPDATE_VALID"] in {0, 1}
            and 0 <= row["SCHED_MODE"] <= 2
            and 0 <= row["SCHED_STATE"] <= 4
            and 0 <= row["STATES_PACKED"] < (1 << (2 * cells))
            and all(
                _signed_32(item)
                for item in row["GAMMA_NOISE_TARGETS_Q"]
            )
            and all(
                _signed_32(row[column])
                for column in _PRIMARY_SIGNED_COLUMNS
            )
            and 0 <= row["COHERENCE_GLOBAL_Q"] <= (1 << 30)
            and all(row[column] >= 0 for column in _COUNTER_COLUMNS)
            and row["PENDING_ROUTE_COUNT"] >= 0
            for _, row in values
        )
    )
    ticks = tuple(row["TICK"] for _, row in values)
    ordering = bool(
        encoded and _integer(steps) and ticks == tuple(range(steps))
    )
    auto_targets = (
        1
        if trace_kind is M15VectorTraceKind.FULL_CORRELATION_VECTORS
        else 0
    )
    scheduler_relation = bool(
        encoded
        and isinstance(scheduler, str)
        and scheduler in _SCHEDULER_CODES
        and all(
            row["RESET_N"] == 1
            and row["SCHED_MODE"] == _SCHEDULER_CODES[scheduler]
            and row["SCHED_STATE"]
            == _scheduler_state(scheduler, row["TICK"])
            and row["AUTO_TARGETS_ENABLE"] == auto_targets
            for _, row in values
        )
    )
    ternary = bool(
        encoded
        and _integer(cells)
        and all(
            all(
                (row["STATES_PACKED"] >> (2 * cell)) & 3
                in _TERNARY_CODES
                for cell in range(cells)
            )
            and all(
                code in _TERNARY_CODES
                for code in row["REQ_TARGET_STATES"]
            )
            and all(
                0 <= cell_id < cells
                for cell_id in row["REQ_CELL_IDS"]
            )
            for _, row in values
        )
    )
    loads = (
        {
            (changes * 65536 + cells // 2) // cells
            for changes in range(lanes + 1)
        }
        if _integer(cells) and _integer(lanes)
        else set()
    )
    capacity = bool(
        encoded
        and _integer(cells)
        and _integer(lanes)
        and all(
            0 <= row["REQ_VALID_MASK"] < (1 << lanes)
            and 0 <= row["PENDING_ROUTE_COUNT"] <= cells
            and row["SWITCH_LOAD_Q"] in loads
            for _, row in values
        )
    )
    invariants = bool(
        encoded
        and all(
            row["ACTUAL_DIRECT_EVENTS"] == 0
            and row["REQUESTED_DIRECT_EVENTS"]
            <= row["PREVENTED_DIRECT_EVENTS"]
            and row["NEUTRAL_ROUTED_EVENTS"]
            <= row["PREVENTED_DIRECT_EVENTS"]
            and row["NEUTRALIZED_CONFLICTS"]
            == row["PREVENTED_DIRECT_EVENTS"]
            and row["C_MINUS_P_Q"]
            == _saturated_difference(row["C_Q"], row["P_Q"])
            for _, row in values
        )
        and all(
            current[column] >= previous[column]
            for (_, previous), (_, current) in zip(values, values[1:])
            for column in _COUNTER_COLUMNS
        )
    )
    source_row = artifact.rows[0] if artifact.rows else None
    return _specs(
        artifact,
        (
            (
                "m15_vector_primary_field_encoding",
                ValidationCategory.TYPE,
                field_values,
                None,
            ),
            (
                "m15_vector_tick_order",
                ValidationCategory.ORDERING,
                ordering,
                "TICK",
            ),
            (
                "m15_vector_scheduler_relation",
                ValidationCategory.SCHEDULER_RELATION,
                scheduler_relation,
                "SCHED_STATE",
            ),
            (
                "m15_vector_ternary_domain",
                ValidationCategory.TERNARY_DOMAIN,
                ternary,
                "STATES_PACKED",
            ),
            (
                "m15_vector_transition_capacity",
                ValidationCategory.TRANSITION_CAPACITY,
                capacity,
                "SWITCH_LOAD_Q",
            ),
            (
                "m15_vector_direct_transition_invariants",
                ValidationCategory.INVARIANT_VECTOR,
                invariants,
                "ACTUAL_DIRECT_EVENTS",
            ),
        ),
        row=source_row,
    )


def _cell_specs(
    artifact: M15VectorArtifact,
) -> tuple[ValidationCheckSpec, ...]:
    decoders: dict[str, Callable[[str], DecodedValue | None]] = {
        column: _decimal for column in CELL_TRACE_COLUMNS
    }
    decoders.update(
        {
            "TICK": lambda value: _fixed_decimal(value, 8),
            "STATE_CODE": lambda value: _hexadecimal(value, 1),
            "PHASE_WORD": lambda value: _hexadecimal(value, 8),
        }
    )
    rows = _decode_rows(
        artifact,
        CELL_TRACE_COLUMNS,
        decoders,
    )
    values = rows or ()
    cells = _metadata(artifact, "cells")
    steps = _metadata(artifact, "trace_steps")
    encoding = bool(
        rows is not None
        and all(
            all(
                _signed_32(row[column])
                for column in _CELL_SIGNED_COLUMNS
            )
            and 0 <= row["THERMAL_NODE_FACTOR_Q"] <= (1 << 30)
            for _, row in values
        )
    )
    ordering = bool(
        rows is not None
        and _integer(cells)
        and _integer(steps)
        and tuple(
            (row["TICK"], row["CELL_ID"])
            for _, row in values
        )
        == tuple(
            (tick, cell)
            for tick in range(steps)
            for cell in range(cells)
        )
    )
    ternary = bool(
        rows is not None
        and all(
            row["STATE_CODE"] in _TERNARY_CODES
            for _, row in values
        )
    )
    source_row = artifact.rows[0] if artifact.rows else None
    return _specs(
        artifact,
        (
            (
                "m15_vector_cell_field_encoding",
                ValidationCategory.TYPE,
                encoding,
                None,
            ),
            (
                "m15_vector_cell_tick_order",
                ValidationCategory.ORDERING,
                ordering,
                "TICK",
            ),
            (
                "m15_vector_cell_ternary_domain",
                ValidationCategory.TERNARY_DOMAIN,
                ternary,
                "STATE_CODE",
            ),
        ),
        row=source_row,
    )


def _route_relation(rows: DecodedRows, steps: int) -> bool:
    pending: set[tuple[DecodedValue, ...]] = set()
    applied: set[tuple[DecodedValue, ...]] = set()
    for _, row in rows:
        tick = row["TICK"]
        ready_tick = row["READY_TICK"]
        status = row["ROUTE_STATUS"]
        if not 0 <= tick < steps or ready_tick < 1:
            return False
        if status == "pending" and tick + 1 != ready_tick:
            return False
        if status == "applied" and tick < ready_tick:
            return False
        key = (
            row["CELL_ID"],
            row["TARGET_STATE_CODE"],
            ready_tick,
        )
        if status == "pending":
            if key in pending:
                return False
            pending.add(key)
        elif key not in pending or key in applied:
            return False
        else:
            applied.add(key)
    return True


def _route_specs(
    artifact: M15VectorArtifact,
) -> tuple[ValidationCheckSpec, ...]:
    decoders: dict[str, Callable[[str], DecodedValue | None]] = {
        column: _decimal for column in ROUTE_TRACE_COLUMNS
    }
    decoders.update(
        {
            "TICK": lambda value: _fixed_decimal(value, 8),
            "TARGET_STATE_CODE": lambda value: _hexadecimal(value, 1),
            "ROUTE_STATUS": _route_status,
        }
    )
    rows = _decode_rows(
        artifact,
        ROUTE_TRACE_COLUMNS,
        decoders,
    )
    values = rows or ()
    cells = _metadata(artifact, "cells")
    steps = _metadata(artifact, "trace_steps")
    encoding = rows is not None
    ordering = bool(
        rows is not None
        and tuple(row["ROUTE_INDEX"] for _, row in values)
        == tuple(range(len(values)))
        and tuple(
            (
                row["TICK"],
                row["CELL_ID"],
                row["READY_TICK"],
                row["ROUTE_STATUS"],
            )
            for _, row in values
        )
        == tuple(
            sorted(
                (
                    row["TICK"],
                    row["CELL_ID"],
                    row["READY_TICK"],
                    row["ROUTE_STATUS"],
                )
                for _, row in values
            )
        )
    )
    ternary = bool(
        rows is not None
        and _integer(cells)
        and all(
            row["TARGET_STATE_CODE"] in _POLARITY_CODES
            and 0 <= row["CELL_ID"] < cells
            for _, row in values
        )
    )
    relation = bool(
        rows is not None
        and _integer(steps)
        and _route_relation(rows, steps)
    )
    source_row = artifact.rows[0] if artifact.rows else None
    return _specs(
        artifact,
        (
            (
                "m15_vector_route_field_encoding",
                ValidationCategory.TYPE,
                encoding,
                None,
            ),
            (
                "m15_vector_route_order",
                ValidationCategory.ORDERING,
                ordering,
                "ROUTE_INDEX",
            ),
            (
                "m15_vector_route_ternary_domain",
                ValidationCategory.TERNARY_DOMAIN,
                ternary,
                "TARGET_STATE_CODE",
            ),
            (
                "m15_vector_pending_route_relation",
                ValidationCategory.PENDING_ROUTE,
                relation,
                "ROUTE_STATUS",
            ),
        ),
        row=source_row,
    )


@dataclass(frozen=True, slots=True)
class M15VectorValidation:
    """Immutable validation result for one registered M15 vector."""

    dispatched_artifact: DispatchedArtifact
    trace_kind: M15VectorTraceKind | None
    check_specs: tuple[ValidationCheckSpec, ...]

    def __post_init__(self) -> None:
        parsed, parsed_kind = _parsed(self.dispatched_artifact)
        if self.trace_kind is not parsed_kind:
            raise M15VectorValidationError(
                "trace_kind must match the registered vector"
            )
        if (
            self.trace_kind is not None
            and parsed.declared_trace_kind != self.trace_kind.value
        ):
            raise M15VectorValidationError(
                "declared trace kind does not match the result"
            )
        if not self.check_specs or any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise M15VectorValidationError(
                "check_specs must contain validation specifications"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )


def validate_m15_vector(
    dispatched: DispatchedArtifact,
) -> M15VectorValidation:
    """Validate one registered M15 vector without changing source bytes."""

    artifact, trace_kind = _parsed(dispatched)
    specs = _common_specs(artifact, trace_kind)
    if trace_kind in _PRIMARY_KINDS:
        specs += _primary_specs(artifact, trace_kind)
    elif trace_kind is M15VectorTraceKind.CELL_TRACE:
        specs += _cell_specs(artifact)
    elif trace_kind is M15VectorTraceKind.PENDING_ROUTES:
        specs += _route_specs(artifact)
    return M15VectorValidation(dispatched, trace_kind, specs)
