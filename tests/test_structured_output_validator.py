"""Tests for read-only structured-output artifact validation."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace

from artifact_auditor.audit_report import CheckOutcome
from artifact_auditor.structured_output_validator import (
    StructuredOutputValidation,
    StructuredOutputValidationError,
    validate_structured_output,
)
from parsers.artifact_dispatch import dispatch_artifact
from parsers.source_artifact import capture_source_bytes


_SCHEMA = "frp.structured_output.v1.7.0"
_VERSION = "1.7.0"
_MILESTONE = (
    "M15 — Implementation Mapping, Domain Interface, and Qualification "
    "Closure Package"
)
_DIGEST = "0" * 64
_SELF_TEST_SECTIONS = tuple(
    "neutral_route_validation scheduler_validation "
    "request_lane_order_validation queue_exhaustion_validation "
    "fixed_point_validation encoding_validation topology_validation "
    "trigonometric_lut_validation semantic_correlation "
    "exact_shadow_replay vector_determinism scaling_validation".split()
)


def _configuration() -> dict[str, object]:
    values: dict[str, object] = dict.fromkeys(
        "transition_fraction gamma_nominal fractal_alpha thermal_beta "
        "ambient_heat thermal_time_constant thermal_soft_limit "
        "thermal_hard_limit coupling_nominal delay_alpha "
        "thermal_diffusion_gain".split(),
        0.5,
    )
    values.update(
        cells=2, steps=2, seed=76, scheduler="free", request_lanes=1
    )
    return values


def _kernel() -> dict[str, object]:
    return {
        "balanced_ternary_states": [-1, 0, 1],
        "active_neutral_state": 0,
        "neutral_routes": ["-1 -> 0 -> 1", "1 -> 0 -> -1"],
        "scheduler_modes": ["free", "7/1", "1/7"],
        "actual_direct_events_target": 0,
    }


def _hardware_profile() -> dict[str, object]:
    return {
        "scalar": "S32Q16",
        "unit": "S32Q30",
        "phase": "PHASE_U32",
        "gamma": "GAMMA_S32",
        "state_encoding": {
            "-1": "11",
            "0": "00",
            "1": "01",
            "reserved": "10",
        },
    }


def _summary() -> dict[str, object]:
    values: dict[str, object] = dict.fromkeys(
        "hierarchy_depth reserved_state_events actual_direct_events "
        "requested_direct_events prevented_direct_events "
        "neutral_routed_events neutralized_conflicts "
        "pending_route_count_final neutral_route_queue_capacity "
        "queue_overflow_events switch_load_peak_q16 C_minus_P_final_q16 "
        "C_minus_P_min_q16".split(),
        0,
    )
    values.update(
        version=_VERSION,
        milestone=_MILESTONE,
        cells=2,
        request_lanes=1,
        steps=2,
        ticks_recorded=2,
        scheduler="free",
        scheduler_counts={"free": 2},
        scheduler_counts_valid=True,
        transition_fraction=0.5,
        balanced_ternary_state_domain=True,
        switch_load_peak=0.0,
        C_minus_P_final=0.0,
        C_minus_P_min=0.0,
        boundary_detected=False,
        fixed_point_topology_sum_exact=True,
        fixed_point_thermal_sum_exact=True,
    )
    return values


def _demo() -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "kind": "demo",
        "version": _VERSION,
        "milestone": _MILESTONE,
        "configuration": _configuration(),
        "kernel": _kernel(),
        "hardware_profile": _hardware_profile(),
        "summary": _summary(),
        "preload_digest": _DIGEST,
        "trace_digest": _DIGEST,
        "cell_trace_digest": _DIGEST,
    }


def _trace_row(tick: int) -> dict[str, object]:
    row: dict[str, object] = dict.fromkeys(
        "scheduler_mode scheduler_state request_valid_mask "
        "gamma_noise_update_valid states_packed pending_route_count "
        "switch_load_q16 heat_global_q16 global_phase_coherence_q30 "
        "C_q16 P_q16 C_minus_P_q16 requested_direct_events "
        "prevented_direct_events neutral_routed_events "
        "neutralized_conflicts actual_direct_events "
        "reserved_state_events queue_overflow_events changes".split(),
        0,
    )
    row.update(
        tick=tick,
        reset_n=1,
        scheduler_state_name="free",
        auto_targets_enable=1,
        request_cell_ids=[0],
        request_target_states=[0],
        gamma_noise_target_q16=[0],
        states_packed_hex="0x0",
        states_human="NN",
    )
    return row


def _cell_row(tick: int, cell_id: int) -> dict[str, int]:
    row = dict.fromkeys(
        "state_code phase_word frequency_target_q16 "
        "frequency_current_q16 frequency_lag_q16 generated_power_q16 "
        "heat_q16 thermal_overload_q16 gamma_noise_state_q16 "
        "gamma_effective_word thermal_node_factor_q30 "
        "coupling_field_q16".split(),
        0,
    )
    row.update(tick=tick, cell_id=cell_id)
    return row


def _canonical_digest(value: object) -> str:
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _refresh_trace_digests(root: dict[str, object]) -> None:
    root["trace_digest"] = _canonical_digest(root["trace"])
    root["cell_trace_digest"] = _canonical_digest(root["cell_trace"])


def _full_demo() -> dict[str, object]:
    root = _demo()
    root["trace"] = [_trace_row(0), _trace_row(1)]
    root["cell_trace"] = [
        _cell_row(tick, cell_id)
        for tick in range(2)
        for cell_id in range(2)
    ]
    root["route_events"] = [
        dict(
            tick=0, cell_id=0, target_state=1,
            ready_tick=1, route_status="pending",
        ),
        dict(
            tick=1, cell_id=0, target_state=1,
            ready_tick=1, route_status="applied",
        ),
    ]
    _refresh_trace_digests(root)
    return root


def _self_test() -> dict[str, object]:
    checks = {
        f"qualification_check_{index:02d}": True
        for index in range(1, 42)
    }
    root: dict[str, object] = {
        "schema": _SCHEMA,
        "kind": "self_test",
        "version": _VERSION,
        "milestone": _MILESTONE,
        "status": "PASS",
        "check_count": 41,
        "checks": checks,
    }
    root.update({section: {} for section in _SELF_TEST_SECTIONS})
    return root


def _dispatch(root: dict[str, object]):
    text = json.dumps(
        root, ensure_ascii=False, separators=(",", ":")
    )
    raw_bytes = (text + "\n").encode("utf-8")
    source = capture_source_bytes(
        raw_bytes,
        source_filename="structured_output.json",
        source_path="published/structured_output.json",
    )
    return dispatch_artifact(source)


def _failed_codes(
    validation: StructuredOutputValidation,
) -> tuple[str, ...]:
    return tuple(
        spec.check_code
        for spec in validation.check_specs
        if spec.outcome is CheckOutcome.FAIL
    )


class CompactDemoValidationTests(unittest.TestCase):
    """Exercise registered demo output without optional trace rows."""

    def test_compact_demo_produces_ordered_valid_result(self) -> None:
        dispatched = _dispatch(_demo())
        original_bytes = dispatched.source_artifact.raw_bytes

        validation = validate_structured_output(dispatched)

        self.assertEqual(validation.kind, "demo")
        self.assertFalse(validation.full_trace_present)
        self.assertTrue(validation.valid)
        expected = tuple(
            (
                "structured_output_envelope structured_demo_required_fields "
                "structured_demo_configuration_fields "
                "structured_demo_kernel_fields "
                "structured_demo_hardware_fields "
                "structured_demo_summary_fields "
                "structured_demo_configuration_types "
                "structured_demo_summary_types "
                "structured_demo_kernel_values "
                "structured_demo_hardware_values "
                "structured_demo_configuration_values "
                "structured_demo_summary_invariants "
                "structured_demo_digest_syntax "
                "structured_demo_full_trace_collection "
                "structured_demo_trace_digest "
                "structured_demo_cell_trace_digest"
            ).split()
        )
        self.assertEqual(
            tuple(spec.check_code for spec in validation.check_specs),
            expected,
        )
        self.assertEqual(
            tuple(spec.outcome for spec in validation.check_specs[-2:]),
            (CheckOutcome.NOT_APPLICABLE,) * 2,
        )
        self.assertTrue(
            all(not spec.mandatory for spec in validation.check_specs[-2:])
        )
        self.assertEqual(
            dispatched.source_artifact.raw_bytes,
            original_bytes,
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(validation, "kind", "self_test")

    def test_demo_contract_failures_remain_distinct(self) -> None:
        prefix = "structured_demo_"
        cases = (
            (("version",), "1.7.1", ("structured_output_envelope",)),
            (
                ("configuration", "cells"), True,
                (prefix + "configuration_types",
                 prefix + "configuration_values"),
            ),
            (
                ("kernel", "balanced_ternary_states"), [-1, 0, 2],
                (prefix + "kernel_values",),
            ),
            (
                ("hardware_profile", "state_encoding", "1"), "10",
                (prefix + "hardware_values",),
            ),
            (
                ("summary", "scheduler_counts_valid"), 1,
                (prefix + "summary_types",
                 prefix + "summary_invariants"),
            ),
            (
                ("trace_digest",), "A" * 64,
                (prefix + "digest_syntax",),
            ),
        )

        for path, value, expected in cases:
            with self.subTest(path=path):
                root = _demo()
                target = root
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value

                validation = validate_structured_output(_dispatch(root))

                self.assertEqual(_failed_codes(validation), expected)

    def test_partial_trace_collection_is_not_treated_as_full(self) -> None:
        root = _demo()
        root["trace"] = []

        validation = validate_structured_output(_dispatch(root))

        self.assertFalse(validation.valid)
        self.assertFalse(validation.full_trace_present)
        self.assertEqual(
            _failed_codes(validation),
            ("structured_demo_full_trace_collection",),
        )
        self.assertEqual(
            tuple(spec.outcome for spec in validation.check_specs[-2:]),
            (CheckOutcome.NOT_APPLICABLE,) * 2,
        )


class FullTraceDemoValidationTests(unittest.TestCase):
    """Exercise trace, cell, route, counter, and digest relations."""

    def test_full_demo_produces_twenty_six_passing_checks(self) -> None:
        validation = validate_structured_output(_dispatch(_full_demo()))

        self.assertTrue(validation.valid)
        self.assertTrue(validation.full_trace_present)
        self.assertEqual(len(validation.check_specs), 26)
        self.assertTrue(
            all(
                spec.outcome is CheckOutcome.PASS
                for spec in validation.check_specs
            )
        )

    def test_full_trace_relations_fail_independently(self) -> None:
        prefix = "structured_demo_"
        cases = (
            ("trace", 0, "tick", 1, prefix + "trace_tick_order"),
            ("cell_trace", 0, "cell_id", 1,
             prefix + "cell_trace_order"),
            ("trace", 0, "scheduler_state", 1,
             prefix + "scheduler_encoding"),
            ("cell_trace", 0, "state_code", 2,
             prefix + "trace_ternary_domain"),
            ("trace", 0, "changes", 2,
             prefix + "transition_capacity"),
            ("route_events", 1, "ready_tick", 2,
             prefix + "pending_route_relations"),
            ("summary", None, "ticks_recorded", 1,
             prefix + "summary_trace_relations"),
        )

        for section, index, field, value, expected in cases:
            with self.subTest(expected=expected):
                root = _full_demo()
                target = root[section]
                if index is not None:
                    target = target[index]
                target[field] = value
                _refresh_trace_digests(root)

                validation = validate_structured_output(_dispatch(root))

                self.assertEqual(_failed_codes(validation), (expected,))

    def test_full_trace_digest_mismatches_are_separate(self) -> None:
        cases = (
            ("trace_digest", "structured_demo_trace_digest"),
            ("cell_trace_digest",
             "structured_demo_cell_trace_digest"),
        )

        for field, expected in cases:
            with self.subTest(field=field):
                root = _full_demo()
                root[field] = "1" * 64

                validation = validate_structured_output(_dispatch(root))

                self.assertEqual(_failed_codes(validation), (expected,))


class SelfTestValidationTests(unittest.TestCase):
    """Exercise the registered qualification summary variant."""

    def test_complete_self_test_produces_five_passes(self) -> None:
        validation = validate_structured_output(_dispatch(_self_test()))

        self.assertEqual(validation.kind, "self_test")
        self.assertTrue(validation.valid)
        expected = tuple(
            (
                "structured_output_envelope "
                "structured_self_test_required_fields "
                "structured_self_test_field_types "
                "structured_self_test_check_registry "
                "structured_self_test_qualification_result"
            ).split()
        )
        self.assertEqual(
            tuple(spec.check_code for spec in validation.check_specs),
            expected,
        )
        self.assertTrue(
            all(
                spec.outcome is CheckOutcome.PASS
                for spec in validation.check_specs
            )
        )

    def test_self_test_contract_failures_remain_separate(self) -> None:
        root = _self_test()
        root.pop("scaling_validation")
        root["check_count"] = "41"
        root["checks"]["qualification_check_41"] = False
        root["status"] = "REVIEW"

        validation = validate_structured_output(_dispatch(root))

        self.assertEqual(
            _failed_codes(validation),
            ("structured_self_test_required_fields",
             "structured_self_test_field_types",
             "structured_self_test_check_registry",
             "structured_self_test_qualification_result"),
        )


class StructuredOutputRoutingAndModelTests(unittest.TestCase):
    """Exercise strict dispatch and immutable result invariants."""

    def test_validator_rejects_unregistered_or_wrong_inputs(self) -> None:
        unknown = _demo()
        unknown["schema"] = "frp.unknown.v1"
        unsupported = _demo()
        unsupported["kind"] = "trace"
        cases = (
            ("artifact", "dispatched must be a DispatchedArtifact"),
            (_dispatch(unknown),
             "artifact is not registered structured output"),
            (_dispatch(unsupported),
             "artifact is not registered structured output"),
        )

        for dispatched, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    StructuredOutputValidationError,
                    message,
                ):
                    validate_structured_output(dispatched)

    def test_result_model_rejects_invalid_direct_replacements(self) -> None:
        validation = validate_structured_output(_dispatch(_demo()))
        cases = (
            ({"kind": "self_test"}, "kind must match"),
            ({"check_specs": ()}, "check_specs must contain"),
            ({"check_specs": ("check",)}, "check_specs must contain"),
            ({"full_trace_present": 1},
             "full_trace_present must be a boolean"),
        )

        for changes, message in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(
                    StructuredOutputValidationError,
                    message,
                ):
                    replace(validation, **changes)


if __name__ == "__main__":
    unittest.main()
