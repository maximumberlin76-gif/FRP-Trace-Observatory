"""Tests for the exact FRP M30 published-member routing registry."""

from __future__ import annotations

import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, replace

from artifact_auditor.m30_archive_intake import FRP_M30_ARCHIVE_SHA256
from artifact_auditor.m30_published_boundary_intake import (
    M28_COMPATIBILITY_REGISTRY_PATH,
    M28_UPSTREAM_CONTRACT_PATH,
    M29_ARTIFACT_REGISTRY_PATH,
    M29_CONSUMPTION_VECTORS_PATH,
    M29_DEMO_PACKAGE_PATH,
    M29_INTEGRATION_CONTRACT_PATH,
    M29_RELEASE_RECORDS_PATH,
    M30_ALIGNMENT_PATH,
    PublishedBoundaryDocument,
    PublishedBoundaryValidation,
    PublishedDemoMember,
)
from schemas.m30_published_registry import (
    M30_PUBLISHED_MEMBER_REGISTRATIONS,
    M30_PUBLISHED_REGISTRY_REVISION,
    M30PublishedRegistryError,
    PublishedMeasurementContour,
    PublishedMemberIdentityError,
    PublishedMemberRegistration,
    PublishedModeRoute,
    PublishedRegistryValidation,
    UnknownPublishedMemberError,
    registration_for_member_id,
    resolve_published_member,
    routes_for_published_member,
    validate_published_registry,
)
from schemas.registry import ObservatoryMode


_BOUNDARY_PATHS = (
    M28_UPSTREAM_CONTRACT_PATH,
    M28_COMPATIBILITY_REGISTRY_PATH,
    M29_INTEGRATION_CONTRACT_PATH,
    M29_ARTIFACT_REGISTRY_PATH,
    M29_DEMO_PACKAGE_PATH,
    M29_RELEASE_RECORDS_PATH,
    M29_CONSUMPTION_VECTORS_PATH,
    M30_ALIGNMENT_PATH,
)


def _published_member(
    registration: PublishedMemberRegistration,
) -> PublishedDemoMember:
    return PublishedDemoMember(
        member_id=registration.member_id,
        source_path=registration.source_path,
        schema_identifier=registration.schema_identifier,
        observatory_modes=tuple(
            mode.value for mode in registration.observatory_modes
        ),
        raw_sha256=registration.raw_sha256,
        byte_length=registration.byte_length,
    )


def _boundary() -> PublishedBoundaryValidation:
    documents = tuple(
        PublishedBoundaryDocument(
            path=path,
            schema=f"frp.test.boundary_document.v{index}",
            kind=f"boundary_document_{index}",
            raw_sha256=f"{index:064x}",
            byte_length=index,
        )
        for index, path in enumerate(_BOUNDARY_PATHS, start=1)
    )
    return PublishedBoundaryValidation(
        archive_sha256=FRP_M30_ARCHIVE_SHA256,
        documents=documents,
        supported_artifact_count=97,
        demo_members=tuple(
            _published_member(registration)
            for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
        ),
        accepted_vector_count=4,
        rejected_vector_count=8,
    )


class PublishedMemberRegistrationTests(unittest.TestCase):
    """Exercise one immutable published-member registration."""

    def test_registration_retains_exact_dispatch_identity(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]

        self.assertEqual(
            registration.dispatch_key,
            (
                "m16-fpga-preparation-execution-trace",
                "frp.m16.fpga_preparation_execution_trace.v2.1.0",
                "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f",
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(registration, "byte_length", 1)

    def test_compatibility_key_is_release_independent(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        other_release = replace(
            registration,
            upstream_release="frp-v99.0.0-test",
        )

        self.assertEqual(
            other_release.compatibility_key,
            registration.compatibility_key,
        )
        self.assertEqual(other_release.dispatch_key, registration.dispatch_key)

    def test_text_fields_require_machine_tokens(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        invalid_changes = (
            {"member_id": "member alias"},
            {"schema_identifier": " schema"},
            {"upstream_release": "FRP v2.1.0"},
        )

        for changes in invalid_changes:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M30PublishedRegistryError,
                    "must be nonempty without whitespace",
                ):
                    replace(registration, **changes)

    def test_source_path_requires_safe_relative_posix_form(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        invalid_paths = (
            "/artifacts/member.json",
            "artifacts\\member.json",
            "artifacts//member.json",
            "artifacts/../member.json",
            "artifacts/./member.json",
        )

        for invalid_path in invalid_paths:
            with self.subTest(invalid_path=invalid_path):
                with self.assertRaisesRegex(
                    M30PublishedRegistryError,
                    "source_path must be a",
                ):
                    replace(registration, source_path=invalid_path)

    def test_measurement_contour_requires_published_enum(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "measurement_contour must be PublishedMeasurementContour",
        ):
            replace(
                registration,
                measurement_contour=(
                    "m16_fpga_preparation_execution"
                ),
            )

    def test_modes_require_nonempty_unique_enum_tuple(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        invalid_modes = (
            [ObservatoryMode.ARTIFACT_AUDITOR],
            (),
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.ARTIFACT_AUDITOR,
            ),
            ("artifact_auditor",),
        )

        for modes in invalid_modes:
            with self.subTest(modes=modes):
                with self.assertRaises(M30PublishedRegistryError):
                    replace(registration, observatory_modes=modes)

    def test_byte_length_requires_positive_non_boolean_integer(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]

        for invalid_length in (0, -1, True, 1.5):
            with self.subTest(invalid_length=invalid_length):
                with self.assertRaisesRegex(
                    M30PublishedRegistryError,
                    "byte_length must be a positive integer",
                ):
                    replace(registration, byte_length=invalid_length)

    def test_digests_require_exact_lowercase_sha256(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "raw_sha256 must be lowercase",
        ):
            replace(registration, raw_sha256="A" * 64)
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "compatibility_key must be lowercase",
        ):
            replace(registration, compatibility_key="0" * 63)

    def test_compatibility_key_cannot_be_forged(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "compatibility_key must use only",
        ):
            replace(registration, compatibility_key="0" * 64)


class PublishedRegistryInventoryTests(unittest.TestCase):
    """Exercise the exact four-member M30 inventory."""

    def test_inventory_has_exact_revision_order_and_keys(self) -> None:
        registrations = M30_PUBLISHED_MEMBER_REGISTRATIONS

        self.assertEqual(
            M30_PUBLISHED_REGISTRY_REVISION,
            "m30-published-boundary-v1",
        )
        self.assertEqual(
            tuple(registration.member_id for registration in registrations),
            (
                "m16-fpga-preparation-execution-trace",
                "m27-telemetry-semantics",
                "m28-trace-observatory-upstream-contract",
                "m28-hierarchical-scaling-contract",
            ),
        )
        self.assertEqual(len(registrations), 4)
        self.assertEqual(
            len({registration.dispatch_key for registration in registrations}),
            4,
        )

    def test_inventory_retains_exact_release_and_contour_mapping(self) -> None:
        mapping = tuple(
            (
                registration.upstream_release,
                registration.measurement_contour,
            )
            for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
        )

        self.assertEqual(
            mapping,
            (
                (
                    "frp-v2.1.0-m19",
                    PublishedMeasurementContour.M16_FPGA_PREPARATION_EXECUTION,
                ),
                (
                    "frp-v2.9.0-m27",
                    PublishedMeasurementContour.M27_LONG_RUN_TELEMETRY_SEMANTICS,
                ),
                (
                    "frp-v3.0.0-m28",
                    PublishedMeasurementContour.M28_UPSTREAM_INTEGRATION_CONTRACT,
                ),
                (
                    "frp-v3.0.0-m28",
                    PublishedMeasurementContour.M28_HIERARCHICAL_SCALING_QUALIFICATION,
                ),
            ),
        )

    def test_inventory_retains_exact_lengths_and_digests(self) -> None:
        identities = tuple(
            (
                registration.byte_length,
                registration.raw_sha256,
                registration.compatibility_key,
            )
            for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
        )

        self.assertEqual(
            identities,
            (
                (
                    9013,
                    "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f",
                    "a221aecb0d24518c8a2dd562405dad9b47ff53be5b4b2f6a972b6ecedc066ff2",
                ),
                (
                    2789,
                    "813ae5c66ceaddabc77734d44f1ebf971ca3bd7e11c1984e2e0c8f0204dfd1bc",
                    "06c74930ea2d928fa07c0f2ca86ee886b67ce6846cdea855dba66acff0bb82b6",
                ),
                (
                    2735,
                    "556cd2921014d78184dad625438e053632c2650164f95787f39a6fc871b4a3f0",
                    "c5d60d4b37f669cc650b56be99bf61eb42ef837491e50cb9081cebc94cea14b0",
                ),
                (
                    3560,
                    "13f85ac82b63d0191157bd2cfa04dd37358ef66d8e69bdb96bb1892abb77dbae",
                    "737e7e29b051a0928575508e506d31b0b275933a490f161b16de0264d4d01746",
                ),
            ),
        )

    def test_inventory_routes_only_to_existing_modes(self) -> None:
        route_counts = Counter(
            mode
            for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS
            for mode in registration.observatory_modes
        )

        self.assertEqual(
            route_counts,
            {
                ObservatoryMode.ARTIFACT_AUDITOR: 4,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER: 2,
                ObservatoryMode.TRACE_EXPLORER: 1,
            },
        )


class PublishedMemberResolutionTests(unittest.TestCase):
    """Exercise exact identity resolution without aliases."""

    def test_each_exact_member_resolves_to_its_registration(self) -> None:
        for registration in M30_PUBLISHED_MEMBER_REGISTRATIONS:
            with self.subTest(member_id=registration.member_id):
                member = _published_member(registration)
                self.assertIs(
                    registration_for_member_id(registration.member_id),
                    registration,
                )
                self.assertIs(resolve_published_member(member), registration)

    def test_unknown_ids_and_aliases_are_rejected(self) -> None:
        exact_id = M30_PUBLISHED_MEMBER_REGISTRATIONS[0].member_id

        for member_id in ("unknown", exact_id.upper(), exact_id + " "):
            with self.subTest(member_id=member_id):
                with self.assertRaises(UnknownPublishedMemberError):
                    registration_for_member_id(member_id)
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "member_id must be a string",
        ):
            registration_for_member_id(None)

    def test_member_object_type_is_exact(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "member must be PublishedDemoMember",
        ):
            resolve_published_member({})

    def test_known_member_rejects_every_identity_mismatch(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        member = _published_member(registration)
        other = M30_PUBLISHED_MEMBER_REGISTRATIONS[1]
        changes = (
            {"source_path": other.source_path},
            {"schema_identifier": "frp.m16.alias.v2.1.0"},
            {"observatory_modes": ("artifact_auditor",)},
            {"raw_sha256": "0" * 64},
            {"byte_length": registration.byte_length + 1},
        )

        for change in changes:
            field = next(iter(change))
            with self.subTest(field=field):
                with self.assertRaises(PublishedMemberIdentityError) as caught:
                    resolve_published_member(replace(member, **change))
                self.assertEqual(caught.exception.field, field)

    def test_routes_follow_only_the_exact_member_declaration(self) -> None:
        expected_modes = (
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ObservatoryMode.TRACE_EXPLORER,
            ),
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
            ),
            (ObservatoryMode.ARTIFACT_AUDITOR,),
            (ObservatoryMode.ARTIFACT_AUDITOR,),
        )

        for registration, modes in zip(
            M30_PUBLISHED_MEMBER_REGISTRATIONS,
            expected_modes,
            strict=True,
        ):
            with self.subTest(member_id=registration.member_id):
                routes = routes_for_published_member(
                    _published_member(registration)
                )
                self.assertEqual(
                    tuple(route.mode for route in routes),
                    modes,
                )
                self.assertTrue(
                    all(route.registration is registration for route in routes)
                )


class PublishedModeRouteTests(unittest.TestCase):
    """Exercise immutable and declared mode routes."""

    def test_route_is_frozen(self) -> None:
        registration = M30_PUBLISHED_MEMBER_REGISTRATIONS[0]
        route = PublishedModeRoute(
            registration=registration,
            mode=ObservatoryMode.ARTIFACT_AUDITOR,
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(route, "mode", ObservatoryMode.TRACE_EXPLORER)

    def test_route_requires_exact_types_and_declared_mode(self) -> None:
        auditor_only = M30_PUBLISHED_MEMBER_REGISTRATIONS[2]

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "route registration must be",
        ):
            PublishedModeRoute(
                registration=None,
                mode=ObservatoryMode.ARTIFACT_AUDITOR,
            )
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "route mode must be ObservatoryMode",
        ):
            PublishedModeRoute(
                registration=auditor_only,
                mode="artifact_auditor",
            )
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "route mode is not declared",
        ):
            PublishedModeRoute(
                registration=auditor_only,
                mode=ObservatoryMode.TRACE_EXPLORER,
            )


class PublishedRegistryValidationTests(unittest.TestCase):
    """Exercise complete M2-to-M3 validation and routing evidence."""

    def test_exact_boundary_produces_complete_routing_evidence(self) -> None:
        result = validate_published_registry(_boundary())

        self.assertEqual(result.archive_sha256, FRP_M30_ARCHIVE_SHA256)
        self.assertEqual(
            result.registry_revision,
            M30_PUBLISHED_REGISTRY_REVISION,
        )
        self.assertEqual(
            result.registrations,
            M30_PUBLISHED_MEMBER_REGISTRATIONS,
        )
        self.assertEqual(len(result.routes), 7)
        self.assertEqual(result.artifact_auditor_route_count, 4)
        self.assertEqual(result.ternary_transition_visualizer_route_count, 2)
        self.assertEqual(result.trace_explorer_route_count, 1)

    def test_mode_views_have_exact_member_inventory(self) -> None:
        result = validate_published_registry(_boundary())

        expected = {
            ObservatoryMode.ARTIFACT_AUDITOR: (
                "m16-fpga-preparation-execution-trace",
                "m27-telemetry-semantics",
                "m28-trace-observatory-upstream-contract",
                "m28-hierarchical-scaling-contract",
            ),
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER: (
                "m16-fpga-preparation-execution-trace",
                "m27-telemetry-semantics",
            ),
            ObservatoryMode.TRACE_EXPLORER: (
                "m16-fpga-preparation-execution-trace",
            ),
        }

        for mode, member_ids in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(
                    tuple(
                        route.registration.member_id
                        for route in result.routes_for_mode(mode)
                    ),
                    member_ids,
                )

    def test_mode_view_rejects_non_enum(self) -> None:
        result = validate_published_registry(_boundary())

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "mode must be ObservatoryMode",
        ):
            result.routes_for_mode("artifact_auditor")

    def test_validation_result_is_frozen(self) -> None:
        result = validate_published_registry(_boundary())

        with self.assertRaises(FrozenInstanceError):
            setattr(result, "trace_explorer_route_count", 2)

    def test_validation_rejects_non_boundary_input(self) -> None:
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "boundary must be PublishedBoundaryValidation",
        ):
            validate_published_registry(None)

    def test_validation_result_rejects_route_inventory_mutation(self) -> None:
        result = validate_published_registry(_boundary())
        mutated_routes = result.routes[:-1] + (result.routes[0],)

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "route inventory mismatch",
        ):
            replace(result, routes=mutated_routes)

    def test_validation_result_rejects_count_mutation(self) -> None:
        result = validate_published_registry(_boundary())

        invalid_counts = (
            {"artifact_auditor_route_count": 3},
            {"ternary_transition_visualizer_route_count": 3},
            {"trace_explorer_route_count": 2},
        )
        for change in invalid_counts:
            with self.subTest(change=change):
                with self.assertRaises(M30PublishedRegistryError):
                    replace(result, **change)

    def test_validation_result_rejects_revision_and_archive_mutation(
        self,
    ) -> None:
        result = validate_published_registry(_boundary())

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "archive digest mismatch",
        ):
            replace(result, archive_sha256="0" * 64)
        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "revision mismatch",
        ):
            replace(result, registry_revision="alias")

    def test_validation_result_requires_exact_registration_inventory(
        self,
    ) -> None:
        result = validate_published_registry(_boundary())

        with self.assertRaisesRegex(
            M30PublishedRegistryError,
            "registration inventory mismatch",
        ):
            PublishedRegistryValidation(
                archive_sha256=result.archive_sha256,
                registry_revision=result.registry_revision,
                registrations=tuple(reversed(result.registrations)),
                routes=result.routes,
                artifact_auditor_route_count=4,
                ternary_transition_visualizer_route_count=2,
                trace_explorer_route_count=1,
            )


if __name__ == "__main__":
    unittest.main()
