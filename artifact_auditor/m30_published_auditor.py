"""Read-only Artifact Auditor reports for exact FRP M30 publications.

This module is the first M30 mode consumer.  It accepts only the four
``artifact_auditor`` envelopes created by the dedicated M5 published dispatch
boundary.  Each report retains its exact M5 dispatch object and its distinct
``PublishedMeasurementContour``.  The implementation deliberately does not
reuse the legacy schema-only dispatcher or legacy ``MeasurementContour``
report binding.

The auditor verifies the captured raw-byte identity, independently replays the
strict JSON decoder, checks each publication with the canonical digest
algorithm used by its producer, and evaluates only rules declared by that
publication.  It never executes upstream code, follows producer paths,
normalizes absent fields, combines measurement contours, mutates source bytes,
or writes back upstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from artifact_auditor.m30_archive_intake import FRP_M30_ARCHIVE_SHA256
from parsers.json_artifact import parse_json_artifact
from parsers.m30_published_dispatch import (
    PublishedDispatchBatch,
    PublishedModeDispatch,
    dispatch_m30_published_members,
)
from schemas.m30_published_registry import (
    M30_PUBLISHED_REGISTRY_REVISION,
    PublishedMeasurementContour,
    registration_for_member_id,
)
from schemas.registry import ObservatoryMode


__all__ = [
    "M30PublishedAuditorError",
    "PublishedAuditBatch",
    "PublishedAuditReport",
    "audit_m30_published_archive",
    "audit_m30_published_batch",
    "audit_m30_published_dispatch",
]


_HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
_CHECK_NAMESPACE: Final = UUID("ac2c58c8-c71e-4d76-9217-ae40f69958e5")
_REPORT_NAMESPACE: Final = UUID("57ee973b-77a0-46ea-b27e-31ad55d82520")

_M16_MEMBER_ID: Final = "m16-fpga-preparation-execution-trace"
_M27_MEMBER_ID: Final = "m27-telemetry-semantics"
_M28_UPSTREAM_MEMBER_ID: Final = (
    "m28-trace-observatory-upstream-contract"
)
_M28_HIERARCHY_MEMBER_ID: Final = "m28-hierarchical-scaling-contract"

_TERNARY_DOMAIN: Final = (-1, 0, 1)
_OPPOSITE_ROUTES: Final = ((-1, 0, 1), (1, 0, -1))
_TEMPORAL_SCHEDULERS: Final = ("1/7", "7/1")

_M16_ROOT_FIELDS: Final = (
    "configuration",
    "execution_epochs",
    "kind",
    "layer",
    "measurement_contours",
    "milestone",
    "monitor",
    "qualified_source",
    "raw_trace",
    "records",
    "schema",
    "source_release",
    "source_testbench",
    "summary",
    "version",
)
_M16_IDENTITY: Final = {
    "kind": "m16_fpga_preparation_execution_trace",
    "layer": "fpga_preparation",
    "milestone": "M19 — Machine-Readable M16 Execution and Qualification Evidence",
    "schema": "frp.m16.fpga_preparation_execution_trace.v2.1.0",
    "source_release": "FRP v1.8.0 / M16",
    "version": "2.1.0",
}
_M16_CONFIGURATION: Final = {
    "cells": 8,
    "counter_bits": 32,
    "request_lanes": 2,
    "state_bits": 2,
    "transition_fraction_denominator": 4,
    "transition_fraction_numerator": 1,
}
_M16_EPOCHS: Final = (
    {"epoch": 0, "mode": "free", "record_count": 3},
    {"epoch": 1, "mode": "1/7", "record_count": 1},
)
_M16_QUALIFIED_SOURCE: Final = {
    "branch": "main",
    "commit": "ede53cf",
    "commit_identity_format": "short_git_sha",
    "result": "SUCCESS",
    "workflow": ".github/workflows/frp-m16-fpga-preparation.yml",
    "workflow_run": 2,
}
_M16_RAW_TRACE_DECLARATION: Final = {
    "byte_length": 396,
    "format": "frp.m19.m16_execution_raw.v1",
    "path": "artifacts/m19/raw/m16-fpga-preparation-execution.trace",
    "raw_sha256": (
        "05168f3d1e9b56f6f99fa5001a705168355431e976b3b152972d2bceb07a3439"
    ),
    "record_count": 4,
}
_M16_INVARIANT_NAMES: Final = (
    "state_domain_valid",
    "scheduler_counts_valid",
    "request_lane_order_valid",
    "pending_polarity_valid",
    "active_neutral_valid",
    "transition_capacity_valid",
    "state_update_valid",
    "no_actual_direct_events",
    "no_reserved_state",
    "no_queue_overflow",
)

_M27_ROOT_FIELDS: Final = (
    "artifact_id",
    "interpretation_boundary",
    "milestone",
    "schema_version",
    "semantics_digest",
    "source_commit",
    "status",
    "telemetry",
    "telemetry_count",
    "validated_relations",
)
_M27_IDENTITY: Final = {
    "artifact_id": "frp-m27-telemetry-semantics",
    "milestone": "M27",
    "schema_version": "2.9.0",
    "source_commit": "67e9cc6d3e5dd2e96380b7cadb16b66f5e7d2427",
    "status": "PASS",
}
_M27_TELEMETRY: Final = (
    {
        "classification": "dimensionless_model_derived_event_fraction_proxy",
        "domain": {"maximum": 65_536, "minimum": 0},
        "relation": "round(changes * 65536 / cells)",
        "storage_type": "signed_integer_s32q16",
        "telemetry_id": "switching_load_q16",
    },
    {
        "classification": "dimensionless_model_state_proxy",
        "domain": {"maximum": 2_147_483_647, "minimum": 0},
        "relation": "integer mean of per-cell model heat state",
        "storage_type": "signed_integer_s32q16",
        "telemetry_id": "thermal_state_proxy_q16",
    },
    {
        "classification": "dimensionless_model_derived_pressure_proxy",
        "domain": {"maximum": 2_147_483_647, "minimum": 0},
        "relation": "thermal_state_proxy_q16 + switching_load_q16",
        "storage_type": "signed_integer_s32q16",
        "telemetry_id": "transition_pressure_q16",
    },
    {
        "classification": "dimensionless_model_coherence_metric",
        "domain": {"maximum": 1_073_741_824, "minimum": 0},
        "relation": "quantized global phase-order metric",
        "storage_type": "signed_integer_s32q30",
        "telemetry_id": "global_phase_coherence_q30",
    },
    {
        "classification": "dimensionless_model_capacity_proxy",
        "domain": {"maximum": 2_147_483_647, "minimum": -2_147_483_648},
        "relation": "canonical fixed-point model coherence capacity C",
        "storage_type": "signed_integer_s32q16",
        "telemetry_id": "coherence_capacity_q16",
    },
    {
        "classification": "dimensionless_model_stability_margin",
        "domain": {"maximum": 2_147_483_647, "minimum": -2_147_483_648},
        "relation": "coherence_capacity_q16 - transition_pressure_q16",
        "storage_type": "signed_integer_s32q16",
        "telemetry_id": "stability_margin_q16",
    },
)
_M27_VALIDATED_RELATIONS: Final = (
    "transition_pressure_q16 equals thermal_state_proxy_q16 plus switching_load_q16",
    "stability_margin_q16 equals coherence_capacity_q16 minus transition_pressure_q16",
    "changes never exceeds request_lanes",
    "pending_route_count never exceeds queue_capacity",
)
_M27_INTERPRETATION_BOUNDARY: Final = {
    "all_values_are_dimensionless": True,
    "all_values_are_model_derived": True,
    "physical_measurements_published": False,
    "physical_units_published": False,
    "unsupported_physical_interpretation": "prohibited",
}

_M28_UPSTREAM_IDENTITY: Final = {
    "kind": "trace_observatory_upstream_contract",
    "milestone": "M28",
    "schema": "frp.m28.trace_observatory_upstream_contract.v3.0.0",
    "source_commit": "23e464206f85cd9473101d9221027ee33d9dd094",
    "status": "PASS",
    "upstream_release": "FRP v3.0.0 / M28",
    "version": "3.0.0",
}
_M28_UPSTREAM_CORE: Final = {
    "active_neutral_state": 0,
    "balanced_ternary_notation": "-1/0/1",
    "opposite_transition_routes": [list(route) for route in _OPPOSITE_ROUTES],
    "semantic_values": list(_TERNARY_DOMAIN),
    "service_scheduler_mode": "free",
    "temporal_scheduler_modes": list(_TEMPORAL_SCHEDULERS),
}
_M28_INTEGRATION_DIRECTION: Final = {
    "consumer": "FRP-Trace-Observatory",
    "direction": "upstream_to_downstream_only",
    "downstream_source_mutation": "forbidden",
    "downstream_writeback": "forbidden",
    "producer": "Fractal-Resonance-Processor",
    "transport": "published_versioned_artifacts",
    "upstream_semantic_authority": True,
}
_M28_DATA_CONTRACT: Final = {
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
}
_M28_IMPLEMENTED_LAYERS: Final = (
    {"mode": "artifact_auditor", "path": "artifact_auditor/"},
    {"mode": "trace_explorer", "path": "trace_explorer/"},
    {
        "mode": "ternary_transition_visualizer",
        "path": "transition_visualizer/",
    },
)
_M28_EXPORT_SCOPE: Final = {
    "downstream_repository_files_modified": False,
    "measurement_contours_remain_separate": True,
    "published_observatory_modes": [
        "artifact_auditor",
        "ternary_transition_visualizer",
        "trace_explorer",
    ],
    "source_fixture_count": 6,
    "trace_dataset_count": 3,
    "ui_dependencies_in_upstream": False,
}

_M28_HIERARCHY_IDENTITY: Final = {
    "kind": "hierarchical_scaling_contract",
    "milestone": "M28",
    "release": "FRP v3.0.0",
    "schema": "frp.m28.hierarchical_scaling_contract.v3.0.0",
    "source_commit": "23e464206f85cd9473101d9221027ee33d9dd094",
    "status": "PASS",
    "version": "3.0.0",
}
_M28_HIERARCHY_SCOPE: Final = (
    "declared_hierarchy_topology",
    "cluster_identities",
    "cell_to_cluster_mapping",
    "cluster_local_scheduler_observation",
    "cluster_local_transition_capacity_observation",
    "cluster_local_telemetry",
    "hotspot_containment_indicators",
    "hierarchy_level_provenance",
    "deterministic_scaling_matrices",
    "explicit_aggregation_equations",
    "machine_readable_hierarchy_manifests",
)
_M28_HIERARCHY_CORE: Final = {
    "active_neutral_state": 0,
    "actual_direct_events_target": 0,
    "balanced_ternary_notation": "-1/0/1",
    "opposite_transition_routes": [list(route) for route in _OPPOSITE_ROUTES],
    "queue_overflow_events_target": 0,
    "reserved_state_events_target": 0,
    "semantic_values": list(_TERNARY_DOMAIN),
    "service_scheduler_mode": "free",
    "temporal_scheduler_modes": list(_TEMPORAL_SCHEDULERS),
}
_M28_HIERARCHY_BOUNDARY: Final = {
    "cluster_size_cells": 4,
    "declared_interaction_scaling": "O(N log N)",
    "execution_path": "hierarchical_reference",
    "hierarchy_depth_relation": "log2(cells)",
    "hierarchy_distance_relation": "bit_length(cell_i XOR cell_j)",
    "qualified_cell_counts": [8, 16, 32],
    "shell_population_relation": "2^(distance-1)",
    "topology": "dyadic_ultrametric_contiguous_domains",
}
_M28_AGGREGATION_EQUATIONS: Final = {
    "cluster_heat_mean": "sum(cell_heat_q16) // cluster_cell_count",
    "cluster_heat_peak": "max(cell_heat_q16)",
    "cluster_pressure_q16": "cluster_heat_mean_q16 + cluster_switch_load_q16",
    "cluster_state_count": "count(state == value for state in cluster)",
    "cluster_switch_changes": "sum(cell_switch_activity)",
    "cluster_switch_load_q16": (
        "round(cluster_switch_changes * 65536 / cluster_cell_count)"
    ),
    "global_from_cluster_count": "sum(cluster_count)",
    "no_undeclared_metric_aggregation": True,
}
_M28_MEASUREMENT_BOUNDARY: Final = {
    "cluster_telemetry": "model_derived_dimensionless_proxy",
    "measurement_contours": [
        "hierarchical_scaling",
        "localized_hotspot_containment",
        "m27_long_run_telemetry",
        "m28_observatory_publication_interchange",
    ],
    "measurement_contours_remain_separate": True,
    "physical_measurement_status": "not_a_physical_measurement",
    "proxy_to_physical_conversion": "prohibited",
    "universal_physical_chip_claim": "not_made",
}
_M28_PROVENANCE_BOUNDARY: Final = {
    "hierarchy_role": "primary_M28_realization",
    "long_run_contract": "artifacts/m27/contracts/m27-long-run-telemetry-contract.json",
    "long_run_source": "artifacts/m27/checkpoints/m27-long-run-checkpoint-evidence.json",
    "observatory_interchange_commit": (
        "566a4ff88baa57f844691b46937552253e095434"
    ),
    "observatory_interchange_role": "additional_publication_layer",
    "prior_hierarchy_qualification": (
        "docs/m14_physical_implementation_correlation_production_qualification.md"
    ),
    "semantic_authority": "frp_prototype_v1_7_0.py",
}


class M30PublishedAuditorError(ValueError):
    """Raised when the published Artifact Auditor boundary is violated."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise M30PublishedAuditorError("non-finite decimal in audit value")
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


def _compact_json_bytes(value: Any, *, ensure_ascii: bool) -> bytes:
    return json.dumps(
        _plain(value),
        allow_nan=False,
        ensure_ascii=ensure_ascii,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _m16_document_bytes(value: Any) -> bytes:
    return _compact_json_bytes(value, ensure_ascii=False) + b"\n"


def _m28_hierarchy_document_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _plain(value),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_without_field(
    root: Mapping[str, Any],
    field: str,
    *,
    hierarchy_style: bool = False,
) -> str:
    payload = _plain(root)
    payload.pop(field, None)
    raw = (
        _m28_hierarchy_document_bytes(payload)
        if hierarchy_style
        else _compact_json_bytes(payload, ensure_ascii=True)
    )
    return _sha256(raw)


def _source_location(
    dispatch: PublishedModeDispatch,
    json_path: str | None = None,
) -> tuple[SourceLocation, ...]:
    return (
        SourceLocation(
            package_member=dispatch.member.registration.source_path,
            json_path=json_path,
        ),
    )


def _check_id(dispatch: PublishedModeDispatch, check_code: str) -> str:
    return str(
        uuid5(
            _CHECK_NAMESPACE,
            f"{dispatch.dispatch_sha256}:{check_code}",
        )
    )


def _make_check(
    dispatch: PublishedModeDispatch,
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
        raise M30PublishedAuditorError("check result must be a boolean")
    outcome = CheckOutcome.PASS if passed else CheckOutcome.FAIL
    return ValidationCheck(
        check_id=_check_id(dispatch, check_code),
        check_code=check_code,
        category=category,
        outcome=outcome,
        severity=None if passed else MessageSeverity.ERROR,
        source_locations=_source_location(dispatch, json_path),
        expected=AuditValueSnapshot(expected),
        observed=AuditValueSnapshot(observed),
        message=message,
        upstream_rule_reference=upstream_rule_reference,
        mandatory=True,
    )


def _selected(root: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    return {field: _plain(root.get(field)) for field in fields}


def _common_checks(
    dispatch: PublishedModeDispatch,
) -> tuple[ValidationCheck, ...]:
    member = dispatch.member
    registration = member.registration
    replay = parse_json_artifact(dispatch.source_artifact)
    observed_identifier = tuple(
        (evidence.field_name, _plain(dispatch.parsed_artifact.root.get(evidence.field_name)))
        for evidence in member.identifier_evidence
    )
    expected_identifier = tuple(
        (evidence.field_name, evidence.value)
        for evidence in member.identifier_evidence
    )
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
            registration
            is registration_for_member_id(registration.member_id)
        ),
        "registration_identity": dispatch.route.registration is registration,
        "route_identity": any(route is dispatch.route for route in member.routes),
        "source_identity": dispatch.source_artifact is member.source_artifact,
        "parsed_identity": dispatch.parsed_artifact is member.parsed_artifact,
        "retained_bytes_identity": (
            dispatch.raw_bytes is member.retained_member.raw_bytes
        ),
    }
    return (
        _make_check(
            dispatch,
            check_code="M30A.COMMON.MODE",
            category=ValidationCategory.IDENTITY,
            passed=dispatch.mode is ObservatoryMode.ARTIFACT_AUDITOR,
            expected=ObservatoryMode.ARTIFACT_AUDITOR.value,
            observed=dispatch.mode.value,
            message="M5 route targets only the published Artifact Auditor consumer.",
            upstream_rule_reference="M30 published registry observatory_modes",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.ARCHIVE",
            category=ValidationCategory.DETERMINISTIC_PACKAGE,
            passed=member.archive_sha256 == FRP_M30_ARCHIVE_SHA256,
            expected=FRP_M30_ARCHIVE_SHA256,
            observed=member.archive_sha256,
            message="The report retains the exact M1 archive identity.",
            upstream_rule_reference="FRP v3.2.0 M30 archival release",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.REGISTRY",
            category=ValidationCategory.IDENTITY,
            passed=member.registry_revision
            == M30_PUBLISHED_REGISTRY_REVISION,
            expected=M30_PUBLISHED_REGISTRY_REVISION,
            observed=member.registry_revision,
            message="The report retains the exact M3 published registry revision.",
            upstream_rule_reference="M30 published boundary registry revision",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.RAW_SOURCE",
            category=ValidationCategory.DIGEST,
            passed=(
                dispatch.source_artifact.verify_integrity()
                and dispatch.raw_bytes == member.retained_member.raw_bytes
                and source_identity == expected_source_identity
            ),
            expected=expected_source_identity,
            observed=source_identity,
            message="Raw source bytes, path, length, and SHA-256 match the M3 registration.",
            upstream_rule_reference="M28 data contract digest_scope=raw_source_bytes",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.DISPATCH_BINDING",
            category=ValidationCategory.IDENTITY,
            passed=all(dispatch_binding.values()),
            expected={key: True for key in dispatch_binding},
            observed=dispatch_binding,
            message="The report retains exact M4 member and M5 route object identities.",
            upstream_rule_reference="M5 immutable published dispatch envelope",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.STRICT_REPLAY",
            category=ValidationCategory.CONTAINER,
            passed=(
                replay.source_artifact is dispatch.source_artifact
                and replay.root == dispatch.parsed_artifact.root
                and replay.text_encoding is dispatch.parsed_artifact.text_encoding
            ),
            expected=True,
            observed=(
                replay.source_artifact is dispatch.source_artifact
                and replay.root == dispatch.parsed_artifact.root
                and replay.text_encoding is dispatch.parsed_artifact.text_encoding
            ),
            message="Independent strict JSON replay matches the retained M4 parsed view.",
            upstream_rule_reference="M28 data contract container_format=json",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.IDENTIFIER",
            category=ValidationCategory.IDENTITY,
            passed=observed_identifier == expected_identifier,
            expected=expected_identifier,
            observed=observed_identifier,
            message="Published identifier fields match the exact M3 registration without aliases.",
            upstream_rule_reference="M3 exact published identifier binding",
        ),
        _make_check(
            dispatch,
            check_code="M30A.COMMON.CONTOUR",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=isinstance(
                registration.measurement_contour,
                PublishedMeasurementContour,
            ),
            expected=registration.measurement_contour.value,
            observed=registration.measurement_contour.value,
            message="The distinct M30 published measurement contour remains unchanged.",
            upstream_rule_reference="M28 measurement_contours_remain_separate",
        ),
    )


def _m16_checks(
    dispatch: PublishedModeDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    records = plain.get("records")
    if not isinstance(records, list):
        records = []
    epochs = plain.get("execution_epochs")
    if not isinstance(epochs, list):
        epochs = []

    state_fields = (
        "retained_state_before",
        "retained_state_after",
        "pending_route_before",
        "pending_route_after",
        "phase_derived_targets",
    )
    domain_valid = len(records) == 4
    active_neutral_valid = len(records) == 4
    scheduler_valid = len(records) == 4
    capacity_valid = len(records) == 4
    invariant_valid = len(records) == 4
    zero_event_valid = len(records) == 4
    for expected_sequence, record in enumerate(records):
        if not isinstance(record, dict):
            domain_valid = active_neutral_valid = scheduler_valid = False
            capacity_valid = invariant_valid = zero_event_valid = False
            continue
        arrays = [record.get(field) for field in state_fields]
        requests = record.get("requests")
        domain_valid = domain_valid and all(
            isinstance(values, list)
            and len(values) == 8
            and all(value in _TERNARY_DOMAIN for value in values)
            for values in arrays
        )
        domain_valid = domain_valid and isinstance(requests, list) and len(requests) == 2
        if isinstance(requests, list):
            domain_valid = domain_valid and all(
                isinstance(request, dict)
                and request.get("target_state") in _TERNARY_DOMAIN
                for request in requests
            )

        before = record.get("retained_state_before")
        after = record.get("retained_state_after")
        active_neutral_valid = active_neutral_valid and (
            isinstance(before, list)
            and isinstance(after, list)
            and len(before) == len(after) == 8
            and all(
                (left, right) not in ((-1, 1), (1, -1))
                for left, right in zip(before, after, strict=True)
            )
        )

        scheduler = record.get("scheduler")
        expected_mode = "free" if expected_sequence < 3 else "1/7"
        expected_state = "free" if expected_sequence < 3 else "excite"
        expected_tick_before = expected_sequence if expected_sequence < 3 else 0
        if not isinstance(scheduler, dict):
            scheduler_valid = False
        else:
            counters = scheduler.get("counters_after")
            scheduler_valid = scheduler_valid and (
                record.get("sequence") == expected_sequence
                and record.get("execution_epoch") == (0 if expected_sequence < 3 else 1)
                and scheduler.get("mode") == expected_mode
                and scheduler.get("state") == expected_state
                and scheduler.get("ticks_before") == expected_tick_before
                and scheduler.get("ticks_after") == expected_tick_before + 1
                and isinstance(counters, dict)
                and sum(counters.values()) == scheduler.get("ticks_after")
            )

        capacity = record.get("transition_capacity")
        telemetry = record.get("telemetry")
        if not isinstance(capacity, dict) or not isinstance(telemetry, dict):
            capacity_valid = False
        else:
            accepted = capacity.get("accepted_changes")
            remaining = capacity.get("capacity_remaining")
            capacity_valid = capacity_valid and (
                isinstance(accepted, int)
                and not isinstance(accepted, bool)
                and 0 <= accepted <= 2
                and capacity.get("capacity_limit") == 2
                and remaining == 2 - accepted
                and capacity.get("capacity_exhausted") is (remaining == 0)
                and telemetry.get("switch_load_denominator") == 8
                and telemetry.get("switch_load_numerator") == accepted
                and telemetry.get("switch_load_q16") == accepted * 8192
                and len(record.get("accepted_change_cell_ids", [])) == accepted
            )

        invariants = record.get("invariants")
        if not isinstance(invariants, dict):
            invariant_valid = False
        else:
            flags = invariants.get("flags")
            invariant_valid = invariant_valid and (
                invariants.get("all_pass") is True
                and isinstance(flags, list)
                and tuple(
                    flag.get("name")
                    for flag in flags
                    if isinstance(flag, dict)
                )
                == _M16_INVARIANT_NAMES
                and all(
                    isinstance(flag, dict) and flag.get("pass") is True
                    for flag in flags
                )
            )

        events = record.get("events")
        zero_event_valid = zero_event_valid and isinstance(events, dict) and all(
            events.get(name) == 0
            for name in (
                "actual_direct_events",
                "reserved_state_events",
                "queue_overflow_events",
            )
        )

    record_digest = _sha256(_m16_document_bytes(records))
    summary = plain.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    event_names = (
        "actual_direct_events",
        "neutral_routed_events",
        "prevented_direct_events",
        "queue_overflow_events",
        "requested_direct_events",
        "reserved_state_events",
    )
    calculated_event_totals = {
        name: sum(
            record.get("events", {}).get(name, 0)
            for record in records
            if isinstance(record, dict)
            and isinstance(record.get("events"), dict)
        )
        for name in event_names
    }
    scheduler_states = Counter(
        record.get("scheduler", {}).get("state")
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("scheduler"), dict)
    )
    calculated_summary = {
        "event_totals": calculated_event_totals,
        "execution_epoch_count": len(epochs),
        "invariant_pass_records": sum(
            isinstance(record, dict)
            and isinstance(record.get("invariants"), dict)
            and record["invariants"].get("all_pass") is True
            for record in records
        ),
        "maximum_switch_load_numerator": max(
            (
                record.get("telemetry", {}).get("switch_load_numerator", -1)
                for record in records
                if isinstance(record, dict)
                and isinstance(record.get("telemetry"), dict)
            ),
            default=-1,
        ),
        "record_count": len(records),
        "record_digest": record_digest,
        "scheduler_state_counts": dict(sorted(scheduler_states.items())),
        "total_accepted_changes": sum(
            record.get("transition_capacity", {}).get("accepted_changes", 0)
            for record in records
            if isinstance(record, dict)
            and isinstance(record.get("transition_capacity"), dict)
        ),
        "zero_event_status": "PASS",
    }
    contours = plain.get("measurement_contours")
    contour_valid = isinstance(contours, dict) and (
        contours.get("m16_execution", {}).get("availability")
        == "emitted_by_m16_execution_boundary"
        and contours.get("m15_semantic_reference", {}).get("correlation_status")
        == "not_evaluated_in_m19"
        and contours.get("physical_measurement", {}).get("availability")
        == "not_in_scope"
        and contours.get("physical_measurement", {}).get("correlation_status")
        == "not_evaluated"
    )
    return (
        _make_check(
            dispatch,
            check_code="M30A.M16.ROOT_FIELDS",
            category=ValidationCategory.STRUCTURE,
            passed=tuple(sorted(plain)) == _M16_ROOT_FIELDS,
            expected=_M16_ROOT_FIELDS,
            observed=tuple(sorted(plain)),
            message="M16 FPGA trace root field set is exact.",
            json_path="$",
            upstream_rule_reference="M19 M16 execution trace schema",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=_selected(plain, tuple(_M16_IDENTITY)) == _M16_IDENTITY,
            expected=_M16_IDENTITY,
            observed=_selected(plain, tuple(_M16_IDENTITY)),
            message="M16 FPGA trace identity and source release are exact.",
            json_path="$",
            upstream_rule_reference="frp.m16.fpga_preparation_execution_trace.v2.1.0",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.CONFIGURATION",
            category=ValidationCategory.TRANSITION_CAPACITY,
            passed=plain.get("configuration") == _M16_CONFIGURATION,
            expected=_M16_CONFIGURATION,
            observed=plain.get("configuration"),
            message="M16 cell, lane, state-bit, and transition-fraction configuration is exact.",
            json_path="$.configuration",
            upstream_rule_reference="M16 FPGA execution configuration",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.PROVENANCE",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=(
                plain.get("qualified_source") == _M16_QUALIFIED_SOURCE
                and plain.get("raw_trace") == _M16_RAW_TRACE_DECLARATION
            ),
            expected={
                "qualified_source": _M16_QUALIFIED_SOURCE,
                "raw_trace": _M16_RAW_TRACE_DECLARATION,
            },
            observed={
                "qualified_source": plain.get("qualified_source"),
                "raw_trace": plain.get("raw_trace"),
            },
            message="M16 qualification and raw-trace declarations remain exact metadata only.",
            json_path="$",
            upstream_rule_reference="M19 qualified source boundary",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.EPOCH_ORDER",
            category=ValidationCategory.ORDERING,
            passed=epochs == list(_M16_EPOCHS),
            expected=_M16_EPOCHS,
            observed=epochs,
            message="M16 source-order free and 1/7 execution epochs are exact.",
            json_path="$.execution_epochs",
            upstream_rule_reference="M19 FPGA expected_epochs",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.TERNARY_DOMAIN",
            category=ValidationCategory.TERNARY_DOMAIN,
            passed=domain_valid,
            expected=True,
            observed=domain_valid,
            message="Every published M16 state and request target remains in -1/0/1.",
            json_path="$.records",
            upstream_rule_reference="M19 ternary canonical domain",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.ACTIVE_NEUTRAL",
            category=ValidationCategory.PENDING_ROUTE,
            passed=active_neutral_valid,
            expected=True,
            observed=active_neutral_valid,
            message="Opposite-polarity M16 transitions remain routed through active neutral 0.",
            json_path="$.records",
            upstream_rule_reference="M19 active_neutral:no_direct_transition",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.SCHEDULER",
            category=ValidationCategory.SCHEDULER_RELATION,
            passed=scheduler_valid,
            expected=True,
            observed=scheduler_valid,
            message="M16 scheduler mode, state, tick, and counter relations are exact.",
            json_path="$.records[*].scheduler",
            upstream_rule_reference="M19 scheduler-state relation",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.CAPACITY",
            category=ValidationCategory.TRANSITION_CAPACITY,
            passed=capacity_valid,
            expected=True,
            observed=capacity_valid,
            message="M16 accepted-change, remaining-capacity, and switch-load relations hold.",
            json_path="$.records",
            upstream_rule_reference="M19 transition capacity relation",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.INVARIANTS",
            category=ValidationCategory.INVARIANT_VECTOR,
            passed=invariant_valid,
            expected=True,
            observed=invariant_valid,
            message="All ten M16 invariant flags are present, ordered, and passing.",
            json_path="$.records[*].invariants",
            upstream_rule_reference="M19 invariant vector",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.ZERO_EVENTS",
            category=ValidationCategory.ALLOWED_VALUE,
            passed=zero_event_valid,
            expected=True,
            observed=zero_event_valid,
            message="Actual-direct, reserved-state, and queue-overflow events remain zero.",
            json_path="$.records[*].events",
            upstream_rule_reference="M19 zero-event invariant",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.RECORD_DIGEST",
            category=ValidationCategory.DIGEST,
            passed=summary.get("record_digest") == record_digest,
            expected=record_digest,
            observed=summary.get("record_digest"),
            message="M16 record digest matches canonical source-order records.",
            json_path="$.summary.record_digest",
            upstream_rule_reference="M19 canonical_json_bytes(records)",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.SUMMARY",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=summary == calculated_summary,
            expected=calculated_summary,
            observed=summary,
            message="M16 summary is derived exactly from the retained record sequence.",
            json_path="$.summary",
            upstream_rule_reference="M19 execution trace summary",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M16.CONTOURS",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=contour_valid,
            expected=True,
            observed=contour_valid,
            message="M16 execution, M15 semantic reference, and physical contours remain separate.",
            json_path="$.measurement_contours",
            upstream_rule_reference="M19 measurement contours",
        ),
    )


def _m27_checks(
    dispatch: PublishedModeDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    telemetry = plain.get("telemetry")
    if not isinstance(telemetry, list):
        telemetry = []
    observed_digest = plain.get("semantics_digest")
    expected_digest = _digest_without_field(plain, "semantics_digest")
    telemetry_ids = tuple(
        item.get("telemetry_id")
        for item in telemetry
        if isinstance(item, dict)
    )
    unique_ids = len(telemetry_ids) == len(set(telemetry_ids)) == 6
    domain_valid = len(telemetry) == 6 and all(
        isinstance(item, dict)
        and isinstance(item.get("domain"), dict)
        and isinstance(item["domain"].get("minimum"), int)
        and not isinstance(item["domain"].get("minimum"), bool)
        and isinstance(item["domain"].get("maximum"), int)
        and not isinstance(item["domain"].get("maximum"), bool)
        and item["domain"]["minimum"] <= item["domain"]["maximum"]
        for item in telemetry
    )
    return (
        _make_check(
            dispatch,
            check_code="M30A.M27.ROOT_FIELDS",
            category=ValidationCategory.STRUCTURE,
            passed=tuple(sorted(plain)) == _M27_ROOT_FIELDS,
            expected=_M27_ROOT_FIELDS,
            observed=tuple(sorted(plain)),
            message="M27 telemetry semantics root field set is exact and has no schema alias.",
            json_path="$",
            upstream_rule_reference="M27 telemetry semantics publication",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=_selected(plain, tuple(_M27_IDENTITY)) == _M27_IDENTITY
            and "schema" not in plain,
            expected={**_M27_IDENTITY, "schema_field_absent": True},
            observed={
                **_selected(plain, tuple(_M27_IDENTITY)),
                "schema_field_absent": "schema" not in plain,
            },
            message="M27 keeps its artifact_id plus schema_version identity without a synthetic schema field.",
            json_path="$",
            upstream_rule_reference="M27 composite published identifier",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.TELEMETRY_COUNT",
            category=ValidationCategory.STRUCTURE,
            passed=plain.get("telemetry_count") == len(telemetry) == 6,
            expected=6,
            observed={
                "declared": plain.get("telemetry_count"),
                "observed": len(telemetry),
            },
            message="M27 declares and publishes exactly six telemetry definitions.",
            json_path="$.telemetry_count",
            upstream_rule_reference="M27 TELEMETRY_DEFINITIONS",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.TELEMETRY_DEFINITIONS",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=telemetry == list(_M27_TELEMETRY) and unique_ids,
            expected=_M27_TELEMETRY,
            observed=telemetry,
            message="M27 telemetry identities, storage types, domains, relations, and classifications are exact.",
            json_path="$.telemetry",
            upstream_rule_reference="M27 build_telemetry_semantics",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.DOMAINS",
            category=ValidationCategory.ALLOWED_VALUE,
            passed=domain_valid,
            expected=True,
            observed=domain_valid,
            message="Every M27 telemetry domain is a declared ordered integer interval.",
            json_path="$.telemetry[*].domain",
            upstream_rule_reference="M27 telemetry domain declarations",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.RELATIONS",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("validated_relations")
            == list(_M27_VALIDATED_RELATIONS),
            expected=_M27_VALIDATED_RELATIONS,
            observed=plain.get("validated_relations"),
            message="M27 validated relation declarations remain exact and source ordered.",
            json_path="$.validated_relations",
            upstream_rule_reference="M27 validated_relations",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.INTERPRETATION",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("interpretation_boundary")
            == _M27_INTERPRETATION_BOUNDARY,
            expected=_M27_INTERPRETATION_BOUNDARY,
            observed=plain.get("interpretation_boundary"),
            message="M27 remains dimensionless model-derived telemetry with no physical measurement claim.",
            json_path="$.interpretation_boundary",
            upstream_rule_reference="M27 interpretation boundary",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M27.SEMANTICS_DIGEST",
            category=ValidationCategory.DIGEST,
            passed=observed_digest == expected_digest,
            expected=expected_digest,
            observed=observed_digest,
            message="M27 semantics digest matches compact canonical JSON without the digest field.",
            json_path="$.semantics_digest",
            upstream_rule_reference="M27 add_digest semantics_digest",
        ),
    )


def _m28_upstream_checks(
    dispatch: PublishedModeDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    baseline = plain.get("consumer_scaffold_baseline")
    if not isinstance(baseline, dict):
        baseline = {}
    expected_baseline = {
        "audited_commit": "a9d71657c56221d0d9b72fb6e954e0028f096a9e",
        "ci_workflow_path": ".github/workflows/observatory-ci.yml",
        "compatibility_registry_path": "schemas/registry.py",
        "implementation_action": "extend_existing_scaffold",
        "implemented_layers": list(_M28_IMPLEMENTED_LAYERS),
        "integration_contract_path": "docs/integration_contract.md",
        "repository": "FRP-Trace-Observatory",
        "verified_test_count": 275,
    }
    observed_digest = plain.get("contract_digest")
    expected_digest = _digest_without_field(plain, "contract_digest")
    return (
        _make_check(
            dispatch,
            check_code="M30A.M28U.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=_selected(plain, tuple(_M28_UPSTREAM_IDENTITY))
            == _M28_UPSTREAM_IDENTITY,
            expected=_M28_UPSTREAM_IDENTITY,
            observed=_selected(plain, tuple(_M28_UPSTREAM_IDENTITY)),
            message="M28 upstream interchange identity and release boundary are exact.",
            json_path="$",
            upstream_rule_reference="M28 trace Observatory upstream contract",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28U.CORE",
            category=ValidationCategory.TERNARY_DOMAIN,
            passed=plain.get("immutable_core") == _M28_UPSTREAM_CORE,
            expected=_M28_UPSTREAM_CORE,
            observed=plain.get("immutable_core"),
            message="M28 preserves -1/0/1, active neutral 0, opposite routes, and 1/7 plus 7/1.",
            json_path="$.immutable_core",
            upstream_rule_reference="M28 immutable core",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28U.DIRECTION",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("integration_direction")
            == _M28_INTEGRATION_DIRECTION,
            expected=_M28_INTEGRATION_DIRECTION,
            observed=plain.get("integration_direction"),
            message="M28 integration remains upstream-to-downstream only with mutation and writeback forbidden.",
            json_path="$.integration_direction",
            upstream_rule_reference="M28 integration direction",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28U.DATA_CONTRACT",
            category=ValidationCategory.CONTAINER,
            passed=plain.get("data_contract") == _M28_DATA_CONTRACT,
            expected=_M28_DATA_CONTRACT,
            observed=plain.get("data_contract"),
            message="M28 exact JSON, raw digest, source order, missing-field, and no-execution rules hold.",
            json_path="$.data_contract",
            upstream_rule_reference="M28 data contract",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28U.SCAFFOLD",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=baseline == expected_baseline,
            expected=expected_baseline,
            observed=baseline,
            message="M28 binds to the audited existing Observatory scaffold and all three modes.",
            json_path="$.consumer_scaffold_baseline",
            upstream_rule_reference="M28 consumer scaffold baseline",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28U.EXPORT_SCOPE",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("export_scope") == _M28_EXPORT_SCOPE,
            expected=_M28_EXPORT_SCOPE,
            observed=plain.get("export_scope"),
            message="M28 export scope keeps measurement contours separate and upstream free of UI changes.",
            json_path="$.export_scope",
            upstream_rule_reference="M28 export scope",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28U.CONTRACT_DIGEST",
            category=ValidationCategory.DIGEST,
            passed=observed_digest == expected_digest,
            expected=expected_digest,
            observed=observed_digest,
            message="M28 upstream contract digest matches compact canonical JSON without the digest field.",
            json_path="$.contract_digest",
            upstream_rule_reference="M28 add_digest contract_digest",
        ),
    )


def _m28_hierarchy_checks(
    dispatch: PublishedModeDispatch,
    root: Mapping[str, Any],
) -> tuple[ValidationCheck, ...]:
    plain = _plain(root)
    observed_digest = plain.get("contract_digest")
    expected_digest = _digest_without_field(
        plain,
        "contract_digest",
        hierarchy_style=True,
    )
    return (
        _make_check(
            dispatch,
            check_code="M30A.M28H.IDENTITY",
            category=ValidationCategory.IDENTITY,
            passed=_selected(plain, tuple(_M28_HIERARCHY_IDENTITY))
            == _M28_HIERARCHY_IDENTITY,
            expected=_M28_HIERARCHY_IDENTITY,
            observed=_selected(plain, tuple(_M28_HIERARCHY_IDENTITY)),
            message="M28 hierarchical scaling contract identity and release boundary are exact.",
            json_path="$",
            upstream_rule_reference="M28 hierarchical scaling contract",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.REQUIRED_SCOPE",
            category=ValidationCategory.STRUCTURE,
            passed=plain.get("required_scope") == list(_M28_HIERARCHY_SCOPE),
            expected=_M28_HIERARCHY_SCOPE,
            observed=plain.get("required_scope"),
            message="M28 hierarchy required scope remains complete and source ordered.",
            json_path="$.required_scope",
            upstream_rule_reference="M28 REQUIRED_SCOPE",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.CORE",
            category=ValidationCategory.TERNARY_DOMAIN,
            passed=plain.get("immutable_core") == _M28_HIERARCHY_CORE,
            expected=_M28_HIERARCHY_CORE,
            observed=plain.get("immutable_core"),
            message="M28 hierarchy preserves -1/0/1, active neutral 0, 1/7 and 7/1, and zero fault targets.",
            json_path="$.immutable_core",
            upstream_rule_reference="M28 hierarchy immutable core",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.HIERARCHY",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("hierarchy_boundary")
            == _M28_HIERARCHY_BOUNDARY,
            expected=_M28_HIERARCHY_BOUNDARY,
            observed=plain.get("hierarchy_boundary"),
            message="M28 hierarchy declares the exact dyadic O(N log N) execution boundary.",
            json_path="$.hierarchy_boundary",
            upstream_rule_reference="M28 hierarchy boundary",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.AGGREGATION",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("aggregation_equations")
            == _M28_AGGREGATION_EQUATIONS,
            expected=_M28_AGGREGATION_EQUATIONS,
            observed=plain.get("aggregation_equations"),
            message="M28 publishes only the declared cluster aggregation equations.",
            json_path="$.aggregation_equations",
            upstream_rule_reference="M28 aggregation equations",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.MEASUREMENT",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("measurement_boundary")
            == _M28_MEASUREMENT_BOUNDARY,
            expected=_M28_MEASUREMENT_BOUNDARY,
            observed=plain.get("measurement_boundary"),
            message="M28 hierarchy keeps model-derived, physical, long-run, and interchange contours separate.",
            json_path="$.measurement_boundary",
            upstream_rule_reference="M28 hierarchy measurement boundary",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.PROVENANCE",
            category=ValidationCategory.QUALIFICATION_EVIDENCE,
            passed=plain.get("provenance_boundary")
            == _M28_PROVENANCE_BOUNDARY,
            expected=_M28_PROVENANCE_BOUNDARY,
            observed=plain.get("provenance_boundary"),
            message="M28 primary hierarchy and additional Observatory publication roles remain distinct.",
            json_path="$.provenance_boundary",
            upstream_rule_reference="M28 hierarchy provenance boundary",
        ),
        _make_check(
            dispatch,
            check_code="M30A.M28H.CONTRACT_DIGEST",
            category=ValidationCategory.DIGEST,
            passed=observed_digest == expected_digest,
            expected=expected_digest,
            observed=observed_digest,
            message="M28 hierarchy digest matches its pretty canonical UTF-8 document algorithm.",
            json_path="$.contract_digest",
            upstream_rule_reference="M28 hierarchy attach_digest contract_digest",
        ),
    )


def _member_checks(
    dispatch: PublishedModeDispatch,
) -> tuple[ValidationCheck, ...]:
    root = dispatch.parsed_artifact.root
    try:
        if dispatch.member_id == _M16_MEMBER_ID:
            return _m16_checks(dispatch, root)
        if dispatch.member_id == _M27_MEMBER_ID:
            return _m27_checks(dispatch, root)
        if dispatch.member_id == _M28_UPSTREAM_MEMBER_ID:
            return _m28_upstream_checks(dispatch, root)
        if dispatch.member_id == _M28_HIERARCHY_MEMBER_ID:
            return _m28_hierarchy_checks(dispatch, root)
    except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
        return (
            _make_check(
                dispatch,
                check_code="M30A.MEMBER.STRUCTURAL_FAILURE",
                category=ValidationCategory.STRUCTURE,
                passed=False,
                expected="member-specific published contract is evaluable",
                observed=f"{type(exc).__name__}: {exc}",
                message=(
                    "Member-specific validation stopped at an invalid "
                    "published structure without executing source content."
                ),
                json_path="$",
                upstream_rule_reference="M30 published member contract",
            ),
        )
    raise M30PublishedAuditorError(
        f"unsupported published auditor member: {dispatch.member_id!r}"
    )


def _derived_status(checks: tuple[ValidationCheck, ...]) -> ValidationStatus:
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
            None if check.expected is None else _json_ready(check.expected.value)
        ),
        "mandatory": check.mandatory,
        "message": check.message,
        "observed": (
            None if check.observed is None else _json_ready(check.observed.value)
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
    dispatch: PublishedModeDispatch,
    contour: PublishedMeasurementContour,
    checks: tuple[ValidationCheck, ...],
    status: ValidationStatus,
) -> str:
    return _sha256(
        _compact_json_bytes(
            {
                "archive_sha256": dispatch.member.archive_sha256,
                "checks": [_check_payload(check) for check in checks],
                "compatibility_key": dispatch.member.registration.compatibility_key,
                "dispatch_sha256": dispatch.dispatch_sha256,
                "measurement_contour": contour.value,
                "member_id": dispatch.member_id,
                "overall_status": status.value,
                "raw_sha256": dispatch.member.registration.raw_sha256,
                "registry_revision": dispatch.member.registry_revision,
                "schema_identifier": dispatch.member.registration.schema_identifier,
            },
            ensure_ascii=True,
        )
    )


@dataclass(frozen=True, slots=True)
class PublishedAuditReport:
    """One deterministic read-only report retaining an exact M5 dispatch."""

    audit_report_id: str
    dispatch: PublishedModeDispatch
    measurement_contour: PublishedMeasurementContour
    checks: tuple[ValidationCheck, ...]
    overall_status: ValidationStatus
    report_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.dispatch, PublishedModeDispatch):
            raise M30PublishedAuditorError(
                "dispatch must be PublishedModeDispatch"
            )
        if self.dispatch.mode is not ObservatoryMode.ARTIFACT_AUDITOR:
            raise M30PublishedAuditorError(
                "published audit report requires an artifact_auditor route"
            )
        expected_contour = self.dispatch.member.registration.measurement_contour
        if self.measurement_contour is not expected_contour:
            raise M30PublishedAuditorError(
                "report contour differs from the M3 published registration"
            )
        if not isinstance(self.checks, tuple) or not self.checks:
            raise M30PublishedAuditorError("checks must be a nonempty tuple")
        if any(not isinstance(check, ValidationCheck) for check in self.checks):
            raise M30PublishedAuditorError(
                "checks must contain ValidationCheck values"
            )
        check_codes = tuple(check.check_code for check in self.checks)
        check_ids = tuple(check.check_id for check in self.checks)
        if len(set(check_codes)) != len(check_codes):
            raise M30PublishedAuditorError("check codes must be unique")
        if len(set(check_ids)) != len(check_ids):
            raise M30PublishedAuditorError("check identifiers must be unique")
        expected_ids = tuple(
            _check_id(self.dispatch, check.check_code)
            for check in self.checks
        )
        if check_ids != expected_ids:
            raise M30PublishedAuditorError(
                "check identifiers do not bind this exact M5 dispatch"
            )
        expected_status = _derived_status(self.checks)
        if self.overall_status is not expected_status:
            raise M30PublishedAuditorError(
                "overall status differs from mandatory check outcomes"
            )
        if not isinstance(self.report_sha256, str) or not _HEX64.fullmatch(
            self.report_sha256
        ):
            raise M30PublishedAuditorError(
                "report_sha256 must be lowercase hexadecimal SHA-256"
            )
        expected_digest = _report_sha256(
            self.dispatch,
            self.measurement_contour,
            self.checks,
            self.overall_status,
        )
        if self.report_sha256 != expected_digest:
            raise M30PublishedAuditorError(
                "report_sha256 does not bind the exact report evidence"
            )
        expected_id = str(uuid5(_REPORT_NAMESPACE, self.report_sha256))
        if self.audit_report_id != expected_id:
            raise M30PublishedAuditorError(
                "audit_report_id does not bind the deterministic report digest"
            )

    @property
    def member_id(self) -> str:
        """Return the exact M3 published member identifier."""

        return self.dispatch.member_id

    @property
    def passed_count(self) -> int:
        """Return the count of successful mandatory checks."""

        return sum(check.outcome is CheckOutcome.PASS for check in self.checks)

    @property
    def failed_count(self) -> int:
        """Return the count of failed mandatory checks."""

        return sum(check.outcome is CheckOutcome.FAIL for check in self.checks)


def _build_report(dispatch: PublishedModeDispatch) -> PublishedAuditReport:
    checks = _common_checks(dispatch) + _member_checks(dispatch)
    status = _derived_status(checks)
    contour = dispatch.member.registration.measurement_contour
    report_digest = _report_sha256(dispatch, contour, checks, status)
    return PublishedAuditReport(
        audit_report_id=str(uuid5(_REPORT_NAMESPACE, report_digest)),
        dispatch=dispatch,
        measurement_contour=contour,
        checks=checks,
        overall_status=status,
        report_sha256=report_digest,
    )


def audit_m30_published_dispatch(
    dispatch: PublishedModeDispatch,
) -> PublishedAuditReport:
    """Audit one exact M5 Artifact Auditor dispatch without legacy rebinding."""

    if not isinstance(dispatch, PublishedModeDispatch):
        raise M30PublishedAuditorError(
            "dispatch must be PublishedModeDispatch"
        )
    if dispatch.mode is not ObservatoryMode.ARTIFACT_AUDITOR:
        raise M30PublishedAuditorError(
            "only artifact_auditor M5 dispatches may be audited"
        )
    if not dispatch.source_artifact.verify_integrity():
        raise M30PublishedAuditorError(
            "dispatch source integrity verification failed"
        )
    return _build_report(dispatch)


def _batch_sha256(
    dispatch_batch: PublishedDispatchBatch,
    reports: tuple[PublishedAuditReport, ...],
    status: ValidationStatus,
) -> str:
    return _sha256(
        _compact_json_bytes(
            {
                "archive_sha256": dispatch_batch.archive_sha256,
                "overall_status": status.value,
                "registry_revision": dispatch_batch.registry_revision,
                "reports": [report.report_sha256 for report in reports],
            },
            ensure_ascii=True,
        )
    )


@dataclass(frozen=True, slots=True)
class PublishedAuditBatch:
    """Complete ordered four-report Artifact Auditor result for M30."""

    dispatch_batch: PublishedDispatchBatch
    reports: tuple[PublishedAuditReport, ...]
    overall_status: ValidationStatus
    batch_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.dispatch_batch, PublishedDispatchBatch):
            raise M30PublishedAuditorError(
                "dispatch_batch must be PublishedDispatchBatch"
            )
        if not isinstance(self.reports, tuple):
            raise M30PublishedAuditorError("reports must be a tuple")
        if any(
            not isinstance(report, PublishedAuditReport)
            for report in self.reports
        ):
            raise M30PublishedAuditorError(
                "reports must contain PublishedAuditReport values"
            )
        expected_dispatches = self.dispatch_batch.dispatches_for_mode(
            ObservatoryMode.ARTIFACT_AUDITOR
        )
        if len(self.reports) != len(expected_dispatches):
            raise M30PublishedAuditorError(
                "published audit report inventory length mismatch"
            )
        for report, dispatch in zip(
            self.reports,
            expected_dispatches,
            strict=True,
        ):
            if report.dispatch is not dispatch:
                raise M30PublishedAuditorError(
                    "report order or exact M5 dispatch identity mismatch"
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
            raise M30PublishedAuditorError(
                "batch status differs from report outcomes"
            )
        if not isinstance(self.batch_sha256, str) or not _HEX64.fullmatch(
            self.batch_sha256
        ):
            raise M30PublishedAuditorError(
                "batch_sha256 must be lowercase hexadecimal SHA-256"
            )
        expected_digest = _batch_sha256(
            self.dispatch_batch,
            self.reports,
            self.overall_status,
        )
        if self.batch_sha256 != expected_digest:
            raise M30PublishedAuditorError(
                "batch_sha256 does not bind the complete report inventory"
            )

    @property
    def total_check_count(self) -> int:
        """Return the total count of report checks."""

        return sum(len(report.checks) for report in self.reports)

    @property
    def failed_check_count(self) -> int:
        """Return the total count of failed checks."""

        return sum(report.failed_count for report in self.reports)

    def report_for_member(self, member_id: str) -> PublishedAuditReport:
        """Resolve one exact member report without aliases."""

        if not isinstance(member_id, str):
            raise M30PublishedAuditorError("member_id must be a string")
        matches = tuple(
            report for report in self.reports
            if report.member_id == member_id
        )
        if len(matches) != 1:
            raise M30PublishedAuditorError(
                f"unknown published audit member: {member_id!r}"
            )
        return matches[0]


def audit_m30_published_batch(
    dispatch_batch: PublishedDispatchBatch,
) -> PublishedAuditBatch:
    """Build all four exact reports from a complete M5 dispatch batch."""

    if not isinstance(dispatch_batch, PublishedDispatchBatch):
        raise M30PublishedAuditorError(
            "dispatch_batch must be PublishedDispatchBatch"
        )
    dispatches = dispatch_batch.dispatches_for_mode(
        ObservatoryMode.ARTIFACT_AUDITOR
    )
    reports = tuple(
        audit_m30_published_dispatch(dispatch)
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
    return PublishedAuditBatch(
        dispatch_batch=dispatch_batch,
        reports=reports,
        overall_status=status,
        batch_sha256=digest,
    )


def audit_m30_published_archive(
    archive_path: str | Path,
) -> PublishedAuditBatch:
    """Validate M1 through M5 and audit all four published M30 members."""

    return audit_m30_published_batch(
        dispatch_m30_published_members(archive_path)
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build four deterministic read-only Artifact Auditor reports "
            "from the exact M30 published dispatch boundary."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    arguments = parser.parse_args()
    result = audit_m30_published_archive(arguments.archive)
    print("FRP Observatory M30 published Artifact Auditor: "
          f"{'PASS' if result.failed_check_count == 0 else 'FAIL'}")
    print(f"archive_sha256={result.dispatch_batch.archive_sha256}")
    print(f"registry_revision={result.dispatch_batch.registry_revision}")
    print(f"audit_reports={len(result.reports)}")
    print(f"validation_checks={result.total_check_count}")
    print(f"failed_checks={result.failed_check_count}")
    print(f"batch_sha256={result.batch_sha256}")
    for report in result.reports:
        print(
            f"report={report.member_id} "
            f"contour={report.measurement_contour.value} "
            f"checks={len(report.checks)} "
            f"status={report.overall_status.value} "
            f"sha256={report.report_sha256}"
        )
    return 0 if result.failed_check_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
