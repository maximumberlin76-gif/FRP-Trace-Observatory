"""Read-only auditing for published Fractal Resonance Processor artifacts.

This package validates captured source bytes and immutable parsed views against
explicit Observatory compatibility contracts. It reports findings without
executing artifact content, invoking upstream producers, modifying source
artifacts, redefining FRP semantics, or combining measurement contours.
"""

from artifact_auditor.audit_report import (
    AuditReport,
    AuditReportError,
    AuditScalar,
    AuditValue,
    AuditValueSnapshot,
    CheckOutcome,
    MessageSeverity,
    SourceLocation,
    ValidationCategory,
    ValidationCheck,
    ValidationStatus,
)
from artifact_auditor.audit_report_serializer import (
    AuditReportSerializationError,
    audit_report_to_json_bytes,
    audit_report_to_mapping,
    audit_report_to_text,
)
from artifact_auditor.auditor import (
    ArtifactAuditorError,
    audit_dispatched_artifact,
    audit_source_artifact,
)
from artifact_auditor.comparative_architecture_validator import (
    ComparativeArchitectureValidation,
    ComparativeArchitectureValidationError,
    validate_comparative_architecture,
)
from artifact_auditor.deterministic_package_validator import (
    DeterministicPackageValidation,
    DeterministicPackageValidationError,
    validate_deterministic_package,
)
from artifact_auditor.fixture_manifest import (
    CANONICAL_FIXTURE_MANIFEST_OWNER,
    CANONICAL_FIXTURE_MANIFEST_TYPE,
    CANONICAL_FIXTURE_MANIFEST_VERSION,
    CanonicalFixtureManifest,
    CanonicalFixtureRecord,
    FixtureIdentificationBasis,
    FixtureManifestError,
    RawDigestContract,
    parse_canonical_fixture_manifest,
)
from artifact_auditor.fixture_validator import (
    FixtureInventoryValidation,
    FixtureValidationError,
    validate_canonical_fixture_inventory,
    validate_canonical_fixture_source,
)
from artifact_auditor.hardware_sensitivity_validator import (
    HardwareSensitivityValidation,
    HardwareSensitivityValidationError,
    validate_hardware_sensitivity,
)
from artifact_auditor.m15_artifact_validator import (
    M15ArtifactValidation,
    M15ArtifactValidationError,
    validate_m15_artifact,
)
from artifact_auditor.m15_vector_validator import (
    M15VectorValidation,
    M15VectorValidationError,
    validate_m15_vector,
)
from artifact_auditor.m3_benchmark_validator import (
    M3BenchmarkValidation,
    M3BenchmarkValidationError,
    validate_m3_benchmark,
)
from artifact_auditor.structured_output_validator import (
    StructuredOutputValidation,
    StructuredOutputValidationError,
    validate_structured_output,
)
from artifact_auditor.validation_core import (
    ValidationCheckSpec,
    ValidationCoreError,
    base_check_specs,
    build_audit_report,
    derive_validation_status,
    materialize_validation_checks,
)


__all__ = [
    "CANONICAL_FIXTURE_MANIFEST_OWNER",
    "CANONICAL_FIXTURE_MANIFEST_TYPE",
    "CANONICAL_FIXTURE_MANIFEST_VERSION",
    "ArtifactAuditorError",
    "AuditReport",
    "AuditReportError",
    "AuditReportSerializationError",
    "AuditScalar",
    "AuditValue",
    "AuditValueSnapshot",
    "CanonicalFixtureManifest",
    "CanonicalFixtureRecord",
    "CheckOutcome",
    "ComparativeArchitectureValidation",
    "ComparativeArchitectureValidationError",
    "DeterministicPackageValidation",
    "DeterministicPackageValidationError",
    "FixtureIdentificationBasis",
    "FixtureInventoryValidation",
    "FixtureManifestError",
    "FixtureValidationError",
    "HardwareSensitivityValidation",
    "HardwareSensitivityValidationError",
    "M15ArtifactValidation",
    "M15ArtifactValidationError",
    "M15VectorValidation",
    "M15VectorValidationError",
    "M3BenchmarkValidation",
    "M3BenchmarkValidationError",
    "MessageSeverity",
    "RawDigestContract",
    "SourceLocation",
    "StructuredOutputValidation",
    "StructuredOutputValidationError",
    "ValidationCategory",
    "ValidationCheck",
    "ValidationCheckSpec",
    "ValidationCoreError",
    "ValidationStatus",
    "audit_dispatched_artifact",
    "audit_report_to_json_bytes",
    "audit_report_to_mapping",
    "audit_report_to_text",
    "audit_source_artifact",
    "base_check_specs",
    "build_audit_report",
    "derive_validation_status",
    "materialize_validation_checks",
    "parse_canonical_fixture_manifest",
    "validate_canonical_fixture_inventory",
    "validate_canonical_fixture_source",
    "validate_comparative_architecture",
    "validate_deterministic_package",
    "validate_hardware_sensitivity",
    "validate_m15_artifact",
    "validate_m15_vector",
    "validate_m3_benchmark",
    "validate_structured_output",
]
