"""Tests for exact read-only M30 published Artifact Auditor reports."""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import FrozenInstanceError, replace
from types import MappingProxyType

from artifact_auditor.audit_report import (
    CheckOutcome,
    ValidationStatus,
)
from artifact_auditor.m30_published_auditor import (
    M30PublishedAuditorError,
    PublishedAuditBatch,
    audit_m30_published_archive,
    audit_m30_published_batch,
    audit_m30_published_dispatch,
)
from parsers.artifact_dispatch import RegistrationStatus, dispatch_artifact
from parsers.m30_published_dispatch import (
    dispatch_m30_published_members,
)
from schemas.m30_published_registry import PublishedMeasurementContour
from schemas.registry import ObservatoryMode
from tests.test_m30_published_member_intake import _published_intake


_ARCHIVE_ENVIRONMENT_VARIABLE = "FRP_M30_ARCHIVE_PATH"


class PublishedAuditorGuardTests(unittest.TestCase):
    """Exercise the dedicated M5-to-M6 public type boundary."""

    def test_dispatch_argument_requires_exact_m5_type(self) -> None:
        for value in (None, "dispatch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M30PublishedAuditorError,
                    "dispatch must be PublishedModeDispatch",
                ):
                    audit_m30_published_dispatch(value)

    def test_batch_argument_requires_exact_m5_batch_type(self) -> None:
        for value in (None, "batch", ()):  # type: ignore[arg-type]
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M30PublishedAuditorError,
                    "dispatch_batch must be PublishedDispatchBatch",
                ):
                    audit_m30_published_batch(value)

    def test_non_auditor_route_is_rejected_before_consumer_logic(self) -> None:
        member = _published_intake(0)
        from parsers.m30_published_dispatch import PublishedModeDispatch

        dispatch = PublishedModeDispatch.create(member, member.routes[1])

        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "only artifact_auditor M5 dispatches",
        ):
            audit_m30_published_dispatch(dispatch)


@unittest.skipUnless(
    os.environ.get(_ARCHIVE_ENVIRONMENT_VARIABLE),
    f"{_ARCHIVE_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM30PublishedAuditorIntegrationTests(unittest.TestCase):
    """Exercise all four reports against the exact M30 archive."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.archive_path = os.environ[_ARCHIVE_ENVIRONMENT_VARIABLE]
        cls.result = audit_m30_published_archive(cls.archive_path)

    def _fresh_dispatch(self, member_id: str):
        batch = dispatch_m30_published_members(self.archive_path)
        return batch.dispatch_for(
            member_id,
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

    def test_four_reports_are_green_and_source_ordered(self) -> None:
        self.assertIs(
            self.result.overall_status,
            ValidationStatus.RECOGNIZED_VALID,
        )
        self.assertEqual(self.result.failed_check_count, 0)
        self.assertEqual(
            tuple(report.member_id for report in self.result.reports),
            (
                "m16-fpga-preparation-execution-trace",
                "m27-telemetry-semantics",
                "m28-trace-observatory-upstream-contract",
                "m28-hierarchical-scaling-contract",
            ),
        )

    def test_report_contours_remain_four_distinct_published_contours(self) -> None:
        self.assertEqual(
            tuple(report.measurement_contour for report in self.result.reports),
            (
                PublishedMeasurementContour.M16_FPGA_PREPARATION_EXECUTION,
                PublishedMeasurementContour.M27_LONG_RUN_TELEMETRY_SEMANTICS,
                PublishedMeasurementContour.M28_UPSTREAM_INTEGRATION_CONTRACT,
                PublishedMeasurementContour.M28_HIERARCHICAL_SCALING_QUALIFICATION,
            ),
        )
        self.assertEqual(
            len({report.measurement_contour for report in self.result.reports}),
            4,
        )

    def test_report_check_counts_are_exact_and_complete(self) -> None:
        self.assertEqual(
            tuple(len(report.checks) for report in self.result.reports),
            (22, 16, 15, 16),
        )
        self.assertEqual(self.result.total_check_count, 69)
        for report in self.result.reports:
            self.assertEqual(report.passed_count, len(report.checks))
            self.assertEqual(report.failed_count, 0)

    def test_every_report_retains_exact_m5_dispatch_identity(self) -> None:
        expected_dispatches = (
            self.result.dispatch_batch.dispatches_for_mode(
                ObservatoryMode.ARTIFACT_AUDITOR
            )
        )
        for report, dispatch in zip(
            self.result.reports,
            expected_dispatches,
            strict=True,
        ):
            self.assertIs(report.dispatch, dispatch)
            self.assertIs(
                report.dispatch.source_artifact,
                dispatch.member.source_artifact,
            )
            self.assertIs(
                report.dispatch.parsed_artifact,
                dispatch.member.parsed_artifact,
            )

    def test_report_and_batch_digests_are_exact_deterministic_vectors(self) -> None:
        self.assertEqual(
            tuple(report.report_sha256 for report in self.result.reports),
            (
                "6c46ca147eb9a6d3bc0483ca4d25283a219b1f7f06a690f35ca7491a34251a17",
                "fbcd34ad44de9c0c3e5501492f6f2f3a6dc7870fc318ad099485d506dde59bb4",
                "db014a90d9d760b02e73e32e40a46cd1ac1defb85236a832e12496717d7c5769",
                "002859852bb07ec653fecc5653ca4d36bfee8d3bf7944cabc6ac57bc60cdf565",
            ),
        )
        self.assertEqual(
            self.result.batch_sha256,
            "aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03",
        )

    def test_repeated_complete_audit_is_digest_identical(self) -> None:
        repeated = audit_m30_published_archive(self.archive_path)

        self.assertEqual(repeated.batch_sha256, self.result.batch_sha256)
        self.assertEqual(
            tuple(report.report_sha256 for report in repeated.reports),
            tuple(report.report_sha256 for report in self.result.reports),
        )
        self.assertEqual(
            tuple(report.audit_report_id for report in repeated.reports),
            tuple(report.audit_report_id for report in self.result.reports),
        )

    def test_all_checks_have_deterministic_ids_and_source_locations(self) -> None:
        for report in self.result.reports:
            self.assertEqual(
                len({check.check_id for check in report.checks}),
                len(report.checks),
            )
            self.assertEqual(
                len({check.check_code for check in report.checks}),
                len(report.checks),
            )
            for check in report.checks:
                self.assertIs(check.outcome, CheckOutcome.PASS)
                self.assertEqual(len(check.source_locations), 1)
                self.assertEqual(
                    check.source_locations[0].package_member,
                    report.dispatch.member.registration.source_path,
                )

    def test_report_and_check_records_are_frozen(self) -> None:
        report = self.result.reports[0]

        with self.assertRaises(FrozenInstanceError):
            setattr(report, "report_sha256", "0" * 64)
        with self.assertRaises(FrozenInstanceError):
            setattr(report.checks[0], "message", "changed")

    def test_report_digest_and_contour_replacement_are_rejected(self) -> None:
        report = self.result.reports[0]

        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "report_sha256 does not bind",
        ):
            replace(report, report_sha256="0" * 64)
        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "contour differs",
        ):
            replace(
                report,
                measurement_contour=(
                    PublishedMeasurementContour.M27_LONG_RUN_TELEMETRY_SEMANTICS
                ),
            )

    def test_report_lookup_is_exact_without_aliases(self) -> None:
        report = self.result.report_for_member("m27-telemetry-semantics")

        self.assertEqual(report.member_id, "m27-telemetry-semantics")
        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "unknown published audit member",
        ):
            self.result.report_for_member("m27-telemetry")
        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "member_id must be a string",
        ):
            self.result.report_for_member(27)  # type: ignore[arg-type]

    def test_m16_exact_record_digest_and_summary_pass(self) -> None:
        report = self.result.report_for_member(
            "m16-fpga-preparation-execution-trace"
        )
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(
            outcomes["M30A.M16.RECORD_DIGEST"],
            CheckOutcome.PASS,
        )
        self.assertIs(outcomes["M30A.M16.SUMMARY"], CheckOutcome.PASS)
        self.assertIs(
            outcomes["M30A.M16.ACTIVE_NEUTRAL"],
            CheckOutcome.PASS,
        )

    def test_m27_composite_identity_is_not_rebound_to_legacy_schema(self) -> None:
        report = self.result.report_for_member("m27-telemetry-semantics")
        root = report.dispatch.parsed_artifact.root
        legacy = dispatch_artifact(report.dispatch.source_artifact)

        self.assertEqual(root["artifact_id"], "frp-m27-telemetry-semantics")
        self.assertEqual(root["schema_version"], "2.9.0")
        self.assertNotIn("schema", root)
        self.assertIs(
            legacy.registration.status,
            RegistrationStatus.MISSING_IDENTIFIER,
        )

    def test_m28_core_notation_and_temporal_schedulers_are_exact(self) -> None:
        for member_id in (
            "m28-trace-observatory-upstream-contract",
            "m28-hierarchical-scaling-contract",
        ):
            with self.subTest(member_id=member_id):
                report = self.result.report_for_member(member_id)
                core = report.dispatch.parsed_artifact.root["immutable_core"]
                self.assertEqual(core["balanced_ternary_notation"], "-1/0/1")
                self.assertEqual(core["active_neutral_state"], 0)
                self.assertEqual(core["semantic_values"], (-1, 0, 1))
                self.assertEqual(
                    core["temporal_scheduler_modes"],
                    ("1/7", "7/1"),
                )

    def test_m28_upstream_direction_forbids_mutation_and_writeback(self) -> None:
        report = self.result.report_for_member(
            "m28-trace-observatory-upstream-contract"
        )
        direction = report.dispatch.parsed_artifact.root[
            "integration_direction"
        ]

        self.assertEqual(direction["direction"], "upstream_to_downstream_only")
        self.assertEqual(direction["downstream_source_mutation"], "forbidden")
        self.assertEqual(direction["downstream_writeback"], "forbidden")

    def test_m16_direct_opposite_transition_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_dispatch(
            "m16-fpga-preparation-execution-trace"
        )

        def mutate(root):
            root["records"][0]["retained_state_before"][0] = -1
            root["records"][0]["retained_state_after"][0] = 1

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m30_published_dispatch(dispatch)
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )
        self.assertIs(
            outcomes["M30A.COMMON.STRICT_REPLAY"],
            CheckOutcome.FAIL,
        )
        self.assertIs(
            outcomes["M30A.M16.ACTIVE_NEUTRAL"],
            CheckOutcome.FAIL,
        )

    def test_m27_digest_tamper_is_invalid_without_execution(self) -> None:
        dispatch = self._fresh_dispatch("m27-telemetry-semantics")
        self._tamper_parsed_root(
            dispatch,
            lambda root: root.__setitem__("semantics_digest", "0" * 64),
        )

        report = audit_m30_published_dispatch(dispatch)
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )
        self.assertIs(
            outcomes["M30A.M27.SEMANTICS_DIGEST"],
            CheckOutcome.FAIL,
        )

    def test_m27_synthetic_schema_alias_is_invalid(self) -> None:
        dispatch = self._fresh_dispatch("m27-telemetry-semantics")
        self._tamper_parsed_root(
            dispatch,
            lambda root: root.__setitem__(
                "schema",
                "m27-telemetry-semantics-v2.9.0",
            ),
        )

        report = audit_m30_published_dispatch(dispatch)
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(outcomes["M30A.M27.ROOT_FIELDS"], CheckOutcome.FAIL)
        self.assertIs(outcomes["M30A.M27.IDENTITY"], CheckOutcome.FAIL)

    def test_m28_notation_plus_sign_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_dispatch(
            "m28-trace-observatory-upstream-contract"
        )

        def mutate(root):
            root["immutable_core"]["balanced_ternary_notation"] = "-1/0/+1"

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m30_published_dispatch(dispatch)
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(outcomes["M30A.M28U.CORE"], CheckOutcome.FAIL)
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_m28_scheduler_order_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_dispatch("m28-hierarchical-scaling-contract")

        def mutate(root):
            root["immutable_core"]["temporal_scheduler_modes"] = ["7/1", "1/7"]

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m30_published_dispatch(dispatch)
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(outcomes["M30A.M28H.CORE"], CheckOutcome.FAIL)
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_m28_writeback_permission_tamper_is_invalid(self) -> None:
        dispatch = self._fresh_dispatch(
            "m28-trace-observatory-upstream-contract"
        )

        def mutate(root):
            root["integration_direction"]["downstream_writeback"] = "allowed"

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m30_published_dispatch(dispatch)
        outcomes = {check.check_code: check.outcome for check in report.checks}

        self.assertIs(outcomes["M30A.M28U.DIRECTION"], CheckOutcome.FAIL)
        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )

    def test_invalid_member_structure_returns_failed_report_not_exception(self) -> None:
        dispatch = self._fresh_dispatch("m28-hierarchical-scaling-contract")

        def mutate(root):
            root["immutable_core"] = "not-an-object"

        self._tamper_parsed_root(dispatch, mutate)
        report = audit_m30_published_dispatch(dispatch)

        self.assertIs(
            report.overall_status,
            ValidationStatus.RECOGNIZED_INVALID,
        )
        self.assertGreater(report.failed_count, 0)

    def test_batch_digest_rejects_report_inventory_replacement(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "inventory length mismatch",
        ):
            replace(self.result, reports=self.result.reports[:-1])
        with self.assertRaisesRegex(
            M30PublishedAuditorError,
            "batch_sha256 does not bind",
        ):
            replace(self.result, batch_sha256="0" * 64)

    def test_batch_is_frozen(self) -> None:
        self.assertIsInstance(self.result, PublishedAuditBatch)
        with self.assertRaises(FrozenInstanceError):
            setattr(self.result, "batch_sha256", "0" * 64)


if __name__ == "__main__":
    unittest.main()
