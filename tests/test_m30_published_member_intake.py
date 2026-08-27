"""Tests for strict read-only intake of M30 published members."""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import PurePosixPath
from unittest.mock import patch

from artifact_auditor.m30_archive_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M30ArchiveMember,
    RetainedArchiveMember,
)
from parsers.json_artifact import parse_json_artifact
from parsers.m30_published_member_intake import (
    M30PublishedMemberIntakeError,
    PublishedIdentifierBinding,
    PublishedIdentifierEvidence,
    PublishedIdentifierMismatchError,
    PublishedMemberIntake,
    identifier_binding_for_registration,
    identifier_evidence_for_registration,
    intake_m30_published_members,
)
from parsers.source_artifact import capture_source_bytes
from schemas.m30_published_registry import (
    M30_PUBLISHED_MEMBER_REGISTRATIONS,
    M30_PUBLISHED_REGISTRY_REVISION,
    PublishedMemberRegistration,
    PublishedModeRoute,
)
from schemas.registry import ObservatoryMode


_ARCHIVE_ENVIRONMENT_VARIABLE = "FRP_M30_ARCHIVE_PATH"


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _compatibility_key(
    member_id: str,
    schema_identifier: str,
    raw_sha256: str,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "member_id": member_id,
                "schema_identifier": schema_identifier,
                "raw_sha256": raw_sha256,
            }
        )
    ).hexdigest()


def _raw_member(index: int) -> bytes:
    registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[index]
    if index == 1:
        value = {
            "artifact_id": "frp-m27-telemetry-semantics",
            "schema_version": "2.9.0",
            "scheduler_modes": ["1/7", "7/1"],
            "ternary_states": [-1, 0, 1],
        }
    else:
        value = {
            "schema": registration.schema_identifier,
            "ternary_states": [-1, 0, 1],
        }
    return _canonical_json_bytes(value)


def _synthetic_registration(
    index: int,
    raw_bytes: bytes,
) -> PublishedMemberRegistration:
    canonical = M30_PUBLISHED_MEMBER_REGISTRATIONS[index]
    digest = hashlib.sha256(raw_bytes).hexdigest()
    return replace(
        canonical,
        byte_length=len(raw_bytes),
        raw_sha256=digest,
        compatibility_key=_compatibility_key(
            canonical.member_id,
            canonical.schema_identifier,
            digest,
        ),
    )


def _intake_arguments(
    index: int,
    *,
    raw_bytes: bytes | None = None,
) -> tuple[PublishedMemberRegistration, dict[str, object]]:
    raw = _raw_member(index) if raw_bytes is None else raw_bytes
    registration = _synthetic_registration(index, raw)
    member = M30ArchiveMember(
        path=registration.source_path,
        byte_length=len(raw),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )
    retained = RetainedArchiveMember(member=member, raw_bytes=raw)
    source = capture_source_bytes(
        raw,
        source_filename=PurePosixPath(registration.source_path).name,
        source_path=registration.source_path,
    )
    parsed = parse_json_artifact(source)
    with patch(
        "parsers.m30_published_member_intake.registration_for_member_id",
        return_value=registration,
    ):
        binding = identifier_binding_for_registration(registration)
        evidence = identifier_evidence_for_registration(registration)
    arguments: dict[str, object] = {
        "archive_sha256": FRP_M30_ARCHIVE_SHA256,
        "registry_revision": M30_PUBLISHED_REGISTRY_REVISION,
        "registration": registration,
        "routes": tuple(
            PublishedModeRoute(registration=registration, mode=mode)
            for mode in registration.observatory_modes
        ),
        "retained_member": retained,
        "source_artifact": source,
        "parsed_artifact": parsed,
        "identifier_binding": binding,
        "identifier_evidence": evidence,
    }
    return registration, arguments


def _published_intake(
    index: int,
    *,
    raw_bytes: bytes | None = None,
    **changes: object,
) -> PublishedMemberIntake:
    registration, arguments = _intake_arguments(
        index,
        raw_bytes=raw_bytes,
    )
    arguments.update(changes)
    with patch(
        "parsers.m30_published_member_intake.registration_for_member_id",
        return_value=registration,
    ):
        return PublishedMemberIntake(**arguments)


class PublishedIdentifierEvidenceTests(unittest.TestCase):
    """Exercise immutable exact identifier evidence."""

    def test_evidence_is_frozen_and_retains_exact_text(self) -> None:
        evidence = PublishedIdentifierEvidence(
            field_name="schema_version",
            value="2.9.0",
        )

        self.assertEqual(evidence.field_name, "schema_version")
        self.assertEqual(evidence.value, "2.9.0")
        with self.assertRaises(FrozenInstanceError):
            setattr(evidence, "value", "3.0.0")

    def test_field_name_requires_one_machine_token(self) -> None:
        for field_name in ("", " schema", "schema ", "schema version", 7):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(
                    M30PublishedMemberIntakeError,
                    "field_name must be a machine token",
                ):
                    PublishedIdentifierEvidence(
                        field_name=field_name,
                        value="v1",
                    )

    def test_value_requires_exact_nonempty_text(self) -> None:
        for value in ("", " v1", "v1 ", 7):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M30PublishedMemberIntakeError,
                    "value must be a nonempty string",
                ):
                    PublishedIdentifierEvidence(
                        field_name="schema",
                        value=value,
                    )


class PublishedIdentifierBindingTests(unittest.TestCase):
    """Exercise exact M3-to-M4 identifier-field bindings."""

    def test_canonical_inventory_has_three_schema_and_one_composite_binding(
        self,
    ) -> None:
        bindings = tuple(
            identifier_binding_for_registration(registration)
            for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
        )

        self.assertEqual(
            bindings,
            (
                PublishedIdentifierBinding.SCHEMA_FIELD,
                PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS,
                PublishedIdentifierBinding.SCHEMA_FIELD,
                PublishedIdentifierBinding.SCHEMA_FIELD,
            ),
        )

    def test_canonical_identifier_evidence_is_exact_and_unaliased(
        self,
    ) -> None:
        evidence = tuple(
            tuple((item.field_name, item.value) for item in values)
            for values in (
                identifier_evidence_for_registration(registration)
                for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
            )
        )

        self.assertEqual(
            evidence,
            (
                (
                    (
                        "schema",
                        "frp.m16.fpga_preparation_execution_trace.v2.1.0",
                    ),
                ),
                (
                    ("artifact_id", "frp-m27-telemetry-semantics"),
                    ("schema_version", "2.9.0"),
                ),
                (
                    (
                        "schema",
                        "frp.m28.trace_observatory_upstream_contract.v3.0.0",
                    ),
                ),
                (
                    (
                        "schema",
                        "frp.m28.hierarchical_scaling_contract.v3.0.0",
                    ),
                ),
            ),
        )

    def test_binding_requires_registration_type(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedMemberIntakeError,
            "registration must be PublishedMemberRegistration",
        ):
            identifier_binding_for_registration("m27-telemetry-semantics")

    def test_binding_rejects_noncanonical_registration(self) -> None:
        registration = replace(
            M30_PUBLISHED_MEMBER_REGISTRATIONS[0],
            upstream_release="frp-v99.0.0-test",
        )

        with self.assertRaisesRegex(
            M30PublishedMemberIntakeError,
            "differs from the canonical M30 identity",
        ):
            identifier_binding_for_registration(registration)

    def test_binding_rejects_unknown_member_without_aliasing(self) -> None:
        canonical = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        member_id = "m16-execution-trace-alias"
        registration = replace(
            canonical,
            member_id=member_id,
            compatibility_key=_compatibility_key(
                member_id,
                canonical.schema_identifier,
                canonical.raw_sha256,
            ),
        )

        with self.assertRaisesRegex(
            M30PublishedMemberIntakeError,
            "not in the canonical M30 inventory",
        ):
            identifier_binding_for_registration(registration)


class PublishedMemberIntakeTests(unittest.TestCase):
    """Exercise one strict raw-byte and JSON member intake."""

    def test_schema_member_preserves_raw_bytes_and_exact_routes(self) -> None:
        intake = _published_intake(0)

        self.assertEqual(intake.raw_bytes, _raw_member(0))
        self.assertEqual(
            intake.identifier_binding,
            PublishedIdentifierBinding.SCHEMA_FIELD,
        )
        self.assertEqual(
            intake.eligible_modes,
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ObservatoryMode.TRACE_EXPLORER,
            ),
        )
        self.assertEqual(intake.parsed_artifact.root["ternary_states"], (-1, 0, 1))

    def test_m27_preserves_separate_identifier_fields_and_scheduler_modes(
        self,
    ) -> None:
        intake = _published_intake(1)

        self.assertEqual(
            intake.identifier_binding,
            PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS,
        )
        self.assertEqual(
            tuple(
                (item.field_name, item.value)
                for item in intake.identifier_evidence
            ),
            (
                ("artifact_id", "frp-m27-telemetry-semantics"),
                ("schema_version", "2.9.0"),
            ),
        )
        self.assertNotIn("schema", intake.parsed_artifact.root)
        self.assertEqual(
            intake.parsed_artifact.root["scheduler_modes"],
            ("1/7", "7/1"),
        )

    def test_intake_is_frozen(self) -> None:
        intake = _published_intake(2)

        with self.assertRaises(FrozenInstanceError):
            setattr(intake, "registry_revision", "changed")

    def test_schema_mismatch_retains_error_coordinates(self) -> None:
        raw = _canonical_json_bytes(
            {
                "schema": "frp.m16.wrong.v1",
                "ternary_states": [-1, 0, 1],
            }
        )

        with self.assertRaises(PublishedIdentifierMismatchError) as context:
            _published_intake(0, raw_bytes=raw)

        error = context.exception
        self.assertEqual(
            error.member_id,
            "m16-fpga-preparation-execution-trace",
        )
        self.assertEqual(error.field_name, "schema")
        self.assertEqual(error.observed, "frp.m16.wrong.v1")
        self.assertEqual(
            error.expected,
            "frp.m16.fpga_preparation_execution_trace.v2.1.0",
        )

    def test_m27_artifact_id_mismatch_is_not_normalized(self) -> None:
        raw = _canonical_json_bytes(
            {
                "artifact_id": "m27-telemetry-semantics",
                "schema_version": "2.9.0",
            }
        )

        with self.assertRaises(PublishedIdentifierMismatchError) as context:
            _published_intake(1, raw_bytes=raw)

        self.assertEqual(context.exception.field_name, "artifact_id")
        self.assertEqual(
            context.exception.expected,
            "frp-m27-telemetry-semantics",
        )

    def test_m27_missing_schema_version_is_rejected(self) -> None:
        raw = _canonical_json_bytes(
            {"artifact_id": "frp-m27-telemetry-semantics"}
        )

        with self.assertRaises(PublishedIdentifierMismatchError) as context:
            _published_intake(1, raw_bytes=raw)

        self.assertEqual(context.exception.field_name, "schema_version")
        self.assertIsNone(context.exception.observed)

    def test_m27_schema_alias_is_rejected(self) -> None:
        raw = _canonical_json_bytes(
            {
                "artifact_id": "frp-m27-telemetry-semantics",
                "schema_version": "2.9.0",
                "schema": "m27-telemetry-semantics-v2.9.0",
            }
        )

        with self.assertRaisesRegex(
            M30PublishedMemberIntakeError,
            "must not declare a schema alias",
        ):
            _published_intake(1, raw_bytes=raw)

    def test_archive_digest_and_registry_revision_are_immutable_boundaries(
        self,
    ) -> None:
        cases = (
            (
                {"archive_sha256": "0" * 64},
                "archive digest mismatch",
            ),
            (
                {"registry_revision": "m30-alias"},
                "registry revision mismatch",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M30PublishedMemberIntakeError,
                    message,
                ):
                    _published_intake(0, **changes)

    def test_route_inventory_cannot_be_reordered_or_changed(self) -> None:
        registration, arguments = _intake_arguments(0)
        routes = arguments["routes"]
        self.assertIsInstance(routes, tuple)

        with patch(
            "parsers.m30_published_member_intake.registration_for_member_id",
            return_value=registration,
        ):
            with self.assertRaisesRegex(
                M30PublishedMemberIntakeError,
                "route inventory mismatch",
            ):
                PublishedMemberIntake(
                    **{**arguments, "routes": tuple(reversed(routes))}
                )

    def test_retained_member_path_must_match_registration(self) -> None:
        registration, arguments = _intake_arguments(0)
        retained = arguments["retained_member"]
        self.assertIsInstance(retained, RetainedArchiveMember)
        altered = RetainedArchiveMember(
            member=M30ArchiveMember(
                path="artifacts/alias.json",
                byte_length=retained.member.byte_length,
                raw_sha256=retained.member.raw_sha256,
            ),
            raw_bytes=retained.raw_bytes,
        )

        with patch(
            "parsers.m30_published_member_intake.registration_for_member_id",
            return_value=registration,
        ):
            with self.assertRaisesRegex(
                M30PublishedMemberIntakeError,
                "path differs from the registration",
            ):
                PublishedMemberIntake(
                    **{**arguments, "retained_member": altered}
                )

    def test_source_filename_must_match_registered_path(self) -> None:
        registration, arguments = _intake_arguments(0)
        retained = arguments["retained_member"]
        self.assertIsInstance(retained, RetainedArchiveMember)
        source = capture_source_bytes(
            retained.raw_bytes,
            source_filename="alias.json",
            source_path=registration.source_path,
        )

        with patch(
            "parsers.m30_published_member_intake.registration_for_member_id",
            return_value=registration,
        ):
            with self.assertRaisesRegex(
                M30PublishedMemberIntakeError,
                "source filename differs",
            ):
                PublishedMemberIntake(
                    **{
                        **arguments,
                        "source_artifact": source,
                        "parsed_artifact": parse_json_artifact(source),
                    }
                )

    def test_parsed_artifact_must_reference_captured_source(self) -> None:
        registration, arguments = _intake_arguments(0)
        retained = arguments["retained_member"]
        self.assertIsInstance(retained, RetainedArchiveMember)
        other_source = capture_source_bytes(
            retained.raw_bytes,
            source_filename=PurePosixPath(registration.source_path).name,
            source_path=registration.source_path,
        )

        with patch(
            "parsers.m30_published_member_intake.registration_for_member_id",
            return_value=registration,
        ):
            with self.assertRaisesRegex(
                M30PublishedMemberIntakeError,
                "must reference the captured source",
            ):
                PublishedMemberIntake(
                    **{
                        **arguments,
                        "parsed_artifact": parse_json_artifact(other_source),
                    }
                )

    def test_binding_and_evidence_cannot_be_forged(self) -> None:
        cases = (
            (
                {
                    "identifier_binding": (
                        PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS
                    )
                },
                "binding differs from the canonical",
            ),
            (
                {
                    "identifier_evidence": (
                        PublishedIdentifierEvidence(
                            field_name="schema",
                            value="frp.m16.alias.v1",
                        ),
                    )
                },
                "evidence differs from the canonical",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M30PublishedMemberIntakeError,
                    message,
                ):
                    _published_intake(0, **changes)

    def test_source_integrity_is_reverified_before_parsing_binding(self) -> None:
        registration, arguments = _intake_arguments(0)
        source = arguments["source_artifact"]
        object.__setattr__(source, "raw_bytes", b"{}")

        with patch(
            "parsers.m30_published_member_intake.registration_for_member_id",
            return_value=registration,
        ):
            with self.assertRaisesRegex(
                M30PublishedMemberIntakeError,
                "integrity verification failed",
            ):
                PublishedMemberIntake(**arguments)


@unittest.skipUnless(
    os.environ.get(_ARCHIVE_ENVIRONMENT_VARIABLE),
    f"{_ARCHIVE_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM30PublishedMemberIntegrationTests(unittest.TestCase):
    """Exercise the fixed 10,189,989-byte M30 archive when supplied."""

    @classmethod
    def setUpClass(cls) -> None:
        archive_path = os.environ[_ARCHIVE_ENVIRONMENT_VARIABLE]
        cls.batch = intake_m30_published_members(archive_path)

    def test_exact_archive_yields_complete_four_member_batch(self) -> None:
        self.assertEqual(
            self.batch.archive_validation.archive_sha256,
            FRP_M30_ARCHIVE_SHA256,
        )
        self.assertEqual(len(self.batch.members), 4)
        self.assertEqual(self.batch.total_byte_length, 18_097)
        self.assertEqual(self.batch.total_route_count, 7)

    def test_exact_member_order_and_raw_digests_match_m3(self) -> None:
        self.assertEqual(
            tuple(member.registration for member in self.batch.members),
            M30_PUBLISHED_MEMBER_REGISTRATIONS,
        )
        self.assertEqual(
            tuple(
                hashlib.sha256(member.raw_bytes).hexdigest()
                for member in self.batch.members
            ),
            tuple(
                registration.raw_sha256
                for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
            ),
        )

    def test_exact_identifier_fields_match_published_bytes(self) -> None:
        self.assertEqual(
            tuple(member.identifier_binding for member in self.batch.members),
            (
                PublishedIdentifierBinding.SCHEMA_FIELD,
                PublishedIdentifierBinding.ARTIFACT_ID_SCHEMA_VERSION_FIELDS,
                PublishedIdentifierBinding.SCHEMA_FIELD,
                PublishedIdentifierBinding.SCHEMA_FIELD,
            ),
        )
        self.assertEqual(
            self.batch.members[1].parsed_artifact.root["artifact_id"],
            "frp-m27-telemetry-semantics",
        )
        self.assertEqual(
            self.batch.members[1].parsed_artifact.root["schema_version"],
            "2.9.0",
        )

    def test_exact_mode_eligibility_is_four_two_one(self) -> None:
        self.assertEqual(
            len(
                self.batch.members_for_mode(
                    ObservatoryMode.ARTIFACT_AUDITOR
                )
            ),
            4,
        )
        self.assertEqual(
            len(
                self.batch.members_for_mode(
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                self.batch.members_for_mode(
                    ObservatoryMode.TRACE_EXPLORER
                )
            ),
            1,
        )

    def test_batch_mode_lookup_rejects_string_alias(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedMemberIntakeError,
            "mode must be ObservatoryMode",
        ):
            self.batch.members_for_mode("artifact_auditor")


if __name__ == "__main__":
    unittest.main()
