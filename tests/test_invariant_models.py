"""Tests for immutable source-linked invariant-vector records."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from uuid import NAMESPACE_URL, uuid5

from artifact_auditor.audit_report import (
    SourceLocation,
    ValidationStatus,
)
from schemas.registry import MeasurementContour
from transition_visualizer import (
    InvariantBitRecord,
    InvariantModelError,
    InvariantVectorRecord,
    RecordOrigin,
    SourceRecordReference,
)


_SCHEMA_IDENTIFIER = "frp.m15.cycle_exact_reference_trace.v1.7.0"
_SOURCE_SHA256 = "cd" * 32
_BIT_ORDER_CONTRACT = "frp.m15.invariant_flag_order.v1.7.0"


def _record_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"frp-invariant-model-test:{label}"))


def _location(index: int, field_name: str) -> SourceLocation:
    return SourceLocation(
        json_path=f"$.trace[{index}].{field_name}",
        source_record_ordinal=index + 1,
    )


def _reference(index: int = 0) -> SourceRecordReference:
    return SourceRecordReference(
        normalized_record_id=_record_id(f"source-{index}"),
        source_artifact_id=_record_id("source-artifact"),
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


def _bit(
    label: str,
    position: int,
    value: bool | int | str,
    *,
    reference: SourceRecordReference | None = None,
    name: str | None = None,
    status: str | None = None,
) -> InvariantBitRecord:
    source_reference = reference or _reference()
    return InvariantBitRecord(
        invariant_bit_record_id=_record_id(label),
        source_reference=source_reference,
        source_bit_position=position,
        source_bit_value=value,
        source_location=_location(
            source_reference.source_ordinal,
            f"invariant_vector[{position}]",
        ),
        origin=RecordOrigin.UPSTREAM_SOURCE,
        registered_invariant_name=name,
        published_status=status,
        published_status_location=(
            _location(
                source_reference.source_ordinal,
                f"invariant_status[{position}]",
            )
            if status is not None
            else None
        ),
    )


def _vector(
    label: str,
    bits: tuple[InvariantBitRecord, ...],
    representation: str,
    *,
    reference: SourceRecordReference | None = None,
    bit_count: int | None = None,
    order_contract: str | None = None,
    aggregate_status: str | None = None,
) -> InvariantVectorRecord:
    source_reference = reference or bits[0].source_reference
    return InvariantVectorRecord(
        invariant_vector_record_id=_record_id(label),
        source_reference=source_reference,
        original_vector_representation=representation,
        bit_count=len(bits) if bit_count is None else bit_count,
        source_location=_location(
            source_reference.source_ordinal,
            "invariant_vector",
        ),
        bits=bits,
        qualification_contour=(
            MeasurementContour.M15_IMPLEMENTATION_MAPPING
        ),
        origin=RecordOrigin.UPSTREAM_SOURCE,
        bit_order_contract_identifier=order_contract,
        published_aggregate_status=aggregate_status,
        aggregate_status_location=(
            _location(
                source_reference.source_ordinal,
                "invariant_status",
            )
            if aggregate_status is not None
            else None
        ),
    )


class InvariantBitTests(unittest.TestCase):
    """Exercise source bit values and published bit metadata."""

    def test_display_value_preserves_supported_source_forms(self) -> None:
        reference = _reference()
        bits = (
            _bit("bool-bit", 0, True, reference=reference),
            _bit("integer-bit", 1, 0, reference=reference),
            _bit("string-bit", 2, "1", reference=reference),
        )

        self.assertEqual(
            tuple(bit.display_value for bit in bits),
            ("1", "0", "1"),
        )
        self.assertIs(bits[0].source_bit_value, True)
        self.assertEqual(bits[1].source_bit_value, 0)
        self.assertEqual(bits[2].source_bit_value, "1")

    def test_bit_rejects_nonbinary_values(self) -> None:
        bit = _bit("valid-bit", 0, 1)
        invalid_values = (
            (2, "integer source_bit_value must be 0 or 1"),
            ("PASS", "string source_bit_value must be '0' or '1'"),
            (
                None,
                "source_bit_value must be a bool, integer, or string bit",
            ),
        )

        for value, message in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvariantModelError,
                    message,
                ):
                    replace(bit, source_bit_value=value)

    def test_bit_position_requires_nonnegative_integer(self) -> None:
        bit = _bit("position-bit", 0, 1)

        with self.assertRaisesRegex(
            InvariantModelError,
            "source_bit_position must be nonnegative",
        ):
            replace(bit, source_bit_position=-1)

        with self.assertRaisesRegex(
            InvariantModelError,
            "source_bit_position must be an integer",
        ):
            replace(bit, source_bit_position=True)

    def test_bit_status_and_location_are_coupled(self) -> None:
        bit = _bit("status-bit", 0, 1)
        status_location = _location(0, "invariant_status[0]")

        with self.assertRaisesRegex(
            InvariantModelError,
            "status location requires a published status",
        ):
            replace(
                bit,
                published_status_location=status_location,
            )

        with self.assertRaisesRegex(
            InvariantModelError,
            "published status requires a source location",
        ):
            replace(
                bit,
                published_status="PASS",
                published_status_location=None,
            )

    def test_bit_rejects_derived_origin_and_is_frozen(self) -> None:
        bit = _bit("origin-bit", 0, 1)

        with self.assertRaisesRegex(
            InvariantModelError,
            "invariant source records cannot have derived origin",
        ):
            replace(
                bit,
                origin=RecordOrigin.OBSERVATORY_DERIVED,
            )

        with self.assertRaises(FrozenInstanceError):
            setattr(bit, "source_bit_value", 0)


class InvariantVectorTests(unittest.TestCase):
    """Exercise vector order, identity, contour, and availability."""

    def test_vector_preserves_order_contour_and_lookups(self) -> None:
        reference = _reference()
        bits = (
            _bit(
                "actual-direct-bit",
                0,
                1,
                reference=reference,
                name="actual_direct_events_zero",
            ),
            _bit(
                "reserved-state-bit",
                1,
                0,
                reference=reference,
                name="reserved_state_events_zero",
            ),
            _bit(
                "queue-overflow-bit",
                2,
                "1",
                reference=reference,
                name="queue_overflow_events_zero",
            ),
        )
        vector = _vector(
            "named-vector",
            bits,
            "101",
            order_contract=_BIT_ORDER_CONTRACT,
            aggregate_status="PASS",
        )

        self.assertEqual(vector.bits, bits)
        self.assertIs(
            vector.qualification_contour,
            MeasurementContour.M15_IMPLEMENTATION_MAPPING,
        )
        self.assertIs(vector.bit_for_position(1), bits[1])
        self.assertIs(
            vector.bit_for_name("queue_overflow_events_zero"),
            bits[2],
        )
        self.assertIsNone(vector.bit_for_position(7))
        self.assertIsNone(vector.bit_for_name("unregistered_flag"))

    def test_vector_requires_positive_matching_bit_count(self) -> None:
        bits = (_bit("count-bit", 0, 1),)

        with self.assertRaisesRegex(
            InvariantModelError,
            "bit_count must be positive",
        ):
            _vector(
                "zero-count-vector",
                bits,
                "1",
                bit_count=0,
            )

        with self.assertRaisesRegex(
            InvariantModelError,
            "bit_count must equal the number of bit records",
        ):
            _vector(
                "mismatched-count-vector",
                bits,
                "1",
                bit_count=2,
            )

    def test_vector_requires_unique_positions(self) -> None:
        reference = _reference()
        bits = (
            _bit("position-one", 0, 1, reference=reference),
            _bit("position-two", 0, 1, reference=reference),
        )

        with self.assertRaisesRegex(
            InvariantModelError,
            "source bit positions must be unique",
        ):
            _vector(
                "duplicate-position-vector",
                bits,
                "11",
            )

    def test_vector_requires_one_source_record(self) -> None:
        first_reference = _reference()
        second_reference = _reference(1)
        bits = (
            _bit(
                "first-record-bit",
                0,
                1,
                reference=first_reference,
            ),
            _bit(
                "second-record-bit",
                1,
                0,
                reference=second_reference,
            ),
        )

        with self.assertRaisesRegex(
            InvariantModelError,
            "bits must reference the vector source record",
        ):
            _vector(
                "mixed-source-vector",
                bits,
                "10",
                reference=first_reference,
            )

    def test_simple_binary_representation_must_match_order(self) -> None:
        reference = _reference()
        bits = (
            _bit("order-zero", 0, 1, reference=reference),
            _bit("order-one", 1, 0, reference=reference),
        )

        with self.assertRaisesRegex(
            InvariantModelError,
            "bit records must preserve simple binary source order",
        ):
            _vector(
                "reversed-representation-vector",
                bits,
                "01",
            )

        preserved = _vector(
            "non-simple-representation-vector",
            bits,
            "0b10",
        )
        self.assertEqual(
            preserved.original_vector_representation,
            "0b10",
        )

    def test_registered_names_require_unique_order_contract(self) -> None:
        reference = _reference()
        named = _bit(
            "named-bit",
            0,
            1,
            reference=reference,
            name="actual_direct_events_zero",
        )

        with self.assertRaisesRegex(
            InvariantModelError,
            "registered bit names require a bit-order contract",
        ):
            _vector(
                "missing-contract-vector",
                (named,),
                "1",
            )

        duplicate_names = (
            named,
            _bit(
                "duplicate-name-bit",
                1,
                1,
                reference=reference,
                name="actual_direct_events_zero",
            ),
        )
        with self.assertRaisesRegex(
            InvariantModelError,
            "registered invariant names must be unique",
        ):
            _vector(
                "duplicate-name-vector",
                duplicate_names,
                "11",
                order_contract=_BIT_ORDER_CONTRACT,
            )

    def test_aggregate_status_and_location_are_coupled(self) -> None:
        vector = _vector(
            "aggregate-vector",
            (_bit("aggregate-bit", 0, 1),),
            "1",
        )
        status_location = _location(0, "invariant_status")

        with self.assertRaisesRegex(
            InvariantModelError,
            "aggregate location requires a published status",
        ):
            replace(
                vector,
                aggregate_status_location=status_location,
            )

        with self.assertRaisesRegex(
            InvariantModelError,
            "published aggregate status requires a source location",
        ):
            replace(
                vector,
                published_aggregate_status="PASS",
                aggregate_status_location=None,
            )

    def test_vector_rejects_wrong_contour_and_derived_origin(self) -> None:
        vector = _vector(
            "contract-vector",
            (_bit("contract-bit", 0, 1),),
            "1",
        )

        with self.assertRaisesRegex(
            InvariantModelError,
            "qualification_contour must be a MeasurementContour",
        ):
            replace(
                vector,
                qualification_contour="m15_implementation_mapping",
            )

        with self.assertRaisesRegex(
            InvariantModelError,
            "invariant source records cannot have derived origin",
        ):
            replace(
                vector,
                origin=RecordOrigin.OBSERVATORY_DERIVED,
            )


if __name__ == "__main__":
    unittest.main()
