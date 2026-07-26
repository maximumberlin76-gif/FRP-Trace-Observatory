"""Read-only trace construction and normalized Trace Explorer models."""

from .trace_builder import (
    TraceBuilderError,
    TraceDatasetBuilder,
    build_trace_dataset,
)
from .trace_model import (
    AggregationClassification,
    CellTraceRecord,
    OrderingValidationStatus,
    RequestBundle,
    TernaryStateSnapshot,
    TickRecord,
    TraceCompletenessStatus,
    TraceDataset,
    TraceFamily,
    TraceField,
    TraceFieldValue,
    TraceModelError,
    TraceScalar,
    TraceTelemetrySnapshot,
)


__all__ = [
    "AggregationClassification",
    "CellTraceRecord",
    "OrderingValidationStatus",
    "RequestBundle",
    "TernaryStateSnapshot",
    "TickRecord",
    "TraceBuilderError",
    "TraceCompletenessStatus",
    "TraceDataset",
    "TraceDatasetBuilder",
    "TraceFamily",
    "TraceField",
    "TraceFieldValue",
    "TraceModelError",
    "TraceScalar",
    "TraceTelemetrySnapshot",
    "build_trace_dataset",
]
