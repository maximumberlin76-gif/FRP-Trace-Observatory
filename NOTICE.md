# Notice

## Project

**FRP Trace Observatory**  
Read-only observability, validation, trace exploration, and transition
visualization for published Fractal Resonance Processor artifacts.

Copyright Maksym Marnov (Alchimist)  
Berlin, Germany

## License

FRP Trace Observatory is made available under the Apache License, Version
2.0. The complete license text is provided in [LICENSE](LICENSE).

This notice is provided for attribution and provenance. It does not alter,
extend, or replace the terms of the Apache License, Version 2.0.

## Project Attribution

FRP Trace Observatory was designed and authored by:

**Maksym Marnov (Alchimist)**  
Berlin, Germany

The Observatory implements deterministic, read-only tooling for:

- exact published-artifact intake;
- schema and publication registry validation;
- artifact-to-consumer dispatch;
- immutable audit reports;
- source-linked trace exploration;
- ternary transition visualization;
- reproducible qualification of FRP M30 and M31 publication boundaries.

## Upstream FRP Relationship

The Observatory consumes published material from the upstream repository:

[Fractal Resonance Processor — Ternary Resonant Coherence Processor](https://github.com/maximumberlin76-gif/Fractal-Resonance-Processor-FRP-Ternary-Resonant-Coherence-Processor)

The FRP upstream repository and FRP Trace Observatory remain separately
versioned repositories. The Observatory resolves upstream inputs read-only
and identifies them through exact paths, publication roles, byte lengths,
archive membership, source coordinates, and SHA-256 digests.

Upstream source records retain their upstream identity. Normalized records
retain their source links. Observatory-derived reports, projections, traces,
frames, and views retain explicit derivation and provenance records.

## Published Boundaries

The retained Observatory implementation qualifies two exact publication
chains:

| Upstream boundary | Observatory closure | Qualified scope |
|---|---|---|
| FRP M30 | Observatory M8B | Immutable archive intake, registry, dispatch, audit, trace, and full-core transition visualization |
| FRP M31 | Observatory M22 | Four-document publication intake, registry, dispatch, audit, trace, transition visualization, and end-to-end qualification |

The detailed milestone ledger is maintained in
[docs/milestones.md](docs/milestones.md). Exact execution and input-identity
requirements are maintained in
[docs/reproducibility.md](docs/reproducibility.md).

## Evidence and Benchmark Attribution

Historical evidence and benchmark records are retained with their original
measurement contour and provenance. Current derived representations preserve
links to the source records from which they were constructed.

The repository distinguishes:

- upstream source data;
- normalized source-linked records;
- Observatory-derived records and views;
- historical benchmark contours;
- current comparative contours;
- hardware-sensitivity contours;
- thermal-profile contours;
- physical-measurement declarations.

These categories carry different evidentiary meanings and remain separately
identified in serialized outputs, documentation, and qualification tests.

When citing a result produced through this repository, retain the applicable:

1. FRP upstream version or milestone;
2. upstream commit, archive, or publication identity;
3. source artifact path;
4. source or archive SHA-256;
5. Observatory milestone and repository revision;
6. dataset, report, contour, record, or frame identity;
7. measurement-contour classification.

## Redistribution and Modified Files

Redistributions must satisfy the Apache License, Version 2.0, including its
requirements for providing the license, identifying modified files, and
retaining applicable copyright, patent, trademark, and attribution notices.

Files or dependencies carrying separate notices retain those notices and
their applicable terms. References to upstream projects identify provenance
and do not transfer authorship of upstream material to the Observatory.

## Names and Marks

Project names are used to identify the software and the provenance of its
inputs. The Apache License, Version 2.0, does not grant trademark rights beyond
reasonable and customary use in describing origin and reproducing applicable
notice content.

## Warranty

The warranty disclaimer and limitation of liability are defined by the
Apache License, Version 2.0, supplied in [LICENSE](LICENSE).

## Documentation Authority

The following files define the current repository contracts:

- [README.md](README.md) — project entry point;
- [docs/usage.md](docs/usage.md) — supported operation;
- [docs/reproducibility.md](docs/reproducibility.md) — reproducibility contract;
- [docs/ci.md](docs/ci.md) — CI and manual qualification rules;
- [docs/milestones.md](docs/milestones.md) — completed milestone history;
- [docs/integration_contract.md](docs/integration_contract.md) — upstream integration boundary;
- [docs/normalized_data_model.md](docs/normalized_data_model.md) — normalized model and provenance semantics;
- [docs/supported_schema_registry.md](docs/supported_schema_registry.md) — executable schema support;
- [docs/m31_published_boundary.md](docs/m31_published_boundary.md) — exact M31 publication boundary.

Where a generated or serialized output is involved, its embedded source,
identity, digest, origin, derivation, and measurement-contour fields provide
the record-specific provenance.
