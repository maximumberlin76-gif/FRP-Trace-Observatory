"""Tests for exact read-only FRP M31 published Artifact Auditor reports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

from artifact_auditor.audit_report import (
    CheckOutcome,
    ValidationStatus,
)
from artifact_auditor.m31_published_auditor import (
    M31PublishedAuditBatch,
    M31PublishedAuditReport,
    M31PublishedAuditorError,
    audit_m31_published_batch,
    audit_m31_published_dispatch,
    audit_m31_published_documents,
)
from artifact_auditor.m31_published_boundary_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M31_PUBLISHED_DOCUMENT_IDENTITIES,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedDocumentRole,
)
from parsers.m31_published_dispatch import (
    M31PublishedDispatchBatch,
    dispatch_m31_published_documents,
)
from schemas.m31_published_registry import M31PublishedMeasurementContour
from schemas.registry import ObservatoryMode


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
_LATER_LOADED_AT = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)

_COMMON_CHECK_CODES = (
    "M31A.COMMON.MODE",
    "M31A.COMMON.REGISTRY",
    "M31A.COMMON.RAW_SOURCE",
    "M31A.COMMON.DISPATCH_BINDING",
    "M31A.COMMON.STRICT_REPLAY",
    "M31A.COMMON.IDENTIFIER",
    "M31A.COMMON.CONTOUR",
)
_ROLE_CHECK_CODES = {
    M31PublishedDocumentRole.FORMAL_SCHEMA: (
        "M31A.SCHEMA.ROOT_FIELDS",
        "M31A.SCHEMA.DECLARATION",
        "M31A.SCHEMA.FIELD_INVENTORY",
        "M31A.SCHEMA.CONSTRAINTS",
    ),
    M31PublishedDocumentRole.EVIDENCE: (
        "M31A.EVIDENCE.IDENTITY",
        "M31A.EVIDENCE.CORE",
        "M31A.EVIDENCE.ACTIVE_ZERO_COUNTS",
        "M31A.EVIDENCE.ACTIVE_ZERO_RELATIONS",
        "M31A.EVIDENCE.HISTORICAL_CONTOUR",
        "M31A.EVIDENCE.CURRENT_CONTOURS",
        "M31A.EVIDENCE.BOUNDARIES",
        "M31A.EVIDENCE.PUBLICATION_CONTRACT",
        "M31A.EVIDENCE.PROVENANCE",
    ),
    M31PublishedDocumentRole.MANIFEST: (
        "M31A.MANIFEST.IDENTITY",
        "M31A.MANIFEST.SOURCE_DECLARATION",
        "M31A.MANIFEST.GENERATED_FILES",
    ),
    M31PublishedDocumentRole.QUALIFICATION: (
        "M31A.QUALIFICATION.IDENTITY",
        "M31A.QUALIFICATION.CHECKS",
        "M31A.QUALIFICATION.OUTPUTS",
    ),
}
_REPORT_SHA256 = (
    "5f18fd174e02f19adcac1809624a2c205b94ae6c226e05a20eaac4f896c6bb36",
    "e7c6163954973aa60994d2fa76f6f7edfdc6429fcbb397cf7e403a4e64f2f130",
    "e0ef32073524cd41ea2cf0b7b273ef3c63c61080e5ff72ae9e5432a81609d652",
    "5374a6b6e0def38ae5a50bb216c9be0396f6139f4a07e982b47e86b719414b53",
)
_BATCH_SHA256 = (
    "3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591"
)


class M31PublishedAuditorGuardTests(unittest.TestCase):
    """Exercise the dedicated M15-to-M16 public type boundary."""

    def test_dispatch_argument_requires_exact_m31_dispatch_type(self) -> None:
        for value in (None, "dispatch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M31PublishedAuditorError,
                    "dispatch must be M31PublishedDocumentDispatch",
                ):
                    audit_m31_published_dispatch(value)

    def test_batch_argument_requires_exact_m31_dispatch_batch_type(self) -> None:
        for value in (None, "batch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M31PublishedAuditorError,
                    "dispatch_batch must be M31PublishedDispatchBatch",
                ):
                    audit_m31_published_batch(value)


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM31PublishedAuditorIntegrationTests(unittest.TestCase):
    """Exercise all four reports against the exact FRP M31 publication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.result = audit_m31_published_documents(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )

    def _fresh_batch(self) -> M31PublishedDispatchBatch:
        return dispatch_m31_published_documents(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )

    def _fresh_auditor_dispatch(self, role: M31PublishedDocumentRole):
        return self._fresh_batch().dispatch_for(
            role,
            ObservatoryMode.ARTIFACT_AUDITOR,
        )

    def _tamper_parsed_root(self, dispatch, operation) -> None:
        root = json.loads(dispatch.raw_bytes.decode("utf-8"))
        operation(root)
        object.__setattr__(
            dispatch.parsed_artifact,
            "root",
            MappingProxyType(root),
        )

    def _outcomes(self, report: M31PublishedAuditReport):
        return {check.check_code: check.outcome for check in report.checks}

    def test_four_reports_are_green_and_role_ordered(self) -> None:
        self.assertIs(
            self.result.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(self.result.failed_check_count, 0)
        self.assertEqual(
            tuple(report.role for report in self.result.reports),
            tuple(M31PublishedDocumentRole),
        )
        self.assertEqual(
            tuple(
                report.dispatch.route.registration.source_path
                for report in self.result.reports
            ),
            tuple(
                identity.source_path
                for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
            ),
        )

    def test_report_contours_remain_four_distinct_m31_contours(self) -> None:
        contours = tuple(
            report.measurement_contour for report in self.result.reports
        )

        self.assertEqual(
            contours,
            (
                M31PublishedMeasurementContour.FORMAL_SCHEMA_DEFINITION,
                M31PublishedMeasurementContour
                .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE,
                M31PublishedMeasurementContour.PUBLICATION_MANIFEST,
                M31PublishedMeasurementContour.PUBLICATION_QUALIFICATION,
            ),
        )
        self.assertEqual(len(set(contours)), 4)

    def test_report_check_counts_and_codes_are_exact(self) -> None:
        self.assertEqual(
            tuple(len(report.checks) for report in self.result.reports),
            (11, 16, 10, 10),
        )
        self.assertEqual(self.result.total_check_count, 47)
        for report in self.result.reports:
            with self.subTest(role=report.role):
                self.assertEqual(
                    tuple(check.check_code for check in report.checks),
                    _COMMON_CHECK_CODES + _ROLE_CHECK_CODES[report.role],
                )
                self.assertEqual(report.passed_count, len(report.checks))
                self.assertEqual(report.failed_count, 0)

    def test_every_report_retains_exact_m15_dispatch_identity(self) -> None:
        expected_dispatches = self.result.dispatch_batch.dispatches_for_mode(
            ObservatoryMode.ARTIFACT_AUDITOR
        )
        for report, dispatch in zip(
            self.result.reports,
            expected_dispatches,
            strict=True,
        ):
            with self.subTest(role=report.role):
                self.assertIs(report.dispatch, dispatch)
                self.assertIs(
                    report.dispatch.source_artifact,
                    dispatch.document.source_artifact,
                )
                self.assertIs(
                    report.dispatch.parsed_artifact,
                    dispatch.document.parsed_artifact,
                )
                self.assertIs(report.dispatch.raw_bytes, dispatch.document.raw_bytes)

    def test_report_and_batch_digests_are_exact_vectors(self) -> None:
        self.assertEqual(
            tuple(report.report_sha256 for report in self.result.reports),
            _REPORT_SHA256,
        )
        self.assertEqual(self.result.batch_sha256, _BATCH_SHA256)

    def test_repeated_audit_ignores_loaded_at_for_digests_and_ids(self) -> None:
        repeated = audit_m31_published_documents(
            self.upstream_root,
            loaded_at=_LATER_LOADED_AT,
        )

        self.assertNotEqual(
            self.result.dispatch_batch.registry_validation.boundary.loaded_at,
            repeated.dispatch_batch.registry_validation.boundary.loaded_at,
        )
        self.assertEqual(repeated.batch_sha256, self.result.batch_sha256)
        self.assertEqual(
            tuple(report.report_sha256 for report in repeated.reports),
            tuple(report.report_sha256 for report in self.result.reports),
        )
        self.assertEqual(
            tuple(report.audit_report_id for report in repeated.reports),
            tuple(report.audit_report_id for report in self.result.reports),
        )
        self.assertEqual(
            tuple(
                check.check_id
                for report in repeated.reports
                for check in report.checks
            ),
            tuple(
                check.check_id
                for report in self.result.reports
                for check in report.checks
            ),
        )

    def test_all_checks_have_unique_ids_and_exact_source_locations(self) -> None:
        all_ids = []
        for report in self.result.reports:
            registration = report.dispatch.route.registration
            self.assertEqual(
                len({check.check_code for check in report.checks}),
                len(report.checks),
            )
            for check in report.checks:
                all_ids.append(check.check_id)
                self.assertIs(check.outcome, CheckOutcome.PASS)
                self.assertTrue(check.mandatory)
                self.assertEqual(len(check.source_locations), 1)
                self.assertEqual(
                    check.source_locations[0].package_member,
                    registration.source_path,
                )
        self.assertEqual(len(all_ids), 47)
        self.assertEqual(len(set(all_ids)), 47)

    def test_report_and_batch_models_are_frozen(self) -> None:
        report = self.result.reports[0]

        self.assertIsInstance(report, M31PublishedAuditReport)
        self.assertIsInstance(self.result, M31PublishedAuditBatch)
        with self.assertRaises(FrozenInstanceError):
            setattr(report, "report_sha256", "0" * 64)
        with self.assertRaises(FrozenInstanceError):
            setattr(report.checks[0], "message", "changed")
        with self.assertRaises(FrozenInstanceError):
            setattr(self.result, "batch_sha256", "0" * 64)

    def test_report_rebinding_is_rejected(self) -> None:
        report = self.result.reports[0]

        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "report_sha256 does not bind",
        ):
            replace(report, report_sha256="0" * 64)
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "contour differs",
        ):
            replace(
                report,
                measurement_contour=(
                    M31PublishedMeasurementContour.PUBLICATION_MANIFEST
                ),
            )
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "overall status differs",
        ):
            replace(
                report,
                overall_status=ValidationStatus.RECOGNIZED_INVALID,
            )
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "check identifiers do not bind",
        ):
            replace(
                report,
                checks=(
                    replace(
                        report.checks[0],
                        check_id="00000000-0000-4000-8000-000000000000",
                    ),
                )
                + report.checks[1:],
            )

    def test_batch_rebinding_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "inventory length mismatch",
        ):
            replace(self.result, reports=self.result.reports[:-1])
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "batch_sha256 does not bind",
        ):
            replace(self.result, batch_sha256="0" * 64)
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "batch status differs",
        ):
            replace(
                self.result,
                overall_status=ValidationStatus.RECOGNIZED_INVALID,
            )
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "order or exact dispatch identity mismatch",
        ):
            replace(
                self.result,
                reports=(self.result.reports[1], self.result.reports[0])
                + self.result.reports[2:],
            )

    def test_report_lookup_requires_exact_role_enum(self) -> None:
        report = self.result.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )

        self.assertIs(report.role, M31PublishedDocumentRole.EVIDENCE)
        with self.assertRaisesRegex(
            M31PublishedAuditorError,
            "role must be M31PublishedDocumentRole",
        ):
            self.result.report_for_role("evidence")  # type: ignore[arg-type]

    def test_visualizer_and_explorer_routes_are_rejected(self) -> None:
        batch = self._fresh_batch()
        for mode in (
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ObservatoryMode.TRACE_EXPLORER,
        ):
            dispatch = batch.dispatch_for(
                M31PublishedDocumentRole.EVIDENCE,
                mode,
            )
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(
                    M31PublishedAuditorError,
                    "only artifact_auditor M31 dispatches",
                ):
                    audit_m31_published_dispatch(dispatch)

    def test_evidence_core_and_active_zero_invariants_are_exact(self) -> None:
        report = self.result.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        root = report.dispatch.parsed_artifact.root
        core = root["core"]
        active = root["active_zero_execution_evidence"]

        self.assertEqual(core["balanced_ternary_notation"], "-1/0/1")
        self.assertEqual(core["semantic_values"], (-1, 0, 1))
        self.assertEqual(core["active_neutral_state"], 0)
        self.assertEqual(
            core["opposite_transition_routes"],
            ((-1, 0, 1), (1, 0, -1)),
        )
        self.assertEqual(core["temporal_scheduler_modes"], ("1/7", "7/1"))
        self.assertEqual(active["record_count"], 100)
        self.assertEqual(active["cell_observation_count"], 800)
        self.assertEqual(active["active_zero_after_observation_count"], 702)
        self.assertEqual(active["retained_transition_counts"]["direct_opposite"], 0)

    def test_historical_and_current_thermal_contours_remain_separate(self) -> None:
        root = self.result.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        ).dispatch.parsed_artifact.root
        historical = root["historical_thermal_experiment"]
        current = root["current_comparative_thermal_contours"]
        boundaries = root["evidence_boundaries"]

        self.assertEqual(
            historical["measurement_class"],
            "release_specific_model_thermal_load",
        )
        self.assertEqual(
            current["measurement_class"],
            "shared_model_comparative_benchmark",
        )
        self.assertFalse(historical["physical_temperature_measurement"])
        self.assertFalse(current["physical_temperature_measurement"])
        self.assertFalse(current["historical_heat_peak_interchangeable"])
        self.assertTrue(boundaries["historical_and_current_contours_separate"])
        self.assertTrue(boundaries["thermal_proxy_is_not_physical_temperature"])

    def test_publication_contract_is_one_way_and_read_only(self) -> None:
        root = self.result.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        ).dispatch.parsed_artifact.root
        contract = root["observatory_publication_contract"]

        self.assertEqual(
            contract["direction"],
            "upstream_published_bytes_to_downstream",
        )
        for field in (
            "downstream_metric_normalization",
            "downstream_semantic_reimplementation",
            "downstream_source_mutation",
            "downstream_writeback",
        ):
            with self.subTest(field=field):
                self.assertEqual(contract[field], "forbidden")
        self.assertTrue(contract["published_contours_must_remain_separate"])

    def test_schema_manifest_and_qualification_bind_exact_publication(self) -> None:
        schema = self.result.report_for_role(
            M31PublishedDocumentRole.FORMAL_SCHEMA
        ).dispatch.parsed_artifact.root
        manifest = self.result.report_for_role(
            M31PublishedDocumentRole.MANIFEST
        ).dispatch.parsed_artifact.root
        qualification = self.result.report_for_role(
            M31PublishedDocumentRole.QUALIFICATION
        ).dispatch.parsed_artifact.root

        self.assertEqual(
            schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(manifest["source_count"], 12)
        self.assertEqual(len(manifest["generated_files"]), 2)
        self.assertEqual(len(qualification["checks"]), 13)
        self.assertTrue(all(qualification["checks"].values()))
        self.assertEqual(len(qualification["outputs"]), 3)

    def test_provenance_binds_twelve_sources_and_m30_archive(self) -> None:
        evidence = self.result.report_for_role(
            M31PublishedDocumentRole.EVIDENCE
        ).dispatch.parsed_artifact.root
        boundary = self.result.dispatch_batch.registry_validation.boundary
        provenance = evidence["provenance"]

        self.assertEqual(len(provenance), 12)
        self.assertEqual(boundary.m30_archive_member_count, 10)
        self.assertEqual(boundary.m30_archive_sha256, FRP_M30_ARCHIVE_SHA256)
        self.assertEqual(
            sum(item["m30_archive_member_verified"] for item in provenance),
            10,
        )
        self.assertTrue(
            all(
                source.source_artifact.verify_integrity()
                for source in boundary.provenance_sources
            )
        )

    def test_schema_required_field_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.FORMAL_SCHEMA
        )
        self._tamper_parsed_root(
            dispatch,
            lambda root: root["required"].pop(),
        )

        report = audit_m31_published_dispatch(dispatch)
        outcomes = self._outcomes(report)
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )
        self.assertIs(outcomes["M31A.COMMON.STRICT_REPLAY"], CheckOutcome.FAIL)
        self.assertIs(outcomes["M31A.SCHEMA.FIELD_INVENTORY"], CheckOutcome.FAIL)

    def test_evidence_ternary_notation_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.EVIDENCE
        )

        def mutate(root):
            root["core"]["balanced_ternary_notation"] = "minus/zero/one"

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m31_published_dispatch(dispatch)
        outcomes = self._outcomes(report)

        self.assertIs(outcomes["M31A.COMMON.STRICT_REPLAY"], CheckOutcome.FAIL)
        self.assertIs(outcomes["M31A.EVIDENCE.CORE"], CheckOutcome.FAIL)
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_evidence_contour_boundary_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.EVIDENCE
        )

        def mutate(root):
            root["evidence_boundaries"][
                "historical_and_current_contours_separate"
            ] = False

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m31_published_dispatch(dispatch)

        self.assertIs(
            self._outcomes(report)["M31A.EVIDENCE.BOUNDARIES"],
            CheckOutcome.FAIL,
        )
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_evidence_writeback_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.EVIDENCE
        )

        def mutate(root):
            root["observatory_publication_contract"][
                "downstream_writeback"
            ] = "allowed"

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m31_published_dispatch(dispatch)

        self.assertIs(
            self._outcomes(report)[
                "M31A.EVIDENCE.PUBLICATION_CONTRACT"
            ],
            CheckOutcome.FAIL,
        )
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_evidence_provenance_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.EVIDENCE
        )

        def mutate(root):
            root["provenance"][0]["raw_sha256"] = "0" * 64

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m31_published_dispatch(dispatch)

        self.assertIs(
            self._outcomes(report)["M31A.EVIDENCE.PROVENANCE"],
            CheckOutcome.FAIL,
        )
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_manifest_generated_file_digest_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.MANIFEST
        )

        def mutate(root):
            root["generated_files"][0]["raw_sha256"] = "0" * 64

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m31_published_dispatch(dispatch)

        self.assertIs(
            self._outcomes(report)["M31A.MANIFEST.GENERATED_FILES"],
            CheckOutcome.FAIL,
        )
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_qualification_check_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.QUALIFICATION
        )

        def mutate(root):
            root["checks"]["observatory_boundary_read_only"] = False

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m31_published_dispatch(dispatch)

        self.assertIs(
            self._outcomes(report)["M31A.QUALIFICATION.CHECKS"],
            CheckOutcome.FAIL,
        )
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_invalid_nested_structure_returns_failed_report(self) -> None:
        dispatch = self._fresh_auditor_dispatch(
            M31PublishedDocumentRole.EVIDENCE
        )
        self._tamper_parsed_root(
            dispatch,
            lambda root: root.__setitem__("core", "not-an-object"),
        )

        report = audit_m31_published_dispatch(dispatch)

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )
        self.assertGreater(report.failed_count, 0)
        self.assertIs(
            self._outcomes(report)["M31A.EVIDENCE.CORE"],
            CheckOutcome.FAIL,
        )

    def test_audit_does_not_modify_upstream_checkout(self) -> None:
        before = subprocess.run(
            [
                "git",
                "-C",
                str(self.upstream_root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        identities_before = tuple(
            (self.upstream_root / identity.source_path).read_bytes()
            for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
        )

        audit_m31_published_documents(
            self.upstream_root,
            loaded_at=_LATER_LOADED_AT,
        )

        identities_after = tuple(
            (self.upstream_root / identity.source_path).read_bytes()
            for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
        )
        after = subprocess.run(
            [
                "git",
                "-C",
                str(self.upstream_root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertEqual(identities_after, identities_before)
        self.assertEqual(after, before)

    def test_cli_reports_exact_audit_and_forbidden_operations(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "artifact_auditor.m31_published_auditor",
                "--upstream-root",
                str(self.upstream_root),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        lines = completed.stdout.splitlines()

        self.assertIn(
            "FRP Observatory M31 published Artifact Auditor: PASS",
            lines,
        )
        self.assertIn(
            f"registry_revision={M31_PUBLISHED_REGISTRY_REVISION}",
            lines,
        )
        self.assertIn(f"m30_archive_sha256={FRP_M30_ARCHIVE_SHA256}", lines)
        self.assertIn("published_documents=4", lines)
        self.assertIn("audit_reports=4", lines)
        self.assertIn("validation_checks=47", lines)
        self.assertIn("failed_checks=0", lines)
        self.assertIn(f"batch_sha256={_BATCH_SHA256}", lines)
        for declaration in (
            "source_execution=forbidden",
            "metric_normalization=forbidden",
            "thermal_contour_merging=forbidden",
            "semantic_reimplementation=forbidden",
            "source_mutation=forbidden",
            "downstream_writeback=forbidden",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, lines)


if __name__ == "__main__":
    unittest.main()
