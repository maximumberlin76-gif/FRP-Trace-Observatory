"""Exact upstream schema and format identifier compatibility registry.

Registry membership records audited identity and routing metadata only. It
does not claim schema validation, execute producers, or redefine FRP
semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


__all__ = [
    "AUDITED_UPSTREAM_RELEASE",
    "ArtifactFormat",
    "CompatibilityRecord",
    "COMPATIBILITY_RECORDS",
    "IdentifierField",
    "MeasurementContour",
    "ObservatoryMode",
    "RegistryError",
    "SchemaEvidenceKind",
    "UnsupportedArtifactKindError",
    "UnknownArtifactIdentifierError",
    "records_for_identifier",
    "resolve_compatibility_record",
]


AUDITED_UPSTREAM_RELEASE: Final = "v1.8.0"


class ArtifactFormat(StrEnum):
    """Outer artifact formats present in the audited compatibility set."""

    JSON = "json"
    M15_VECTOR_TEXT = "frp_m15_vector_text"


class IdentifierField(StrEnum):
    """Exact field that carries an upstream contract identifier."""

    SCHEMA = "schema"
    FORMAT_VERSION = "format_version"


class MeasurementContour(StrEnum):
    """Non-interchangeable FRP measurement and qualification contours."""

    STRUCTURED_OUTPUT = "structured_output"
    M3_BENCHMARK_MATRIX = "m3_benchmark_matrix"
    M15_IMPLEMENTATION_MAPPING = "m15_implementation_mapping"
    COMPARATIVE_ARCHITECTURE = "comparative_architecture_benchmark_suite"
    HARDWARE_SENSITIVITY = "hardware_informed_sensitivity_qualification"


class ObservatoryMode(StrEnum):
    """Independent user modes that may consume a compatibility record."""

    TRACE_EXPLORER = "trace_explorer"
    TERNARY_TRANSITION_VISUALIZER = "ternary_transition_visualizer"
    ARTIFACT_AUDITOR = "artifact_auditor"


class SchemaEvidenceKind(StrEnum):
    """Upstream evidence supporting a registry entry."""

    COMMITTED_ARTIFACT = "committed_artifact"
    PRODUCER_DECLARATION = "producer_declaration"


class RegistryError(ValueError):
    """Raised when compatibility registry metadata is internally invalid."""


class UnknownArtifactIdentifierError(LookupError):
    """Raised when no exact registry identity matches an artifact."""

    def __init__(
        self,
        identifier: str,
        identifier_field: IdentifierField,
    ) -> None:
        super().__init__(
            f"unknown {identifier_field.value} identifier: {identifier!r}"
        )
        self.identifier = identifier
        self.identifier_field = identifier_field


class UnsupportedArtifactKindError(LookupError):
    """Raised when a shared schema has no matching artifact kind."""

    def __init__(
        self,
        identifier: str,
        declared_kind: str | None,
        expected_kinds: tuple[str, ...],
    ) -> None:
        super().__init__(
            f"unsupported kind {declared_kind!r} for {identifier!r}; "
            f"expected one of {expected_kinds!r}"
        )
        self.identifier = identifier
        self.declared_kind = declared_kind
        self.expected_kinds = expected_kinds


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise RegistryError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise RegistryError(
            f"{field_name} must be nonempty without outer whitespace"
        )
    if any(character.isspace() for character in value):
        raise RegistryError(f"{field_name} must not contain whitespace")


def _validate_repository_path(
    value: str | None,
    field_name: str,
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{field_name} must be a nonempty string")
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise RegistryError(
            f"{field_name} must be a relative POSIX repository path"
        )
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise RegistryError(
            f"{field_name} must not contain empty or traversal segments"
        )

  @dataclass(frozen=True, slots=True)
class CompatibilityRecord:
    """One exact upstream identifier and Observatory routing contract."""

    identifier: str
    identifier_field: IdentifierField
    schema_version: str
    artifact_format: ArtifactFormat
    artifact_kind: str | None
    measurement_contour: MeasurementContour
    producer_path: str | None
    producer_version: str | None
    evidence_kind: SchemaEvidenceKind
    evidence_path: str
    canonical_fixture_path: str | None
    observatory_modes: tuple[ObservatoryMode, ...]
    upstream_release: str = AUDITED_UPSTREAM_RELEASE

    def __post_init__(self) -> None:
        _validate_text(self.identifier, "identifier")
        _validate_text(self.schema_version, "schema_version")
        _validate_text(self.upstream_release, "upstream_release")

        if not self.identifier.startswith("frp."):
            raise RegistryError("identifier must begin with 'frp.'")
        if not self.identifier.endswith(f".v{self.schema_version}"):
            raise RegistryError(
                "schema_version must match the identifier suffix"
            )
        if not isinstance(self.identifier_field, IdentifierField):
            raise RegistryError(
                "identifier_field must be an IdentifierField"
            )
        if not isinstance(self.artifact_format, ArtifactFormat):
            raise RegistryError(
                "artifact_format must be an ArtifactFormat"
            )
        if not isinstance(self.measurement_contour, MeasurementContour):
            raise RegistryError(
                "measurement_contour must be a MeasurementContour"
            )
        if not isinstance(self.evidence_kind, SchemaEvidenceKind):
            raise RegistryError(
                "evidence_kind must be a SchemaEvidenceKind"
            )

        if self.artifact_kind is not None:
            _validate_text(self.artifact_kind, "artifact_kind")
        if self.producer_version is not None:
            _validate_text(self.producer_version, "producer_version")

        _validate_repository_path(self.producer_path, "producer_path")
        _validate_repository_path(self.evidence_path, "evidence_path")
        _validate_repository_path(
            self.canonical_fixture_path,
            "canonical_fixture_path",
        )

        if self.evidence_kind is SchemaEvidenceKind.PRODUCER_DECLARATION:
            if self.producer_path is None:
                raise RegistryError(
                    "producer declarations require producer_path"
                )
        if self.evidence_kind is SchemaEvidenceKind.COMMITTED_ARTIFACT:
            if self.canonical_fixture_path is None:
                raise RegistryError(
                    "committed artifacts require canonical_fixture_path"
                )
            if self.evidence_path != self.canonical_fixture_path:
                raise RegistryError(
                    "committed artifact evidence must be its fixture path"
                )

        if not isinstance(self.observatory_modes, tuple):
            raise RegistryError("observatory_modes must be a tuple")
        if not self.observatory_modes:
            raise RegistryError("observatory_modes must not be empty")
        if any(
            not isinstance(mode, ObservatoryMode)
            for mode in self.observatory_modes
        ):
            raise RegistryError(
                "observatory_modes must contain ObservatoryMode values"
            )
        if len(set(self.observatory_modes)) != len(
            self.observatory_modes
        ):
            raise RegistryError("observatory_modes must be unique")

        if self.artifact_format is ArtifactFormat.JSON:
            if self.identifier_field is not IdentifierField.SCHEMA:
                raise RegistryError(
                    "registered JSON artifacts must use the schema field"
                )
        if self.artifact_format is ArtifactFormat.M15_VECTOR_TEXT:
            if self.identifier_field is not IdentifierField.FORMAT_VERSION:
                raise RegistryError(
                    "M15 vector text must use the format_version field"
                )

    @property
    def dispatch_key(
        self,
    ) -> tuple[IdentifierField, str, str | None]:
        """Return the exact identifier and optional kind dispatch key."""

        return (
            self.identifier_field,
            self.identifier,
            self.artifact_kind,
        )


_AUDITOR_ONLY: Final = (
    ObservatoryMode.ARTIFACT_AUDITOR,
)
_AUDITOR_AND_VISUALIZER: Final = (
    ObservatoryMode.ARTIFACT_AUDITOR,
    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
)
_ALL_MODES: Final = (
    ObservatoryMode.ARTIFACT_AUDITOR,
    ObservatoryMode.TERNARY_TRANSITION_VISUALIZER,
    ObservatoryMode.TRACE_EXPLORER,
)

_REFERENCE_PRODUCER: Final = "frp_prototype_v1_7_0.py"
_REFERENCE_PRODUCER_VERSION: Final = "1.7.0"
_ARCHITECTURE_ROOT: Final = "benchmarks/architecture_comparison"

COMPATIBILITY_RECORDS: Final = (
    CompatibilityRecord(
        identifier="frp.structured_output.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="demo",
        measurement_contour=MeasurementContour.STRUCTURED_OUTPUT,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_ALL_MODES,
    ),
    CompatibilityRecord(
        identifier="frp.structured_output.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="self_test",
        measurement_contour=MeasurementContour.STRUCTURED_OUTPUT,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.m3.benchmark_matrix.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="benchmark_matrix",
        measurement_contour=MeasurementContour.M3_BENCHMARK_MATRIX,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.m15.fixed_point_interface_profile.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="fixed_point_interface_profile",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier=(
            "frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0"
        ),
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="balanced_ternary_hardware_encoding_map",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_AND_VISUALIZER,
    ),
    CompatibilityRecord(
        identifier="frp.m15.quantized_reference_shadow_model.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="quantized_reference_shadow_model",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_ALL_MODES,
    ),
    CompatibilityRecord(
        identifier="frp.m15.cycle_exact_reference_trace.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="cycle_exact_reference_trace",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_ALL_MODES,
    ),
    CompatibilityRecord(
        identifier="frp.m15.rtl_comparison_vector_package.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="rtl_comparison_vector_package",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier=(
            "frp.m15.systemverilog_testbench_interface_map.v1.7.0"
        ),
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="systemverilog_testbench_interface_map",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),

    CompatibilityRecord(
        identifier="frp.m15.synthesizable_rtl_reference_core.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="synthesizable_rtl_reference_core",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier=(
            "frp.m15.rtl_assertion_correlation_harness.v1.7.0"
        ),
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="rtl_assertion_correlation_harness",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.m15.reference_rtl_equivalence_report.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="reference_rtl_equivalence_report",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.m15.qualification_closure_manifest.v1.7.0",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1.7.0",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind="qualification_closure_manifest",
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.m15.vector.v1",
        identifier_field=IdentifierField.FORMAT_VERSION,
        schema_version="1",
        artifact_format=ArtifactFormat.M15_VECTOR_TEXT,
        artifact_kind=None,
        measurement_contour=MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        producer_path=_REFERENCE_PRODUCER,
        producer_version=_REFERENCE_PRODUCER_VERSION,
        evidence_kind=SchemaEvidenceKind.PRODUCER_DECLARATION,
        evidence_path=_REFERENCE_PRODUCER,
        canonical_fixture_path=None,
        observatory_modes=_ALL_MODES,
    ),
    CompatibilityRecord(
        identifier="frp.benchmark.normalized_cost_profile.v1",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind=None,
        measurement_contour=MeasurementContour.COMPARATIVE_ARCHITECTURE,
        producer_path=f"{_ARCHITECTURE_ROOT}/common_cost_model.py",
        producer_version=None,
        evidence_kind=SchemaEvidenceKind.COMMITTED_ARTIFACT,
        evidence_path=(
            f"{_ARCHITECTURE_ROOT}/profiles/normalized_cost_profile_v1.json"
        ),
        canonical_fixture_path=(
            f"{_ARCHITECTURE_ROOT}/profiles/normalized_cost_profile_v1.json"
        ),
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.benchmark.thermal_proxy_profile.v1",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind=None,
        measurement_contour=MeasurementContour.COMPARATIVE_ARCHITECTURE,
        producer_path=f"{_ARCHITECTURE_ROOT}/common_thermal_model.py",
        producer_version=None,
        evidence_kind=SchemaEvidenceKind.COMMITTED_ARTIFACT,
        evidence_path=(
            f"{_ARCHITECTURE_ROOT}/profiles/thermal_proxy_profile_v1.json"
        ),
        canonical_fixture_path=(
            f"{_ARCHITECTURE_ROOT}/profiles/thermal_proxy_profile_v1.json"
        ),
        observatory_modes=_AUDITOR_ONLY,
    ),

    CompatibilityRecord(
        identifier="frp.benchmark.hardware_sensitivity_cost_profile.v1",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind=None,
        measurement_contour=MeasurementContour.HARDWARE_SENSITIVITY,
        producer_path=None,
        producer_version=None,
        evidence_kind=SchemaEvidenceKind.COMMITTED_ARTIFACT,
        evidence_path=(
            f"{_ARCHITECTURE_ROOT}/profiles/"
            "hardware_sensitivity_cost_profile_v1.json"
        ),
        canonical_fixture_path=(
            f"{_ARCHITECTURE_ROOT}/profiles/"
            "hardware_sensitivity_cost_profile_v1.json"
        ),
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier="frp.benchmark.architecture_comparison.v1",
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind=None,
        measurement_contour=MeasurementContour.COMPARATIVE_ARCHITECTURE,
        producer_path=(
            f"{_ARCHITECTURE_ROOT}/run_architecture_comparison.py"
        ),
        producer_version=None,
        evidence_kind=SchemaEvidenceKind.COMMITTED_ARTIFACT,
        evidence_path=(
            f"{_ARCHITECTURE_ROOT}/results/"
            "reference_comparison_seed_76.json"
        ),
        canonical_fixture_path=(
            f"{_ARCHITECTURE_ROOT}/results/"
            "reference_comparison_seed_76.json"
        ),
        observatory_modes=_AUDITOR_ONLY,
    ),
    CompatibilityRecord(
        identifier=(
            "frp.benchmark.hardware_sensitivity_comparison.v1"
        ),
        identifier_field=IdentifierField.SCHEMA,
        schema_version="1",
        artifact_format=ArtifactFormat.JSON,
        artifact_kind=None,
        measurement_contour=MeasurementContour.HARDWARE_SENSITIVITY,
        producer_path=(
            f"{_ARCHITECTURE_ROOT}/"
            "run_hardware_sensitivity_comparison.py"
        ),
        producer_version=None,
        evidence_kind=SchemaEvidenceKind.COMMITTED_ARTIFACT,
        evidence_path=(
            f"{_ARCHITECTURE_ROOT}/results/"
            "reference_comparison_seed_76_hardware_sensitivity_v1.json"
        ),
        canonical_fixture_path=(
            f"{_ARCHITECTURE_ROOT}/results/"
            "reference_comparison_seed_76_hardware_sensitivity_v1.json"
        ),
        observatory_modes=_AUDITOR_ONLY,
    ),
)

def _build_identifier_index(
    records: tuple[CompatibilityRecord, ...],
) -> MappingProxyType:
    mutable_index: dict[
        tuple[IdentifierField, str],
        list[CompatibilityRecord],
    ] = {}
    dispatch_keys: set[
        tuple[IdentifierField, str, str | None]
    ] = set()

    for record in records:
        if record.dispatch_key in dispatch_keys:
            raise RegistryError(
                f"duplicate registry dispatch key: {record.dispatch_key!r}"
            )
        dispatch_keys.add(record.dispatch_key)
        identity_key = (
            record.identifier_field,
            record.identifier,
        )
        mutable_index.setdefault(identity_key, []).append(record)

    return MappingProxyType(
        {
            key: tuple(indexed_records)
            for key, indexed_records in mutable_index.items()
        }
    )


_IDENTIFIER_INDEX: Final = _build_identifier_index(
    COMPATIBILITY_RECORDS
)


def records_for_identifier(
    identifier: str,
    *,
    identifier_field: IdentifierField = IdentifierField.SCHEMA,
) -> tuple[CompatibilityRecord, ...]:
    """Return all exact records for one identifier without aliases."""

    if not isinstance(identifier, str):
        raise RegistryError("identifier must be a string")
    if not isinstance(identifier_field, IdentifierField):
        raise RegistryError(
            "identifier_field must be an IdentifierField"
        )
    return _IDENTIFIER_INDEX.get(
        (identifier_field, identifier),
        (),
    )


def resolve_compatibility_record(
    identifier: str,
    *,
    declared_kind: str | None = None,
    identifier_field: IdentifierField = IdentifierField.SCHEMA,
) -> CompatibilityRecord:
    """Resolve one exact schema or format identity and optional kind."""

    records = records_for_identifier(
        identifier,
        identifier_field=identifier_field,
    )
    if not records:
        raise UnknownArtifactIdentifierError(
            identifier,
            identifier_field,
        )

    kind_independent = tuple(
        record
        for record in records
        if record.artifact_kind is None
    )
    if len(kind_independent) == 1:
        return kind_independent[0]

    for record in records:
        if record.artifact_kind == declared_kind:
            return record

    expected_kinds = tuple(
        record.artifact_kind
        for record in records
        if record.artifact_kind is not None
    )
    raise UnsupportedArtifactKindError(
        identifier,
        declared_kind,
        expected_kinds,
    )
