"""Tests for the exact FRP M31 published-document routing registry."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from artifact_auditor.m31_published_boundary_intake import (
    FRP_M30_ARCHIVE_PATH,
    M31_PUBLISHED_DOCUMENT_IDENTITIES,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedBoundaryError,
    M31PublishedDocumentRole,
)
from schemas.m31_published_registry import (
    M31_PUBLISHED_DOCUMENT_REGISTRATIONS,
    M31PublishedDocumentRegistration,
    M31PublishedMeasurementContour,
    M31PublishedModeRoute,
    M31PublishedRegistryError,
    registration_for_m31_role,
    resolve_m31_published_document,
    routes_for_m31_document,
    validate_m31_document_registry,
    validate_m31_published_registry,
)
from schemas.registry import ObservatoryMode


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flip_one_byte(path: Path) -> None:
    raw = bytearray(path.read_bytes())
    if not raw:
        raise AssertionError(f"cannot tamper with empty source: {path}")
    raw[len(raw) // 2] ^= 1
    path.write_bytes(raw)


class M31PublishedRegistrationContractTests(unittest.TestCase):
    """Exercise the four immutable M31 document registrations."""

    def test_inventory_has_exact_roles_contours_modes_and_keys(self) -> None:
        registrations = M31_PUBLISHED_DOCUMENT_REGISTRATIONS

        self.assertEqual(
            tuple(registration.role for registration in registrations),
            tuple(M31PublishedDocumentRole),
        )
        self.assertEqual(
            tuple(
                registration.measurement_contour
                for registration in registrations
            ),
            (
                M31PublishedMeasurementContour.FORMAL_SCHEMA_DEFINITION,
                M31PublishedMeasurementContour
                .PHASE_INTERFERENCE_ACTIVE_ZERO_THERMAL_EVIDENCE,
                M31PublishedMeasurementContour.PUBLICATION_MANIFEST,
                M31PublishedMeasurementContour.PUBLICATION_QUALIFICATION,
            ),
        )
        self.assertEqual(
            tuple(
                registration.observatory_modes
                for registration in registrations
            ),
            (
                (ObservatoryMode.ARTIFACT_AUDITOR,),
                (
                    ObservatoryMode.ARTIFACT_AUDITOR,
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                    ObservatoryMode.TRACE_EXPLORER,
                ),
                (ObservatoryMode.ARTIFACT_AUDITOR,),
                (ObservatoryMode.ARTIFACT_AUDITOR,),
            ),
        )
        self.assertEqual(
            tuple(
                registration.compatibility_key
                for registration in registrations
            ),
            (
                "0a3b92c08456517bd03e5c49ed683d490869688e6a2039f021228fc8db66b8b2",
                "ac1a9fae03831d912e1b1abf42dd73713b506a10b28c7b65041cca2e2b56e296",
                "8263f4f97b459fcdb5defbe2d9881bd1b7b0c52a3a94830dfb5cb16a982bc59e",
                "594bd40bba735ff9572cde8e6cc38cfcbb184748aaa0ce5f394a38d24737187a",
            ),
        )
        self.assertEqual(len(registrations), 4)
        self.assertEqual(
            len({registration.dispatch_key for registration in registrations}),
            4,
        )

    def test_registration_delegates_only_exact_identity_fields(self) -> None:
        for registration, identity in zip(
            M31_PUBLISHED_DOCUMENT_REGISTRATIONS,
            M31_PUBLISHED_DOCUMENT_IDENTITIES,
            strict=True,
        ):
            with self.subTest(role=identity.role):
                self.assertIs(registration.document_identity, identity)
                self.assertEqual(registration.source_path, identity.source_path)
                self.assertEqual(
                    registration.identifier_field,
                    identity.identifier_field,
                )
                self.assertEqual(
                    registration.identifier_value,
                    identity.identifier_value,
                )
                self.assertEqual(registration.artifact_kind, identity.kind)
                self.assertEqual(registration.byte_length, identity.byte_length)
                self.assertEqual(registration.raw_sha256, identity.raw_sha256)
                self.assertEqual(registration.upstream_milestone, "M31")
                self.assertEqual(registration.upstream_version, "1.0.0")

    def test_registration_is_frozen_and_requires_canonical_identity(
        self,
    ) -> None:
        registration = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[0]

        with self.assertRaises(FrozenInstanceError):
            registration.upstream_milestone = "M32"
        cloned_identity = replace(registration.document_identity)
        self.assertEqual(cloned_identity, registration.document_identity)
        self.assertIsNot(cloned_identity, registration.document_identity)
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "canonical M31 identity",
        ):
            replace(registration, document_identity=cloned_identity)
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "document_identity must be",
        ):
            replace(registration, document_identity=None)

    def test_measurement_contour_cannot_be_aliased_or_reassigned(
        self,
    ) -> None:
        registration = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[1]

        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "must be M31PublishedMeasurementContour",
        ):
            replace(
                registration,
                measurement_contour=(
                    "phase_interference_active_zero_thermal_evidence"
                ),
            )
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "does not match document role",
        ):
            replace(
                registration,
                measurement_contour=(
                    M31PublishedMeasurementContour.PUBLICATION_MANIFEST
                ),
            )

    def test_mode_tuple_cannot_be_aliased_narrowed_or_expanded(self) -> None:
        schema = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[0]
        evidence = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[1]
        invalid = (
            (
                schema,
                [ObservatoryMode.ARTIFACT_AUDITOR],
                "must be a tuple",
            ),
            (schema, ("artifact_auditor",), "must contain"),
            (
                schema,
                (
                    ObservatoryMode.ARTIFACT_AUDITOR,
                    ObservatoryMode.TRACE_EXPLORER,
                ),
                "do not match document role",
            ),
            (
                evidence,
                (ObservatoryMode.ARTIFACT_AUDITOR,),
                "do not match document role",
            ),
        )
        for registration, modes, message in invalid:
            with self.subTest(role=registration.role, modes=modes):
                with self.assertRaisesRegex(
                    M31PublishedRegistryError,
                    message,
                ):
                    replace(registration, observatory_modes=modes)

    def test_compatibility_key_rejects_format_and_semantic_forgery(
        self,
    ) -> None:
        registration = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[0]

        for invalid_key, message in (
            ("A" * 64, "lowercase hexadecimal"),
            ("0" * 63, "lowercase hexadecimal"),
            ("0" * 64, "must use only role"),
        ):
            with self.subTest(invalid_key=invalid_key):
                with self.assertRaisesRegex(
                    M31PublishedRegistryError,
                    message,
                ):
                    replace(registration, compatibility_key=invalid_key)

    def test_upstream_milestone_and_version_are_fixed(self) -> None:
        registration = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[0]

        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "upstream_milestone must be M31",
        ):
            replace(registration, upstream_milestone="M30")
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "upstream_version must be 1.0.0",
        ):
            replace(registration, upstream_version="1.0.1")

    def test_role_lookup_requires_exact_enum_without_aliases(self) -> None:
        for role, expected in zip(
            M31PublishedDocumentRole,
            M31_PUBLISHED_DOCUMENT_REGISTRATIONS,
            strict=True,
        ):
            with self.subTest(role=role):
                self.assertIs(registration_for_m31_role(role), expected)

        for alias in ("evidence", "EVIDENCE", None):
            with self.subTest(alias=alias):
                with self.assertRaisesRegex(
                    M31PublishedRegistryError,
                    "role must be M31PublishedDocumentRole",
                ):
                    registration_for_m31_role(alias)


class M31PublishedRouteContractTests(unittest.TestCase):
    """Exercise exact routes into the three existing Observatory modes."""

    def test_routes_follow_only_each_registration_declaration(self) -> None:
        expected_modes = (
            (ObservatoryMode.ARTIFACT_AUDITOR,),
            (
                ObservatoryMode.ARTIFACT_AUDITOR,
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ObservatoryMode.TRACE_EXPLORER,
            ),
            (ObservatoryMode.ARTIFACT_AUDITOR,),
            (ObservatoryMode.ARTIFACT_AUDITOR,),
        )

        for registration, modes in zip(
            M31_PUBLISHED_DOCUMENT_REGISTRATIONS,
            expected_modes,
            strict=True,
        ):
            with self.subTest(role=registration.role):
                routes = tuple(
                    M31PublishedModeRoute(registration, mode)
                    for mode in registration.observatory_modes
                )
                self.assertEqual(
                    tuple(route.mode for route in routes),
                    modes,
                )
                self.assertTrue(
                    all(route.registration is registration for route in routes)
                )

    def test_route_is_frozen_and_rejects_aliases_or_undeclared_modes(
        self,
    ) -> None:
        auditor_only = M31_PUBLISHED_DOCUMENT_REGISTRATIONS[0]
        route = M31PublishedModeRoute(
            auditor_only,
            ObservatoryMode.ARTIFACT_AUDITOR,
        )

        with self.assertRaises(FrozenInstanceError):
            route.mode = ObservatoryMode.TRACE_EXPLORER
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "route registration must be",
        ):
            M31PublishedModeRoute(None, ObservatoryMode.ARTIFACT_AUDITOR)
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "route mode must be ObservatoryMode",
        ):
            M31PublishedModeRoute(auditor_only, "artifact_auditor")
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "route mode is not declared",
        ):
            M31PublishedModeRoute(
                auditor_only,
                ObservatoryMode.TRACE_EXPLORER,
            )


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not set",
)
class ExactM31PublishedRegistryIntegrationTests(unittest.TestCase):
    """Exercise exact routing and adversarial failures against FRP M31."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.result = validate_m31_published_registry(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        cls.boundary_paths = tuple(
            dict.fromkeys(
                [
                    *(
                        identity.source_path
                        for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
                    ),
                    *(
                        source.source_path
                        for source in cls.result.boundary.provenance_sources
                    ),
                ]
            )
        )
        if FRP_M30_ARCHIVE_PATH not in cls.boundary_paths:
            raise AssertionError("M30 archive is absent from boundary paths")

    @classmethod
    @contextmanager
    def boundary_copy(cls) -> Iterator[Path]:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "upstream"
            root.mkdir()
            for relative in cls.boundary_paths:
                source = cls.upstream_root.joinpath(*relative.split("/"))
                target = root.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            yield root

    def test_exact_boundary_produces_complete_registry_evidence(self) -> None:
        self.assertEqual(
            self.result.registry_revision,
            M31_PUBLISHED_REGISTRY_REVISION,
        )
        self.assertEqual(
            self.result.registrations,
            M31_PUBLISHED_DOCUMENT_REGISTRATIONS,
        )
        self.assertEqual(len(self.result.routes), 6)
        self.assertEqual(self.result.artifact_auditor_route_count, 4)
        self.assertEqual(
            self.result.ternary_transition_visualizer_route_count,
            1,
        )
        self.assertEqual(self.result.trace_explorer_route_count, 1)
        self.assertEqual(self.result.boundary.total_document_bytes, 43_801)

    def test_mode_views_have_exact_document_roles(self) -> None:
        expected = {
            ObservatoryMode.ARTIFACT_AUDITOR: tuple(
                M31PublishedDocumentRole
            ),
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER: (
                M31PublishedDocumentRole.EVIDENCE,
            ),
            ObservatoryMode.TRACE_EXPLORER: (
                M31PublishedDocumentRole.EVIDENCE,
            ),
        }

        for mode, roles in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(
                    tuple(
                        route.registration.role
                        for route in self.result.routes_for_mode(mode)
                    ),
                    roles,
                )

    def test_exact_documents_resolve_to_canonical_registrations(self) -> None:
        for document, registration in zip(
            self.result.boundary.documents,
            M31_PUBLISHED_DOCUMENT_REGISTRATIONS,
            strict=True,
        ):
            with self.subTest(role=registration.role):
                self.assertIs(
                    resolve_m31_published_document(document),
                    registration,
                )
                routes = routes_for_m31_document(document)
                self.assertEqual(
                    tuple(route.mode for route in routes),
                    registration.observatory_modes,
                )
                self.assertTrue(
                    all(route.registration is registration for route in routes)
                )

    def test_validation_guards_reject_aliases_and_non_boundary_input(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "document must be M31PublishedDocument",
        ):
            resolve_m31_published_document(None)
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "boundary must be M31PublishedBoundaryValidation",
        ):
            validate_m31_document_registry(None)
        with self.assertRaisesRegex(
            M31PublishedRegistryError,
            "mode must be ObservatoryMode",
        ):
            self.result.routes_for_mode("artifact_auditor")
        with self.assertRaises(FrozenInstanceError):
            self.result.registry_revision = "alias"

    def test_validation_result_rejects_every_inventory_rebinding(self) -> None:
        invalid = (
            (
                {"registry_revision": "m31-published-boundary-v2"},
                "revision mismatch",
            ),
            (
                {"registrations": self.result.registrations[::-1]},
                "registration inventory mismatch",
            ),
            (
                {"routes": self.result.routes[:-1]},
                "route inventory mismatch",
            ),
            ({"artifact_auditor_route_count": 3}, "auditor route count"),
            (
                {"ternary_transition_visualizer_route_count": 2},
                "visualizer route count",
            ),
            ({"trace_explorer_route_count": 2}, "explorer route count"),
        )
        for changes, message in invalid:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M31PublishedRegistryError,
                    message,
                ):
                    replace(self.result, **changes)

    def test_repeated_validation_preserves_routes_and_raw_identity(
        self,
    ) -> None:
        repeated = validate_m31_published_registry(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )

        self.assertEqual(repeated.registrations, self.result.registrations)
        self.assertEqual(repeated.routes, self.result.routes)
        self.assertEqual(
            tuple(
                (
                    document.identity,
                    document.raw_bytes,
                    document.root,
                )
                for document in repeated.boundary.documents
            ),
            tuple(
                (
                    document.identity,
                    document.raw_bytes,
                    document.root,
                )
                for document in self.result.boundary.documents
            ),
        )
        self.assertEqual(
            tuple(
                (
                    source.source_path,
                    source.source_artifact.raw_bytes,
                    source.m30_archive_member_verified,
                    source.role,
                )
                for source in repeated.boundary.provenance_sources
            ),
            tuple(
                (
                    source.source_path,
                    source.source_artifact.raw_bytes,
                    source.m30_archive_member_verified,
                    source.role,
                )
                for source in self.result.boundary.provenance_sources
            ),
        )

    def test_registry_validation_does_not_modify_upstream(self) -> None:
        before_paths = tuple(
            sorted(
                path.relative_to(self.upstream_root).as_posix()
                for path in self.upstream_root.rglob("*")
                if path.is_file()
            )
        )
        before = {
            relative: (
                _sha256(self.upstream_root / relative),
                (self.upstream_root / relative).stat().st_mtime_ns,
            )
            for relative in self.boundary_paths
        }
        validate_m31_published_registry(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        after_paths = tuple(
            sorted(
                path.relative_to(self.upstream_root).as_posix()
                for path in self.upstream_root.rglob("*")
                if path.is_file()
            )
        )
        after = {
            relative: (
                _sha256(self.upstream_root / relative),
                (self.upstream_root / relative).stat().st_mtime_ns,
            )
            for relative in self.boundary_paths
        }
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after, before)

    def test_one_byte_document_tamper_is_rejected_before_routing(
        self,
    ) -> None:
        with self.boundary_copy() as root:
            relative = M31_PUBLISHED_DOCUMENT_IDENTITIES[1].source_path
            _flip_one_byte(root / relative)
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "raw identity mismatch",
            ):
                validate_m31_published_registry(root)

    def test_one_byte_provenance_tamper_is_rejected_before_routing(
        self,
    ) -> None:
        with self.boundary_copy() as root:
            relative = next(
                source.source_path
                for source in self.result.boundary.provenance_sources
                if source.source_path != FRP_M30_ARCHIVE_PATH
                and source.source_path
                not in {
                    identity.source_path
                    for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
                }
            )
            _flip_one_byte(root / relative)
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "provenance source identity mismatch",
            ):
                validate_m31_published_registry(root)

    def test_upstream_python_source_is_never_executed(self) -> None:
        with self.boundary_copy() as root:
            relative = next(
                source.source_path
                for source in self.result.boundary.provenance_sources
                if source.source_path.endswith(".py")
            )
            target = root / relative
            marker = root / "execution-marker"
            target.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "provenance source identity mismatch",
            ):
                validate_m31_published_registry(root)
            self.assertFalse(marker.exists())

    def test_cli_reports_exact_registry_and_forbidden_operations(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "schemas.m31_published_registry",
                "--upstream-root",
                str(self.upstream_root),
            ],
            cwd=repository_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        output = completed.stdout.splitlines()
        for expected in (
            "FRP Observatory M31 published document registry: PASS",
            "registry_revision=m31-published-boundary-v1",
            "published_documents=4",
            "mode_routes=6",
            "artifact_auditor_routes=4",
            "ternary_transition_visualizer_routes=1",
            "trace_explorer_routes=1",
            "schema_aliases=forbidden",
            "metric_normalization=forbidden",
            "source_execution=forbidden",
            "semantic_reimplementation=forbidden",
            "source_mutation=forbidden",
            "downstream_writeback=forbidden",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, output)


if __name__ == "__main__":
    unittest.main()
