"""Tests for read-only Hardware-Informed Sensitivity validation."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from artifact_auditor.audit_report import CheckOutcome
from artifact_auditor.hardware_sensitivity_validator import (
    HardwareSensitivityValidation,
    HardwareSensitivityValidationError,
    validate_hardware_sensitivity,
)
from parsers.artifact_dispatch import (
    DispatchedArtifact,
    dispatch_artifact,
)
from parsers.source_artifact import capture_source_bytes


_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "hardware_sensitivity"
)
_PROFILE_FILE = "hardware_sensitivity_cost_profile_v1.json"
_COMPARISON_FILE = (
    "reference_comparison_seed_76_hardware_sensitivity_v1.json"
)
_PROFILE_SCHEMA = "frp.benchmark.hardware_sensitivity_cost_profile.v1"
_COMPARISON_SCHEMA = "frp.benchmark.hardware_sensitivity_comparison.v1"
_ZERO_DIGEST = "0" * 64


def _load(filename: str) -> dict[str, object]:
    path = _FIXTURE_ROOT / filename
    return json.loads(path.read_text(encoding="utf-8"))


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
        source_path=f"fixtures/hardware_sensitivity/{filename}",
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


def _refresh_digest(
    root: dict[str, object],
    digest_field: str,
) -> None:
    payload = {
        key: value
        for key, value in root.items()
        if key != digest_field
    }
    root[digest_field] = _canonical_digest(payload)


def _failed(
    result: HardwareSensitivityValidation,
) -> tuple[str, ...]:
    return tuple(
        spec.check_code
        for spec in result.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


class HardwareSensitivityValidatorTests(unittest.TestCase):
    """Exercise profiles, scenarios, evidence, digests, and safeguards."""

    def test_canonical_fixtures_pass_without_source_mutation(self) -> None:
        cases = (
            (_PROFILE_FILE, _PROFILE_SCHEMA, 11),
            (_COMPARISON_FILE, _COMPARISON_SCHEMA, 21),
        )
        for filename, schema, check_count in cases:
            with self.subTest(filename=filename):
                root = _load(filename)
                dispatched = _dispatch(root, filename)
                raw_bytes = dispatched.source_artifact.raw_bytes

                result = validate_hardware_sensitivity(dispatched)

                self.assertEqual(result.schema_identifier, schema)
                self.assertEqual(len(result.check_specs), check_count)
                self.assertEqual(_failed(result), ())
                self.assertTrue(result.valid)
                self.assertEqual(
                    dispatched.source_artifact.raw_bytes,
                    raw_bytes,
                )

    def test_profile_checks_report_independent_failures(self) -> None:
        cases = (
            ("identity", "hardware_sensitivity_profile_identity"),
            ("fields", "hardware_sensitivity_profile_fields"),
            (
                "normalization",
                "hardware_sensitivity_normalization_reference",
            ),
            ("reference", "hardware_sensitivity_reference_basis"),
            ("orders", "hardware_sensitivity_profile_orders"),
            ("coefficients", "hardware_sensitivity_coefficients"),
            ("vectors", "hardware_sensitivity_scenario_vectors"),
            (
                "evaluation",
                "hardware_sensitivity_evaluation_contract",
            ),
            (
                "validation",
                "hardware_sensitivity_validation_contract",
            ),
            (
                "digest_contract",
                "hardware_sensitivity_digest_contract",
            ),
            ("digest", "hardware_sensitivity_profile_digest"),
        )
        for case, expected in cases:
            with self.subTest(check=expected):
                root = _load(_PROFILE_FILE)
                if case == "identity":
                    root["suite_name"] = "Different Suite"
                elif case == "fields":
                    root["extra"] = True
                elif case == "normalization":
                    root["normalization_reference"]["normalized_weight"] = 2
                elif case == "reference":
                    root["reference_basis"][0]["author"] = ""
                elif case == "orders":
                    root["scenario_order"].reverse()
                elif case == "coefficients":
                    coefficient = root["coefficients"][
                        "encoded_bit_toggle"
                    ]
                    coefficient["lower_bound"] = -1
                elif case == "vectors":
                    vector = root["scenario_vectors"]["lower_bound"]
                    vector["encoded_bit_toggle"] = 0.5
                elif case == "evaluation":
                    contract = root["evaluation_contract"]
                    contract["winner_assertions"] = ["binary"]
                elif case == "validation":
                    contract = root["validation_contract"]
                    contract["winner_assertions"] = ["binary"]
                elif case == "digest_contract":
                    root["digest_contract"]["algorithm"] = "sha512"
                else:
                    root["cost_profile_sha256"] = _ZERO_DIGEST
                if case != "digest":
                    _refresh_digest(root, "cost_profile_sha256")

                result = validate_hardware_sensitivity(
                    _dispatch(root, _PROFILE_FILE)
                )

                self.assertEqual(_failed(result), (expected,))
                self.assertFalse(result.valid)

    def test_comparison_top_level_checks_remain_distinct(self) -> None:
        cases = (
            ("identity", ("hardware_sensitivity_comparison_identity",)),
            ("fields", ("hardware_sensitivity_comparison_fields",)),
            (
                "types",
                (
                    "hardware_sensitivity_comparison_identity",
                    "hardware_sensitivity_comparison_types",
                ),
            ),
            (
                "scheduler",
                ("hardware_sensitivity_comparison_scheduler",),
            ),
            ("order", ("hardware_sensitivity_comparison_order",)),
            (
                "workload",
                ("hardware_sensitivity_comparison_workload",),
            ),
            ("digest", ("hardware_sensitivity_package_digest",)),
        )
        for case, expected in cases:
            with self.subTest(expected=expected):
                root = _load(_COMPARISON_FILE)
                if case == "identity":
                    root["frp_reference_version"] = "1.8.0"
                elif case == "fields":
                    root["extra"] = True
                elif case == "types":
                    root["frp_reference_version"] = 76
                elif case == "scheduler":
                    root["frp_scheduler"] = "free"
                elif case == "order":
                    root["architecture_order"].reverse()
                elif case == "workload":
                    root["workload_profile"]["issue_policy"] = "parallel"
                else:
                    root[
                        "hardware_sensitivity_package_sha256"
                    ] = _ZERO_DIGEST
                if case != "digest":
                    _refresh_digest(
                        root,
                        "hardware_sensitivity_package_sha256",
                    )

                result = validate_hardware_sensitivity(
                    _dispatch(root, _COMPARISON_FILE)
                )

                self.assertEqual(_failed(result), expected)
                self.assertFalse(result.valid)

    def test_profile_binding_and_raw_ledger_failures_are_explicit(
        self,
    ) -> None:
        cases = (
            (
                "embedded_profile",
                ("hardware_sensitivity_embedded_profile",),
            ),
            (
                "profile_validation",
                (
                    "hardware_sensitivity_profile_validation",
                    "hardware_sensitivity_integrity_vector",
                    "hardware_sensitivity_qualification",
                ),
            ),
            (
                "baseline",
                (
                    "hardware_sensitivity_baseline_binding",
                    "hardware_sensitivity_integrity_vector",
                    "hardware_sensitivity_qualification",
                ),
            ),
            ("thermal", ("hardware_sensitivity_thermal_profile",)),
            (
                "raw_shapes",
                (
                    "hardware_sensitivity_raw_ledger_shapes",
                    "hardware_sensitivity_scenario_relations",
                ),
            ),
            ("raw_values", ("hardware_sensitivity_raw_ledger_values",)),
            (
                "raw_relations",
                ("hardware_sensitivity_raw_ledger_relations",),
            ),
            (
                "raw_digest",
                ("hardware_sensitivity_raw_trace_set_digest",),
            ),
        )
        for case, expected in cases:
            with self.subTest(expected=expected):
                root = _load(_COMPARISON_FILE)
                if case == "embedded_profile":
                    profile = root["hardware_sensitivity_profile"]
                    profile["profile_name"] = "different"
                elif case == "profile_validation":
                    root["profile_validation"]["status"] = "FAIL"
                elif case == "baseline":
                    root["baseline_binding"]["status"] = "FAIL"
                elif case == "thermal":
                    root["thermal_profile"]["thermal_decay"] = 1
                elif case == "raw_shapes":
                    ledger = root["raw_trace_ledger"][0]
                    ledger["architecture_name"] = ""
                elif case == "raw_values":
                    ledger = root["raw_trace_ledger"][0]
                    metrics = ledger["architecture_specific_metrics"]
                    metrics["direct_binary_switches"] = -1
                elif case == "raw_relations":
                    ledger = root["raw_trace_ledger"][0]
                    ledger["processor_cycles"] += 1
                else:
                    root["raw_trace_set_sha256"] = _ZERO_DIGEST
                _refresh_digest(
                    root,
                    "hardware_sensitivity_package_sha256",
                )

                result = validate_hardware_sensitivity(
                    _dispatch(root, _COMPARISON_FILE)
                )

                self.assertEqual(_failed(result), expected)
                self.assertFalse(result.valid)

    def test_scenario_and_aggregate_failures_are_explicit(self) -> None:
        cases = (
            (
                "scenario_shapes",
                (
                    "hardware_sensitivity_scenario_shapes",
                    "hardware_sensitivity_scenario_values",
                    "hardware_sensitivity_scenario_relations",
                ),
            ),
            (
                "scenario_values",
                (
                    "hardware_sensitivity_scenario_values",
                    "hardware_sensitivity_scenario_relations",
                ),
            ),
            (
                "scenario_relations",
                ("hardware_sensitivity_scenario_relations",),
            ),
            (
                "ranking",
                ("hardware_sensitivity_ranking_stability",),
            ),
            (
                "integrity",
                ("hardware_sensitivity_integrity_vector",),
            ),
            (
                "qualification",
                (
                    "hardware_sensitivity_integrity_vector",
                    "hardware_sensitivity_qualification",
                ),
            ),
        )
        for case, expected in cases:
            with self.subTest(expected=expected):
                root = _load(_COMPARISON_FILE)
                scenario = root["scenarios"][0]
                if case == "scenario_shapes":
                    scenario["extra"] = True
                elif case == "scenario_values":
                    architecture = scenario["architectures"][0]
                    metrics = architecture["comparison_metrics"]
                    metrics["active_clock_fraction"] = 2
                elif case == "scenario_relations":
                    matrix = scenario["comparison_matrix"][0]
                    matrix["completion_ticks"] = 999
                elif case == "ranking":
                    stability = root["ranking_stability"]
                    stability["ranking_stable"] = not stability[
                        "ranking_stable"
                    ]
                elif case == "integrity":
                    root["integrity"]["status"] = "FAIL"
                else:
                    qualification = root["qualification"]
                    qualification["winner_assertions"] = ["binary"]
                _refresh_digest(
                    root,
                    "hardware_sensitivity_package_sha256",
                )

                result = validate_hardware_sensitivity(
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
                    HardwareSensitivityValidationError
                ):
                    validate_hardware_sensitivity(value)

        result = validate_hardware_sensitivity(
            _dispatch(_load(_PROFILE_FILE), _PROFILE_FILE)
        )
        with self.assertRaises(HardwareSensitivityValidationError):
            replace(result, schema_identifier=_COMPARISON_SCHEMA)
        with self.assertRaises(HardwareSensitivityValidationError):
            replace(result, check_specs=())
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "schema_identifier", _COMPARISON_SCHEMA)
