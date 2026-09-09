"""Tests for the exact read-only FRP M32 published boundary intake."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from artifact_auditor.m32_published_boundary_intake import (
    M32_PUBLISHED_DOCUMENT_IDENTITIES,
    M32_PUBLISHED_REGISTRY_REVISION,
    M32_PUBLISHED_TRANSCRIPT_IDENTITIES,
    M32_SOURCE_COMMIT,
    M32PublishedBoundaryError,
    M32PublishedDocumentRole,
    validate_m32_published_boundary,
)


_UPSTREAM_ENVIRONMENT_VARIABLE = "FRP_M32_UPSTREAM_ROOT"
_EXACT_LOADED_AT = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flip_one_byte(path: Path) -> None:
    raw = bytearray(path.read_bytes())
    if not raw:
        raise AssertionError(f"cannot tamper with empty source: {path}")
    index = 0 if len(raw) == 1 else len(raw) // 2
    raw[index] ^= 1
    path.write_bytes(raw)


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _canonical_sha256(value: object) -> str:
    raw = (
        json.dumps(
            _plain(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class PublishedIdentityContractTests(unittest.TestCase):
    """Exercise fixed identities without requiring an upstream checkout."""

    def test_canonical_document_identity_inventory_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                identity.role
                for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            (
                M32PublishedDocumentRole.FORMAL_SCHEMA,
                M32PublishedDocumentRole.TRACE_BUNDLE,
                M32PublishedDocumentRole.MANIFEST,
                M32PublishedDocumentRole.QUALIFICATION,
            ),
        )
        self.assertEqual(
            tuple(
                identity.source_path
                for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            (
                "schemas/m32/"
                "frp.m32.deterministic_rtl_trace_bundle.v1.schema.json",
                "artifacts/m32/exports/"
                "m32-deterministic-rtl-trace-bundle.json",
                "artifacts/m32/manifests/"
                "m32-deterministic-rtl-trace-manifest.json",
                "artifacts/m32/qualification/"
                "m32-deterministic-rtl-trace-qualification.json",
            ),
        )
        self.assertEqual(
            tuple(
                identity.byte_length
                for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            (34_066, 412_195, 7_211, 4_624),
        )
        self.assertEqual(
            tuple(
                identity.raw_sha256
                for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            (
                "534db8227218184cac5d1cabb461dd63"
                "b1b61a99e0269c98535539ad3f7d7da2",
                "62d8c1e6d205b9262a5c950883d32592"
                "75d5049f7a896ae12956a210cb75b7e0",
                "da011dbc726d6d1fc0b7dbae12afe1e1"
                "3d8240df64b9474fd0130c94ba005859",
                "26ec2d3eadd73b490eb023572101bb78c"
                "f5d11561ead91b78b1a30e690458273",
            ),
        )
        self.assertEqual(
            sum(
                identity.byte_length
                for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
            ),
            458_096,
        )
        self.assertEqual(
            M32_PUBLISHED_REGISTRY_REVISION,
            "m32-published-boundary-v1",
        )
        self.assertEqual(
            M32_SOURCE_COMMIT,
            "c0bc0fbc2c1c2e500b19d0ba84b3431a813e3941",
        )

    def test_canonical_transcript_identity_inventory_is_exact(self) -> None:
        self.assertEqual(
            tuple(
                (
                    identity.artifact_member_path,
                    identity.byte_length,
                    identity.raw_sha256,
                    identity.replay,
                    identity.scheduler_mode,
                )
                for identity in M32_PUBLISHED_TRANSCRIPT_IDENTITIES
            ),
            (
                (
                    "m32-mode-7-1-full-trace-run-1.log",
                    105_702,
                    "9517a02cd1ce2c687365f3712a453a93"
                    "70e505ee4267e151fd05b266977ce915",
                    1,
                    "7/1",
                ),
                (
                    "m32-mode-7-1-full-trace-run-2.log",
                    105_702,
                    "9517a02cd1ce2c687365f3712a453a93"
                    "70e505ee4267e151fd05b266977ce915",
                    2,
                    "7/1",
                ),
                (
                    "m32-mode-1-7-full-trace-run-1.log",
                    112_364,
                    "41de8e92c28f150f8d163fc1438b4d4"
                    "381fa42d76a970f9246bbda4679491d89",
                    1,
                    "1/7",
                ),
                (
                    "m32-mode-1-7-full-trace-run-2.log",
                    112_364,
                    "41de8e92c28f150f8d163fc1438b4d4"
                    "381fa42d76a970f9246bbda4679491d89",
                    2,
                    "1/7",
                ),
            ),
        )
        self.assertEqual(
            sum(
                identity.byte_length
                for identity in M32_PUBLISHED_TRANSCRIPT_IDENTITIES
            ),
            436_132,
        )

    def test_registered_identities_are_frozen(self) -> None:
        document = M32_PUBLISHED_DOCUMENT_IDENTITIES[0]
        transcript = M32_PUBLISHED_TRANSCRIPT_IDENTITIES[0]
        with self.assertRaises(FrozenInstanceError):
            document.source_path = "replacement.json"
        with self.assertRaises(FrozenInstanceError):
            transcript.replay = 2

    def test_registered_identities_reject_unsafe_metadata(self) -> None:
        schema = M32_PUBLISHED_DOCUMENT_IDENTITIES[0]
        bundle = M32_PUBLISHED_DOCUMENT_IDENTITIES[1]
        transcript = M32_PUBLISHED_TRANSCRIPT_IDENTITIES[0]
        invalid_documents = (
            (schema, {"role": "formal_schema"}, "role must"),
            (schema, {"source_path": "../schema.json"}, "safe relative"),
            (schema, {"identifier_field": "id"}, "must be"),
            (schema, {"kind": "schema"}, "only"),
            (schema, {"byte_length": True}, "positive integer"),
            (schema, {"raw_sha256": "A" * 64}, "lowercase"),
            (bundle, {"identifier_field": "$id"}, "schema and kind"),
            (bundle, {"kind": None}, "schema and kind"),
        )
        for identity, changes, message in invalid_documents:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M32PublishedBoundaryError,
                    message,
                ):
                    replace(identity, **changes)

        invalid_transcripts = (
            ({"artifact_member_path": "../trace.log"}, "safe relative"),
            ({"byte_length": True}, "positive integer"),
            ({"raw_sha256": "A" * 64}, "lowercase"),
            ({"replay": 0}, "positive integer"),
            ({"scheduler_mode": "1/1"}, "7/1 or 1/7"),
        )
        for changes, message in invalid_transcripts:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M32PublishedBoundaryError,
                    message,
                ):
                    replace(transcript, **changes)

    def test_validator_rejects_invalid_root_and_time_contracts(self) -> None:
        with self.assertRaisesRegex(
            M32PublishedBoundaryError,
            "upstream_root must be a string or Path",
        ):
            validate_m32_published_boundary(1)

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing"
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "regular directory",
            ):
                validate_m32_published_boundary(missing)

            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "loaded_at must be timezone-aware",
            ):
                validate_m32_published_boundary(
                    root,
                    loaded_at=datetime(2026, 9, 9),
                )

            real = root / "real"
            real.mkdir()
            link = root / "link"
            try:
                link.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "regular directory",
            ):
                validate_m32_published_boundary(link)


@unittest.skipUnless(
    os.environ.get(_UPSTREAM_ENVIRONMENT_VARIABLE),
    f"{_UPSTREAM_ENVIRONMENT_VARIABLE} is not set",
)
class ExactM32PublishedBoundaryIntegrationTests(unittest.TestCase):
    """Exercise exact intake and adversarial failures against FRP M32."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.upstream_root = Path(
            os.environ[_UPSTREAM_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
        cls.result = validate_m32_published_boundary(
            cls.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        cls.boundary_paths = tuple(
            dict.fromkeys(
                [
                    *(
                        identity.source_path
                        for identity in M32_PUBLISHED_DOCUMENT_IDENTITIES
                    ),
                    *(
                        source.source_path
                        for source in cls.result.source_identities
                    ),
                ]
            )
        )

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

    def test_exact_boundary_preserves_document_order_and_identity(
        self,
    ) -> None:
        self.assertEqual(len(self.result.documents), 4)
        self.assertEqual(self.result.total_document_bytes, 458_096)
        for document, identity in zip(
            self.result.documents,
            M32_PUBLISHED_DOCUMENT_IDENTITIES,
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
                for source in self.result.source_identities
            )
        )
        with self.assertRaises(FrozenInstanceError):
            self.result.loaded_at = datetime.now(timezone.utc)

    def test_current_source_identity_inventory_is_exact(self) -> None:
        self.assertEqual(len(self.result.source_identities), 29)
        self.assertEqual(self.result.total_source_bytes, 442_916)
        paths = tuple(
            source.source_path for source in self.result.source_identities
        )
        self.assertEqual(len(set(paths)), 29)
        self.assertEqual(
            Counter(
                "m31_rtl"
                if path.startswith("rtl/m31/")
                else "m32_rtl"
                if path.startswith("rtl/m32/")
                else "m32_formal"
                if path.startswith("formal/m32/")
                else "registered_workflow"
                if path
                == (
                    ".github/workflows/"
                    "frp-m32-registered-target-boundary-workflow.yml"
                )
                else "unexpected"
                for path in paths
            ),
            {
                "m31_rtl": 16,
                "m32_rtl": 11,
                "m32_formal": 1,
                "registered_workflow": 1,
            },
        )
        for source in self.result.source_identities:
            with self.subTest(path=source.source_path):
                target = self.upstream_root.joinpath(
                    *source.source_path.split("/")
                )
                self.assertEqual(target.stat().st_size, source.byte_length)
                self.assertEqual(_sha256(target), source.raw_sha256)
                self.assertTrue(source.source_artifact.verify_integrity())

    def test_transcript_identity_records_are_exact(self) -> None:
        self.assertEqual(
            self.result.transcript_identities,
            M32_PUBLISHED_TRANSCRIPT_IDENTITIES,
        )
        self.assertEqual(self.result.total_transcript_bytes, 436_132)
        for mode in ("7/1", "1/7"):
            records = tuple(
                identity
                for identity in self.result.transcript_identities
                if identity.scheduler_mode == mode
            )
            with self.subTest(mode=mode):
                self.assertEqual(tuple(item.replay for item in records), (1, 2))
                self.assertEqual(records[0].byte_length, records[1].byte_length)
                self.assertEqual(records[0].raw_sha256, records[1].raw_sha256)

    def test_execution_contract_preserves_ternary_boundaries(self) -> None:
        bundle = self.result.document(
            M32PublishedDocumentRole.TRACE_BUNDLE
        ).root
        contract = bundle["execution_contract"]
        self.assertEqual(contract["canonical_ternary_domain"], (-1, 0, 1))
        self.assertEqual(contract["canonical_ternary_notation"], "-1/0/1")
        self.assertEqual(
            contract["opposite_polarity_routes"],
            ((-1, 0, 1), (1, 0, -1)),
        )
        self.assertIs(contract["direct_opposite_transitions_allowed"], False)
        self.assertIs(contract["route_legs_separately_observable"], True)
        self.assertEqual(contract["scheduler_modes"], ("7/1", "1/7"))
        self.assertIs(contract["phase_derived_target_is_executed_state"], False)
        self.assertIs(
            contract["registered_target_is_final_executed_state"],
            False,
        )
        self.assertIs(
            contract["phase_order_and_coherence_capacity_interchangeable"],
            False,
        )
        self.assertEqual(
            contract["packed_cell_order"],
            "cell_0_least_significant",
        )
        self.assertEqual(len(contract["active_zero_roles"]), 8)

    def test_trace_profiles_and_record_digests_are_exact(self) -> None:
        traces = self.result.document(
            M32PublishedDocumentRole.TRACE_BUNDLE
        ).root["traces"]
        expected = {
            "7/1": {
                "scheduler_mode_code": 1,
                "source_tick_count": 16,
                "sample_record_count": 16,
                "bank_record_count": 16,
                "cell_record_count": 128,
                "request_record_count": 32,
                "record_count": 192,
                "active_zero_cell_observation_count": 115,
                "scheduler_state_counts": {"balance": 14, "commit": 2},
                "records_sha256": (
                    "bc412e6d548cb1d7f4a2264b526d6d98"
                    "ac669b75e59c03cd5dbc7cd88756f033"
                ),
            },
            "1/7": {
                "scheduler_mode_code": 2,
                "source_tick_count": 17,
                "sample_record_count": 17,
                "bank_record_count": 17,
                "cell_record_count": 136,
                "request_record_count": 34,
                "record_count": 204,
                "active_zero_cell_observation_count": 123,
                "scheduler_state_counts": {"excite": 3, "neutralize": 14},
                "records_sha256": (
                    "dfb28db5a8bcef2b43c83edd6b420a22"
                    "86f8f804cfbaead716c2647cffbdf1f5"
                ),
            },
        }
        self.assertEqual(
            tuple(trace["scheduler_mode"] for trace in traces),
            ("7/1", "1/7"),
        )
        for trace in traces:
            mode = trace["scheduler_mode"]
            profile = expected[mode]
            with self.subTest(mode=mode):
                for field, value in profile.items():
                    self.assertEqual(trace[field], value)
                self.assertEqual(
                    len(trace["records"]),
                    trace["source_tick_count"],
                )
                self.assertEqual(
                    _canonical_sha256(trace["records"]),
                    trace["records_sha256"],
                )
                self.assertEqual(
                    Counter(
                        record["sample"]["scheduler_state"]
                        for record in trace["records"]
                    ),
                    dict(trace["scheduler_state_counts"]),
                )

    def test_trace_coordinates_and_ternary_pairs_are_exact(self) -> None:
        traces = self.result.document(
            M32PublishedDocumentRole.TRACE_BUNDLE
        ).root["traces"]
        code_to_value = {0: 0, 1: 1, 3: -1}
        retained_domain: set[int] = set()
        for trace in traces:
            mode = trace["scheduler_mode"]
            for tick, record in enumerate(trace["records"]):
                with self.subTest(mode=mode, tick=tick):
                    self.assertEqual(record["source_tick"], tick)
                    self.assertEqual(record["sample"]["source_tick"], tick)
                    self.assertEqual(record["bank"]["source_tick"], tick)
                    self.assertEqual(
                        tuple(
                            cell["source_cell"]
                            for cell in record["cells"]
                        ),
                        tuple(range(8)),
                    )
                    self.assertEqual(
                        tuple(
                            request["request_lane"]
                            for request in record["requests"]
                        ),
                        (0, 1),
                    )
                    for cell in record["cells"]:
                        self.assertEqual(cell["source_tick"], tick)
                        for prefix in (
                            "source_target",
                            "registered_target",
                            "execution_target",
                            "retained_state",
                            "pending_target",
                        ):
                            self.assertEqual(
                                code_to_value[cell[f"{prefix}_code"]],
                                cell[f"{prefix}_value"],
                            )
                        retained_domain.add(cell["retained_state_value"])
                    for request in record["requests"]:
                        self.assertEqual(request["source_tick"], tick)
                        for prefix in ("phase_target", "execution_target"):
                            self.assertEqual(
                                code_to_value[request[f"{prefix}_code"]],
                                request[f"{prefix}_value"],
                            )
        self.assertEqual(retained_domain, {-1, 0, 1})

    def test_active_zero_routes_and_event_counters_are_exact(self) -> None:
        traces = self.result.document(
            M32PublishedDocumentRole.TRACE_BUNDLE
        ).root["traces"]
        expected_routes = {
            "7/1": (((9, 0),), ((15, 0),)),
            "1/7": (((10, 0),), ((16, 0),)),
        }
        active_zero_count = 0
        for trace in traces:
            mode = trace["scheduler_mode"]
            first: list[tuple[int, int]] = []
            second: list[tuple[int, int]] = []
            previous: dict[int, int] = {}
            for record in trace["records"]:
                sample = record["sample"]
                self.assertEqual(sample["actual_direct_events"], 0)
                self.assertEqual(sample["reserved_state_events"], 0)
                self.assertEqual(sample["queue_overflow_events"], 0)
                self.assertIs(sample["invariant_all_valid"], True)
                self.assertEqual(sample["invariant_flags_hex"], "3ff")
                for cell in record["cells"]:
                    retained = cell["retained_state_value"]
                    self.assertIs(cell["active_zero"], retained == 0)
                    active_zero_count += int(cell["active_zero"])
                    cell_index = cell["source_cell"]
                    previous_value = previous.get(cell_index)
                    self.assertFalse(
                        previous_value in {-1, 1}
                        and retained == -previous_value
                    )
                    previous[cell_index] = retained
                    coordinate = (record["source_tick"], cell_index)
                    if cell["first_route_leg"]:
                        first.append(coordinate)
                    if cell["second_route_leg"]:
                        second.append(coordinate)
            with self.subTest(mode=mode):
                self.assertEqual(
                    (tuple(first), tuple(second)),
                    expected_routes[mode],
                )
        self.assertEqual(active_zero_count, 238)
        self.assertEqual(self.result.direct_opposite_transition_count, 0)
        self.assertEqual(self.result.reserved_state_event_count, 0)
        self.assertEqual(self.result.queue_overflow_event_count, 0)

    def test_manifest_and_qualification_relations_are_exact(self) -> None:
        bundle = self.result.document(
            M32PublishedDocumentRole.TRACE_BUNDLE
        ).root
        manifest = self.result.document(
            M32PublishedDocumentRole.MANIFEST
        ).root
        qualification = self.result.document(
            M32PublishedDocumentRole.QUALIFICATION
        ).root
        self.assertEqual(bundle["source_boundary"]["source_commit"], M32_SOURCE_COMMIT)
        self.assertEqual(manifest["source_commit"], M32_SOURCE_COMMIT)
        self.assertEqual(qualification["source_commit"], M32_SOURCE_COMMIT)
        self.assertEqual(manifest["generated_file_count"], 2)
        self.assertEqual(manifest["source_identity_count"], 29)
        self.assertEqual(manifest["transcript_identity_count"], 4)
        self.assertEqual(
            manifest["source_identities"],
            bundle["source_boundary"]["source_identities"],
        )
        self.assertEqual(
            manifest["transcript_identities"],
            bundle["source_boundary"]["transcript_identities"],
        )
        self.assertEqual(qualification["check_count"], 38)
        self.assertEqual(qualification["passed_count"], 38)
        self.assertEqual(qualification["failed_count"], 0)
        self.assertEqual(len(qualification["checks"]), 38)
        self.assertTrue(
            all(check["status"] == "PASS" for check in qualification["checks"])
        )
        self.assertEqual(qualification["qualified_artifact_count"], 3)

    def test_document_lookup_rejects_string_alias(self) -> None:
        for role in M32PublishedDocumentRole:
            with self.subTest(role=role):
                self.assertIs(
                    self.result.document(role).identity.role,
                    role,
                )
        with self.assertRaisesRegex(
            M32PublishedBoundaryError,
            "role must be M32PublishedDocumentRole",
        ):
            self.result.document("trace_bundle")

    def test_result_rejects_rebinding(self) -> None:
        invalid = (
            (
                {"registry_revision": "m32-published-boundary-v2"},
                "registry revision",
            ),
            ({"documents": self.result.documents[::-1]}, "document order"),
            (
                {"source_identities": self.result.source_identities[:-1]},
                "source identity inventory",
            ),
            (
                {
                    "transcript_identities":
                    self.result.transcript_identities[::-1]
                },
                "transcript identity inventory",
            ),
            ({"source_commit": "0" * 40}, "source commit"),
            ({"trace_count": 1}, "trace count"),
            ({"source_tick_count": 32}, "source tick count"),
            ({"record_count": 395}, "record count"),
            (
                {"active_zero_cell_observation_count": 237},
                "active-zero observation count",
            ),
            (
                {"direct_opposite_transition_count": 1},
                "direct opposite transition count",
            ),
            (
                {"reserved_state_event_count": 1},
                "reserved-state event count",
            ),
            (
                {"queue_overflow_event_count": 1},
                "queue-overflow event count",
            ),
            (
                {"loaded_at": datetime(2026, 9, 9)},
                "timezone-aware UTC",
            ),
        )
        for changes, message in invalid:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M32PublishedBoundaryError,
                    message,
                ):
                    replace(self.result, **changes)

    def test_repeated_validation_preserves_published_identities(self) -> None:
        repeated = validate_m32_published_boundary(
            self.upstream_root,
            loaded_at=_EXACT_LOADED_AT,
        )
        self.assertEqual(
            tuple(
                (document.identity, document.raw_bytes, document.root)
                for document in repeated.documents
            ),
            tuple(
                (document.identity, document.raw_bytes, document.root)
                for document in self.result.documents
            ),
        )
        self.assertEqual(
            tuple(
                (
                    source.source_path,
                    source.byte_length,
                    source.raw_sha256,
                    source.source_artifact.raw_bytes,
                )
                for source in repeated.source_identities
            ),
            tuple(
                (
                    source.source_path,
                    source.byte_length,
                    source.raw_sha256,
                    source.source_artifact.raw_bytes,
                )
                for source in self.result.source_identities
            ),
        )
        self.assertEqual(
            repeated.transcript_identities,
            self.result.transcript_identities,
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
        validate_m32_published_boundary(
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
            relative = M32_PUBLISHED_DOCUMENT_IDENTITIES[1].source_path
            _flip_one_byte(root / relative)
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "raw identity mismatch",
            ):
                validate_m32_published_boundary(root)

    def test_one_byte_source_identity_tamper_is_rejected(self) -> None:
        with self.boundary_copy() as root:
            source = next(
                identity
                for identity in self.result.source_identities
                if identity.source_path
                not in {
                    document.source_path
                    for document in M32_PUBLISHED_DOCUMENT_IDENTITIES
                }
            )
            _flip_one_byte(root / source.source_path)
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "source identity mismatch",
            ):
                validate_m32_published_boundary(root)

    def test_missing_or_symlinked_document_is_rejected(self) -> None:
        relative = M32_PUBLISHED_DOCUMENT_IDENTITIES[0].source_path
        with self.boundary_copy() as root:
            (root / relative).unlink()
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "required regular upstream file is missing",
            ):
                validate_m32_published_boundary(root)

        with self.boundary_copy() as root:
            target = root / relative
            saved = target.with_suffix(".saved")
            target.rename(saved)
            try:
                target.symlink_to(saved.name)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "required regular upstream file is missing",
            ):
                validate_m32_published_boundary(root)

    def test_upstream_workflow_source_is_never_executed(self) -> None:
        with self.boundary_copy() as root:
            source = next(
                identity
                for identity in self.result.source_identities
                if identity.source_path.endswith(
                    "frp-m32-registered-target-boundary-workflow.yml"
                )
            )
            target = root / source.source_path
            marker = root / "execution-marker"
            target.write_text(
                "name: hostile\n"
                "on: workflow_dispatch\n"
                "jobs:\n"
                "  hostile:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: touch "
                f"{marker}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                M32PublishedBoundaryError,
                "source identity mismatch",
            ):
                validate_m32_published_boundary(root)
            self.assertFalse(marker.exists())

    def test_cli_reports_exact_read_only_boundary(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "artifact_auditor.m32_published_boundary_intake",
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
            "FRP Observatory M32 published boundary intake: PASS",
            "registry_revision=m32-published-boundary-v1",
            "published_documents=4",
            "published_document_bytes=458096",
            "source_commit=c0bc0fbc2c1c2e500b19d0ba84b3431a813e3941",
            "source_identities=29",
            "source_identity_bytes=442916",
            "transcript_identities=4",
            "transcript_identity_bytes=436132",
            "scheduler_traces=2",
            "source_ticks=33",
            "structured_trace_records=396",
            "active_zero_cell_observations=238",
            "balanced_ternary_notation=-1/0/1",
            "opposite_transition_routes=-1/0/1,1/0/-1",
            "direct_opposite_transitions=0",
            "reserved_state_events=0",
            "queue_overflow_events=0",
            "transient_workflow_artifact_reads=forbidden",
            "record_normalization=forbidden",
            "source_mutation=forbidden",
            "downstream_writeback=forbidden",
        )
        self.assertEqual(tuple(output), expected)


if __name__ == "__main__":
    unittest.main()
