"""Tests for exact read-only dispatch of verified M30 members."""

from __future__ import annotations

import os
import unittest
from dataclasses import FrozenInstanceError, replace

from parsers.artifact_dispatch import (
    RegistrationStatus,
    dispatch_artifact,
)
from parsers.m30_published_dispatch import (
    M30PublishedDispatchError,
    PublishedModeDispatch,
    build_m30_published_dispatch_batch,
    dispatch_m30_published_members,
)
from parsers.source_artifact import capture_source_bytes
from schemas.m30_published_registry import (
    M30_PUBLISHED_MEMBER_REGISTRATIONS,
    PublishedModeRoute,
)
from schemas.registry import ObservatoryMode
from tests.test_m30_published_member_intake import _published_intake


_ARCHIVE_ENVIRONMENT_VARIABLE = "FRP_M30_ARCHIVE_PATH"


class PublishedModeDispatchTests(unittest.TestCase):
    """Exercise one exact M4-member-to-mode envelope."""

    def test_create_preserves_exact_m4_objects_and_raw_bytes(self) -> None:
        member = _published_intake(0)
        route = member.routes[0]

        dispatch = PublishedModeDispatch.create(member, route)

        self.assertIs(dispatch.member, member)
        self.assertIs(dispatch.route, route)
        self.assertIs(dispatch.source_artifact, member.source_artifact)
        self.assertIs(dispatch.parsed_artifact, member.parsed_artifact)
        self.assertEqual(dispatch.raw_bytes, member.raw_bytes)
        self.assertEqual(dispatch.member_id, member.member_id)
        self.assertIs(dispatch.mode, ObservatoryMode.ARTIFACT_AUDITOR)

    def test_dispatch_key_retains_member_mode_and_raw_digest(self) -> None:
        member = _published_intake(0)
        dispatch = PublishedModeDispatch.create(
            member,
            member.routes[2],
        )

        self.assertEqual(
            dispatch.dispatch_key,
            (
                "m16-fpga-preparation-execution-trace",
                ObservatoryMode.TRACE_EXPLORER,
                member.registration.raw_sha256,
            ),
        )

    def test_m27_dispatch_retains_composite_identifier_object(self) -> None:
        member = _published_intake(1)
        dispatch = PublishedModeDispatch.create(
            member,
            member.routes[1],
        )

        self.assertIs(
            dispatch.mode,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
        )
        self.assertEqual(
            dispatch.parsed_artifact.root["artifact_id"],
            "frp-m27-telemetry-semantics",
        )
        self.assertEqual(
            dispatch.parsed_artifact.root["schema_version"],
            "2.9.0",
        )
        self.assertNotIn("schema", dispatch.parsed_artifact.root)

    def test_dispatch_is_frozen(self) -> None:
        member = _published_intake(2)
        dispatch = PublishedModeDispatch.create(member, member.routes[0])

        with self.assertRaises(FrozenInstanceError):
            setattr(dispatch, "dispatch_sha256", "0" * 64)

    def test_create_requires_exact_input_types(self) -> None:
        member = _published_intake(0)

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "member must be PublishedMemberIntake",
        ):
            PublishedModeDispatch.create("member", member.routes[0])
        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "route must be PublishedModeRoute",
        ):
            PublishedModeDispatch.create(member, "artifact_auditor")

    def test_equal_but_reconstructed_route_is_rejected(self) -> None:
        member = _published_intake(0)
        reconstructed = PublishedModeRoute(
            registration=member.registration,
            mode=member.routes[0].mode,
        )
        self.assertEqual(reconstructed, member.routes[0])
        self.assertIsNot(reconstructed, member.routes[0])

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "not exact M4 member route evidence",
        ):
            PublishedModeDispatch.create(member, reconstructed)

    def test_route_from_another_registration_is_rejected(self) -> None:
        member = _published_intake(0)
        route = PublishedModeRoute(
            registration=M30_PUBLISHED_MEMBER_REGISTRATIONS[0],
            mode=ObservatoryMode.ARTIFACT_AUDITOR,
        )

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "not the M4 member registration",
        ):
            PublishedModeDispatch.create(member, route)

    def test_dispatch_digest_format_and_identity_are_enforced(self) -> None:
        member = _published_intake(0)
        dispatch = PublishedModeDispatch.create(member, member.routes[0])
        cases = (
            ("A" * 64, "lowercase hexadecimal SHA-256"),
            ("0" * 64, "does not bind the exact member and route"),
        )

        for digest, message in cases:
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(
                    M30PublishedDispatchError,
                    message,
                ):
                    replace(dispatch, dispatch_sha256=digest)

    def test_route_change_cannot_reuse_a_dispatch_digest(self) -> None:
        member = _published_intake(0)
        auditor = PublishedModeDispatch.create(member, member.routes[0])

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "does not bind the exact member and route",
        ):
            replace(auditor, route=member.routes[1])

    def test_source_integrity_is_rechecked_at_dispatch_boundary(self) -> None:
        member = _published_intake(0)
        object.__setattr__(member.source_artifact, "raw_bytes", b"{}")

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "source integrity verification failed",
        ):
            PublishedModeDispatch.create(member, member.routes[0])

    def test_parsed_object_must_remain_bound_to_m4_source(self) -> None:
        member = _published_intake(0)
        other_source = capture_source_bytes(
            member.raw_bytes,
            source_filename=member.source_artifact.source_filename,
            source_path=member.source_artifact.source_path,
        )
        object.__setattr__(
            member.parsed_artifact,
            "source_artifact",
            other_source,
        )

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "parsed object differs from the M4 source",
        ):
            PublishedModeDispatch.create(member, member.routes[0])


class PublishedDispatchBuilderGuardTests(unittest.TestCase):
    """Exercise public M5 builder type boundaries."""

    def test_builder_requires_complete_m4_batch(self) -> None:
        for value in (None, (), "batch"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M30PublishedDispatchError,
                    "intake_batch must be PublishedMemberIntakeBatch",
                ):
                    build_m30_published_dispatch_batch(value)


@unittest.skipUnless(
    os.environ.get(_ARCHIVE_ENVIRONMENT_VARIABLE),
    f"{_ARCHIVE_ENVIRONMENT_VARIABLE} is not configured",
)
class ExactM30PublishedDispatchIntegrationTests(unittest.TestCase):
    """Exercise all seven envelopes against the exact M30 archive."""

    @classmethod
    def setUpClass(cls) -> None:
        archive_path = os.environ[_ARCHIVE_ENVIRONMENT_VARIABLE]
        cls.batch = dispatch_m30_published_members(archive_path)

    def test_exact_dispatch_inventory_order_is_three_two_one_one(self) -> None:
        self.assertEqual(self.batch.total_dispatch_count, 7)
        self.assertEqual(
            tuple(
                (dispatch.member_id, dispatch.mode)
                for dispatch in self.batch.dispatches
            ),
            (
                (
                    "m16-fpga-preparation-execution-trace",
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    "m16-fpga-preparation-execution-trace",
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ),
                (
                    "m16-fpga-preparation-execution-trace",
                    ObservatoryMode.TRACE_EXPLORER,
                ),
                (
                    "m27-telemetry-semantics",
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    "m27-telemetry-semantics",
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ),
                (
                    "m28-trace-observatory-upstream-contract",
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    "m28-hierarchical-scaling-contract",
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
            ),
        )

    def test_exact_dispatch_digests_are_stable_and_unique(self) -> None:
        self.assertEqual(
            tuple(
                dispatch.dispatch_sha256
                for dispatch in self.batch.dispatches
            ),
            (
                "28e808f6b49cf9123082a9ff1a9045a02b54071eff2431e1c38042fec791d4a1",
                "204c63f20db49a7d946b0963058db148fe43bb715c353c74ac4f6b203e4e792f",
                "55e9c53f55cc5507e33271bfcdd2a48c751fd710b9fe8f9df972fc1c308f69b2",
                "9c5191fec35bcde4aeb6faca6e8476bc7cb5a4e5ff11f6b5359d11b55db71d8c",
                "b17c84a8adc66205f75d8ae81053b181ba585647e8a5e29764f0d6ec062d4d21",
                "9fb6445250f6e29879a2433e9526d9f744bc2a3f10ee0a00be551e39cde4bdeb",
                "6b923c5d9e8a98130eef848ce43818f3ff76b44a9e9c3426ef6d681265c548d1",
            ),
        )

    def test_exact_mode_counts_are_four_two_one(self) -> None:
        self.assertEqual(
            len(
                self.batch.dispatches_for_mode(
                    ObservatoryMode.ARTIFACT_AUDITOR
                )
            ),
            4,
        )
        self.assertEqual(
            len(
                self.batch.dispatches_for_mode(
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                self.batch.dispatches_for_mode(
                    ObservatoryMode.TRACE_EXPLORER
                )
            ),
            1,
        )

    def test_dispatch_objects_retain_exact_m4_evidence_identity(self) -> None:
        expected_pairs = tuple(
            (member, route)
            for member in self.batch.intake_batch.members
            for route in member.routes
        )

        for dispatch, (member, route) in zip(
            self.batch.dispatches,
            expected_pairs,
            strict=True,
        ):
            self.assertIs(dispatch.member, member)
            self.assertIs(dispatch.route, route)
            self.assertIs(dispatch.source_artifact, member.source_artifact)
            self.assertIs(dispatch.parsed_artifact, member.parsed_artifact)

    def test_exact_member_and_mode_resolution_has_no_aliases(self) -> None:
        dispatch = self.batch.dispatch_for(
            "m16-fpga-preparation-execution-trace",
            ObservatoryMode.TRACE_EXPLORER,
        )
        self.assertIs(dispatch.mode, ObservatoryMode.TRACE_EXPLORER)

        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "unknown published dispatch member",
        ):
            self.batch.dispatches_for_member("m16-trace-alias")
        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "is not eligible",
        ):
            self.batch.dispatch_for(
                "m28-hierarchical-scaling-contract",
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            )

    def test_mode_and_member_lookup_require_exact_types(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "mode must be ObservatoryMode",
        ):
            self.batch.dispatches_for_mode("artifact_auditor")
        with self.assertRaisesRegex(
            M30PublishedDispatchError,
            "member_id must be a string",
        ):
            self.batch.dispatches_for_member(27)

    def test_m27_is_not_forced_through_legacy_schema_only_dispatch(self) -> None:
        m27 = self.batch.intake_batch.members[1]
        legacy_result = dispatch_artifact(m27.source_artifact)

        self.assertIs(
            legacy_result.registration.status,
            RegistrationStatus.MISSING_IDENTIFIER,
        )
        self.assertEqual(
            len(self.batch.dispatches_for_member(m27.member_id)),
            2,
        )

    def test_repeated_exact_build_has_byte_stable_dispatch_digests(self) -> None:
        archive_path = os.environ[_ARCHIVE_ENVIRONMENT_VARIABLE]
        repeated = dispatch_m30_published_members(archive_path)

        self.assertEqual(
            tuple(
                dispatch.dispatch_sha256
                for dispatch in repeated.dispatches
            ),
            tuple(
                dispatch.dispatch_sha256
                for dispatch in self.batch.dispatches
            ),
        )


if __name__ == "__main__":
    unittest.main()
