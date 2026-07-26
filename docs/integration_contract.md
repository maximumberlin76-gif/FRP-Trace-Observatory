# FRP Trace Observatory Integration Contract

- **Status:** Implemented downstream integration contract
- **Upstream audit baseline:** FRP v1.8.0 / M16
- **Observatory version:** Not assigned
- **Current local verification:** 275 tests, `OK`

## Purpose

This document defines the integration boundary between the Fractal Resonance
Processor repository and FRP Trace Observatory. It governs identification,
read-only loading, validation, provenance, normalization, audit reporting,
trace construction, derived views, and mode eligibility. It does not define,
extend, execute, or replace FRP processor semantics.

## Implementation State

The repository implements:

- immutable source capture and integrity verification in `parsers/`;
- exact compatibility records in `schemas/registry.py`;
- six canonical fixture copies and their raw-byte digest manifest;
- validators and deterministic reports in `artifact_auditor/`;
- immutable trace records and builders in `trace_explorer/`;
- transition records and derived-view builders in `transition_visualizer/`;
- 275 repository tests in `tests/`.

The executable registry contains 19 exact compatibility records. Registry
membership remains distinct from `supported` status. CI workflow evidence and
a release package are not yet declared.

## Integration Direction

The direction is strictly one-way:

`Fractal-Resonance-Processor` → published artifacts →
`FRP-Trace-Observatory`

Observatory-generated data is not written back upstream under this contract.

## Repository Boundary

Upstream FRP contains processor architecture and semantics, benchmark and
trace producers, foundations, RTL, FPGA preparation, and qualification
evidence. Observatory contains downstream source capture, parsing, validation,
normalization, correlation, trace construction, derived views, and reports.

UI dependencies, parser dependencies, Observatory tests, CI, and the
Observatory release lifecycle remain outside the upstream repository.

## Source Authority

FRP is the sole source of truth for processor semantics.

Observatory must not:

- redefine an FRP state or transition;
- replace the executable semantic reference;
- reproduce internal processor execution logic;
- modify an upstream artifact;
- change a published value or digest;
- invent a missing field or event;
- assign a new upstream schema identifier;
- silently reinterpret a schema version;
- merge unrelated measurement contours.

Captured source bytes establish what was loaded. Embedded identifiers and
values remain declarations subject to the exact registered producer contract.
A conflict is reported without repairing the source or choosing a replacement
value.

## Audited Upstream Baseline

This contract derives from the FRP v1.8.0 / M16 baseline and these exact
evidence paths:

- `frp_prototype_v1_7_0.py`;
- `docs/output_schema.md`;
- `docs/benchmark_matrix.md`;
- `docs/m15_implementation_mapping_domain_interface_qualification_closure.md`;
- `FRP_VALIDATION_INDEX_v1_8_0.md`;
- `docs/m16_qualification_manifest.md`;
- `docs/m16_qualification_index.md`;
- `docs/m16_public_status_snapshot.md`;
- `benchmarks/architecture_comparison/README.md`;
- `rtl/m16/ARTIFACTS.md`;
- `rtl/m16/SIMULATION_TRANSCRIPT.md`;
- `fpga/m16/SIMULATION_TRANSCRIPT.md`.

Producer details are recorded in `docs/supported_schema_registry.md`.
Evidence presence does not establish support. The baseline contains no formal
JSON Schema, canonical CSV artifact, or machine-readable `frp.m16.*` schema.
M16 retains published M15 identifiers without changing their versions.

## Artifact Eligibility

Typed normalized loading requires an exact compatibility record. Identity may
be established by:

1. embedded schema identifier;
2. embedded schema identifier and required `kind`;
3. registered format identifier;
4. exact role inside a verified deterministic package;
5. exact path-and-digest contract for a schema-free fixture.

A filename alone is insufficient, and a path does not override conflicting
content. An unrecognized artifact may receive source-integrity and format
diagnostics but cannot enter a typed trace or visualizer view.

## Compatibility Registry

The human-readable inventory is `docs/supported_schema_registry.md`; the
executable exact-match registry is `schemas/registry.py`.

Each executable record contains:

- exact schema or format identifier;
- identifier field;
- required artifact kind when applicable;
- artifact format;
- measurement contour;
- producer path and version when recorded;
- evidence kind and path;
- canonical fixture path when committed;
- eligible Observatory modes;
- audited upstream release.

Historical identifiers remain separate records. Aliases, automatic upgrades,
and implicit substitutions are prohibited. Shared schemas with different
`kind` values are dispatched by both fields. Producer commands are provenance
only and are never executed.

## Support States

Registry recognition and implementation support are separate facts. The
registry uses `not_implemented`, `implemented`, `tested`, `supported`,
`unsupported`, and `blocked_missing_fixture`.

Discovery or membership is not a support claim. An artifact becomes
`supported` only after every acceptance criterion is satisfied.

## Read-Only Loading Sequence

A conforming loader:

1. captures original source bytes;
2. records filename and known source path;
3. calculates a digest over unchanged bytes;
4. detects the non-executable container format;
5. parses through an applicable safe parser;
6. resolves the exact compatibility record;
7. validates identity, structure, values, relations, order, and digests;
8. constructs a separate immutable normalized representation;
9. exposes only registered eligible modes;
10. produces ordered checks and an audit report.

A failure blocks dependent success states. Source bytes remain available for
provenance even when validation fails.

## Provenance

Every captured artifact retains:

- source artifact identity;
- source filename and known source path;
- source byte length and SHA-256 digest;
- Observatory load timestamp;
- detected container format;
- declared schema or format identifier when present;
- matched compatibility record when resolved;
- producer path and version when registered;
- validation report identity and status;
- validation messages and source locations.

Absent values remain absent. Load time is Observatory, not upstream, metadata.

## Data Layers

Observatory separates four layers:

| Layer | Content | Authority |
|---|---|---|
| Source | Original bytes and embedded values | Upstream instance |
| Normalized | Immutable typed source projection | Observatory |
| Derived | Filters, correlations, output record sets | Observatory-derived |
| Audit | Validation checks, evidence, and status | Observatory analysis |

Normalized records retain source identities and locations. Derived records
retain their operation, source and validation identities, and the
`observatory_derived` label. Neither layer overwrites an upstream value.

## Source Immutability

Parsing, validation, normalization, filtering, and visualization do not
rewrite source bytes. Forbidden operations include:

- insertion, deletion, or renaming of fields;
- numeric replacement or automatic default insertion;
- array reordering;
- pre-digest whitespace or line-ending normalization;
- digest replacement;
- in-place schema migration.

A registered default is allowed only as a labeled derived interpretation.

## Validation Layers

Independent validation categories include:

1. container, encoding, and identity;
2. structure, type, and allowed values;
3. canonical ternary domain;
4. trace, tick, and event ordering;
5. scheduler and transition-capacity relations;
6. pending-route relations;
7. invariant vectors;
8. declared and calculated digests;
9. deterministic packages;
10. qualification evidence.

A lower-layer success does not imply higher-layer success. Warnings cannot
override a mandatory failure. Rules extracted from upstream code or
documentation are integration rules, not upstream JSON Schemas.

## Canonical Ternary Domain

The canonical processor domain is:

`-1, 0, 1`

State `0` is active neutral; the positive state is `1`. Canonical validation
applies only to registered processor-state fields. Packed codes, vector
values, and interface encodings require a separate exact mapping contract.

## Trace and Transition Rules

The canonical opposite-polarity routes are:

- `-1 → 0 → 1`;
- `1 → 0 → -1`.

Source-linked records may represent:

- first-leg neutralization;
- retained pending polarity and route completion;
- scheduler or transition-capacity deferral;
- accepted and rejected request lanes;
- published telemetry, event counters, and invariants.

Records remain linked to validated source evidence or are explicitly marked
as deterministic Observatory-derived results.

Aggregate counters are not expanded into invented per-tick events.

An absent field is not equivalent to a zero value.

Source trace and record order are preserved. Filters retain source order.

Tick monotonicity, uniqueness, event order, and route order are validated
under the exact artifact contract.

An invalid trace is not silently sorted and presented as source order.

A separately sorted presentation requires an Observatory-derived label while
the source-order result remains visible.

Scheduler mode, scheduler state, counters, transition capacity, switching
load, and retained state remain distinct fields.

Relations are checked only when published by the registered contract.

Acceptance, rejection, or deferral reasons are not inferred from unrelated
aggregate counters.

## Digest and Package Handling

Observatory distinguishes:

- source raw-byte digest;
- whole-artifact declared digest;
- canonical-substructure digest;
- trace and per-cell trace digests;
- deterministic-package digest;
- package-member digests.

Digests are checked only with registered algorithms, scopes, serialization
rules, and ordering rules.

Raw-byte digest input is not normalized.

A mismatch retains both declared and calculated values.

Package validation may check:

- exact filenames, count, and byte sizes;
- per-file and package digests;
- manifest consistency;
- required format identifiers;
- cross-file relations.

A schema-free member is recognized only by its role in a verified package.

A missing member produces `incomplete_package`. Missing members are not
reconstructed or substituted.

## Qualification Evidence

Qualification evidence retains original scope and provenance.

Published `PASS` and `SUCCESS` values may be displayed exactly as recorded.

Results remain associated with their release, contour, source, producer or
workflow, recorded run or commit identity, artifact set, and available digest.

A zero-event result is valid only when its value and scope are explicit.

Invariant vectors retain source bit order. Unregistered meanings are not
assigned to bit positions.

Human-readable M16 qualification documents are evidence records, not
machine-readable per-tick traces.

Absent referenced CI artifacts remain unavailable and are not reconstructed.

Target-independent FPGA preparation evidence is not physical-chip evidence.

## Measurement Contours

These upstream contours remain separate:

- historical transition benchmark;
- structured-output benchmark;
- M3 benchmark matrices;
- transition-pressure and feedback-stress matrix;
- thermal-survival and stability-boundary matrix;
- hierarchical scaling and hotspot-containment matrix;
- M15 implementation-mapping matrix;
- Comparative Architecture Benchmark Suite;
- Hardware-Informed Sensitivity Qualification;
- M16 RTL qualification;
- M16 FPGA preparation qualification.

Each compatibility record identifies its implemented contour.

Operation count, thermal proxy, transition pressure, `heat_peak`, scheduler
timing, latency, throughput, RTL execution, FPGA preparation evidence, and
physical measurements remain distinct quantities.

Identical names across contours do not establish identical definitions, units,
or methods.

Cross-contour correlation is Observatory-derived and retains source contours.

Comparative aggregates are not processor-tick traces.

## Mode Eligibility

| Mode | Eligible validated data |
|---|---|
| Trace Explorer | Registered processor-tick, cell, and cycle-exact traces |
| Transition Visualizer | States, routes, scheduler data, telemetry, counters, and invariants |
| Artifact Auditor | Registered artifacts, packages, profiles, results, and manifests |

Multi-mode use requires every mode in the exact compatibility record.

Unsupported or unrecognized artifacts do not enter Trace Explorer or Ternary
Transition Visualizer.

## Current Implementation Boundary

Parsers accept registered JSON and M15 headered vector text. Other text,
archives, and binary input receive safe classification.

Artifact Auditor routes structured output, M3 matrices, registered M15 JSON
and vector text, deterministic M15 packages, comparative and
hardware-sensitivity artifacts, and canonical fixture inventories.

Trace construction covers valid structured full traces, M15 cycle-exact
reference traces, primary and per-cell vectors, and pending-route traces.

Visualizer models and builders cover validated state, transition, request,
route, scheduler, telemetry, counter, and invariant records.

CSV remains outside until an upstream artifact and producer contract exist.
Typed M16 views remain outside because no committed machine-readable M16
trace or `frp.m16.*` schema was present.

The fixture inventory does not claim committed canonical M15 vector fixtures.

## Safe Processing Boundary

Uploaded artifacts are untrusted data.

Loading must not:

- execute scripts, commands, or expressions;
- compile or simulate SystemVerilog;
- invoke producer commands;
- load executable artifact modules;
- follow paths outside the controlled boundary;
- automatically fetch external resources.

SystemVerilog is opaque package data for registered identity, size, or digest
checks only.

Archive extraction is not implemented. Any future extraction must reject
traversal, unsafe links, and external writes.

Resource limits precede unrestricted parsing of large, nested, or compressed
inputs.

Rendered artifact strings remain data, not executable markup.

## Audit Reports and Outcomes

Machine-readable and user-facing reports originate from the same ordered
validation checks.

Reports identify:

- source provenance and detected format;
- declared and matched identities;
- producer association;
- checks, locations, expected values, and observed values;
- outcome counts and digest-check identities;
- missing package members;
- aggregate status;
- Observatory version when assigned.

Reports serialize to immutable mappings, deterministic compact JSON, and plain
text. They are Observatory-derived, not upstream qualification evidence.

The implemented aggregate outcomes are:

- `recognized_valid`;
- `recognized_valid_with_warnings`;
- `recognized_invalid`;
- `known_unsupported`;
- `unrecognized`;
- `incomplete_package`.

Unsupported does not invalidate upstream semantics; invalid does not authorize
source modification. Uncertainty remains explicit.

## Support Acceptance Criteria

A format may be declared `supported` only when all are present:

1. exact compatibility record;
2. upstream producer and version when published;
3. field, value, order, relation, and digest rules;
4. read-only parser and validator;
5. canonical and mandatory-failure fixtures;
6. parser, validator, provenance, and immutability tests;
7. mode integration tests;
8. synchronized documentation;
9. applicable CI workflow evidence.

Qualification support additionally requires applicable manifest, digest,
deterministic-set, zero-event, and invariant tests.

## Versioning and Change Control

Observatory has an independent version lifecycle and does not automatically
match or support a new FRP release. Supported releases, identifiers, producer
versions, kinds, and modes are explicit.

A compatibility change requires audited evidence, registry, fixture, parser,
validator, test, documentation, and workflow review. Release claims require
test and workflow evidence. Upstream changes require a separate action.

## Non-Goals

This contract does not authorize:

- execution or reimplementation of FRP processor semantics;
- modification or replacement of published FRP artifacts;
- creation of new FRP schema identifiers;
- automatic schema-version migration;
- AI inference, training, or autonomous-agent functions;
- new processor execution or physical implementation claims.

## Author

Maksym Marnov
