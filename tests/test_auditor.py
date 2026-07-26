"""Tests for read-only Artifact Auditor orchestration."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from artifact_auditor.audit_report import (
    CheckOutcome,
    SourceLocation,
    ValidationCategory,
    ValidationStatus,
)
from artifact_auditor.auditor import (
    ArtifactAuditorError,
    audit_dispatched_artifact,
    audit_source_artifact,
)
from artifact_auditor.validation_core import (
    ValidationCheckSpec,
    ValidationCoreError,
)
from parsers.artifact_dispatch import dispatch_artifact
from parsers.m15_vector import M15_VECTOR_FORMAT_VERSION, ROUTE_TRACE_COLUMNS
from parsers.source_artifact import SourceArtifact, capture_source_bytes
from schemas.registry import MeasurementContour


_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "hardware_sensitivity"
)
_HARDWARE_FILE = "hardware_sensitivity_cost_profile_v1.json"
_HARDWARE_SCHEMA = "frp.benchmark.hardware_sensitivity_cost_profile.v1"
_STRUCTURED_SCHEMA = "frp.structured_output.v1.7.0"
_M3_SCHEMA = "frp.m3.benchmark_matrix.v1.7.0"
_M15_SCHEMA = "frp.m15.fixed_point_interface_profile.v1.7.0"
_M15_PACKAGE_SCHEMA = "frp.m15.rtl_comparison_vector_package.v1.7.0"
_COMPARATIVE_SCHEMA = "frp.benchmark.normalized_cost_profile.v1"
_LOADED_AT = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
_STARTED_AT = _LOADED_AT + timedelta(seconds=1)
_COMPLETED_AT = _STARTED_AT + timedelta(seconds=1)
_REPORT_ID = "00000000-0000-4000-8000-000000000076"
_M15_TARGET = "artifact_auditor.auditor.validate_m15_artifact"
_PACKAGE_TARGET = "artifact_auditor.auditor.validate_deterministic_package"
_STRUCTURED_TARGET = "artifact_auditor.auditor.validate_structured_output"


def _source(
    raw_bytes: bytes,
    filename: str,
) -> SourceArtifact:
    return capture_source_bytes(
        raw_bytes,
        source_filename=filename,
        source_path=f"published/{filename}",
        loaded_at=_LOADED_AT,
    )


def _json_source(
    schema: str,
    *,
    kind: str | None = None,
    filename: str = "artifact.json",
) -> SourceArtifact:
    root: dict[str, object] = {"schema": schema}
    if kind is not None:
        root["kind"] = kind
    raw_bytes = json.dumps(
        root,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode() + b"\n"
    return _source(raw_bytes, filename)


def _vector_source() -> SourceArtifact:
    metadata = (
        ("format_version", M15_VECTOR_FORMAT_VERSION),
        ("trace_kind", "pending_routes"),
        ("column_definition", list(ROUTE_TRACE_COLUMNS)),
    )
    lines = [
        f"# {key}="
        + json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for key, value in metadata
    ]
    lines.append("# " + " | ".join(ROUTE_TRACE_COLUMNS))
    lines.append("00000000 | 0 | 0 | 1 | 1 | pending")
    return _source(
        ("\n".join(lines) + "\n").encode(),
        "pending_routes.vec",
    )


def _spec(
    code: str,
    outcome: CheckOutcome = CheckOutcome.PASS,
) -> ValidationCheckSpec:
    return ValidationCheckSpec(
        check_code=code,
        category=ValidationCategory.STRUCTURE,
        outcome=outcome,
        message=f"{code} produced {outcome.value}",
        source_locations=(SourceLocation(json_path="$"),),
        upstream_rule_reference="docs/integration_contract.md",
    )


def _audit(
    source: SourceArtifact,
    *,
    audit_report_id: str = _REPORT_ID,
):
    return audit_source_artifact(
        source,
        registry_revision="registry-v1",
        observatory_version="0.1.0",
        started_at=_STARTED_AT,
        completed_at=_COMPLETED_AT,
        audit_report_id=audit_report_id,
    )


class ArtifactAuditorTests(unittest.TestCase):
    """Exercise routing, package state, provenance, and run guards."""

    def test_canonical_hardware_profile_builds_valid_report(self) -> None:
        path = _FIXTURE_ROOT / _HARDWARE_FILE
        source = capture_source_bytes(
            path.read_bytes(),
            source_filename=_HARDWARE_FILE,
            source_path=f"fixtures/hardware_sensitivity/{_HARDWARE_FILE}",
            loaded_at=_LOADED_AT,
        )
        raw_bytes = source.raw_bytes

        report = _audit(source)

        self.assertIs(
            report.overall_status, ValidationStatus.RECOGNIZED_VALID
        )
        self.assertIs(
            report.measurement_contour,
            MeasurementContour.HARDWARE_SENSITIVITY,
        )
        self.assertEqual(
            report.matched_registry_identifier, _HARDWARE_SCHEMA
        )
        self.assertEqual(len(report.checks), 14)
        self.assertEqual(
            tuple(check.check_code for check in report.checks[:3]),
            (
                "source_integrity",
                "artifact_classification",
                "registry_resolution",
            ),
        )
        self.assertTrue(
            all(check.outcome is CheckOutcome.PASS for check in report.checks)
        )
        self.assertEqual(report.started_at, _STARTED_AT)
        self.assertEqual(report.completed_at, _COMPLETED_AT)
        self.assertEqual(source.raw_bytes, raw_bytes)
        self.assertTrue(source.verify_integrity())

    def test_registered_contours_use_exact_validator_routes(self) -> None:
        cases = (
            (
                _STRUCTURED_SCHEMA,
                "demo",
                "validate_structured_output",
                MeasurementContour.STRUCTURED_OUTPUT,
                "structured_rule",
            ),
            (
                _M3_SCHEMA,
                "benchmark_matrix",
                "validate_m3_benchmark",
                MeasurementContour.M3_BENCHMARK_MATRIX,
                "m3_rule",
            ),
            (
                _M15_SCHEMA,
                "fixed_point_interface_profile",
                "validate_m15_artifact",
                MeasurementContour.M15_IMPLEMENTATION_MAPPING,
                "m15_rule",
            ),
            (
                None,
                None,
                "validate_m15_vector",
                MeasurementContour.M15_IMPLEMENTATION_MAPPING,
                "vector_rule",
            ),
            (
                _COMPARATIVE_SCHEMA,
                None,
                "validate_comparative_architecture",
                MeasurementContour.COMPARATIVE_ARCHITECTURE,
                "comparative_rule",
            ),
            (
                _HARDWARE_SCHEMA,
                None,
                "validate_hardware_sensitivity",
                MeasurementContour.HARDWARE_SENSITIVITY,
                "hardware_rule",
            ),
        )
        for schema, kind, validator_name, contour, code in cases:
            source = (
                _vector_source()
                if schema is None
                else _json_source(
                    schema,
                    kind=kind,
                    filename=f"{code}.json",
                )
            )
            target = f"artifact_auditor.auditor.{validator_name}"
            with self.subTest(validator=validator_name):
                with patch(target) as validator:
                    validator.return_value = SimpleNamespace(
                        check_specs=(_spec(code),)
                    )

                    report = _audit(source)

                validator.assert_called_once()
                dispatched = validator.call_args.args[0]
                self.assertIs(dispatched.source_artifact, source)
                self.assertIs(report.measurement_contour, contour)
                self.assertIs(
                    report.overall_status,
                    ValidationStatus.RECOGNIZED_VALID,
                )
                self.assertEqual(len(report.checks), 4)
                self.assertEqual(report.checks[-1].check_code, code)
                self.assertTrue(source.verify_integrity())

    def test_unregistered_states_are_not_promoted(self) -> None:
        cases = (
            (
                _source(b"plain text\n", "plain.txt"),
                ValidationStatus.UNRECOGNIZED,
            ),
            (
                _json_source(
                    "frp.unknown.v1",
                    filename="unknown.json",
                ),
                ValidationStatus.UNRECOGNIZED,
            ),
            (
                _json_source(
                    _STRUCTURED_SCHEMA,
                    kind="trace",
                    filename="unsupported.json",
                ),
                ValidationStatus.KNOWN_UNSUPPORTED,
            ),
        )
        for source, expected in cases:
            with self.subTest(expected=expected):
                report = _audit(source)

                self.assertIs(report.overall_status, expected)
                self.assertEqual(len(report.checks), 3)
                self.assertIsNone(report.registry_binding_id)
                self.assertIsNone(report.measurement_contour)
                self.assertEqual(report.missing_package_members, ())
                self.assertTrue(source.verify_integrity())

    def test_m15_package_reports_incomplete_and_complete_states(self) -> None:
        source = _json_source(
            _M15_PACKAGE_SCHEMA,
            kind="rtl_comparison_vector_package",
            filename="rtl_comparison_vector_package.json",
        )
        dispatched = dispatch_artifact(source)
        raw_bytes = source.raw_bytes
        artifact_result = SimpleNamespace(
            check_specs=(_spec("manifest_rule"),)
        )
        incomplete_result = SimpleNamespace(
            check_specs=(
                _spec("package_rule", CheckOutcome.FAIL),
            ),
            missing_member_names=("missing.vec",),
        )
        with (
            patch(
                _M15_TARGET, return_value=artifact_result
            ) as artifact_validator,
            patch(
                _PACKAGE_TARGET, return_value=incomplete_result
            ) as package_validator,
        ):
            report = audit_dispatched_artifact(
                dispatched,
                registry_revision="registry-v1",
                started_at=_STARTED_AT,
                completed_at=_COMPLETED_AT,
                audit_report_id=_REPORT_ID,
            )

        artifact_validator.assert_called_once_with(dispatched)
        package_validator.assert_called_once_with(dispatched, {})
        self.assertIs(
            report.overall_status,
            ValidationStatus.INCOMPLETE_PACKAGE,
        )
        self.assertEqual(
            report.missing_package_members,
            ("missing.vec",),
        )
        self.assertEqual(
            tuple(check.check_code for check in report.checks[-2:]),
            ("manifest_rule", "package_rule"),
        )

        members = {"member.vec": _source(b"member\n", "member.vec")}
        complete_result = SimpleNamespace(
            check_specs=(_spec("package_rule"),),
            missing_member_names=(),
        )
        with (
            patch(_M15_TARGET, return_value=artifact_result),
            patch(
                _PACKAGE_TARGET, return_value=complete_result
            ) as package_validator,
        ):
            complete = audit_dispatched_artifact(
                dispatched,
                registry_revision="registry-v1",
                package_members=members,
                started_at=_STARTED_AT,
                completed_at=_COMPLETED_AT,
                audit_report_id=(
                    "00000000-0000-4000-8000-000000000077"
                ),
            )

        package_validator.assert_called_once_with(dispatched, members)
        self.assertIs(
            complete.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(complete.missing_package_members, ())
        self.assertEqual(source.raw_bytes, raw_bytes)

    def test_package_members_are_restricted_to_package_route(self) -> None:
        member = _source(b"member\n", "member.vec")
        members = {"member.vec": member}
        source = _json_source(
            _HARDWARE_SCHEMA,
            filename="hardware.json",
        )
        with self.assertRaisesRegex(
            ArtifactAuditorError,
            "package_members apply only",
        ):
            audit_source_artifact(
                source,
                registry_revision="registry-v1",
                package_members=members,
            )

        with self.assertRaisesRegex(
            ArtifactAuditorError,
            "must be a mapping or None",
        ):
            audit_source_artifact(
                _source(b"plain\n", "plain.txt"),
                registry_revision="registry-v1",
                package_members=[member],
            )

    def test_timestamp_defaults_and_validation_are_enforced(self) -> None:
        source = _source(b"plain\n", "plain.txt")

        report = audit_source_artifact(
            source,
            registry_revision="registry-v1",
        )

        self.assertGreaterEqual(report.started_at, source.loaded_at)
        self.assertGreaterEqual(report.completed_at, report.started_at)

        non_utc = datetime(
            2026,
            7,
            26,
            12,
            tzinfo=timezone(timedelta(hours=2)),
        )
        cases = (
            (
                {"started_at": datetime(2026, 7, 26, 10, 0)},
                "started_at must include a timezone",
            ),
            (
                {"started_at": non_utc},
                "started_at must be normalized to UTC",
            ),
            (
                {
                    "started_at": _STARTED_AT,
                    "completed_at": non_utc,
                },
                "completed_at must be normalized to UTC",
            ),
        )
        for arguments, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    ArtifactAuditorError,
                    message,
                ):
                    audit_source_artifact(
                        source,
                        registry_revision="registry-v1",
                        **arguments,
                    )

        with self.assertRaisesRegex(
            ValidationCoreError,
            "must not precede started_at",
        ):
            audit_source_artifact(
                source,
                registry_revision="registry-v1",
                started_at=_STARTED_AT,
                completed_at=_LOADED_AT,
            )

    def test_input_integrity_and_route_results_are_guarded(self) -> None:
        with self.assertRaisesRegex(
            ArtifactAuditorError,
            "source_artifact must be a SourceArtifact",
        ):
            audit_source_artifact(
                b"artifact",
                registry_revision="registry-v1",
            )
        with self.assertRaisesRegex(
            ArtifactAuditorError,
            "dispatched_artifact must be a DispatchedArtifact",
        ):
            audit_dispatched_artifact(
                "artifact",
                registry_revision="registry-v1",
            )

        source = _json_source(
            _STRUCTURED_SCHEMA,
            kind="demo",
            filename="structured.json",
        )
        dispatched = dispatch_artifact(source)
        object.__setattr__(source, "raw_bytes", b"changed")
        with self.assertRaisesRegex(
            ArtifactAuditorError,
            "integrity verification failed",
        ):
            audit_dispatched_artifact(
                dispatched,
                registry_revision="registry-v1",
            )

        source = _json_source(
            _STRUCTURED_SCHEMA,
            kind="demo",
            filename="structured.json",
        )
        with patch(_STRUCTURED_TARGET) as validator:
            validator.return_value = SimpleNamespace(check_specs=[])
            with self.assertRaisesRegex(
                ArtifactAuditorError,
                "check_specs must be a tuple",
            ):
                _audit(source)

        with patch(_STRUCTURED_TARGET) as validator:
            validator.return_value = SimpleNamespace(check_specs=())
            with self.assertRaisesRegex(
                ArtifactAuditorError,
                "complete validation requires",
            ):
                _audit(source)
