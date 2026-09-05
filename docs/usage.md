# FRP Trace Observatory Usage

- **Usage status:** Implemented and qualified through the FRP M31 published boundary
- **Runtime:** Python 3.12
- **Runtime dependencies:** Python standard library
- **Integration direction:** FRP published artifacts → FRP Trace Observatory
- **Current exact verification:** 655 tests, `OK`

Related contracts:

- [Integration Contract](integration_contract.md)
- [Supported Schema Registry](supported_schema_registry.md)
- [Normalized Read-Only Data Model](normalized_data_model.md)
- [M31 Published Evidence Boundary](m31_published_boundary.md)

## Purpose

This document defines the executable use of FRP Trace Observatory for:

- immutable source capture;
- exact schema and format dispatch;
- Artifact Auditor report construction;
- Trace Explorer dataset construction;
- Ternary Transition Visualizer dataset construction;
- exact M30 archive qualification;
- exact M31 publication qualification;
- complete repository verification.

FRP supplies the source artifacts and processor semantics. Observatory reads
the published bytes, verifies their registered identities and relations, and
constructs source-linked read-only representations.

## Requirements

Use Python 3.12 from the repository root.

```
python --version
```

Expected major and minor version:

```
Python 3.12
```

The repository uses the Python standard library. Package installation is not
required for the implemented command-line and test contours.

Compile the complete Python tree:

```
python -m compileall -q \
  artifact_auditor \
  parsers \
  schemas \
  trace_explorer \
  transition_visualizer \
  tests
```

## Input Authorities

| Scope | Input | Authority |
|---|---|---|
| Base compatibility | One captured JSON or M15 vector artifact | Exact 19-record registry in `schemas/registry.py` |
| M30 publication | Exact immutable M30 archive | Archive digest and member manifest |
| M31 publication | Clean FRP repository root | Four registered M31 documents and their provenance sources |

The exact M30 archive identity is:

- path within FRP: `artifacts/m30/packages/frp-v3.2.0-m30-archival-release.tar.gz`;
- byte length: 10,189,989;
- SHA-256:
  `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa`.

The exact M31 document paths are:

```
schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json
artifacts/m31/evidence/m31-phase-interference-active-zero-thermal-evidence.json
artifacts/m31/manifests/m31-phase-interference-active-zero-thermal-evidence-manifest.json
artifacts/m31/qualification/m31-phase-interference-active-zero-thermal-evidence-qualification.json
```

## Base Artifact Audit

Base compatibility artifacts are consumed through the Python API. The source
is captured first, dispatched against the exact registry, and audited without
changing the source bytes.

Example using the committed normalized-cost fixture:

```
from artifact_auditor import (
    audit_report_to_json_bytes,
    audit_report_to_text,
    audit_source_artifact,
)
from parsers.source_artifact import load_source_file

source = load_source_file(
    "fixtures/comparative_architecture/normalized_cost_profile_v1.json"
)
report = audit_source_artifact(
    source,
    registry_revision="v1.8.0-audit",
)

print(report.overall_status.value)
print(report.source_sha256)
print(audit_report_to_text(report))
print(audit_report_to_json_bytes(report).decode("utf-8"))
```

The committed fixture produces:

```
recognized_valid
bd2f5bfc4f0430c2764c5f1ddb1258d176b42f1667d1f0f691e40730ddc4c979
```

The report remains an Observatory-derived representation. Its provenance
retains the source artifact identity, exact source SHA-256, byte length,
registry binding, measurement contour, ordered checks, and source locations.

## Source Capture API

Capture caller-provided bytes:

```
from parsers.source_artifact import capture_source_bytes

source = capture_source_bytes(
    raw_bytes,
    source_filename="published-artifact.json",
    source_path="artifacts/published-artifact.json",
)

assert source.verify_integrity()
```

Capture a regular local file:

```
from parsers.source_artifact import load_source_file

source = load_source_file("path/to/published-artifact.json")
assert source.verify_integrity()
```

The captured record retains immutable bytes, detected container format,
filename, recorded path, byte length, UTC load time, raw SHA-256, and separate
load and digest identities.

## Exact Dispatch API

```
from parsers.artifact_dispatch import dispatch_artifact

dispatched = dispatch_artifact(source)

print(dispatched.classification.value)
print(dispatched.registration.status.value)
print(dispatched.registration.declared_identifier)
```

Dispatch uses only exact registered `schema` or `format_version` identities.
Shared schemas additionally require the exact registered `kind`.

Registration outcomes remain explicit:

- `registered`;
- `missing_identifier`;
- `invalid_identifier`;
- `unknown_identifier`;
- `unsupported_kind`;
- `not_applicable`.

## Base Trace Explorer API

A base trace dataset requires both the dispatched artifact and its matching
valid audit report:

```
from artifact_auditor import audit_dispatched_artifact
from parsers.artifact_dispatch import dispatch_artifact
from parsers.source_artifact import load_source_file
from trace_explorer import build_trace_dataset

trace_source = load_source_file("path/to/registered-trace.json")
trace_dispatched = dispatch_artifact(trace_source)
trace_report = audit_dispatched_artifact(
    trace_dispatched,
    registry_revision="v1.8.0-audit",
)
trace_dataset = build_trace_dataset(trace_dispatched, trace_report)

print(trace_dataset.trace_dataset_id)
print(trace_dataset.trace_family.value)
print(trace_dataset.ordering_validation.value)
print(trace_dataset.completeness_status.value)
```

Trace construction applies only to registered trace families. The resulting
dataset retains source order, normalized record identities, source locations,
registry binding, audit identity, and exact source digest.

## M30 Configuration

Bind the exact M30 archive to one environment variable:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
```

Verify that the configured path resolves to the intended regular file:

```
test -f "$FRP_M30_ARCHIVE_PATH"
```

M30 intake validates the archive as a complete immutable container. It does
not extract or execute source content.

## M30 Archive Intake

```
python -m artifact_auditor.m30_archive_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Qualified identity:

| Property | Exact value |
|---|---:|
| Archive entries | 519 |
| Manifested source members | 518 |
| Source execution | forbidden |
| Source mutation | forbidden |

## M30 Published Boundary Intake

```
python -m artifact_auditor.m30_published_boundary_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

This stage verifies the exact M28–M30 publication boundary, registered demo
members, accepted and rejected vector counts, the `-1/0/1` core notation, and
the `free`, `1/7`, and `7/1` scheduler modes.

## M30 Registry Qualification

```
python -m schemas.m30_published_registry \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Qualified routing inventory:

| Mode | Routes |
|---|---:|
| Artifact Auditor | 4 |
| Ternary Transition Visualizer | 2 |
| Trace Explorer | 1 |
| Total | 7 |

## M30 Published-Member Intake

```
python -m parsers.m30_published_member_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

This stage captures and strictly decodes the four exact registered members.
It retains raw member bytes, archive identity, registry identity, parsed JSON,
identifier evidence, compatibility binding, and mode routes.

## M30 Dispatch Boundary

```
python -m parsers.m30_published_dispatch \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

The command builds seven deterministic member-to-mode dispatch envelopes.
Consumer execution remains a separate downstream stage.

## M30 Artifact Auditor

```
python -m artifact_auditor.m30_published_auditor \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Audit reports | 4 |
| Ordered checks | 69 |
| Failed checks | 0 |
| Batch SHA-256 | `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03` |

## M30 Trace Explorer

```
python -m trace_explorer.m30_published_trace_explorer \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Trace records | 4 |
| Cell snapshots | 32 |
| Request records | 8 |
| Observed ternary domain | `-1/0/1` |
| Dataset SHA-256 | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |

## M30 Ternary Transition Visualizer

```
python -m transition_visualizer.m30_published_transition_visualizer \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Source trace contours | 2 |
| Trace records | 100 |
| Transition frames | 800 |
| `same_state_retention` | 783 |
| `polarity_to_neutral_transition` | 5 |
| `neutral_to_polarity_transition` | 12 |
| Visualizer dataset id | `68de3476-2e03-5506-93ea-062c3744e90d` |
| Dataset SHA-256 | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |

## M31 Configuration

Bind `FRP_M31_UPSTREAM_ROOT` to a clean FRP repository checkout containing
the complete exact M31 publication and its recorded provenance sources:

```
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
```

Verify that the configured root exists:

```
test -d "$FRP_M31_UPSTREAM_ROOT"
```

The M31 intake resolves registered relative paths beneath this root and
validates exact byte lengths and SHA-256 identities before dispatch.

## M31 Published Boundary Intake

```
python -m artifact_auditor.m31_published_boundary_intake \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Published documents | 4 |
| Provenance sources | 12 |
| Verified historical M30 provenance members | 10 |
| Balanced ternary notation | `-1/0/1` |
| Retained active-zero observations | 702 |

## M31 Registry Qualification

```
python -m schemas.m31_published_registry \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Qualified routing inventory:

| Mode | Routes |
|---|---:|
| Artifact Auditor | 4 |
| Ternary Transition Visualizer | 1 |
| Trace Explorer | 1 |
| Total | 6 |

## M31 Dispatch Boundary

```
python -m parsers.m31_published_dispatch \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

The command creates six deterministic document-to-mode dispatch envelopes
from the canonical boundary and registry objects.

## M31 Artifact Auditor

```
python -m artifact_auditor.m31_published_auditor \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Audit reports | 4 |
| Ordered checks | 47 |
| Failed checks | 0 |
| Batch SHA-256 | `3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591` |

## M31 Trace Explorer

```
python -m trace_explorer.m31_published_trace_explorer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Trace contours | 2 |
| Trace records | 100 |
| Cell snapshots | 800 |
| Request records | 200 |
| Invariant-pass records | 100 |
| Retained active-zero observations | 702 |
| Direct opposite transitions | 0 |
| Dataset SHA-256 | `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff` |

The two source contours remain distinct:

- RTL execution: 96 records and 768 cell snapshots;
- FPGA preparation execution: 4 records and 32 cell snapshots.

## M31 Ternary Transition Visualizer

```
python -m transition_visualizer.m31_published_transition_visualizer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Qualified result:

| Property | Exact value |
|---|---:|
| Transition frames | 800 |
| `retained_same` | 783 |
| `polarity_to_active_zero` | 5 |
| `active_zero_to_polarity` | 12 |
| `direct_opposite` | 0 |
| Thermal contours | 4 |
| Physical-temperature measurements | 0 |
| Visualizer dataset id | `63a1feb9-1835-579e-ab00-eec4569e8ff3` |
| Dataset SHA-256 | `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304` |

The visualizer retains the historical release benchmark, current comparative
baseline, hardware-sensitivity contour, and current thermal-profile contour as
four separate source-linked records.

## Complete Verification

Configure both exact upstream inputs:

```
export FRP_M30_ARCHIVE_PATH=/absolute/path/to/frp-v3.2.0-m30-archival-release.tar.gz
export FRP_M31_UPSTREAM_ROOT=/absolute/path/to/Fractal-Resonance-Processor
```

Run the complete suite:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

Without one of the exact upstream inputs, the test runner still discovers the
complete suite and marks the corresponding integration contour as skipped.
Base, controlled-fixture, model, and input-independent tests continue to run.

Run the complete M31 end-to-end contour directly:

```
python -m unittest \
  tests.test_m31_published_observatory_end_to_end \
  -v
```

The M31 end-to-end contour contains 26 tests.

## Focused Verification Commands

Base registry and dispatch:

```
python -m unittest \
  tests.test_schema_registry \
  tests.test_artifact_dispatch \
  -v
```

Source capture and parsers:

```
python -m unittest \
  tests.test_source_artifact \
  tests.test_json_artifact \
  tests.test_m15_vector \
  -v
```

Artifact Auditor:

```
python -m unittest \
  tests.test_auditor \
  tests.test_audit_report \
  tests.test_audit_report_serializer \
  -v
```

Base Trace Explorer and visualizer models:

```
python -m unittest \
  tests.test_trace_model \
  tests.test_trace_builder \
  tests.test_transition_models \
  tests.test_transition_view_model \
  tests.test_transition_view_builder \
  -v
```

M30 published contour:

```
python -m unittest \
  tests.test_m30_published_registry \
  tests.test_m30_published_member_intake \
  tests.test_m30_published_dispatch \
  tests.test_m30_published_auditor \
  tests.test_m30_published_trace_explorer \
  tests.test_m30_published_transition_visualizer \
  -v
```

M31 published contour:

```
python -m unittest \
  tests.test_m31_published_boundary_intake \
  tests.test_m31_published_registry \
  tests.test_m31_published_dispatch \
  tests.test_m31_published_auditor \
  tests.test_m31_published_trace_explorer \
  tests.test_m31_published_transition_visualizer \
  tests.test_m31_published_observatory_end_to_end \
  -v
```

## Mode Routing

| Scope | Artifact Auditor | Trace Explorer | Ternary Transition Visualizer |
|---|---:|---:|---:|
| Base compatibility registry | Per-record eligibility | Per-record eligibility | Per-record eligibility |
| M30 publication | 4 routes | 1 route | 2 routes |
| M31 publication | 4 routes | 1 route | 1 route |

Mode eligibility comes from the exact registry object. A source artifact does
not acquire additional modes through filename matching or schema aliases.

## Result Interpretation

Command-line publication stages emit `PASS` only after their complete exact
input boundary has been constructed successfully.

The base Artifact Auditor uses these aggregate statuses:

- `recognized_valid`;
- `recognized_valid_with_warnings`;
- `recognized_invalid`;
- `known_unsupported`;
- `unrecognized`;
- `incomplete_package`.

Parser failures, identity mismatches, digest mismatches, path mismatches,
cardinality changes, reordered records, substituted canonical objects, and
failed mandatory checks terminate the applicable exact qualification contour.

## Read-Only Operating Rules

1. Capture source bytes before parsing.
2. Verify raw SHA-256 against the applicable exact authority.
3. Resolve only exact registered identities.
4. Preserve source ordering and source coordinates.
5. Preserve `-1/0/1` as the canonical state notation.
6. Preserve state `0` as the active computational neutral state.
7. Preserve `-1 → 0 → 1` and `1 → 0 → -1` as separate two-leg routes.
8. Preserve scheduler mode and scheduler state as distinct fields.
9. Preserve historical and current thermal contours as distinct records.
10. Keep source, normalized, and Observatory-derived representations distinct.
11. Retain validation evidence and provenance through every downstream layer.
12. Keep all derived output outside the upstream FRP source boundary.

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
