# DXF Copper V3.5 Phase A Full-Layer

## V4 handoff

This artifact is a V4 handoff precursor for the Phase A full-layer geometry chain.
Phase B/C geometry is not evaluated here; phase_b_offset_deg is recorded for downstream transforms only.
The physical bridge is not evaluated and remains outside this Milestone 3.5 writer.

## Summary

- v35_full_layer_passed: True
- milestone: Milestone 3.5: Phase A Full-Layer Geometry Precursor
- geometry_scope: v35_phase_a_full_layer_2d
- phase: A
- layer: L01
- segment_count: 6
- ordered_segments_with_physical_gap: True
- phase_b_offset_deg: 120.0
- terminal_keepout_policy: metadata_only_not_final_escape

## Validation

- valid: True
- blocking_issues: []
- validation_issues: []

## Geometry Inventory

- full_layer_regions: 6
- full_layer_outline_groups_xy_mm: 6
- full_layer_aedt_polyline_regions_mm: 6
- full_layer_centerline_points_xy_mm: 6
- logical_connection_policy: ordered_segments_with_physical_gap
- metadata.logical_connection_policy: ordered_segments_with_physical_gap

## Diagnostics

- centerline_length_mm: 865.3461623710929
- copper_area_mm2: 1304.0192435566405
- radial_fill_ratio: 1.0
- angular_occupancy_ratio: 0.9

## Not Evaluated

- aedt_sheet_creation_evaluated: False
- dc_conduction_evaluated: False
- manufacturing_dxf_evaluated: False
- phase_b_geometry_evaluated: False
- phase_c_geometry_evaluated: False
- physical_bridge_evaluated: False
- physical_terminal_escape_evaluated: False
- six_layer_stack_evaluated: False
- solve_evaluated: False
- terminal_escape_evaluated: False
- three_phase_evaluated: False
- three_phase_spacing_evaluated: False

## Policies

- terminal_keepout_policy: metadata_only_not_final_escape
- terminal keepouts are reserved metadata only, not final terminal escape geometry.
- physical bridge routing is intentionally not evaluated in this milestone.
