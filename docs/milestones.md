# FRP Trace Observatory Milestone History

- **Implementation status:** Complete through Observatory M22
- **Qualified upstream boundary:** FRP M31
- **Retained publication chain:** Observatory M1–M22
- **Terminal M30 qualification:** Observatory M8B
- **Terminal M31 qualification:** Observatory M22
- **Current complete verification:** 655 tests, `OK`

Related documents:

- [Usage](usage.md)
- [Reproducibility Contract](reproducibility.md)
- [CI and Manual Qualification Workflows](ci.md)
- [Integration Contract](integration_contract.md)
- [Normalized Data Model](normalized_data_model.md)
- [Supported Schema Registry](supported_schema_registry.md)
- [M31 Published Evidence Boundary](m31_published_boundary.md)

## Purpose

This document records the completed implementation history of FRP Trace
Observatory. It identifies every retained milestone, the exact workflow that
installed or qualified it, the boundary established by that stage, and the
terminal acceptance results for the M30 and M31 publication chains.

The history is append-only. Later stages qualify composed behavior while the
source, tests, workflows, evidence identities, and successful run history of
earlier stages remain independently addressable.

## Numbering Domains

Two milestone domains appear in this repository and have different meanings.

| Domain | Range used here | Meaning |
|---|---|---|
| FRP upstream | M16, M28–M31 | Processor, evidence, integration, and publication milestones produced by the FRP repository |
| FRP Trace Observatory | M1–M22 | Ordered intake, registry, dispatch, audit, trace, visualization, and qualification stages in this repository |

An Observatory number does not rename an FRP upstream milestone. For example,
Observatory M16 installs the M31 Artifact Auditor source; it is distinct from
the upstream FRP M16 RTL and FPGA-preparation evidence retained inside the
M30 and M31 provenance chains.

## Completion Definition

An Observatory milestone is complete when its declared boundary is present
and all applicable gates have passed:

1. the exact predecessor boundary is verified;
2. the required upstream input is resolved read-only;
3. source identity, path, length, digest, and cardinality checks pass;
4. only the milestone's declared files are installed or qualified;
5. Python source compiles under Python 3.12;
6. focused milestone tests pass;
7. the complete available repository regression passes;
8. upstream and unrelated Observatory content remain unchanged;
9. the milestone summary is published by its manual workflow;
10. the workflow and its result remain in repository history.

Publication stages add their declared files before qualification. Read-only
qualification stages validate an already published boundary without rewriting
its source evidence.

## Completed M30 Chain

The M30 chain begins with the immutable FRP v3.2.0 archival package and ends
with the qualified full-core Ternary Transition Visualizer dataset.

### M1 — Immutable M30 Archive Intake

Workflow:

[`frp-observatory-m1-m30-archive-intake-workflow.yml`](../.github/workflows/frp-observatory-m1-m30-archive-intake-workflow.yml)

Completed boundary:

- exact immutable M30 archive intake;
- archive path and package identity enforcement;
- 10,189,989-byte package;
- 519 archive entries;
- 518 manifested source members;
- archive SHA-256
  `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa`.

### M2 — Published-Boundary Intake

Workflow:

[`frp-observatory-m2-published-boundary-intake-workflow.yml`](../.github/workflows/frp-observatory-m2-published-boundary-intake-workflow.yml)

Completed boundary:

- exact M28–M30 published-boundary intake;
- archive-member resolution without source mutation;
- preservation of publication metadata and member identity.

### M3 — Published Registry and Routing

Workflow:

[`frp-observatory-m3-published-registry-routing-workflow.yml`](../.github/workflows/frp-observatory-m3-published-registry-routing-workflow.yml)

Completed boundary:

- four exact M30 published-member registrations;
- seven exact member-to-mode routes;
- identity, role, routing, and mutation-failure tests.

### M4 — Published-Member Intake

Workflow:

[`frp-observatory-m4-published-member-intake-workflow.yml`](../.github/workflows/frp-observatory-m4-published-member-intake-workflow.yml)

Completed boundary:

- strict read-only intake of all four registered M30 members;
- exact source-byte retention;
- shared member identity for downstream consumers.

### M5 — Published Dispatch Boundary

Workflow:

[`frp-observatory-m5-published-dispatch-boundary-workflow.yml`](../.github/workflows/frp-observatory-m5-published-dispatch-boundary-workflow.yml)

Completed boundary:

- seven immutable member-to-mode dispatch envelopes;
- exact consumer eligibility;
- deterministic dispatch identity;
- rejection of unregistered or ineligible routes.

### M6 — Published Artifact Auditor

Workflow:

[`frp-observatory-m6-published-artifact-auditor-workflow.yml`](../.github/workflows/frp-observatory-m6-published-artifact-auditor-workflow.yml)

Completed boundary:

- four immutable M30 audit reports;
- 69 ordered validation checks;
- zero failed checks;
- audit batch SHA-256
  `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03`.

### M7A — Published Trace Explorer Source

Workflow:

[`frp-observatory-m7a-published-trace-explorer-source-workflow.yml`](../.github/workflows/frp-observatory-m7a-published-trace-explorer-source-workflow.yml)

Completed boundary:

- exact M30-published M16 Trace Explorer source;
- binding to the M5 dispatch route and M6 audited member;
- deterministic read-only trace projection.

### M7B — Published Trace Explorer Qualification

Workflow:

[`frp-observatory-m7b-published-trace-explorer-qualification-workflow.yml`](../.github/workflows/frp-observatory-m7b-published-trace-explorer-qualification-workflow.yml)

Completed boundary:

- four ordered trace records;
- 32 cell snapshots;
- eight request records;
- observed processor state domain `-1/0/1`;
- trace dataset SHA-256
  `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd`.

### M8A1 — Full-Core Visualizer Payload Segment 1

Workflow:

[`frp-observatory-m8a-full-core-transition-visualizer-source-workflow.yml`](../.github/workflows/frp-observatory-m8a-full-core-transition-visualizer-source-workflow.yml)

Completed boundary:

- first integrity-bound segment of the exact full-core visualizer source;
- deterministic staged-payload identity;
- preservation of the established M1–M7B boundary.

### M8A2 — Full-Core Visualizer Payload Segment 2

Workflow:

[`frp-observatory-m8a2-full-core-transition-visualizer-source-workflow.yml`](../.github/workflows/frp-observatory-m8a2-full-core-transition-visualizer-source-workflow.yml)

Completed boundary:

- second integrity-bound source segment;
- ordered continuation of the staged payload;
- exact predecessor-segment verification.

### M8A3 — Full-Core Visualizer Assembly

Workflow:

[`frp-observatory-m8a3-full-core-transition-visualizer-source-workflow.yml`](../.github/workflows/frp-observatory-m8a3-full-core-transition-visualizer-source-workflow.yml)

Completed boundary:

- exact source reconstruction from the staged segments;
- assembled-source digest and compilation verification;
- removal of only the temporary transport segments after successful assembly.

The completed source remains part of the repository. Removal of temporary
transport segments does not remove historical evidence, benchmarks, workflow
definitions, or qualified output identities.

### M8B — Full-Core Visualizer Qualification

Workflow:

[`frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml`](../.github/workflows/frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml)

Completed boundary:

- two exact published trace contours;
- 100 ordered trace records;
- 800 source-linked transition frames;
- visualizer dataset identifier
  `68de3476-2e03-5506-93ea-062c3744e90d`;
- visualizer dataset SHA-256
  `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b`.

M8B is the terminal M30 Observatory qualification. It composes M1–M8A3
without replacing their independently retained boundaries.

## Completed M31 Chain

The M31 chain qualifies four exact upstream publication documents and builds
the Observatory registry, dispatch, auditor, trace, visualization, and
end-to-end verification layers over that immutable boundary.

### M9 — M31 Published-Boundary Intake Qualification

Workflow:

[`frp-observatory-m9-m31-published-boundary-intake-workflow.yml`](../.github/workflows/frp-observatory-m9-m31-published-boundary-intake-workflow.yml)

Completed boundary:

- read-only qualification of four exact M31 publication documents;
- verification of 12 provenance sources;
- reverification of ten historical members from the immutable M30 archive;
- clean-state verification for both repositories.

M9 is a qualification gate and does not publish source files.

### M10 — M31 Published-Boundary Source

Workflow:

[`frp-observatory-m10-m31-published-boundary-source-workflow.yml`](../.github/workflows/frp-observatory-m10-m31-published-boundary-source-workflow.yml)

Completed boundary:

- integrity-bound M31 publication-intake source;
- exact document-path, role, length, and raw-digest handling;
- read-only upstream document resolution.

### M11 — M31 Published-Boundary Tests

Workflow:

[`frp-observatory-m11-m31-published-boundary-tests-workflow.yml`](../.github/workflows/frp-observatory-m11-m31-published-boundary-tests-workflow.yml)

Completed boundary:

- canonical four-document intake qualification;
- identity, cardinality, provenance, mutation, and source-preservation tests;
- rejection of incomplete or altered publication boundaries.

### M12 — M31 Published Registry Source

Workflow:

[`frp-observatory-m12-m31-published-registry-source-workflow.yml`](../.github/workflows/frp-observatory-m12-m31-published-registry-source-workflow.yml)

Completed boundary:

- exact four-document M31 registry;
- separate formal-schema, evidence, manifest, and qualification roles;
- six declared document-to-mode routes.

### M13 — M31 Published Registry Tests

Workflow:

[`frp-observatory-m13-m31-published-registry-tests-workflow.yml`](../.github/workflows/frp-observatory-m13-m31-published-registry-tests-workflow.yml)

Completed boundary:

- registry identity and role qualification;
- exact route-matrix qualification;
- mandatory failure coverage for altered identities, roles, and routes.

### M14 — M31 Published Dispatch Source

Workflow:

[`frp-observatory-m14-m31-published-dispatch-source-workflow.yml`](../.github/workflows/frp-observatory-m14-m31-published-dispatch-source-workflow.yml)

Completed boundary:

- exact document-to-mode dispatch source;
- immutable dispatch envelopes derived from registered documents;
- consumer-specific routing without document reinterpretation.

### M15 — M31 Published Dispatch Tests

Workflow:

[`frp-observatory-m15-m31-published-dispatch-tests-workflow.yml`](../.github/workflows/frp-observatory-m15-m31-published-dispatch-tests-workflow.yml)

Completed boundary:

- all six declared routes qualified;
- route-order and deterministic-identity verification;
- rejection of undeclared roles, consumers, and route mutations.

### M16 — M31 Published Artifact Auditor Source

Workflow:

[`frp-observatory-m16-m31-published-auditor-source-workflow.yml`](../.github/workflows/frp-observatory-m16-m31-published-auditor-source-workflow.yml)

Completed boundary:

- four-report M31 Artifact Auditor source;
- exact role-specific validation;
- immutable ordered check records;
- deterministic aggregate audit identity.

### M17 — M31 Published Artifact Auditor Tests

Workflow:

[`frp-observatory-m17-m31-published-auditor-tests-workflow.yml`](../.github/workflows/frp-observatory-m17-m31-published-auditor-tests-workflow.yml)

Completed boundary:

- four immutable audit reports;
- 47 ordered validation checks;
- zero failed checks;
- audit batch SHA-256
  `3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591`.

### M18 — M31 Published Trace Explorer Source

Workflow:

[`frp-observatory-m18-m31-published-trace-explorer-source-workflow.yml`](../.github/workflows/frp-observatory-m18-m31-published-trace-explorer-source-workflow.yml)

Completed boundary:

- two-contour M31 Trace Explorer source;
- source-linked records, cell snapshots, requests, and invariant results;
- separate scheduler modes `free`, `1/7`, and `7/1`;
- formal processor-state domain `-1/0/1`.

State `0` is retained as an active neutral mediation state in the published
processor model. The trace layer records it as processor state and does not
reinterpret it as missing, idle, false, or absent data.

### M19 — M31 Published Trace Explorer Tests

Workflow:

[`frp-observatory-m19-m31-published-trace-explorer-tests-workflow.yml`](../.github/workflows/frp-observatory-m19-m31-published-trace-explorer-tests-workflow.yml)

Completed boundary:

- two source contours;
- 100 ordered trace records;
- 800 source-linked cell snapshots;
- 200 request records;
- 100 invariant-pass records;
- 702 retained observations of state `0`;
- scheduler-mode totals `free = 19`, `7/1 = 64`, and `1/7 = 17`;
- trace dataset identifier
  `0f0f0f7e-0409-5e7b-8c76-2f72bb954321`;
- trace dataset SHA-256
  `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff`.

### M20 — M31 Published Transition Visualizer Source

Workflow:

[`frp-observatory-m20-m31-published-transition-visualizer-source-workflow.yml`](../.github/workflows/frp-observatory-m20-m31-published-transition-visualizer-source-workflow.yml)

Completed boundary:

- exact M31 Ternary Transition Visualizer source;
- source-linked transition-frame generation;
- classification of neutral mediation and retained-state transitions;
- separate handling of the four published thermal evidence contours.

### M21 — M31 Published Transition Visualizer Tests

Workflow:

[`frp-observatory-m21-m31-published-transition-visualizer-tests-workflow.yml`](../.github/workflows/frp-observatory-m21-m31-published-transition-visualizer-tests-workflow.yml)

Completed boundary:

- 800 source-linked transition frames;
- 12 `active_zero_to_polarity` transitions;
- five `polarity_to_active_zero` transitions;
- 783 `retained_same` transitions;
- zero `direct_opposite` transitions;
- 790 non-route frames;
- five first route legs to state `0`;
- five pending route completions;
- visualizer dataset identifier
  `63a1feb9-1835-579e-ab00-eec4569e8ff3`;
- visualizer dataset SHA-256
  `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304`.

### M22 — Complete M31 End-to-End Qualification

Workflow:

[`frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml`](../.github/workflows/frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml)

Completed boundary:

- complete publication-intake-to-visualization chain;
- four registered documents and six exact routes;
- four audit reports and 47 passing checks;
- two trace contours and 100 trace records;
- 800 source-linked transition frames;
- four separately retained thermal evidence contours;
- deterministic audit, dispatch, trace, core, contour, frame, and visualizer
  identities;
- 26 focused end-to-end tests, `OK`;
- 655 complete repository tests with both exact upstream inputs configured,
  `OK`.

M22 is the terminal completed Observatory stage for the FRP M31 publication
boundary. It verifies the composed system while preserving M9–M21 as the
ordered implementation and qualification chain.

## Terminal Acceptance Ledger

| Boundary | Terminal stage | Principal result | Deterministic identity |
|---|---|---|---|
| M30 archive | M1 | 10,189,989 bytes, 519 entries, 518 members | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |
| M30 audit | M6 | 4 reports, 69 checks, 0 failures | `aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03` |
| M30 trace | M7B | 4 records, 32 snapshots, 8 requests | `4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd` |
| M30 visualizer | M8B | 100 records, 800 frames | `7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b` |
| M31 audit | M17 | 4 reports, 47 checks, 0 failures | `3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591` |
| M31 trace | M19 | 2 contours, 100 records, 800 snapshots | `ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff` |
| M31 visualizer | M21 | 800 frames, 0 direct-opposite transitions | `0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304` |
| M31 end-to-end | M22 | 26 focused tests and 655 complete tests | All constituent identities reverified |

## Thermal Evidence Retention

M20–M22 retain four distinct M31 thermal evidence contours:

| Contour | Evidence group | Physical-temperature measurement |
|---|---|---:|
| `historical_release_benchmark` | historical | false |
| `current_comparative_baseline` | current | false |
| `current_hardware_sensitivity` | current | false |
| `current_thermal_profile` | current | false |

These contours remain separate because they have different provenance and
measurement meaning. The historical benchmark record, current comparative
baseline, hardware-sensitivity contour, and thermal-profile contour are not
merged into one physical claim.

## Preserved History Boundary

Completion through M22 preserves:

- all 26 manually dispatched milestone workflows;
- the routine repository CI workflow;
- the M1–M22 ordering and predecessor gates;
- the split M7 source and qualification stages;
- the split M8 payload, assembly, and qualification stages;
- exact M30 archive, audit, trace, and visualizer identities;
- exact M31 publication, audit, trace, and visualizer identities;
- all historical evidence and benchmark contours;
- focused and complete test suites;
- successful and failed GitHub Actions run history;
- source-linked record, contour, and frame identities.

A later document, test, or qualification may reference an earlier result. It
does not replace that result or collapse distinct historical and current
measurement contours.

## Manual Qualification Entry Points

Milestone workflows are run manually from GitHub Actions on branch `main`.
A commit does not itself execute a milestone workflow.

Terminal M30 workflow:

```
.github/workflows/frp-observatory-m8b-full-core-transition-visualizer-qualification-workflow.yml
```

Terminal M31 workflow:

```
.github/workflows/frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml
```

Complete local verification with both exact upstream inputs configured:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified result:

```
Ran 655 tests

OK
```

Detailed setup, identity verification, and execution commands are defined in
[Reproducibility Contract](reproducibility.md). Workflow permissions and
manual execution rules are defined in
[CI and Manual Qualification Workflows](ci.md).

## Current Closure

The completed Observatory history establishes two terminal qualified
boundaries:

1. M8B closes the immutable M30 intake-to-visualization chain.
2. M22 closes the exact M31 publication-to-visualization chain.

Both closures retain their complete predecessor histories. This document
records implemented repository state and makes no unimplemented milestone a
condition of the current M31 qualification.

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
