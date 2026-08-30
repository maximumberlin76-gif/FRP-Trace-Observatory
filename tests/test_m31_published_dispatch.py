"""Tests for exact read-only dispatch of verified FRP M31 documents."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from artifact_auditor.m31_published_boundary_intake import (
    M31PublishedDocument,
    M31PublishedDocumentRole,
)
from parsers.artifact_dispatch import (
    RegistrationStatus,
    dispatch_artifact,
)
from parsers.m31_published_dispatch import (
    M31PublishedDispatchBatch,
    M31PublishedDispatchError,
    M31PublishedDocumentDispatch,
    build_m31_published_dispatch_batch,
    dispatch_m31_published_documents,
)
from parsers.source_artifact import capture_source_bytes
from schemas.m31_published_registry import M31PublishedModeRoute
from schemas.registry import ObservatoryMode


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class M31PublishedDispatchBuilderGuardTests(unittest.TestCase):
    """Exercise the public M31 dispatch builder type boundary."""

    def test_builder_requires_complete_registry_validation(self) -> None:
        for value in (None, (), "registry"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    M31PublishedDispatchError,
                    "registry_validation must be "
                    "M31PublishedRegistryValidation",
                ):
                    build_m31_published_dispatch_batch(value)


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not set",
)
class ExactM31PublishedDispatchIntegrationTests(unittest.TestCase):
    """Exercise all six envelopes against the exact FRP M31 publication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.batch = dispatch_m31_published_documents(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        cls.validation = cls.batch.registry_validation
        cls.boundary_paths = tuple(
            dict.fromkeys(
                [
                    *(
                        document.identity.source_path
                        for document in cls.validation.boundary.documents
                    ),
                    *(
                        source.source_path
                        for source in (
                            cls.validation.boundary.provenance_sources
                        )
                    ),
                ]
            )
        )

    def fresh_batch(self) -> M31PublishedDispatchBatch:
        return dispatch_m31_published_documents(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )

    def test_exact_inventory_order_is_one_three_one_one(self) -> None:
        self.assertEqual(self.batch.published_document_count, 4)
        self.assertEqual(self.batch.total_dispatch_count, 6)
        self.assertEqual(
            tuple(
                (dispatch.role, dispatch.mode)
                for dispatch in self.batch.dispatches
            ),
            (
                (
                    M31PublishedDocumentRole.FORMAL_SCHEMA,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    M31PublishedDocumentRole.EVIDENCE,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    M31PublishedDocumentRole.EVIDENCE,
                    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ),
                (
                    M31PublishedDocumentRole.EVIDENCE,
                    ObservatoryMode.TRACE_EXPLORER,
                ),
                (
                    M31PublishedDocumentRole.MANIFEST,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
                (
                    M31PublishedDocumentRole.QUALIFICATION,
                    ObservatoryMode.ARTIFACT_AUDITOR,
                ),
            ),
        )

    def test_exact_dispatch_digests_are_stable_and_unique(self) -> None:
        observed = tuple(
            dispatch.dispatch_sha256
            for dispatch in self.batch.dispatches
        )
        self.assertEqual(
            observed,
            (
                "63617ee1b7861551691d98aee2399ab4"
                "93954c1a120b180d86eae6d539bdbe15",
                "649502c9cb9c27572ff6691fb111c33f"
                "bf3022048865a17a2fc85f9fc3d74aa0",
                "ff4597411a781c814ab8ef009d307398"
                "57411d2a31ff34839d3060b478a697e8",
                "f34b867fabcaab51515ecca39f2eb728"
                "7f52aa218d3ac48596a1481326009630",
                "5d67da0bfe4506c048200b50124fa574"
                "be697affa01ccb0cc3d0e338ca2daea3",
                "cb2843b72922803846a2bbecc541e420"
                "6b5886b818569d638968abd447562836",
            ),
        )
        self.assertEqual(len(set(observed)), 6)

    def test_exact_mode_counts_are_four_one_one(self) -> None:
        expected = {
            ObservatoryMode.ARTIFACT_AUDITOR: 4,
            ObservatoryMode.TERNARY_TRANSITION_VISUALIZER: 1,
            ObservatoryMode.TRACE_EXPLORER: 1,
        }
        for mode, count in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(
                    len(self.batch.dispatches_for_mode(mode)),
                    count,
                )

    def test_exact_role_counts_are_one_three_one_one(self) -> None:
        expected = {
            M31PublishedDocumentRole.FORMAL_SCHEMA: 1,
            M31PublishedDocumentRole.EVIDENCE: 3,
            M31PublishedDocumentRole.MANIFEST: 1,
            M31PublishedDocumentRole.QUALIFICATION: 1,
        }
        for role, count in expected.items():
            with self.subTest(role=role):
                self.assertEqual(
                    len(self.batch.dispatches_for_role(role)),
                    count,
                )

    def test_envelopes_retain_exact_registry_evidence_identity(self) -> None:
        expected_pairs = tuple(
            (document, route)
            for document in self.validation.boundary.documents
            for route in self.validation.routes
            if route.registration.role is document.identity.role
        )
        for dispatch, (document, route) in zip(
            self.batch.dispatches,
            expected_pairs,
            strict=True,
        ):
            with self.subTest(role=dispatch.role, mode=dispatch.mode):
                self.assertIs(dispatch.registry_validation, self.validation)
                self.assertIs(dispatch.document, document)
                self.assertIs(dispatch.route, route)
                self.assertIs(
                    dispatch.source_artifact,
                    document.source_artifact,
                )
                self.assertIs(
                    dispatch.parsed_artifact,
                    document.parsed_artifact,
                )
                self.assertEqual(dispatch.raw_bytes, document.raw_bytes)

    def test_evidence_modes_share_one_unmerged_document(self) -> None:
        dispatches = self.batch.dispatches_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        evidence = self.validation.boundary.document(
            M31PublishedDocumentRole.EVIDENCE
        )
        self.assertTrue(
            all(dispatch.document is evidence for dispatch in dispatches)
        )
        self.assertTrue(
            all(
                dispatch.parsed_artifact is evidence.parsed_artifact
                for dispatch in dispatches
            )
        )
        self.assertIn(
            "historical_thermal_experiment",
            evidence.root,
        )
        self.assertIn(
            "current_comparative_thermal_contours",
            evidence.root,
        )
        self.assertIsNot(
            evidence.root["historical_thermal_experiment"],
            evidence.root["current_comparative_thermal_contours"],
        )

    def test_dispatch_keys_retain_role_mode_and_raw_identity(self) -> None:
        keys = tuple(
            dispatch.dispatch_key
            for dispatch in self.batch.dispatches
        )
        self.assertEqual(len(set(keys)), 6)
        for dispatch, key in zip(
            self.batch.dispatches,
            keys,
            strict=True,
        ):
            with self.subTest(role=dispatch.role, mode=dispatch.mode):
                self.assertEqual(key[0], dispatch.role)
                self.assertIs(key[1], dispatch.mode)
                self.assertEqual(
                    key[2],
                    dispatch.route.registration.raw_sha256,
                )

    def test_lookups_require_exact_enums_without_aliases(self) -> None:
        evidence = self.batch.dispatch_for(
            M31PublishedDocumentRole.EVIDENCE,
            ObservatoryMode.TRACE_EXPLORER,
        )
        self.assertIs(evidence.mode, ObservatoryMode.TRACE_EXPLORER)

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "role must be M31PublishedDocumentRole",
        ):
            self.batch.dispatches_for_role("evidence")
        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "mode must be ObservatoryMode",
        ):
            self.batch.dispatches_for_mode("trace_explorer")
        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "mode must be ObservatoryMode",
        ):
            self.batch.dispatch_for(
                M31PublishedDocumentRole.EVIDENCE,
                "trace_explorer",
            )

    def test_ineligible_role_mode_routes_are_rejected(self) -> None:
        ineligible = (
            M31PublishedDocumentRole.FORMAL_SCHEMA,
            M31PublishedDocumentRole.MANIFEST,
            M31PublishedDocumentRole.QUALIFICATION,
        )
        for role in ineligible:
            for mode in (
                ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
                ObservatoryMode.TRACE_EXPLORER,
            ):
                with self.subTest(role=role, mode=mode):
                    with self.assertRaisesRegex(
                        M31PublishedDispatchError,
                        "is not eligible",
                    ):
                        self.batch.dispatch_for(role, mode)

    def test_repeated_exact_dispatch_is_byte_stable(self) -> None:
        repeated = self.fresh_batch()
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
        self.assertEqual(
            tuple(
                dispatch.raw_bytes
                for dispatch in repeated.dispatches
            ),
            tuple(
                dispatch.raw_bytes
                for dispatch in self.batch.dispatches
            ),
        )

    def test_loaded_at_is_preserved_without_digest_dependence(self) -> None:
        self.assertEqual(
            self.validation.boundary.loaded_at,
            _EXACT_LOADED_AT,
        )
        self.assertTrue(
            all(
                dispatch.source_artifact.loaded_at == _EXACT_LOADED_AT
                for dispatch in self.batch.dispatches
            )
        )
        later = dispatch_m31_published_documents(
            self.upstream_root,
            loaded_at=datetime(
                2026,
                8,
                30,
                1,
                0,
                tzinfo=timezone.utc,
            ),
        )
        self.assertEqual(
            tuple(
                dispatch.dispatch_sha256
                for dispatch in later.dispatches
            ),
            tuple(
                dispatch.dispatch_sha256
                for dispatch in self.batch.dispatches
            ),
        )

    def test_dispatch_and_batch_are_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.batch.dispatches[0].dispatch_sha256 = "0" * 64
        with self.assertRaises(FrozenInstanceError):
            self.batch.dispatches = ()

    def test_create_requires_exact_public_input_types(self) -> None:
        document = self.validation.boundary.documents[0]
        route = self.validation.routes[0]
        invalid = (
            (
                (None, document, route),
                "registry_validation must be "
                "M31PublishedRegistryValidation",
            ),
            (
                (self.validation, "document", route),
                "document must be M31PublishedDocument",
            ),
            (
                (self.validation, document, "route"),
                "route must be M31PublishedModeRoute",
            ),
        )
        for arguments, message in invalid:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(
                    M31PublishedDispatchError,
                    message,
                ):
                    M31PublishedDocumentDispatch.create(*arguments)

    def test_equal_but_reconstructed_document_is_rejected(self) -> None:
        original = self.validation.boundary.documents[0]
        reconstructed = M31PublishedDocument(
            identity=original.identity,
            source_artifact=original.source_artifact,
            parsed_artifact=original.parsed_artifact,
        )
        self.assertEqual(reconstructed, original)
        self.assertIsNot(reconstructed, original)

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "document is not exact registry boundary evidence",
        ):
            M31PublishedDocumentDispatch.create(
                self.validation,
                reconstructed,
                self.validation.routes[0],
            )

    def test_equal_but_reconstructed_route_is_rejected(self) -> None:
        document = self.validation.boundary.documents[0]
        route = self.validation.routes[0]
        reconstructed = M31PublishedModeRoute(
            registration=route.registration,
            mode=route.mode,
        )
        self.assertEqual(reconstructed, route)
        self.assertIsNot(reconstructed, route)

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "route is not exact registry route evidence",
        ):
            M31PublishedDocumentDispatch.create(
                self.validation,
                document,
                reconstructed,
            )

    def test_route_for_another_document_is_rejected(self) -> None:
        schema = self.validation.boundary.document(
            M31PublishedDocumentRole.FORMAL_SCHEMA
        )
        evidence_route = next(
            route
            for route in self.validation.routes
            if route.registration.role is M31PublishedDocumentRole.EVIDENCE
        )

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "route registration does not match boundary document",
        ):
            M31PublishedDocumentDispatch.create(
                self.validation,
                schema,
                evidence_route,
            )

    def test_dispatch_digest_format_and_identity_are_enforced(self) -> None:
        dispatch = self.batch.dispatches[0]
        invalid = (
            (None, "lowercase hexadecimal SHA-256"),
            ("A" * 64, "lowercase hexadecimal SHA-256"),
            ("0" * 64, "does not bind the exact document and route"),
        )
        for digest, message in invalid:
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(
                    M31PublishedDispatchError,
                    message,
                ):
                    replace(dispatch, dispatch_sha256=digest)

    def test_route_change_cannot_reuse_a_dispatch_digest(self) -> None:
        evidence = self.batch.dispatches_for_role(
            M31PublishedDocumentRole.EVIDENCE
        )
        auditor = evidence[0]
        visualizer = evidence[1]

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "does not bind the exact document and route",
        ):
            replace(auditor, route=visualizer.route)

    def test_source_integrity_is_rechecked_at_dispatch_boundary(self) -> None:
        batch = self.fresh_batch()
        dispatch = batch.dispatches[0]
        object.__setattr__(
            dispatch.source_artifact,
            "raw_bytes",
            b"{}",
        )

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "dispatch source integrity verification failed",
        ):
            M31PublishedDocumentDispatch.create(
                batch.registry_validation,
                dispatch.document,
                dispatch.route,
            )

    def test_parsed_object_must_remain_bound_to_boundary_source(self) -> None:
        batch = self.fresh_batch()
        dispatch = batch.dispatches[0]
        source = dispatch.source_artifact
        reconstructed_source = capture_source_bytes(
            dispatch.raw_bytes,
            source_filename=source.source_filename,
            source_path=source.source_path,
            loaded_at=source.loaded_at,
        )
        object.__setattr__(
            dispatch.parsed_artifact,
            "source_artifact",
            reconstructed_source,
        )

        with self.assertRaisesRegex(
            M31PublishedDispatchError,
            "dispatch parsed object differs from boundary source",
        ):
            M31PublishedDocumentDispatch.create(
                batch.registry_validation,
                dispatch.document,
                dispatch.route,
            )

    def test_batch_model_rejects_inventory_rebinding(self) -> None:
        repeated = self.fresh_batch()
        invalid = (
            (
                {"dispatches": list(self.batch.dispatches)},
                "dispatches must be a tuple",
            ),
            (
                {"dispatches": (None, *self.batch.dispatches[1:])},
                "must contain M31PublishedDocumentDispatch",
            ),
            (
                {"dispatches": self.batch.dispatches[:-1]},
                "dispatch inventory length mismatch",
            ),
            (
                {
                    "dispatches": (
                        self.batch.dispatches[1],
                        self.batch.dispatches[0],
                        *self.batch.dispatches[2:],
                    )
                },
                "dispatch order or registry evidence identity mismatch",
            ),
            (
                {
                    "registry_validation": (
                        repeated.registry_validation
                    )
                },
                "dispatch registry evidence identity mismatch",
            ),
        )
        for changes, message in invalid:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M31PublishedDispatchError,
                    message,
                ):
                    replace(self.batch, **changes)

    def test_legacy_schema_only_dispatch_is_not_reused(self) -> None:
        evidence = self.validation.boundary.document(
            M31PublishedDocumentRole.EVIDENCE
        )
        legacy = dispatch_artifact(evidence.source_artifact)
        self.assertIs(
            legacy.registration.status,
            RegistrationStatus.UNKNOWN_IDENTIFIER,
        )
        self.assertEqual(
            len(
                self.batch.dispatches_for_role(
                    M31PublishedDocumentRole.EVIDENCE
                )
            ),
            3,
        )

    def test_cli_reports_exact_boundary_and_forbidden_operations(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "parsers.m31_published_dispatch",
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
        expected = (
            "FRP Observatory M31 published dispatch boundary: PASS",
            "registry_revision=m31-published-boundary-v1",
            "published_documents=4",
            "dispatch_envelopes=6",
            "artifact_auditor_dispatches=4",
            "ternary_transition_visualizer_dispatches=1",
            "trace_explorer_dispatches=1",
            "legacy_schema_only_dispatch_reuse=forbidden",
            "mode_consumer_invocation=deferred",
            "source_execution=forbidden",
            "metric_normalization=forbidden",
            "semantic_reimplementation=forbidden",
            "source_mutation=forbidden",
            "downstream_writeback=forbidden",
        )
        self.assertEqual(tuple(output), expected)

    def test_dispatch_does_not_modify_upstream(self) -> None:
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
        dispatch_m31_published_documents(
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


if __name__ == "__main__":
    unittest.main()
