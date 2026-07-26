"""Tests for immutable transition telemetry and event counters."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)
from transition_visualizer import (
    EventCounterName,
    EventCounterSnapshot,
    EventCounterValue,
    RecordOrigin,
    SourceRecordReference,
    TelemetryModelError,
    TransitionTelemetryField,
    TransitionTelemetryRecord,
    TransitionTelemetryValue,
)


_SCHEMA_IDENTIFIER = "frp.m15.cycle_exact_reference_trace.v1.7.0"
_SOURCE_SHA256 = "ab" * 32


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-telemetry-model-test:{label}"))


def _location(index: int, field_name: str) -> SourceLocation:
    return SourceLocation(
        json_path=f"$.trace[{index}].{field_name}",
        source_record_ordinal=index + 1,
    )


def _reference(
    index: int = 0,
    *,
    artifact_label: str = "source-artifact",
) -> SourceRecordReference:
    return SourceRecordReference(
        normalized_record_id=_record_id(f"source-{artifact_label}-{index}"),
        source_artifact_id=_record_id(artifact_label),
        trace_dataset_id=_record_id("trace-dataset"),
        registry_binding_id=_record_id("registry-binding"),
        validation_report_id=_record_id("validation-report"),
        source_sha256=_SOURCE_SHA256,
        source_ordinal=index,
        tick=index,
        validation_status=ValidationStatus.RECOGNIZED_VALID,
        source_locations=(_location(index, "tick"),),
        schema_identifier=_SCHEMA_IDENTIFIER,
    )


def _source_value(
    label: str,
    field: TransitionTelemetryField,
    value: bool | int | Decimal,
    *,
    reference: SourceRecordReference | None = None,
) -> TransitionTelemetryValue:
    source_reference = reference or _reference()
    return TransitionTelemetryValue(
        telemetry_value_id=_record_id(label),
        field=field,
        value=value,
        origin=RecordOrigin.UPSTREAM_SOURCE,
        source_references=(source_reference,),
        source_locations=(
            _location(
                source_reference.source_ordinal,
                field.value,
            ),
        ),
        source_field_name=field.value,
    )


def _counter_value(
    label: str,
    counter: EventCounterName,
    value: int,
    *,
    reference: SourceRecordReference | None = None,
) -> EventCounterValue:
    source_reference = reference or _reference()
    return EventCounterValue(
        counter_value_id=_record_id(label),
        counter=counter,
        value=value,
        source_reference=source_reference,
        source_location=_location(
            source_reference.source_ordinal,
            counter.value,
        ),
        origin=RecordOrigin.UPSTREAM_SOURCE,
        accumulation_classification="cumulative",
    )


class TransitionTelemetryValueTests(unittest.TestCase):
    """Exercise field-specific telemetry value contracts."""

    def test_source_values_preserve_types_and_provenance(self) -> None:
        reference = _reference()
        fraction = _source_value(
            "transition-fraction",
            TransitionTelemetryField.TRANSITION_FRACTION,
            Decimal("0.25"),
            reference=reference,
        )

        self.assertIsInstance(fraction.value, Decimal)
        self.assertEqual(
            fraction.source_field_name,
            "transition_fraction",
        )
        self.assertEqual(
            fraction.source_references,
            (reference,),
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(fraction, "value", Decimal("0.5"))

    def test_integer_fields_reject_bool_decimal_and_negative(self) -> None:
        value = _source_value(
            "transition-capacity",
            TransitionTelemetryField.TRANSITION_CAPACITY,
            2,
        )

        invalid_values = (
            (True, "transition_capacity must be an integer"),
            (
                Decimal("2"),
                "transition_capacity must be an integer",
            ),
            (-1, "transition_capacity must be nonnegative"),
        )
        for invalid, message in invalid_values:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    TelemetryModelError,
                    message,
                ):
                    replace(value, value=invalid)

    def test_numeric_fields_enforce_finite_nonnegative_bounds(
        self,
    ) -> None:
        fraction = _source_value(
            "bounded-fraction",
            TransitionTelemetryField.TRANSITION_FRACTION,
            Decimal("0.5"),
        )
        switch_load = _source_value(
            "switch-load",
            TransitionTelemetryField.SWITCH_LOAD,
            Decimal("0.25"),
        )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "transition_fraction must not exceed one",
        ):
            replace(fraction, value=Decimal("1.01"))

        with self.assertRaisesRegex(
            TelemetryModelError,
            "switch_load must be nonnegative",
        ):
            replace(switch_load, value=Decimal("-0.01"))

        with self.assertRaisesRegex(
            TelemetryModelError,
            "switch_load must be finite",
        ):
            replace(switch_load, value=Decimal("NaN"))

    def test_derived_value_requires_explicit_derivation(self) -> None:
        reference = _reference()
        derived = TransitionTelemetryValue(
            telemetry_value_id=_record_id("derived-remaining-capacity"),
            field=TransitionTelemetryField.REMAINING_CAPACITY,
            value=1,
            origin=RecordOrigin.OBSERVATORY_DERIVED,
            source_references=(reference,),
            source_locations=(_location(0, "transition_capacity"),),
            derivation_record_id=_record_id("capacity-derivation"),
            derivation_operation="subtract validated changes from capacity",
        )

        self.assertIs(
            derived.origin,
            RecordOrigin.OBSERVATORY_DERIVED,
        )
        self.assertIsNone(derived.source_field_name)

        with self.assertRaisesRegex(
            TelemetryModelError,
            "derived telemetry requires a derivation record",
        ):
            replace(
                derived,
                derivation_record_id=None,
            )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "derived telemetry cannot claim an upstream field name",
        ):
            replace(
                derived,
                source_field_name="remaining_capacity",
            )


class TransitionTelemetryRecordTests(unittest.TestCase):
    """Exercise tick records and transition-capacity relations."""

    def _capacity_record(
        self,
        *,
        changes: int = 1,
        capacity: int = 2,
        remaining: int = 1,
        exhausted: bool = False,
    ) -> TransitionTelemetryRecord:
        reference = _reference()
        return TransitionTelemetryRecord(
            telemetry_record_id=_record_id("capacity-record"),
            tick_reference=reference,
            values=(
                _source_value(
                    "record-changes",
                    TransitionTelemetryField.CURRENT_TICK_CHANGES,
                    changes,
                    reference=reference,
                ),
                _source_value(
                    "record-capacity",
                    TransitionTelemetryField.TRANSITION_CAPACITY,
                    capacity,
                    reference=reference,
                ),
                _source_value(
                    "record-remaining",
                    TransitionTelemetryField.REMAINING_CAPACITY,
                    remaining,
                    reference=reference,
                ),
                _source_value(
                    "record-exhausted",
                    TransitionTelemetryField.CAPACITY_EXHAUSTED,
                    exhausted,
                    reference=reference,
                ),
            ),
        )

    def test_record_preserves_zero_and_absence_separately(self) -> None:
        record = self._capacity_record(
            changes=2,
            capacity=2,
            remaining=0,
            exhausted=True,
        )

        remaining = record.value_for(
            TransitionTelemetryField.REMAINING_CAPACITY
        )
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining.value, 0)
        self.assertIsNone(
            record.value_for(
                TransitionTelemetryField.SCHEDULER_DEFERRAL
            )
        )

    def test_record_enforces_capacity_relations(self) -> None:
        invalid_records = (
            (
                {
                    "changes": 3,
                    "capacity": 2,
                    "remaining": 0,
                    "exhausted": True,
                },
                "current_tick_changes must not exceed capacity",
            ),
            (
                {
                    "changes": 0,
                    "capacity": 2,
                    "remaining": 3,
                    "exhausted": False,
                },
                "remaining_capacity must not exceed capacity",
            ),
            (
                {
                    "changes": 1,
                    "capacity": 3,
                    "remaining": 1,
                    "exhausted": False,
                },
                "remaining_capacity must equal capacity minus changes",
            ),
            (
                {
                    "changes": 1,
                    "capacity": 1,
                    "remaining": 0,
                    "exhausted": False,
                },
                "capacity_exhausted must match remaining capacity",
            ),
        )
        for arguments, message in invalid_records:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(
                    TelemetryModelError,
                    message,
                ):
                    self._capacity_record(**arguments)

    def test_record_rejects_duplicate_fields(self) -> None:
        reference = _reference()
        capacity = _source_value(
            "duplicate-capacity-one",
            TransitionTelemetryField.TRANSITION_CAPACITY,
            2,
            reference=reference,
        )
        duplicate = replace(
            capacity,
            telemetry_value_id=_record_id("duplicate-capacity-two"),
        )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "telemetry fields must be unique within one record",
        ):
            TransitionTelemetryRecord(
                telemetry_record_id=_record_id("duplicate-record"),
                tick_reference=reference,
                values=(capacity, duplicate),
            )

    def test_record_rejects_foreign_artifact_reference(self) -> None:
        tick_reference = _reference()
        foreign_reference = _reference(
            1,
            artifact_label="foreign-artifact",
        )
        foreign_value = _source_value(
            "foreign-value",
            TransitionTelemetryField.SWITCH_LOAD,
            Decimal("0.25"),
            reference=foreign_reference,
        )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "each telemetry field must reference the tick artifact",
        ):
            TransitionTelemetryRecord(
                telemetry_record_id=_record_id("foreign-record"),
                tick_reference=tick_reference,
                values=(foreign_value,),
            )


class EventCounterTests(unittest.TestCase):
    """Exercise published counter values and snapshots."""

    def test_snapshot_keeps_zero_distinct_from_absence(self) -> None:
        reference = _reference()
        snapshot = EventCounterSnapshot(
            counter_snapshot_id=_record_id("zero-counter-snapshot"),
            source_reference=reference,
            counters=(
                _counter_value(
                    "actual-direct-events",
                    EventCounterName.ACTUAL_DIRECT_EVENTS,
                    0,
                    reference=reference,
                ),
                _counter_value(
                    "queue-overflow-events",
                    EventCounterName.QUEUE_OVERFLOW_EVENTS,
                    0,
                    reference=reference,
                ),
            ),
        )

        actual = snapshot.value_for(
            EventCounterName.ACTUAL_DIRECT_EVENTS
        )
        self.assertIsNotNone(actual)
        self.assertEqual(actual.value, 0)
        self.assertIsNone(
            snapshot.value_for(
                EventCounterName.RESERVED_STATE_EVENTS
            )
        )

    def test_counter_requires_nonnegative_published_value(self) -> None:
        counter = _counter_value(
            "published-counter",
            EventCounterName.NEUTRAL_ROUTED_EVENTS,
            1,
        )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "value must be nonnegative",
        ):
            replace(counter, value=-1)

        with self.assertRaisesRegex(
            TelemetryModelError,
            "value must be an integer",
        ):
            replace(counter, value=True)

        with self.assertRaisesRegex(
            TelemetryModelError,
            "published counters cannot have derived origin",
        ):
            replace(
                counter,
                origin=RecordOrigin.OBSERVATORY_DERIVED,
            )

    def test_snapshot_requires_unique_counter_names(self) -> None:
        reference = _reference()
        first = _counter_value(
            "first-requested-counter",
            EventCounterName.REQUESTED_DIRECT_EVENTS,
            2,
            reference=reference,
        )
        duplicate = replace(
            first,
            counter_value_id=_record_id("second-requested-counter"),
        )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "counter names must be unique within one snapshot",
        ):
            EventCounterSnapshot(
                counter_snapshot_id=_record_id(
                    "duplicate-counter-snapshot"
                ),
                source_reference=reference,
                counters=(first, duplicate),
            )

    def test_snapshot_requires_exact_source_record(self) -> None:
        snapshot_reference = _reference()
        other_reference = _reference(1)
        other_counter = _counter_value(
            "other-record-counter",
            EventCounterName.PREVENTED_DIRECT_EVENTS,
            1,
            reference=other_reference,
        )

        with self.assertRaisesRegex(
            TelemetryModelError,
            "counter values must reference the snapshot source record",
        ):
            EventCounterSnapshot(
                counter_snapshot_id=_record_id(
                    "mismatched-counter-snapshot"
                ),
                source_reference=snapshot_reference,
                counters=(other_counter,),
            )


if __name__ == "__main__":
    unittest.main()
