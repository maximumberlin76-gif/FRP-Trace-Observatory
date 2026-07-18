# FRP Trace Observatory

FRP Trace Observatory is a standalone downstream project for observing, validating, and visualizing artifacts published by the Fractal Resonance Processor project.

It is maintained outside the main FRP repository so that user-interface dependencies, artifact parsers, and the Observatory release lifecycle remain outside the qualified FRP boundary.

## Integration Boundary

The integration direction is strictly one-way:

**Fractal-Resonance-Processor → published artifacts → FRP-Trace-Observatory**

Published artifacts may include JSON, CSV, traces, schemas, manifests, deterministic vectors, and qualification records.

FRP remains the sole source of truth for processor semantics.

FRP Trace Observatory does not:

- replace the executable semantic reference;
- reproduce internal processor logic;
- introduce independent processor semantics;
- modify published FRP artifacts;
- change published metric values;
- combine unrelated benchmark contours.

## Planned Modes

### Trace Explorer

Trace Explorer will provide read-only inspection of supported FRP trace artifacts, including tick sequences, scheduler state, retained ternary state, pending routes, state changes, and published telemetry.

### Ternary Transition Visualizer

Ternary Transition Visualizer will present transitions in the canonical processor domain:

`-1, 0, 1`

State `0` is an active neutral state.

The visualizer will present supported neutralization, pending-route, scheduler, transition-capacity, request-lane, event-counter, and invariant records without inferring events that are absent from the source artifact.

### Artifact Auditor

Artifact Auditor will identify and validate supported artifact formats, schema identifiers, required fields, value domains, ordering relations, declared digests, deterministic artifact sets, and qualification records.

Uploaded artifacts are treated as data. Artifact Auditor will not execute arbitrary code, SystemVerilog, producer commands, or executable content contained in an artifact.

## Artifact Integrity

Original artifact bytes remain unchanged.

Each loaded artifact retains provenance information, including its source filename, known source path, schema identifier, producer version, artifact digest, load timestamp, validation status, and validation messages.

Normalized internal records are stored separately from source bytes.

Calculated presentations are identified as Observatory-derived views and do not replace published FRP values.

## Measurement Boundaries

Operation count, thermal proxy, transition pressure, heat, scheduler timing, latency, throughput, RTL execution, FPGA preparation evidence, and physical measurements remain separate measurement fields and qualification contours.

Target-independent FPGA preparation evidence is not presented as physical-chip evidence.

## Project Status

The project is currently in the repository-definition stage.

Implementation will begin with an integration contract and an explicit supported-schema registry derived from published FRP artifacts.

No user-interface framework, implementation support, qualification status, or release version is declared at this stage.

## Versioning

FRP Trace Observatory has an independent version lifecycle.

Its version does not automatically match an FRP release version. Supported FRP releases and schema identifiers will be recorded explicitly in the compatibility registry.

## Out of Scope

The following are outside the scope of FRP Trace Observatory:

- AI inference engines;
- training pipelines;
- autonomous agent logic;
- changes to FRP processor semantics;
- new FRP execution claims.

## Author

Maksym Marnov
