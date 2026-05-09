# Milestone 4 Three-Phase Logical Geometry And V5 Handoff Design

Date: 2026-05-09

## Purpose

Milestone 4 is a diagnostic and handoff milestone between the validated V3.5 Phase A full-layer precursor and Milestone 5 six-layer spatial topology.

The default V3.5 Phase A geometry is intentionally dense: six macro segments occupy almost the entire 360 degree annular working area. A direct same-plane copy/rotation into Phase B and Phase C is therefore expected to create severe overlap. V4 must not hide that result or treat it as an implementation failure.

V4 succeeds when it:

- starts from a passing V3.5 Phase A source;
- generates Phase A/B/C logical geometries by angular transform;
- calculates same-plane overlap and clearance diagnostics;
- emits JSON, Markdown, and SVG evidence;
- prepares a V5-ready spatial stack handoff.

V4 does not succeed by proving same-plane three-phase copper is physically feasible.

## Pass Semantics

The Markdown report and JSON artifact must use this pass rule:

```python
v4_passed = (source_passed is True) and (overlap_area_calculated is True)
```

Definitions:

- `source_passed`: the V3.5 input has `v35_full_layer_passed == True` and `blocking_issues == []`.
- `overlap_area_calculated`: numeric overlap-area diagnostics were produced for all phase pairs `A_B`, `B_C`, and `C_A`.
- `v4_passed`: the V4 diagnostic pipeline executed successfully.
- `same_plane_feasibility_passed`: same-plane physical feasibility; this is expected to be `False` for the dense default geometry.
- `blocking_issues`: only broken V4 execution or broken handoff conditions.
- `same_plane_issues`: expected or discovered same-plane physical conflicts.

Expected default status:

```python
{
    "source_passed": True,
    "overlap_area_calculated": True,
    "same_plane_feasibility_passed": False,
    "v4_passed": True,
    "v5_spatial_handoff_ready": True,
    "blocking_issues": [],
    "same_plane_issues": [
        "phase_pair_overlap_detected:A_B",
        "phase_pair_overlap_detected:B_C",
        "phase_pair_overlap_detected:C_A",
    ],
}
```

## Electrical And Mechanical Angles

`phase_offsets_deg` are electrical angles:

```python
{
    "A": 0.0,
    "B": 120.0,
    "C": 240.0,
}
```

XY geometry rotation must use mechanical angle:

```python
mechanical_rotation_angle_deg = phase_offsets_deg[phase] / pole_pairs_count
```

`pole_pairs_count` is a required positive integer. Invalid values must fail before geometry generation with:

```python
ValueError("pole_pairs_count must be a positive integer")
```

The artifact must record both:

- `phase_offsets_deg`
- `mechanical_phase_offsets_deg`

## Geometry Source And Transform

V4 must use V3.5 Phase A as the canonical geometry source:

- `generation_mode == "phase_full_layer"`
- `geometry_scope == "v35_phase_a_full_layer_2d"`
- `full_layer_regions[]` present
- grouped outline, centerline, and AEDT polyline regions present

Phase B and Phase C must be generated only by angular transform from Phase A `full_layer_regions[]`. V4 must not reinterpret Phase B/C into a different topology or geometry language.

Each phase must retain:

- `full_layer_regions[]`
- `full_layer_outline_groups_xy_mm`
- `full_layer_outline_groups_xyz_mm`
- `full_layer_aedt_polyline_regions_mm`
- `full_layer_centerline_points_xy_mm`
- `full_layer_centerline_points_xyz_mm`
- transformed terminal keepouts
- source lineage metadata

XY fields remain authoritative for Shapely validation. XYZ fields use `[x, y, 0.0]` so V5 can assign real layer z positions later without changing point shape.

## Same-Plane Diagnostics

V4 must calculate phase-pair metrics for:

- `A_B`
- `B_C`
- `C_A`

Each phase pair must include:

- `minimum_clearance_mm`
- `overlap_area_mm2`
- `overlap_detected`
- `clearance_violation`

Positive overlap area must be recorded as `same_plane_issues`, not `blocking_issues`.

Clearance below `minimum_phase_to_phase_clearance_mm` must be recorded as `same_plane_issues`, not `blocking_issues`.

Same-plane feasibility is:

```python
same_plane_feasibility_passed = (
    all(pair["overlap_area_mm2"] == 0.0 for pair in phase_pair_metrics.values())
    and all(pair["minimum_clearance_mm"] >= minimum_phase_to_phase_clearance_mm for pair in phase_pair_metrics.values())
)
```

For the dense V3.5 default, `same_plane_feasibility_passed` is expected to be false.

## V5 Spatial Handoff

V4 must prepare a V5 handoff scaffold without building V5 geometry:

```python
{
    "recommended_layer_sequence": ["A", "B", "C", "C", "B", "A"],
    "layer_instances": [
        {"layer_id": "L01", "phase": "A", "z_index": 0, "z_mm": None},
        {"layer_id": "L02", "phase": "B", "z_index": 1, "z_mm": None},
        {"layer_id": "L03", "phase": "C", "z_index": 2, "z_mm": None},
        {"layer_id": "L04", "phase": "C", "z_index": 3, "z_mm": None},
        {"layer_id": "L05", "phase": "B", "z_index": 4, "z_mm": None},
        {"layer_id": "L06", "phase": "A", "z_index": 5, "z_mm": None},
    ],
    "z_assignment_policy": "reserved_for_v5",
    "interlayer_insulation_evaluated": False,
    "vias_or_physical_bridges_evaluated": False,
}
```

`v5_spatial_handoff_ready` is true when all layer instances exist, each references an available transformed phase, and every phase has XYZ point fields.

V4 must not assign real z spacing, insulation thickness, bridge geometry, vias, or terminal escape routing.

## Terminal Keepouts

Terminal keepouts are feasibility diagnostics only.

V4 must rotate keepout centers with each phase and test:

- keepout circle vs same-plane copper;
- keepout circle vs other-phase copper;
- keepout circle vs other terminal keepout circles.

Conflicts are recorded under `terminal_keepout_conflicts`. They do not make `v4_passed` false unless the conflict calculation itself fails.

The SVG preview must draw terminal keepout markers as red dashed circles with translucent red fill:

```svg
stroke="#dc2626" stroke-dasharray="4 3" fill="rgba(220, 38, 38, 0.16)"
```

## Required Artifacts

V4 must write:

- `artifacts/dxf_copper_v4_three_phase_single_layer.json`
- `reports/dxf_copper_v4_three_phase_single_layer.md`
- `artifacts/dxf_copper_v4_three_phase_single_layer_preview.svg`

The Markdown report must explicitly include:

- `v4_passed`
- `source_passed`
- `overlap_area_calculated`
- `same_plane_feasibility_passed`
- `same_plane_issues`
- `phase_pair_metrics`
- electrical and mechanical phase angles
- `pole_pairs_count`
- `v5_spatial_handoff_ready`
- terminal keepout conflict summary

The artifact writer must still write JSON/Markdown/SVG when same-plane feasibility fails. It should raise only when V4 diagnostic execution fails, such as missing source, invalid angle conversion, missing overlap metrics, missing grouped geometry, radial-wave regression, or incomplete V5 handoff.

## Non-Goals

V4 must not implement or claim:

- same-plane three-phase physical feasibility;
- AEDT sheet creation;
- DC conduction;
- solve readiness;
- manufacturing DXF readiness;
- physical bridges;
- final terminal escape routes;
- real six-layer z spacing;
- interlayer insulation validation.

## Acceptance Criteria

V4 is complete when:

- `v4_passed == True` using `source_passed and overlap_area_calculated`.
- `same_plane_feasibility_passed == False` is allowed and expected for the default dense source.
- `blocking_issues == []`.
- `same_plane_issues` contains overlap/clearance evidence when present.
- JSON/Markdown/SVG artifacts are written.
- V5 handoff scaffold is present and ready.
- V1/V2/V3.5 behavior remains unchanged.
