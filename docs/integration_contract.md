# FRP Trace Observatory Integration Contract

- **Status:** Implemented and qualified through the FRP M31 published boundary
- **Integration direction:** FRP published bytes → FRP Trace Observatory
- **Audited upstream scopes:** FRP v1.8.0 / M16, immutable M30 archive, M31 publication
- **Base compatibility records:** 19
- **M30 published-member registrations:** 4
- **M30 exact mode routes:** 7
- **M31 published-document registrations:** 4
- **M31 exact mode routes:** 6
- **Current exact verification:** 655 tests, `OK`

Related contracts:

- [Supported Schema Registry](supported_schema_registry.md)
- [Normalized Data Model](normalized_data_model.md)
- [M31 Published Evidence Boundary](m31_published_boundary.md)

## Purpose

This document defines the integration boundary between the Fractal Resonance
Processor repository and FRP Trace Observatory. It governs immutable source
capture, exact identity resolution, read-only loading, validation,
provenance, normalization, audit reporting, trace construction, transition
visualization, measurement-contour separation, and Observatory mode
eligibility.

FRP remains the authority for processor architecture, semantics, equations,
published measurements, release identities, and qualification evidence.
Observatory verifies and projects published evidence without replacing that
authority.

## Contract Authority

The integration contract is implemented by three executable registry layers:

| Scope | Executable authority | Inventory |
|---|---|---:|
| M16-baseline compatibility | `schemas/registry.py` | 19 records |
| M30 immutable publication | `schemas/m30_published_registry.py` | 4 registrations, 7 routes |
| M31 immutable publication | `schemas/m31_published_registry.py` | 4 registrations, 6 routes |

The human-readable companion is
[`docs/supported_schema_registry.md`](supported_schema_registry.md).
Executable records control identity and mode routing. Documentation records
the same boundary, provenance, lifecycle state, and qualification history.

When documentation and a published artifact differ, the artifact is not
silently repaired. The conflict is reported against the exact executable
registration and retained in audit provenance.

## Integration Direction

The data flow is one-way:

```
Fractal-Resonance-Processor
    → immutable published artifacts
    → exact Observatory intake
    → Artifact Auditor
    → Trace Explorer
    → Ternary Transition Visualizer
```

Observatory-generated records remain downstream. The integration does not
write source, normalized data, derived data, audit results, or visualizer
state back into FRP.

## Repository Boundary

The upstream FRP repository contains:

- processor architecture and semantic definitions;
- balanced-ternary state and route definitions;
- physical and computational foundations;
- executable references;
- benchmark and trace producers;
- RTL and FPGA preparation artifacts;
- release, evidence, manifest, and qualification records.

FRP Trace Observatory contains:

- immutable source capture and safe parsing;
- exact compatibility and publication registries;
- schema and artifact validation;
- deterministic audit reports;
- source-linked normalized records;
- trace and transition datasets;
- derived views and measurement-contour ledgers;
- downstream qualification tests and workflows.

Upstream producer commands are provenance. Observatory does not execute them
during artifact intake.

## Implemented Observatory Boundary

The repository implements:

- source capture, digest calculation, and format classification in
  `parsers/`;
- base, M30, and M31 exact registries in `schemas/`;
- six unchanged canonical upstream fixture copies in `fixtures/`;
- validators, package checks, and deterministic reports in
  `artifact_auditor/`;
- immutable trace records and builders in `trace_explorer/`;
- transition, route, scheduler, telemetry, invariant, and view models in
  `transition_visualizer/`;
- complete base, M30, and M31 tests in `tests/`;
- manual qualification entry points in `.github/workflows/`.

The current test inventory contains 655 tests. Publication-contour integration
tests execute against the exact configured M30 archive and M31 repository
root. When an upstream input is absent, the affected integration cases remain
reported as skipped rather than being replaced by synthetic evidence.

## Audited Upstream Scopes

### FRP v1.8.0 / M16 baseline

The original compatibility inventory was audited from the FRP v1.8.0 / M16
scope, including:

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

This baseline supplies 19 compatibility records. It contains no committed
formal JSON Schema, canonical CSV artifact, or machine-readable
`frp.m16.*` schema. M16 retains published M15 identifiers at their recorded
versions.

### Immutable M30 publication

The M30 publication authority is the exact archive:

`artifacts/m30/packages/frp-v3.2.0-m30-archival-release.tar.gz`

| Property | Exact value |
|---|---|
| Archive bytes | 10,189,989 |
| Raw SHA-256 | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |
| Release root | `Fractal-Resonance-Processor-FRP-v3.2.0` |
| Source commit | `ff3dd434da5dcbd9e8fa62444f658ed4c495b540` |
| Archive entries | 519 |
| Manifested source members | 518 |
| Registry revision | `m30-published-boundary-v1` |

The M30 registry exposes four digest-bound members:

| Member id | Exact upstream path | Exact schema | Bytes | Raw SHA-256 |
|---|---|---|---:|---|
| `m16-fpga-preparation-execution-trace` | `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` | `frp.m16.fpga_preparation_execution_trace.v2.1.0` | 9,013 | `7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f` |
| `m27-telemetry-semantics` | `artifacts/m27/telemetry/m27-telemetry-semantics.json` | `m27-telemetry-semantics-v2.9.0` | 2,789 | `813ae5c66ceaddabc77734d44f1ebf971ca3bd7e11c1984e2e0c8f0204dfd1bc` |
| `m28-trace-observatory-upstream-contract` | `artifacts/m28/contracts/m28-trace-observatory-upstream-contract.json` | `frp.m28.trace_observatory_upstream_contract.v3.0.0` | 2,735 | `556cd2921014d78184dad625438e053632c2650164f95787f39a6fc871b4a3f0` |
| `m28-hierarchical-scaling-contract` | `artifacts/m28/hierarchy/contracts/m28-hierarchical-scaling-contract.json` | `frp.m28.hierarchical_scaling_contract.v3.0.0` | 3,560 | `13f85ac82b63d0191157bd2cfa04dd37358ef66d8e69bdb96bb1892abb77dbae` |

### M31 publication

The M31 authority consists of exactly four immutable JSON documents:

| Role | Exact upstream path | Identifier | Bytes | Raw SHA-256 |
|---|---|---|---:|---|
| Formal schema | `schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | `$id = https://frp.example/schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | 1,468 | `53d79d45d70753ccd24c3dc4c97af6fee481f86a9d7cdca7ef78b486c76479f7` |
| Evidence | `artifacts/m31/evidence/m31-phase-interference-active-zero-thermal-evidence.json` | `schema = frp.m31.phase_interference_active_zero_thermal_evidence.v1` | 39,993 | `bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42` |
| Manifest | `artifacts/m31/manifests/m31-phase-interference-active-zero-thermal-evidence-manifest.json` | `schema = frp.m31.phase_interference_active_zero_thermal_evidence_manifest.v1` | 828 | `80f0841d0041cd22c2f76175b6139e601aede7b69823356ae1fefbce5f793e7c` |
| Qualification | `artifacts/m31/qualification/m31-phase-interference-active-zero-thermal-evidence-qualification.json` | `schema = frp.m31.phase_interference_active_zero_thermal_evidence_qualification.v1` | 1,512 | `4c2446f954e01ec0aa37cc6c0fc70cf4a87ec565c450628e31b0efcac9160224` |

The exact publication version is `1.0.0`, the upstream milestone is `M31`,
the publication status is `PASS`, and the registry revision is
`m31-published-boundary-v1`.

The complete M31 source inventory and provenance chain are recorded in
[`docs/m31_published_boundary.md`](m31_published_boundary.md).

## Artifact Eligibility

Typed normalized loading requires an exact executable registration. Identity
is established by one of these registered contracts:

1. exact embedded schema identifier;
2. exact embedded schema identifier plus required `kind`;
3. exact registered format identifier;
4. exact role within a verified deterministic package;
5. exact path, byte length, and digest for a schema-free fixture;
6. exact publication role, path, identifier field, identifier value, kind,
   byte length, and digest for an M31 document.

A filename alone does not establish typed identity. A matching path does not
override conflicting bytes or fields. An unrecognized artifact may receive
source-integrity and format diagnostics, but it does not enter a typed trace
or visualizer dataset.

## Executable Registry Model

Each base compatibility record contains:

- exact schema or format identifier;
- identifier field;
- required artifact kind where applicable;
- artifact format;
- measurement contour;
- producer path and version when recorded;
- evidence path;
- canonical fixture path when committed;
- eligible Observatory modes;
- audited upstream release.

Each M30 registration additionally binds:

- archive identity;
- exact member id and archive-relative source path;
- exact schema identifier;
- exact byte length and raw SHA-256;
- upstream release identity;
- deterministic compatibility key.

Each M31 registration additionally binds:

- canonical publication role;
- exact source path;
- exact identifier field and value;
- exact required `kind` where applicable;
- exact byte length and raw SHA-256;
- measurement contour;
- eligible mode tuple;
- deterministic compatibility key.

Historical identifiers remain separate records. Aliases, automatic upgrades,
implicit substitutions, and case-normalized identity matching are excluded.
Shared schemas with different `kind` values are dispatched by both fields.

## Lifecycle and Qualification States

Registry recognition and implementation support are separate facts.

| State | Meaning |
|---|---|
| `not_implemented` | Identity is audited without a parser and validator |
| `implemented` | Parser, routing, and validation exist |
| `tested` | Canonical evidence and mandatory-failure cases pass tests |
| `supported` | All integration-contract gates and CI evidence are complete |
| `unsupported` | Identity is intentionally outside the current boundary |
| `blocked_missing_fixture` | Required canonical upstream evidence is absent |

Current registry state:

- base records 1–14 are `implemented`;
- base records 15–19 are `tested` against unchanged canonical fixture copies;
- the schema-free workload copy is tested only as manifest-bound evidence;
- the four M30 registrations and seven routes are qualified by M8B;
- the four M31 registrations and six routes are qualified by M22;
- base records 1–14 retain their state until canonical upstream instances and
  all remaining support gates are present.

Discovery, documentation, or registry membership alone does not create a
`supported` claim.

## Common Read-Only Intake Protocol

A conforming loader performs these operations in order:

1. accepts a controlled path or byte source;
2. rejects unsafe path forms and unsupported source types;
3. captures the original bytes without modification;
4. records filename and known source path;
5. calculates raw byte length and SHA-256;
6. detects the non-executable container format;
7. parses through the applicable bounded parser;
8. resolves the exact registry identity;
9. validates structure, values, relations, ordering, and digests;
10. constructs a separate immutable normalized representation;
11. exposes only the modes declared by the resolved registration;
12. produces ordered validation checks and an immutable audit report.

A failed prerequisite blocks dependent success states. Captured source bytes
remain available for provenance after validation failure.

## M30 Archive Intake Protocol

M30 intake uses `FRP_M30_ARCHIVE_PATH` and validates the archive as one
immutable publication boundary.

The intake verifies:

- exact archive byte length and raw SHA-256;
- gzip and tar container structure;
- exact release root;
- exact entry count;
- exact internal manifest identity;
- exact manifested-member count;
- safe relative POSIX member paths;
- regular-file and directory types allowed by the contract;
- absence of traversal, absolute paths, unsafe links, and duplicate members;
- member byte lengths and SHA-256 values against the internal manifest;
- source commit and release identity;
- exact identities of the four registered published members.

Archive members are read as data. The intake does not execute archive
content, producer commands, Python modules, shell scripts, RTL, or workflows.

## M31 Repository Intake Protocol

M31 intake uses `FRP_M31_UPSTREAM_ROOT` and resolves exactly four registered
paths beneath a clean FRP repository root.

The intake verifies:

- the root is a directory;
- each requested path remains beneath that root;
- every target is a regular file rather than a symbolic link;
- exact byte length and raw SHA-256 for every document;
- exact JSON object structure;
- exact identifier field and value;
- exact `kind`, `milestone`, `version`, and `status` where applicable;
- formal-schema identity and publication document relationships;
- manifest and qualification references;
- exact provenance declarations and measurement contours.

Only the evidence document is eligible for all three Observatory modes. The
formal schema, manifest, and qualification documents are routed to Artifact
Auditor only.

## Provenance Contract

Every captured artifact retains:

- source artifact identity;
- source filename and known source path;
- source byte length and raw SHA-256;
- Observatory load timestamp;
- detected container format;
- declared schema or format identifier when present;
- matched compatibility or publication registration;
- producer path and version when registered;
- upstream release, milestone, and source commit when published;
- validation report identity and status;
- ordered validation messages and source locations;
- parent archive, manifest, and publication identities when applicable.

Absent values remain absent. Observatory load time is downstream provenance,
not an upstream production timestamp.

## Data Layers

Observatory separates four immutable data layers:

| Layer | Content | Authority |
|---|---|---|
| Source | Original bytes and embedded values | Upstream instance |
| Normalized | Typed, immutable projection of validated source fields | Observatory |
| Derived | Filters, correlations, trace datasets, transition frames, and views | Observatory-derived |
| Audit | Ordered checks, evidence, digests, and aggregate status | Observatory analysis |

Normalized records retain source identity and location. Derived records retain
their operation, source identities, validation identities, measurement
contours, and `observatory_derived` classification. No downstream layer
overwrites a value in an upstream layer.

The complete field-level projection contract is recorded in
[`docs/normalized_data_model.md`](normalized_data_model.md).

## Source Immutability

Parsing, validation, normalization, filtering, correlation, and visualization
preserve source bytes. The boundary excludes:

- insertion, deletion, or renaming of source fields;
- numeric replacement or automatic default insertion;
- source-array reordering;
- pre-digest whitespace or line-ending normalization;
- digest replacement;
- in-place schema migration;
- publication role substitution;
- writeback to the upstream repository.

A registered default may appear only as a labeled downstream interpretation.
The original absence remains visible.

## Safe Processing Boundary

Uploaded artifacts are untrusted data. The loader treats source content as
data and applies bounded parsing before semantic projection.

The processing boundary excludes:

- execution of scripts, commands, expressions, or embedded code;
- compilation or simulation of SystemVerilog;
- invocation of producer commands or GitHub workflows;
- import of executable artifact modules;
- path traversal and absolute archive member paths;
- symbolic-link, hard-link, device, FIFO, and unknown retained paths;
- automatic retrieval of external resources;
- external writes.

SystemVerilog is opaque package data for registered identity, size, digest,
and manifest checks. Resource limits precede unrestricted processing of
large, nested, or compressed inputs. Rendered artifact strings remain data,
not executable markup.

## Validation Layers

Validation is divided into independently reported layers:

1. source type, path, and containment;
2. container and encoding;
3. raw byte length and digest;
4. schema, format, role, and kind identity;
5. structure, field presence, type, and allowed values;
6. balanced-ternary state domain;
7. trace, tick, epoch, and event ordering;
8. scheduler and transition-capacity relations;
9. request, acceptance, rejection, and pending-route relations;
10. invariant vectors and declared bit order;
11. declared and calculated digest scopes;
12. deterministic archive and package membership;
13. manifest and qualification relationships;
14. mode-route eligibility;
15. deterministic output identity.

A lower-layer success does not imply a higher-layer success. Warnings do not
override mandatory failures. Rules transcribed from upstream code or
documentation are integration rules unless an exact upstream formal schema is
part of the registered publication.

## Processor Semantic Boundary

The published M31 processor state domain is the balanced ternary set:

```
S = {-1, 0, 1}
```

State `0` is an active computational state. It is the neutral state used for
conflict mediation, temporal separation, balancing, damping, transition
buffering, switching-load distribution, retained-transition continuity,
pending-route preparation, and stabilization.

The published opposite-polarity routes are:

```
-1 → 0 → 1
 1 → 0 → -1
```

The route relation requires the active neutral state between opposite
polarities.

The published primary computational organization is:

```
retained_relative_phase_interference_and_resonant_selection
```

The published computation chain is:

1. retained phase and frequency state;
2. relative-phase interaction;
3. phase organization and dispersion;
4. resonance selection;
5. multiscale coherence evaluation;
6. dynamic stability evaluation;
7. phase-derived ternary target;
8. distributed active-neutral commit;
9. retained coherent ternary state.

The ternary layer is the discrete-state target-transition and retained-result
boundary. The published temporal scheduler modes are `1/7` and `7/1`; the
service scheduler mode is `free`.

Observatory preserves this declaration and projects published evidence. It
does not define a replacement state machine, transition rule, scheduler,
resonance equation, thermal equation, or processor execution model.

## Trace and Transition Contract

Source-linked records may represent:

- first-leg neutralization;
- retained pending polarity and route completion;
- scheduler or transition-capacity deferral;
- accepted and rejected request lanes;
- published telemetry, counters, and invariants;
- primary and per-cell state observations;
- cycle-exact reference records;
- source-linked M30 and M31 execution contours.

Trace construction follows these rules:

- aggregate counters are retained as aggregates;
- absent fields remain absent rather than being converted to zero;
- source record, tick, epoch, event, and cell order are preserved;
- filters preserve relative source order;
- invalid source order is reported rather than silently sorted;
- separately sorted presentations are labeled Observatory-derived;
- scheduler mode, scheduler state, capacity, switching load, and retained
  state remain distinct fields;
- acceptance, rejection, and deferral reasons are taken only from fields
  published by the exact contract;
- cross-record relations are evaluated only when their registered source
  contract publishes the required fields.

Every M31 transition frame retains its source contour, source record, cell,
before-state, after-state, transition classification, and route-leg identity.

## Measurement-Contour Separation

The Observatory preserves the following established contours as distinct:

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
- M16 FPGA preparation qualification;
- M27 long-run telemetry semantics;
- M28 upstream integration contract;
- M28 hierarchical-scaling qualification;
- M31 formal schema definition;
- M31 phase-interference, active-zero, and thermal evidence;
- M31 publication manifest;
- M31 publication qualification.

Operation count, thermal proxy, transition pressure, `heat_peak`, scheduler
timing, latency, throughput, RTL execution, FPGA preparation evidence, and
physical measurements remain distinct quantities. Identical labels across
contours do not establish identical definitions, units, methods, or scopes.

Cross-contour correlation is Observatory-derived and retains every source
contour. Comparative aggregates are not converted into processor-tick traces.

## Digest and Package Contract

Observatory distinguishes:

- source raw-byte digest;
- whole-artifact declared digest;
- canonical-substructure digest;
- trace and per-cell trace digests;
- deterministic-package digest;
- archive-container digest;
- manifest digest;
- package-member digest;
- compatibility key;
- derived dataset digest.

Each digest is checked only with its registered algorithm, byte scope,
serialization rule, and ordering rule. Raw-byte digest input is not normalized.
A mismatch retains both declared and calculated values in the audit result.

Package validation may check:

- exact root and filenames;
- exact member count, byte size, and file type;
- per-file, manifest, and package digests;
- required schema and format identifiers;
- deterministic member order where published;
- cross-file references and relations.

A schema-free member is recognized only by its exact role in a verified
package. A missing or mismatched member produces an incomplete or invalid
package result; Observatory does not reconstruct or substitute it.

## Mode Eligibility

| Mode | Eligible validated data |
|---|---|
| Artifact Auditor | Registered artifacts, packages, profiles, results, schemas, manifests, and qualifications |
| Trace Explorer | Registered processor-tick, cell, cycle-exact, and published execution traces |
| Ternary Transition Visualizer | Registered states, routes, scheduler data, telemetry, counters, invariants, and transition frames |

Multi-mode use requires every requested mode in the exact registration.
Unrecognized or ineligible artifacts remain outside Trace Explorer and
Ternary Transition Visualizer.

M30 mode routes:

| Mode | Route count |
|---|---:|
| Artifact Auditor | 4 |
| Trace Explorer | 1 |
| Ternary Transition Visualizer | 2 |
| **Total** | **7** |

M31 mode routes:

| Mode | Route count |
|---|---:|
| Artifact Auditor | 4 |
| Trace Explorer | 1 |
| Ternary Transition Visualizer | 1 |
| **Total** | **6** |

## Audit Reports and Outcomes

Machine-readable and user-facing reports originate from the same ordered
validation checks.

Reports identify:

- source provenance and detected format;
- declared and matched identities;
- registration and producer association;
- checks, source locations, expected values, and observed values;
- outcome counts and digest-check identities;
- missing or mismatched package members;
- aggregate status;
- Observatory version when assigned.

Reports serialize to immutable mappings, deterministic compact JSON, and
plain text. They are Observatory-derived records and do not replace upstream
qualification evidence.

The implemented aggregate outcomes are:

- `recognized_valid`;
- `recognized_valid_with_warnings`;
- `recognized_invalid`;
- `known_unsupported`;
- `unrecognized`;
- `incomplete_package`.

An invalid result records a conflict without authorizing source modification.
An unsupported result records downstream scope without changing upstream
semantics or status.

## Qualified M30 Boundary

### Artifact Auditor

The qualified M30 audit batch contains:

```
published_members=4
audit_reports=4
validation_checks=69
failed_checks=0
batch_sha256=aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03
```

### Trace Explorer

The qualified M30 trace projection contains:

```
trace_records=4
cell_snapshots=32
request_records=8
observed_state_domain=-1/0/1
dataset_sha256=4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd
```

### Ternary Transition Visualizer

The M8B full-core qualification combines two exact published trace sources:

```
trace_records=100
transition_frames=800
visualizer_dataset_id=68de3476-2e03-5506-93ea-062c3744e90d
dataset_sha256=7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b
```

## Qualified M31 Boundary

### Artifact Auditor

The M31 Artifact Auditor produces four immutable reports:

| Role | Checks | Status | Report SHA-256 |
|---|---:|---|---|
| Formal schema | 11 | `recognized_valid` | `5f18fd174e02f19adcac1809624a2c205b94ae6c226e05a20eaac4f896c6bb36` |
| Evidence | 16 | `recognized_valid` | `e7c6163954973aa60994d2fa76f6f7edfdc6429fcbb397cf7e403a4e64f2f130` |
| Manifest | 10 | `recognized_valid` | `e0ef32073524cd41ea2cf0b7b273ef3c63c61080e5ff72ae9e5432a81609d652` |
| Qualification | 10 | `recognized_valid` | `5374a6b6e0def38ae5a50bb216c9be0396f6139f4a07e982b47e86b719414b53` |

Aggregate identity:

```
published_documents=4
audit_reports=4
validation_checks=47
failed_checks=0
batch_sha256=3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591
```

### Trace Explorer

The qualified M31 trace dataset contains:

- 2 source contours;
- 100 ordered trace records;
- 800 source-linked cell snapshots;
- 200 request records;
- 100 invariant-pass records;
- 702 observations with retained active-neutral state `0`;
- scheduler-mode counts `free = 19`, `7/1 = 64`, and `1/7 = 17`;
- observed state domain `-1/0/1`.

Source contours:

| Source path | Records | Source-record digest | Contour SHA-256 |
|---|---:|---|---|
| `artifacts/m19/execution/m16-rtl-execution-trace.json` | 96 | `3f730a3d088e4d75fdd1631dd234878a6acd3a7561cb463e19c815096c04fe6a` | `23a0af37356389dc6ffd4ab2bac4a0cf64a418583ed43195b44193dacc3c4600` |
| `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` | 4 | `4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57` | `3e06ba60c8fb3bab08eabd83b9a3d83dee0176c6a682bb2825d2bba9d62dee94` |

Deterministic identities:

```
trace_dataset_id=0f0f0f7e-0409-5e7b-8c76-2f72bb954321
trace_dispatch_sha256=f34b867fabcaab51515ecca39f2eb7287f52aa218d3ac48596a1481326009630
dataset_sha256=ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff
```

### Ternary Transition Visualizer

The qualified visualizer dataset contains 800 source-linked transition
frames.

| Transition classification | Count |
|---|---:|
| `active_zero_to_polarity` | 12 |
| `polarity_to_active_zero` | 5 |
| `retained_same` | 783 |
| `direct_opposite` | 0 |

| Route leg | Count |
|---|---:|
| `non_route_transition` | 790 |
| `first_leg_to_active_zero` | 5 |
| `pending_route_completion` | 5 |

Deterministic identities:

```
visualizer_dataset_id=63a1feb9-1835-579e-ab00-eec4569e8ff3
visualizer_dispatch_sha256=ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8
dataset_sha256=0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304
```

### Thermal Evidence Separation

The M31 visualizer retains four separate published thermal evidence contours:

| Contour | Group | Physical temperature | Contour SHA-256 |
|---|---|---|---|
| `historical_release_benchmark` | historical | false | `8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140` |
| `current_comparative_baseline` | current | false | `c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add` |
| `current_hardware_sensitivity` | current | false | `9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0` |
| `current_thermal_profile` | current | false | `1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee` |

These are proxy and benchmark contours. The M31 publication records zero
physical-temperature measurements.

The historical focused comparison remains exactly source-linked:

```
binary_heat_peak=0.051000
active_neutral_ternary_heat_peak=0.003250
heat_peak_ratio_binary_over_active_neutral_ternary=15.6923076923
heat_peak_relative_reduction_percent=93.63
```

Its source record contains an empty `winner_assertions` list. Current
comparative, hardware-sensitivity, and thermal-profile contours remain
separate from that historical record.

## Observatory Qualification History

The M30 and M31 integration boundaries were implemented incrementally. Every
milestone remains independently addressable.

| Observatory milestone | Published increment |
|---|---|
| M1 | Immutable M30 archive intake |
| M2 | M30 published-boundary intake |
| M3 | M30 published registry and routing |
| M4 | M30 published-member intake |
| M5 | M30 published dispatch boundary |
| M6 | M30 published Artifact Auditor |
| M7A | M30 published Trace Explorer source |
| M7B | M30 published Trace Explorer qualification |
| M8A1 | M30 full-core Transition Visualizer payload segment 1 |
| M8A2 | M30 full-core Transition Visualizer source continuation |
| M8A3 | M30 full-core Transition Visualizer assembly |
| M8B | M30 full-core Transition Visualizer qualification |
| M9 | M31 published-boundary intake workflow |
| M10 | Read-only M31 published-boundary intake source |
| M11 | M31 published-boundary intake tests |
| M12 | Exact M31 published-document registry source |
| M13 | M31 published-document registry tests |
| M14 | Exact M31 mode-dispatch source |
| M15 | M31 mode-dispatch tests |
| M16 | M31 published Artifact Auditor source |
| M17 | M31 published Artifact Auditor tests |
| M18 | M31 published Trace Explorer source |
| M19 | M31 published Trace Explorer tests |
| M20 | M31 published Ternary Transition Visualizer source |
| M21 | M31 published Ternary Transition Visualizer tests |
| M22 | Complete M31 Observatory end-to-end qualification |

M22 verifies the complete M31 chain without replacing M9–M21 history. M8B
verifies the complete M30 visualization chain without replacing M1–M8A3
history.

## Qualification Commands

Configure the exact upstream inputs:

```
export FRP_M30_ARCHIVE_PATH=/path/to/frp-v3.2.0-m30-archival-release.tar.gz
export FRP_M31_UPSTREAM_ROOT=/path/to/Fractal-Resonance-Processor
```

Validate the exact M30 boundary:

```
python -m artifact_auditor.m30_archive_intake \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m schemas.m30_published_registry \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m artifact_auditor.m30_published_auditor \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m trace_explorer.m30_published_trace_explorer \
  --archive "$FRP_M30_ARCHIVE_PATH"

python -m transition_visualizer.m30_published_transition_visualizer \
  --archive "$FRP_M30_ARCHIVE_PATH"
```

Validate the exact M31 boundary:

```
python -m schemas.m31_published_registry \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m artifact_auditor.m31_published_auditor \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m trace_explorer.m31_published_trace_explorer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"

python -m transition_visualizer.m31_published_transition_visualizer \
  --upstream-root "$FRP_M31_UPSTREAM_ROOT"
```

Run the exact M31 end-to-end suite:

```
python -m unittest \
  tests.test_m31_published_observatory_end_to_end \
  -v
```

Expected M31 end-to-end result:

```
Ran 26 tests

OK
```

Run the complete Observatory suite:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified complete result with both exact upstream inputs configured:

```
Ran 655 tests

OK
```

## Manual GitHub Actions Qualification

Qualification workflows are manually dispatched after their corresponding
repository files have been committed. A workflow run validates published
repository state; it is not the mechanism used to create or replace the
source file being qualified.

The terminal M30 qualification entry point is:

`.github/workflows/frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml`

The terminal M31 qualification entry point is:

`.github/workflows/frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml`

The complete M1–M22 workflow history remains in `.github/workflows/`.

## Support Acceptance Criteria

A format or publication role may be declared `supported` only when all
applicable gates are present:

1. exact executable registration;
2. exact upstream producer and version when published;
3. field, value, order, relation, and digest rules;
4. read-only parser and validator;
5. canonical success evidence;
6. mandatory identity, mutation, and relation failure cases;
7. provenance and source-immutability tests;
8. mode-routing and consumer integration tests;
9. synchronized integration, registry, and data-model documentation;
10. applicable CI or manual workflow qualification evidence.

Publication support additionally requires exact path, byte length, raw
SHA-256, role, manifest or archive membership, deterministic output identity,
and full-boundary qualification.

## Versioning and Change Control

Observatory has an independent version lifecycle. A new FRP release,
milestone, schema, artifact kind, package, digest, or producer version does
not automatically inherit an existing Observatory route.

A compatibility change requires:

1. audited upstream evidence;
2. a new or deliberately revised exact registration;
3. parser and validator review;
4. success and mandatory-failure fixtures;
5. provenance, immutability, and route tests;
6. consumer integration tests;
7. synchronized documentation;
8. qualification workflow evidence.

Historical registrations, evidence, benchmarks, manifests, reports, dataset
identities, RTL records, FPGA records, and workflow history remain preserved.

## Non-Goals

This contract does not authorize:

- execution or reimplementation of FRP processor semantics;
- modification or replacement of published FRP artifacts;
- creation of new upstream FRP schema identifiers;
- automatic schema-version migration;
- conversion of proxy measurements into physical measurements;
- merging of independent benchmark or thermal contours;
- fabrication of absent per-tick events, fields, fixtures, or evidence;
- upstream repository mutation or downstream writeback;
- new processor execution, RTL, FPGA, silicon, or physical-measurement claims.

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
