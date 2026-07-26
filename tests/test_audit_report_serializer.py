"""Tests for deterministic Artifact Auditor report serialization."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

from artifact_auditor.audit_report import (
    AuditReport,
    AuditValueSnapshot,
    CheckOutcome,
    MessageSeverity,
    SourceLocation,
    ValidationCategory,
    ValidationCheck,
    ValidationStatus,
)
from artifact_auditor.audit_report_serializer import (
    AuditReportSerializationError,
    audit_report_to_json_bytes,
    audit_report_to_mapping,
    audit_report_to_text,
)
from parsers.artifact_dispatch import ArtifactClassification
from schemas.registry import MeasurementContour


_LOADED_AT = datetime(
    2026,
    7,
    26,
    10,
    0,
    0,
    123456,
    tzinfo=timezone.utc,
)
_STARTED_AT = _LOADED_AT + timedelta(seconds=1)
_COMPLETED_AT = _STARTED_AT + timedelta(seconds=2)
_SCHEMA_IDENTIFIER = "frp.structured_output.v1.7.0"
_TOP_LEVEL_FIELDS = (
    "report_origin",
    "audit_report_id",
    "source_artifact_id",
    "source_filename",
    "source_path",
    "source_sha256",
    "source_byte_length",
    "loaded_at",
    "detected_format",
    "declared_schema_identifier",
    "declared_kind",
    "registry_binding_id",
    "matched_registry_identifier",
    "matched_registry_kind",
    "producer_path",
    "producer_version",
    "measurement_contour",
    "started_at",
    "completed_at",
    "observatory_version",
    "registry_revision",
    "check_summary",
    "checks",
    "missing_package_members",
    "overall_status",
)


def _uuid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def _severity(outcome: CheckOutcome) -> MessageSeverity | None:
    return {
        CheckOutcome.FAIL: MessageSeverity.ERROR,
        CheckOutcome.WARNING: MessageSeverity.WARNING,
        CheckOutcome.NOT_EVALUATED: MessageSeverity.INFO,
    }.get(outcome)


def _rich_location() -> SourceLocation:
    return SourceLocation(
        line_number=7,
        column_number=3,
        json_path="$.trace[0].state",
        array_index=0,
        vector_column="STATE",
        package_member="trace.json",
        markdown_heading="Trace evidence",
        markdown_table_row=2,
        source_record_ordinal=1,
    )


def _snapshot(number: int) -> AuditValueSnapshot:
    return AuditValueSnapshot(
        {
            "states": [-1, 0, 1],
            "ratio": Decimal(f"0.{number}25"),
            "flags": [True, None],
        }
    )


def _check(
    number: int,
    outcome: CheckOutcome,
    *,
    category: ValidationCategory = ValidationCategory.STRUCTURE,
) -> ValidationCheck:
    no_evidence = outcome in {
        CheckOutcome.NOT_APPLICABLE,
        CheckOutcome.NOT_EVALUATED,
    }
    return ValidationCheck(
        check_id=_uuid(100 + number),
        check_code=f"SERIALIZER_{number}",
        category=category,
        outcome=outcome,
        severity=_severity(outcome),
        source_locations=(
            ()
            if outcome is CheckOutcome.NOT_APPLICABLE
            else (
                _rich_location()
                if number == 1
                else SourceLocation(json_path=f"$.checks[{number - 1}]"),
            )
        ),
        expected=None if no_evidence else _snapshot(number),
        observed=None if no_evidence else _snapshot(number),
        message=f"{outcome.value} validation check <probe>& \u03a9",
        upstream_rule_reference=(
            None
            if outcome is CheckOutcome.NOT_APPLICABLE
            else "docs/integration_contract.md"
        ),
        mandatory=outcome is not CheckOutcome.NOT_APPLICABLE,
    )


def _mixed_checks() -> tuple[ValidationCheck, ...]:
    return (
        _check(1, CheckOutcome.PASS),
        _check(
            2,
            CheckOutcome.FAIL,
            category=ValidationCategory.DIGEST,
        ),
        _check(3, CheckOutcome.WARNING),
        _check(4, CheckOutcome.NOT_APPLICABLE),
        _check(5, CheckOutcome.NOT_EVALUATED),
    )


def _report(
    *,
    checks: tuple[ValidationCheck, ...] | None = None,
    status: ValidationStatus = ValidationStatus.RECOGNIZED_INVALID,
    missing_members: tuple[str, ...] = (),
) -> AuditReport:
    return AuditReport(
        audit_report_id=_uuid(1),
        source_artifact_id=_uuid(2),
        source_filename="artifact \N{GREEK CAPITAL LETTER OMEGA}.json",
        source_path=(
            "published/artifact "
            "\N{GREEK CAPITAL LETTER OMEGA}.json"
        ),
        source_sha256="a" * 64,
        source_byte_length=76,
        loaded_at=_LOADED_AT,
        detected_format=ArtifactClassification.JSON,
        declared_schema_identifier=_SCHEMA_IDENTIFIER,
        declared_kind="demo",
        registry_binding_id=(
            "schema:frp.structured_output.v1.7.0:demo"
        ),
        matched_registry_identifier=_SCHEMA_IDENTIFIER,
        matched_registry_kind="demo",
        producer_path="frp_prototype_v1_7_0.py",
        producer_version="1.7.0",
        measurement_contour=MeasurementContour.STRUCTURED_OUTPUT,
        started_at=_STARTED_AT,
        completed_at=_COMPLETED_AT,
        observatory_version="0.1.0",
        registry_revision="test-registry-v1",
        checks=_mixed_checks() if checks is None else checks,
        missing_package_members=missing_members,
        overall_status=status,
    )


class AuditReportMappingTests(unittest.TestCase):
    """Exercise the immutable machine-readable projection."""

    def test_mapping_is_complete_ordered_and_immutable(self) -> None:
        report = _report()

        projection = audit_report_to_mapping(report)

        self.assertIsInstance(projection, MappingProxyType)
        self.assertEqual(tuple(projection), _TOP_LEVEL_FIELDS)
        self.assertEqual(
            projection["report_origin"],
            "observatory_derived",
        )
        self.assertEqual(
            projection["loaded_at"],
            "2026-07-26T10:00:00.123456Z",
        )
        self.assertEqual(
            projection["measurement_contour"],
            "structured_output",
        )
        self.assertEqual(
            projection["overall_status"],
            "recognized_invalid",
        )
        self.assertNotIn("raw_bytes", projection)
        with self.assertRaises(TypeError):
            projection["overall_status"] = "changed"
        with self.assertRaises(TypeError):
            projection["check_summary"]["total"] = 0

    def test_recursive_values_and_source_locations_are_exact(self) -> None:
        projection = audit_report_to_mapping(_report())
        first_check = projection["checks"][0]
        fourth_check = projection["checks"][3]
        expected = first_check["expected"]["value"]
        location = first_check["source_locations"][0]

        self.assertIsInstance(first_check, MappingProxyType)
        self.assertEqual(expected["states"], (-1, 0, 1))
        self.assertEqual(expected["ratio"], Decimal("0.125"))
        self.assertEqual(expected["flags"], (True, None))
        self.assertEqual(
            dict(location),
            {
                "line_number": 7,
                "column_number": 3,
                "json_path": "$.trace[0].state",
                "array_index": 0,
                "vector_column": "STATE",
                "package_member": "trace.json",
                "markdown_heading": "Trace evidence",
                "markdown_table_row": 2,
                "source_record_ordinal": 1,
            },
        )
        self.assertEqual(fourth_check["source_locations"], ())
        self.assertIsNone(fourth_check["expected"])
        self.assertIsNone(fourth_check["observed"])
        self.assertFalse(fourth_check["mandatory"])
        self.assertEqual(
            dict(projection["check_summary"]),
            {
                "total": 5,
                "passed": 1,
                "failed": 1,
                "warnings": 1,
                "not_applicable": 1,
                "not_evaluated": 1,
                "digest_check_ids": (_uuid(102),),
            },
        )


class AuditReportJsonTests(unittest.TestCase):
    """Exercise deterministic compact JSON generation."""

    def test_json_bytes_are_deterministic_compact_and_numeric(self) -> None:
        report = _report()

        first = audit_report_to_json_bytes(report)
        second = audit_report_to_json_bytes(report)
        decoded = json.loads(first)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))
        self.assertEqual(first.count(b"\n"), 1)
        self.assertNotIn(b": ", first)
        self.assertNotIn(b", ", first)
        self.assertIn(b'"states":[-1,0,1]', first)
        self.assertIn(b'"ratio":0.125', first)
        self.assertNotIn(b'"ratio":"0.125"', first)
        self.assertIn(b"\\u03a9", first)
        self.assertNotIn("\N{GREEK CAPITAL LETTER OMEGA}".encode(), first)
        self.assertEqual(
            decoded["checks"][0]["expected"]["value"]["states"],
            [-1, 0, 1],
        )
        self.assertEqual(
            decoded["check_summary"]["digest_check_ids"],
            [_uuid(102)],
        )


class AuditReportTextTests(unittest.TestCase):
    """Exercise complete safe plain-text report generation."""

    def test_text_contains_provenance_summary_and_ordered_checks(
        self,
    ) -> None:
        report = _report()

        text = audit_report_to_text(report)

        self.assertTrue(
            text.startswith(
                "FRP Trace Observatory Artifact Audit Report\n"
            )
        )
        self.assertTrue(text.endswith("\n"))
        check_headings = tuple(
            line
            for line in text.splitlines()
            if line.startswith("Check ") and line[6:].isdigit()
        )
        self.assertEqual(
            check_headings,
            tuple(f"Check {number}" for number in range(1, 6)),
        )
        self.assertIn('Report origin: "observatory_derived"', text)
        self.assertIn('Overall status: "recognized_invalid"', text)
        self.assertIn("Source SHA-256: " + '"' + "a" * 64 + '"', text)
        self.assertIn("Total checks: 5", text)
        self.assertIn("Passed checks: 1", text)
        self.assertIn("Failed checks: 1", text)
        self.assertIn("Warnings: 1", text)
        self.assertIn("Not applicable: 1", text)
        self.assertIn("Not evaluated: 1", text)
        self.assertIn(f"Check ID: \"{_uuid(102)}\"", text)
        self.assertIn(
            r"Message: "
            r'"fail validation check \u003cprobe\u003e\u0026 \u03a9"',
            text,
        )
        self.assertNotIn("<probe>", text)
        self.assertNotIn("raw_bytes", text)

    def test_text_lists_only_declared_missing_package_members(
        self,
    ) -> None:
        report = _report(
            checks=(_check(1, CheckOutcome.NOT_EVALUATED),),
            status=ValidationStatus.INCOMPLETE_PACKAGE,
            missing_members=("trace.json", "manifest.json"),
        )

        text = audit_report_to_text(report)

        self.assertIn("Missing package members: 2", text)
        self.assertIn("Missing package member list", text)
        self.assertIn('1. "trace.json"', text)
        self.assertIn('2. "manifest.json"', text)
        self.assertNotIn("Missing package member list", audit_report_to_text(
            _report()
        ))


class AuditReportSerializerGuardTests(unittest.TestCase):
    """Exercise serializer boundary failures without executing input."""

    def test_non_report_inputs_are_rejected(self) -> None:
        serializers = (
            audit_report_to_mapping,
            audit_report_to_json_bytes,
            audit_report_to_text,
        )

        for serializer in serializers:
            for value in (None, {}, object()):
                with self.subTest(
                    serializer=serializer.__name__,
                    value=type(value).__name__,
                ):
                    with self.assertRaisesRegex(
                        AuditReportSerializationError,
                        "report must be an AuditReport",
                    ):
                        serializer(value)

    def test_tampered_audit_values_are_rejected(self) -> None:
        invalid_values = (
            (
                Decimal("NaN"),
                "non-finite decimals",
            ),
            (
                {76: "invalid key"},
                "mapping keys must be strings",
            ),
            (
                object(),
                "unsupported audit value type",
            ),
        )
        serializers = (
            audit_report_to_mapping,
            audit_report_to_json_bytes,
            audit_report_to_text,
        )

        for value, message in invalid_values:
            for serializer in serializers:
                report = _report()
                snapshot = report.checks[0].observed
                self.assertIsNotNone(snapshot)
                object.__setattr__(snapshot, "value", value)
                with self.subTest(
                    serializer=serializer.__name__,
                    value=type(value).__name__,
                ):
                    with self.assertRaisesRegex(
                        AuditReportSerializationError,
                        message,
                    ):
                        serializer(report)


if __name__ == "__main__":
    unittest.main()
