"""Deterministic internal serialization of Artifact Auditor reports.

The serializer projects one immutable ``AuditReport`` into machine-readable
JSON bytes and a user-facing plain-text report. Both views originate from the
same validation checks. This module does not assign an Observatory schema
identifier, alter validation values, include source bytes, or render artifact
strings as executable markup.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from .audit_report import (
    AuditReport,
    AuditValue,
    AuditValueSnapshot,
    CheckOutcome,
    SourceLocation,
    ValidationCheck,
)


__all__ = [
    "AuditReportSerializationError",
    "audit_report_to_json_bytes",
    "audit_report_to_mapping",
    "audit_report_to_text",
]


type SerializedScalar = None | bool | int | Decimal | str
type SerializedValue = (
    SerializedScalar
    | tuple[SerializedValue, ...]
    | Mapping[str, SerializedValue]
)


class AuditReportSerializationError(ValueError):
    """Raised when an audit report cannot be serialized losslessly."""


def _validate_report(report: AuditReport) -> None:
    if not isinstance(report, AuditReport):
        raise AuditReportSerializationError(
            "report must be an AuditReport"
        )


def _mapping(
    values: Mapping[str, SerializedValue],
) -> Mapping[str, SerializedValue]:
    if not isinstance(values, Mapping):
        raise AuditReportSerializationError(
            "serialized mapping input must be a mapping"
        )
    if any(not isinstance(key, str) for key in values):
        raise AuditReportSerializationError(
            "serialized mapping keys must be strings"
        )
    return MappingProxyType(dict(values))


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _audit_value(value: AuditValue) -> SerializedValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise AuditReportSerializationError(
                "audit values must not contain non-finite decimals"
            )
        return value
    if isinstance(value, tuple):
        return tuple(_audit_value(item) for item in value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise AuditReportSerializationError(
                "audit-value mapping keys must be strings"
            )
        return _mapping(
            {
                key: _audit_value(item)
                for key, item in value.items()
            }
        )
    raise AuditReportSerializationError(
        f"unsupported audit value type: {type(value).__name__}"
    )


def _snapshot(
    value: AuditValueSnapshot | None,
) -> SerializedValue:
    if value is None:
        return None
    return _mapping({"value": _audit_value(value.value)})


def _source_location(
    location: SourceLocation,
) -> Mapping[str, SerializedValue]:
    return _mapping(
        {
            "line_number": location.line_number,
            "column_number": location.column_number,
            "json_path": location.json_path,
            "array_index": location.array_index,
            "vector_column": location.vector_column,
            "package_member": location.package_member,
            "markdown_heading": location.markdown_heading,
            "markdown_table_row": location.markdown_table_row,
            "source_record_ordinal": location.source_record_ordinal,
        }
    )


def _validation_check(
    check: ValidationCheck,
) -> Mapping[str, SerializedValue]:
    return _mapping(
        {
            "check_id": check.check_id,
            "check_code": check.check_code,
            "category": check.category.value,
            "outcome": check.outcome.value,
            "severity": (
                None if check.severity is None else check.severity.value
            ),
            "source_locations": tuple(
                _source_location(location)
                for location in check.source_locations
            ),
            "expected": _snapshot(check.expected),
            "observed": _snapshot(check.observed),
            "message": check.message,
            "upstream_rule_reference": check.upstream_rule_reference,
            "mandatory": check.mandatory,
        }
    )


def _check_summary(
    report: AuditReport,
) -> Mapping[str, SerializedValue]:
    outcomes = tuple(check.outcome for check in report.checks)
    return _mapping(
        {
            "total": len(report.checks),
            "passed": len(report.passed_checks),
            "failed": len(report.failed_checks),
            "warnings": len(report.warning_checks),
            "not_applicable": outcomes.count(
                CheckOutcome.NOT_APPLICABLE
            ),
            "not_evaluated": len(report.not_evaluated_checks),
            "digest_check_ids": tuple(
                check.check_id for check in report.digest_checks
            ),
        }
    )


def audit_report_to_mapping(
    report: AuditReport,
) -> Mapping[str, SerializedValue]:
    """Return one immutable serialization projection in field order."""

    _validate_report(report)
    return _mapping(
        {
            "report_origin": report.report_origin,
            "audit_report_id": report.audit_report_id,
            "source_artifact_id": report.source_artifact_id,
            "source_filename": report.source_filename,
            "source_path": report.source_path,
            "source_sha256": report.source_sha256,
            "source_byte_length": report.source_byte_length,
            "loaded_at": _timestamp(report.loaded_at),
            "detected_format": report.detected_format.value,
            "declared_schema_identifier": (
                report.declared_schema_identifier
            ),
            "declared_kind": report.declared_kind,
            "registry_binding_id": report.registry_binding_id,
            "matched_registry_identifier": (
                report.matched_registry_identifier
            ),
            "matched_registry_kind": report.matched_registry_kind,
            "producer_path": report.producer_path,
            "producer_version": report.producer_version,
            "measurement_contour": (
                None
                if report.measurement_contour is None
                else report.measurement_contour.value
            ),
            "started_at": _timestamp(report.started_at),
            "completed_at": _timestamp(report.completed_at),
            "observatory_version": report.observatory_version,
            "registry_revision": report.registry_revision,
            "check_summary": _check_summary(report),
            "checks": tuple(
                _validation_check(check) for check in report.checks
            ),
            "missing_package_members": report.missing_package_members,
            "overall_status": report.overall_status.value,
        }
    )


def _decimal_json(value: Decimal) -> str:
    if not value.is_finite():
        raise AuditReportSerializationError(
            "JSON output cannot contain non-finite decimals"
        )
    encoded = str(value)
    if encoded.startswith("+"):
        encoded = encoded[1:]
    return encoded


def _json_string(value: str) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def _json_value(value: SerializedValue) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return _decimal_json(value)
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, tuple):
        return "[" + ",".join(_json_value(item) for item in value) + "]"
    if isinstance(value, Mapping):
        return (
            "{"
            + ",".join(
                f"{_json_string(key)}:{_json_value(item)}"
                for key, item in value.items()
            )
            + "}"
        )
    raise AuditReportSerializationError(
        f"unsupported serialized value type: {type(value).__name__}"
    )


def audit_report_to_json_bytes(report: AuditReport) -> bytes:
    """Return compact UTF-8 JSON bytes with one terminating line feed."""

    projection = audit_report_to_mapping(report)
    return (_json_value(projection) + "\n").encode("utf-8")


def _data_string(value: str | None) -> str:
    if value is None:
        return "unavailable"
    encoded = _json_string(value)
    return (
        encoded.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _data_value(value: AuditValueSnapshot | None) -> str:
    if value is None:
        return "unavailable"
    return _json_value(_audit_value(value.value))


def _location_text(locations: tuple[SourceLocation, ...]) -> str:
    if not locations:
        return "unavailable"
    serialized = tuple(_source_location(location) for location in locations)
    return _json_value(serialized)


def _text_header(report: AuditReport) -> tuple[str, ...]:
    summary = _check_summary(report)
    return (
        "FRP Trace Observatory Artifact Audit Report",
        "",
        f"Report origin: {_data_string(report.report_origin)}",
        f"Overall status: {_data_string(report.overall_status.value)}",
        f"Audit report ID: {_data_string(report.audit_report_id)}",
        "",
        "Source provenance",
        f"Source artifact ID: {_data_string(report.source_artifact_id)}",
        f"Source filename: {_data_string(report.source_filename)}",
        f"Source path: {_data_string(report.source_path)}",
        f"Source SHA-256: {_data_string(report.source_sha256)}",
        f"Source byte length: {report.source_byte_length}",
        f"Loaded at: {_data_string(_timestamp(report.loaded_at))}",
        f"Detected format: {_data_string(report.detected_format.value)}",
        "",
        "Registry association",
        (
            "Declared schema identifier: "
            f"{_data_string(report.declared_schema_identifier)}"
        ),
        f"Declared kind: {_data_string(report.declared_kind)}",
        (
            "Registry binding ID: "
            f"{_data_string(report.registry_binding_id)}"
        ),
        (
            "Matched registry identifier: "
            f"{_data_string(report.matched_registry_identifier)}"
        ),
        (
            "Matched registry kind: "
            f"{_data_string(report.matched_registry_kind)}"
        ),
        f"Producer path: {_data_string(report.producer_path)}",
        f"Producer version: {_data_string(report.producer_version)}",
        (
            "Measurement contour: "
            + _data_string(
                None
                if report.measurement_contour is None
                else report.measurement_contour.value
            )
        ),
        f"Registry revision: {_data_string(report.registry_revision)}",
        (
            "Observatory version: "
            f"{_data_string(report.observatory_version)}"
        ),
        "",
        "Validation run",
        f"Started at: {_data_string(_timestamp(report.started_at))}",
        f"Completed at: {_data_string(_timestamp(report.completed_at))}",
        f"Total checks: {summary['total']}",
        f"Passed checks: {summary['passed']}",
        f"Failed checks: {summary['failed']}",
        f"Warnings: {summary['warnings']}",
        f"Not applicable: {summary['not_applicable']}",
        f"Not evaluated: {summary['not_evaluated']}",
        (
            "Missing package members: "
            f"{len(report.missing_package_members)}"
        ),
    )


def _missing_member_text(report: AuditReport) -> tuple[str, ...]:
    if not report.missing_package_members:
        return ()
    return (
        "",
        "Missing package member list",
        *(
            f"{index}. {_data_string(name)}"
            for index, name in enumerate(
                report.missing_package_members,
                start=1,
            )
        ),
    )


def _check_text(
    check: ValidationCheck,
    ordinal: int,
) -> tuple[str, ...]:
    severity = (
        "none" if check.severity is None else check.severity.value
    )
    return (
        "",
        f"Check {ordinal}",
        f"Check ID: {_data_string(check.check_id)}",
        f"Check code: {_data_string(check.check_code)}",
        f"Category: {_data_string(check.category.value)}",
        f"Outcome: {_data_string(check.outcome.value)}",
        f"Severity: {_data_string(severity)}",
        f"Mandatory: {'true' if check.mandatory else 'false'}",
        f"Source locations: {_location_text(check.source_locations)}",
        f"Expected: {_data_value(check.expected)}",
        f"Observed: {_data_value(check.observed)}",
        f"Message: {_data_string(check.message)}",
        (
            "Upstream rule reference: "
            f"{_data_string(check.upstream_rule_reference)}"
        ),
    )


def audit_report_to_text(report: AuditReport) -> str:
    """Return a complete user-facing plain-text view with final line feed."""

    _validate_report(report)
    lines = list(_text_header(report))
    lines.extend(_missing_member_text(report))
    lines.extend(("", "Validation checks"))
    for ordinal, check in enumerate(report.checks, start=1):
        lines.extend(_check_text(check, ordinal))
    return "\n".join(lines) + "\n"
