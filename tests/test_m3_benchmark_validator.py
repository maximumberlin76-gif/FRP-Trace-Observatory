"""Tests for read-only M3 benchmark-matrix validation."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from artifact_auditor.audit_report import (
    CheckOutcome,
    ValidationCategory,
)
from artifact_auditor.m3_benchmark_validator import (
    M3BenchmarkValidation,
    M3BenchmarkValidationError,
    validate_m3_benchmark,
)
from parsers.artifact_dispatch import (
    DispatchedArtifact,
    dispatch_artifact,
)
from parsers.source_artifact import capture_source_bytes


_SCHEMA = "frp.m3.benchmark_matrix.v1.7.0"
_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_CHECK_CODES = (
    "m3_benchmark_envelope",
    "m3_benchmark_top_level_fields",
    "m3_benchmark_top_level_types",
    "m3_benchmark_row_count",
    "m3_benchmark_row_field_sets",
    "m3_benchmark_row_types",
    "m3_benchmark_architecture_order",
    "m3_benchmark_progression_flags",
    "m3_floating_reference_markers",
    "m3_quantized_shadow_markers",
    "m3_semantic_correlation_markers",
    "m3_vector_package_markers",
    "m3_correlation_contract_markers",
    "m3_qualification_closure_markers",
)


def _matrix() -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "kind": "benchmark_matrix",
        "version": _VERSION,
        "milestone": _MILESTONE,
        "rows": [
            {
                "architecture": (
                    "frp_v1_6_0_m14_floating_semantic_reference"
                ),
                "numeric_domain": "floating semantic reference",
                "cycle_exact_integer_trace": False,
                "hardware_facing_encoding": False,
                "interaction_scaling": (
                    "O(N log N) hierarchical reference path"
                ),
            },
            {
                "architecture": (
                    "frp_v1_7_0_quantized_hardware_shadow"
                ),
                "numeric_domain": (
                    "S32Q16 / S32Q30 / PHASE_U32 / GAMMA_S32"
                ),
                "cycle_exact_integer_trace": True,
                "hardware_facing_encoding": True,
                "interaction_scaling": (
                    "O(N^2) shadow evaluation with exact dyadic weights"
                ),
                "state_sequence_match": 1.0,
                "scheduler_sequence_match": 1.0,
                "C_minus_P_sign_match": 1.0,
            },
            {
                "architecture": (
                    "frp_v1_7_0_cycle_exact_vector_package"
                ),
                "numeric_domain": "integer and hexadecimal vectors",
                "cycle_exact_integer_trace": True,
                "hardware_facing_encoding": True,
                "vector_repeat_match": 1.0,
            },
            {
                "architecture": (
                    "frp_v1_7_0_systemverilog_correlation_contract"
                ),
                "numeric_domain": "exact integer comparison",
                "cycle_exact_integer_trace": True,
                "hardware_facing_encoding": True,
                "comparison_rule": "actual == expected",
            },
            {
                "architecture": (
                    "frp_v1_7_0_qualification_closure"
                ),
                "numeric_domain": (
                    "semantic correlation plus exact integer replay"
                ),
                "cycle_exact_integer_trace": True,
                "hardware_facing_encoding": True,
                "artifact_layers": 10,
            },
        ],
    }


def _dispatch(
    root: dict[str, object],
    *,
    filename: str = "benchmark_matrix.json",
) -> DispatchedArtifact:
    text = json.dumps(
        root,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    source = capture_source_bytes(
        (text + "\n").encode("utf-8"),
        source_filename=filename,
        source_path=f"published/{filename}",
    )
    return dispatch_artifact(source)


def _rows(root: dict[str, object]) -> list[dict[str, object]]:
    rows = root["rows"]
    if not isinstance(rows, list):
        raise AssertionError("test matrix rows must be a list")
    return rows


def _failed_codes(
    validation: M3BenchmarkValidation,
) -> tuple[str, ...]:
    return tuple(
        spec.check_code
        for spec in validation.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


class ValidM3BenchmarkTests(unittest.TestCase):
    """Exercise the exact registered M3 benchmark contract."""

    def test_valid_matrix_produces_ordered_immutable_result(self) -> None:
        dispatched = _dispatch(_matrix())
        original_bytes = dispatched.source_artifact.raw_bytes

        validation = validate_m3_benchmark(dispatched)

        self.assertIs(validation.dispatched_artifact, dispatched)
        self.assertEqual(validation.row_count, 5)
        self.assertTrue(validation.valid)
        self.assertEqual(_failed_codes(validation), ())
        self.assertEqual(
            tuple(
                spec.check_code for spec in validation.check_specs
            ),
            _CHECK_CODES,
        )
        self.assertTrue(
            all(
                spec.outcome is CheckOutcome.PASS
                for spec in validation.check_specs
            )
        )
        self.assertEqual(
            dispatched.source_artifact.raw_bytes,
            original_bytes,
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(validation, "row_count", 4)

    def test_check_categories_and_locations_remain_separate(self) -> None:
        validation = validate_m3_benchmark(_dispatch(_matrix()))

        self.assertEqual(
            tuple(spec.category for spec in validation.check_specs),
            (
                ValidationCategory.IDENTITY,
                ValidationCategory.STRUCTURE,
                ValidationCategory.TYPE,
                ValidationCategory.STRUCTURE,
                ValidationCategory.STRUCTURE,
                ValidationCategory.TYPE,
                ValidationCategory.ORDERING,
                ValidationCategory.ALLOWED_VALUE,
                ValidationCategory.ALLOWED_VALUE,
                ValidationCategory.ALLOWED_VALUE,
                ValidationCategory.QUALIFICATION_EVIDENCE,
                ValidationCategory.ALLOWED_VALUE,
                ValidationCategory.ALLOWED_VALUE,
                ValidationCategory.QUALIFICATION_EVIDENCE,
            ),
        )
        self.assertEqual(
            tuple(
                spec.source_locations[0].json_path
                for spec in validation.check_specs
            ),
            (
                "$",
                "$",
                "$",
                "$.rows",
                "$.rows",
                "$.rows",
                "$.rows",
                "$.rows",
                "$.rows[0]",
                "$.rows[1]",
                "$.rows[1]",
                "$.rows[2]",
                "$.rows[3]",
                "$.rows[4]",
            ),
        )
        self.assertTrue(
            all(
                spec.upstream_rule_reference
                == "docs/output_schema.md"
                for spec in validation.check_specs
            )
        )


class EnvelopeAndStructureFailureTests(unittest.TestCase):
    """Keep envelope, structure, and type failures distinguishable."""

    def test_envelope_and_extra_field_fail_independently(self) -> None:
        cases = (
            (
                "version",
                lambda root: root.__setitem__("version", "1.7.1"),
                ("m3_benchmark_envelope",),
            ),
            (
                "extra field",
                lambda root: root.__setitem__("qualification", {}),
                ("m3_benchmark_top_level_fields",),
            ),
            (
                "milestone type",
                lambda root: root.__setitem__("milestone", 15),
                (
                    "m3_benchmark_envelope",
                    "m3_benchmark_top_level_types",
                ),
            ),
        )

        for name, mutate, expected in cases:
            with self.subTest(name=name):
                root = _matrix()
                mutate(root)

                validation = validate_m3_benchmark(_dispatch(root))

                self.assertEqual(_failed_codes(validation), expected)
                self.assertFalse(validation.valid)

    def test_row_count_and_field_sets_are_checked_exactly(self) -> None:
        short = _matrix()
        _rows(short).pop()
        extra = _matrix()
        _rows(extra)[0]["observatory_note"] = "derived"
        cases = (
            (
                short,
                (
                    "m3_benchmark_row_count",
                    "m3_benchmark_row_field_sets",
                    "m3_benchmark_row_types",
                    "m3_benchmark_architecture_order",
                    "m3_benchmark_progression_flags",
                    "m3_qualification_closure_markers",
                ),
            ),
            (
                extra,
                ("m3_benchmark_row_field_sets",),
            ),
        )

        for root, expected in cases:
            with self.subTest(expected=expected):
                validation = validate_m3_benchmark(_dispatch(root))

                self.assertEqual(_failed_codes(validation), expected)

    def test_row_scalar_types_reject_boolean_numeric_aliases(self) -> None:
        text_match = _matrix()
        _rows(text_match)[1]["state_sequence_match"] = "1.0"
        boolean_match = _matrix()
        _rows(boolean_match)[2]["vector_repeat_match"] = True
        integer_flag = _matrix()
        _rows(integer_flag)[2]["cycle_exact_integer_trace"] = 1
        cases = (
            (
                text_match,
                (
                    "m3_benchmark_row_types",
                    "m3_semantic_correlation_markers",
                ),
            ),
            (
                boolean_match,
                ("m3_benchmark_row_types",),
            ),
            (
                integer_flag,
                (
                    "m3_benchmark_row_types",
                    "m3_benchmark_progression_flags",
                ),
            ),
        )

        for root, expected in cases:
            with self.subTest(expected=expected):
                validation = validate_m3_benchmark(_dispatch(root))

                self.assertEqual(_failed_codes(validation), expected)


class OrderingAndMarkerFailureTests(unittest.TestCase):
    """Exercise progression ordering and every published row marker."""

    def test_architecture_order_and_progression_are_independent(self) -> None:
        reordered = _matrix()
        first = _rows(reordered)[0]
        second = _rows(reordered)[1]
        first["architecture"], second["architecture"] = (
            second["architecture"],
            first["architecture"],
        )
        deferred = _matrix()
        _rows(deferred)[2]["hardware_facing_encoding"] = False
        cases = (
            (
                reordered,
                ("m3_benchmark_architecture_order",),
            ),
            (
                deferred,
                ("m3_benchmark_progression_flags",),
            ),
        )

        for root, expected in cases:
            with self.subTest(expected=expected):
                validation = validate_m3_benchmark(_dispatch(root))

                self.assertEqual(_failed_codes(validation), expected)

    def test_each_published_marker_has_a_dedicated_failure(self) -> None:
        cases = (
            (
                0,
                "numeric_domain",
                "floating execution",
                "m3_floating_reference_markers",
            ),
            (
                1,
                "interaction_scaling",
                "O(N)",
                "m3_quantized_shadow_markers",
            ),
            (
                1,
                "C_minus_P_sign_match",
                0.5,
                "m3_semantic_correlation_markers",
            ),
            (
                2,
                "vector_repeat_match",
                0.5,
                "m3_vector_package_markers",
            ),
            (
                3,
                "comparison_rule",
                "actual ~= expected",
                "m3_correlation_contract_markers",
            ),
            (
                4,
                "artifact_layers",
                9,
                "m3_qualification_closure_markers",
            ),
        )

        for index, field, value, expected in cases:
            with self.subTest(index=index, field=field):
                root = _matrix()
                _rows(root)[index][field] = value

                validation = validate_m3_benchmark(_dispatch(root))

                self.assertEqual(_failed_codes(validation), (expected,))


class RoutingAndResultInvariantTests(unittest.TestCase):
    """Reject unregistered inputs and inconsistent result metadata."""

    def test_validator_rejects_non_m3_dispatch_routes(self) -> None:
        wrong_kind = _matrix()
        wrong_kind["kind"] = "demo"
        wrong_schema = _matrix()
        wrong_schema["schema"] = "frp.m3.benchmark_matrix.v1.6.0"
        text_source = capture_source_bytes(
            b"not json\n",
            source_filename="benchmark_matrix.txt",
        )
        cases = (
            "not dispatched",
            _dispatch(wrong_kind),
            _dispatch(wrong_schema),
            dispatch_artifact(text_source),
        )

        for dispatched in cases:
            with self.subTest(dispatched=type(dispatched).__name__):
                with self.assertRaises(M3BenchmarkValidationError):
                    validate_m3_benchmark(dispatched)

    def test_result_rejects_invalid_specs_and_row_counts(self) -> None:
        validation = validate_m3_benchmark(_dispatch(_matrix()))
        cases = (
            (
                {"check_specs": ()},
                "check_specs must contain validation specifications",
            ),
            (
                {"check_specs": ("invalid",)},
                "check_specs must contain validation specifications",
            ),
            (
                {"row_count": -1},
                "row_count must be a nonnegative integer",
            ),
            (
                {"row_count": True},
                "row_count must be a nonnegative integer",
            ),
            (
                {"row_count": 4},
                "row_count must match the parsed rows collection",
            ),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    M3BenchmarkValidationError,
                    message,
                ):
                    replace(validation, **changes)

    def test_valid_property_reflects_mandatory_failures(self) -> None:
        validation = validate_m3_benchmark(_dispatch(_matrix()))
        failed = replace(
            validation.check_specs[0],
            outcome=CheckOutcome.FAIL,
        )
        changed = replace(
            validation,
            check_specs=(failed,) + validation.check_specs[1:],
        )

        self.assertFalse(changed.valid)
        self.assertTrue(validation.valid)


if __name__ == "__main__":
    unittest.main()
