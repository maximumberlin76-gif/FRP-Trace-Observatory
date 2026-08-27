"""Read-only validation of the FRP M28-M30 Observatory boundary.

The validator consumes only members retained from the exact FRP v3.2.0 / M30
archive after :mod:`artifact_auditor.m30_archive_intake` has verified the full
package.  It enforces raw-byte identity before JSON parsing, validates the
published object digests, preserves the immutable ``-1/0/1`` core and the
``1/7`` and ``7/1`` temporal modes, and rejects any bidirectional or mutable
integration boundary.  It never extracts, executes, normalizes, or writes
upstream content.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from .m30_archive_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M30ArchiveValidation,
    validate_m30_archive,
)


__all__ = [
    "M28_COMPATIBILITY_REGISTRY_PATH",
    "M28_UPSTREAM_CONTRACT_PATH",
    "M29_ARTIFACT_REGISTRY_PATH",
    "M29_CONSUMPTION_VECTORS_PATH",
    "M29_DEMO_PACKAGE_PATH",
    "M29_INTEGRATION_CONTRACT_PATH",
    "M29_RELEASE_RECORDS_PATH",
    "M30_ALIGNMENT_PATH",
    "M30PublishedBoundaryError",
    "PublishedBoundaryDocument",
    "PublishedBoundaryValidation",
    "PublishedDemoMember",
    "validate_m30_published_boundary",
]


M28_UPSTREAM_CONTRACT_PATH: Final = (
    "artifacts/m28/contracts/m28-trace-observatory-upstream-contract.json"
)
M28_COMPATIBILITY_REGISTRY_PATH: Final = (
    "artifacts/m28/registry/m28-observatory-compatibility-registry.json"
)
M29_INTEGRATION_CONTRACT_PATH: Final = (
    "artifacts/m29/contracts/m29-system-integration-contract.json"
)
M29_ARTIFACT_REGISTRY_PATH: Final = (
    "artifacts/m29/registries/m29-supported-artifact-registry.json"
)
M29_DEMO_PACKAGE_PATH: Final = (
    "artifacts/m29/packages/m29-canonical-demo-artifact-package.json"
)
M29_RELEASE_RECORDS_PATH: Final = (
    "artifacts/m29/compatibility/"
    "m29-release-independent-compatibility-records.json"
)
M29_CONSUMPTION_VECTORS_PATH: Final = (
    "artifacts/m29/vectors/m29-downstream-consumption-test-vectors.json"
)
M30_ALIGNMENT_PATH: Final = (
    "artifacts/m30/alignment/m30-repository-alignment-record.json"
)

_M28_SOURCE_COMMIT: Final = (
    "23e464206f85cd9473101d9221027ee33d9dd094"
)
_M29_SOURCE_COMMIT: Final = (
    "a1c0bb2fa0a4731b9339e6cd996589e1bf226c04"
)
_M30_SOURCE_COMMIT: Final = (
    "ff3dd434da5dcbd9e8fa62444f658ed4c495b540"
)
_OBSERVATORY_AUDITED_COMMIT: Final = (
    "a9d71657c56221d0d9b72fb6e954e0028f096a9e"
)
_UPSTREAM_INTERCHANGE_COMMIT: Final = (
    "566a4ff88baa57f844691b46937552253e095434"
)
_OBSERVATORY_REPOSITORY: Final = "FRP-Trace-Observatory"
_OBSERVATORY_MODES: Final = (
    "artifact_auditor",
    "ternary_transition_visualizer",
    "trace_explorer",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_M28_CORE: Final = {
    "active_neutral_state": 0,
    "balanced_ternary_notation": "-1/0/1",
    "opposite_transition_routes": [[-1, 0, 1], [1, 0, -1]],
    "semantic_values": [-1, 0, 1],
    "service_scheduler_mode": "free",
    "temporal_scheduler_modes": ["1/7", "7/1"],
}
_M29_CORE: Final = {
    **_M28_CORE,
    "actual_direct_events": 0,
}
_M30_CORE: Final = {
    "active_neutral_state": 0,
    "balanced_ternary_notation": "-1/0/1",
    "opposite_polarity_routes": [[-1, 0, 1], [1, 0, -1]],
    "semantic_values": [-1, 0, 1],
    "service_scheduler_mode": "free",
    "temporal_scheduler_modes": ["1/7", "7/1"],
}

_BOUNDARY_DOCUMENT_PATHS: Final = (
    M28_UPSTREAM_CONTRACT_PATH,
    M28_COMPATIBILITY_REGISTRY_PATH,
    M29_INTEGRATION_CONTRACT_PATH,
    M29_ARTIFACT_REGISTRY_PATH,
    M29_DEMO_PACKAGE_PATH,
    M29_RELEASE_RECORDS_PATH,
    M29_CONSUMPTION_VECTORS_PATH,
    M30_ALIGNMENT_PATH,
)

_DEMO_MEMBER_SPECS: Final = (
    {
        "member_id": "m16-fpga-preparation-execution-trace",
        "source_path": (
            "artifacts/m19/execution/"
            "m16-fpga-preparation-execution-trace.json"
        ),
        "schema_identifier": (
            "frp.m16.fpga_preparation_execution_trace.v2.1.0"
        ),
        "measurement_contour": "m16_fpga_preparation_execution",
        "observatory_modes": list(_OBSERVATORY_MODES),
        "byte_length": 9013,
        "raw_sha256": (
            "7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f"
        ),
    },
    {
        "member_id": "m27-telemetry-semantics",
        "source_path": "artifacts/m27/telemetry/m27-telemetry-semantics.json",
        "schema_identifier": "m27-telemetry-semantics-v2.9.0",
        "measurement_contour": "m27_long_run_telemetry_semantics",
        "observatory_modes": [
            "artifact_auditor",
            "ternary_transition_visualizer",
        ],
        "byte_length": 2789,
        "raw_sha256": (
            "813ae5c66ceaddabc77734d44f1ebf971ca3bd7e11c1984e2e0c8f0204dfd1bc"
        ),
    },
    {
        "member_id": "m28-trace-observatory-upstream-contract",
        "source_path": M28_UPSTREAM_CONTRACT_PATH,
        "schema_identifier": (
            "frp.m28.trace_observatory_upstream_contract.v3.0.0"
        ),
        "measurement_contour": "m28_upstream_integration_contract",
        "observatory_modes": ["artifact_auditor"],
        "byte_length": 2735,
        "raw_sha256": (
            "556cd2921014d78184dad625438e053632c2650164f95787f39a6fc871b4a3f0"
        ),
    },
    {
        "member_id": "m28-hierarchical-scaling-contract",
        "source_path": (
            "artifacts/m28/hierarchy/contracts/"
            "m28-hierarchical-scaling-contract.json"
        ),
        "schema_identifier": (
            "frp.m28.hierarchical_scaling_contract.v3.0.0"
        ),
        "measurement_contour": "m28_hierarchical_scaling_qualification",
        "observatory_modes": ["artifact_auditor"],
        "byte_length": 3560,
        "raw_sha256": (
            "13f85ac82b63d0191157bd2cfa04dd37358ef66d8e69bdb96bb1892abb77dbae"
        ),
    },
)
_DEMO_SOURCE_PATHS: Final = tuple(
    str(spec["source_path"]) for spec in _DEMO_MEMBER_SPECS
)
_RETAIN_PATHS: Final = tuple(
    sorted(set(_BOUNDARY_DOCUMENT_PATHS + _DEMO_SOURCE_PATHS))
)


class M30PublishedBoundaryError(ValueError):
    """Raised when an exact published-byte boundary requirement fails."""


@dataclass(frozen=True, slots=True)
class PublishedBoundaryDocument:
    """Identity of one verified boundary document."""

    path: str
    schema: str
    kind: str
    raw_sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if self.path not in _BOUNDARY_DOCUMENT_PATHS:
            raise M30PublishedBoundaryError(
                f"unexpected boundary document path: {self.path}"
            )
        if not self.schema or not self.kind:
            raise M30PublishedBoundaryError(
                f"boundary document identity is incomplete: {self.path}"
            )
        if not _HEX64.fullmatch(self.raw_sha256):
            raise M30PublishedBoundaryError(
                f"boundary document digest is invalid: {self.path}"
            )
        if self.byte_length <= 0:
            raise M30PublishedBoundaryError(
                f"boundary document byte length is invalid: {self.path}"
            )


@dataclass(frozen=True, slots=True)
class PublishedDemoMember:
    """Identity of one decoded, byte-identical M29 demo member."""

    member_id: str
    source_path: str
    schema_identifier: str
    observatory_modes: tuple[str, ...]
    raw_sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if self.source_path not in _DEMO_SOURCE_PATHS:
            raise M30PublishedBoundaryError(
                f"unexpected demo member path: {self.source_path}"
            )
        if not self.member_id or not self.schema_identifier:
            raise M30PublishedBoundaryError(
                f"demo member identity is incomplete: {self.source_path}"
            )
        if not self.observatory_modes or any(
            mode not in _OBSERVATORY_MODES for mode in self.observatory_modes
        ):
            raise M30PublishedBoundaryError(
                f"demo member mode routing is invalid: {self.source_path}"
            )
        if not _HEX64.fullmatch(self.raw_sha256):
            raise M30PublishedBoundaryError(
                f"demo member digest is invalid: {self.source_path}"
            )
        if self.byte_length <= 0:
            raise M30PublishedBoundaryError(
                f"demo member byte length is invalid: {self.source_path}"
            )


@dataclass(frozen=True, slots=True)
class PublishedBoundaryValidation:
    """Successful evidence for the exact M28-M30 downstream boundary."""

    archive_sha256: str
    documents: tuple[PublishedBoundaryDocument, ...]
    supported_artifact_count: int
    demo_members: tuple[PublishedDemoMember, ...]
    accepted_vector_count: int
    rejected_vector_count: int

    def __post_init__(self) -> None:
        if self.archive_sha256 != FRP_M30_ARCHIVE_SHA256:
            raise M30PublishedBoundaryError(
                "boundary result archive digest is not the exact M30 digest"
            )
        if tuple(document.path for document in self.documents) != (
            _BOUNDARY_DOCUMENT_PATHS
        ):
            raise M30PublishedBoundaryError(
                "boundary result document order or inventory mismatch"
            )
        if self.supported_artifact_count != 97:
            raise M30PublishedBoundaryError(
                "boundary result supported artifact count mismatch"
            )
        if tuple(member.member_id for member in self.demo_members) != tuple(
            str(spec["member_id"]) for spec in _DEMO_MEMBER_SPECS
        ):
            raise M30PublishedBoundaryError(
                "boundary result demo member order or inventory mismatch"
            )
        if self.accepted_vector_count != 4:
            raise M30PublishedBoundaryError(
                "boundary result accepted vector count mismatch"
            )
        if self.rejected_vector_count != 8:
            raise M30PublishedBoundaryError(
                "boundary result rejected vector count mismatch"
            )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs_without_duplicates(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise M30PublishedBoundaryError(
                f"duplicate JSON object key: {key!r}"
            )
        result[key] = value
    return result


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise M30PublishedBoundaryError(
            f"{label} is not strict UTF-8"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
        )
    except json.JSONDecodeError as exc:
        raise M30PublishedBoundaryError(
            f"{label} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise M30PublishedBoundaryError(f"{label} must be a JSON object")
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _object_digest(value: Mapping[str, Any], digest_field: str) -> str:
    subject = dict(value)
    subject.pop(digest_field, None)
    return _sha256(_canonical_json_bytes(subject))


def _require_equal(
    value: Mapping[str, Any],
    field: str,
    expected: object,
    label: str,
) -> None:
    if value.get(field) != expected:
        raise M30PublishedBoundaryError(f"{label} {field} mismatch")


def _require_header(
    value: Mapping[str, Any],
    *,
    schema: str,
    kind: str,
    milestone: str,
    version: str,
    source_commit: str,
    label: str,
) -> None:
    expected = {
        "schema": schema,
        "kind": kind,
        "milestone": milestone,
        "version": version,
        "source_commit": source_commit,
        "status": "PASS",
    }
    for field, expected_value in expected.items():
        _require_equal(value, field, expected_value, label)


def _require_digest(
    value: Mapping[str, Any],
    *,
    field: str,
    expected: str,
    label: str,
) -> None:
    observed = value.get(field)
    if observed != expected:
        raise M30PublishedBoundaryError(
            f"{label} fixed {field} mismatch"
        )
    if observed != _object_digest(value, field):
        raise M30PublishedBoundaryError(
            f"{label} calculated {field} mismatch"
        )


def _validate_m28_contract(value: Mapping[str, Any]) -> None:
    label = "M28 Observatory upstream contract"
    _require_header(
        value,
        schema="frp.m28.trace_observatory_upstream_contract.v3.0.0",
        kind="trace_observatory_upstream_contract",
        milestone="M28",
        version="3.0.0",
        source_commit=_M28_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="contract_digest",
        expected=(
            "43543c810738cb0505937311e53fd3f5b5f65029bd936c7a0ca615322fcca0da"
        ),
        label=label,
    )
    _require_equal(value, "immutable_core", _M28_CORE, label)
    _require_equal(
        value,
        "consumer_scaffold_baseline",
        {
            "audited_commit": _OBSERVATORY_AUDITED_COMMIT,
            "ci_workflow_path": ".github/workflows/observatory-ci.yml",
            "compatibility_registry_path": "schemas/registry.py",
            "implementation_action": "extend_existing_scaffold",
            "implemented_layers": [
                {"mode": "artifact_auditor", "path": "artifact_auditor/"},
                {"mode": "trace_explorer", "path": "trace_explorer/"},
                {
                    "mode": "ternary_transition_visualizer",
                    "path": "transition_visualizer/",
                },
            ],
            "integration_contract_path": "docs/integration_contract.md",
            "repository": _OBSERVATORY_REPOSITORY,
            "verified_test_count": 275,
        },
        label,
    )
    _require_equal(
        value,
        "data_contract",
        {
            "absent_is_zero": False,
            "automatic_schema_migration": "forbidden",
            "container_format": "json",
            "digest_algorithm": "sha256",
            "digest_scope": "raw_source_bytes",
            "missing_field_policy": "remain_absent",
            "ordering": "preserve_source_order",
            "producer_command_execution_by_consumer": "forbidden",
            "schema_aliases": "forbidden",
            "schema_resolution": "exact_identifier_and_kind",
            "source_execution": "forbidden",
            "text_encoding": "utf-8",
        },
        label,
    )
    _require_equal(
        value,
        "integration_direction",
        {
            "consumer": _OBSERVATORY_REPOSITORY,
            "direction": "upstream_to_downstream_only",
            "downstream_source_mutation": "forbidden",
            "downstream_writeback": "forbidden",
            "producer": "Fractal-Resonance-Processor",
            "transport": "published_versioned_artifacts",
            "upstream_semantic_authority": True,
        },
        label,
    )
    _require_equal(
        value,
        "export_scope",
        {
            "downstream_repository_files_modified": False,
            "measurement_contours_remain_separate": True,
            "published_observatory_modes": list(_OBSERVATORY_MODES),
            "source_fixture_count": 6,
            "trace_dataset_count": 3,
            "ui_dependencies_in_upstream": False,
        },
        label,
    )


def _validate_m28_registry(value: Mapping[str, Any]) -> None:
    label = "M28 Observatory compatibility registry"
    _require_header(
        value,
        schema="frp.m28.trace_observatory_compatibility_registry.v3.0.0",
        kind="trace_observatory_compatibility_registry",
        milestone="M28",
        version="3.0.0",
        source_commit=_M28_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="registry_digest",
        expected=(
            "e4cddb040ab4577c4cc21dc89431750e239a31b22c276a4ff1c6a6bbe1b99ff8"
        ),
        label=label,
    )
    _require_equal(value, "registry_revision", "m28-v3.0.0", label)
    _require_equal(value, "consumer_repository", _OBSERVATORY_REPOSITORY, label)
    _require_equal(value, "consumer_registry_path", "schemas/registry.py", label)
    _require_equal(
        value,
        "consumer_registration_state",
        "upstream_published_downstream_registration_required",
        label,
    )
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 5:
        raise M30PublishedBoundaryError(f"{label} record inventory mismatch")
    _require_equal(value, "record_count", len(records), label)
    expected_identifiers = [
        "frp.m28.trace_observatory_upstream_contract.v3.0.0",
        "frp.m28.trace_observatory_canonical_trace_bundle.v3.0.0",
        "frp.m28.trace_observatory_fixture_manifest.v3.0.0",
        "frp.m28.trace_observatory_compatibility_registry.v3.0.0",
        "frp.m28.trace_observatory_interchange_qualification.v3.0.0",
    ]
    if [record.get("identifier") for record in records] != expected_identifiers:
        raise M30PublishedBoundaryError(f"{label} identifier order mismatch")
    for record in records:
        if record.get("identifier_field") != "schema":
            raise M30PublishedBoundaryError(f"{label} identifier field mismatch")
        if record.get("downstream_registration_state") != "registration_required":
            raise M30PublishedBoundaryError(f"{label} registration state mismatch")
        modes = record.get("observatory_modes")
        if not isinstance(modes, list) or not modes or any(
            mode not in _OBSERVATORY_MODES for mode in modes
        ):
            raise M30PublishedBoundaryError(f"{label} mode routing mismatch")
    if records[1].get("observatory_modes") != list(_OBSERVATORY_MODES):
        raise M30PublishedBoundaryError(
            f"{label} canonical trace routing mismatch"
        )


def _validate_m29_contract(value: Mapping[str, Any]) -> None:
    label = "M29 system integration contract"
    _require_header(
        value,
        schema="frp.m29.system_integration_contract.v3.1.0",
        kind="system_integration_contract",
        milestone="M29",
        version="3.1.0",
        source_commit=_M29_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="contract_digest",
        expected=(
            "2495fa8ef47f3e9d00539934350f99afd877cf0c5b449fb1add9833773a35c40"
        ),
        label=label,
    )
    _require_equal(value, "immutable_core", _M29_CORE, label)
    _require_equal(
        value,
        "objective",
        (
            "close the published integration boundary without coupling FRP "
            "qualification to downstream implementation code"
        ),
        label,
    )
    _require_equal(
        value,
        "integration_boundary",
        {
            "direction": "upstream_to_published_bytes_to_downstream",
            "downstream_audited_commit": _OBSERVATORY_AUDITED_COMMIT,
            "downstream_files_modified_by_m29": False,
            "downstream_modes": list(_OBSERVATORY_MODES),
            "downstream_repository": _OBSERVATORY_REPOSITORY,
            "downstream_semantic_reimplementation": "forbidden",
            "downstream_source_mutation": "forbidden",
            "downstream_verified_test_count": 275,
            "downstream_writeback": "forbidden",
            "existing_scaffold_action": "preserve_existing_scaffold",
            "preserved_m28_observatory_commit": _UPSTREAM_INTERCHANGE_COMMIT,
            "upstream_dependency_on_downstream_code": False,
            "upstream_repository": "Fractal-Resonance-Processor",
            "upstream_semantic_authority": True,
        },
        label,
    )
    _require_equal(
        value,
        "inventory_boundary",
        {
            "complete_upstream_publication_files": 193,
            "identity": "exact_identifiers_paths_and_raw_sha256",
            "measurement_contours": "preserved_separately",
            "milestones": [f"M{number}" for number in range(18, 29)],
            "upstream_artifacts": 97,
            "upstream_schema_definitions": 84,
            "upstream_schema_registries": 12,
        },
        label,
    )
    deliverables = value.get("required_deliverables")
    expected_paths = [
        "schemas/m29/frp_m29_supported_schema_registry.json",
        M29_ARTIFACT_REGISTRY_PATH,
        "artifacts/m29/compatibility/m29-compatibility-version-declarations.json",
        M29_DEMO_PACKAGE_PATH,
        "artifacts/m29/packages/m29-deterministic-package-manifest.json",
        "artifacts/m29/registries/m29-producer-command-registry.json",
        "artifacts/m29/policies/m29-immutable-source-artifact-policy.json",
        "artifacts/m29/provenance/m29-provenance-completeness-record.json",
        "artifacts/m29/compatibility/m29-unsupported-version-behavior.json",
        M29_CONSUMPTION_VECTORS_PATH,
        M29_RELEASE_RECORDS_PATH,
    ]
    if not isinstance(deliverables, list) or [
        item.get("path") for item in deliverables if isinstance(item, dict)
    ] != expected_paths:
        raise M30PublishedBoundaryError(f"{label} deliverable order mismatch")


def _validate_m29_artifact_registry(
    value: Mapping[str, Any],
    archive: M30ArchiveValidation,
) -> int:
    label = "M29 supported artifact registry"
    _require_header(
        value,
        schema="frp.m29.supported_artifact_registry.v3.1.0",
        kind="supported_artifact_registry",
        milestone="M29",
        version="3.1.0",
        source_commit=_M29_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="registry_digest",
        expected=(
            "ceeba647adaa8cdb8dfdf5622293bcb5945d445b4d6ef4a8593a04205c9b6577"
        ),
        label=label,
    )
    _require_equal(
        value,
        "identity_policy",
        {
            "artifact_resolution": "exact_path_identifier_and_raw_sha256",
            "pre_parse_digest_required": True,
            "schema_resolution": "exact_schema_identifier",
            "source_byte_normalization": "forbidden",
            "unknown_identifiers": "unsupported",
            "validated_json_artifact_count": 86,
        },
        label,
    )
    expected_milestones = {
        "M18": 36,
        "M19": 10,
        "M20": 4,
        "M21": 4,
        "M22": 4,
        "M23": 5,
        "M24": 5,
        "M25": 6,
        "M26": 6,
        "M27": 7,
        "M28": 10,
    }
    _require_equal(value, "milestone_counts", expected_milestones, label)
    _require_equal(value, "json_artifact_count", 86, label)
    _require_equal(value, "byte_artifact_count", 11, label)
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 97:
        raise M30PublishedBoundaryError(f"{label} record inventory mismatch")
    _require_equal(value, "record_count", len(records), label)
    paths = [record.get("artifact_path") for record in records]
    if any(not isinstance(path, str) for path in paths):
        raise M30PublishedBoundaryError(f"{label} contains an invalid path")
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        raise M30PublishedBoundaryError(f"{label} path order mismatch")
    observed_milestones: dict[str, int] = {}
    for record in records:
        path = record["artifact_path"]
        try:
            archive_member = archive.member(path)
        except KeyError as exc:
            raise M30PublishedBoundaryError(
                f"{label} path is absent from M30 archive: {path}"
            ) from exc
        if record.get("artifact_identifier") != f"frp.artifact.path:{path}":
            raise M30PublishedBoundaryError(
                f"{label} artifact identifier mismatch: {path}"
            )
        if record.get("identity_basis") != (
            "exact_repository_path_and_raw_sha256"
        ):
            raise M30PublishedBoundaryError(
                f"{label} identity basis mismatch: {path}"
            )
        if record.get("source_byte_policy") != "immutable":
            raise M30PublishedBoundaryError(
                f"{label} source-byte policy mismatch: {path}"
            )
        if record.get("byte_length") != archive_member.byte_length:
            raise M30PublishedBoundaryError(
                f"{label} byte length mismatch: {path}"
            )
        if record.get("raw_sha256") != archive_member.raw_sha256:
            raise M30PublishedBoundaryError(
                f"{label} raw digest mismatch: {path}"
            )
        milestone = record.get("milestone")
        if milestone not in expected_milestones:
            raise M30PublishedBoundaryError(
                f"{label} milestone mismatch: {path}"
            )
        observed_milestones[milestone] = observed_milestones.get(milestone, 0) + 1
    if observed_milestones != expected_milestones:
        raise M30PublishedBoundaryError(f"{label} milestone counts mismatch")
    return len(records)


def _validate_demo_package(
    value: Mapping[str, Any],
    retained_raw: Mapping[str, bytes],
) -> tuple[PublishedDemoMember, ...]:
    label = "M29 canonical demo package"
    _require_header(
        value,
        schema="frp.m29.canonical_demo_artifact_package.v3.1.0",
        kind="canonical_demo_artifact_package",
        milestone="M29",
        version="3.1.0",
        source_commit=_M29_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="package_digest",
        expected=(
            "e4bc5fbb40c72ec2fa6a7409daaa0e01b5836aa25e0fc29ed873074ed2c7b99b"
        ),
        label=label,
    )
    _require_equal(
        value,
        "package_id",
        "frp-m29-canonical-downstream-demo-package",
        label,
    )
    _require_equal(
        value,
        "transport_contract",
        {
            "container": "json_with_base64_members",
            "digest_algorithm": "sha256",
            "digest_scope": "decoded_raw_source_bytes",
            "member_encoding": "base64_rfc4648",
            "parse_order": "decode_then_digest_then_schema_resolve_then_parse",
            "source_execution": "forbidden",
        },
        label,
    )
    members = value.get("members")
    if not isinstance(members, list) or len(members) != len(_DEMO_MEMBER_SPECS):
        raise M30PublishedBoundaryError(f"{label} member inventory mismatch")
    _require_equal(value, "member_count", len(members), label)
    result: list[PublishedDemoMember] = []
    for member, spec in zip(members, _DEMO_MEMBER_SPECS, strict=True):
        if not isinstance(member, dict):
            raise M30PublishedBoundaryError(f"{label} member shape mismatch")
        for field in (
            "member_id",
            "source_path",
            "schema_identifier",
            "measurement_contour",
            "observatory_modes",
            "byte_length",
            "raw_sha256",
        ):
            if member.get(field) != spec[field]:
                raise M30PublishedBoundaryError(
                    f"{label} {field} mismatch: {spec['member_id']}"
                )
        if member.get("media_type") != "application/json":
            raise M30PublishedBoundaryError(
                f"{label} media type mismatch: {spec['member_id']}"
            )
        if member.get("copy_requirement") != "unchanged_upstream_bytes":
            raise M30PublishedBoundaryError(
                f"{label} copy requirement mismatch: {spec['member_id']}"
            )
        encoded = member.get("payload_base64")
        if not isinstance(encoded, str):
            raise M30PublishedBoundaryError(
                f"{label} Base64 type mismatch: {spec['member_id']}"
            )
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise M30PublishedBoundaryError(
                f"{label} Base64 is invalid: {spec['member_id']}"
            ) from exc
        if len(decoded) != spec["byte_length"]:
            raise M30PublishedBoundaryError(
                f"{label} decoded byte length mismatch: {spec['member_id']}"
            )
        if _sha256(decoded) != spec["raw_sha256"]:
            raise M30PublishedBoundaryError(
                f"{label} decoded digest mismatch: {spec['member_id']}"
            )
        source_path = str(spec["source_path"])
        if decoded != retained_raw[source_path]:
            raise M30PublishedBoundaryError(
                f"{label} decoded bytes differ from M30 archive: {spec['member_id']}"
            )
        _json_object(decoded, f"{label} member {spec['member_id']}")
        result.append(
            PublishedDemoMember(
                member_id=str(spec["member_id"]),
                source_path=source_path,
                schema_identifier=str(spec["schema_identifier"]),
                observatory_modes=tuple(spec["observatory_modes"]),
                raw_sha256=str(spec["raw_sha256"]),
                byte_length=int(spec["byte_length"]),
            )
        )
    return tuple(result)


def _compatibility_key(member: Mapping[str, Any]) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "member_id": member["member_id"],
                "schema_identifier": member["schema_identifier"],
                "raw_sha256": member["raw_sha256"],
            }
        )
    )


def _validate_release_records(
    value: Mapping[str, Any],
    demo_package: Mapping[str, Any],
) -> None:
    label = "M29 release-independent compatibility records"
    _require_header(
        value,
        schema="frp.m29.release_independent_compatibility_records.v3.1.0",
        kind="release_independent_compatibility_records",
        milestone="M29",
        version="3.1.0",
        source_commit=_M29_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="record_set_digest",
        expected=(
            "b990f050a32d46fa27bd44f33d053ec26808d59658f1c2d7b2c87e7ac96b25da"
        ),
        label=label,
    )
    _require_equal(
        value,
        "compatibility_key_contract",
        {
            "algorithm": "sha256",
            "excluded_fields": [
                "upstream_release_label",
                "consumer_baseline_commit",
                "consumer_version",
            ],
            "included_fields": [
                "member_id",
                "schema_identifier",
                "raw_sha256",
            ],
            "observatory_versioning": "independent",
        },
        label,
    )
    records = value.get("records")
    demo_members = demo_package.get("members")
    if not isinstance(records, list) or not isinstance(demo_members, list):
        raise M30PublishedBoundaryError(f"{label} record inventory mismatch")
    if len(records) != 4 or len(demo_members) != 4:
        raise M30PublishedBoundaryError(f"{label} record count mismatch")
    _require_equal(value, "record_count", len(records), label)
    for record, member in zip(records, demo_members, strict=True):
        for field in ("member_id", "schema_identifier", "raw_sha256"):
            if record.get(field) != member.get(field):
                raise M30PublishedBoundaryError(
                    f"{label} {field} mismatch: {member.get('member_id')}"
                )
        if record.get("compatibility_key") != _compatibility_key(member):
            raise M30PublishedBoundaryError(
                f"{label} compatibility key mismatch: {member.get('member_id')}"
            )
        if record.get("compatibility_state") != "supported":
            raise M30PublishedBoundaryError(
                f"{label} compatibility state mismatch: {member.get('member_id')}"
            )
        if record.get("observatory_modes") != member.get("observatory_modes"):
            raise M30PublishedBoundaryError(
                f"{label} mode routing mismatch: {member.get('member_id')}"
            )
        if record.get("consumer_baseline_commit") != _OBSERVATORY_AUDITED_COMMIT:
            raise M30PublishedBoundaryError(
                f"{label} consumer baseline mismatch: {member.get('member_id')}"
            )
        if record.get("release_label_in_key") is not False:
            raise M30PublishedBoundaryError(
                f"{label} release label entered identity key"
            )
        if record.get("consumer_version_in_key") is not False:
            raise M30PublishedBoundaryError(
                f"{label} consumer version entered identity key"
            )


def _validate_consumption_vectors(value: Mapping[str, Any]) -> tuple[int, int]:
    label = "M29 downstream consumption vectors"
    _require_header(
        value,
        schema="frp.m29.downstream_consumption_test_vectors.v3.1.0",
        kind="downstream_consumption_test_vectors",
        milestone="M29",
        version="3.1.0",
        source_commit=_M29_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="vector_set_digest",
        expected=(
            "3057e2195ac07ee24aafdd644118629c929ee61f65e63e8dfad8ccf8741a4701"
        ),
        label=label,
    )
    vectors = value.get("vectors")
    if not isinstance(vectors, list) or len(vectors) != 12:
        raise M30PublishedBoundaryError(f"{label} vector inventory mismatch")
    _require_equal(value, "vector_count", len(vectors), label)
    accepted = sum(
        1 for vector in vectors if vector.get("expected_outcome") == "accepted"
    )
    rejected = sum(
        1 for vector in vectors if vector.get("expected_outcome") == "rejected"
    )
    _require_equal(value, "accepted_count", accepted, label)
    _require_equal(value, "rejected_count", rejected, label)
    if accepted != 4 or rejected != 8:
        raise M30PublishedBoundaryError(f"{label} outcome counts mismatch")
    for vector in vectors:
        if vector.get("status") != "PASS":
            raise M30PublishedBoundaryError(
                f"{label} contains a failed vector: {vector.get('vector_id')}"
            )
        if vector.get("observed_outcome") != vector.get("expected_outcome"):
            raise M30PublishedBoundaryError(
                f"{label} outcome mismatch: {vector.get('vector_id')}"
            )
        if vector.get("observed_reason") != vector.get("expected_reason"):
            raise M30PublishedBoundaryError(
                f"{label} reason mismatch: {vector.get('vector_id')}"
            )
    return accepted, rejected


def _validate_m30_alignment(value: Mapping[str, Any]) -> None:
    label = "M30 repository alignment record"
    _require_header(
        value,
        schema="frp.m30.repository_alignment_record.v3.2.0",
        kind="repository_alignment_record",
        milestone="M30",
        version="3.2.0",
        source_commit=_M30_SOURCE_COMMIT,
        label=label,
    )
    _require_digest(
        value,
        field="content_digest",
        expected=(
            "ce94e5d99dd37bb86c1c8a75df1084cd060241fbea2f10342c4e53e0f738d218"
        ),
        label=label,
    )
    _require_equal(value, "immutable_core", _M30_CORE, label)
    _require_equal(
        value,
        "observatory_boundary",
        {
            "audited_commit": _OBSERVATORY_AUDITED_COMMIT,
            "downstream_files_modified_by_m30": False,
            "downstream_semantic_reimplementation": "forbidden",
            "downstream_writeback": "forbidden",
            "existing_scaffold_action": "preserve_existing_scaffold",
            "integration_direction": "upstream_to_downstream_only",
            "repository": _OBSERVATORY_REPOSITORY,
            "upstream_dependency_on_downstream_code": False,
            "upstream_interchange_commit": _UPSTREAM_INTERCHANGE_COMMIT,
        },
        label,
    )
    records = value.get("records")
    expected_paths = [
        "README.md",
        "PROJECT_STRUCTURE.md",
        "CI.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "REPRODUCIBILITY.md",
    ]
    if not isinstance(records, list) or [
        record.get("path") for record in records if isinstance(record, dict)
    ] != expected_paths:
        raise M30PublishedBoundaryError(f"{label} record order mismatch")
    _require_equal(value, "record_count", len(records), label)
    for record in records:
        if record.get("status") != "aligned":
            raise M30PublishedBoundaryError(
                f"{label} contains an unaligned path: {record.get('path')}"
            )
        if record.get("historical_content_policy") != "preserved":
            raise M30PublishedBoundaryError(
                f"{label} history policy mismatch: {record.get('path')}"
            )
        for field in ("before_sha256", "after_sha256"):
            digest = record.get(field)
            if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
                raise M30PublishedBoundaryError(
                    f"{label} invalid {field}: {record.get('path')}"
                )
    _require_equal(
        value,
        "summary",
        {
            "aligned_document_count": 6,
            "current_milestone": (
                "M30 - Reproducibility, Qualification, and Archival "
                "Release Closure"
            ),
            "current_release": "FRP v3.2.0",
            "historical_records_preserved": True,
        },
        label,
    )


def _document_result(
    path: str,
    raw: bytes,
    value: Mapping[str, Any],
) -> PublishedBoundaryDocument:
    return PublishedBoundaryDocument(
        path=path,
        schema=str(value["schema"]),
        kind=str(value["kind"]),
        raw_sha256=_sha256(raw),
        byte_length=len(raw),
    )


def validate_m30_published_boundary(
    archive_path: str | Path,
) -> PublishedBoundaryValidation:
    """Validate the exact one-way M28-M30 published-byte boundary."""

    archive = validate_m30_archive(
        archive_path,
        retain_paths=_RETAIN_PATHS,
    )
    retained_raw = {
        retained.member.path: retained.raw_bytes
        for retained in archive.retained_members
    }
    if set(retained_raw) != set(_RETAIN_PATHS):
        raise M30PublishedBoundaryError(
            "retained M30 boundary member inventory mismatch"
        )
    documents = {
        path: _json_object(retained_raw[path], path)
        for path in _BOUNDARY_DOCUMENT_PATHS
    }

    _validate_m28_contract(documents[M28_UPSTREAM_CONTRACT_PATH])
    _validate_m28_registry(documents[M28_COMPATIBILITY_REGISTRY_PATH])
    _validate_m29_contract(documents[M29_INTEGRATION_CONTRACT_PATH])
    supported_artifact_count = _validate_m29_artifact_registry(
        documents[M29_ARTIFACT_REGISTRY_PATH],
        archive,
    )
    demo_members = _validate_demo_package(
        documents[M29_DEMO_PACKAGE_PATH],
        retained_raw,
    )
    _validate_release_records(
        documents[M29_RELEASE_RECORDS_PATH],
        documents[M29_DEMO_PACKAGE_PATH],
    )
    accepted, rejected = _validate_consumption_vectors(
        documents[M29_CONSUMPTION_VECTORS_PATH]
    )
    _validate_m30_alignment(documents[M30_ALIGNMENT_PATH])

    document_results = tuple(
        _document_result(path, retained_raw[path], documents[path])
        for path in _BOUNDARY_DOCUMENT_PATHS
    )
    return PublishedBoundaryValidation(
        archive_sha256=archive.archive_sha256,
        documents=document_results,
        supported_artifact_count=supported_artifact_count,
        demo_members=demo_members,
        accepted_vector_count=accepted,
        rejected_vector_count=rejected,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the exact read-only FRP M28-M30 published-byte boundary "
            "for FRP Trace Observatory."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate_m30_published_boundary(arguments.archive)
    print("FRP Observatory M30 published boundary intake: PASS")
    print(f"archive_sha256={result.archive_sha256}")
    print(f"boundary_documents={len(result.documents)}")
    print(f"supported_artifacts={result.supported_artifact_count}")
    print(f"demo_members={len(result.demo_members)}")
    print(f"accepted_vectors={result.accepted_vector_count}")
    print(f"rejected_vectors={result.rejected_vector_count}")
    print("immutable_core=-1/0/1")
    print("temporal_scheduler_modes=1/7,7/1")
    print("service_scheduler_mode=free")
    print("integration_direction=upstream_to_downstream_only")
    print("source_execution=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
