"""Read-only Artifact Auditor reports for exact FRP M31 publications.

This module is the first M31 mode consumer.  It accepts only the four
``artifact_auditor`` envelopes created by the dedicated M31 published
dispatch boundary.  Every report retains its exact envelope and its distinct
``M31PublishedMeasurementContour``.

The auditor independently replays strict JSON decoding, verifies captured
raw-byte and registry identities, and evaluates only declarations already
published in the four M31 documents.  It never executes upstream content,
normalizes metrics, combines thermal measurement contours, reimplements FRP
processor semantics, mutates source bytes, or writes upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid5

from artifact_auditor.audit_report import (
    AuditValueSnapshot,
    CheckOutcome,
    MessageSeverity,
    SourceLocation,
    ValidationCategory,
    ValidationCheck,
    ValidationStatus,
)
from artifact_auditor.m31_published_boundary_intake import (
    FRP_M30_ARCHIVE_SHA256,
    M31_PUBLISHED_DOCUMENT_IDENTITIES,
    M31_PUBLISHED_REGISTRY_REVISION,
    M31PublishedDocumentRole,
)
from parsers.json_artifact import parse_json_artifact
from parsers.m31_published_dispatch import (
    M31PublishedDispatchBatch,
    M31PublishedDocumentDispatch,
    dispatch_m31_published_documents,
)
from schemas.m31_published_registry import (
    M31PublishedMeasurementContour,
    registration_for_m31_role,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M31PublishedAuditBatch",
    "M31PublishedAuditReport",
    "M31PublishedAuditorError",
    "audit_m31_published_batch",
    "audit_m31_published_dispatch",
    "audit_m31_published_documents",
]


_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
_CHECK_NAMESPACE: Final = UUID("4f74b147-05d2-4f90-a3df-b7e22dc7b92f")
_REPORT_NAMESPACE: Final = UUID("e899221b-c2b5-4ad0-9d3f-f267d7ad5575")

_EVIDENCE_SCHEMA: Final = (
    "frp.m31.phase_interference_active_zero_thermal_evidence.v1"
)
_SCHEMA_DRAFT: Final = "https://json-schema.org/draft/2020-12/schema"
_SCHEMA_TITLE: Final = (
    "FRP M31 Phase-Interference Active-Zero Thermal Evidence"
)
_SCHEMA_ROOT_FIELDS: Final = (
    "$id",
    "$schema",
    "additionalProperties",
    "properties",
    "required",
    "title",
    "type",
)
_EVIDENCE_REQUIRED_FIELDS: Final = (
    "schema",
    "version",
    "milestone",
    "kind",
    "status",
    "core",
    "active_zero_execution_evidence",
    "historical_thermal_experiment",
    "current_comparative_thermal_contours",
    "evidence_boundaries",
    "observatory_publication_contract",
    "provenance",
)
_EVIDENCE_ROOT_FIELDS: Final = tuple(sorted(_EVIDENCE_REQUIRED_FIELDS))
_EVIDENCE_IDENTITY: Final = {
    "kind": "phase_interference_active_zero_thermal_evidence",
    "milestone": "M31",
    "schema": _EVIDENCE_SCHEMA,
    "status": "PASS",
    "version": "1.0.0",
}
_CORE_BOUNDARY: Final = {
    "active_neutral_state": 0,
    "balanced_ternary_notation": "-1/0/1",
    "classical_bit_addition_primary_mechanism": False,
    "opposite_transition_routes": [[-1, 0, 1], [1, 0, -1]],
    "primary_computational_organization": (
        "retained_relative_phase_interference_and_resonant_selection"
    ),
    "semantic_values": [-1, 0, 1],
    "service_scheduler_mode": "free",
    "temporal_scheduler_modes": ["1/7", "7/1"],
    "zero_role": "active_computational_state",
}
_ACTIVE_ZERO_BOUNDARY: Final = {
    "active_zero_after_observation_count": 702,
    "cell_observation_count": 800,
    "invariant_pass_records": 100,
    "observed_ternary_domain": [-1, 0, 1],
    "record_count": 100,
}
_HISTORICAL_ARCHITECTURE_ORDER: Final = (
    "binary_style_forced_switch",
    "direct_ternary_commit",
    "distributed_neutral_ternary",
    "frp_distributed_resonant",
)
_HISTORICAL_FOCUSED_RELATIONS: Final = {
    "heat_peak_ratio_binary_over_active_neutral_ternary": "15.6923076923",
    "heat_peak_relative_reduction_percent_exact": "93.6274509804",
    "switch_load_ratio_binary_over_active_neutral_ternary": "4.0",
}
_EVIDENCE_BOUNDARIES: Final = {
    "historical_and_current_contours_separate": True,
    "historical_heat_peak_is_not_current_rc_temperature_proxy": True,
    "normalized_activity_cost_is_not_physical_energy": True,
    "operation_count_is_not_thermal_load": True,
    "physical_measurement_required_for_silicon_temperature_claim": True,
    "scope_limited_relations_are_not_universal_winner_claims": True,
    "thermal_proxy_is_not_physical_temperature": True,
}
_PUBLICATION_CONTRACT: Final = {
    "direction": "upstream_published_bytes_to_downstream",
    "downstream_metric_normalization": "forbidden",
    "downstream_repository": "FRP-Trace-Observatory",
    "downstream_role": "read_only_validation_and_visualization",
    "downstream_semantic_reimplementation": "forbidden",
    "downstream_source_mutation": "forbidden",
    "downstream_writeback": "forbidden",
    "m29_boundary_confirmed": True,
    "published_contours_must_remain_separate": True,
    "upstream_repository": "FRP",
}
_MANIFEST_IDENTITY: Final = {
    "kind": "phase_interference_active_zero_thermal_evidence_manifest",
    "milestone": "M31",
    "schema": (
        "frp.m31.phase_interference_active_zero_thermal_evidence_manifest.v1"
    ),
    "status": "PASS",
    "version": "1.0.0",
}
_HISTORICAL_STDOUT_SHA256: Final = (
    "b18e1affec6dec8029086e923b907c9ae3cb0c50131e4291b31fbd2a4d97cbb6"
)
_QUALIFICATION_IDENTITY: Final = {
    "kind": "phase_interference_active_zero_thermal_evidence_qualification",
    "milestone": "M31",
    "schema": (
        "frp.m31.phase_interference_active_zero_thermal_evidence_qualification.v1"
    ),
    "status": "PASS",
    "version": "1.0.0",
}
_QUALIFICATION_CHECKS: Final = (
    "active_zero_trace_evidence_exact",
    "current_comparative_contours_integrity_pass",
    "direct_opposite_transitions_zero",
    "historical_experiment_reproduced",
    "historical_rows_exact",
    "m30_archive_members_byte_identical",
    "observatory_boundary_read_only",
    "physical_temperature_claim_absent",
    "scheduler_modes_exact",
    "source_digests_exact",
    "ternary_notation_exact",
    "thermal_measurement_contours_separate",
    "winner_assertions_absent",
)


class M31PublishedAuditorError(ValueError):
    """Raised when the M31 Artifact Auditor boundary is violated."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise M31PublishedAuditorError(
                "non-finite decimal in audit value"
            )
        return value
    return value


def _json_ready(value: Any) -> Any:
    value = _plain(value)
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _plain(value),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _selected(
    root: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    return {field: _plain(root.get(field)) for field in fields}


def _identity_record(role: M31PublishedDocumentRole) -> dict[str, object]:
    identity = next(
        candidate
        for candidate in M31_PUBLISHED_DOCUMENT_IDENTITIES
        if candidate.role is role
    )
    return {
        "byte_count": identity.byte_length,
        "path": identity.source_path,
        "raw_sha256": identity.raw_sha256,
    }


def _source_location(
    dispatch: M31PublishedDocumentDispatch,
    json_path: str | None = None,
) -> tuple[SourceLocation, ...]:
    return (
        SourceLocation(
            package_member=dispatch.route.registration.source_path,
            json_path=json_path,
        ),
    )


def _check_id(
    dispatch: M31PublishedDocumentDispatch,
    check_code: str,
) -> str:
    return str(
        uuid5(
            _CHECK_NAMESPACE,
            f"{dispatch.dispatch_sha256}:{check_code}",
        )
    )


def _make_check(
    dispatch: M31PublishedDocumentDispatch,
    *,
    check_code: str,
    category: ValidationCategory,
    passed: bool,
    expected: Any,
    observed: Any,
    message: str,
    json_path: str | None = None,
    upstream_rule_reference: str | None = None,
) -> ValidationCheck:
    if not isinstance(passed, bool):
        raise M31PublishedAuditorError("check result must be a boolean")
    return ValidationCheck(
        check_id=_check_id(dispatch, check_code),
        check_code=check_code,
        category=category,
        outcome=CheckOutcome.PASS if passed else CheckOutcome.FAIL,
        severity=None if passed else MessageSeverity.ERROR,
        source_locations=_source_location(dispatch, json_path),
        expected=AuditValueSnapshot(expected),
        observed=AuditValueSnapshot(observed),
        message=message,
        upstream_rule_reference=upstream_rule_reference,
        mandatory=True,
    )


def _common_checks(
    dispatch: M31PublishedDocumentDispatch,
) -> tuple[ValidationCheck, ...]:
    document = dispatch.document
    registration = dispatch.route.registration
    validation = dispatch.registry_validation
    replay = parse_json_artifact(dispatch.source_artifact)
    source_identity = {
        "byte_length": dispatch.source_artifact.byte_length,
        "raw_sha256": dispatch.source_artifact.content_sha256,
        "source_path": dispatch.source_artifact.source_path,
    }
    expected_source_identity = {
        "byte_length": registration.byte_length,
        "raw_sha256": registration.raw_sha256,
        "source_path": registration.source_path,
    }
    dispatch_binding = {
        "canonical_registration_identity": (
            registration is registration_for_m31_role(dispatch.role)
        ),
        "document_identity": any(
            candidate is document
            for candidate in validation.boundary.documents
        ),
        "parsed_identity": (
            dispatch.parsed_artifact is document.parsed_artifact
        ),
        "raw_bytes_identity": dispatch.raw_bytes is document.raw_bytes,
        "route_identity": any(
            candidate is dispatch.route for candidate in validation.routes
        ),
        "source_identity": (
            dispatch.source_artifact is document.source_artifact
        ),
    }
    observed_identifier = {
        "identifier": _plain(
            dispatch.parsed_artifact.root.get(
                registration.identifier_field
            )
        ),
        "kind": dispatch.parsed_artifact.declared_kind,
    }
    expected_identifier = {
        "identifier": registration.identifier_value,
        "kind": registration.artifact_kind,
    }
    replay_matches = (
        replay.source_artifact is dispatch.source_artifact
        and replay.root == dispatch.parsed_artifact.root
        and replay.text_encoding is dispatch.parsed_artifact.text_encoding
    )
    contour_valid = (
        isinstance(
            registration.measurement_contour,
            M31PublishedMeasurementContour,
        )
        and dispatch.route.registration is registration
    )
    return (
        _make_check(
            dispatch,
            check_code="M31A.COMMON.MODE",
            category=ValidationCategory.IDENTITY,
            passed=dispatch.mode is ObservatoryMode.ARTIFACT_AUDITOR,
            expected=ObservatoryMode.ARTIFACT_AUDITOR.value,
            observed=dispatch.mode.value,
            message="The report accepts only the registered Artifact Auditor route.",
            upstream_rule_reference="M31 published registry observatory_modes",
        ),
        _make_check(
            dispatch,
            check_code="M31A.COMMON.REGISTRY",
            category=ValidationCategory.IDENTITY,
            passed=(
                validation.registry_revision
                == M31_PUBLISHED_REGISTRY_REVISION
                and validation.boundary.registry_revision
                == M31_PUBLISHED_REGISTRY_REVISION
            ),
            expected=M31_PUBLISHED_REGISTRY_REVISION,
            observed=validation.registry_revision,
            message="The report retains the exact M31 registry revision.",
            upstream_rule_reference="M31 published boundary registry revision",
        ),
        _make_check(
            dispatch,
            check_code="M31A.COMMON.RAW_SOURCE",
            category=ValidationCategory.DIGEST,
            passed=(
                dispatch.source_artifact.verify_integrity()
                and dispatch.raw_bytes == document.raw_bytes
                and source_identity == expected_source_identity
            ),
            expected=expected_source_identity,
            observed=source_identity,
            message="Raw path, byte length, and SHA-256 match the M31 registration.",
            upstream_rule_reference="M31 raw published source identity",
        ),
        _make_check(
            dispatch,
            check_code="M31A.COMMON.DISPATCH_BINDING",
            category=ValidationCategory.IDENTITY,
            passed=all(dispatch_binding.values()),
            expected={key: True for key in dispatch_binding},
            observed=dispatch_binding,
            message=(
                "The report retains exact boundary, registry, and dispatch "
                "identities."
            ),
            upstream_rule_reference="M31 immutable published dispatch envelope",
        ),
        _make_check(
            dispatch,
            check_code="M31A.COMMON.STRICT_REPLAY",
            category=ValidationCategory.CONTAINER,
            passed=replay_matches,
            expected=True,
            observed=replay_matches,
            message="Independent strict JSON replay matches the retained parsed view.",
            upstream_rule_reference="M31 strict JSON publication boundary",
        ),
        _make_check(
            dispatch,
            check_code="M31A.COMMON.IDENTIFIER",
            category=ValidationCategory.IDENTITY,
            passed=observed_identifier == expected_identifier,
            expected=expected_identifier,
            observed=observed_identifier,
            message="Published identifier and kind match the exact registration.",
            json_path="$",
            upstream_rule_reference="M31 exact published document identity",
        ),
        _make_check(
            dispatch,
            check_code="M31A.COMMON.CONTOUR",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=contour_valid,
            expected=registration.measurement_contour.value,
            observed=registration.measurement_contour.value,
            message="The registered M31 measurement contour remains distinct.",
            upstream_rule_reference=(
                "M31 published_contours_must_remain_separate"
            ),
        ),
    )


def _schema_checks(
    dispatch: M31PublishedDocumentDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    properties = plain.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    declaration = {
        "$schema": plain.get("$schema"),
        "additionalProperties": plain.get("additionalProperties"),
        "title": plain.get("title"),
        "type": plain.get("type"),
    }
    expected_declaration = {
        "$schema": _SCHEMA_DRAFT,
        "additionalProperties": False,
        "title": _SCHEMA_TITLE,
        "type": "object",
    }
    expected_constants = {
        "kind": _EVIDENCE_IDENTITY["kind"],
        "milestone": "M31",
        "schema": _EVIDENCE_SCHEMA,
        "status": "PASS",
        "version": "1.0.0",
    }
    observed_constants = {
        name: properties.get(name, {}).get("const")
        if isinstance(properties.get(name), dict)
        else None
        for name in expected_constants
    }
    provenance = properties.get("provenance")
    provenance_minimum = (
        provenance.get("minItems")
        if isinstance(provenance, dict)
        else None
    )
    return (
        _make_check(
            dispatch,
            check_code="M31A.SCHEMA.ROOT_FIELDS",
            category=ValidationCategory.STRUCTURE,
            passed=tuple(sorted(plain)) == _SCHEMA_ROOT_FIELDS,
            expected=_SCHEMA_ROOT_FIELDS,
            observed=tuple(sorted(plain)),
            message="The formal-schema root field inventory is exact.",
            json_path="$",
            upstream_rule_reference="M31 formal schema root",
        ),
        _make_check(
            dispatch,
            check_code="M31A.SCHEMA.DECLARATION",
            category=ValidationCategory.CONTAINER,
            passed=declaration == expected_declaration,
            expected=expected_declaration,
            observed=declaration,
            message="The JSON Schema draft, object boundary, and title are exact.",
            json_path="$",
            upstream_rule_reference="M31 JSON Schema 2020-12 declaration",
        ),
        _make_check(
            dispatch,
            check_code="M31A.SCHEMA.FIELD_INVENTORY",
            category=ValidationCategory.STRUCTURE,
            passed=(
                plain.get("required") == list(_EVIDENCE_REQUIRED_FIELDS)
                and tuple(sorted(properties)) == _EVIDENCE_ROOT_FIELDS
            ),
            expected={
                "properties": _EVIDENCE_ROOT_FIELDS,
                "required": _EVIDENCE_REQUIRED_FIELDS,
            },
            observed={
                "properties": tuple(sorted(properties)),
                "required": plain.get("required"),
            },
            message=(
                "Schema properties and required fields match the evidence "
                "document."
            ),
            json_path="$.required",
            upstream_rule_reference="M31 evidence field inventory",
        ),
        _make_check(
            dispatch,
            check_code="M31A.SCHEMA.CONSTRAINTS",
            category=ValidationCategory.ALLOWED_VALUE,
            passed=(
                observed_constants == expected_constants
                and provenance_minimum == 12
            ),
            expected={
                "constants": expected_constants,
                "provenance_min_items": 12,
            },
            observed={
                "constants": observed_constants,
                "provenance_min_items": provenance_minimum,
            },
            message="Identity constants and provenance minimum are exact.",
            json_path="$.properties",
            upstream_rule_reference="M31 formal schema constants",
        ),
    )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _integer_sum(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    values = tuple(value.values())
    if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
        return None
    return sum(values)


def _evidence_checks(
    dispatch: M31PublishedDocumentDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    core = _mapping(plain.get("core"))
    active = _mapping(plain.get("active_zero_execution_evidence"))
    historical = _mapping(plain.get("historical_thermal_experiment"))
    current = _mapping(plain.get("current_comparative_thermal_contours"))
    baseline = _mapping(current.get("baseline"))
    hardware = _mapping(current.get("hardware_sensitivity"))
    focused = _mapping(
        historical.get("focused_binary_ternary_comparison")
    )
    boundaries = _mapping(plain.get("evidence_boundaries"))
    contract = _mapping(plain.get("observatory_publication_contract"))

    active_boundary = _selected(active, tuple(_ACTIVE_ZERO_BOUNDARY))
    active_events = _mapping(active.get("event_totals"))
    transition_counts = _mapping(active.get("retained_transition_counts"))
    aggregate_relations = {
        "direct_opposite": transition_counts.get("direct_opposite"),
        "actual_direct_events": active_events.get("actual_direct_events"),
        "reserved_state_events": active_events.get("reserved_state_events"),
        "queue_overflow_events": active_events.get("queue_overflow_events"),
        "scheduler_mode_total": _integer_sum(
            active.get("scheduler_mode_counts")
        ),
        "scheduler_state_total": _integer_sum(
            active.get("scheduler_state_counts")
        ),
        "retained_transition_total": _integer_sum(transition_counts),
    }
    expected_aggregate_relations = {
        "direct_opposite": 0,
        "actual_direct_events": 0,
        "reserved_state_events": 0,
        "queue_overflow_events": 0,
        "scheduler_mode_total": 100,
        "scheduler_state_total": 100,
        "retained_transition_total": 800,
    }
    architecture_order = historical.get("architecture_order")
    historical_summary = {
        "architecture_order": (
            tuple(architecture_order)
            if isinstance(architecture_order, list)
            else architecture_order
        ),
        "evidence_class": historical.get("evidence_class"),
        "focused_relations": _selected(
            focused,
            tuple(_HISTORICAL_FOCUSED_RELATIONS),
        ),
        "measurement_class": historical.get("measurement_class"),
        "physical_temperature_measurement": historical.get(
            "physical_temperature_measurement"
        ),
        "row_count": len(historical.get("rows", []))
        if isinstance(historical.get("rows"), list)
        else None,
        "winner_assertions": historical.get("winner_assertions"),
    }
    expected_historical_summary = {
        "architecture_order": _HISTORICAL_ARCHITECTURE_ORDER,
        "evidence_class": "reproduced_release_benchmark",
        "focused_relations": _HISTORICAL_FOCUSED_RELATIONS,
        "measurement_class": "release_specific_model_thermal_load",
        "physical_temperature_measurement": False,
        "row_count": 4,
        "winner_assertions": [],
    }
    current_summary = {
        "baseline_qualification_status": baseline.get(
            "qualification_status"
        ),
        "baseline_winner_assertions": baseline.get("winner_assertions"),
        "hardware_qualification_status": hardware.get(
            "qualification_status"
        ),
        "hardware_winner_assertions": hardware.get("winner_assertions"),
        "historical_heat_peak_interchangeable": current.get(
            "historical_heat_peak_interchangeable"
        ),
        "measurement_class": current.get("measurement_class"),
        "physical_temperature_measurement": current.get(
            "physical_temperature_measurement"
        ),
    }
    expected_current_summary = {
        "baseline_qualification_status": "PASS",
        "baseline_winner_assertions": [],
        "hardware_qualification_status": "PASS",
        "hardware_winner_assertions": [],
        "historical_heat_peak_interchangeable": False,
        "measurement_class": "shared_model_comparative_benchmark",
        "physical_temperature_measurement": False,
    }

    provenance = plain.get("provenance")
    if not isinstance(provenance, list):
        provenance = []
    boundary = dispatch.registry_validation.boundary
    expected_provenance = []
    for source in boundary.provenance_sources:
        record: dict[str, object] = {
            "byte_count": source.source_artifact.byte_length,
            "m30_archive_member_verified": (
                source.m30_archive_member_verified
            ),
            "path": source.source_path,
            "raw_sha256": source.source_artifact.content_sha256,
        }
        if source.role is not None:
            record["role"] = source.role
        expected_provenance.append(record)
    source_integrity = all(
        source.source_artifact.verify_integrity()
        for source in boundary.provenance_sources
    )
    archive_verified_count = sum(
        source.m30_archive_member_verified
        for source in boundary.provenance_sources
    )
    provenance_summary = {
        "archive_member_count": boundary.m30_archive_member_count,
        "archive_sha256": boundary.m30_archive_sha256,
        "current_source_integrity": source_integrity,
        "published_record_count": len(provenance),
        "records_match_current_sources": provenance == expected_provenance,
        "verified_archive_member_count": archive_verified_count,
    }
    expected_provenance_summary = {
        "archive_member_count": 10,
        "archive_sha256": FRP_M30_ARCHIVE_SHA256,
        "current_source_integrity": True,
        "published_record_count": 12,
        "records_match_current_sources": True,
        "verified_archive_member_count": 10,
    }
    return (
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=(
                tuple(sorted(plain)) == _EVIDENCE_ROOT_FIELDS
                and _selected(plain, tuple(_EVIDENCE_IDENTITY))
                == _EVIDENCE_IDENTITY
            ),
            expected={
                "fields": _EVIDENCE_ROOT_FIELDS,
                "identity": _EVIDENCE_IDENTITY,
            },
            observed={
                "fields": tuple(sorted(plain)),
                "identity": _selected(plain, tuple(_EVIDENCE_IDENTITY)),
            },
            message="The M31 evidence root inventory and identity are exact.",
            json_path="$",
            upstream_rule_reference=_EVIDENCE_SCHEMA,
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.CORE",
            category=ValidationCategory.TERNARY_DOMAIN,
            passed=_selected(core, tuple(_CORE_BOUNDARY)) == _CORE_BOUNDARY,
            expected=_CORE_BOUNDARY,
            observed=_selected(core, tuple(_CORE_BOUNDARY)),
            message="The published -1/0/1 active-neutral processor boundary is exact.",
            json_path="$.core",
            upstream_rule_reference="M31 immutable processor core boundary",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.ACTIVE_ZERO_COUNTS",
            category=ValidationCategory.INVARIANT_VECTOR,
            passed=active_boundary == _ACTIVE_ZERO_BOUNDARY,
            expected=_ACTIVE_ZERO_BOUNDARY,
            observed=active_boundary,
            message="Published active-zero counts and ternary domain are exact.",
            json_path="$.active_zero_execution_evidence",
            upstream_rule_reference="M31 active-zero execution evidence",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.ACTIVE_ZERO_RELATIONS",
            category=ValidationCategory.TRANSITION_CAPACITY,
            passed=aggregate_relations == expected_aggregate_relations,
            expected=expected_aggregate_relations,
            observed=aggregate_relations,
            message="Zero-event and source-published aggregate relations hold.",
            json_path="$.active_zero_execution_evidence",
            upstream_rule_reference="M31 active-zero aggregate relations",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.HISTORICAL_CONTOUR",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=historical_summary == expected_historical_summary,
            expected=expected_historical_summary,
            observed=historical_summary,
            message=(
                "Historical thermal evidence remains one release-specific "
                "model contour."
            ),
            json_path="$.historical_thermal_experiment",
            upstream_rule_reference="M31 historical thermal experiment",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.CURRENT_CONTOURS",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=current_summary == expected_current_summary,
            expected=expected_current_summary,
            observed=current_summary,
            message=(
                "Current comparative contours retain their published "
                "qualifications."
            ),
            json_path="$.current_comparative_thermal_contours",
            upstream_rule_reference="M31 current comparative thermal contours",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.BOUNDARIES",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=boundaries == _EVIDENCE_BOUNDARIES,
            expected=_EVIDENCE_BOUNDARIES,
            observed=boundaries,
            message="All seven interpretation boundaries remain explicit and true.",
            json_path="$.evidence_boundaries",
            upstream_rule_reference="M31 evidence interpretation boundaries",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.PUBLICATION_CONTRACT",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=contract == _PUBLICATION_CONTRACT,
            expected=_PUBLICATION_CONTRACT,
            observed=contract,
            message="The one-way read-only Observatory publication contract is exact.",
            json_path="$.observatory_publication_contract",
            upstream_rule_reference="M31 Observatory publication contract",
        ),
        _make_check(
            dispatch,
            check_code="M31A.EVIDENCE.PROVENANCE",
            category=ValidationCategory.DETERMINISTIC_PACKAGE,
            passed=provenance_summary == expected_provenance_summary,
            expected=expected_provenance_summary,
            observed=provenance_summary,
            message=(
                "All twelve source identities and ten M30 archive members "
                "remain exact."
            ),
            json_path="$.provenance",
            upstream_rule_reference="M31 exact source provenance inventory",
        ),
    )


def _manifest_checks(
    dispatch: M31PublishedDocumentDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    expected_fields = (
        "generated_files",
        "historical_experiment_stdout_sha256",
        "kind",
        "milestone",
        "schema",
        "source_count",
        "status",
        "version",
    )
    expected_generated = [
        _identity_record(M31PublishedDocumentRole.FORMAL_SCHEMA),
        _identity_record(M31PublishedDocumentRole.EVIDENCE),
    ]
    return (
        _make_check(
            dispatch,
            check_code="M31A.MANIFEST.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=(
                tuple(sorted(plain)) == expected_fields
                and _selected(plain, tuple(_MANIFEST_IDENTITY))
                == _MANIFEST_IDENTITY
            ),
            expected={
                "fields": expected_fields,
                "identity": _MANIFEST_IDENTITY,
            },
            observed={
                "fields": tuple(sorted(plain)),
                "identity": _selected(plain, tuple(_MANIFEST_IDENTITY)),
            },
            message="The publication manifest root and identity are exact.",
            json_path="$",
            upstream_rule_reference="M31 publication manifest identity",
        ),
        _make_check(
            dispatch,
            check_code="M31A.MANIFEST.SOURCE_DECLARATION",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=(
                plain.get("source_count") == 12
                and plain.get("historical_experiment_stdout_sha256")
                == _HISTORICAL_STDOUT_SHA256
            ),
            expected={
                "historical_experiment_stdout_sha256": (
                    _HISTORICAL_STDOUT_SHA256
                ),
                "source_count": 12,
            },
            observed={
                "historical_experiment_stdout_sha256": plain.get(
                    "historical_experiment_stdout_sha256"
                ),
                "source_count": plain.get("source_count"),
            },
            message="Manifest source count and historical stdout digest are exact.",
            json_path="$",
            upstream_rule_reference="M31 publication source declaration",
        ),
        _make_check(
            dispatch,
            check_code="M31A.MANIFEST.GENERATED_FILES",
            category=ValidationCategory.DIGEST,
            passed=plain.get("generated_files") == expected_generated,
            expected=expected_generated,
            observed=plain.get("generated_files"),
            message=(
                "Manifest output paths, byte lengths, and SHA-256 values "
                "are exact."
            ),
            json_path="$.generated_files",
            upstream_rule_reference="M31 generated publication identities",
        ),
    )


def _qualification_checks(
    dispatch: M31PublishedDocumentDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    expected_fields = (
        "checks",
        "kind",
        "milestone",
        "outputs",
        "schema",
        "status",
        "version",
    )
    expected_checks = {name: True for name in _QUALIFICATION_CHECKS}
    expected_outputs = [
        _identity_record(M31PublishedDocumentRole.FORMAL_SCHEMA),
        _identity_record(M31PublishedDocumentRole.EVIDENCE),
        _identity_record(M31PublishedDocumentRole.MANIFEST),
    ]
    return (
        _make_check(
            dispatch,
            check_code="M31A.QUALIFICATION.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=(
                tuple(sorted(plain)) == expected_fields
                and _selected(plain, tuple(_QUALIFICATION_IDENTITY))
                == _QUALIFICATION_IDENTITY
            ),
            expected={
                "fields": expected_fields,
                "identity": _QUALIFICATION_IDENTITY,
            },
            observed={
                "fields": tuple(sorted(plain)),
                "identity": _selected(
                    plain,
                    tuple(_QUALIFICATION_IDENTITY),
                ),
            },
            message="The M31 qualification root and identity are exact.",
            json_path="$",
            upstream_rule_reference="M31 publication qualification identity",
        ),
        _make_check(
            dispatch,
            check_code="M31A.QUALIFICATION.CHECKS",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("checks") == expected_checks,
            expected=expected_checks,
            observed=plain.get("checks"),
            message="All thirteen exact upstream qualification checks pass.",
            json_path="$.checks",
            upstream_rule_reference="M31 publication qualification checks",
        ),
        _make_check(
            dispatch,
            check_code="M31A.QUALIFICATION.OUTPUTS",
            category=ValidationCategory.DIGEST,
            passed=plain.get("outputs") == expected_outputs,
            expected=expected_outputs,
            observed=plain.get("outputs"),
            message=(
                "Qualification output identities bind schema, evidence, "
                "and manifest."
            ),
            json_path="$.outputs",
            upstream_rule_reference="M31 qualified publication outputs",
        ),
    )


def _document_checks(
    dispatch: M31PublishedDocumentDispatch,
) -> tuple[ValidationCheck, ...]:
    root = dispatch.parsed_artifact.root
    try:
        if dispatch.role is M31PublishedDocumentRole.FORMAL_SCHEMA:
            return _schema_checks(dispatch, root)
        if dispatch.role is M31PublishedDocumentRole.EVIDENCE:
            return _evidence_checks(dispatch, root)
        if dispatch.role is M31PublishedDocumentRole.MANIFEST:
            return _manifest_checks(dispatch, root)
        if dispatch.role is M31PublishedDocumentRole.QUALIFICATION:
            return _qualification_checks(dispatch, root)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return (
            _make_check(
                dispatch,
                check_code="M31A.DOCUMENT.STRUCTURAL_FAILURE",
                category=ValidationCategory.STRUCTURE,
                passed=False,
                expected="well_formed_registered_document",
                observed=type(exc).__name__,
                message=(
                    "The registered M31 document could not be audited "
                    "structurally."
                ),
                json_path="$",
                upstream_rule_reference="M31 published document structure",
            ),
        )
    raise M31PublishedAuditorError(
        f"unsupported M31 published document role: {dispatch.role!r}"
    )


def _derived_status(
    checks: tuple[ValidationCheck, ...],
) -> ValidationStatus:
    if any(
        check.mandatory and check.outcome is CheckOutcome.FAIL
        for check in checks
    ):
        return ValidationStatus.RECOGNIZED_INVALID
    return ValidationStatus.RECOGNIZED_VALID


def _check_payload(check: ValidationCheck) -> dict[str, Any]:
    return {
        "category": check.category.value,
        "check_code": check.check_code,
        "check_id": check.check_id,
        "expected": (
            None
            if check.expected is None
            else _json_ready(check.expected.value)
        ),
        "mandatory": check.mandatory,
        "message": check.message,
        "observed": (
            None
            if check.observed is None
            else _json_ready(check.observed.value)
        ),
        "outcome": check.outcome.value,
        "severity": (
            None if check.severity is None else check.severity.value
        ),
        "source_locations": [
            {
                "array_index": location.array_index,
                "column_number": location.column_number,
                "json_path": location.json_path,
                "line_number": location.line_number,
                "markdown_heading": location.markdown_heading,
                "markdown_table_row": location.markdown_table_row,
                "package_member": location.package_member,
                "source_record_ordinal": location.source_record_ordinal,
                "vector_column": location.vector_column,
            }
            for location in check.source_locations
        ],
        "upstream_rule_reference": check.upstream_rule_reference,
    }


def _report_sha256(
    dispatch: M31PublishedDocumentDispatch,
    contour: M31PublishedMeasurementContour,
    checks: tuple[ValidationCheck, ...],
    status: ValidationStatus,
) -> str:
    registration = dispatch.route.registration
    boundary = dispatch.registry_validation.boundary
    return _sha256(
        _compact_json_bytes(
            {
                "checks": [_check_payload(check) for check in checks],
                "compatibility_key": registration.compatibility_key,
                "dispatch_sha256": dispatch.dispatch_sha256,
                "identifier_field": registration.identifier_field,
                "identifier_value": registration.identifier_value,
                "m30_archive_sha256": boundary.m30_archive_sha256,
                "measurement_contour": contour.value,
                "overall_status": status.value,
                "raw_sha256": registration.raw_sha256,
                "registry_revision": (
                    dispatch.registry_validation.registry_revision
                ),
                "role": dispatch.role.value,
                "source_path": registration.source_path,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M31PublishedAuditReport:
    """One deterministic report retaining an exact M31 auditor envelope."""

    audit_report_id: str
    dispatch: M31PublishedDocumentDispatch
    measurement_contour: M31PublishedMeasurementContour
    checks: tuple[ValidationCheck, ...]
    overall_status: ValidationStatus
    report_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.dispatch, M31PublishedDocumentDispatch):
            raise M31PublishedAuditorError(
                "dispatch must be M31PublishedDocumentDispatch"
            )
        if self.dispatch.mode is not ObservatoryMode.ARTIFACT_AUDITOR:
            raise M31PublishedAuditorError(
                "M31 audit report requires an artifact_auditor route"
            )
        expected_contour = (
            self.dispatch.route.registration.measurement_contour
        )
        if self.measurement_contour is not expected_contour:
            raise M31PublishedAuditorError(
                "report contour differs from the M31 registration"
            )
        if not isinstance(self.checks, tuple) or not self.checks:
            raise M31PublishedAuditorError(
                "checks must be a nonempty tuple"
            )
        if any(not isinstance(check, ValidationCheck) for check in self.checks):
            raise M31PublishedAuditorError(
                "checks must contain ValidationCheck values"
            )
        check_codes = tuple(check.check_code for check in self.checks)
        check_ids = tuple(check.check_id for check in self.checks)
        if len(set(check_codes)) != len(check_codes):
            raise M31PublishedAuditorError("check codes must be unique")
        if len(set(check_ids)) != len(check_ids):
            raise M31PublishedAuditorError(
                "check identifiers must be unique"
            )
        expected_ids = tuple(
            _check_id(self.dispatch, check.check_code)
            for check in self.checks
        )
        if check_ids != expected_ids:
            raise M31PublishedAuditorError(
                "check identifiers do not bind this exact M31 dispatch"
            )
        expected_status = _derived_status(self.checks)
        if self.overall_status is not expected_status:
            raise M31PublishedAuditorError(
                "overall status differs from mandatory check outcomes"
            )
        if not isinstance(self.report_sha256, str) or not _HEX64.fullmatch(
            self.report_sha256
        ):
            raise M31PublishedAuditorError(
                "report_sha256 must be lowercase hexadecimal SHA-256"
            )
        expected_digest = _report_sha256(
            self.dispatch,
            self.measurement_contour,
            self.checks,
            self.overall_status,
        )
        if self.report_sha256 != expected_digest:
            raise M31PublishedAuditorError(
                "report_sha256 does not bind the exact report evidence"
            )
        expected_id = str(uuid5(_REPORT_NAMESPACE, self.report_sha256))
        if self.audit_report_id != expected_id:
            raise M31PublishedAuditorError(
                "audit_report_id does not bind the deterministic report digest"
            )

    @property
    def role(self) -> M31PublishedDocumentRole:
        """Return the exact M31 document role."""

        return self.dispatch.role

    @property
    def passed_count(self) -> int:
        """Return the number of successful mandatory checks."""

        return sum(check.outcome is CheckOutcome.PASS for check in self.checks)

    @property
    def failed_count(self) -> int:
        """Return the number of failed mandatory checks."""

        return sum(check.outcome is CheckOutcome.FAIL for check in self.checks)


def _build_report(
    dispatch: M31PublishedDocumentDispatch,
) -> M31PublishedAuditReport:
    checks = _common_checks(dispatch) + _document_checks(dispatch)
    status = _derived_status(checks)
    contour = dispatch.route.registration.measurement_contour
    report_digest = _report_sha256(dispatch, contour, checks, status)
    return M31PublishedAuditReport(
        audit_report_id=str(uuid5(_REPORT_NAMESPACE, report_digest)),
        dispatch=dispatch,
        measurement_contour=contour,
        checks=checks,
        overall_status=status,
        report_sha256=report_digest,
    )


def audit_m31_published_dispatch(
    dispatch: M31PublishedDocumentDispatch,
) -> M31PublishedAuditReport:
    """Audit one exact M31 Artifact Auditor dispatch."""

    if not isinstance(dispatch, M31PublishedDocumentDispatch):
        raise M31PublishedAuditorError(
            "dispatch must be M31PublishedDocumentDispatch"
        )
    if dispatch.mode is not ObservatoryMode.ARTIFACT_AUDITOR:
        raise M31PublishedAuditorError(
            "only artifact_auditor M31 dispatches may be audited"
        )
    if not dispatch.source_artifact.verify_integrity():
        raise M31PublishedAuditorError(
            "dispatch source integrity verification failed"
        )
    return _build_report(dispatch)


def _batch_sha256(
    dispatch_batch: M31PublishedDispatchBatch,
    reports: tuple[M31PublishedAuditReport, ...],
    status: ValidationStatus,
) -> str:
    return _sha256(
        _compact_json_bytes(
            {
                "m30_archive_sha256": (
                    dispatch_batch.registry_validation
                    .boundary.m30_archive_sha256
                ),
                "overall_status": status.value,
                "registry_revision": dispatch_batch.registry_revision,
                "reports": [report.report_sha256 for report in reports],
            }
        )
    )


@dataclass(frozen=True, slots=True)
class M31PublishedAuditBatch:
    """Complete ordered four-report M31 Artifact Auditor result."""

    dispatch_batch: M31PublishedDispatchBatch
    reports: tuple[M31PublishedAuditReport, ...]
    overall_status: ValidationStatus
    batch_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.dispatch_batch, M31PublishedDispatchBatch):
            raise M31PublishedAuditorError(
                "dispatch_batch must be M31PublishedDispatchBatch"
            )
        if not isinstance(self.reports, tuple):
            raise M31PublishedAuditorError("reports must be a tuple")
        if any(
            not isinstance(report, M31PublishedAuditReport)
            for report in self.reports
        ):
            raise M31PublishedAuditorError(
                "reports must contain M31PublishedAuditReport values"
            )
        expected_dispatches = self.dispatch_batch.dispatches_for_mode(
            ObservatoryMode.ARTIFACT_AUDITOR
        )
        if len(self.reports) != len(expected_dispatches) or len(self.reports) != 4:
            raise M31PublishedAuditorError(
                "M31 audit report inventory length mismatch"
            )
        for report, dispatch in zip(
            self.reports,
            expected_dispatches,
            strict=True,
        ):
            if report.dispatch is not dispatch:
                raise M31PublishedAuditorError(
                    "report order or exact dispatch identity mismatch"
                )
        expected_roles = tuple(
            identity.role for identity in M31_PUBLISHED_DOCUMENT_IDENTITIES
        )
        if tuple(report.role for report in self.reports) != expected_roles:
            raise M31PublishedAuditorError(
                "M31 audit report role inventory mismatch"
            )
        expected_status = (
            ValidationStatus.RECOGNIZED_VALID
            if all(
                report.overall_status is ValidationStatus.RECOGNIZED_VALID
                for report in self.reports
            )
            else ValidationStatus.RECOGNIZED_INVALID
        )
        if self.overall_status is not expected_status:
            raise M31PublishedAuditorError(
                "batch status differs from report outcomes"
            )
        if not isinstance(self.batch_sha256, str) or not _HEX64.fullmatch(
            self.batch_sha256
        ):
            raise M31PublishedAuditorError(
                "batch_sha256 must be lowercase hexadecimal SHA-256"
            )
        expected_digest = _batch_sha256(
            self.dispatch_batch,
            self.reports,
            self.overall_status,
        )
        if self.batch_sha256 != expected_digest:
            raise M31PublishedAuditorError(
                "batch_sha256 does not bind the complete report inventory"
            )

    @property
    def total_check_count(self) -> int:
        """Return the total number of report checks."""

        return sum(len(report.checks) for report in self.reports)

    @property
    def failed_check_count(self) -> int:
        """Return the total number of failed checks."""

        return sum(report.failed_count for report in self.reports)

    def report_for_role(
        self,
        role: M31PublishedDocumentRole,
    ) -> M31PublishedAuditReport:
        """Resolve one exact M31 role report without string aliases."""

        if not isinstance(role, M31PublishedDocumentRole):
            raise M31PublishedAuditorError(
                "role must be M31PublishedDocumentRole"
            )
        matches = tuple(
            report for report in self.reports if report.role is role
        )
        if len(matches) != 1:
            raise M31PublishedAuditorError(
                f"unknown M31 audit report role: {role!r}"
            )
        return matches[0]


def audit_m31_published_batch(
    dispatch_batch: M31PublishedDispatchBatch,
) -> M31PublishedAuditBatch:
    """Build all four reports from a complete M31 dispatch batch."""

    if not isinstance(dispatch_batch, M31PublishedDispatchBatch):
        raise M31PublishedAuditorError(
            "dispatch_batch must be M31PublishedDispatchBatch"
        )
    dispatches = dispatch_batch.dispatches_for_mode(
        ObservatoryMode.ARTIFACT_AUDITOR
    )
    reports = tuple(
        audit_m31_published_dispatch(dispatch)
        for dispatch in dispatches
    )
    status = (
        ValidationStatus.RECOGNIZED_VALID
        if all(
            report.overall_status is ValidationStatus.RECOGNIZED_VALID
            for report in reports
        )
        else ValidationStatus.RECOGNIZED_INVALID
    )
    digest = _batch_sha256(dispatch_batch, reports, status)
    return M31PublishedAuditBatch(
        dispatch_batch=dispatch_batch,
        reports=reports,
        overall_status=status,
        batch_sha256=digest,
    )


def audit_m31_published_documents(
    upstream_root: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> M31PublishedAuditBatch:
    """Validate and audit the four exact M31 publications read-only."""

    return audit_m31_published_batch(
        dispatch_m31_published_documents(
            upstream_root,
            loaded_at=loaded_at,
        )
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build four deterministic read-only Artifact Auditor reports "
            "from the exact FRP M31 published dispatch boundary."
        )
    )
    parser.add_argument("--upstream-root", required=True, type=Path)
    arguments = parser.parse_args()
    result = audit_m31_published_documents(arguments.upstream_root)
    print(
        "FRP Observatory M31 published Artifact Auditor: "
        f"{'PASS' if result.failed_check_count == 0 else 'FAIL'}"
    )
    print(f"registry_revision={result.dispatch_batch.registry_revision}")
    print(
        "m30_archive_sha256="
        f"{result.dispatch_batch.registry_validation.boundary.m30_archive_sha256}"
    )
    print(
        "published_documents="
        f"{result.dispatch_batch.published_document_count}"
    )
    print(f"audit_reports={len(result.reports)}")
    print(f"validation_checks={result.total_check_count}")
    print(f"failed_checks={result.failed_check_count}")
    print(f"batch_sha256={result.batch_sha256}")
    for report in result.reports:
        print(
            f"report={report.role.value} "
            f"contour={report.measurement_contour.value} "
            f"checks={len(report.checks)} "
            f"status={report.overall_status.value} "
            f"sha256={report.report_sha256}"
        )
    print("source_execution=forbidden")
    print("metric_normalization=forbidden")
    print("thermal_contour_merging=forbidden")
    print("semantic_reimplementation=forbidden")
    print("source_mutation=forbidden")
    print("downstream_writeback=forbidden")
    return 0 if result.failed_check_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
