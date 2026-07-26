"""Tests for read-only FRP M15 deterministic-package validation."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256

from artifact_auditor.audit_report import CheckOutcome
from artifact_auditor.deterministic_package_validator import (
    DeterministicPackageValidation,
    DeterministicPackageValidationError,
    validate_deterministic_package,
)
from parsers.artifact_dispatch import (
    DispatchedArtifact,
    dispatch_artifact,
)
from parsers.source_artifact import (
    SourceArtifact,
    capture_source_bytes,
)


_SCHEMA = "frp.m15.rtl_comparison_vector_package.v1.7.0"
_KIND = "rtl_comparison_vector_package"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_DIGEST_MANIFEST = "frp_m15_sha256_manifest.json"
_MEMBER_NAMES = tuple(
    sorted(
        """
        frp_m15_kernel_vectors.vec
        frp_m15_pending_routes.trace
        frp_m15_scheduler_free_vectors.vec
        frp_m15_scheduler_7_1_vectors.vec
        frp_m15_scheduler_1_7_vectors.vec
        frp_m15_full_correlation_vectors.vec
        frp_m15_cell_trace.vec
        frp_m15_reference_preload.json
        frp_m15_trig_lut_q30.vec
        frp_m15_sha256_manifest.json
        """.split()
    )
)
_INNER_MEMBER_NAMES = tuple(
    name for name in _MEMBER_NAMES if name != _DIGEST_MANIFEST
)
_ZERO_DIGEST = "0" * 64


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _source(name: str, raw_bytes: bytes) -> SourceArtifact:
    return capture_source_bytes(
        raw_bytes,
        source_filename=name,
        source_path=f"published/m15/{name}",
    )


def _member_sources() -> dict[str, SourceArtifact]:
    sources = {
        name: _source(name, f"fixture:{name}\n".encode())
        for name in _INNER_MEMBER_NAMES
    }
    inner_manifest = {
        name: sources[name].content_sha256
        for name in _INNER_MEMBER_NAMES
    }
    sources[_DIGEST_MANIFEST] = _source(
        _DIGEST_MANIFEST,
        _json_bytes(inner_manifest),
    )
    return dict(sorted(sources.items()))


def _aggregate_digest(
    sources: dict[str, SourceArtifact],
) -> str:
    digest = sha256()
    for name in _MEMBER_NAMES:
        digest.update(name.encode())
        digest.update(b"\x00")
        digest.update(sources[name].raw_bytes)
    return digest.hexdigest()


def _package_root(
    sources: dict[str, SourceArtifact],
) -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "kind": _KIND,
        "version": "1.7.0",
        "milestone": _MILESTONE,
        "vector_classes": [
            "kernel_transition_vectors",
            "scheduler_vectors",
            "full_correlation_vectors",
        ],
        "manifest": {
            "file_count": len(_MEMBER_NAMES),
            "files": [
                {
                    "name": name,
                    "size_bytes": sources[name].byte_length,
                    "sha256": sources[name].content_sha256,
                }
                for name in _MEMBER_NAMES
            ],
        },
        "deterministic_package_digest": _aggregate_digest(sources),
    }


def _dispatch(root: dict[str, object]) -> DispatchedArtifact:
    source = capture_source_bytes(
        _json_bytes(root),
        source_filename="rtl_comparison_vector_package.json",
        source_path="published/m15/rtl_comparison_vector_package.json",
    )
    return dispatch_artifact(source)


def _clone(root: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(root, ensure_ascii=False))


def _failed(
    result: DeterministicPackageValidation,
) -> tuple[str, ...]:
    return tuple(
        spec.check_code
        for spec in result.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


class DeterministicPackageValidatorTests(unittest.TestCase):
    """Exercise package inventory, manifests, digests, and result guards."""

    def test_complete_package_passes_without_source_mutation(self) -> None:
        sources = _member_sources()
        root = _package_root(sources)
        dispatched = _dispatch(root)
        outer_bytes = dispatched.source_artifact.raw_bytes
        member_bytes = {
            name: source.raw_bytes for name, source in sources.items()
        }

        result = validate_deterministic_package(dispatched, sources)

        self.assertEqual(len(result.check_specs), 79)
        self.assertEqual(result.matched_member_names, _MEMBER_NAMES)
        self.assertEqual(result.missing_member_names, ())
        self.assertEqual(result.unexpected_member_names, ())
        self.assertEqual(
            result.computed_package_sha256,
            root["deterministic_package_digest"],
        )
        self.assertEqual(_failed(result), ())
        self.assertEqual(result.failed_check_specs, ())
        self.assertTrue(result.valid)
        self.assertEqual(
            dispatched.source_artifact.raw_bytes,
            outer_bytes,
        )
        self.assertEqual(
            {
                name: source.raw_bytes
                for name, source in sources.items()
            },
            member_bytes,
        )

    def test_missing_and_unexpected_members_remain_explicit(self) -> None:
        sources = _member_sources()
        root = _package_root(sources)
        missing_name = "frp_m15_cell_trace.vec"
        incomplete = dict(sources)
        del incomplete[missing_name]

        missing = validate_deterministic_package(
            _dispatch(root),
            incomplete,
        )

        self.assertEqual(missing.missing_member_names, (missing_name,))
        self.assertEqual(missing.unexpected_member_names, ())
        self.assertIsNone(missing.computed_package_sha256)
        self.assertEqual(
            _failed(missing),
            (
                "m15_package_captured_members",
                "m15_package_member_presence",
                "m15_package_inner_member_digest",
                "m15_package_aggregate_digest",
            ),
        )

        unexpected_name = "observatory-derived.txt"
        extended = dict(sources)
        extended[unexpected_name] = _source(
            unexpected_name,
            b"derived view\n",
        )
        unexpected = validate_deterministic_package(
            _dispatch(root),
            extended,
        )

        self.assertEqual(unexpected.missing_member_names, ())
        self.assertEqual(
            unexpected.unexpected_member_names,
            (unexpected_name,),
        )
        self.assertEqual(
            unexpected.computed_package_sha256,
            root["deterministic_package_digest"],
        )
        self.assertEqual(
            _failed(unexpected),
            ("m15_package_captured_members",),
        )

    def test_outer_manifest_failures_are_independent(self) -> None:
        sources = _member_sources()
        base = _package_root(sources)

        wrong_count = _clone(base)
        wrong_count["manifest"]["file_count"] = 9
        count_result = validate_deterministic_package(
            _dispatch(wrong_count),
            sources,
        )
        self.assertEqual(
            _failed(count_result),
            (
                "m15_package_outer_manifest_shape",
                "m15_package_outer_file_count",
            ),
        )

        wrong_order = _clone(base)
        wrong_order["manifest"]["files"].reverse()
        order_result = validate_deterministic_package(
            _dispatch(wrong_order),
            sources,
        )
        self.assertEqual(
            _failed(order_result),
            ("m15_package_outer_member_order",),
        )

        wrong_size = _clone(base)
        wrong_size["manifest"]["files"][0]["size_bytes"] += 1
        size_result = validate_deterministic_package(
            _dispatch(wrong_size),
            sources,
        )
        self.assertEqual(
            _failed(size_result),
            ("m15_package_member_byte_length",),
        )

        wrong_digest = _clone(base)
        wrong_digest["manifest"]["files"][0]["sha256"] = _ZERO_DIGEST
        digest_result = validate_deterministic_package(
            _dispatch(wrong_digest),
            sources,
        )
        self.assertEqual(
            _failed(digest_result),
            ("m15_package_member_outer_digest",),
        )

    def test_inner_manifest_failures_do_not_change_member_bytes(self) -> None:
        sources = _member_sources()
        wrong_inner = {
            name: sources[name].content_sha256
            for name in _INNER_MEMBER_NAMES
        }
        wrong_inner[_INNER_MEMBER_NAMES[0]] = _ZERO_DIGEST
        wrong_sources = dict(sources)
        wrong_sources[_DIGEST_MANIFEST] = _source(
            _DIGEST_MANIFEST,
            _json_bytes(wrong_inner),
        )
        wrong_result = validate_deterministic_package(
            _dispatch(_package_root(wrong_sources)),
            wrong_sources,
        )
        self.assertEqual(
            _failed(wrong_result),
            ("m15_package_inner_member_digest",),
        )

        invalid_sources = dict(sources)
        invalid_sources[_DIGEST_MANIFEST] = _source(
            _DIGEST_MANIFEST,
            b"{invalid json\n",
        )
        invalid_result = validate_deterministic_package(
            _dispatch(_package_root(invalid_sources)),
            invalid_sources,
        )
        failures = _failed(invalid_result)
        self.assertEqual(
            failures[:3],
            (
                "m15_package_inner_manifest_json",
                "m15_package_inner_manifest_members",
                "m15_package_inner_manifest_shape",
            ),
        )
        self.assertEqual(
            failures[3:],
            ("m15_package_inner_member_digest",) * 9,
        )
        self.assertEqual(
            invalid_result.computed_package_sha256,
            _aggregate_digest(invalid_sources),
        )

    def test_declared_package_digest_is_checked_separately(self) -> None:
        sources = _member_sources()
        root = _package_root(sources)
        root["deterministic_package_digest"] = _ZERO_DIGEST

        mismatch = validate_deterministic_package(
            _dispatch(root),
            sources,
        )

        self.assertEqual(
            _failed(mismatch),
            ("m15_package_aggregate_digest",),
        )
        self.assertEqual(
            mismatch.computed_package_sha256,
            _aggregate_digest(sources),
        )

        root["deterministic_package_digest"] = "invalid"
        invalid = validate_deterministic_package(
            _dispatch(root),
            sources,
        )
        self.assertEqual(
            _failed(invalid),
            (
                "m15_package_declared_digest_syntax",
                "m15_package_aggregate_digest",
            ),
        )

    def test_input_and_result_invariants_are_enforced(self) -> None:
        sources = _member_sources()
        dispatched = _dispatch(_package_root(sources))
        plain = dispatch_artifact(
            capture_source_bytes(
                b"plain text\n",
                source_filename="plain.txt",
            )
        )
        for value in ("invalid", plain):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(
                    DeterministicPackageValidationError
                ):
                    validate_deterministic_package(value, sources)

        invalid_inventories = (
            [],
            {"../member.vec": next(iter(sources.values()))},
            {"member.vec": b"raw bytes"},
        )
        for inventory in invalid_inventories:
            with self.subTest(inventory=type(inventory).__name__):
                with self.assertRaises(
                    DeterministicPackageValidationError
                ):
                    validate_deterministic_package(
                        dispatched,
                        inventory,
                    )

        result = validate_deterministic_package(dispatched, sources)
        with self.assertRaises(DeterministicPackageValidationError):
            replace(
                result,
                member_sources=tuple(reversed(result.member_sources)),
            )
        with self.assertRaises(DeterministicPackageValidationError):
            replace(result, check_specs=())
        with self.assertRaises(DeterministicPackageValidationError):
            replace(
                result,
                missing_member_names=(_MEMBER_NAMES[0],),
            )
        with self.assertRaises(DeterministicPackageValidationError):
            replace(result, computed_package_sha256=None)
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "missing_member_names", ())
