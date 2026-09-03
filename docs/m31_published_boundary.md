
# FRP M31 Published Evidence Boundary

- **Upstream project:** Fractal Resonance Processor
- **Upstream milestone:** M31
- **Published document version:** 1.0.0
- **Observatory registry revision:** `m31-published-boundary-v1`
- **Observatory qualification:** M22, PASS
- **Integration direction:** FRP published bytes → FRP Trace Observatory

## Purpose

This document defines the exact published FRP M31 evidence boundary consumed
by FRP Trace Observatory. It records the processor declaration, immutable
source identities, provenance chain, exact routing, downstream projections,
qualification results, and preservation requirements implemented by the M9
through M22 Observatory contour.

FRP remains the authority for processor semantics and published measurements.
Observatory captures and validates the published bytes, then constructs
source-linked audit, trace, and transition-visualization records.

## Processor Declaration

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
polarities. The qualified execution evidence contains:

- 5 polarity-to-active-zero transitions;
- 12 active-zero-to-polarity transitions;
- 783 retained-same transitions;
- 0 direct opposite transitions.

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

## Exact Publication Inventory

The M31 intake accepts exactly four JSON documents. Path, identifier, byte
length, and raw SHA-256 must all match.

| Role | Exact upstream path | Identifier | Bytes | Raw SHA-256 |
|---|---|---|---:|---|
| Formal schema | `schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | `$id = https://frp.example/schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | 1,468 | `53d79d45d70753ccd24c3dc4c97af6fee481f86a9d7cdca7ef78b486c76479f7` |
| Evidence | `artifacts/m31/evidence/m31-phase-interference-active-zero-thermal-evidence.json` | `schema = frp.m31.phase_interference_active_zero_thermal_evidence.v1` | 39,993 | `bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42` |
| Manifest | `artifacts/m31/manifests/m31-phase-interference-active-zero-thermal-evidence-manifest.json` | `schema = frp.m31.phase_interference_active_zero_thermal_evidence_manifest.v1` | 828 | `80f0841d0041cd22c2f76175b6139e601aede7b69823356ae1fefbce5f793e7c` |
| Qualification | `artifacts/m31/qualification/m31-phase-interference-active-zero-thermal-evidence-qualification.json` | `schema = frp.m31.phase_interference_active_zero_thermal_evidence_qualification.v1` | 1,512 | `4c2446f954e01ec0aa37cc6c0fc70cf4a87ec565c450628e31b0efcac9160224` |

The evidence, manifest, and qualification documents also require their exact
`kind`, `milestone = M31`, `version = 1.0.0`, and `status = PASS`
declarations. The formal schema is identified by its exact `$id`.

## Provenance Chain

The published evidence records 12 provenance sources. Ten historical members
are verified byte-for-byte inside the immutable M30 archival package. The
archive container and the post-archive M30 qualification workflow retain
their own exact source identities.

### Immutable M30 archive

| Path | Bytes | Raw SHA-256 |
|---|---:|---|
| `artifacts/m30/packages/frp-v3.2.0-m30-archival-release.tar.gz` | 10,189,989 | `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa` |

### Verified historical members

| Exact upstream path | Bytes | Raw SHA-256 |
|---|---:|---|
| `TEST_REPORT_v0_9_3.md` | 9,009 | `c6fe86f2c0c922243a8bd001742e9fcbfd3c31cdedf40a6a728b989dbd01679e` |
| `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` | 9,013 | `7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f` |
| `artifacts/m19/execution/m16-rtl-execution-trace.json` | 152,109 | `d7945e0d2b5aaa05c5fff2e4e60d3b984017f7e4ae1984c55920368a110020bd` |
| `artifacts/m29/contracts/m29-system-integration-contract.json` | 4,071 | `6e14d93abe5646b4e094f27b07217d9e4dcd833d8af0d5afb30da21b904c4642` |
| `benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json` | 517 | `aeafebc3e71d1311a3445bd1528cbe7322546f79d6a5099dfed3a9590fc4a25b` |
| `benchmarks/architecture_comparison/results/reference_comparison_seed_76.json` | 21,988 | `5ba86d26dc62db36ae14ac2c1167e71dd5c06c00bbd5aa3dc21c6d11b38db064` |
| `benchmarks/architecture_comparison/results/reference_comparison_seed_76_hardware_sensitivity_v1.json` | 81,632 | `e4785aa4c234cc7dd8e5377e5e0b41a8ec401f962400975e0cef7a88cc494680` |
| `docs/physical_foundation.md` | 22,814 | `e9bacd13ebe7a7058e698a80dc4f677476e3ed2eab4b9d41f58fd9cdbcf68a7e` |
| `docs/resonance_computation.md` | 49,745 | `1149cbd0aeb90d0a6133db5ecc1e5b4d45268815b70a75cb7a347a5e44a9b615` |
| `frp_prototype_v0_9_3_mobile.py` | 40,760 | `48361714bb815f362a30a5a884a0fb782cb97349e9a18f9b607af7bf54c02e52` |

### Post-archive qualification source

| Exact upstream path | Bytes | Raw SHA-256 |
|---|---:|---|
| `.github/workflows/frp-m30-observatory-full-core-trace-qualification-workflow.yml` | 22,259 | `01ca22bc98f63d9d4ea4a58299d53ff58b410f3f2db94b81097d7cef3ad4dee7` |

This chain preserves the historical release evidence, M16 RTL and FPGA
execution traces, M29 integration contract, benchmark profiles and results,
physical and computational foundations, executable reference, M30 archive,
and post-archive qualification source.

## Exact Observatory Registry

The executable registry is
`schemas/m31_published_registry.py`. It contains four exact registrations
and six mode routes.

| Published role | Measurement contour | Artifact Auditor | Trace Explorer | Ternary Transition Visualizer |
|---|---|---:|---:|---:|
| Formal schema | `formal_schema_definition` | 1 | 0 | 0 |
| Evidence | `phase_interference_active_zero_thermal_evidence` | 1 | 1 | 1 |
| Manifest | `publication_manifest` | 1 | 0 | 0 |
| Qualification | `publication_qualification` | 1 | 0 | 0 |
| **Total** | Four separate contours | **4** | **1** | **1** |

Routing uses the exact role, identifier field, identifier value, kind where
applicable, source path, byte length, and raw SHA-256. Each registration has
one deterministic compatibility key:

| Role | Compatibility key |
|---|---|
| Formal schema | `0a3b92c08456517bd03e5c49ed683d490869688e6a2039f021228fc8db66b8b2` |
| Evidence | `ac1a9fae03831d912e1b1abf42dd73713b506a10b28c7b65041cca2e2b56e296` |
| Manifest | `8263f4f97b459fcdb5defbe2d9881bd1b7b0c52a3a94830dfb5cb16a982bc59e` |
| Qualification | `594bd40bba735ff9572cde8e6cc38cfcbb184748aaa0ce5f394a38d24737187a` |

## Artifact Auditor Result

The M31 Artifact Auditor validates all four published documents and produces
four immutable reports containing 47 ordered checks.

| Role | Contour | Checks | Status | Report SHA-256 |
|---|---|---:|---|---|
| Formal schema | `formal_schema_definition` | 11 | `recognized_valid` | `5f18fd174e02f19adcac1809624a2c205b94ae6c226e05a20eaac4f896c6bb36` |
| Evidence | `phase_interference_active_zero_thermal_evidence` | 16 | `recognized_valid` | `e7c6163954973aa60994d2fa76f6f7edfdc6429fcbb397cf7e403a4e64f2f130` |
| Manifest | `publication_manifest` | 10 | `recognized_valid` | `e0ef32073524cd41ea2cf0b7b273ef3c63c61080e5ff72ae9e5432a81609d652` |
| Qualification | `publication_qualification` | 10 | `recognized_valid` | `5374a6b6e0def38ae5a50bb216c9be0396f6139f4a07e982b47e86b719414b53` |

The aggregate result is:

```
published_documents=4
audit_reports=4
validation_checks=47
failed_checks=0
batch_sha256=3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591
```

## Trace Explorer Result

Trace Explorer constructs one deterministic source-linked dataset from the
two published execution contours:

| Source contour | Records | Source-record digest | Contour SHA-256 |
|---|---:|---|---|
| `artifacts/m19/execution/m16-rtl-execution-trace.json` | 96 | `3f730a3d088e4d75fdd1631dd234878a6acd3a7561cb463e19c815096c04fe6a` | `23a0af37356389dc6ffd4ab2bac4a0cf64a418583ed43195b44193dacc3c4600` |
| `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` | 4 | `4b2e8aec64a0b3cb76d0819383ed66d306b8e50dc3feb7bb8c6c76486cd83d57` | `3e06ba60c8fb3bab08eabd83b9a3d83dee0176c6a682bb2825d2bba9d62dee94` |

The qualified dataset contains:

- 2 trace contours;
- 100 ordered trace records;
- 800 source-linked cell snapshots;
- 200 request records;
- 100 invariant-pass records;
- 702 observations whose retained state is active neutral `0`;
- scheduler-mode counts `free = 19`, `7/1 = 64`, and `1/7 = 17`;
- observed ternary domain `-1/0/1`.

Its deterministic identities are:

```
trace_dataset_id=0f0f0f7e-0409-5e7b-8c76-2f72bb954321
trace_dispatch_sha256=f34b867fabcaab51515ecca39f2eb7287f52aa218d3ac48596a1481326009630
dataset_sha256=ef5a040c9d30d02f90003e007e447cf0d66238f31ed27e3be92bdce31ad19fff
```

## Ternary Transition Visualizer Result

Ternary Transition Visualizer projects the same qualified trace dataset into
800 source-linked transition frames. Every frame retains its exact source
contour, trace record, cell, before-state, after-state, transition class, and
route-leg identity.

The transition classification is:

| Classification | Count |
|---|---:|
| `active_zero_to_polarity` | 12 |
| `direct_opposite` | 0 |
| `polarity_to_active_zero` | 5 |
| `retained_same` | 783 |

The route-leg inventory is:

| Route leg | Count |
|---|---:|
| `non_route_transition` | 790 |
| `first_leg_to_active_zero` | 5 |
| `pending_route_completion` | 5 |

Its deterministic identities are:

```
visualizer_dataset_id=63a1feb9-1835-579e-ab00-eec4569e8ff3
visualizer_dispatch_sha256=ff4597411a781c814ab8ef009d30739857411d2a31ff34839d3060b478a697e8
dataset_sha256=0ad87af2486798918a86a8a9fababdb45cb2b633c0f66e7c9b80b590ca8ed304
```

## Thermal Evidence Separation

The visualizer retains four non-interchangeable thermal evidence contours:

| Contour | Group | Physical temperature | Contour SHA-256 |
|---|---|---|---|
| `historical_release_benchmark` | historical | false | `8ae48a85c971d6fe8d136fd08b45ac7d801c6146c82eab2ac785c4e8318cb140` |
| `current_comparative_baseline` | current | false | `c7a66b2a99608b51508cc249459917d23ffebc4258501afd8567ca99afff6add` |
| `current_hardware_sensitivity` | current | false | `9b8a709f65e156b160facfb977a8b7362b928344dc45c840ef4b9eae637313a0` |
| `current_thermal_profile` | current | false | `1c92e0fbfb54f19803c70970b0dbf135c4bb37121a34407d64639ad6a3582eee` |

These values are published proxy and benchmark contours. The qualified M31
boundary contains zero physical-temperature measurements.

The historical focused comparison is retained exactly as published:

```
binary_heat_peak=0.051000
active_neutral_ternary_heat_peak=0.003250
heat_peak_ratio_binary_over_active_neutral_ternary=15.6923076923
heat_peak_relative_reduction_percent=93.63
```

The historical record retains its own release identity and contains an empty
`winner_assertions` list. Current comparative, hardware-sensitivity, and
thermal-profile contours remain separate from that historical record.

## Preservation Contract

The M31 Observatory boundary is read-only and source-linked:

- source bytes are captured unchanged;
- all registered byte lengths and SHA-256 identities are verified;
- schema aliases and implicit substitutions are excluded;
- source content and producer commands are treated as data;
- upstream source execution is excluded;
- downstream metric normalization is excluded;
- thermal contours remain separate;
- processor semantics remain defined by FRP;
- upstream source mutation is excluded;
- downstream writeback is excluded.

Validation failure prevents downstream routing. No failed source is repaired,
reordered, normalized, or assigned a replacement identity.

## Observatory Implementation History

The M31 integration contour was added and qualified incrementally:

| Observatory milestone | Published increment |
|---|---|
| M9 | M31 published-boundary intake workflow |
| M10 | Read-only M31 published-boundary intake source |
| M11 | Published-boundary intake tests |
| M12 | Exact M31 published-document registry source |
| M13 | Published-document registry tests |
| M14 | Exact M31 mode-dispatch source |
| M15 | Mode-dispatch tests |
| M16 | M31 published Artifact Auditor source |
| M17 | M31 published Artifact Auditor tests |
| M18 | M31 published Trace Explorer source |
| M19 | M31 published Trace Explorer tests |
| M20 | M31 published Ternary Transition Visualizer source |
| M21 | M31 published Ternary Transition Visualizer tests |
| M22 | Complete M31 Observatory end-to-end qualification |

The implementation files produced by these milestones remain independently
addressable. M22 verifies the complete chain without replacing M9–M21
history.

## Qualification Commands

Set `FRP_M31_UPSTREAM_ROOT` to a clean FRP repository checkout containing
the exact published M31 boundary:

```
export FRP_M31_UPSTREAM_ROOT=/path/to/Fractal-Resonance-Processor
```

Run the exact registry and all three downstream consumers:

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

Run the exact M22 end-to-end suite:

```
python -m unittest \
  tests.test_m31_published_observatory_end_to_end \
  -v
```

Expected result:

```
Ran 26 tests

OK
```

Run the complete Observatory suite with the same upstream root:

```
python -m unittest discover -s tests -p 'test_*.py' -q
```

Qualified repository result:

```
Ran 655 tests

OK (skipped=102)
```

The manual GitHub Actions qualification entry point is:

`.github/workflows/frp-observatory-m22-m31-published-end-to-end-qualification-workflow.yml`

## Implementation Map

| Responsibility | Observatory path |
|---|---|
| Immutable M31 intake | `artifact_auditor/m31_published_boundary_intake.py` |
| Exact document registry | `schemas/m31_published_registry.py` |
| Exact mode dispatch | `parsers/m31_published_dispatch.py` |
| Artifact Auditor | `artifact_auditor/m31_published_auditor.py` |
| Trace Explorer | `trace_explorer/m31_published_trace_explorer.py` |
| Ternary Transition Visualizer | `transition_visualizer/m31_published_transition_visualizer.py` |
| Complete end-to-end tests | `tests/test_m31_published_observatory_end_to_end.py` |

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
