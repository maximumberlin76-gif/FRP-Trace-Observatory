# Changelog

All notable completed changes to FRP Trace Observatory are recorded in this
file.

- **Current implementation boundary:** Observatory M22
- **Current qualified upstream boundary:** FRP M31
- **Terminal M30 qualification:** Observatory M8B
- **Terminal M31 qualification:** Observatory M22
- **Current complete verification:** 655 tests, `OK`
- **Canonical repository:** [FRP Trace Observatory](https://github.com/maximumberlin76-gif/FRP-Trace-Observatory)

This changelog records completed repository state by qualification boundary.
Exact file history and commit ordering remain available in the Git history.
Exact implementation-stage ordering is recorded in
[docs/milestones.md](docs/milestones.md).

## Observatory M22 — Complete FRP M31 Boundary

Status: **completed and qualified**

Observatory M22 closes the exact FRP M31 publication-to-visualization chain.
It composes the M9–M21 boundaries while retaining every earlier workflow,
test, evidence identity, benchmark contour, and source-provenance relation.

### Added — M31 Published-Boundary Intake

- Added exact read-only intake for four M31 publication documents:
  formal schema, evidence, manifest, and qualification.
- Added exact path, role, kind, identity-field, identity-value, byte-length,
  and raw SHA-256 validation.
- Added validation for 12 exact provenance sources.
- Added reverification of ten historical members from the immutable M30
  archive.
- Added clean-repository and source-preservation checks.

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M9 | Read-only qualification of the exact M31 published boundary |
| M10 | Integrity-bound M31 publication-intake source |
| M11 | M31 publication-intake qualification tests |

### Added — M31 Registry and Dispatch

- Added a four-document immutable M31 publication registry.
- Added distinct formal-schema, evidence, manifest, and qualification roles.
- Added six exact document-to-mode routes.
- Added immutable dispatch envelopes with deterministic identities.
- Added rejection coverage for altered document identities, roles, paths,
  route order, consumers, and undeclared dispatches.

Qualified route matrix:

| Published role | Artifact Auditor | Trace Explorer | Ternary Transition Visualizer |
|---|---:|---:|---:|
| Formal schema | 1 | 0 | 0 |
| Evidence | 1 | 1 | 1 |
| Manifest | 1 | 0 | 0 |
| Qualification | 1 | 0 | 0 |
| **Total** | **4** | **1** | **1** |

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M12 | Exact M31 published-document registry source |
| M13 | M31 registry and route qualification tests |
| M14 | Exact M31 document-to-mode dispatch source |
| M15 | M31 dispatch qualification tests |

### Added — M31 Artifact Auditor

- Added four immutable role-specific audit reports.
- Added 47 ordered validation checks.
- Qualified all 47 checks with zero failures.
- Added deterministic per-report and aggregate batch identities.

Qualified aggregate:

```
published_documents=4
audit_reports=4
validation_checks=47
failed_checks=0
batch_sha256=3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591
```

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M16 | M31 published Artifact Auditor source |
| M17 | M31 Artifact Auditor qualification tests |

### Added — M31 Trace Explorer

- Added a deterministic two-contour M31 trace projection.
- Added 100 ordered source-linked trace records.
- Added 800 source-linked cell snapshots.
- Added 200 request records and 100 invariant-pass records.
- Retained 702 observations of processor state `0`.
- Preserved the formal processor-state domain `-1/0/1`.
- Preserved separate scheduler modes `free`, `1/7`, and `7/1`.
- Bound every record to its source contour, source coordinates, dispatch,
  registry entry, and audit result.

Qualified scheduler-mode totals:

| Scheduler mode | Records |
|---|---:|
| `free` | 19 |
| `7/1` | 64 |
| `1/7` | 17 |
| **Total** | **100** |

Deterministic identities:

```
trace_dataset_id=0f0f0f7e-0409-5e7b-8c76-2f72bb954321
trace_dispatch_sha256=f34b867fabcaab51515ecca39f2eb7287f52aa218d3ac48596a1481326009630
dataset_sha256=ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff
```

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M18 | M31 published Trace Explorer source |
| M19 | M31 Trace Explorer qualification tests |

### Added — M31 Ternary Transition Visualizer

- Added 800 source-linked transition frames.
- Added formal transition classification over the `-1/0/1` state domain.
- Added explicit active-neutral mediation through processor state `0`.
- Added route-leg attribution backed by source request and route evidence.
- Added deterministic core, contour, frame, dispatch, and dataset identities.

Qualified transition totals:

| Transition classification | Frames |
|---|---:|
| `active_zero_to_polarity` | 12 |
| `polarity_to_active_zero` | 5 |
| `retained_same` | 783 |
| `direct_opposite` | 0 |
| **Total** | **800** |

Qualified route-leg totals:

| Route leg | Frames |
|---|---:|
| `non_route_transition` | 790 |
| `first_leg_to_active_zero` | 5 |
| `pending_route_completion` | 5 |
| **Total** | **800** |

Deterministic identities:

```
visualizer_dataset_id=63a1feb9-1835-579e-ab00-eec4569e8ff3
visualizer_dispatch_sha256=ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8
dataset_sha256=0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304
```

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M20 | M31 published Ternary Transition Visualizer source |
| M21 | M31 Transition Visualizer qualification tests |

### Added — M31 Thermal Evidence Separation

- Added four separately identified published evidence contours.
- Retained historical and current evidence as non-interchangeable records.
- Retained each contour's own group, measurement declaration, source path,
  and SHA-256.
- Recorded all four contours as proxy or benchmark evidence rather than
  physical-temperature measurements.

| Contour | Group | Physical temperature | Contour SHA-256 |
|---|---|---|---|
| `historical_release_benchmark` | historical | false | `8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140` |
| `current_comparative_baseline` | current | false | `c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add` |
| `current_hardware_sensitivity` | current | false | `9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0` |
| `current_thermal_profile` | current | false | `1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee` |

The historical benchmark retains its exact source-linked values:

```
binary_heat_peak=0.051000
active_neutral_ternary_heat_peak=0.003250
heat_peak_ratio_binary_over_active_neutral_ternary=15.6923076923
heat_peak_relative_reduction_percent=93.63
winner_assertions=[]
```

### Added — M31 End-to-End Qualification

- Added a terminal 26-test M31 end-to-end suite.
- Added complete verification from publication intake through visualization.
- Added repeated deterministic-identity checks across all M31 consumers.
- Added complete source and repository preservation checks.
- Qualified 26 focused M31 end-to-end tests with `OK`.
- Qualified 655 complete repository tests with both exact upstream inputs
  configured, with `OK`.

Completed Observatory stage:

| Stage | Completed change |
|---|---|
| M22 | Complete M31 Observatory end-to-end qualification |

## Observatory M8B — Complete FRP M30 Boundary

Status: **completed, qualified, and retained**

Observatory M8B closes the immutable M30 archive-to-visualization chain. Its
implementation and evidence remain part of the current repository alongside
the later M31 boundary.

### Added — Immutable M30 Intake

- Added exact intake for the FRP v3.2.0 M30 archival package.
- Bound the archive to a length of 10,189,989 bytes.
- Verified 519 archive entries and 518 manifested source members.
- Added exact M28–M30 published-boundary intake.
- Added strict read-only access to four registered published members.

Archive identity:

```
sha256=05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa
```

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M1 | Immutable M30 archive intake |
| M2 | M28–M30 published-boundary intake |
| M3 | Four-member M30 registry and seven exact routes |
| M4 | Strict read-only intake of four M30 members |
| M5 | Seven immutable member-to-mode dispatch envelopes |

### Added — M30 Artifact Auditor

- Added four immutable M30 audit reports.
- Added 69 ordered validation checks.
- Qualified all 69 checks with zero failures.

Deterministic aggregate:

```
published_members=4
audit_reports=4
validation_checks=69
failed_checks=0
batch_sha256=aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03
```

Completed Observatory stage:

| Stage | Completed change |
|---|---|
| M6 | M30 published Artifact Auditor source and qualification |

### Added — M30 Trace Explorer

- Added exact M30-published M16 Trace Explorer source.
- Added four ordered trace records.
- Added 32 source-linked cell snapshots and eight request records.
- Preserved observed state domain `-1/0/1`.
- Added deterministic projection and repeated-projection verification.

Trace identity:

```
dataset_sha256=4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd
```

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M7A | M30 published Trace Explorer source |
| M7B | M30 published Trace Explorer qualification |

### Added — M30 Full-Core Transition Visualizer

- Added the full-core visualizer source through three integrity-bound payload
  and assembly stages.
- Added exact assembly verification before removal of temporary transport
  segments.
- Added two exact published trace contours.
- Added 100 ordered trace records and 800 transition frames.
- Added deterministic full-core visualizer qualification.

Visualizer identity:

```
visualizer_dataset_id=68de3476-2e03-5506-93ea-062c3744e90d
dataset_sha256=7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b
```

Completed Observatory stages:

| Stage | Completed change |
|---|---|
| M8A1 | Full-core visualizer payload segment 1 |
| M8A2 | Full-core visualizer payload segment 2 |
| M8A3 | Exact full-core source assembly |
| M8B | Full-core Transition Visualizer qualification |

## Foundational Observatory Implementation

Status: **implemented and retained**

The foundational implementation established the repository-wide contracts
used by the M30 and M31 publication chains.

### Added — Schema Registry

- Added executable support-state records.
- Added exact schema identifiers and compatibility keys.
- Added required, optional, order, value, relation, and digest rules.
- Added parser and validator bindings.
- Added base, M30, and M31 registry layers.
- Added explicit supported, partial, and unsupported classifications.

### Added — Artifact Auditor

- Added immutable validation checks and audit reports.
- Added deterministic report serialization.
- Added explicit source, registry, dispatch, and validation identities.
- Added ordered success and failure evidence.

### Added — Trace Explorer

- Added immutable trace, cell, request, lane, and source-coordinate models.
- Added exact source-order preservation.
- Added deterministic trace builders and serializers.
- Added M15, M16, M30, and M31 source-linked trace contours.

### Added — Ternary Transition Visualizer

- Added immutable transition, scheduler, request-route, telemetry, invariant,
  and view models.
- Added source-backed and explicitly Observatory-derived record classes.
- Added deterministic transition datasets and derived views.
- Added separate execution, semantic, proxy, benchmark, and physical
  measurement contours.

### Added — Test and CI Boundaries

- Added unit, identity, immutability, mutation-failure, routing, integration,
  deterministic-output, and end-to-end tests.
- Added routine repository CI for push, pull request, and manual dispatch.
- Added 26 retained manually dispatched milestone workflows.
- Standardized qualification on Python 3.12.
- Enforced read-only upstream checkout and minimum workflow permissions.
- Preserved active milestone runs with `cancel-in-progress: false`.

## Documentation Closure Through M31

Status: **completed for the current M31 repository boundary**

### Added

- Added the exact [integration contract](docs/integration_contract.md).
- Added the complete [normalized data model](docs/normalized_data_model.md).
- Added the executable [supported schema registry](docs/supported_schema_registry.md).
- Added the exact [M31 published evidence boundary](docs/m31_published_boundary.md).
- Added the complete [usage guide](docs/usage.md).
- Added the [reproducibility contract](docs/reproducibility.md).
- Added [CI and manual qualification documentation](docs/ci.md).
- Added the completed [Observatory milestone history](docs/milestones.md).
- Added the project [attribution and provenance notice](NOTICE.md).
- Added this completed-boundary changelog.

### Standardized

- Standardized the processor-state notation as `-1/0/1`.
- Standardized Python qualification on version 3.12.
- Standardized the author identity as `Maksym Marnov (Alchimist)`.
- Standardized the project location as `Berlin, Germany`.
- Standardized source, normalized, and Observatory-derived provenance labels.
- Standardized manual milestone execution from GitHub Actions on branch
  `main`.

## Preserved Historical Boundaries

The current implementation retains:

- the complete foundational compatibility registry;
- all M1–M22 Observatory workflows;
- M30 archive, registry, dispatch, audit, trace, and visualizer identities;
- M31 publication, registry, dispatch, audit, trace, and visualizer identities;
- historical evidence and benchmark records;
- current comparative and sensitivity records;
- all four separately classified M31 thermal evidence contours;
- source-linked normalized and derived representations;
- focused and complete qualification suites;
- successful and failed GitHub Actions run history.

Later qualification stages compose these boundaries and do not replace their
source evidence, deterministic identities, tests, workflows, or historical
records.

## Current Acceptance Identities

| Boundary | SHA-256 |
|---|---|
| M30 archive | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |
| M30 audit batch | `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03` |
| M30 trace dataset | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |
| M30 visualizer dataset | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |
| M31 audit batch | `3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591` |
| M31 trace dataset | `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff` |
| M31 visualizer dataset | `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304` |

## Current Qualification Result

With the exact M30 archive and clean M31 upstream repository configured:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

The exact reproduction procedure is defined in
[docs/reproducibility.md](docs/reproducibility.md). Manual workflow operation
and failure interpretation are defined in [docs/ci.md](docs/ci.md).

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
