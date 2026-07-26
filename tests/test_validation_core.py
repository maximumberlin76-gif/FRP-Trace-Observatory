"""Tests for shared Artifact Auditor validation orchestration."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

from artifact_auditor.audit_report import (
    AuditValueSnapshot,
    CheckOutcome,
    MessageSeverity,
    SourceLocation,
    ValidationCategory,
    ValidationStatus,
)
from artifact_auditor.validation_core import (
    ValidationCheckSpec,
    ValidationCoreError,
    base_check_specs,
    build_audit_report,
    derive_validation_status,
    materialize_validation_checks,
)
from parsers.artifact_dispatch import (
    ArtifactClassification,
    RegistrationStatus,
    dispatch_artifact,
)
from parsers.source_artifact import (
    SourceArtifact,
    capture_source_bytes,
)


_LOADED_AT = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
_STARTED_AT = _LOADED_AT + timedelta(seconds=1)
_COMPLETED_AT = _STARTED_AT + timedelta(seconds=1)
_STRUCTURED_SCHEMA = "frp.structured_output.v1.7.0"
_REPORT_ID = "00000000-0000-4000-8000-000000000076"
_MISSING = object()


def _source(
    raw_bytes: bytes,
    filename: str = "artifact.json",
) -> SourceArtifact:
    return capture_source_bytes(
        raw_bytes,
        source_filename=filename,
        source_path=f"published/{filename}",
        loaded_at=_LOADED_AT,
    )


def _json_bytes(
    *,
    schema: object = _STRUCTURED_SCHEMA,
    kind: object = "demo",
) -> bytes:
    root: dict[str, object] = {"value": 76}
    if schema is not _MISSING:
        root["schema"] = schema
    if kind is not _MISSING:
        root["kind"] = kind
    return (
        json.dumps(
            root,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _dispatch_json(
    *,
    schema: object = _STRUCTURED_SCHEMA,
    kind: object = "demo",
):
    return dispatch_artifact(_source(_json_bytes(schema=schema, kind=kind)))


def _spec(
    outcome: CheckOutcome = CheckOutcome.PASS,
    *,
    code: str = "artifact_rule",
) -> ValidationCheckSpec:
    return ValidationCheckSpec(
        check_code=code,
        category=ValidationCategory.STRUCTURE,
        outcome=outcome,
        message=f"{code} produced {outcome.value}",
        source_locations=(SourceLocation(json_path="$.value"),),
        expected=AuditValueSnapshot(76),
        observed=AuditValueSnapshot(76),
        upstream_rule_reference="docs/integration_contract.md",
    )


def _checks(*outcomes: CheckOutcome):
    specs = tuple(
        _spec(outcome, code=f"rule_{ordinal}")
        for ordinal, outcome in enumerate(outcomes, start=1)
    )
    return materialize_validation_checks(
        specs,
        audit_report_id=_REPORT_ID,
    )


def _build(
    *specs: ValidationCheckSpec,
    dispatched=None,
):
    return build_audit_report(
        dispatched if dispatched is not None else _dispatch_json(),
        tuple(specs) if specs else (_spec(),),
        validation_complete=True,
        started_at=_STARTED_AT,
        completed_at=_COMPLETED_AT,
        registry_revision="registry-v1",
        observatory_version="0.1.0",
        audit_report_id=_REPORT_ID,
    )


class ValidationCheckSpecTests(unittest.TestCase):
    """Exercise pre-materialization check invariants."""

    def test_invalid_spec_fields_raise_core_error(self) -> None:
        spec = _spec()
        cases = (
            ({"check_code": "bad code"}, "check_code"),
            ({"category": "structure"}, "category"),
            ({"outcome": "pass"}, "outcome"),
            ({"message": ""}, "message"),
            ({"source_locations": []}, "source_locations"),
            ({"mandatory": 1}, "mandatory"),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    ValidationCoreError,
                    message,
                ):
                    replace(spec, **changes)


class BaseCheckSpecTests(unittest.TestCase):
    """Exercise non-executing container and registry checks."""

    def test_registered_json_produces_ordered_passing_checks(self) -> None:
        dispatched = _dispatch_json()

        specs = base_check_specs(dispatched)

        self.assertEqual(
            tuple(spec.check_code for spec in specs),
            (
                "source_integrity",
                "artifact_classification",
                "registry_resolution",
            ),
        )
        self.assertEqual(
            tuple(spec.outcome for spec in specs),
            (CheckOutcome.PASS,) * 3,
        )
        self.assertEqual(specs[0].observed.value, True)
        self.assertEqual(specs[1].observed.value, "json")
        self.assertEqual(
            specs[2].expected.value,
            _STRUCTURED_SCHEMA,
        )
        self.assertEqual(
            specs[2].observed.value,
            _STRUCTURED_SCHEMA,
        )

    def test_unresolved_registry_states_remain_distinct(self) -> None:
        cases = (
            (
                _dispatch_json(schema=_MISSING),
                RegistrationStatus.MISSING_IDENTIFIER,
                "registered identifier string",
                None,
            ),
            (
                _dispatch_json(schema=76),
                RegistrationStatus.INVALID_IDENTIFIER,
                "registered identifier string",
                None,
            ),
            (
                _dispatch_json(schema="frp.unknown.v1"),
                RegistrationStatus.UNKNOWN_IDENTIFIER,
                None,
                "frp.unknown.v1",
            ),
            (
                _dispatch_json(kind="trace"),
                RegistrationStatus.UNSUPPORTED_KIND,
                ("demo", "self_test"),
                "trace",
            ),
        )

        for dispatched, status, expected, observed in cases:
            with self.subTest(status=status):
                spec = base_check_specs(dispatched)[2]

                self.assertIs(dispatched.registration.status, status)
                self.assertIs(spec.outcome, CheckOutcome.WARNING)
                self.assertEqual(
                    None if spec.expected is None else spec.expected.value,
                    expected,
                )
                self.assertEqual(
                    None if spec.observed is None else spec.observed.value,
                    observed,
                )

    def test_unparsed_container_is_registry_not_applicable(self) -> None:
        dispatched = dispatch_artifact(
            _source(b"plain text\n", "artifact.txt")
        )

        spec = base_check_specs(dispatched)[2]

        self.assertIs(
            dispatched.classification,
            ArtifactClassification.UTF8_TEXT,
        )
        self.assertIs(spec.outcome, CheckOutcome.NOT_APPLICABLE)
        self.assertFalse(spec.mandatory)
        self.assertEqual(spec.observed.value, "utf8_text")

    def test_tampered_source_is_rejected_before_checks(self) -> None:
        dispatched = _dispatch_json()
        object.__setattr__(
            dispatched.source_artifact,
            "raw_bytes",
            b"changed",
        )

        with self.assertRaisesRegex(
            ValidationCoreError,
            "integrity verification failed",
        ):
            base_check_specs(dispatched)


class MaterializationTests(unittest.TestCase):
    """Exercise ordered deterministic check identities and severity."""

    def test_materialization_preserves_order_and_stable_ids(self) -> None:
        specs = (
            _spec(CheckOutcome.PASS, code="first"),
            _spec(CheckOutcome.WARNING, code="second"),
            _spec(CheckOutcome.FAIL, code="third"),
        )

        first = materialize_validation_checks(
            specs,
            audit_report_id=_REPORT_ID,
        )
        second = materialize_validation_checks(
            specs,
            audit_report_id=_REPORT_ID,
        )

        self.assertEqual(first, second)
        self.assertEqual(
            tuple(check.check_code for check in first),
            ("first", "second", "third"),
        )
        self.assertEqual(len(set(check.check_id for check in first)), 3)
        expected_id = str(
            uuid5(
                UUID(_REPORT_ID),
                "validation-check:1:first",
            )
        )
        self.assertEqual(first[0].check_id, expected_id)

    def test_materialization_assigns_outcome_severity(self) -> None:
        outcomes = tuple(CheckOutcome)
        checks = _checks(*outcomes)
        expected = (
            None,
            MessageSeverity.ERROR,
            MessageSeverity.WARNING,
            None,
            None,
        )

        self.assertEqual(
            tuple(check.severity for check in checks),
            expected,
        )


class ValidationStatusTests(unittest.TestCase):
    """Exercise conservative aggregate status derivation."""

    def test_registered_statuses_follow_outcome_precedence(self) -> None:
        dispatched = _dispatch_json()
        cases = (
            (
                _checks(CheckOutcome.PASS),
                True,
                (),
                ValidationStatus.RECOGNIZED_VALID,
            ),
            (
                _checks(CheckOutcome.WARNING),
                True,
                (),
                ValidationStatus.RECOGNIZED_VALID_WITH_WARNINGS,
            ),
            (
                _checks(CheckOutcome.WARNING, CheckOutcome.FAIL),
                True,
                (),
                ValidationStatus.RECOGNIZED_INVALID,
            ),
            (
                _checks(CheckOutcome.NOT_EVALUATED),
                True,
                (),
                ValidationStatus.KNOWN_UNSUPPORTED,
            ),
            (
                _checks(CheckOutcome.FAIL),
                False,
                (),
                ValidationStatus.KNOWN_UNSUPPORTED,
            ),
            (
                _checks(CheckOutcome.FAIL),
                True,
                ("manifest.json",),
                ValidationStatus.INCOMPLETE_PACKAGE,
            ),
        )

        for checks, complete, missing, expected in cases:
            with self.subTest(expected=expected):
                status = derive_validation_status(
                    dispatched,
                    checks,
                    validation_complete=complete,
                    missing_package_members=missing,
                )

                self.assertIs(status, expected)

    def test_unregistered_statuses_are_not_promoted(self) -> None:
        cases = (
            (
                _dispatch_json(schema=_MISSING),
                ValidationStatus.UNRECOGNIZED,
            ),
            (
                _dispatch_json(schema="frp.unknown.v1"),
                ValidationStatus.UNRECOGNIZED,
            ),
            (
                _dispatch_json(kind="trace"),
                ValidationStatus.KNOWN_UNSUPPORTED,
            ),
            (
                dispatch_artifact(
                    _source(b"plain\n", "artifact.txt")
                ),
                ValidationStatus.UNRECOGNIZED,
            ),
        )

        for dispatched, expected in cases:
            with self.subTest(expected=expected):
                status = derive_validation_status(
                    dispatched,
                    _checks(CheckOutcome.PASS),
                    validation_complete=False,
                )

                self.assertIs(status, expected)


class AuditReportBuilderTests(unittest.TestCase):
    """Exercise report provenance, binding, and construction guards."""

    def test_registered_report_preserves_provenance_and_binding(self) -> None:
        dispatched = _dispatch_json()
        source = dispatched.source_artifact
        record = dispatched.compatibility_record
        raw_bytes = source.raw_bytes

        report = _build(_spec(), dispatched=dispatched)

        self.assertEqual(report.audit_report_id, _REPORT_ID)
        self.assertEqual(report.source_artifact_id, source.source_artifact_id)
        self.assertEqual(report.source_filename, source.source_filename)
        self.assertEqual(report.source_path, source.source_path)
        self.assertEqual(report.source_sha256, source.content_sha256)
        self.assertEqual(report.source_byte_length, source.byte_length)
        self.assertEqual(report.loaded_at, source.loaded_at)
        self.assertIs(report.detected_format, ArtifactClassification.JSON)
        self.assertEqual(
            report.declared_schema_identifier,
            _STRUCTURED_SCHEMA,
        )
        self.assertEqual(report.declared_kind, "demo")
        self.assertEqual(report.matched_registry_identifier, record.identifier)
        self.assertEqual(report.matched_registry_kind, record.artifact_kind)
        self.assertEqual(report.producer_path, record.producer_path)
        self.assertEqual(report.producer_version, record.producer_version)
        self.assertIs(report.measurement_contour, record.measurement_contour)
        self.assertIs(report.overall_status, ValidationStatus.RECOGNIZED_VALID)
        self.assertEqual(
            tuple(check.check_code for check in report.checks),
            (
                "source_integrity",
                "artifact_classification",
                "registry_resolution",
                "artifact_rule",
            ),
        )
        self.assertEqual(source.raw_bytes, raw_bytes)
        self.assertTrue(source.verify_integrity())

    def test_report_and_check_ids_are_repeatable_when_supplied(self) -> None:
        dispatched = _dispatch_json()

        first = _build(_spec(), dispatched=dispatched)
        second = _build(_spec(), dispatched=dispatched)

        self.assertEqual(first.audit_report_id, second.audit_report_id)
        self.assertEqual(first.check_ids, second.check_ids)
        self.assertEqual(
            first.registry_binding_id,
            second.registry_binding_id,
        )

    def test_report_builder_rejects_invalid_run_metadata(self) -> None:
        dispatched = _dispatch_json()
        non_utc = datetime(
            2026,
            7,
            26,
            12,
            tzinfo=timezone(timedelta(hours=2)),
        )
        base = {
            "validation_complete": False,
            "started_at": _STARTED_AT,
            "completed_at": _COMPLETED_AT,
            "registry_revision": "registry-v1",
            "audit_report_id": _REPORT_ID,
        }
        cases = (
            (
                {"validation_complete": True},
                "requires artifact-specific checks",
            ),
            ({"started_at": non_utc}, "normalized to UTC"),
            (
                {"started_at": _LOADED_AT - timedelta(seconds=1)},
                "must not precede the source load",
            ),
            (
                {"completed_at": _LOADED_AT},
                "must not precede started_at",
            ),
            ({"registry_revision": "bad revision"}, "contain whitespace"),
            ({"audit_report_id": "invalid"}, "must be a valid UUID"),
            (
                {"missing_package_members": ["missing.json"]},
                "must be a tuple",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                arguments = {**base, **changes}
                with self.assertRaisesRegex(
                    ValidationCoreError,
                    message,
                ):
                    build_audit_report(dispatched, **arguments)


if __name__ == "__main__":
    unittest.main()
