# FRP Trace Observatory Supported Schema Registry

**Registry status:** Initial audited inventory  
**Upstream audit baseline:** FRP v1.8.0 / M16  
**Observatory version:** Not assigned  
**Implemented parsers:** None

## Purpose

This registry records exact upstream artifact identities discovered during the FRP v1.8.0 audit.

It defines the artifacts targeted by the initial FRP Trace Observatory implementation without claiming that parsers, validators, fixtures, or user-interface support already exist.

An artifact becomes supported only after all acceptance criteria in `docs/integration_contract.md` are satisfied.

## Registry Rules

Each entry records:

- exact schema or format identifier;
- required discriminator when applicable;
- exact upstream contract path;
- exact upstream producer path;
- producer version;
- published producer command;
- format;
- required top-level fields;
- optional top-level fields;
- canonical fixture candidate;
- measurement or qualification contour;
- target Observatory mode;
- implementation status.

Exact matching is required.

Historical schema identifiers are not aliases for current identifiers.

The same schema identifier may have multiple registry entries when the upstream producer uses an additional discriminator such as `kind`.

Producer commands are provenance records. Observatory must not execute them while loading an artifact.

No formal JSON Schema document was found in the audited upstream repository. Field requirements in this registry are Observatory integration contracts extracted from the published upstream producer and documentation.

## Status Vocabulary

| Status | Meaning |
|---|---|
| `not_implemented` | Upstream identity is audited, but no Observatory parser or validator exists |
| `implemented` | Parser and structural validation exist |
| `tested` | Canonical and negative fixtures pass the required tests |
| `supported` | Registry, parser, validator, fixtures, tests, provenance, and mode integration are complete |
| `unsupported` | Artifact is known but intentionally outside the current implementation boundary |
| `blocked_missing_fixture` | Upstream contract is known, but a required canonical artifact is unavailable |

No entry in this initial registry has `supported` status.

## Mode Names

Registry entries use the following exact mode names:

- `Trace Explorer`;
- `Ternary Transition Visualizer`;
- `Artifact Auditor`.

A mode listed as conditional may consume the artifact only when the required optional collections or verified package members are present.

## Current Release-Facing Schema Set

The FRP v1.8.0 output documentation retains twelve release-facing schema identifiers from the v1.7.0 semantic-reference and M15 export package.

| Schema identifier | Required discriminator | MVP target modes |
|---|---|---|
| `frp.structured_output.v1.7.0` | `kind = demo` | Artifact Auditor; Trace Explorer and Ternary Transition Visualizer when full trace collections are present |
| `frp.structured_output.v1.7.0` | `kind = self_test` | Artifact Auditor |
| `frp.m3.benchmark_matrix.v1.7.0` | `kind = benchmark_matrix` | Artifact Auditor |
| `frp.m15.fixed_point_interface_profile.v1.7.0` | `kind = fixed_point_interface_profile` | Artifact Auditor |
| `frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0` | `kind = balanced_ternary_hardware_encoding_map` | Artifact Auditor; Ternary Transition Visualizer as an auxiliary encoding contract |
| `frp.m15.quantized_reference_shadow_model.v1.7.0` | `kind = quantized_reference_shadow_model` | Artifact Auditor |
| `frp.m15.cycle_exact_reference_trace.v1.7.0` | `kind = cycle_exact_reference_trace` | Artifact Auditor; Trace Explorer; Ternary Transition Visualizer |
| `frp.m15.rtl_comparison_vector_package.v1.7.0` | `kind = rtl_comparison_vector_package` | Artifact Auditor; conditional Trace Explorer and Ternary Transition Visualizer access to registered package members |
| `frp.m15.systemverilog_testbench_interface_map.v1.7.0` | `kind = systemverilog_testbench_interface_map` | Artifact Auditor |
| `frp.m15.synthesizable_rtl_reference_core.v1.7.0` | `kind = synthesizable_rtl_reference_core` | Artifact Auditor |
| `frp.m15.rtl_assertion_correlation_harness.v1.7.0` | `kind = rtl_assertion_correlation_harness` | Artifact Auditor |
| `frp.m15.reference_rtl_equivalence_report.v1.7.0` | `kind = reference_rtl_equivalence_report` | Artifact Auditor |
| `frp.m15.qualification_closure_manifest.v1.7.0` | `kind = qualification_closure_manifest` | Artifact Auditor |

The table contains thirteen registry entries because `frp.structured_output.v1.7.0` has two distinct `kind` contracts.

No `frp.m16.*` machine-readable schema identifier was found in the audited upstream baseline.

## Shared v1.7.0 Identity Contract

The structured-output and M15 export objects use the following shared identity fields:

- `schema`;
- `kind`;
- `version`;
- `milestone`.

Registered producer version:

`1.7.0`

Registered milestone:

`M15 — Implementation Mapping, Domain Interface, and Qualification Closure Package`

Retaining these values inside FRP v1.8.0 does not change their schema version to v1.8.0.

## Canonical JSON Digest Contract

The audited producer uses canonical JSON bytes for the registered deterministic digests.

Published canonical serialization properties:

- sorted keys;
- compact separators;
- Unicode preservation;
- UTF-8 encoding;
- trailing newline.

Published digest algorithm:

`SHA-256`

Published digest representation:

`64-character lowercase hexadecimal string`

This contract applies only to digest fields whose upstream producer explicitly uses this serialization.

## Structured Output Entries

### `frp.structured_output.v1.7.0` with `kind = demo`

- Registry key: `frp.structured_output.v1.7.0#demo`
- Exact schema identifier: `frp.structured_output.v1.7.0`
- Required discriminator: `kind = demo`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python frp_prototype_v1_7_0.py --mode demo --output json`
- Full-trace producer command: `python frp_prototype_v1_7_0.py --mode demo --output json --include-trace`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `configuration`, `kernel`, `hardware_profile`, `summary`, `preload_digest`, `trace_digest`, `cell_trace_digest`
- Optional top-level fields: `trace`, `cell_trace`, `route_events`
- Full-trace collection rule: `trace`, `cell_trace`, and `route_events` are added together by `--include-trace`
- Embedded digest fields: `preload_digest`, `trace_digest`, `cell_trace_digest`
- Measurement contour: structured-output benchmark
- Canonical fixture candidate: default full-trace JSON produced by the registered full-trace command
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Conditional target mode: `Trace Explorer` when all full-trace collections are present and valid
- Conditional target mode: `Ternary Transition Visualizer` when all required transition records are present and valid
- Implementation status: `not_implemented`

#### `configuration` required fields

- `cells`;
- `steps`;
- `seed`;
- `scheduler`;
- `transition_fraction`;
- `request_lanes`;
- `gamma_nominal`;
- `fractal_alpha`;
- `thermal_beta`;
- `ambient_heat`;
- `thermal_time_constant`;
- `thermal_soft_limit`;
- `thermal_hard_limit`;
- `coupling_nominal`;
- `delay_alpha`;
- `thermal_diffusion_gain`.

#### `kernel` required fields

- `balanced_ternary_states`;
- `active_neutral_state`;
- `neutral_routes`;
- `scheduler_modes`;
- `actual_direct_events_target`.

#### `hardware_profile` required fields

- `scalar`;
- `unit`;
- `phase`;
- `gamma`;
- `state_encoding`.

#### Processor-tick `trace` row fields

- `tick`;
- `reset_n`;
- `scheduler_mode`;
- `scheduler_state`;
- `scheduler_state_name`;
- `auto_targets_enable`;
- `request_valid_mask`;
- `request_cell_ids`;
- `request_target_states`;
- `gamma_noise_update_valid`;
- `gamma_noise_target_q16`;
- `states_packed`;
- `states_packed_hex`;
- `states_human`;
- `pending_route_count`;
- `switch_load_q16`;
- `heat_global_q16`;
- `global_phase_coherence_q30`;
- `C_q16`;
- `P_q16`;
- `C_minus_P_q16`;
- `requested_direct_events`;
- `prevented_direct_events`;
- `neutral_routed_events`;
- `neutralized_conflicts`;
- `actual_direct_events`;
- `reserved_state_events`;
- `queue_overflow_events`;
- `changes`.

#### Per-cell `cell_trace` row fields

- `tick`;
- `cell_id`;
- `state_code`;
- `phase_word`;
- `frequency_target_q16`;
- `frequency_current_q16`;
- `frequency_lag_q16`;
- `generated_power_q16`;
- `heat_q16`;
- `thermal_overload_q16`;
- `gamma_noise_state_q16`;
- `gamma_effective_word`;
- `thermal_node_factor_q30`;
- `coupling_field_q16`.

#### `route_events` row fields

- `tick`;
- `cell_id`;
- `target_state`;
- `ready_tick`;
- `route_status`.

Registered `route_status` values:

- `pending`;
- `applied`.

### `frp.structured_output.v1.7.0` with `kind = self_test`

- Registry key: `frp.structured_output.v1.7.0#self_test`
- Exact schema identifier: `frp.structured_output.v1.7.0`
- Required discriminator: `kind = self_test`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python frp_prototype_v1_7_0.py --mode self-test --output json`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `status`, `check_count`, `checks`, `neutral_route_validation`, `scheduler_validation`, `request_lane_order_validation`, `queue_exhaustion_validation`, `fixed_point_validation`, `encoding_validation`, `topology_validation`, `trigonometric_lut_validation`, `semantic_correlation`, `exact_shadow_replay`, `vector_determinism`, `scaling_validation`
- Optional top-level fields: none documented
- Required check count for the audited producer: `41`
- Required successful check relation: all 41 values in `checks` are `true`
- Qualification contour: M15 implementation-mapping qualification
- Canonical fixture candidate: default self-test JSON produced by the registered command
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

## Benchmark-Matrix Entry

### `frp.m3.benchmark_matrix.v1.7.0`

- Registry key: `frp.m3.benchmark_matrix.v1.7.0#benchmark_matrix`
- Exact schema identifier: `frp.m3.benchmark_matrix.v1.7.0`
- Required discriminator: `kind = benchmark_matrix`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python frp_prototype_v1_7_0.py --mode benchmark --output json`
- Equivalent producer command: `python frp_prototype_v1_7_0.py --export-benchmark-matrix`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `rows`
- Optional top-level fields: none produced by the audited current producer
- Required row count for the default audited producer: `5`
- Measurement contour: M3 benchmark matrices
- Canonical fixture candidate: default benchmark-matrix JSON produced by either registered command
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

## M15 Export Entries

### `frp.m15.fixed_point_interface_profile.v1.7.0`

- Registry key: `frp.m15.fixed_point_interface_profile.v1.7.0#fixed_point_interface_profile`
- Exact schema identifier: `frp.m15.fixed_point_interface_profile.v1.7.0`
- Required discriminator: `kind = fixed_point_interface_profile`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-fixed-point-interface-profile`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `inherited_boundary`, `profile`, `topology_fixed_point_profile`, `thermal_fixed_point_profile`, `fixed_point_topology_sum_exact`, `fixed_point_thermal_sum_exact`
- Optional top-level fields: none documented
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default fixed-point interface profile JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

### `frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0`

- Registry key: `frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0#balanced_ternary_hardware_encoding_map`
- Exact schema identifier: `frp.m15.balanced_ternary_hardware_encoding_map.v1.7.0`
- Required discriminator: `kind = balanced_ternary_hardware_encoding_map`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-balanced-ternary-hardware-encoding-map`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `inherited_boundary`, `state_encoding`, `reserved_state_code`, `packed_state_vector`, `request_interface`, `scheduler_mode_encoding`, `scheduler_state_encoding`
- Optional top-level fields: none documented
- Canonical ternary domain: `-1, 0, 1`
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default balanced ternary hardware encoding map JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Auxiliary target mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

### `frp.m15.quantized_reference_shadow_model.v1.7.0`

- Registry key: `frp.m15.quantized_reference_shadow_model.v1.7.0#quantized_reference_shadow_model`
- Exact schema identifier: `frp.m15.quantized_reference_shadow_model.v1.7.0`
- Required discriminator: `kind = quantized_reference_shadow_model`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-quantized-reference-shadow-model`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `inherited_boundary`, `execution_model`, `configuration`, `numeric_profile`, `preload`, `summary`, `trace_digest`, `cell_trace_digest`
- Optional top-level fields: none documented
- Embedded digest fields: `trace_digest`, `cell_trace_digest`
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default quantized reference shadow model JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

### `frp.m15.cycle_exact_reference_trace.v1.7.0`

- Registry key: `frp.m15.cycle_exact_reference_trace.v1.7.0#cycle_exact_reference_trace`
- Exact schema identifier: `frp.m15.cycle_exact_reference_trace.v1.7.0`
- Required discriminator: `kind = cycle_exact_reference_trace`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-cycle-exact-reference-trace`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `configuration`, `preload`, `summary`, `trace`, `route_events`
- Optional top-level fields: none documented
- Default trace length: `64`
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default cycle-exact reference trace JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Target mode: `Trace Explorer`
- Target mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

### `frp.m15.rtl_comparison_vector_package.v1.7.0`

- Registry key: `frp.m15.rtl_comparison_vector_package.v1.7.0#rtl_comparison_vector_package`
- Exact schema identifier: `frp.m15.rtl_comparison_vector_package.v1.7.0`
- Required discriminator: `kind = rtl_comparison_vector_package`
- Format: JSON package description with an optional written multi-file package
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-rtl-comparison-vector-package`
- Written-package command: `python frp_prototype_v1_7_0.py --export-rtl-comparison-vector-package --vector-output-dir <directory>`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `vector_classes`, `manifest`, `deterministic_package_digest`
- Optional top-level fields: none documented
- Required `manifest` fields: `file_count`, `files`
- Required package file count: `10`
- Published deterministic package digest: `703dd4b56f4b34289a2c5bc5521ad4ddc3113bdec8c38238c3244c69cb4d58df`
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default JSON package description and complete written ten-file deterministic package
- Upstream fixture availability: package description and ten-file package are not committed as instances
- Target mode: `Artifact Auditor`
- Conditional target mode: `Trace Explorer` for registered trace members inside a complete verified package
- Conditional target mode: `Ternary Transition Visualizer` for registered transition members inside a complete verified package
- Implementation status: `not_implemented`

### `frp.m15.systemverilog_testbench_interface_map.v1.7.0`

- Registry key: `frp.m15.systemverilog_testbench_interface_map.v1.7.0#systemverilog_testbench_interface_map`
- Exact schema identifier: `frp.m15.systemverilog_testbench_interface_map.v1.7.0`
- Required discriminator: `kind = systemverilog_testbench_interface_map`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-systemverilog-testbench-interface-map`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `parameters`, `execution_inputs`, `verification_stimulus_inputs`, `comparison_outputs`, `vector_replay_order`
- Optional top-level fields: none documented
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default SystemVerilog testbench interface map JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Execution restriction: SystemVerilog must not be compiled or simulated by Observatory
- Implementation status: `not_implemented`

### `frp.m15.synthesizable_rtl_reference_core.v1.7.0`

- Registry key: `frp.m15.synthesizable_rtl_reference_core.v1.7.0#synthesizable_rtl_reference_core`
- Exact schema identifier: `frp.m15.synthesizable_rtl_reference_core.v1.7.0`
- Required discriminator: `kind = synthesizable_rtl_reference_core`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-synthesizable-rtl-reference-core`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `kernel_requirements`, `planned_rtl_files`, `exact_tick_execution_order`
- Optional top-level fields: none documented
- Published mapped RTL file count: `13`
- Published tick-order count: `26`
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default synthesizable RTL reference-core map JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

### `frp.m15.rtl_assertion_correlation_harness.v1.7.0`

- Registry key: `frp.m15.rtl_assertion_correlation_harness.v1.7.0#rtl_assertion_correlation_harness`
- Exact schema identifier: `frp.m15.rtl_assertion_correlation_harness.v1.7.0`
- Required discriminator: `kind = rtl_assertion_correlation_harness`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-rtl-assertion-correlation-harness`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `assertion_count`, `assertions`, `direct_transition_rules`, `scheduler_modes`, `exact_comparison_rule`
- Optional top-level fields: none documented
- Published assertion count: `13`
- Measurement contour: M15 implementation-mapping matrix
- Canonical fixture candidate: default RTL assertion correlation harness JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

### `frp.m15.reference_rtl_equivalence_report.v1.7.0`

- Registry key: `frp.m15.reference_rtl_equivalence_report.v1.7.0#reference_rtl_equivalence_report`
- Exact schema identifier: `frp.m15.reference_rtl_equivalence_report.v1.7.0`
- Required discriminator: `kind = reference_rtl_equivalence_report`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-reference-rtl-equivalence-report`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `floating_reference_to_quantized_shadow`, `quantized_shadow_deterministic_replay`, `rtl_exact_integer_comparison_contract`
- Optional top-level fields: none documented
- Qualification contour: M15 implementation-mapping qualification
- Canonical fixture candidate: default reference RTL equivalence report JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

### `frp.m15.qualification_closure_manifest.v1.7.0`

- Registry key: `frp.m15.qualification_closure_manifest.v1.7.0#qualification_closure_manifest`
- Exact schema identifier: `frp.m15.qualification_closure_manifest.v1.7.0`
- Required discriminator: `kind = qualification_closure_manifest`
- Format: JSON object
- Exact upstream contract path: `docs/output_schema.md`
- Exact upstream producer path: `frp_prototype_v1_7_0.py`
- Producer version: `1.7.0`
- Producer command: `python frp_prototype_v1_7_0.py --export-qualification-closure-manifest`
- Required top-level fields: `schema`, `kind`, `version`, `milestone`, `artifact_layers`, `checks`, `semantic_correlation`, `exact_shadow_replay`, `vector_manifest`, `status`
- Optional top-level fields: none documented
- Published artifact-layer count: `10`
- Qualification contour: M15 implementation-mapping qualification
- Canonical fixture candidate: default qualification closure manifest JSON
- Upstream fixture availability: not committed as a JSON instance
- Target mode: `Artifact Auditor`
- Implementation status: `not_implemented`

## Comparative Architecture Benchmark Artifacts

The audited upstream repository commits six JSON artifacts under:

`benchmarks/architecture_comparison/`

These artifacts belong to the Comparative Architecture Benchmark Suite or Hardware-Informed Sensitivity Qualification.

They contain profiles, aggregate results, qualification checks, and declared digests.

They do not contain the raw processor-tick trace arrays required by Trace Explorer.

### Schema-Free Workload Profile

- Registry key: `architecture_comparison.workload_profile_v1`
- Embedded schema identifier: none
- Format: JSON object
- Exact upstream path: `benchmarks/architecture_comparison/profiles/workload_profile_v1.json`
- Exact upstream loader and validator: `benchmarks/architecture_comparison/common_workload.py`
- Profile version: `v1` from the published filename
- Upstream release association: `FRP v1.8.0 / M16`
- Validation command: `python benchmarks/architecture_comparison/common_workload.py --profile benchmarks/architecture_comparison/profiles/workload_profile_v1.json --output json`
- Required top-level fields: none; the upstream loader defines defaults for all recognized fields
- Recognized optional fields: `num_cells`, `command_count`, `seed`, `issue_policy`, `max_completion_cycles_per_command`, `final_cooldown_cycles`
- Unknown-field policy: rejected by the upstream loader
- Canonical committed field count: `6`
- Canonical committed values: `num_cells = 16`, `command_count = 256`, `seed = 76`, `issue_policy = transaction_serial`, `max_completion_cycles_per_command = 64`, `final_cooldown_cycles = 32`
- Declared artifact digest: none
- Published generated-workload binding digest: `8386174d0a4751af26cc68bf46a5494cf0e58a3c14fc59ff46830a21645f0562`
- Digest distinction: the published workload binding digest identifies the generated semantic workload package, not the raw profile-file bytes
- Measurement contour: Comparative Architecture Benchmark Suite
- Canonical fixture candidate: the committed upstream file at the exact registered path
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

The schema identifier `frp.benchmark.semantic_workload.v1` belongs to the generated workload package. It must not be assigned to this schema-free profile file.

### `frp.benchmark.normalized_cost_profile.v1`

- Registry key: `frp.benchmark.normalized_cost_profile.v1`
- Exact schema identifier: `frp.benchmark.normalized_cost_profile.v1`
- Format: JSON object
- Exact upstream path: `benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json`
- Exact upstream producer and validator: `benchmarks/architecture_comparison/common_cost_model.py`
- Schema version: `v1`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python benchmarks/architecture_comparison/common_cost_model.py --write-default-profile benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json`
- Validation command: `python benchmarks/architecture_comparison/common_cost_model.py --profile benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json --output json`
- Required top-level fields: `schema`, `suite_name`, `profile_name`, `cost_unit`, `costs`, `cost_profile_sha256`
- Optional top-level fields: none in the canonical producer output
- Declared digest field: `cost_profile_sha256`
- Declared digest: `4c4a470150ecc182c9a51eaefc0bcba0353e71160d16c6c6afd28a39c23b05bc`
- Measurement contour: Comparative Architecture Benchmark Suite
- Canonical fixture candidate: the committed upstream file at the exact registered path
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

### `frp.benchmark.thermal_proxy_profile.v1`

- Registry key: `frp.benchmark.thermal_proxy_profile.v1`
- Exact schema identifier: `frp.benchmark.thermal_proxy_profile.v1`
- Format: JSON object
- Exact upstream path: `benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json`
- Exact upstream producer and validator: `benchmarks/architecture_comparison/common_thermal_model.py`
- Schema version: `v1`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python benchmarks/architecture_comparison/common_thermal_model.py --write-default-profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json`
- Validation command: `python benchmarks/architecture_comparison/common_thermal_model.py --profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json --output json`
- Required top-level fields: `schema`, `suite_name`, `profile_name`, `temperature_unit`, `ambient_temperature_proxy`, `thermal_decay`, `thermal_gain`, `update_equation`, `thermal_profile_sha256`
- Optional top-level fields: none in the canonical producer output
- Declared digest field: `thermal_profile_sha256`
- Declared digest: `8cc2992f5699c47c88e81c17a4a5f0c8ff5bb7a5b32ebf73ab0e5a0f9c5494c8`
- Measurement contour: Comparative Architecture Benchmark Suite
- Canonical fixture candidate: the committed upstream file at the exact registered path
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

### `frp.benchmark.hardware_sensitivity_cost_profile.v1`

- Registry key: `frp.benchmark.hardware_sensitivity_cost_profile.v1`
- Exact schema identifier: `frp.benchmark.hardware_sensitivity_cost_profile.v1`
- Format: JSON object
- Exact upstream path: `benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json`
- Exact upstream validator: `benchmarks/architecture_comparison/validate_hardware_sensitivity_profile.py`
- Profile source: committed upstream profile artifact
- Schema version: `v1`
- Upstream release association: `FRP v1.8.0 / M16`
- Validation command: `python benchmarks/architecture_comparison/validate_hardware_sensitivity_profile.py --profile benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json --output json`
- Required top-level fields: `schema`, `suite_name`, `profile_name`, `profile_role`, `profile_status`, `baseline_profile`, `baseline_result`, `reference_basis`, `provenance_map`, `normalization_reference`, `coefficient_order`, `coefficients`, `scenario_order`, `scenario_vectors`, `digest_contract`, `evaluation_contract`, `validation_contract`, `cost_profile_sha256`
- Optional top-level fields: none
- Unknown-field policy: the upstream validator requires the exact root field set
- Declared digest field: `cost_profile_sha256`
- Declared digest: `3814925a54d274bd43ab4576b6e60b53f60a2dfca9520d533ab49700c11dd553`
- Qualification contour: Hardware-Informed Sensitivity Qualification
- Canonical fixture candidate: the committed upstream file at the exact registered path
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Implementation status: `not_implemented`

### `frp.benchmark.architecture_comparison.v1`

- Registry key: `frp.benchmark.architecture_comparison.v1`
- Exact schema identifier: `frp.benchmark.architecture_comparison.v1`
- Format: JSON object
- Exact upstream path: `benchmarks/architecture_comparison/results/reference_comparison_seed_76.json`
- Exact upstream producer: `benchmarks/architecture_comparison/run_architecture_comparison.py`
- Schema version: `v1`
- FRP semantic-reference version recorded by the package: `1.7.0`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python benchmarks/architecture_comparison/run_architecture_comparison.py --workload-profile benchmarks/architecture_comparison/profiles/workload_profile_v1.json --cost-profile benchmarks/architecture_comparison/profiles/normalized_cost_profile_v1.json --thermal-profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json --frp-scheduler 7/1 --write benchmarks/architecture_comparison/results/reference_comparison_seed_76.json --output text`
- Required top-level fields: `schema`, `suite_name`, `benchmark_kind`, `frp_reference_version`, `frp_scheduler`, `architecture_order`, `workload_profile`, `workload_sha256`, `cost_profile`, `cost_profile_sha256`, `thermal_profile`, `thermal_profile_sha256`, `architectures`, `comparison_matrix`, `integrity`, `qualification`, `comparison_package_sha256`
- Optional top-level fields: none in the canonical producer output
- Declared package digest field: `comparison_package_sha256`
- Declared package digest: `5a4be61ce7fd6bc680bbd8bc28bfe7cc9d2ad35adddf642cecff111fbd503d6a`
- Bound workload digest: `8386174d0a4751af26cc68bf46a5494cf0e58a3c14fc59ff46830a21645f0562`
- Bound normalized cost-profile digest: `4c4a470150ecc182c9a51eaefc0bcba0353e71160d16c6c6afd28a39c23b05bc`
- Bound thermal-profile digest: `8cc2992f5699c47c88e81c17a4a5f0c8ff5bb7a5b32ebf73ab0e5a0f9c5494c8`
- Measurement contour: Comparative Architecture Benchmark Suite
- Canonical fixture candidate: the committed upstream file at the exact registered path
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Exclusion reason: the committed package contains aggregate evaluations and digests, not raw processor-tick trace arrays
- Implementation status: `not_implemented`

### `frp.benchmark.hardware_sensitivity_comparison.v1`

- Registry key: `frp.benchmark.hardware_sensitivity_comparison.v1`
- Exact schema identifier: `frp.benchmark.hardware_sensitivity_comparison.v1`
- Format: JSON object
- Exact upstream path: `benchmarks/architecture_comparison/results/reference_comparison_seed_76_hardware_sensitivity_v1.json`
- Exact upstream producer: `benchmarks/architecture_comparison/run_hardware_sensitivity_comparison.py`
- Schema version: `v1`
- FRP semantic-reference version recorded by the package: `1.7.0`
- Upstream release association: `FRP v1.8.0 / M16`
- Producer command: `python benchmarks/architecture_comparison/run_hardware_sensitivity_comparison.py --workload-profile benchmarks/architecture_comparison/profiles/workload_profile_v1.json --hardware-sensitivity-profile benchmarks/architecture_comparison/profiles/hardware_sensitivity_cost_profile_v1.json --thermal-profile benchmarks/architecture_comparison/profiles/thermal_proxy_profile_v1.json --frp-scheduler 7/1 --write benchmarks/architecture_comparison/results/reference_comparison_seed_76_hardware_sensitivity_v1.json --output text`
- Required top-level fields: `schema`, `suite_name`, `benchmark_kind`, `frp_reference_version`, `frp_scheduler`, `architecture_order`, `workload_profile`, `workload_sha256`, `hardware_sensitivity_profile`, `hardware_sensitivity_profile_sha256`, `profile_validation`, `baseline_binding`, `thermal_profile`, `thermal_profile_sha256`, `raw_trace_ledger`, `raw_trace_set_sha256`, `scenarios`, `ranking_stability`, `integrity`, `qualification`, `hardware_sensitivity_package_sha256`
- Optional top-level fields: none in the canonical producer output
- Declared package digest field: `hardware_sensitivity_package_sha256`
- Declared package digest: `a44cf392d946e3b5c21dffbaa1d726d31da326a007e2908914f6477215261ea0`
- Declared raw trace-set digest field: `raw_trace_set_sha256`
- Declared raw trace-set digest: `42444ea48fc4a00fbc747e0392d218f624896c9e934b1031d38a8acf1a030952`
- Bound hardware sensitivity profile digest: `3814925a54d274bd43ab4576b6e60b53f60a2dfca9520d533ab49700c11dd553`
- Bound workload digest: `8386174d0a4751af26cc68bf46a5494cf0e58a3c14fc59ff46830a21645f0562`
- Bound thermal-profile digest: `8cc2992f5699c47c88e81c17a4a5f0c8ff5bb7a5b32ebf73ab0e5a0f9c5494c8`
- Qualification contour: Hardware-Informed Sensitivity Qualification
- Canonical fixture candidate: the committed upstream file at the exact registered path
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer`
- Exclusion reason: `raw_trace_ledger` records trace identities and relations but does not contain the raw event traces
- Implementation status: `not_implemented`

## M15 Deterministic Package Member Registry

The registered M15 deterministic package contains exactly ten files.

The complete package is produced by:

`python frp_prototype_v1_7_0.py --export-rtl-comparison-vector-package --vector-output-dir <directory>`

The package is not committed in the audited upstream repository.

### Registered Package Members

| Exact filename | Embedded identifier | Format | Target mode |
|---|---|---|---|
| `frp_m15_kernel_vectors.vec` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited vector text | Artifact Auditor; Trace Explorer; Ternary Transition Visualizer |
| `frp_m15_pending_routes.trace` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited route trace | Artifact Auditor; Ternary Transition Visualizer |
| `frp_m15_scheduler_free_vectors.vec` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited vector text | Artifact Auditor; Trace Explorer; Ternary Transition Visualizer |
| `frp_m15_scheduler_7_1_vectors.vec` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited vector text | Artifact Auditor; Trace Explorer; Ternary Transition Visualizer |
| `frp_m15_scheduler_1_7_vectors.vec` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited vector text | Artifact Auditor; Trace Explorer; Ternary Transition Visualizer |
| `frp_m15_full_correlation_vectors.vec` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited vector text | Artifact Auditor; Trace Explorer; Ternary Transition Visualizer |
| `frp_m15_cell_trace.vec` | `format_version = frp.m15.vector.v1` | Headered pipe-delimited cell trace | Artifact Auditor; Trace Explorer |
| `frp_m15_reference_preload.json` | none | JSON object | Artifact Auditor |
| `frp_m15_trig_lut_q30.vec` | none | Headered lookup-table text | Artifact Auditor |
| `frp_m15_sha256_manifest.json` | none | JSON filename-to-digest map | Artifact Auditor |

All ten members have implementation status:

`not_implemented`

The three members without an embedded identifier may be recognized only by exact filename, exact package role, size, and digest inside a complete verified package.

### `frp.m15.vector.v1` Header

Required header fields:

- `format_version`;
- `frp_version`;
- `milestone`;
- `trace_kind`;
- `cells`;
- `hierarchy_depth`;
- `request_lanes`;
- `transition_fraction`;
- `scheduler_mode`;
- `fractal_alpha`;
- `thermal_beta`;
- `scalar_format`;
- `unit_format`;
- `phase_format`;
- `seed`;
- `trace_steps`;
- `column_definition`.

Required format identifier:

`frp.m15.vector.v1`

Registered producer version:

`1.7.0`

### Primary Vector Columns

The kernel, scheduler, and full-correlation vector files use:

- `TICK`;
- `RESET_N`;
- `SCHED_MODE`;
- `SCHED_STATE`;
- `AUTO_TARGETS_ENABLE`;
- `REQ_VALID_MASK`;
- `REQ_CELL_IDS`;
- `REQ_TARGET_STATES`;
- `GAMMA_UPDATE_VALID`;
- `GAMMA_NOISE_TARGETS_Q`;
- `STATES_PACKED`;
- `PENDING_ROUTE_COUNT`;
- `SWITCH_LOAD_Q`;
- `HEAT_GLOBAL_Q`;
- `COHERENCE_GLOBAL_Q`;
- `C_Q`;
- `P_Q`;
- `C_MINUS_P_Q`;
- `REQUESTED_DIRECT_EVENTS`;
- `PREVENTED_DIRECT_EVENTS`;
- `NEUTRAL_ROUTED_EVENTS`;
- `NEUTRALIZED_CONFLICTS`;
- `ACTUAL_DIRECT_EVENTS`.

### Pending-Route Columns

`frp_m15_pending_routes.trace` uses:

- `TICK`;
- `ROUTE_INDEX`;
- `CELL_ID`;
- `TARGET_STATE_CODE`;
- `READY_TICK`;
- `ROUTE_STATUS`.

### Cell-Trace Columns

`frp_m15_cell_trace.vec` uses:

- `TICK`;
- `CELL_ID`;
- `STATE_CODE`;
- `PHASE_WORD`;
- `FREQUENCY_TARGET_Q`;
- `FREQUENCY_CURRENT_Q`;
- `FREQUENCY_LAG_Q`;
- `GENERATED_POWER_Q`;
- `HEAT_Q`;
- `THERMAL_OVERLOAD_Q`;
- `GAMMA_NOISE_STATE_Q`;
- `GAMMA_EFFECTIVE_WORD`;
- `THERMAL_NODE_FACTOR_Q`;
- `COUPLING_FIELD_Q`.

### Reference Preload Fields

`frp_m15_reference_preload.json` contains:

- `cells`;
- `scheduler`;
- `seed`;
- `states`;
- `states_packed_hex`;
- `phase_words`;
- `frequency_target_q16`;
- `frequency_current_q16`;
- `heat_q16`;
- `gamma_noise_state_q16`;
- `gamma_noise_target_q16`.

This file has no embedded schema identifier. Observatory must not assign one.

### Trigonometric Lookup Table

`frp_m15_trig_lut_q30.vec` contains:

- a descriptive header;
- an `entries` declaration;
- a column-format declaration;
- indexed `sin_q30` rows.

This file has no `format_version` field. It is valid only as a registered member of a verified M15 package.

### Internal SHA-256 Manifest

`frp_m15_sha256_manifest.json` maps each of the other nine package filenames to its SHA-256 digest.

The outer `frp.m15.rtl_comparison_vector_package.v1.7.0` manifest records all ten files with:

- filename;
- byte size;
- SHA-256.

The internal SHA-256 manifest must not be expected to contain its own digest.

## M16 Qualification Evidence Registry

M16 qualification evidence in the audited repository is published primarily as Markdown documents and workflow records.

These records have no machine-readable `frp.m16.*` schema identifier.

They are evidence inputs for Artifact Auditor, not processor-tick inputs for Trace Explorer.

| Exact upstream path | Evidence role | Qualification contour |
|---|---|---|
| `FRP_VALIDATION_INDEX_v1_8_0.md` | Current release validation index | M16 RTL qualification and M16 FPGA preparation qualification |
| `TEST_REPORT_v1_8_0.md` | Current release test report | FRP v1.8.0 qualification |
| `RELEASE_CHECKLIST_v1_8_0.md` | Current release checklist | FRP v1.8.0 release evidence |
| `RELEASE_NOTES_v1_8_0.md` | Current release record | FRP v1.8.0 release context |
| `docs/m16_qualification_manifest.md` | M16 qualification manifest | M16 RTL qualification and M16 FPGA preparation qualification |
| `docs/m16_qualification_index.md` | M16 qualification index | M16 RTL qualification and M16 FPGA preparation qualification |
| `docs/m16_public_status_snapshot.md` | Published M16 status snapshot | M16 RTL qualification and M16 FPGA preparation qualification |
| `docs/m16_m15_vector_replay_compatibility_report.md` | M15 vector replay compatibility evidence | M16 RTL qualification |
| `docs/m16_rtl_artifact_boundary_qualification.md` | RTL artifact-boundary qualification | M16 RTL qualification |
| `rtl/m16/ARTIFACTS.md` | RTL artifact manifest | M16 RTL qualification |
| `rtl/m16/SIMULATION_TRANSCRIPT.md` | RTL simulation transcript | M16 RTL qualification |
| `rtl/m16/CLOSURE.md` | RTL closure record | M16 RTL qualification |
| `fpga/m16/SIMULATION_TRANSCRIPT.md` | FPGA preparation simulation transcript | M16 FPGA preparation qualification |
| `fpga/m16/CLOSURE.md` | FPGA preparation closure record | M16 FPGA preparation qualification |

Common evidence properties:

- Format: Markdown
- Embedded schema identifier: none
- Target mode: `Artifact Auditor`
- Excluded mode: `Trace Explorer`
- Excluded mode: `Ternary Transition Visualizer` for per-tick presentation
- Implementation status: `not_implemented`

Registered producer workflows:

- `.github/workflows/frp-m16-rtl-artifact-boundary.yml`;
- `.github/workflows/frp-m16-fpga-preparation.yml`.

Published M16 evidence includes:

- `actual_direct_events = 0`;
- `reserved_state_events = 0`;
- `queue_overflow_events = 0`;
- terminal invariant vector `1111111111`;
- RTL workflow runs `#82` and `#84`;
- FPGA preparation workflow runs `#1` and `#2`;
- recorded `PASS` and `SUCCESS` results.

These values remain bound to their exact evidence records and qualification contours.

The audited archive does not contain the retained CI log, text, or SHA-256 artifact files referenced by the workflows. Their absence must be reported as unavailable rather than reconstructed.

## Producer Schemas Outside the Initial MVP

The following exact schema identifiers are present in current comparative benchmark producers but do not have committed standalone canonical artifacts in the audited repository.

They are not initial MVP registry entries.

| Exact schema identifier | Exact upstream producer | Initial status |
|---|---|---|
| `frp.benchmark.semantic_workload.v1` | `benchmarks/architecture_comparison/common_workload.py` | `blocked_missing_fixture` |
| `frp.benchmark.semantic_workload.self_test.v1` | `benchmarks/architecture_comparison/common_workload.py` | `unsupported` |
| `frp.benchmark.normalized_cost_result.v1` | `benchmarks/architecture_comparison/common_cost_model.py` | `unsupported` |
| `frp.benchmark.normalized_cost_model.self_test.v1` | `benchmarks/architecture_comparison/common_cost_model.py` | `unsupported` |
| `frp.benchmark.thermal_proxy_result.v1` | `benchmarks/architecture_comparison/common_thermal_model.py` | `unsupported` |
| `frp.benchmark.thermal_proxy_model.self_test.v1` | `benchmarks/architecture_comparison/common_thermal_model.py` | `unsupported` |
| `frp.benchmark.architecture_reference_result.v1` | architecture reference producers under `benchmarks/architecture_comparison/` | `blocked_missing_fixture` |
| `frp.benchmark.binary_synchronous_reference.self_test.v1` | `benchmarks/architecture_comparison/binary_synchronous_reference.py` | `unsupported` |
| `frp.benchmark.binary_clock_gated_reference.self_test.v1` | `benchmarks/architecture_comparison/binary_clock_gated_reference.py` | `unsupported` |
| `frp.benchmark.direct_ternary_reference.self_test.v1` | `benchmarks/architecture_comparison/direct_ternary_reference.py` | `unsupported` |
| `frp.benchmark.frp_v1_7_0_adapter.self_test.v1` | `benchmarks/architecture_comparison/frp_v1_7_0_adapter.py` | `unsupported` |
| `frp.benchmark.architecture_comparison.self_test.v1` | `benchmarks/architecture_comparison/run_architecture_comparison.py` | `unsupported` |
| `frp.benchmark.hardware_sensitivity_comparison.self_test.v1` | `benchmarks/architecture_comparison/run_hardware_sensitivity_comparison.py` | `unsupported` |

Before any of these identifiers becomes supported, it must receive a complete registry entry with required fields, optional fields, digest rules, canonical fixtures, negative fixtures, and tests.

## Historical Structured-Output Schemas

Historical schema identifiers remain distinct and unsupported.

| Exact schema identifier | Exact upstream producer | Status |
|---|---|---|
| `frp.structured_output.v0.9.4` | `frp_prototype_v0_9_4.py` | `unsupported` |
| `frp.structured_output.v0.9.5` | `frp_prototype_v0_9_5.py` | `unsupported` |
| `frp.structured_output.v0.9.6` | `frp_prototype_v0_9_6.py` | `unsupported` |
| `frp.structured_output.v0.9.7` | `frp_prototype_v0_9_7.py` | `unsupported` |
| `frp.structured_output.v0.9.8` | `frp_prototype_v0_9_8.py` | `unsupported` |
| `frp.structured_output.v0.9.9` | `frp_prototype_v0_9_9.py` | `unsupported` |
| `frp.structured_output.v1.0.0` | `frp_prototype_v1_0_0.py` | `unsupported` |
| `frp.structured_output.v1.1.0` | `frp_prototype_v1_1_0.py` | `unsupported` |
| `frp.structured_output.v1.2.0` | `frp_prototype_v1_2_0.py` | `unsupported` |
| `frp.structured_output.v1.3.0` | `frp_prototype_v1_3_0.py` | `unsupported` |
| `frp.structured_output.v1.4.0` | `frp_prototype_v1_4_0.py` | `unsupported` |
| `frp.structured_output.v1.5.0` | `frp_prototype_v1_5_0.py` | `unsupported` |
| `frp.structured_output.v1.6.0` | `frp_prototype_v1_6_0.py` | `unsupported` |

No schema identifier is assigned to `frp_prototype_v0_9_3_mobile.py` by this registry.

## Historical Benchmark-Matrix Schemas

| Exact schema identifier | Exact upstream producer | Status |
|---|---|---|
| `frp.m3.benchmark_matrix.v0.9.5` | `frp_prototype_v0_9_5.py` | `unsupported` |
| `frp.m3.benchmark_matrix.v1.5.0` | `frp_prototype_v1_5_0.py` | `unsupported` |
| `frp.m3.benchmark_matrix.v1.6.0` | `frp_prototype_v1_6_0.py` | `unsupported` |

These versions must not be parsed through the `frp.m3.benchmark_matrix.v1.7.0` contract.

## Retained M14 Schema Constants

The current `frp_prototype_v1_7_0.py` source retains the following M14 schema constants:

- `frp.m14.hierarchical_ultrametric_topology_model.v1.6.0`;
- `frp.m14.fractal_coupling_weight_map.v1.6.0`;
- `frp.m14.multiscale_phase_coherence_map.v1.6.0`;
- `frp.m14.cluster_local_thermal_field.v1.6.0`;
- `frp.m14.cross_cluster_propagation_map.v1.6.0`;
- `frp.m14.localized_hotspot_containment_harness.v1.6.0`;
- `frp.m14.dense_hierarchical_equivalence_map.v1.6.0`;
- `frp.m14.physical_domain_correlation_package.v1.6.0`.

These identifiers are not part of the documented twelve-schema FRP v1.8.0 release-facing set.

They have status:

`unsupported`

Their presence as retained constants must not be interpreted as an Observatory support declaration.

## Current Upstream Data Gaps

The audited FRP v1.8.0 repository does not contain:

- formal JSON Schema documents;
- a committed canonical full-trace structured-output JSON artifact;
- a committed `frp.m15.cycle_exact_reference_trace.v1.7.0` JSON artifact;
- the committed ten-file M15 deterministic vector directory;
- a machine-readable M16 per-tick execution trace;
- a machine-readable M16 per-request-lane acceptance and rejection trace;
- machine-readable M16 per-tick transition-capacity and deferral records;
- a machine-readable M16 qualification manifest with the referenced CI artifact digests;
- committed CSV or TSV artifacts;
- a machine-readable v0.9.3 benchmark artifact.

Observatory must not synthesize these missing upstream artifacts.

A future upstream artifact may be added only through a new audit and an explicit registry update.

## Initial Fixture Priority

Canonical fixture work must proceed in this order:

1. committed schema-free workload profile;
2. committed normalized cost profile;
3. committed thermal proxy profile;
4. committed hardware sensitivity profile;
5. committed architecture comparison result;
6. committed hardware sensitivity comparison result;
7. captured default full-trace `frp.structured_output.v1.7.0` artifact;
8. captured default `frp.m15.cycle_exact_reference_trace.v1.7.0` artifact;
9. captured complete M15 deterministic vector package;
10. registered M16 qualification evidence documents.

Generated fixtures must retain their producer command, producer version, source digest, and upstream association.

## Registry Change Requirements

A registry entry may change to `supported` only when:

- the exact artifact identity is stable;
- all required and optional fields are recorded;
- the parser preserves source bytes;
- validation rules are implemented;
- digest rules are implemented where applicable;
- a canonical fixture is committed;
- negative fixtures are committed;
- ordering and relation tests pass;
- provenance tests pass;
- source-immutability tests pass;
- each enabled Observatory mode has integration tests.

An upstream release update does not change this registry automatically.

## Registry Summary

Initial audited inventory:

- twelve current release-facing FRP schema identifiers;
- thirteen current release-facing registry entries after `kind` dispatch;
- six committed comparative benchmark JSON artifacts;
- one schema-free committed workload profile;
- one registered M15 vector format identifier;
- ten deterministic M15 package-member roles;
- no formal JSON Schema documents;
- no machine-readable `frp.m16.*` schema identifier;
- no implemented Observatory parser;
- no supported Observatory schema.

## Author

Maksym Marnov
