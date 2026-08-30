"""Tests for the exact read-only FRP M31 published boundary intake."""

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
    FRP_M30_ARCHIVE_BYTES,
    FRP_M30_ARCHIVE_PATH,
    FRP_M30_ARCHIVE_SHA256,
    M31_PUBLISHED_DOCUMENT_IDENTITIES,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedBoundaryError,
    M31PublishedDocumentRole,
    validate_m31_published_boundary,
)


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M31_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flip_one_byte(path: Path) -> None:
    raw = bytearray(path.read_bytes())
    if not raw:
        raise AssertionError(f"cannot tamper with empty source: {path}")
    index = 0 if len(raw) == 1 else len(raw) // 2
    raw[index] ^= 1
    path.write_bytes(raw)


class PublishedIdentityContractTests(unittest.TestCase):
    """Exercise fixed identities without requiring an upstream checkout."""

    def test_canonical_document_identity_inventory_is_exact(self) -> None:
        self.assertEqual(
            tuple(identity.role for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES),
            (
                M31PublishedDocumentRole.FORMAL_SCHEMA,
                M31PublishedDocumentRole.EVIDENCE,
                M31PublishedDocumentRole.MANIFEST,
                M31PublishedDocumentRole.QUALIFICATION,
            ),
        )
        self.assertEqual(
            tuple(
                identity.byte_length
                for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            (1_468, 39_993, 828, 1_512),
        )
        self.assertEqual(
            sum(
                identity.byte_length
                for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            43_801,
        )
        self.assertEqual(
            M31_PUBLISHED_REGISTRY_REVISION,
            "m31-published-boundary-v1",
        )
        self.assertEqual(FRP_M30_ARCHIVE_BYTES, 10_189_989)
        self.assertEqual(
            FRP_M30_ARCHIVE_SHA256,
            "05ea33f6f3f505d315af930c2d51779f"
            "7189905308473f32a57375e477069caa",
        )

    def test_document_identities_are_frozen(self) -> None:
        identity = M31_PUBLISHED_DOCUMENT_IDENTITIES[0]
        with self.assertRaises(FrozenInstanceError):
            identity.source_path = "replacement.json"

    def test_identity_rejects_aliases_and_unsafe_metadata(self) -> None:
        schema = M31_PUBLISHED_DOCUMENT_IDENTITIES[0]
        evidence = M31_PUBLISHED_DOCUMENT_IDENTITIES[1]
        invalid = (
            (schema, {"role": "formal_schema"}, "role must"),
            (schema, {"source_path": "../schema.json"}, "safe relative"),
            (schema, {"identifier_field": "id"}, "must be"),
            (schema, {"kind": "schema"}, "only"),
            (schema, {"byte_length": True}, "positive integer"),
            (schema, {"raw_sha256": "A" * 64}, "lowercase"),
            (evidence, {"identifier_field": "$id"}, "schema and kind"),
            (evidence, {"kind": None}, "schema and kind"),
        )
        for identity, changes, message in invalid:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M31PublishedBoundaryError,
                    message,
                ):
                    replace(identity, **changes)

    def test_validator_rejects_invalid_root_contracts(self) -> None:
        with self.assertRaisesRegex(
            M31PublishedBoundaryError,
            "upstream_root must be a string or Path",
        ):
            validate_m31_published_boundary(1)

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing"
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "regular directory",
            ):
                validate_m31_published_boundary(missing)

            real = root / "real"
            real.mkdir()
            link = root / "link"
            try:
                link.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "regular directory",
            ):
                validate_m31_published_boundary(link)

    def test_validator_requires_timezone_aware_loaded_at(self) -> None:
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "loaded_at must be timezone-aware",
            ):
                validate_m31_published_boundary(
                    Path(temporary),
                    loaded_at=datetime(2026, 8, 30),
                )


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not set",
)
class ExactM31PublishedBoundaryIntegrationTests(unittest.TestCase):
    """Exercise exact intake and adversarial failures against FRP M31."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.result = validate_m31_published_boundary(
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
                        for source in cls.result.provenance_sources
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

    def test_exact_boundary_preserves_document_order_and_raw_identity(
        self,
    ) -> None:
        self.assertEqual(len(self.result.documents), 4)
        self.assertEqual(self.result.total_document_bytes, 43_801)
        for document, identity in zip(
            self.result.documents,
            M31_PUBLISHED_DOCUMENT_IDENTITIES,
            strict=True,
        ):
            with self.subTest(role=identity.role):
                self.assertIs(document.identity, identity)
                self.assertEqual(len(document.raw_bytes), identity.byte_length)
                self.assertEqual(
                    hashlib.sha256(document.raw_bytes).hexdigest(),
                    identity.raw_sha256,
                )
                self.assertEqual(
                    document.source_artifact.source_path,
                    identity.source_path,
                )
                self.assertTrue(document.source_artifact.verify_integrity())

    def test_loaded_at_is_shared_immutable_utc(self) -> None:
        self.assertEqual(self.result.loaded_at, _EXACT_LOADED_AT)
        self.assertEqual(self.result.loaded_at.utcoffset().total_seconds(), 0)
        self.assertTrue(
            all(
                document.source_artifact.loaded_at == self.result.loaded_at
                for document in self.result.documents
            )
        )
        self.assertTrue(
            all(
                source.source_artifact.loaded_at == self.result.loaded_at
                for source in self.result.provenance_sources
            )
        )
        with self.assertRaises(FrozenInstanceError):
            self.result.loaded_at = datetime.now(timezone.utc)

    def test_processor_core_and_active_zero_invariants_are_exact(self) -> None:
        evidence = self.result.document(
            M31PublishedDocumentRole.EVIDENCE
        ).root
        core = evidence["core"]
        active = evidence["active_zero_execution_evidence"]
        self.assertEqual(core["balanced_ternary_notation"], "-1/0/1")
        self.assertEqual(core["semantic_values"], (-1, 0, 1))
        self.assertEqual(core["active_neutral_state"], 0)
        self.assertEqual(
            core["opposite_transition_routes"],
            ((-1, 0, 1), (1, 0, -1)),
        )
        self.assertEqual(core["temporal_scheduler_modes"], ("1/7", "7/1"))
        self.assertEqual(core["service_scheduler_mode"], "free")
        self.assertIs(
            core["classical_bit_addition_primary_mechanism"],
            False,
        )
        self.assertEqual(active["record_count"], 100)
        self.assertEqual(active["cell_observation_count"], 800)
        self.assertEqual(active["active_zero_after_observation_count"], 702)
        self.assertEqual(active["invariant_pass_records"], 100)
        self.assertEqual(
            active["retained_transition_counts"]["direct_opposite"],
            0,
        )
        self.assertEqual(active["event_totals"]["actual_direct_events"], 0)
        self.assertEqual(active["event_totals"]["reserved_state_events"], 0)
        self.assertEqual(active["event_totals"]["queue_overflow_events"], 0)

    def test_thermal_contours_remain_separate_and_nonphysical(self) -> None:
        evidence = self.result.document(
            M31PublishedDocumentRole.EVIDENCE
        ).root
        historical = evidence["historical_thermal_experiment"]
        current = evidence["current_comparative_thermal_contours"]
        self.assertEqual(
            historical["measurement_class"],
            "release_specific_model_thermal_load",
        )
        self.assertEqual(
            current["measurement_class"],
            "shared_model_comparative_benchmark",
        )
        self.assertIs(historical["physical_temperature_measurement"], False)
        self.assertIs(current["physical_temperature_measurement"], False)
        self.assertEqual(historical["winner_assertions"], ())
        self.assertEqual(current["baseline"]["winner_assertions"], ())
        self.assertEqual(
            current["hardware_sensitivity"]["winner_assertions"],
            (),
        )
        self.assertIs(
            current["historical_heat_peak_interchangeable"],
            False,
        )

    def test_observatory_contract_is_strictly_read_only(self) -> None:
        contract = self.result.document(
            M31PublishedDocumentRole.EVIDENCE
        ).root["observatory_publication_contract"]
        self.assertEqual(
            contract["direction"],
            "upstream_published_bytes_to_downstream",
        )
        self.assertEqual(
            contract["downstream_role"],
            "read_only_validation_and_visualization",
        )
        for field in (
            "downstream_metric_normalization",
            "downstream_semantic_reimplementation",
            "downstream_source_mutation",
            "downstream_writeback",
        ):
            with self.subTest(field=field):
                self.assertEqual(contract[field], "forbidden")
        self.assertIs(
            contract["published_contours_must_remain_separate"],
            True,
        )

    def test_provenance_and_m30_archive_relations_are_exact(self) -> None:
        self.assertEqual(len(self.result.provenance_sources), 12)
        self.assertEqual(self.result.m30_archive_member_count, 10)
        self.assertEqual(
            self.result.m30_archive_sha256,
            FRP_M30_ARCHIVE_SHA256,
        )
        self.assertEqual(
            sum(
                source.m30_archive_member_verified
                for source in self.result.provenance_sources
            ),
            10,
        )
        self.assertEqual(
            len(
                {
                    source.source_path
                    for source in self.result.provenance_sources
                }
            ),
            12,
        )
        archive = next(
            source
            for source in self.result.provenance_sources
            if source.source_path == FRP_M30_ARCHIVE_PATH
        )
        self.assertEqual(
            archive.source_artifact.byte_length,
            FRP_M30_ARCHIVE_BYTES,
        )
        self.assertEqual(
            archive.source_artifact.content_sha256,
            FRP_M30_ARCHIVE_SHA256,
        )

    def test_document_lookup_rejects_string_alias(self) -> None:
        for role in M31PublishedDocumentRole:
            with self.subTest(role=role):
                self.assertIs(
                    self.result.document(role).identity.role,
                    role,
                )
        with self.assertRaisesRegex(
            M31PublishedBoundaryError,
            "role must be M31PublishedDocumentRole",
        ):
            self.result.document("evidence")

    def test_result_rejects_rebinding(self) -> None:
        invalid = (
            (
                {"registry_revision": "m31-published-boundary-v2"},
                "registry revision",
            ),
            ({"documents": self.result.documents[::-1]}, "document order"),
            (
                {
                    "provenance_sources":
                    self.result.provenance_sources[:-1]
                },
                "provenance source inventory",
            ),
            ({"m30_archive_sha256": "0" * 64}, "archive digest"),
            ({"m30_archive_member_count": 9}, "member count"),
            (
                {"loaded_at": datetime(2026, 8, 30)},
                "timezone-aware UTC",
            ),
        )
        for changes, message in invalid:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M31PublishedBoundaryError,
                    message,
                ):
                    replace(self.result, **changes)

    def test_repeated_validation_preserves_all_published_identities(
        self,
    ) -> None:
        repeated = validate_m31_published_boundary(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        self.assertEqual(
            tuple(
                (
                    document.identity,
                    document.raw_bytes,
                    document.root,
                )
                for document in repeated.documents
            ),
            tuple(
                (
                    document.identity,
                    document.raw_bytes,
                    document.root,
                )
                for document in self.result.documents
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
                for source in repeated.provenance_sources
            ),
            tuple(
                (
                    source.source_path,
                    source.source_artifact.raw_bytes,
                    source.m30_archive_member_verified,
                    source.role,
                )
                for source in self.result.provenance_sources
            ),
        )

    def test_validation_does_not_modify_or_create_upstream_files(self) -> None:
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
        validate_m31_published_boundary(
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

    def test_one_byte_document_tamper_is_rejected(self) -> None:
        with self.boundary_copy() as root:
            relative = M31_PUBLISHED_DOCUMENT_IDENTITIES[1].source_path
            _flip_one_byte(root / relative)
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "raw identity mismatch",
            ):
                validate_m31_published_boundary(root)

    def test_one_byte_provenance_tamper_is_rejected(self) -> None:
        with self.boundary_copy() as root:
            provenance = next(
                source
                for source in self.result.provenance_sources
                if source.source_path != FRP_M30_ARCHIVE_PATH
                and source.source_path
                not in {
                    identity.source_path
                    for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
                }
            )
            _flip_one_byte(root / provenance.source_path)
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "provenance source identity mismatch",
            ):
                validate_m31_published_boundary(root)

    def test_one_byte_archive_tamper_is_rejected(self) -> None:
        with self.boundary_copy() as root:
            _flip_one_byte(root / FRP_M30_ARCHIVE_PATH)
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "provenance source identity mismatch",
            ):
                validate_m31_published_boundary(root)

    def test_missing_or_symlinked_document_is_rejected(self) -> None:
        relative = M31_PUBLISHED_DOCUMENT_IDENTITIES[0].source_path
        with self.boundary_copy() as root:
            (root / relative).unlink()
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "required regular upstream file is missing",
            ):
                validate_m31_published_boundary(root)

        with self.boundary_copy() as root:
            target = root / relative
            saved = target.with_suffix(".saved")
            target.rename(saved)
            try:
                target.symlink_to(saved.name)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaisesRegex(
                M31PublishedBoundaryError,
                "required regular upstream file is missing",
            ):
                validate_m31_published_boundary(root)

    def test_upstream_python_source_is_never_executed(self) -> None:
        with self.boundary_copy() as root:
            provenance = next(
                source
                for source in self.result.provenance_sources
                if source.source_path.endswith(".py")
            )
            target = root / provenance.source_path
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
                validate_m31_published_boundary(root)
            self.assertFalse(marker.exists())

    def test_cli_reports_exact_read_only_boundary(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "artifact_auditor.m31_published_boundary_intake",
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
        self.assertIn(
            "FRP Observatory M31 published boundary intake: PASS",
            output,
        )
        self.assertIn("published_documents=4", output)
        self.assertIn("published_document_bytes=43801", output)
        self.assertIn("provenance_sources=12", output)
        self.assertIn("m30_archive_members=10", output)
        self.assertIn("balanced_ternary_notation=-1/0/1", output)
        self.assertIn("metric_normalization=forbidden", output)
        self.assertIn("semantic_reimplementation=forbidden", output)
        self.assertIn("source_mutation=forbidden", output)
        self.assertIn("downstream_writeback=forbidden", output)


if __name__ == "__main__":
    unittest.main()
