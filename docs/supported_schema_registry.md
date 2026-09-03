
# FRP Trace Observatory Supported Schema Registry

- **Registry status:** Implemented exact-match compatibility inventories
- **Audited upstream scopes:** FRP v1.8.0 / M16, M30 archive, M31 publication
- **Base compatibility records:** 19
- **M30 published-member registrations:** 4
- **M30 exact mode routes:** 7
- **M31 published-document registrations:** 4
- **M31 exact mode routes:** 6
- **Canonical upstream fixture copies:** 6
- **Current exact verification:** 655 tests, `OK`

## Purpose

This document is the human-readable companion to `schemas/registry.py`,
`schemas/m30_published_registry.py`, and
`schemas/m31_published_registry.py`. It records exact upstream identities,
producers, evidence paths, formats, measurement contours, field contracts,
fixtures, modes, immutable publication identities, and qualification states.
FRP remains the sole authority for processor semantics. Registry membership
does not create a new upstream schema and does not itself establish
`supported` status.

## Registry Authority

The three executable registries contain identity and routing facts:

- `schemas/registry.py` contains the 19 audited M16-baseline compatibility
  records;
- `schemas/m30_published_registry.py` contains four exact members captured
  from the immutable M30 archive;
- `schemas/m31_published_registry.py` contains four exact M31 publication
  documents.

Lifecycle states in this document describe downstream implementation evidence
and are not fields of `CompatibilityRecord`.
Exact matching rules are:

- JSON identities use the exact `schema` value;
- shared schemas also require the exact `kind` value;
- M15 vector text uses the exact `format_version` value;
- historical identifiers remain separate versions;
- aliases, automatic upgrades, and implicit substitutions are prohibited;
- filenames alone do not establish typed identity;
- source bytes remain unchanged and receive a raw SHA-256 digest;
- M30 members require exact member id, path, schema, byte length, raw SHA-256,
  and archive identity;
- M31 documents require exact role, path, identifier field, identifier value,
  kind where applicable, byte length, and raw SHA-256;
- producer commands are provenance and are never executed during loading.

No formal upstream JSON Schema, canonical upstream CSV artifact, or
machine-readable `frp.m16.*` schema was present in the audited FRP v1.8.0 /
M16 baseline. The M31 publication independently supplies its exact formal
JSON Schema.

## Lifecycle States

| State | Meaning |
|---|---|
| `not_implemented` | Identity is audited without a parser and validator |
| `implemented` | Parser, routing, and validation exist |
| `tested` | Canonical evidence and mandatory-failure cases pass tests |
| `supported` | All integration-contract gates and CI evidence are complete |
| `unsupported` | Identity is intentionally outside the current boundary |
| `blocked_missing_fixture` | Required canonical upstream evidence is absent |

- base records 1–14 are `implemented`;
- base records 15–19 are `tested` against unchanged canonical fixture
  copies;
- the schema-free workload copy is tested only as manifest-bound evidence;
- the four M30 registrations and seven routes are qualified by the M8B
  full-core transition-visualizer workflow;
- the four M31 registrations and six routes are qualified by the M22
  end-to-end workflow;
- base records 1–14 retain their original implementation state and still lack
  committed canonical upstream artifact instances.

## Exact Enumerations

Artifact formats:

- `json`;
- `frp_m15_vector_text`.

Measurement contours:

- `structured_output`;
- `m3_benchmark_matrix`;
- `m15_implementation_mapping`;
- `comparative_architecture_benchmark_suite`;
- `hardware_informed_sensitivity_qualification`.

M30 published measurement contours:

- `m16_fpga_preparation_execution`;
- `m27_long_run_telemetry_semantics`;
- `m28_upstream_integration_contract`;
- `m28_hierarchical_scaling_qualification`.

M31 published measurement contours:

- `formal_schema_definition`;
- `phase_interference_active_zero_thermal_evidence`;
- `publication_manifest`;
- `publication_qualification`.

Observatory modes:

- `artifact_auditor` (`A`);
- `ternary_transition_visualizer` (`V`);
- `trace_explorer` (`T`).

## Base Compatibility Records

All base records are associated with audited upstream release `v1.8.0`.

| No. | Exact identifier | Required kind | Format | Contour | Modes | State |
|---:|---|---|---|---|---|---|
| 1 | `frp.structured_output.v1.7.0` | `demo` | JSON | structured output | A, V, T | `implemented` |
| 2 | `frp.structured_output.v1.7.0` | `self_test` | JSON | structured output | A | `implemented` |
| 3 | `frp.m3.benchmark_matrix.v1.7.0` | `benchmark_matrix` | JSON | M3 matrix | A | `implemented` |
| 4 | `frp.m15.fixed_point_interface_profile.v1.7.0` | `fixed_point_interface_profile` | JSON | M15 mapping | A | `implemented` |
| 5 | `frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0` | `balanced_ternary_hardware_encoding_map` | JSON | M15 mapping | A, V | `implemented` |
| 6 | `frp.m15.quantized_reference_shadow_model.v1.7.0` | `quantized_reference_shadow_model` | JSON | M15 mapping | A, V, T | `implemented` |
| 7 | `frp.m15.cycle_exact_reference_trace.v1.7.0` | `cycle_exact_reference_trace` | JSON | M15 mapping | A, V, T | `implemented` |
| 8 | `frp.m15.rtl_comparison_vector_package.v1.7.0` | `rtl_comparison_vector_package` | JSON | M15 mapping | A | `implemented` |
| 9 | `frp.m15.systemverilog_testbench_interface_map.v1.7.0` | `systemverilog_testbench_interface_map` | JSON | M15 mapping | A | `implemented` |
| 10 | `frp.m15.synthesizable_rtl_reference_core.v1.7.0` | `synthesizable_rtl_reference_core` | JSON | M15 mapping | A | `implemented` |
| 11 | `frp.m15.rtl_assertion_correlation_harness.v1.7.0` | `rtl_assertion_correlation_harness` | JSON | M15 mapping | A | `implemented` |
| 12 | `frp.m15.reference_rtl_equivalence_report.v1.7.0` | `reference_rtl_equivalence_report` | JSON | M15 mapping | A | `implemented` |
| 13 | `frp.m15.qualification_closure_manifest.v1.7.0` | `qualification_closure_manifest` | JSON | M15 mapping | A | `implemented` |
| 14 | `frp.m15.vector.v1` | none | M15 vector text | M15 mapping | A, V, T | `implemented` |
| 15 | `frp.benchmark.normalized_cost_profile.v1` | none | JSON | comparative architecture | A | `tested` |
| 16 | `frp.benchmark.thermal_proxy_profile.v1` | none | JSON | comparative architecture | A | `tested` |
| 17 | `frp.benchmark.hardware_sensitivity_cost_profile.v1` | none | JSON | hardware sensitivity | A | `tested` |
| 18 | `frp.benchmark.architecture_comparison.v1` | none | JSON | comparative architecture | A | `tested` |
| 19 | `frp.benchmark.hardware_sensitivity_comparison.v1` | none | JSON | hardware sensitivity | A | `tested` |

Record 14 uses identifier field `format_version`; every other record uses
identifier field `schema`.

## M30 Digest-Bound Published Registry

The M30 registry revision is `m30-published-boundary-v1`. Its authority is
the immutable archive:

`artifacts/m30/packages/frp-v3.2.0-m30-archival-release.tar.gz`

Archive identity:

- byte length: 10,189,989;
- raw SHA-256:
  `05ea33f6f3f505d315af930c2d51779f7189905308473f32a57375e477069caa`.

The exact M30 registrations are:

| Member id | Exact schema | Contour | Modes | Bytes | Raw SHA-256 | Upstream release |
|---|---|---|---|---:|---|---|
| `m16-fpga-preparation-execution-trace` | `frp.m16.fpga_preparation_execution_trace.v2.1.0` | `m16_fpga_preparation_execution` | A, V, T | 9,013 | `7d58b6741bdcadbfb9acb9049ed0e956305f49b9ad36946e719a4121b5caf22f` | `frp-v2.1.0-m19` |
| `m27-telemetry-semantics` | `m27-telemetry-semantics-v2.9.0` | `m27_long_run_telemetry_semantics` | A, V | 2,789 | `813ae5c66ceaddabc77734d44f1ebf971ca3bd7e11c1984e2e0c8f0204dfd1bc` | `frp-v2.9.0-m27` |
| `m28-trace-observatory-upstream-contract` | `frp.m28.trace_observatory_upstream_contract.v3.0.0` | `m28_upstream_integration_contract` | A | 2,735 | `556cd2921014d78184dad625438e053632c2650164f95787f39a6fc871b4a3f0` | `frp-v3.0.0-m28` |
| `m28-hierarchical-scaling-contract` | `frp.m28.hierarchical_scaling_contract.v3.0.0` | `m28_hierarchical_scaling_qualification` | A | 3,560 | `13f85ac82b63d0191157bd2cfa04dd37358ef66d8e69bdb96bb1892abb77dbae` | `frp-v3.0.0-m28` |

Their exact upstream paths are:

| Member id | Exact upstream path |
|---|---|
| `m16-fpga-preparation-execution-trace` | `artifacts/m19/execution/m16-fpga-preparation-execution-trace.json` |
| `m27-telemetry-semantics` | `artifacts/m27/telemetry/m27-telemetry-semantics.json` |
| `m28-trace-observatory-upstream-contract` | `artifacts/m28/contracts/m28-trace-observatory-upstream-contract.json` |
| `m28-hierarchical-scaling-contract` | `artifacts/m28/hierarchy/contracts/m28-hierarchical-scaling-contract.json` |

Their deterministic compatibility keys are:

| Member id | Compatibility key |
|---|---|
| `m16-fpga-preparation-execution-trace` | `a221aecb0d24518c8a2dd562405dad9b47ff53be5b4b2f6a972b6ecedc066ff2` |
| `m27-telemetry-semantics` | `06c74930ea2d928fa07c0f2ca86ee886b67ce6846cdea855dba66acff0bb82b6` |
| `m28-trace-observatory-upstream-contract` | `c5d60d4b37f669cc650b56be99bf61eb42ef837491e50cb9081cebc94cea14b0` |
| `m28-hierarchical-scaling-contract` | `737e7e29b051a0928575508e506d31b0b275933a490f161b16de0264d4d01746` |

The exact route counts are:

- Artifact Auditor: 4;
- Ternary Transition Visualizer: 2;
- Trace Explorer: 1;
- total: 7.

The qualified M30 Artifact Auditor result contains four reports, 69 checks,
zero failed checks, and batch SHA-256
`aeb9c1d7390a3bc3d1d7ef35c5f3f110e195e9b7ac8d4a4f4636c47c0a99bd03`.

The M30 Trace Explorer projection contains four records, 32 cell snapshots,
eight requests, the observed `-1/0/1` state domain, and dataset SHA-256
`4e6e0a1cd13dccbf6c6ab45850aefcb09d212fe4883f2d56c2c190dbee42bafd`.

The M8B full-core Transition Visualizer qualification combines two exact trace
sources into 100 trace records and 800 transition frames. Its dataset SHA-256
is
`7325fb188fd7709f28dda06765decaa29ac942895e4772b747291aec29ad3f2b`,
and its visualizer dataset id is
`68de3476-2e03-5506-93ea-062c3744e90d`.

## M31 Digest-Bound Published Registry

The M31 registry revision is `m31-published-boundary-v1`. It binds exactly
four immutable upstream documents:

| Role | Exact identifier | Required kind | Contour | Modes | Bytes | Raw SHA-256 |
|---|---|---|---|---|---:|---|
| Formal schema | `https://frp.example/schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | none | `formal_schema_definition` | A | 1,468 | `53d79d45d70753ccd24c3dc4c97af6fee481f86a9d7cdca7ef78b486c76479f7` |
| Evidence | `frp.m31.phase_interference_active_zero_thermal_evidence.v1` | `phase_interference_active_zero_thermal_evidence` | `phase_interference_active_zero_thermal_evidence` | A, V, T | 39,993 | `bdaa676acbfb09d86d848070e8a2673c5ce6902657a0b13b2e4293383bec8b42` |
| Manifest | `frp.m31.phase_interference_active_zero_thermal_evidence_manifest.v1` | `phase_interference_active_zero_thermal_evidence_manifest` | `publication_manifest` | A | 828 | `80f0841d0041cd22c2f76175b6139e601aede7b69823356ae1fefbce5f793e7c` |
| Qualification | `frp.m31.phase_interference_active_zero_thermal_evidence_qualification.v1` | `phase_interference_active_zero_thermal_evidence_qualification` | `publication_qualification` | A | 1,512 | `4c2446f954e01ec0aa37cc6c0fc70cf4a87ec565c450628e31b0efcac9160224` |

Their exact upstream paths and identifier fields are:

| Role | Exact upstream path | Identifier field |
|---|---|---|
| Formal schema | `schemas/m31/frp.m31.phase_interference_active_zero_thermal_evidence.v1.schema.json` | `$id` |
| Evidence | `artifacts/m31/evidence/m31-phase-interference-active-zero-thermal-evidence.json` | `schema` |
| Manifest | `artifacts/m31/manifests/m31-phase-interference-active-zero-thermal-evidence-manifest.json` | `schema` |
| Qualification | `artifacts/m31/qualification/m31-phase-interference-active-zero-thermal-evidence-qualification.json` | `schema` |

Their deterministic compatibility keys are:

| Role | Compatibility key |
|---|---|
| Formal schema | `0a3b92c08456517bd03e5c49ed683d490869688e6a2039f021228fc8db66b8b2` |
| Evidence | `ac1a9fae03831d912e1b1abf42dd73713b506a10b28c7b65041cca2e2b56e296` |
| Manifest | `8263f4f97b459fcdb5defbe2d9881bd1b7b0c52a3a94830dfb5cb16a982bc59e` |
| Qualification | `594bd40bba735ff9572cde8e6cc38cfcbb184748aaa0ce5f394a38d24737187a` |

The exact route counts are:

- Artifact Auditor: 4;
- Ternary Transition Visualizer: 1;
- Trace Explorer: 1;
- total: 6.

The M22 end-to-end qualification verifies:

- 4 published documents;
- 4 Artifact Auditor reports;
- 47 Artifact Auditor checks with zero failed checks;
- 2 trace contours and 100 ordered trace records;
- 800 source-linked cell snapshots and transition frames;
- 200 request records;
- balanced ternary domain `-1/0/1`;
- active neutral state `0`;
- 0 direct opposite transitions;
- 4 separate thermal evidence contours;
- 26 exact end-to-end tests.

The qualified M31 Artifact Auditor batch SHA-256 is
`3e5eb2ad76f2605a49cc8a53902435bdcc1b52afac40dcdb3132fd33ce94d591`.

The exact document paths, provenance members, compatibility keys, derived
dataset identities, thermal contours, and M9–M22 implementation history are
recorded in
[`docs/m31_published_boundary.md`](m31_published_boundary.md).

## Current Cross-Registry Qualification

With both exact upstream inputs configured:

```
FRP_M30_ARCHIVE_PATH=<exact M30 archive>
FRP_M31_UPSTREAM_ROOT=<clean FRP checkout>
python -m unittest discover -s tests -p 'test_*.py' -q
```

Current result:

```
Ran 655 tests

OK
```

This run exercises the base registry, exact M30 archive and published-member
contour, exact M31 publication contour, all three Observatory modes, and the
complete M31 end-to-end qualification.

## Producer and Evidence Associations

Records 1–14:

- producer and evidence path: `frp_prototype_v1_7_0.py`;
- producer version: `1.7.0`;
- registered version: `1.7.0` for records 1–13 and `1` for record 14;
- contract path: `docs/output_schema.md`.

Committed-artifact records:

| No. | Exact producer | Exact evidence path | Producer version |
|---:|---|---|---|
| 15 | `benchmarks/architecture_comparison/common_cost_model.py` | `benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json` | not recorded |
| 16 | `benchmarks/architecture_comparison/common_thermal_model.py` | `benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json` | not recorded |
| 17 | not recorded | `benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json` | not recorded |
| 18 | `benchmarks/architecture_comparison/run_architecture_comparison.py` | `benchmarks/architecture_comparison/results/reference_comparison_seed_76.json` | not recorded |
| 19 | `benchmarks/architecture_comparison/run_hardware_sensitivity_comparison.py` | `benchmarks/architecture_comparison/results/reference_comparison_seed_76_hardware_sensitivity_v1.json` | not recorded |

The upstream validator for record 17 is
`benchmarks/architecture_comparison/validate_hardware_sensitivity_profile.py`.
It is not substituted into the empty producer field.

## Shared M15 Identity Contract

JSON records 1–13 require:

- `schema`;
- `kind`;
- `version = 1.7.0`;
- milestone: M15 — Implementation Mapping, Domain Interface, and
  Qualification Closure Package.

Retention of these identifiers by FRP v1.8.0 does not rename them to v1.8.0.

## Structured Output Field Contracts

### Record 1: `demo`

- Root: `schema`, `kind`, `version`, `milestone`, `configuration`, `kernel`,
  `hardware_profile`, `summary`, `preload_digest`, `trace_digest`,
  `cell_trace_digest`.
- Optional: `trace`, `cell_trace`, `route_events`; full trace output emits all
  three together.
- `configuration`: `cells`, `steps`, `seed`, `scheduler`,
  `transition_fraction`, `request_lanes`, `gamma_nominal`, `fractal_alpha`,
  `thermal_beta`, `ambient_heat`, `thermal_time_constant`,
  `thermal_soft_limit`, `thermal_hard_limit`, `coupling_nominal`,
  `delay_alpha`, `thermal_diffusion_gain`.
- `kernel`: `balanced_ternary_states`, `active_neutral_state`,
  `neutral_routes`, `scheduler_modes`, `actual_direct_events_target`.
- `hardware_profile`: `scalar`, `unit`, `phase`, `gamma`, `state_encoding`.
- `summary`: `version`, `milestone`, `cells`, `hierarchy_depth`,
  `request_lanes`, `steps`, `ticks_recorded`, `scheduler`,
  `scheduler_counts`, `scheduler_counts_valid`, `transition_fraction`,
  `balanced_ternary_state_domain`, `reserved_state_events`,
  `actual_direct_events`, `requested_direct_events`,
  `prevented_direct_events`, `neutral_routed_events`,
  `neutralized_conflicts`, `pending_route_count_final`,
  `neutral_route_queue_capacity`, `queue_overflow_events`,
  `switch_load_peak_q16`, `switch_load_peak`, `C_minus_P_final_q16`,
  `C_minus_P_final`, `C_minus_P_min_q16`, `C_minus_P_min`,
  `boundary_detected`, `fixed_point_topology_sum_exact`,
  `fixed_point_thermal_sum_exact`.
- `trace` row: `tick`, `reset_n`, `scheduler_mode`, `scheduler_state`,
  `scheduler_state_name`, `auto_targets_enable`, `request_valid_mask`,
  `request_cell_ids`, `request_target_states`,
  `gamma_noise_update_valid`, `gamma_noise_target_q16`, `states_packed`,
  `states_packed_hex`, `states_human`, `pending_route_count`,
  `switch_load_q16`, `heat_global_q16`, `global_phase_coherence_q30`,
  `C_q16`, `P_q16`, `C_minus_P_q16`, `requested_direct_events`,
  `prevented_direct_events`, `neutral_routed_events`,
  `neutralized_conflicts`, `actual_direct_events`, `reserved_state_events`,
  `queue_overflow_events`, `changes`.
- `cell_trace` row: `tick`, `cell_id`, `state_code`, `phase_word`,
  `frequency_target_q16`, `frequency_current_q16`, `frequency_lag_q16`,
  `generated_power_q16`, `heat_q16`, `thermal_overload_q16`,
  `gamma_noise_state_q16`, `gamma_effective_word`,
  `thermal_node_factor_q30`, `coupling_field_q16`.
- `route_events` row: `tick`, `cell_id`, `target_state`, `ready_tick`,
  `route_status`.

### Record 2: `self_test`

- Root: `schema`, `kind`, `version`, `milestone`, `status`, `check_count`,
  `checks`, `neutral_route_validation`, `scheduler_validation`,
  `request_lane_order_validation`, `queue_exhaustion_validation`,
  `fixed_point_validation`, `encoding_validation`, `topology_validation`,
  `trigonometric_lut_validation`, `semantic_correlation`,
  `exact_shadow_replay`, `vector_determinism`, `scaling_validation`.
- Optional: none published.
- Qualification: 41 checks, all true for `status = PASS`.

## M3 Benchmark-Matrix Contract

Record 3 requires root fields `schema`, `kind`, `version`, `milestone`, and
`rows`.

Every row requires `architecture`, `numeric_domain`,
`cycle_exact_integer_trace`, and `hardware_facing_encoding`.

The five ordered rows add:

1. `interaction_scaling`;
2. `interaction_scaling`, `state_sequence_match`,
   `scheduler_sequence_match`, `C_minus_P_sign_match`;
3. `vector_repeat_match`;
4. `comparison_rule`;
5. `artifact_layers`.

No optional root fields are produced.

## M15 JSON Field Contracts

All sets below include the shared M15 identity fields.

| No. | Required kind-specific root fields | Optional root fields |
|---:|---|---|
| 4 | `inherited_boundary`, `profile`, `topology_fixed_point_profile`, `thermal_fixed_point_profile`, `fixed_point_topology_sum_exact`, `fixed_point_thermal_sum_exact` | none |
| 5 | `inherited_boundary`, `state_encoding`, `reserved_state_code`, `packed_state_vector`, `request_interface`, `scheduler_mode_encoding`, `scheduler_state_encoding` | none |
| 6 | `inherited_boundary`, `execution_model`, `configuration`, `numeric_profile`, `preload`, `summary`, `trace_digest`, `cell_trace_digest` | none |
| 7 | `configuration`, `preload`, `summary`, `trace`, `route_events` | none |
| 8 | `vector_classes`, `manifest`, `deterministic_package_digest` | `written_files` |
| 9 | `parameters`, `execution_inputs`, `verification_stimulus_inputs`, `comparison_outputs`, `vector_replay_order` | none |
| 10 | `kernel_requirements`, `planned_rtl_files`, `exact_tick_execution_order` | none |
| 11 | `assertion_count`, `assertions`, `direct_transition_rules`, `scheduler_modes`, `exact_comparison_rule` | none |
| 12 | `floating_reference_to_quantized_shadow`, `quantized_shadow_deterministic_replay`, `rtl_exact_integer_comparison_contract` | none |
| 13 | `artifact_layers`, `checks`, `semantic_correlation`, `exact_shadow_replay`, `vector_manifest`, `status` | none |

Record 5 preserves the canonical processor domain `-1, 0, 1`.

## M15 Vector-Text Contract

Record 14 requires:

- ordered metadata: `format_version`, `frp_version`, `milestone`,
  `trace_kind`, `cells`, `hierarchy_depth`, `request_lanes`,
  `transition_fraction`, `scheduler_mode`, `fractal_alpha`, `thermal_beta`,
  `scalar_format`, `unit_format`, `phase_format`, `seed`, `trace_steps`,
  `column_definition`;
- `trace_kind`: `kernel_transition_vectors`, `pending_routes`,
  `scheduler_free_vectors`, `scheduler_7_1_vectors`,
  `scheduler_1_7_vectors`, `full_correlation_vectors`, or `cell_trace`;
- primary columns: `TICK`, `RESET_N`, `SCHED_MODE`, `SCHED_STATE`,
  `AUTO_TARGETS_ENABLE`, `REQ_VALID_MASK`, `REQ_CELL_IDS`,
  `REQ_TARGET_STATES`, `GAMMA_UPDATE_VALID`, `GAMMA_NOISE_TARGETS_Q`,
  `STATES_PACKED`, `PENDING_ROUTE_COUNT`, `SWITCH_LOAD_Q`,
  `HEAT_GLOBAL_Q`, `COHERENCE_GLOBAL_Q`, `C_Q`, `P_Q`, `C_MINUS_P_Q`,
  `REQUESTED_DIRECT_EVENTS`, `PREVENTED_DIRECT_EVENTS`,
  `NEUTRAL_ROUTED_EVENTS`, `NEUTRALIZED_CONFLICTS`,
  `ACTUAL_DIRECT_EVENTS`;
- pending-route columns: `TICK`, `ROUTE_INDEX`, `CELL_ID`,
  `TARGET_STATE_CODE`, `READY_TICK`, `ROUTE_STATUS`;
- cell-trace columns: `TICK`, `CELL_ID`, `STATE_CODE`, `PHASE_WORD`,
  `FREQUENCY_TARGET_Q`, `FREQUENCY_CURRENT_Q`, `FREQUENCY_LAG_Q`,
  `GENERATED_POWER_Q`, `HEAT_Q`, `THERMAL_OVERLOAD_Q`,
  `GAMMA_NOISE_STATE_Q`, `GAMMA_EFFECTIVE_WORD`,
  `THERMAL_NODE_FACTOR_Q`, `COUPLING_FIELD_Q`.

## Comparative and Sensitivity Root Contracts

Records 15–19 permit no optional root fields:

- 15: `schema`, `suite_name`, `profile_name`, `cost_unit`, `costs`,
  `cost_profile_sha256`;
- 16: `schema`, `suite_name`, `profile_name`, `temperature_unit`,
  `ambient_temperature_proxy`, `thermal_decay`, `thermal_gain`,
  `update_equation`, `thermal_profile_sha256`;
- 17: `schema`, `suite_name`, `profile_name`, `profile_role`,
  `profile_status`, `baseline_profile`, `baseline_result`, `provenance_map`,
  `normalization_reference`, `reference_basis`, `scenario_order`,
  `coefficient_order`, `coefficients`, `scenario_vectors`,
  `evaluation_contract`, `validation_contract`, `digest_contract`,
  `cost_profile_sha256`;
- 18: `schema`, `suite_name`, `benchmark_kind`, `frp_reference_version`,
  `frp_scheduler`, `architecture_order`, `workload_profile`,
  `workload_sha256`, `cost_profile`, `cost_profile_sha256`,
  `thermal_profile`, `thermal_profile_sha256`, `architectures`,
  `comparison_matrix`, `integrity`, `qualification`,
  `comparison_package_sha256`;
- 19: `schema`, `suite_name`, `benchmark_kind`, `frp_reference_version`,
  `frp_scheduler`, `architecture_order`, `workload_profile`,
  `workload_sha256`, `hardware_sensitivity_profile`,
  `hardware_sensitivity_profile_sha256`, `profile_validation`,
  `baseline_binding`, `thermal_profile`, `thermal_profile_sha256`,
  `raw_trace_ledger`, `raw_trace_set_sha256`, `scenarios`,
  `ranking_stability`, `integrity`, `qualification`,
  `hardware_sensitivity_package_sha256`.

The committed comparison artifacts contain aggregate evidence and trace
identities, not raw processor-tick trace arrays.

## Schema-Free Workload Fixture

`workload_profile_v1.json` has no embedded schema and is not an executable
registry record. `common_workload.py` recognizes only `num_cells`,
`command_count`, `seed`, `issue_policy`,
`max_completion_cycles_per_command`, and `final_cooldown_cycles`.

The canonical copy contains `16`, `256`, `76`, `transaction_serial`, `64`,
and `32` respectively. Unknown fields are rejected.

## Producer Commands

```
# Structured output and M3
python frp_prototype_v1_7_0.py --mode demo --output json
python frp_prototype_v1_7_0.py --mode demo --output json --include-trace
python frp_prototype_v1_7_0.py --mode self-test --output json
python frp_prototype_v1_7_0.py --mode benchmark --output json
python frp_prototype_v1_7_0.py --export-benchmark-matrix

# M15 base command: python frp_prototype_v1_7_0.py
--export-fixed-point-interface-profile
--export-balanced-ternary-hardware-encoding-map
--export-quantized-reference-shadow-model
--export-cycle-exact-reference-trace
--export-rtl-comparison-vector-package
--export-systemverilog-testbench-interface-map
--export-synthesizable-rtl-reference-core
--export-rtl-assertion-correlation-harness
--export-reference-rtl-equivalence-report
--export-qualification-closure-manifest

# Written deterministic package
python frp_prototype_v1_7_0.py --export-rtl-comparison-vector-package --vector-output-dir <directory>

# Comparative profiles and results
python benchmarks/architecture_comparison/common_workload.py --profile benchmarks/architecture_comparison/profiles/workload_profile_v1.json --output json
python benchmarks/architecture_comparison/common_cost_model.py --write-default-profile benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json
python benchmarks/architecture_comparison/common_thermal_model.py --write-default-profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json
python benchmarks/architecture_comparison/run_architecture_comparison.py --workload-profile benchmarks/architecture_comparison/profiles/workload_profile_v1.json --cost-profile benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json --thermal-profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json --frp-scheduler 7/1 --write benchmarks/architecture_comparison/results/reference_comparison_seed_76.json --output text
python benchmarks/architecture_comparison/run_hardware_sensitivity_comparison.py --workload-profile benchmarks/architecture_comparison/profiles/workload_profile_v1.json --hardware-sensitivity-profile benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json --thermal-profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json --frp-scheduler 7/1 --write benchmarks/architecture_comparison/results/reference_comparison_seed_76_hardware_sensitivity_v1.json --output text

# Record 17 validation command; no producer command is recorded
python benchmarks/architecture_comparison/validate_hardware_sensitivity_profile.py --profile benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json --output json
```

## Canonical Fixture Inventory

`fixtures/canonical_fixture_manifest.json` records six unchanged upstream byte
copies in lexicographic fixture-path order.

| Local fixture path | Exact upstream path | Raw bytes | Raw SHA-256 |
|---|---|---:|---|
| `fixtures/comparative_architecture/normalized_cost_profile_v1.json` | `benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json` | 677 | `bd2f5bfc4f0430c2764c5f1ddb1258d176b42f1667d1f0f691e40730ddc4c979` |
| `fixtures/comparative_architecture/reference_comparison_seed_76.json` | `benchmarks/architecture_comparison/results/reference_comparison_seed_76.json` | 21988 | `c27c4ecbe755df784b6fcb25d5549b719fd98dcf3821f280b7550f1669e8d76e` |
| `fixtures/comparative_architecture/thermal_proxy_profile_v1.json` | `benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json` | 517 | `aeafebc3e71d1311a3445bd1528cbe7322546f79d6a5099dfed3a9590fc4a25b` |
| `fixtures/comparative_architecture/workload_profile_v1.json` | `benchmarks/architecture_comparison/profiles/workload_profile_v1.json` | 174 | `5680c50220a751ea748e55644dd3a189321ca8e89398bb3751a471556dce94b9` |
| `fixtures/hardware_sensitivity/hardware_sensitivity_cost_profile_v1.json` | `benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json` | 15360 | `79c1c17c924bde6947dce477c2b8b64600684c993e7f42c1f00f6ffca0228a1c` |
| `fixtures/hardware_sensitivity/reference_comparison_seed_76_hardware_sensitivity_v1.json` | `benchmarks/architecture_comparison/results/reference_comparison_seed_76_hardware_sensitivity_v1.json` | 81632 | `f91ae25e06f5ae8024b8847c7aa4c9ac0ae77d78b3b912b1cf882d4dc52b346d` |

The workload profile has no embedded schema identifier. It is identified only
by exact upstream path and raw digest inside the verified fixture inventory.
It is not an independently dispatched compatibility record.

Declared artifact digests remain distinct from raw fixture digests:

| Artifact | Declared field | Exact declared digest |
|---|---|---|
| normalized cost profile | `cost_profile_sha256` | `4c4a470150ecc182c9a51eaefc0bcba0353e71160d16c6c6afd28a39c23b05bc` |
| thermal proxy profile | `thermal_profile_sha256` | `8cc2992f5699c47c88e81c17a4a5f0c8ff5bb7a5b32ebf73ab0e5a0f9c5494c8` |
| hardware sensitivity profile | `cost_profile_sha256` | `3814925a54d274bd43ab4576b6e60b53f60a2dfca9520d533ab49700c11dd553` |
| architecture comparison | `comparison_package_sha256` | `5a4be61ce7fd6bc680bbd8bc28bfe7cc9d2ad35adddf642cecff111fbd503d6a` |
| hardware sensitivity comparison | `hardware_sensitivity_package_sha256` | `a44cf392d946e3b5c21dffbaa1d726d31da326a007e2908914f6477215261ea0` |
| hardware sensitivity comparison | `raw_trace_set_sha256` | `42444ea48fc4a00fbc747e0392d218f624896c9e934b1031d38a8acf1a030952` |

The common workload binding digest is
`8386174d0a4751af26cc68bf46a5494cf0e58a3c14fc59ff46830a21645f0562`.

## M15 Deterministic Package

The package contains exactly ten members:

| Exact filename | Identity basis | Eligible mode |
|---|---|---|
| `frp_m15_kernel_vectors.vec` | `frp.m15.vector.v1` | A, V, T |
| `frp_m15_pending_routes.trace` | `frp.m15.vector.v1` | A, V |
| `frp_m15_scheduler_free_vectors.vec` | `frp.m15.vector.v1` | A, V, T |
| `frp_m15_scheduler_7_1_vectors.vec` | `frp.m15.vector.v1` | A, V, T |
| `frp_m15_scheduler_1_7_vectors.vec` | `frp.m15.vector.v1` | A, V, T |
| `frp_m15_full_correlation_vectors.vec` | `frp.m15.vector.v1` | A, V, T |
| `frp_m15_cell_trace.vec` | `frp.m15.vector.v1` | A, T |
| `frp_m15_reference_preload.json` | verified package role | A |
| `frp_m15_trig_lut_q30.vec` | verified package role | A |
| `frp_m15_sha256_manifest.json` | verified package role | A |

The published deterministic package digest is
`703dd4b56f4b34289a2c5bc5521ad4ddc3113bdec8c38238c3244c69cb4d58df`.

The package is not committed in the audited upstream baseline. Package parser,
member, ordering, size, digest, and incomplete-package rules are implemented
and tested with controlled test inputs; the support gate remains missing
canonical upstream fixture evidence.

## M16 Evidence Outside the Executable Registry

The following audited Markdown records have no machine-readable
`frp.m16.*` identifier:

- root: `FRP_VALIDATION_INDEX_v1_8_0.md`, `TEST_REPORT_v1_8_0.md`,
  `RELEASE_CHECKLIST_v1_8_0.md`, `RELEASE_NOTES_v1_8_0.md`;
- docs: `docs/m16_qualification_manifest.md`,
  `docs/m16_qualification_index.md`, `docs/m16_public_status_snapshot.md`,
  `docs/m16_m15_vector_replay_compatibility_report.md`,
  `docs/m16_rtl_artifact_boundary_qualification.md`;
- RTL: `rtl/m16/ARTIFACTS.md`, `rtl/m16/SIMULATION_TRANSCRIPT.md`,
  `rtl/m16/CLOSURE.md`;
- FPGA preparation: `fpga/m16/SIMULATION_TRANSCRIPT.md`,
  `fpga/m16/CLOSURE.md`.

Their producer workflows are
`.github/workflows/frp-m16-rtl-artifact-boundary.yml` and
`.github/workflows/frp-m16-fpga-preparation.yml`.

These files remain non-executable qualification evidence outside typed M16
loading. FPGA preparation evidence retains its recorded target-independent
qualification classification.

## Known Identifiers Outside the Executable Registry

Current producer identifiers without registered standalone canonical inputs:

`frp.benchmark.semantic_workload.v1`,
`frp.benchmark.semantic_workload.self_test.v1`, `frp.benchmark.normalized_cost_result.v1`,
`frp.benchmark.normalized_cost_model.self_test.v1`, `frp.benchmark.thermal_proxy_result.v1`,
`frp.benchmark.thermal_proxy_model.self_test.v1`, `frp.benchmark.architecture_reference_result.v1`,
`frp.benchmark.binary_synchronous_reference.self_test.v1`, `frp.benchmark.binary_clock_gated_reference.self_test.v1`,
`frp.benchmark.direct_ternary_reference.self_test.v1`, `frp.benchmark.frp_v1_7_0_adapter.self_test.v1`,
`frp.benchmark.architecture_comparison.self_test.v1`,
`frp.benchmark.hardware_sensitivity_comparison.self_test.v1`.

These identifiers are `unsupported` or `blocked_missing_fixture`; none is
silently routed through a registered contract.

Historical structured-output identifiers remain distinct and unsupported:

`frp.structured_output.v0.9.4`, `frp.structured_output.v0.9.5`,
`frp.structured_output.v0.9.6`, `frp.structured_output.v0.9.7`, `frp.structured_output.v0.9.8`,
`frp.structured_output.v0.9.9`, `frp.structured_output.v1.0.0`, `frp.structured_output.v1.1.0`,
`frp.structured_output.v1.2.0`, `frp.structured_output.v1.3.0`, `frp.structured_output.v1.4.0`,
`frp.structured_output.v1.5.0`, `frp.structured_output.v1.6.0`.

Historical M3 identifiers remain distinct and unsupported:

`frp.m3.benchmark_matrix.v0.9.5`, `frp.m3.benchmark_matrix.v1.5.0`,
`frp.m3.benchmark_matrix.v1.6.0`.

Retained M14 constants remain outside the executable registry:

`frp.m14.hierarchical_ultrametric_topology_model.v1.6.0`,
`frp.m14.fractal_coupling_weight_map.v1.6.0`, `frp.m14.multiscale_phase_coherence_map.v1.6.0`,
`frp.m14.cluster_local_thermal_field.v1.6.0`, `frp.m14.cross_cluster_propagation_map.v1.6.0`,
`frp.m14.localized_hotspot_containment_harness.v1.6.0`, `frp.m14.dense_hierarchical_equivalence_map.v1.6.0`,
`frp.m14.physical_domain_correlation_package.v1.6.0`.

No schema identifier is assigned to `frp_prototype_v0_9_3_mobile.py`.

## M16 Baseline Data Gaps

The audited FRP v1.8.0 / M16 baseline lacks:

- formal JSON Schema documents;
- committed canonical structured full-trace JSON;
- committed canonical M15 JSON exports;
- committed canonical M15 vector files and complete package;
- machine-readable M16 tick, lane, capacity, and qualification records;
- committed CSV or TSV artifacts;
- a machine-readable v0.9.3 benchmark artifact;
- retained CI artifact files referenced by M16 workflows.

The M30 and M31 digest-bound publication registries preserve their own exact
later evidence and do not rewrite the historical M16 compatibility baseline.

## Registry Change Requirements

A base compatibility record may become `supported` only after:

1. exact identity and producer evidence are audited;
2. required, optional, order, value, relation, and digest rules are recorded;
3. read-only parsing and validation are implemented;
4. canonical and mandatory-failure fixtures are committed;
5. provenance, immutability, parser, validator, and mode tests pass;
6. documentation is synchronized;
7. applicable CI workflow evidence passes.

An additional digest-bound publication registration requires:

1. an immutable upstream source identity;
2. an exact path, identifier, byte length, and raw SHA-256;
3. a non-interchangeable measurement contour;
4. explicit Observatory mode eligibility;
5. mandatory identity and mutation-failure tests;
6. end-to-end source immutability verification;
7. synchronized documentation and passing CI qualification.

An upstream release does not change any registry automatically.

## Author

Maksym Marnov (Alchimist)  
Berlin, Germany
