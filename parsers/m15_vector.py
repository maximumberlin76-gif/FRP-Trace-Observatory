"""Read-only parser for the published FRP M15 vector text format."""

from __future__ import annotations

import json
from codecs import BOM_UTF8
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final

from .source_artifact import (
    SourceArtifact,
    SourceContainerFormat,
)


__all__ = [
    "CELL_TRACE_COLUMNS",
    "M15_VECTOR_FORMAT_VERSION",
    "M15_VECTOR_PRODUCER_METADATA_ORDER",
    "M15VectorArtifact",
    "M15VectorEncodingError",
    "M15VectorError",
    "M15VectorMetadataEntry",
    "M15VectorMetadataError",
    "M15VectorRow",
    "M15VectorRowError",
    "M15VectorStructureError",
    "M15VectorTextEncoding",
    "M15VectorTraceKind",
    "MetadataScalar",
    "MetadataValue",
    "PRIMARY_VECTOR_COLUMNS",
    "ROUTE_TRACE_COLUMNS",
    "expected_columns_for_trace_kind",
    "parse_m15_vector",
]


type MetadataScalar = None | bool | int | Decimal | str
type MetadataValue = MetadataScalar | tuple[MetadataValue, ...]


M15_VECTOR_FORMAT_VERSION: Final = "frp.m15.vector.v1"
M15_VECTOR_DELIMITER: Final = " | "

M15_VECTOR_PRODUCER_METADATA_ORDER: Final = (
    "format_version",
    "frp_version",
    "milestone",
    "trace_kind",
    "cells",
    "hierarchy_depth",
    "request_lanes",
    "transition_fraction",
    "scheduler_mode",
    "fractal_alpha",
    "thermal_beta",
    "scalar_format",
    "unit_format",
    "phase_format",
    "seed",
    "trace_steps",
    "column_definition",
)

PRIMARY_VECTOR_COLUMNS: Final = (
    "TICK",
    "RESET_N",
    "SCHED_MODE",
    "SCHED_STATE",
    "AUTO_TARGETS_ENABLE",
    "REQ_VALID_MASK",
    "REQ_CELL_IDS",
    "REQ_TARGET_STATES",
    "GAMMA_UPDATE_VALID",
    "GAMMA_NOISE_TARGETS_Q",
    "STATES_PACKED",
    "PENDING_ROUTE_COUNT",
    "SWITCH_LOAD_Q",
    "HEAT_GLOBAL_Q",
    "COHERENCE_GLOBAL_Q",
    "C_Q",
    "P_Q",
    "C_MINUS_P_Q",
    "REQUESTED_DIRECT_EVENTS",
    "PREVENTED_DIRECT_EVENTS",
    "NEUTRAL_ROUTED_EVENTS",
    "NEUTRALIZED_CONFLICTS",
    "ACTUAL_DIRECT_EVENTS",
)

CELL_TRACE_COLUMNS: Final = (
    "TICK",
    "CELL_ID",
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

ROUTE_TRACE_COLUMNS: Final = (
    "TICK",
    "ROUTE_INDEX",
    "CELL_ID",
    "TARGET_STATE_CODE",
    "READY_TICK",
    "ROUTE_STATUS",
)


class M15VectorTraceKind(StrEnum):
    """Trace kinds emitted by the audited M15 vector producer."""

    KERNEL_TRANSITION_VECTORS = "kernel_transition_vectors"
    PENDING_ROUTES = "pending_routes"
    SCHEDULER_FREE_VECTORS = "scheduler_free_vectors"
    SCHEDULER_7_1_VECTORS = "scheduler_7_1_vectors"
    SCHEDULER_1_7_VECTORS = "scheduler_1_7_vectors"
    FULL_CORRELATION_VECTORS = "full_correlation_vectors"
    CELL_TRACE = "cell_trace"


_PRIMARY_TRACE_KINDS: Final = frozenset(
    {
        M15VectorTraceKind.KERNEL_TRANSITION_VECTORS,
        M15VectorTraceKind.SCHEDULER_FREE_VECTORS,
        M15VectorTraceKind.SCHEDULER_7_1_VECTORS,
        M15VectorTraceKind.SCHEDULER_1_7_VECTORS,
        M15VectorTraceKind.FULL_CORRELATION_VECTORS,
    }
)

class M15VectorTextEncoding(StrEnum):
    """Accepted UTF-8 decodings for captured M15 vector bytes."""

    UTF8 = "utf-8"
    UTF8_WITH_BOM = "utf-8-sig"


class M15VectorError(ValueError):
    """Base error raised for an invalid M15 vector artifact."""


class M15VectorEncodingError(M15VectorError):
    """Raised when vector source bytes are not valid UTF-8 text."""

    def __init__(
        self,
        message: str,
        *,
        byte_start: int,
        byte_end: int,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.byte_start = byte_start
        self.byte_end = byte_end
        self.reason = reason


class M15VectorStructureError(M15VectorError):
    """Raised when vector headers or line ordering are invalid."""

    def __init__(
        self,
        message: str,
        *,
        line_number: int | None = None,
    ) -> None:
        super().__init__(message)
        self.line_number = line_number


class M15VectorMetadataError(M15VectorStructureError):
    """Raised when one metadata declaration is invalid."""

    def __init__(
        self,
        message: str,
        *,
        key: str | None,
        line_number: int | None,
    ) -> None:
        super().__init__(message, line_number=line_number)
        self.key = key


class M15VectorRowError(M15VectorStructureError):
    """Raised when one data row does not match the declared columns."""

    def __init__(
        self,
        message: str,
        *,
        line_number: int,
        expected_field_count: int,
        actual_field_count: int,
    ) -> None:
        super().__init__(message, line_number=line_number)
        self.expected_field_count = expected_field_count
        self.actual_field_count = actual_field_count


class _NonFiniteMetadataNumber(ValueError):
    def __init__(self, token: str) -> None:
        super().__init__(token)
        self.token = token


def _reject_non_finite_metadata_number(token: str) -> None:
    raise _NonFiniteMetadataNumber(token)


def _freeze_metadata_value(value: Any) -> MetadataValue:
    if value is None or isinstance(value, (bool, int, Decimal, str)):
        return value
    if isinstance(value, list):
        return tuple(_freeze_metadata_value(item) for item in value)
    raise TypeError(
        f"unsupported metadata JSON value type: {type(value).__name__}"
    )


def _is_metadata_value(value: object) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, tuple):
        return all(_is_metadata_value(item) for item in value)
    return False


def _validate_line_number(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M15VectorError(f"{field_name} must be an integer")
    if value <= 0:
        raise M15VectorError(f"{field_name} must be positive")


def _detect_text_encoding(
    source: SourceArtifact,
) -> M15VectorTextEncoding:
    if source.raw_bytes.startswith(BOM_UTF8):
        return M15VectorTextEncoding.UTF8_WITH_BOM
    return M15VectorTextEncoding.UTF8


def expected_columns_for_trace_kind(
    trace_kind: str | M15VectorTraceKind,
) -> tuple[str, ...] | None:
    """Return audited producer columns for a recognized trace kind."""

    if not isinstance(trace_kind, (str, M15VectorTraceKind)):
        raise M15VectorError(
            "trace_kind must be a string or M15VectorTraceKind"
        )
    try:
        recognized = M15VectorTraceKind(trace_kind)
    except ValueError:
        return None

    if recognized in _PRIMARY_TRACE_KINDS:
        return PRIMARY_VECTOR_COLUMNS
    if recognized is M15VectorTraceKind.CELL_TRACE:
        return CELL_TRACE_COLUMNS
    if recognized is M15VectorTraceKind.PENDING_ROUTES:
        return ROUTE_TRACE_COLUMNS
    return None

@dataclass(frozen=True, slots=True)
class M15VectorMetadataEntry:
    """One ordered metadata line and its immutable decoded value."""

    key: str
    raw_json: str
    value: MetadataValue
    line_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise M15VectorMetadataError(
                "metadata key must be a nonempty string",
                key=None,
                line_number=self.line_number,
            )
        if (
            self.key != self.key.strip()
            or any(character.isspace() for character in self.key)
            or "=" in self.key
        ):
            raise M15VectorMetadataError(
                "metadata key contains unsupported characters",
                key=self.key,
                line_number=self.line_number,
            )
        if not isinstance(self.raw_json, str) or not self.raw_json:
            raise M15VectorMetadataError(
                "metadata JSON text must be nonempty",
                key=self.key,
                line_number=self.line_number,
            )
        if not _is_metadata_value(self.value):
            raise M15VectorMetadataError(
                "metadata value is mutable or unsupported",
                key=self.key,
                line_number=self.line_number,
            )
        _validate_line_number(self.line_number, "metadata line_number")


@dataclass(frozen=True, slots=True)
class M15VectorRow:
    """One immutable vector data row with unmodified field text."""

    line_number: int
    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_line_number(self.line_number, "row line_number")
        if not isinstance(self.fields, tuple):
            raise M15VectorError("row fields must be a tuple")
        if any(not isinstance(field, str) for field in self.fields):
            raise M15VectorError("row fields must contain strings")

  @dataclass(frozen=True, slots=True)
class M15VectorArtifact:
    """Immutable parsed view linked to one unchanged vector source."""

    source_artifact: SourceArtifact
    metadata_entries: tuple[M15VectorMetadataEntry, ...]
    column_header_line_number: int
    columns: tuple[str, ...]
    rows: tuple[M15VectorRow, ...]
    text_encoding: M15VectorTextEncoding
    format_identifier: str
    declared_trace_kind: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_artifact, SourceArtifact):
            raise M15VectorError(
                "source_artifact must be a SourceArtifact"
            )
        if not self.source_artifact.verify_integrity():
            raise M15VectorError(
                "source artifact integrity verification failed"
            )
        if (
            self.source_artifact.detected_container_format
            is not SourceContainerFormat.UTF8_TEXT
        ):
            raise M15VectorError(
                "source artifact is not a UTF-8 text container"
            )
        if not isinstance(self.metadata_entries, tuple):
            raise M15VectorError("metadata_entries must be a tuple")
        if not self.metadata_entries:
            raise M15VectorMetadataError(
                "vector metadata must not be empty",
                key=None,
                line_number=None,
            )
        if any(
            not isinstance(entry, M15VectorMetadataEntry)
            for entry in self.metadata_entries
        ):
            raise M15VectorError(
                "metadata_entries contain an invalid entry"
            )

        metadata_keys = tuple(
            entry.key for entry in self.metadata_entries
        )
        if len(set(metadata_keys)) != len(metadata_keys):
            raise M15VectorMetadataError(
                "metadata keys must be unique",
                key=None,
                line_number=None,
            )
        metadata_line_numbers = tuple(
            entry.line_number for entry in self.metadata_entries
        )
        if metadata_line_numbers != tuple(sorted(metadata_line_numbers)):
            raise M15VectorStructureError(
                "metadata lines must preserve source ordering"
            )
        if len(set(metadata_line_numbers)) != len(metadata_line_numbers):
            raise M15VectorStructureError(
                "metadata line numbers must be unique"
            )

        _validate_line_number(
            self.column_header_line_number,
            "column_header_line_number",
        )
        if any(
            line_number >= self.column_header_line_number
            for line_number in metadata_line_numbers
        ):
            raise M15VectorStructureError(
                "metadata lines must precede the column header",
                line_number=self.column_header_line_number,
            )
        if not isinstance(self.columns, tuple) or not self.columns:
            raise M15VectorStructureError(
                "columns must be a nonempty tuple",
                line_number=self.column_header_line_number,
            )
        if any(
            not isinstance(column, str) or not column
            for column in self.columns
        ):
            raise M15VectorStructureError(
                "column names must be nonempty strings",
                line_number=self.column_header_line_number,
            )
        if len(set(self.columns)) != len(self.columns):
            raise M15VectorStructureError(
                "column names must be unique",
                line_number=self.column_header_line_number,
            )

        if not isinstance(self.rows, tuple):
            raise M15VectorError("rows must be a tuple")
        if any(not isinstance(row, M15VectorRow) for row in self.rows):
            raise M15VectorError("rows contain an invalid row")
        row_line_numbers = tuple(row.line_number for row in self.rows)
        if row_line_numbers != tuple(sorted(row_line_numbers)):
            raise M15VectorStructureError(
                "data rows must preserve source ordering"
            )
        if len(set(row_line_numbers)) != len(row_line_numbers):
            raise M15VectorStructureError(
                "data row line numbers must be unique"
            )
        if any(
            line_number <= self.column_header_line_number
            for line_number in row_line_numbers
        ):
            raise M15VectorStructureError(
                "data rows must follow the column header"
            )
        for row in self.rows:
            if len(row.fields) != len(self.columns):
                raise M15VectorRowError(
                    "data row field count does not match columns",
                    line_number=row.line_number,
                    expected_field_count=len(self.columns),
                    actual_field_count=len(row.fields),
                )

        if not isinstance(self.text_encoding, M15VectorTextEncoding):
            raise M15VectorError(
                "text_encoding must be an M15VectorTextEncoding"
            )
        if self.text_encoding is not _detect_text_encoding(
            self.source_artifact
        ):
            raise M15VectorError(
                "text_encoding does not match the source bytes"
            )
        metadata_format_identifier = _metadata_lookup(
            self.metadata_entries,
            "format_version",
        )
        if not isinstance(metadata_format_identifier, str):
            raise M15VectorMetadataError(
                "format_version metadata must be a string",
                key="format_version",
                line_number=None,
            )
        if not isinstance(self.format_identifier, str):
            raise M15VectorMetadataError(
                "format_identifier must be a string",
                key="format_version",
                line_number=None,
            )
        if self.format_identifier != metadata_format_identifier:
            raise M15VectorMetadataError(
                "format_identifier does not match format_version metadata",
                key="format_version",
                line_number=None,
            )
        if self.format_identifier != M15_VECTOR_FORMAT_VERSION:
            raise M15VectorMetadataError(
                "unsupported M15 vector format_version",
                key="format_version",
                line_number=None,
            )

        metadata_trace_kind = _metadata_lookup(
            self.metadata_entries,
            "trace_kind",
        )
        if not isinstance(metadata_trace_kind, str):
            raise M15VectorMetadataError(
                "trace_kind metadata must be a string",
                key="trace_kind",
                line_number=None,
            )
        if not isinstance(self.declared_trace_kind, str):
            raise M15VectorMetadataError(
                "declared_trace_kind must be a string",
                key="trace_kind",
                line_number=None,
            )
        if self.declared_trace_kind != metadata_trace_kind:
            raise M15VectorMetadataError(
                "declared_trace_kind does not match trace_kind metadata",
                key="trace_kind",
                line_number=None,
            )

        column_definition = _metadata_lookup(
            self.metadata_entries,
            "column_definition",
        )
        if not isinstance(column_definition, tuple) or any(
            not isinstance(column, str)
            for column in column_definition
        ):
            raise M15VectorMetadataError(
                "column_definition must be an array of strings",
                key="column_definition",
                line_number=None,
            )
        if column_definition != self.columns:
            raise M15VectorMetadataError(
                "column_definition does not match the column header",
                key="column_definition",
                line_number=self.column_header_line_number,
            )

    @property
    def source_artifact_id(self) -> str:
        """Return the identity of the captured source artifact."""

        return self.source_artifact.source_artifact_id

    @property
    def content_sha256(self) -> str:
        """Return the digest of the original, unchanged source bytes."""

        return self.source_artifact.content_sha256

    @property
    def recognized_trace_kind(self) -> M15VectorTraceKind | None:
        """Return the exact known trace kind, if recognized."""

        try:
            return M15VectorTraceKind(self.declared_trace_kind)
        except ValueError:
            return None

    @property
    def columns_match_recognized_trace_kind(self) -> bool:
        """Report whether columns match the audited producer declaration."""

        expected = expected_columns_for_trace_kind(
            self.declared_trace_kind
        )
        return expected is not None and self.columns == expected

    def metadata_value(self, key: str) -> MetadataValue:
        """Return one decoded metadata value by its exact key."""

        if not isinstance(key, str):
            raise M15VectorError("metadata key must be a string")
        for entry in self.metadata_entries:
            if entry.key == key:
                return entry.value
        raise KeyError(key)

    def value_at(self, row_index: int, column: str) -> str:
        """Return one raw field without numeric or semantic conversion."""

        if isinstance(row_index, bool) or not isinstance(row_index, int):
            raise M15VectorError("row_index must be an integer")
        if not isinstance(column, str):
            raise M15VectorError("column must be a string")
        try:
            column_index = self.columns.index(column)
        except ValueError as exc:
            raise KeyError(column) from exc
        return self.rows[row_index].fields[column_index]


def _parse_metadata_json(
    raw_json: str,
    *,
    key: str,
    line_number: int,
) -> MetadataValue:
    try:
        decoded = json.loads(
            raw_json,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_non_finite_metadata_number,
            strict=True,
        )
    except _NonFiniteMetadataNumber as exc:
        raise M15VectorMetadataError(
            f"non-finite metadata number is not permitted: {exc.token}",
            key=key,
            line_number=line_number,
        ) from exc
    except json.JSONDecodeError as exc:
        raise M15VectorMetadataError(
            f"invalid metadata JSON: {exc.msg}",
            key=key,
            line_number=line_number,
        ) from exc

    try:
        return _freeze_metadata_value(decoded)
    except TypeError as exc:
        raise M15VectorMetadataError(
            str(exc),
            key=key,
            line_number=line_number,
        ) from exc


def _metadata_lookup(
    entries: tuple[M15VectorMetadataEntry, ...],
    key: str,
) -> MetadataValue:
    for entry in entries:
        if entry.key == key:
            return entry.value
    raise M15VectorMetadataError(
        f"required metadata key is missing: {key}",
        key=key,
        line_number=None,
    )

def parse_m15_vector(source: SourceArtifact) -> M15VectorArtifact:
    """Parse one captured M15 vector without interpreting field values."""

    if not isinstance(source, SourceArtifact):
        raise M15VectorError("source must be a SourceArtifact")
    if not source.verify_integrity():
        raise M15VectorError(
            "source artifact integrity verification failed"
        )

    encoding = _detect_text_encoding(source)
    try:
        text = source.raw_bytes.decode(encoding.value)
    except UnicodeDecodeError as exc:
        raise M15VectorEncodingError(
            "source bytes are not valid UTF-8 vector text",
            byte_start=exc.start,
            byte_end=exc.end,
            reason=exc.reason,
        ) from exc

    if not text:
        raise M15VectorStructureError("vector text must not be empty")

    metadata_entries: list[M15VectorMetadataEntry] = []
    metadata_keys: set[str] = set()
    column_header_line_number: int | None = None
    columns: tuple[str, ...] | None = None
    rows: list[M15VectorRow] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise M15VectorStructureError(
                "blank lines are not permitted in vector text",
                line_number=line_number,
            )

        if column_header_line_number is None:
            if not line.startswith("# "):
                raise M15VectorStructureError(
                    "vector data appeared before the column header",
                    line_number=line_number,
                )

            header_body = line[2:]
            if "=" in header_body:
                key, raw_json = header_body.split("=", 1)
                if key in metadata_keys:
                    raise M15VectorMetadataError(
                        f"duplicate metadata key: {key}",
                        key=key,
                        line_number=line_number,
                    )
                entry = M15VectorMetadataEntry(
                    key=key,
                    raw_json=raw_json,
                    value=_parse_metadata_json(
                        raw_json,
                        key=key,
                        line_number=line_number,
                    ),
                    line_number=line_number,
                )
                metadata_entries.append(entry)
                metadata_keys.add(key)
                continue

            if M15_VECTOR_DELIMITER not in header_body:
                raise M15VectorStructureError(
                    "header comment is neither metadata nor columns",
                    line_number=line_number,
                )
            columns = tuple(header_body.split(M15_VECTOR_DELIMITER))
            column_header_line_number = line_number
            continue

        if line.startswith("#"):
            raise M15VectorStructureError(
                "comments are not permitted after the column header",
                line_number=line_number,
            )

        fields = tuple(line.split(M15_VECTOR_DELIMITER))
        if columns is None:
            raise M15VectorStructureError(
                "internal column state is unavailable",
                line_number=line_number,
            )
        if len(fields) != len(columns):
            raise M15VectorRowError(
                "data row field count does not match columns",
                line_number=line_number,
                expected_field_count=len(columns),
                actual_field_count=len(fields),
            )
        rows.append(
            M15VectorRow(
                line_number=line_number,
                fields=fields,
            )
        )

    if column_header_line_number is None or columns is None:
        raise M15VectorStructureError(
            "vector column header is missing"
        )

    immutable_metadata = tuple(metadata_entries)
    format_identifier = _metadata_lookup(
        immutable_metadata,
        "format_version",
    )
    if not isinstance(format_identifier, str):
        raise M15VectorMetadataError(
            "format_version metadata must be a string",
            key="format_version",
            line_number=None,
        )
    declared_trace_kind = _metadata_lookup(
        immutable_metadata,
        "trace_kind",
    )
    if not isinstance(declared_trace_kind, str):
        raise M15VectorMetadataError(
            "trace_kind metadata must be a string",
            key="trace_kind",
            line_number=None,
        )

    return M15VectorArtifact(
        source_artifact=source,
        metadata_entries=immutable_metadata,
        column_header_line_number=column_header_line_number,
        columns=columns,
        rows=tuple(rows),
        text_encoding=encoding,
        format_identifier=format_identifier,
        declared_trace_kind=declared_trace_kind,
    )
