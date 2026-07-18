# FRP Trace Observatory Integration Contract

**Status:** Initial downstream integration contract  
**Upstream audit baseline:** FRP v1.8.0 / M16  
**Observatory version:** Not assigned

## Purpose

This document defines the integration boundary between the Fractal Resonance Processor repository and FRP Trace Observatory.

It governs artifact identification, read-only loading, validation, provenance, normalization, audit reporting, and mode eligibility.

This contract does not define, extend, or replace FRP processor semantics.

## Integration Direction

The integration direction is strictly one-way:

**Fractal-Resonance-Processor → published artifacts → FRP-Trace-Observatory**

Published artifacts may include:

- JSON outputs;
- CSV outputs;
- processor traces;
- per-cell traces;
- route-event traces;
- deterministic vectors;
- schema identifiers;
- profiles;
- benchmark results;
- manifests;
- declared digests;
- validation indexes;
- qualification records.

Observatory-generated data is not written back to the upstream FRP repository under this contract.

## Repository Boundary

The upstream FRP repository contains the processor architecture, executable semantic reference, benchmark contours, structured output, deterministic traces, mathematical and physical foundations, RTL, target-independent FPGA preparation, and qualification evidence.

FRP Trace Observatory contains downstream observation, parsing, validation, correlation, visualization, and audit functions.

User-interface dependencies, parser dependencies, Observatory tests, and the Observatory release lifecycle remain outside the upstream FRP repository.

## Source Authority

FRP is the sole source of truth for processor semantics.

FRP Trace Observatory must not:

- redefine an FRP state or transition;
- replace the executable semantic reference;
- reproduce internal processor execution logic;
- modify an upstream artifact;
- change a published value;
- replace a published digest;
- invent a missing field;
- infer an event that is not present in the source data;
- assign a new upstream schema identifier;
- silently reinterpret an upstream schema version.

The source bytes establish what was loaded.

Embedded identifiers and values are retained as declarations made by the artifact. They remain subject to validation against the registered upstream producer and artifact contract.

If an artifact conflicts with its registered producer contract, Observatory records the conflict. It does not repair the source or choose a replacement value.

## Audited Upstream Baseline

The initial contract was derived from the FRP v1.8.0 repository baseline.

Relevant upstream sources include:

| Upstream subject | Exact upstream path |
|---|---|
| Executable semantic reference | `frp_prototype_v1_7_0.py` |
| Structured-output and export documentation | `docs/output_schema.md` |
| Benchmark-matrix documentation | `docs/benchmark_matrix.md` |
| M15 implementation-mapping qualification | `docs/m15_implementation_mapping_domain_interface_qualification_closure.md` |
| Current validation index | `FRP_VALIDATION_INDEX_v1_8_0.md` |
| M16 qualification manifest | `docs/m16_qualification_manifest.md` |
| M16 qualification index | `docs/m16_qualification_index.md` |
| M16 public status record | `docs/m16_public_status_snapshot.md` |
| Comparative benchmark documentation | `benchmarks/architecture_comparison/README.md` |
| RTL artifact manifest | `rtl/m16/ARTIFACTS.md` |
| RTL execution transcript | `rtl/m16/SIMULATION_TRANSCRIPT.md` |
| FPGA preparation transcript | `fpga/m16/SIMULATION_TRANSCRIPT.md` |

These paths identify the audit baseline. Their presence does not automatically establish Observatory implementation support.

The audited baseline contains no formal JSON Schema documents and no machine-readable schema identifier in the `frp.m16.*` namespace.

M16 retains the qualified M15 structured-output and export-schema identities.

## Artifact Eligibility

An artifact is eligible for normalized loading only when it has an exact entry in the supported schema registry.

The registry may identify an artifact through:

1. an embedded schema identifier;
2. an embedded schema identifier and artifact kind;
3. a registered package-format identifier;
4. an exact role inside a verified deterministic package;
5. an exact upstream producer and path contract for a schema-free artifact.

A filename alone does not establish artifact identity.

An upstream path alone does not override conflicting artifact content.

An unrecognized artifact may receive a source digest and safe format diagnostics, but it must not enter a typed Observatory view.

## Supported Schema Registry

The supported schema registry is maintained separately in:

`docs/supported_schema_registry.md`

Each registry entry must record:

- exact schema or format identifier;
- artifact kind or other required discriminator;
- exact upstream repository path;
- format;
- upstream producer;
- producer version;
- producer command when published;
- upstream FRP release association;
- required fields;
- optional fields;
- allowed value domains;
- ordering rules;
- relational validation rules;
- digest rules;
- deterministic-package role;
- measurement contour;
- canonical fixture candidate;
- supported Observatory mode;
- implementation-support status.

Historical schema identifiers remain separate entries.

No schema alias, automatic upgrade, or implicit version substitution is permitted.

Artifacts that share a schema identifier but use different `kind` values must be dispatched using both values when the upstream producer defines both fields.

## Support States

The registry must distinguish between:

- discovered artifacts;
- implemented and tested artifacts;
- known but unsupported artifacts;
- historical artifacts;
- artifacts blocked by missing canonical fixtures.

Discovery is not an implementation-support claim.

An artifact becomes supported only after its registry entry, parser, validator, canonical fixture, negative fixtures, and tests are complete.

## Read-Only Loading Sequence

A conforming loader performs the following sequence:

1. capture the original source bytes;
2. record the source filename and known source path;
3. calculate a source-artifact digest without changing the bytes;
4. detect the non-executable container format;
5. identify the exact registry entry;
6. parse data using the registered parser;
7. validate required fields, types, values, ordering, relations, and digests;
8. create a separate normalized read-only representation;
9. expose only the Observatory modes permitted by the registry;
10. produce validation messages and an audit result.

A failure at one stage prevents dependent stages from being represented as successful.

The original source remains available for provenance and inspection even when validation fails.

## Provenance Record

Every loaded artifact must retain a provenance record containing:

- source filename;
- source path when known;
- schema identifier when declared;
- identified registry entry;
- producer version when declared or registered;
- source-artifact digest;
- digest algorithm;
- Observatory load timestamp;
- validation status;
- validation messages.

An absent source path remains absent.

An absent producer version is reported as not declared. It must not be copied from an unrelated artifact.

The load timestamp is Observatory metadata and is not attributed to the upstream producer.

## Data Layers

Observatory keeps source, normalized, and derived data separate.

| Layer | Content | Authority |
|---|---|---|
| Source artifact | Original loaded bytes and embedded values | Upstream artifact instance |
| Normalized representation | Read-only typed access to validated source values | Observatory representation of the source |
| Derived view | Filters, indexes, projections, correlations, and visual coordinates | Observatory-derived presentation |
| Audit report | Validation checks, results, and messages | Observatory analysis |

A normalized record must retain a link to its source artifact and source location.

A derived value must be identified as Observatory-derived.

A derived value must not overwrite, rename, or replace an upstream value.

## Source Immutability

Observatory must not rewrite source bytes during parsing, validation, normalization, filtering, or visualization.

The following operations must not be applied to the source artifact:

- field insertion;
- field deletion;
- field renaming;
- numeric replacement;
- automatic default insertion;
- array reordering;
- whitespace normalization before source-digest calculation;
- digest replacement;
- in-place schema migration.

A registered upstream default may be represented only as an explicitly labeled derived interpretation. It must not be inserted into the source record.

## Validation Layers

Artifact validation is divided into independent layers:

1. container and encoding validation;
2. artifact identity validation;
3. structural validation;
4. type validation;
5. allowed-value validation;
6. canonical ternary-domain validation;
7. trace and tick ordering validation;
8. scheduler-relation validation;
9. transition-capacity validation;
10. pending-route validation;
11. invariant-vector validation;
12. digest validation;
13. deterministic-package validation;
14. qualification-record validation.

A successful lower layer does not imply success in a higher layer.

Warnings do not convert a failed mandatory rule into a valid result.

Validation rules extracted from upstream producer code or documentation are Observatory integration rules. They must not be described as official upstream JSON Schemas unless the upstream repository publishes such schemas.

## Canonical Ternary Domain

The canonical processor domain is:

`-1, 0, 1`

State `0` is an active neutral state.

The canonical positive state is displayed as `1`.

Canonical-domain validation applies only to fields that the registered upstream contract defines as processor-state values.

Packed hardware encodings, textual vectors, and interface encodings remain separate representations. They may be mapped to canonical states only through an exact registered upstream encoding map.

## Transition Representation

The canonical opposite-polarity routes are:

`-1 → 0 → 1`

`1 → 0 → -1`

Observatory may display:

- first-leg neutralization;
- retained pending polarity;
- pending-route completion;
- scheduler deferral;
- transition-capacity deferral;
- accepted request lanes;
- rejected request lanes.

Each displayed event must be linked to a validated source record or identified as an Observatory-derived view produced by a registered deterministic rule.

Aggregate counters must not be expanded into invented per-tick events.

A missing event field is not equivalent to a zero event count.

## Trace Ordering

Source trace order is preserved exactly.

Filters select records without changing their source order.

Tick monotonicity, tick uniqueness, event ordering, and route ordering are validated according to the exact registered artifact contract.

Observatory must not silently sort an invalid trace and present the sorted result as the source sequence.

A separately sorted presentation is permitted only when it is labeled as an Observatory-derived view and the source-order validation result remains visible.

## Scheduler and Capacity Relations

Scheduler modes, scheduler states, scheduler counters, transition-capacity values, switching load, and retained state are distinct fields.

Relations between these fields are checked only when they are published by the registered upstream producer contract.

Observatory must not derive request acceptance, rejection, or deferral reasons from unrelated aggregate counters.

A relation failure is reported against the source records involved. The affected source values remain unchanged.

## Digest Handling

Observatory distinguishes between:

- the digest calculated over original loaded bytes;
- a digest declared for an entire artifact;
- a digest declared for a canonical substructure;
- a trace digest;
- a per-cell trace digest;
- a deterministic-package digest;
- individual package-file digests.

A declared digest is checked only with the exact algorithm, byte scope, serialization rule, and ordering rule defined by its registered producer contract.

A component digest must not be compared with a whole-file digest unless the upstream contract defines them as the same digest.

Whitespace, key ordering, numeric formatting, and line endings must not be normalized before a raw-byte digest is calculated.

A digest mismatch is reported. The declared and calculated values are both retained.

## Deterministic Artifact Sets

A deterministic package is valid only when its registered package requirements are satisfied.

Package validation may include:

- exact file count;
- exact filenames;
- exact byte sizes;
- exact per-file digests;
- manifest consistency;
- deterministic-package digest;
- required format identifiers;
- cross-file relations.

A package member without its own schema or format identifier may be recognized only through its exact role inside a verified registered package.

A missing package member produces an incomplete-package result.

Observatory must not reconstruct a missing file or substitute a file from another package.

## Qualification Evidence

Qualification evidence is presented with its original scope and provenance.

Observatory may display published `PASS` and `SUCCESS` values exactly as recorded by the upstream evidence.

A qualification result must remain associated with:

- its upstream release;
- its qualification contour;
- its source artifact;
- its producer or workflow when recorded;
- its run or commit identity when recorded;
- its declared artifact set;
- its recorded digest when available.

A zero-event qualification record is valid only when the zero value and its scope are explicitly present.

Invariant vectors are displayed without changing their bit order or assigning unregistered meanings to bit positions.

Human-readable M16 qualification documents are evidence records. They are not machine-readable per-tick processor traces.

Referenced CI artifacts that are absent from the loaded artifact set are reported as unavailable. They are not reconstructed from documentation.

Target-independent FPGA preparation evidence must not be presented as physical-chip evidence.

## Measurement Contours

The following contours remain separate:

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

Every registered artifact must be assigned to its upstream measurement or qualification contour.

Operation count, thermal proxy, transition pressure, `heat_peak`, scheduler timing, latency, throughput, RTL execution, FPGA preparation evidence, and physical measurements remain distinct quantities.

Identical field names in different contours do not establish identical definitions, units, or measurement methods.

Cross-contour correlation is permitted only as an explicitly labeled Observatory-derived view. It must preserve the source contour of every displayed value.

Published comparative benchmark aggregates must not be presented as processor tick traces.

## Mode Eligibility

Mode eligibility is declared per registry entry.

| Observatory mode | Eligible data |
|---|---|
| Trace Explorer | Validated processor-tick, per-cell, route-event, or cycle-exact trace records explicitly registered for this mode |
| Ternary Transition Visualizer | Validated state-transition, pending-route, scheduler, request-lane, capacity, counter, or invariant records explicitly registered for this mode |
| Artifact Auditor | Registered artifacts, deterministic packages, manifests, profiles, benchmark results, and qualification evidence |

An artifact may be used by more than one mode only when each mode is recorded in its registry entry.

Artifact Auditor may report an unsupported or unrecognized artifact, but such an artifact must not enter Trace Explorer or Ternary Transition Visualizer.

## MVP Input Boundary

The initial Trace Explorer target is limited to:

- full trace output using `frp.structured_output.v1.7.0` with the required trace collections present;
- `frp.m15.cycle_exact_reference_trace.v1.7.0`.

The initial Ternary Transition Visualizer target is limited to:

- validated structured trace records;
- validated cycle-exact trace records;
- `frp_m15_pending_routes.trace` inside a complete verified M15 deterministic vector package;
- event counters and invariant records explicitly present in a supported artifact.

The initial Artifact Auditor target includes:

- the twelve FRP v1.8.0 release-facing structured-output, benchmark-matrix, and inherited M15 export schemas;
- the M15 deterministic vector package;
- committed comparative benchmark profiles and result packages;
- registered M16 qualification manifests, indexes, transcripts, and artifact records.

The schema-free committed workload profile must not receive an invented schema identifier. It may be recognized only through an explicit registry contract.

CSV parsing remains outside the MVP until a canonical upstream CSV artifact and its producer contract are available.

M16 per-tick request-lane, transition-capacity, and deferral views remain outside the MVP because the audited upstream baseline does not contain a committed machine-readable M16 trace carrying those records.

## Safe Processing Boundary

Uploaded artifacts are treated as untrusted data.

Loading an artifact must not:

- execute Python or another script;
- execute a shell command;
- evaluate an embedded expression;
- compile or simulate SystemVerilog;
- invoke a producer command;
- load executable modules from the artifact;
- follow a path outside the controlled artifact boundary;
- automatically fetch referenced external resources.

SystemVerilog files may be recorded as opaque manifest members and checked for identity, size, or digest when a registered manifest requires those checks. They are not executed.

If archive support is added later, extraction must reject path traversal, unsafe symbolic links, and writes outside the controlled extraction boundary.

Resource limits must be applied to artifact size, nesting depth, record count, and decompression before unrestricted parsing is permitted.

Artifact strings rendered in a user interface must remain data and must not become executable markup.

## Audit Reports

Artifact Auditor produces:

- a machine-readable audit report;
- a user-facing audit report.

Both reports must originate from the same validation results.

An audit report must identify:

- source provenance;
- detected format;
- declared schema identifier;
- matched registry entry;
- producer association;
- executed validation checks;
- passed checks;
- failed checks;
- warnings;
- declared digests;
- calculated digests;
- missing package members;
- overall validation status;
- Observatory version when assigned.

An audit report is an Observatory-derived artifact. It is not an upstream FRP qualification record.

## Validation Outcomes

The normalized data model must distinguish at least:

- recognized and valid;
- recognized with warnings;
- recognized but invalid;
- known but unsupported;
- unrecognized;
- incomplete package.

Unsupported does not mean that the upstream artifact is semantically invalid. It means that the current Observatory version does not implement its integration contract.

Invalid does not authorize source modification.

Uncertainty is reported explicitly and is not replaced with an inferred value.

## Support Acceptance Criteria

A format may be declared supported only when all of the following are present:

1. an exact registry entry;
2. an identified upstream producer and version;
3. required and optional field definitions;
4. value-domain and relation rules;
5. a read-only parser;
6. a validator;
7. at least one canonical fixture;
8. negative fixtures for mandatory failures;
9. parser and validator tests;
10. provenance preservation tests;
11. source-immutability tests;
12. declared Observatory mode eligibility.

Qualification support additionally requires tests for the applicable manifest, digest, deterministic-set, zero-event, and invariant rules.

## Versioning and Change Control

FRP Trace Observatory has an independent version lifecycle.

An Observatory version must not automatically match an FRP release version.

Supported FRP releases, schema identifiers, format identifiers, producer versions, and artifact kinds are recorded explicitly in the supported schema registry.

A new upstream release does not become supported automatically.

A compatibility change requires:

- an audited upstream source;
- a registry update;
- fixture review;
- parser and validator review;
- relevant tests;
- documentation review.

Release claims require corresponding test and workflow evidence.

Changes to the upstream FRP repository are outside this contract and require a separate explicit action.

## Non-Goals

This integration contract does not authorize:

- execution of FRP processor semantics by Observatory;
- modification of published FRP artifacts;
- generation of replacement FRP artifacts;
- creation of new FRP schema identifiers;
- automatic migration between FRP schema versions;
- AI inference or training functions;
- autonomous agent functions;
- new processor execution claims;
- new physical implementation claims.

## Author

Maksym Marnov
