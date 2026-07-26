"""Tests for immutable Artifact Auditor report records."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

from artifact_auditor.audit_report import (
    AuditReport,
    AuditReportError,
    AuditValueSnapshot,
    CheckOutcome,
    MessageSeverity,
    SourceLocation,
    ValidationCategory,
    ValidationCheck,
    ValidationStatus,
)
from parsers.artifact_dispatch import ArtifactClassification
from schemas.registry import MeasurementContour


_LOADED_AT = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
_STARTED_AT = _LOADED_AT + timedelta(seconds=1)
_COMPLETED_AT = _STARTED_AT + timedelta(seconds=1)
_STRUCTURED_SCHEMA = "frp.structured_output.v1.7.0"


def _uuid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def _severity(outcome: CheckOutcome) -> MessageSeverity | None:
    return {
        CheckOutcome.FAIL: MessageSeverity.ERROR,
        CheckOutcome.WARNING: MessageSeverity.WARNING,
        CheckOutcome.NOT_EVALUATED: MessageSeverity.INFO,
    }.get(outcome)


def _check(
    outcome: CheckOutcome = CheckOutcome.PASS,
    *,
    number: int = 1,
    category: ValidationCategory = ValidationCategory.STRUCTURE,
) -> ValidationCheck:
    return ValidationCheck(
        check_id=_uuid(100 + number),
        check_code=f"TEST_{number}",
        category=category,
        outcome=outcome,
        severity=_severity(outcome),
        source_locations=(SourceLocation(json_path="$.value"),),
        expected=AuditValueSnapshot("expected"),
        observed=AuditValueSnapshot("observed"),
        message=f"{outcome.value} validation check",
        upstream_rule_reference="docs/integration_contract.md",
    )


def _report(
    *,
    status: ValidationStatus = ValidationStatus.RECOGNIZED_VALID,
    checks: tuple[ValidationCheck, ...] | None = None,
    missing_members: tuple[str, ...] = (),
) -> AuditReport:
    registered = status in {
        ValidationStatus.RECOGNIZED_VALID,
        ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
        ValidationStatus.RECOGNIZED_INVALID,
        ValidationStatus.INCOMPLETE_PACKAGE,
    }
    return AuditReport(
        audit_report_id=_uuid(1),
        source_artifact_id=_uuid(2),
        source_filename="artifact.json",
        source_path="published/artifact.json",
        source_sha256="a" * 64,
        source_byte_length=76,
        loaded_at=_LOADED_AT,
        detected_format=ArtifactClassification.JSON,
        declared_schema_identifier=_STRUCTURED_SCHEMA,
        declared_kind="demo",
        registry_binding_id=(
            "schema:frp.structured_output.v1.7.0:demo"
            if registered
            else None
        ),
        matched_registry_identifier=(
            _STRUCTURED_SCHEMA if registered else None
        ),
        matched_registry_kind="demo" if registered else None,
        producer_path="frp_prototype_v1_7_0.py" if registered else None,
        producer_version="1.7.0" if registered else None,
        measurement_contour=(
            MeasurementContour.STRUCTURED_OUTPUT
            if registered
            else None
        ),
        started_at=_STARTED_AT,
        completed_at=_COMPLETED_AT,
        observatory_version="0.1.0",
        registry_revision="test-registry-v1",
        checks=checks if checks is not None else (_check(),),
        missing_package_members=missing_members,
        overall_status=status,
    )


class AuditValueSnapshotTests(unittest.TestCase):
    """Exercise recursive immutable value capture."""

    def test_nested_values_are_frozen_without_type_loss(self) -> None:
        source_value = {
            "states": [-1, 0, 1],
            "ratio": Decimal("0.25"),
            "flags": [True, None],
        }

        snapshot = AuditValueSnapshot(source_value)

        self.assertIsInstance(snapshot.value, MappingProxyType)
        self.assertEqual(snapshot.value["states"], (-1, 0, 1))
        self.assertEqual(snapshot.value["ratio"], Decimal("0.25"))
        self.assertEqual(snapshot.value["flags"], (True, None))
        source_value["states"].append(76)
        self.assertEqual(snapshot.value["states"], (-1, 0, 1))
        with self.assertRaises(TypeError):
            snapshot.value["new"] = "value"
        with self.assertRaises(FrozenInstanceError):
            setattr(snapshot, "value", "changed")

    def test_unsupported_values_are_rejected(self) -> None:
        cases = (
            (Decimal("NaN"), "non-finite decimals"),
            (Decimal("Infinity"), "non-finite decimals"),
            ({"value": 0.25}, "unsupported audit value type"),
            ({76: "value"}, "mapping keys must be strings"),
            (object(), "unsupported audit value type"),
        )

        for value, message in cases:
            with self.subTest(value=value):
                with self.assertRaisesRegex(AuditReportError, message):
                    AuditValueSnapshot(value)


class SourceLocationTests(unittest.TestCase):
    """Exercise known-coordinate preservation without invention."""

    def test_location_retains_exact_coordinates_and_is_frozen(self) -> None:
        location = SourceLocation(
            line_number=7,
            column_number=3,
            json_path="$.trace[0]",
            array_index=0,
            vector_column="STATE_CODE",
            package_member="trace.json",
            markdown_heading="Qualification evidence",
            markdown_table_row=2,
            source_record_ordinal=1,
        )

        self.assertEqual(location.line_number, 7)
        self.assertEqual(location.array_index, 0)
        self.assertEqual(location.vector_column, "STATE_CODE")
        with self.assertRaises(FrozenInstanceError):
            setattr(location, "line_number", 8)

    def test_location_rejects_unknown_or_invalid_coordinates(self) -> None:
        valid = SourceLocation(json_path="$.value")
        cases = (
            ({}, "at least one known coordinate"),
            ({"column_number": 1}, "requires line_number"),
            ({"line_number": 0}, "line_number must be positive"),
            ({"line_number": True}, "line_number must be an integer"),
            ({"array_index": -1}, "array_index must be nonnegative"),
            ({"array_index": True}, "array_index must be an integer"),
            ({"json_path": ""}, "json_path must be nonempty"),
            ({"vector_column": " STATE "}, "without outer whitespace"),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    if changes:
                        coordinates = {"json_path": None, **changes}
                        replace(valid, **coordinates)
                    else:
                        SourceLocation()


class ValidationCheckTests(unittest.TestCase):
    """Exercise check outcome, severity, and storage relations."""

    def test_each_supported_outcome_retains_required_severity(self) -> None:
        outcomes = tuple(CheckOutcome)

        for number, outcome in enumerate(outcomes, start=1):
            with self.subTest(outcome=outcome):
                check = _check(outcome, number=number)

                self.assertIs(check.outcome, outcome)
                self.assertIs(check.severity, _severity(outcome))
                self.assertIsInstance(check.source_locations, tuple)
                self.assertIsInstance(check.expected, AuditValueSnapshot)
                self.assertIsInstance(check.observed, AuditValueSnapshot)

    def test_outcome_and_severity_relations_are_enforced(self) -> None:
        passed = _check()
        cases = (
            (
                {"severity": MessageSeverity.INFO},
                "pass and not-applicable",
            ),
            (
                {
                    "outcome": CheckOutcome.NOT_APPLICABLE,
                    "severity": MessageSeverity.WARNING,
                },
                "pass and not-applicable",
            ),
            (
                {"outcome": CheckOutcome.FAIL},
                "failed checks must have error severity",
            ),
            (
                {"outcome": CheckOutcome.WARNING},
                "warning checks must have warning severity",
            ),
            (
                {
                    "outcome": CheckOutcome.NOT_EVALUATED,
                    "severity": MessageSeverity.ERROR,
                },
                "not-evaluated checks must not have error severity",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    replace(passed, **changes)

    def test_check_fields_require_exact_types_and_identity(self) -> None:
        check = _check()
        location = check.source_locations[0]
        cases = (
            ({"check_id": "invalid"}, "check_id must be a valid UUID"),
            ({"check_code": "BAD CODE"}, "must not contain whitespace"),
            ({"category": "structure"}, "category must be"),
            ({"outcome": "pass"}, "outcome must be"),
            ({"severity": "info"}, "severity must be"),
            ({"source_locations": [location]}, "must be a tuple"),
            ({"source_locations": ("location",)}, "must contain"),
            ({"source_locations": (location, location)}, "must be unique"),
            ({"expected": "expected"}, "expected must be"),
            ({"observed": "observed"}, "observed must be"),
            ({"message": ""}, "message must be nonempty"),
            ({"upstream_rule_reference": ""}, "must be nonempty"),
            ({"mandatory": 1}, "mandatory must be a boolean"),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    replace(check, **changes)


class AuditReportTests(unittest.TestCase):
    """Exercise aggregate status, provenance, and registry relations."""

    def test_report_preserves_ordered_checks_and_derived_views(self) -> None:
        checks = (
            _check(CheckOutcome.PASS, number=1),
            _check(
                CheckOutcome.FAIL,
                number=2,
                category=ValidationCategory.DIGEST,
            ),
            _check(CheckOutcome.WARNING, number=3),
            _check(CheckOutcome.NOT_EVALUATED, number=4),
        )

        report = _report(
            status=ValidationStatus.RECOGNIZED_INVALID,
            checks=checks,
        )

        self.assertEqual(report.checks, checks)
        self.assertEqual(report.check_ids, tuple(c.check_id for c in checks))
        self.assertEqual(report.passed_checks, (checks[0],))
        self.assertEqual(report.failed_checks, (checks[1],))
        self.assertEqual(report.warning_checks, (checks[2],))
        self.assertEqual(report.not_evaluated_checks, (checks[3],))
        self.assertEqual(report.digest_checks, (checks[1],))
        self.assertEqual(report.report_origin, "observatory_derived")
        with self.assertRaises(FrozenInstanceError):
            setattr(report, "overall_status", ValidationStatus.UNRECOGNIZED)

    def test_supported_aggregate_statuses_accept_exact_evidence(self) -> None:
        cases = (
            (
                ValidationStatus.RECOGNIZED_VALID,
                (_check(),),
                (),
            ),
            (
                ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
                (
                    _check(),
                    _check(CheckOutcome.WARNING, number=2),
                ),
                (),
            ),
            (
                ValidationStatus.RECOGNIZED_INVALID,
                (_check(CheckOutcome.FAIL),),
                (),
            ),
            (
                ValidationStatus.INCOMPLETE_PACKAGE,
                (_check(CheckOutcome.NOT_EVALUATED),),
                ("missing.json",),
            ),
            (
                ValidationStatus.KNOWN_UNSUPPORTED,
                (_check(CheckOutcome.NOT_APPLICABLE),),
                (),
            ),
            (
                ValidationStatus.UNRECOGNIZED,
                (_check(CheckOutcome.NOT_APPLICABLE),),
                (),
            ),
        )

        for status, checks, missing_members in cases:
            with self.subTest(status=status):
                report = _report(
                    status=status,
                    checks=checks,
                    missing_members=missing_members,
                )

                self.assertIs(report.overall_status, status)
                self.assertEqual(
                    report.missing_package_members,
                    missing_members,
                )

    def test_invalid_aggregate_status_relations_are_rejected(self) -> None:
        valid = _report()
        warning = _check(CheckOutcome.WARNING, number=2)
        failure = _check(CheckOutcome.FAIL, number=3)
        not_evaluated = _check(CheckOutcome.NOT_EVALUATED, number=4)
        cases = (
            (
                {"checks": (warning,)},
                "recognized-valid reports require fully evaluated",
            ),
            (
                {"checks": (failure,)},
                "recognized-valid reports require fully evaluated",
            ),
            (
                {"checks": (not_evaluated,)},
                "recognized-valid reports require fully evaluated",
            ),
            (
                {
                    "overall_status":
                        ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
                },
                "warning reports require warnings",
            ),
            (
                {
                    "overall_status": ValidationStatus.RECOGNIZED_INVALID,
                },
                "recognized-invalid reports require a failed check",
            ),
            (
                {
                    "overall_status": ValidationStatus.INCOMPLETE_PACKAGE,
                },
                "incomplete-package reports require missing members",
            ),
            (
                {"missing_package_members": ("missing.json",)},
                "missing package members require incomplete-package",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    replace(valid, **changes)

    def test_registry_association_is_not_inferred(self) -> None:
        registered = _report()
        unrecognized = _report(status=ValidationStatus.UNRECOGNIZED)
        cases = (
            (
                registered,
                {"registry_binding_id": None},
                "recognized reports require registry_binding_id",
            ),
            (
                unrecognized,
                {"registry_binding_id": "schema:test"},
                "unrecognized reports must not have",
            ),
            (
                unrecognized,
                {"producer_path": "producer.py"},
                "registry-derived fields require",
            ),
        )

        for report, changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    replace(report, **changes)

    def test_report_fields_require_exact_provenance_types(self) -> None:
        report = _report()
        non_utc = datetime(
            2026,
            7,
            26,
            12,
            tzinfo=timezone(timedelta(hours=2)),
        )
        cases = (
            ({"audit_report_id": "invalid"}, "must be a valid UUID"),
            ({"source_artifact_id": "invalid"}, "must be a valid UUID"),
            ({"source_filename": "../artifact"}, "path separators"),
            ({"source_path": ""}, "source_path must not be empty"),
            ({"source_sha256": "A" * 64}, "lowercase hexadecimal"),
            ({"source_byte_length": True}, "must be an integer"),
            ({"source_byte_length": -1}, "must be nonnegative"),
            ({"loaded_at": non_utc}, "must be normalized to UTC"),
            ({"detected_format": "json"}, "detected_format must be"),
            ({"declared_kind": 76}, "must be a string or None"),
            ({"registry_binding_id": "bad binding"}, "contain whitespace"),
            ({"measurement_contour": "structured"}, "measurement_contour"),
            ({"started_at": _LOADED_AT - timedelta(seconds=1)},
             "must not precede loaded_at"),
            ({"completed_at": _STARTED_AT - timedelta(seconds=1)},
             "must not precede started_at"),
            ({"registry_revision": "bad revision"}, "contain whitespace"),
            ({"overall_status": "recognized_valid"}, "overall_status must"),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    replace(report, **changes)

    def test_check_and_missing_member_collections_are_exact(self) -> None:
        report = _report()
        check = report.checks[0]
        incomplete = _report(
            status=ValidationStatus.INCOMPLETE_PACKAGE,
            missing_members=("missing.json",),
        )
        cases = (
            (report, {"checks": [check]}, "checks must be a nonempty tuple"),
            (report, {"checks": ()}, "checks must be a nonempty tuple"),
            (report, {"checks": ("check",)}, "must contain ValidationCheck"),
            (report, {"checks": (check, check)}, "identifiers must be unique"),
            (
                report,
                {"missing_package_members": ["missing.json"]},
                "missing_package_members must be a tuple",
            ),
            (
                incomplete,
                {"missing_package_members": ("",)},
                "missing package member must be nonempty",
            ),
            (
                incomplete,
                {"missing_package_members": ("a.json", "a.json")},
                "missing_package_members must be unique",
            ),
        )

        for target, changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AuditReportError, message):
                    replace(target, **changes)


if __name__ == "__main__":
    unittest.main()
