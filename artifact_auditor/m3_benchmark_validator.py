"""Read-only checks for ``frp.m3.benchmark_matrix.v1.7.0``.

The M3 benchmark matrix is validated as its own measurement contour. This
module does not execute producers, reinterpret benchmark values, or merge the
matrix with structured output, M15, architecture-comparison, or hardware-
sensitivity evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from parsers.artifact_dispatch import (
    ArtifactClassification,
    DispatchedArtifact,
    RegistrationStatus,
)
from parsers.json_artifact import JsonValue, ParsedJsonArtifact

from .audit_report import CheckOutcome, SourceLocation, ValidationCategory
from .validation_core import ValidationCheckSpec


__all__ = [
    "M3BenchmarkValidation",
    "M3BenchmarkValidationError",
    "validate_m3_benchmark",
]


_SCHEMA = "frp.m3.benchmark_matrix.v1.7.0"
_KIND = "benchmark_matrix"
_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_TOP_LEVEL_FIELDS = frozenset(
    {"schema", "kind", "version", "milestone", "rows"}
)
_ARCHITECTURES = (
    "frp_v1_6_0_m14_floating_semantic_reference",
    "frp_v1_7_0_quantized_hardware_shadow",
    "frp_v1_7_0_cycle_exact_vector_package",
    "frp_v1_7_0_systemverilog_correlation_contract",
    "frp_v1_7_0_qualification_closure",
)
_COMMON_FIELDS = frozenset(
    {
        "architecture",
        "numeric_domain",
        "cycle_exact_integer_trace",
        "hardware_facing_encoding",
    }
)
_ROW_FIELD_SETS = (
    _COMMON_FIELDS | {"interaction_scaling"},
    _COMMON_FIELDS
    | {
        "interaction_scaling",
        "state_sequence_match",
        "scheduler_sequence_match",
        "C_minus_P_sign_match",
    },
    _COMMON_FIELDS | {"vector_repeat_match"},
    _COMMON_FIELDS | {"comparison_rule"},
    _COMMON_FIELDS | {"artifact_layers"},
)


class M3BenchmarkValidationError(ValueError):
    """Raised when a validator input violates routing invariants."""


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: object) -> bool:
    return _integer(value) or isinstance(value, Decimal)


def _rows(
    value: object,
) -> tuple[Mapping[str, JsonValue], ...] | None:
    if isinstance(value, tuple) and all(
        isinstance(row, Mapping) for row in value
    ):
        return value
    return None


def _spec(
    code: str,
    category: ValidationCategory,
    valid: bool,
    path: str,
) -> ValidationCheckSpec:
    label = code.replace("_", " ")
    result = "matches" if valid else "does not match"
    return ValidationCheckSpec(
        check_code=code,
        category=category,
        outcome=CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        message=(
            f"The {label} {result} the registered upstream contract."
        ),
        source_locations=(SourceLocation(json_path=path),),
        upstream_rule_reference="docs/output_schema.md",
    )


def _parsed(dispatched: DispatchedArtifact) -> ParsedJsonArtifact:
    if not isinstance(dispatched, DispatchedArtifact):
        raise M3BenchmarkValidationError(
            "dispatched must be a DispatchedArtifact"
        )
    record = dispatched.compatibility_record
    if (
        dispatched.classification is not ArtifactClassification.JSON
        or dispatched.registration.status
        is not RegistrationStatus.REGISTERED
        or record is None
        or record.identifier != _SCHEMA
        or record.artifact_kind != _KIND
        or not isinstance(dispatched.parsed_artifact, ParsedJsonArtifact)
    ):
        raise M3BenchmarkValidationError(
            "artifact is not registered M3 benchmark matrix v1.7.0"
        )
    return dispatched.parsed_artifact


def _envelope(root: Mapping[str, JsonValue]) -> bool:
    return (
        root.get("schema") == _SCHEMA
        and root.get("kind") == _KIND
        and root.get("version") == _VERSION
        and root.get("milestone") == _MILESTONE
    )


def _top_level_types(root: Mapping[str, JsonValue]) -> bool:
    return (
        all(
            isinstance(root.get(field), str)
            for field in ("schema", "kind", "version", "milestone")
        )
        and isinstance(root.get("rows"), tuple)
    )


def _row_field_sets(
    rows: tuple[Mapping[str, JsonValue], ...] | None,
) -> bool:
    return rows is not None and len(rows) == len(_ROW_FIELD_SETS) and all(
        frozenset(row) == expected
        for row, expected in zip(rows, _ROW_FIELD_SETS, strict=True)
    )


def _row_types(
    rows: tuple[Mapping[str, JsonValue], ...] | None,
) -> bool:
    if rows is None or len(rows) != 5:
        return False
    for row in rows:
        if not all(
            isinstance(row.get(field), str)
            for field in ("architecture", "numeric_domain")
        ):
            return False
        if not all(
            isinstance(row.get(field), bool)
            for field in (
                "cycle_exact_integer_trace",
                "hardware_facing_encoding",
            )
        ):
            return False
    return (
        isinstance(rows[0].get("interaction_scaling"), str)
        and isinstance(rows[1].get("interaction_scaling"), str)
        and all(
            _number(rows[1].get(field))
            for field in (
                "state_sequence_match",
                "scheduler_sequence_match",
                "C_minus_P_sign_match",
            )
        )
        and _number(rows[2].get("vector_repeat_match"))
        and isinstance(rows[3].get("comparison_rule"), str)
        and _integer(rows[4].get("artifact_layers"))
    )


def _row(
    rows: tuple[Mapping[str, JsonValue], ...] | None,
    index: int,
) -> Mapping[str, JsonValue]:
    if rows is None or len(rows) <= index:
        return {}
    return rows[index]


def _matches(
    row: Mapping[str, JsonValue],
    expected: Mapping[str, object],
) -> bool:
    return all(row.get(field) == value for field, value in expected.items())


def _check_specs(
    root: Mapping[str, JsonValue],
) -> tuple[ValidationCheckSpec, ...]:
    rows = _rows(root.get("rows"))
    row0 = _row(rows, 0)
    row1 = _row(rows, 1)
    row2 = _row(rows, 2)
    row3 = _row(rows, 3)
    row4 = _row(rows, 4)

    architecture_order = rows is not None and tuple(
        row.get("architecture") for row in rows
    ) == _ARCHITECTURES
    progression = rows is not None and len(rows) == 5 and (
        row0.get("cycle_exact_integer_trace") is False
        and row0.get("hardware_facing_encoding") is False
        and all(
            row.get("cycle_exact_integer_trace") is True
            and row.get("hardware_facing_encoding") is True
            for row in rows[1:]
        )
    )

    results = (
        (
            "m3_benchmark_envelope",
            ValidationCategory.IDENTITY,
            _envelope(root),
            "$",
        ),
        (
            "m3_benchmark_top_level_fields",
            ValidationCategory.STRUCTURE,
            frozenset(root) == _TOP_LEVEL_FIELDS,
            "$",
        ),
        (
            "m3_benchmark_top_level_types",
            ValidationCategory.TYPE,
            _top_level_types(root),
            "$",
        ),
        (
            "m3_benchmark_row_count",
            ValidationCategory.STRUCTURE,
            rows is not None and len(rows) == 5,
            "$.rows",
        ),
        (
            "m3_benchmark_row_field_sets",
            ValidationCategory.STRUCTURE,
            _row_field_sets(rows),
            "$.rows",
        ),
        (
            "m3_benchmark_row_types",
            ValidationCategory.TYPE,
            _row_types(rows),
            "$.rows",
        ),
        (
            "m3_benchmark_architecture_order",
            ValidationCategory.ORDERING,
            architecture_order,
            "$.rows",
        ),
        (
            "m3_benchmark_progression_flags",
            ValidationCategory.ALLOWED_VALUE,
            progression,
            "$.rows",
        ),
        (
            "m3_floating_reference_markers",
            ValidationCategory.ALLOWED_VALUE,
            _matches(
                row0,
                {
                    "numeric_domain": "floating semantic reference",
                    "interaction_scaling": (
                        "O(N log N) hierarchical reference path"
                    ),
                },
            ),
            "$.rows[0]",
        ),
        (
            "m3_quantized_shadow_markers",
            ValidationCategory.ALLOWED_VALUE,
            _matches(
                row1,
                {
                    "numeric_domain": (
                        "S32Q16 / S32Q30 / PHASE_U32 / GAMMA_S32"
                    ),
                    "interaction_scaling": (
                        "O(N^2) shadow evaluation with exact dyadic weights"
                    ),
                },
            ),
            "$.rows[1]",
        ),
        (
            "m3_semantic_correlation_markers",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _matches(
                row1,
                {
                    "state_sequence_match": Decimal("1.0"),
                    "scheduler_sequence_match": Decimal("1.0"),
                    "C_minus_P_sign_match": Decimal("1.0"),
                },
            ),
            "$.rows[1]",
        ),
        (
            "m3_vector_package_markers",
            ValidationCategory.ALLOWED_VALUE,
            _matches(
                row2,
                {
                    "numeric_domain": "integer and hexadecimal vectors",
                    "vector_repeat_match": Decimal("1.0"),
                },
            ),
            "$.rows[2]",
        ),
        (
            "m3_correlation_contract_markers",
            ValidationCategory.ALLOWED_VALUE,
            _matches(
                row3,
                {
                    "numeric_domain": "exact integer comparison",
                    "comparison_rule": "actual == expected",
                },
            ),
            "$.rows[3]",
        ),
        (
            "m3_qualification_closure_markers",
            ValidationCategory.QUALIFICATION_EVIDENCE,
            _matches(
                row4,
                {
                    "numeric_domain": (
                        "semantic correlation plus exact integer replay"
                    ),
                    "artifact_layers": 10,
                },
            ),
            "$.rows[4]",
        ),
    )
    return tuple(
        _spec(code, category, valid, path)
        for code, category, valid, path in results
    )


@dataclass(frozen=True, slots=True)
class M3BenchmarkValidation:
    """Immutable validation result for one M3 benchmark matrix."""

    dispatched_artifact: DispatchedArtifact
    check_specs: tuple[ValidationCheckSpec, ...]
    row_count: int

    def __post_init__(self) -> None:
        parsed = _parsed(self.dispatched_artifact)
        rows = _rows(parsed.root.get("rows"))
        if not self.check_specs or any(
            not isinstance(spec, ValidationCheckSpec)
            for spec in self.check_specs
        ):
            raise M3BenchmarkValidationError(
                "check_specs must contain validation specifications"
            )
        if not _integer(self.row_count) or self.row_count < 0:
            raise M3BenchmarkValidationError(
                "row_count must be a nonnegative integer"
            )
        observed_count = len(rows) if rows is not None else 0
        if self.row_count != observed_count:
            raise M3BenchmarkValidationError(
                "row_count must match the parsed rows collection"
            )

    @property
    def valid(self) -> bool:
        """Return whether every mandatory check passed."""

        return all(
            not spec.mandatory or spec.outcome is CheckOutcome.PASS
            for spec in self.check_specs
        )


def validate_m3_benchmark(
    dispatched: DispatchedArtifact,
) -> M3BenchmarkValidation:
    """Validate one registered M3 benchmark matrix without mutation."""

    parsed = _parsed(dispatched)
    rows = _rows(parsed.root.get("rows"))
    return M3BenchmarkValidation(
        dispatched_artifact=dispatched,
        check_specs=_check_specs(parsed.root),
        row_count=len(rows) if rows is not None else 0,
    )
