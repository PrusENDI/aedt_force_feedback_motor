# Milestone 3.5 Phase A Full-Layer Geometry Precursor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a parameterized, complete, dense, pure-2D Phase A full-layer geometry source that Milestone 4 can use to generate Phase B/C candidates and run three-phase single-layer spacing checks.

**Architecture:** Keep `dxf-copper-v2` as the geometry contract version, reuse V2 naming and base parameters, and use `generation_mode="phase_full_layer"` for Milestone 3.5. Implement a V2-based constrained segment primitive in the independent V3.5 module: keep V2-style output fields, Shapely outline construction, terminal records, diagnostics, and AEDT polyline format, but generate centerlines inside explicit angular ownership windows so the segments can tile into a Phase A full layer. The current sparse `pitch_owned_tile` output is only a topology smoke reference and must not satisfy the exit gate.

**Tech Stack:** Python 3.10 in the PyAEDT environment, unittest, Shapely, existing V2 geometry helpers, plain SVG output.

---

## Current Milestone

Active local stage: `Milestone 3.5: Phase A Full-Layer Geometry Precursor`.

This is a bridge after V2 / Roadmap Milestone 3 and before Milestone 4 / Three-Phase Single-Layer Geometry. It must not implement Phase B/C, six-layer stack, AEDT host execution, DC Conduction, transient solve, final DXF manufacturing output, or old Sector3D scaffold changes.

## File Boundary

Files to modify:

- `docs/superpowers/specs/2026-05-03-motor-validation-master-roadmap.md`: Milestone 3.5 bridge wording.
- `docs/superpowers/specs/2026-05-07-complete-single-phase-topology-design.md`: full-layer precursor design.
- `docs/superpowers/plans/2026-05-07-complete-single-phase-topology.md`: this plan.
- `scripts/dxf_copper_phase_chain.py`: independent Milestone 3.5 geometry module; do not move V3.5 code into `scripts/dxf_copper_geometry.py`.
- `tests/test_dxf_copper_v3_phase_chain.py`: pure Python Milestone 3.5 tests.

Files to create or update during implementation:

- `scripts/build_dxf_copper_v35_phase_a_full_layer.py`: report-only artifact writer for JSON/Markdown/SVG, no AEDT host behavior.

Generated artifacts:

- `artifacts/dxf_copper_v35_phase_a_full_layer.json`
- `reports/dxf_copper_v35_phase_a_full_layer.md`
- `artifacts/dxf_copper_v35_phase_a_full_layer_preview.svg`
- `artifacts/debug_v35_*.svg` after every geometry-changing step.

Files not to modify for Milestone 3.5:

- `scripts/agent_runtime.py`
- `config/project.json`
- `launchers/Queue-Command.ps1`
- `scripts/in_aedt_agent_host.py`
- `scripts/sector3d_scaffold.py`
- `scripts/sector3d_aedt.py`

## Task 1: Rename The Milestone Contract In Tests

**Files:**

- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Write RED tests for full-layer identity**

Update the default-spec test so it expects:

```python
self.assertEqual(spec["milestone"], "Milestone 3.5: Phase A Full-Layer Geometry Precursor")
self.assertEqual(spec["geometry_contract_version"], "dxf-copper-v2")
self.assertEqual(spec["generation_mode"], "phase_full_layer")
self.assertEqual(spec["topology_preset"], "phase_a_full_layer_v2_constrained_segment")
self.assertEqual(spec["geometry_scope"], "v35_phase_a_full_layer_2d")
self.assertEqual(spec["phase"], "A")
self.assertEqual(spec["layer"], "L01")
self.assertEqual(spec["macro_segment_count"], 6)
self.assertEqual(spec["macro_segment_pitch_deg"], 60.0)
self.assertEqual(spec["full_layer_coverage_deg"], 360.0)
self.assertGreaterEqual(spec["turn_count_per_macro_segment"], 4)
self.assertGreaterEqual(spec["radial_lane_count"], 3)
self.assertIn("minimum_radial_fill_ratio", spec)
self.assertIn("minimum_angular_occupancy_ratio", spec)
self.assertIn("minimum_full_layer_centerline_length_mm", spec)
self.assertIn("minimum_full_layer_area_mm2", spec)
self.assertFalse(spec["three_phase_enabled"])
self.assertFalse(spec["six_layer_stack_enabled"])
```

- [ ] **Step 2: Run RED**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_v3_phase_chain -v
```

Expected: FAIL because the implementation still exposes `phase_chain` / sparse tile fields.

## Task 2: Full-Layer Geometry Contract Tests

**Files:**

- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Add RED test for top-level full-layer output**

Add a test named `test_phase_a_full_layer_outputs_v4_usable_geometry_source` with these assertions:

```python
chain = module.build_phase_chain_geometry()
status = module.validate_phase_chain_geometry(chain)

self.assertEqual(chain["generation_mode"], "phase_full_layer")
self.assertEqual(chain["segment_count"], 6)
self.assertIn("full_layer_regions", chain)
self.assertIn("full_layer_outline_groups_xy_mm", chain)
self.assertIn("full_layer_aedt_polyline_regions_mm", chain)
self.assertIn("full_layer_centerline_points_xy_mm", chain)
self.assertEqual(len(chain["full_layer_regions"]), 6)
self.assertEqual(len(chain["full_layer_outline_groups_xy_mm"]), 6)
self.assertEqual(len(chain["full_layer_aedt_polyline_regions_mm"]), 6)
self.assertGreater(sum(len(points) for points in chain["full_layer_outline_groups_xy_mm"]), 100)
self.assertGreater(sum(len(points) for points in chain["full_layer_aedt_polyline_regions_mm"]), 100)
self.assertGreater(len(chain["full_layer_centerline_points_xy_mm"]), 80)
self.assertEqual(chain["diagnostics"]["full_layer_coverage_deg"], 360.0)
self.assertTrue(status["valid"])
self.assertTrue(status["full_layer_coverage_valid"])
self.assertTrue(status["full_layer_self_overlap_free"])
self.assertTrue(status["segment_overlap_free"])
self.assertEqual(chain["logical_connection_policy"], "ordered_segments_with_physical_gap")
self.assertNotIn("full_layer_outline_points_xy_mm", chain)
self.assertNotIn("full_layer_aedt_polyline_points_mm", chain)
```

- [ ] **Step 2: Add RED test that rejects the sparse smoke primitive**

Add `test_sparse_smoke_primitive_does_not_pass_full_layer_gate`:

```python
spec = module.phase_chain_default_spec()
spec["turn_count_per_macro_segment"] = 1
spec["radial_lane_count"] = 1
chain = module.build_phase_chain_geometry(spec)
status = module.validate_phase_chain_geometry(chain)

self.assertFalse(status["valid"])
self.assertIn("radial_fill_ratio_too_low", status["issues"])
self.assertIn("centerline_length_too_short", status["issues"])
```

- [ ] **Step 3: Run RED**

Run the V3.5 test file. Expected: FAIL because full-layer fields and density validation do not exist yet.

## Task 2.1: V2 Reuse And Constraint Tests

**Files:**

- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Add RED test proving naive V2 repetition is not enough**

Add `test_unconstrained_v2_segment_repetition_fails_full_layer_gate`:

```python
spec = module.phase_chain_default_spec()
spec["segment_primitive_mode"] = "unconstrained_v2_repetition"
chain = module.build_phase_chain_geometry(spec)
status = module.validate_phase_chain_geometry(chain)

self.assertFalse(status["valid"])
self.assertTrue(
    "segment_overlap_detected" in status["issues"]
    or "minimum_segment_clearance_violation" in status["issues"]
)
```

- [ ] **Step 2: Add RED test proving constrained segments keep V2-style outputs**

Add `test_constrained_segments_keep_v2_style_geometry_fields`:

```python
v2_module = self._v2_module()
chain = module.build_phase_chain_geometry()

for segment in chain["segments"]:
    self.assertEqual(segment["geometry_contract_version"], "dxf-copper-v2")
    self.assertEqual(segment["metadata"]["corner_policy"], "flat_caps_mitred_joins_no_auto_rounding")
    self.assertEqual(segment["metadata"]["buffer_cap_style"], "flat")
    self.assertEqual(segment["metadata"]["buffer_join_style"], "mitre")
    self.assertIn("centerline_points_xy_mm", segment)
    self.assertIn("outline_points_xy_mm", segment)
    self.assertIn("aedt_polyline_points_mm", segment)
    self.assertIn("terminal_pads", segment)
    self.assertTrue(v2_module.validate_single_layer_geometry(segment)["valid"])
```

- [ ] **Step 3: Run RED**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_v3_phase_chain -v
```

Expected: FAIL until the V2-based constrained primitive is implemented.

## Task 2.2: Logical Continuity Without Physical Bridges

**Files:**

- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Add RED test for logical connections**

Add `test_macro_segments_use_logical_connections_with_physical_gaps`:

```python
chain = module.build_phase_chain_geometry()
status = module.validate_phase_chain_geometry(chain)
segments = chain["segments"]

self.assertEqual(chain["logical_connection_policy"], "ordered_segments_with_physical_gap")
self.assertGreaterEqual(status["minimum_segment_clearance_mm"], chain["spec_summary"]["trace_gap_mm"])
for index, segment in enumerate(segments):
    logical = segment["metadata"]["logical_connections"]
    if index == 0:
        self.assertIsNone(logical["entry_from"])
    else:
        self.assertEqual(logical["entry_from"], segments[index - 1]["segment_id"])
    if index == len(segments) - 1:
        self.assertIsNone(logical["exit_to"])
    else:
        self.assertEqual(logical["exit_to"], segments[index + 1]["segment_id"])
```

- [ ] **Step 2: Add RED test blocking physical bridge output**

Add `test_phase_a_full_layer_does_not_emit_physical_bridge_geometry`:

```python
chain = module.build_phase_chain_geometry()

self.assertFalse(chain["not_evaluated"]["physical_bridge_evaluated"])
self.assertNotIn("bridge_polygons_xy_mm", chain)
self.assertNotIn("physical_bridges", chain)
for segment in chain["segments"]:
    self.assertNotIn("bridge_polygons_xy_mm", segment)
    self.assertNotIn("physical_bridges", segment)
```

Add `test_phase_a_full_layer_exposes_terminal_keepout_metadata`:

```python
chain = module.build_phase_chain_geometry()

self.assertEqual(chain["terminal_keepout_policy"], "metadata_only_not_final_escape")
self.assertIn("terminal_keepouts", chain)
self.assertGreaterEqual(len(chain["terminal_keepouts"]), 2)
for keepout in chain["terminal_keepouts"]:
    self.assertIn("center_xy_mm", keepout)
    self.assertIn("radius_mm", keepout)
    self.assertEqual(keepout["physical_escape_evaluated"], False)
```

- [ ] **Step 3: Run RED**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_v3_phase_chain -v
```

Expected: FAIL until logical connection metadata and physical-bridge exclusions are implemented.

## Task 2.5: Parameterization Contract Tests

**Files:**

- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Add RED tests proving V2-style parameters change real geometry**

Add `test_phase_a_full_layer_parameter_changes_modify_real_geometry`:

```python
base = module.build_phase_chain_geometry()
spec = module.phase_chain_default_spec()
spec["turn_count_per_macro_segment"] = spec["turn_count_per_macro_segment"] + 1
spec["radial_lane_count"] = spec["radial_lane_count"] + 1
spec["macro_guard_angle_deg"] = spec["macro_guard_angle_deg"] + 0.5
variant = module.build_phase_chain_geometry(spec)

self.assertNotEqual(base["full_layer_centerline_points_xy_mm"], variant["full_layer_centerline_points_xy_mm"])
self.assertNotEqual(base["full_layer_outline_groups_xy_mm"], variant["full_layer_outline_groups_xy_mm"])
self.assertNotEqual(base["diagnostics"]["centerline_length_mm"], variant["diagnostics"]["centerline_length_mm"])
self.assertNotEqual(base["diagnostics"]["radial_fill_ratio"], variant["diagnostics"]["radial_fill_ratio"])
```

Add `test_phase_a_full_layer_v2_parameter_changes_propagate`:

```python
base = module.build_phase_chain_geometry()
spec = module.phase_chain_default_spec()
spec["inner_radius_mm"] = spec["inner_radius_mm"] + 1.0
spec["outer_radius_mm"] = spec["outer_radius_mm"] - 1.0
spec["trace_width_mm"] = spec["trace_width_mm"] - 0.25
variant = module.build_phase_chain_geometry(spec)

self.assertNotEqual(base["full_layer_outline_groups_xy_mm"], variant["full_layer_outline_groups_xy_mm"])
self.assertNotEqual(base["diagnostics"]["copper_area_mm2"], variant["diagnostics"]["copper_area_mm2"])
self.assertEqual(variant["spec_summary"]["inner_radius_mm"], spec["inner_radius_mm"])
self.assertEqual(variant["spec_summary"]["outer_radius_mm"], spec["outer_radius_mm"])
self.assertEqual(variant["spec_summary"]["trace_width_mm"], spec["trace_width_mm"])
```

- [ ] **Step 2: Add RED tests for parameter fail-fast behavior**

Add `test_phase_a_full_layer_rejects_inconsistent_macro_pitch`:

```python
spec = module.phase_chain_default_spec()
spec["macro_segment_count"] = 5
spec["macro_segment_pitch_deg"] = 60.0

with self.assertRaisesRegex(ValueError, "macro_segment_count and macro_segment_pitch_deg must cover 360 deg"):
    module.build_phase_chain_geometry(spec)
```

Add `test_phase_a_full_layer_rejects_radius_window_too_small_for_lanes`:

```python
spec = module.phase_chain_default_spec()
spec["inner_radius_mm"] = 28.0
spec["outer_radius_mm"] = 31.0
spec["radial_lane_count"] = 4

with self.assertRaisesRegex(ValueError, "radius window cannot fit radial_lane_count"):
    module.build_phase_chain_geometry(spec)
```

Add `test_phase_a_full_layer_allows_pitch_only_when_it_divides_full_circle`:

```python
spec = module.phase_chain_default_spec()
del spec["macro_segment_count"]
spec["macro_segment_pitch_deg"] = 45.0
chain = module.build_phase_chain_geometry(spec)

self.assertEqual(chain["spec_summary"]["macro_segment_count"], 8)
self.assertEqual(chain["spec_summary"]["macro_segment_pitch_deg"], 45.0)
```

- [ ] **Step 3: Run RED**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_v3_phase_chain -v
```

Expected: FAIL because V3.5 parameterization, `spec_summary`, and fail-fast validation do not exist yet.

## Task 3: V2-Based Constrained Full-Layer Generator

**Files:**

- Modify: `scripts/dxf_copper_phase_chain.py`

- [ ] **Step 1: Update constants and default spec**

Change the public constants to:

```python
V35_PHASE_FULL_LAYER_MILESTONE = "Milestone 3.5: Phase A Full-Layer Geometry Precursor"
V35_PHASE_FULL_LAYER_PRESET = "phase_a_full_layer_v2_constrained_segment"
V35_PHASE_FULL_LAYER_SCOPE = "v35_phase_a_full_layer_2d"
```

Update `phase_chain_default_spec()` to keep the function name for compatibility but return the full-layer defaults:

```python
"generation_mode": "phase_full_layer",
"macro_segment_count": 6,
"macro_segment_pitch_deg": 60.0,
"full_layer_coverage_deg": 360.0,
"turn_count_per_macro_segment": 4,
"radial_lane_count": 4,
"macro_guard_angle_deg": 2.0,
"segment_primitive_mode": "v2_constrained_full_phase_segment",
"minimum_radial_fill_ratio": 0.60,
"minimum_angular_occupancy_ratio": 0.70,
"minimum_full_layer_centerline_length_mm": 280.0,
"minimum_full_layer_area_mm2": 900.0,
```

Keep `phase_segment_count` and `segment_pitch_deg` only as backward-compatible aliases set from the macro fields.

- [ ] **Step 1.5: Implement parameter normalization and fail-fast validation**

`_as_phase_chain_spec()` must:

- Start from `phase_chain_default_spec()`.
- Merge caller overrides without mutating the input.
- Keep V2 names authoritative for units, radii, trace width/gap, terminal sizing, and AEDT handshake.
- Derive `macro_segment_pitch_deg = 360.0 / macro_segment_count` when the caller changes only `macro_segment_count`.
- Derive `macro_segment_count = int(360.0 / macro_segment_pitch_deg)` when the caller changes only `macro_segment_pitch_deg` and it divides 360 into an integer count.
- Reject inconsistent `macro_segment_count * macro_segment_pitch_deg != 360.0`.
- Use `provided_keys = set(spec or {})` to distinguish caller overrides from defaults.
- Reject radius windows that cannot fit `radial_lane_count` lanes with `trace_width_mm` and `trace_gap_mm` using `required_radial_span_mm = radial_lane_count * trace_width_mm + (radial_lane_count - 1) * trace_gap_mm`.
- Reject guard angles that leave no usable angular span.
- Populate a `spec_summary` containing the effective V2 and V3.5 parameters.

- [ ] **Step 2: Implement V2-based constrained segment generation**

Replace the sparse tile path with a V2-style constrained segment primitive:

- For each of 6 macro segments, reserve `macro_guard_angle_deg` on both sides.
- Generate the segment centerline inside `usable_start_angle_deg..usable_end_angle_deg` using V2-style slot pitch and turn-count semantics.
- Reuse V2-style radius window, trace width/gap, flat caps, mitred joins, terminal record shape, diagnostics names, and AEDT polyline output.
- Use `turn_count_per_macro_segment` and `radial_lane_count` to keep the V2-style path dense enough without exceeding the segment angular ownership window.
- Keep 1x1mm logical contact stubs small and label them as non-final terminal escape geometry.
- Keep neighboring macro segments physically separated; do not generate bridge polygons or jumper traces.
- Add `metadata.logical_connections.entry_from` and `metadata.logical_connections.exit_to` on each segment.
- Store each macro segment in `segments[]`.
- Union segment polygons to derive full-layer diagnostics, but do not merge away segment debug identity.

- [ ] **Step 3: Expose full-layer fields**

The built chain must include:

```python
"full_layer_centerline_points_xy_mm": [...],
"full_layer_regions": [
    {
        "region_id": "A_L01_R01",
        "source_segment_id": "A_L01_S01",
        "outline_points_xy_mm": [...],
        "aedt_polyline_points_mm": [...],
        "physical_connection": "isolated_macro_segment",
        "logical_connections": {...}
    }
],
"full_layer_outline_groups_xy_mm": [[...], ...],
"full_layer_aedt_polyline_regions_mm": [[...], ...],
"phase_transform_policy": {
    "type": "angular_offset_from_phase_a",
    "phase_b_offset_deg": 120.0,
    "phase_c_offset_deg": 240.0,
    "candidate_generation_stage": "Milestone 4"
}
```

The built chain must also include:

```python
"logical_connection_policy": "ordered_segments_with_physical_gap",
"terminal_keepout_policy": "metadata_only_not_final_escape",
"terminal_keepouts": [...],
"spec_summary": {
    "generation_mode": "phase_full_layer",
    "inner_radius_mm": ...,
    "outer_radius_mm": ...,
    "trace_width_mm": ...,
    "trace_gap_mm": ...,
    "slot_pitch_deg": ...,
    "macro_segment_count": ...,
    "macro_segment_pitch_deg": ...,
    "turn_count_per_macro_segment": ...,
    "radial_lane_count": ...,
    "macro_guard_angle_deg": ...,
    "minimum_radial_fill_ratio": ...,
    "minimum_angular_occupancy_ratio": ...,
    "minimum_full_layer_centerline_length_mm": ...,
    "minimum_full_layer_area_mm2": ...,
    "max_outer_diameter_mm": ...
}
```

- [ ] **Step 4: Generate debug SVG**

After this geometry change, write:

```text
artifacts/debug_v35_v2_constrained_full_layer_first_pass.svg
```

Expected visual target: six labeled macro segments forming a complete dense Phase A ring, with V2-style routed turns inside each segment and no quadrant-size empty space.

## Task 4: Full-Layer Validation Metrics

**Files:**

- Modify: `scripts/dxf_copper_phase_chain.py`
- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Add RED metric assertions**

Extend the validation-pass test to assert:

```python
self.assertGreaterEqual(status["radial_fill_ratio"], chain["spec_summary"]["minimum_radial_fill_ratio"])
self.assertGreaterEqual(status["angular_occupancy_ratio"], chain["spec_summary"]["minimum_angular_occupancy_ratio"])
self.assertGreaterEqual(status["centerline_length_mm"], chain["spec_summary"]["minimum_full_layer_centerline_length_mm"])
self.assertGreaterEqual(status["copper_area_mm2"], chain["spec_summary"]["minimum_full_layer_area_mm2"])
self.assertLessEqual(status["bounding_diameter_mm"], chain["spec_summary"]["max_outer_diameter_mm"])
self.assertEqual(chain["blocking_issues"], [])
self.assertTrue(chain["v35_full_layer_passed"])
```

- [ ] **Step 2: Implement validation metrics**

`validate_phase_chain_geometry()` must compute:

- `full_layer_coverage_valid`
- `full_layer_self_overlap_free`
- `segment_overlap_free`
- `minimum_segment_clearance_mm`
- `radial_fill_ratio`
- `angular_occupancy_ratio`
- `centerline_length_mm`
- `copper_area_mm2`
- `bounding_diameter_mm`
- `aedt_preflight_passed`

Issue codes must include:

- `full_layer_coverage_not_360_deg`
- `full_layer_outline_invalid`
- `full_layer_region_invalid`
- `segment_overlap_detected`
- `minimum_segment_clearance_violation`
- `physical_bridge_geometry_present`
- `radial_fill_ratio_too_low`
- `angular_occupancy_ratio_too_low`
- `centerline_length_too_short`
- `copper_area_too_low`
- `outline_exceeds_max_outer_diameter`

- [ ] **Step 3: Run tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_v3_phase_chain -v
```

Expected: PASS for V3.5 tests after implementation.

## Task 5: Artifact Writer And SVG Contract

**Files:**

- Create: `scripts/build_dxf_copper_v35_phase_a_full_layer.py`
- Modify: `tests/test_dxf_copper_v3_phase_chain.py`

- [ ] **Step 1: Add artifact writer test**

Add `test_phase_a_full_layer_writer_outputs_v4_handoff_artifacts`:

```python
module = importlib.import_module("build_dxf_copper_v35_phase_a_full_layer")
summary = module.build_report_artifacts(root=ROOT)

self.assertTrue(summary["v35_full_layer_passed"])
self.assertTrue(os.path.exists(os.path.join(ROOT, "artifacts", "dxf_copper_v35_phase_a_full_layer.json")))
self.assertTrue(os.path.exists(os.path.join(ROOT, "reports", "dxf_copper_v35_phase_a_full_layer.md")))
self.assertTrue(os.path.exists(os.path.join(ROOT, "artifacts", "dxf_copper_v35_phase_a_full_layer_preview.svg")))
with open(os.path.join(ROOT, "reports", "dxf_copper_v35_phase_a_full_layer.md"), "r", encoding="utf-8") as handle:
    text = handle.read()
self.assertIn("Milestone 4 handoff", text)
self.assertIn("phase_b_offset_deg", text)
self.assertIn("physical_bridge_evaluated", text)
self.assertIn("ordered_segments_with_physical_gap", text)
self.assertIn("full_layer_regions", text)
self.assertIn("terminal_keepout_policy", text)
self.assertIn("not evaluated", text)
```

- [ ] **Step 2: Implement writer**

The writer must:

- Build the default Phase A full-layer chain.
- Write JSON artifact.
- Write Markdown report with diagnostics and V4 handoff.
- Write SVG preview.
- Raise `RuntimeError` if `v35_full_layer_passed` is false.

- [ ] **Step 3: Generate review SVG**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' scripts\build_dxf_copper_v35_phase_a_full_layer.py
```

Expected:

- `artifacts/dxf_copper_v35_phase_a_full_layer_preview.svg` exists.
- The SVG shows a dense full-circle Phase A layer, physical gaps between macro segments, and logical connection markers only; it must not show solid bridge copper across segment boundaries.

## Task 6: Regression Verification

**Files:**

- No new files.

- [ ] **Step 1: Run V1/V2/V3.5 tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_dxf_copper_geometry tests.test_dxf_copper_v2_contract tests.test_dxf_copper_mvp_contract tests.test_dxf_copper_v3_phase_chain -v
```

Expected: all tests pass.

- [ ] **Step 2: Run py_compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\dxf_copper_geometry.py scripts\dxf_copper_phase_chain.py scripts\build_dxf_copper_v35_phase_a_full_layer.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Human SVG review**

Open or inspect:

```text
artifacts/dxf_copper_v35_phase_a_full_layer_preview.svg
```

Review criteria:

- Six macro segments are visible and labeled.
- The full circle is populated with dense routed copper.
- There are no quadrant-size voids.
- Gaps are visible but not excessive.
- Segment-to-segment continuity is shown as logical metadata/markers, not physical copper bridges.
- Logical contact stubs are small.
- The copper remains inside the `100 mm` bounding circle.

## Stop Conditions

Stop immediately and report to the user if:

- A command fails for a reason other than an expected RED test.
- The dense default cannot meet clearance and fill thresholds simultaneously.
- The SVG is mathematically valid but visually sparse.
- The SVG or JSON includes physical bridge geometry across macro segment boundaries.
- Any change would require modifying V2 source behavior or host/AEDT runtime files.

## Self-Review

- This plan targets Milestone 3.5, not Milestone 4.
- This plan makes V3.5 produce a V4-usable Phase A full-layer 2D source.
- This plan explicitly rejects the current sparse `pitch_owned_tile` output as an exit-gate candidate.
- This plan keeps Phase B/C, AEDT build, solve, and manufacturing DXF out of scope.
- This plan preserves the existing V1/V2 verification requirements.
