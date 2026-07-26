"""Tests for read-only Comparative Architecture artifact validation."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from artifact_auditor.audit_report import CheckOutcome
from artifact_auditor.comparative_architecture_validator import (
    ComparativeArchitectureValidation,
    ComparativeArchitectureValidationError,
    validate_comparative_architecture,
)
from parsers.artifact_dispatch import (
    DispatchedArtifact,
    dispatch_artifact,
)
from parsers.source_artifact import capture_source_bytes


_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "comparative_architecture"
)
_COST_FILE = "normalized_cost_profile_v1.json"
_THERMAL_FILE = "thermal_proxy_profile_v1.json"
_COMPARISON_FILE = "reference_comparison_seed_76.json"
_COST_SCHEMA = "frp.benchmark.normalized_cost_profile.v1"
_THERMAL_SCHEMA = "frp.benchmark.thermal_proxy_profile.v1"
_COMPARISON_SCHEMA = "frp.benchmark.architecture_comparison.v1"
_SUITE = "FRP Comparative Architecture Benchmark Suite"
_THERMAL_EQUATION = (
    "ambient + (temperature - ambient) * thermal_decay "
    "+ normalized_cycle_cost * thermal_gain"
)
_ZERO_DIGEST = "0" * 64


def _load(filename: str) -> dict[str, object]:
    return json.loads((_FIXTURE_ROOT / filename).read_text())


def _json_bytes(root: dict[str, object]) -> bytes:
    return (
        json.dumps(
            root,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _dispatch(
    root: dict[str, object],
    filename: str,
) -> DispatchedArtifact:
    source = capture_source_bytes(
        _json_bytes(root),
        source_filename=filename,
        source_path=f"fixtures/comparative_architecture/{filename}",
    )
    return dispatch_artifact(source)


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _refresh_cost_digest(root: dict[str, object]) -> None:
    payload = {
        "schema": _COST_SCHEMA,
        "suite_name": _SUITE,
        "profile_name": root["profile_name"],
        "cost_unit": root["cost_unit"],
        "costs": root["costs"],
    }
    root["cost_profile_sha256"] = _canonical_digest(payload)


def _refresh_thermal_digest(root: dict[str, object]) -> None:
    payload = {
        "schema": _THERMAL_SCHEMA,
        "suite_name": _SUITE,
        "profile_name": root["profile_name"],
        "temperature_unit": root["temperature_unit"],
        "ambient_temperature_proxy": root["ambient_temperature_proxy"],
        "thermal_decay": root["thermal_decay"],
        "thermal_gain": root["thermal_gain"],
        "update_equation": _THERMAL_EQUATION,
    }
    root["thermal_profile_sha256"] = _canonical_digest(payload)


def _refresh_comparison_digest(root: dict[str, object]) -> None:
    payload = {
        key: value
        for key, value in root.items()
        if key != "comparison_package_sha256"
    }
    root["comparison_package_sha256"] = _canonical_digest(payload)


def _failed(
    result: ComparativeArchitectureValidation,
) -> tuple[str, ...]:
    return tuple(
        spec.check_code
        for spec in result.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


class ComparativeArchitectureValidatorTests(unittest.TestCase):
    """Exercise profiles, comparison relations, digests, and safeguards."""

    def test_canonical_fixtures_pass_without_source_mutation(self) -> None:
        cases = (
            (_COST_FILE, _COST_SCHEMA, 5),
            (_THERMAL_FILE, _THERMAL_SCHEMA, 5),
            (_COMPARISON_FILE, _COMPARISON_SCHEMA, 15),
        )
        for filename, schema, check_count in cases:
            with self.subTest(filename=filename):
                root = _load(filename)
                dispatched = _dispatch(root, filename)
                raw_bytes = dispatched.source_artifact.raw_bytes

                result = validate_comparative_architecture(dispatched)

                self.assertEqual(result.schema_identifier, schema)
                self.assertEqual(len(result.check_specs), check_count)
                self.assertEqual(_failed(result), ())
                self.assertTrue(result.valid)
                self.assertEqual(
                    dispatched.source_artifact.raw_bytes,
                    raw_bytes,
                )

    def test_cost_profile_checks_report_independent_failures(self) -> None:
        cases = (
            ("identity", "comparative_cost_profile_identity"),
            ("fields", "comparative_cost_profile_fields"),
            ("types", "comparative_cost_profile_types"),
            ("values", "comparative_cost_profile_values"),
            ("digest", "comparative_cost_profile_digest"),
        )
        for case, expected in cases:
            with self.subTest(check=expected):
                root = _load(_COST_FILE)
                if case == "identity":
                    root["suite_name"] = "Different Suite"
                elif case == "fields":
                    root["extra"] = True
                elif case == "types":
                    root["profile_name"] = 76
                    _refresh_cost_digest(root)
                elif case == "values":
                    root["costs"]["encoded_bit_toggle"] = -1
                    _refresh_cost_digest(root)
                else:
                    root["cost_profile_sha256"] = _ZERO_DIGEST

                result = validate_comparative_architecture(
                    _dispatch(root, _COST_FILE)
                )

                self.assertEqual(_failed(result), (expected,))
                self.assertFalse(result.valid)

    def test_thermal_profile_checks_report_independent_failures(self) -> None:
        cases = (
            ("identity", "comparative_thermal_profile_identity"),
            ("fields", "comparative_thermal_profile_fields"),
            ("types", "comparative_thermal_profile_types"),
            ("values", "comparative_thermal_profile_values"),
            ("digest", "comparative_thermal_profile_digest"),
        )
        for case, expected in cases:
            with self.subTest(check=expected):
                root = _load(_THERMAL_FILE)
                if case == "identity":
                    root["suite_name"] = "Different Suite"
                elif case == "fields":
                    root["extra"] = True
                elif case == "types":
                    root["profile_name"] = 76
                    _refresh_thermal_digest(root)
                elif case == "values":
                    root["thermal_decay"] = 1
                    _refresh_thermal_digest(root)
                else:
                    root["thermal_profile_sha256"] = _ZERO_DIGEST

                result = validate_comparative_architecture(
                    _dispatch(root, _THERMAL_FILE)
                )

                self.assertEqual(_failed(result), (expected,))
                self.assertFalse(result.valid)

    def test_comparison_top_level_checks_remain_distinct(self) -> None:
        cases = (
            ("identity", ("comparative_architecture_identity",)),
            (
                "types",
                (
                    "comparative_architecture_identity",
                    "comparative_architecture_top_level_types",
                ),
            ),
            (
                "fields",
                ("comparative_architecture_top_level_fields",),
            ),
            (
                "scheduler",
                ("comparative_architecture_scheduler",),
            ),
            ("order", ("comparative_architecture_order",)),
            (
                "workload",
                ("comparative_architecture_workload_profile",),
            ),
            (
                "matrix",
                ("comparative_architecture_matrix_projection",),
            ),
            (
                "integrity",
                ("comparative_architecture_integrity_vector",),
            ),
            (
                "qualification",
                ("comparative_architecture_qualification",),
            ),
            (
                "package_digest",
                ("comparative_architecture_package_digest",),
            ),
        )
        for case, expected in cases:
            with self.subTest(expected=expected):
                root = _load(_COMPARISON_FILE)
                if case == "identity":
                    root["frp_reference_version"] = "1.8.0"
                elif case == "types":
                    root["frp_reference_version"] = 76
                elif case == "fields":
                    root["extra"] = True
                elif case == "scheduler":
                    root["frp_scheduler"] = "free"
                elif case == "order":
                    root["architecture_order"].reverse()
                elif case == "workload":
                    root["workload_profile"]["issue_policy"] = "parallel"
                elif case == "matrix":
                    root["comparison_matrix"][0]["completion_ticks"] = 999
                elif case == "integrity":
                    root["integrity"]["status"] = "FAIL"
                elif case == "qualification":
                    root["qualification"]["winner_assertions"] = ["binary"]
                else:
                    root["comparison_package_sha256"] = _ZERO_DIGEST
                if case != "package_digest":
                    _refresh_comparison_digest(root)

                result = validate_comparative_architecture(
                    _dispatch(root, _COMPARISON_FILE)
                )

                self.assertEqual(_failed(result), expected)

    def test_comparison_profile_and_result_failures_are_explicit(self) -> None:
        cases = (
            (
                "embedded_profiles",
                (
                    "comparative_architecture_embedded_profiles",
                    "comparative_architecture_profile_digests",
                    "comparative_architecture_result_relations",
                ),
            ),
            (
                "profile_digests",
                ("comparative_architecture_profile_digests",),
            ),
            (
                "result_shapes",
                ("comparative_architecture_result_shapes",),
            ),
            (
                "result_values",
                (
                    "comparative_architecture_result_values",
                    "comparative_architecture_result_relations",
                    "comparative_architecture_matrix_projection",
                ),
            ),
            (
                "result_relations",
                (
                    "comparative_architecture_result_relations",
                    "comparative_architecture_matrix_projection",
                ),
            ),
        )
        for case, expected in cases:
            with self.subTest(expected=expected):
                root = _load(_COMPARISON_FILE)
                first = root["architectures"][0]
                if case == "embedded_profiles":
                    costs = root["cost_profile"]["costs"]
                    costs["encoded_bit_toggle"] = -1
                elif case == "profile_digests":
                    root["cost_profile_sha256"] = _ZERO_DIGEST
                    for architecture in root["architectures"]:
                        normalized = architecture["normalized_cost"]
                        normalized["cost_profile_sha256"] = _ZERO_DIGEST
                elif case == "result_shapes":
                    first["architecture_name"] = ""
                elif case == "result_values":
                    metrics = first["comparison_metrics"]
                    metrics["active_clock_fraction"] = 2
                else:
                    metrics = first["comparison_metrics"]
                    metrics["logical_state_changes"] = 131
                _refresh_comparison_digest(root)

                result = validate_comparative_architecture(
                    _dispatch(root, _COMPARISON_FILE)
                )

                self.assertEqual(_failed(result), expected)
                self.assertFalse(result.valid)

    def test_routing_and_result_invariants_are_enforced(self) -> None:
        plain = dispatch_artifact(
            capture_source_bytes(
                b"plain text\n",
                source_filename="plain.txt",
            )
        )
        for value in ("invalid", plain):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(
                    ComparativeArchitectureValidationError
                ):
                    validate_comparative_architecture(value)

        result = validate_comparative_architecture(
            _dispatch(_load(_COST_FILE), _COST_FILE)
        )
        with self.assertRaises(ComparativeArchitectureValidationError):
            replace(result, schema_identifier=_THERMAL_SCHEMA)
        with self.assertRaises(ComparativeArchitectureValidationError):
            replace(result, check_specs=())
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "schema_identifier", _THERMAL_SCHEMA)
