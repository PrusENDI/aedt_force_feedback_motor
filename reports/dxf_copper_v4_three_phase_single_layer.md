# DXF Copper V4 Three-Phase Single-Layer

## Milestone 4 diagnostic pass

V4 pass means the diagnostic pipeline completed, not that same-plane three-phase copper is physically feasible.

```python
v4_passed = source_passed and overlap_area_calculated
```

## Summary

- v4_passed: True
- source_passed: True
- overlap_area_calculated: True
- same-plane feasibility passed: False
- v5_spatial_handoff_ready: True
- blocking_issues: []
- same_plane_issues: ['phase_pair_overlap_detected:A_B', 'phase_pair_clearance_violation:A_B', 'phase_pair_overlap_detected:B_C', 'phase_pair_clearance_violation:B_C', 'phase_pair_overlap_detected:C_A', 'phase_pair_clearance_violation:C_A']

## Electrical And Mechanical Angles

- phase_offset_angle_units: electrical_degrees
- phase_offsets_deg: {'A': 0.0, 'B': 120.0, 'C': 240.0}
- pole_pairs_count: 7
- mechanical_phase_offsets_deg: {'A': 0.0, 'B': 17.142857142857142, 'C': 34.285714285714285}

## Same-Plane Diagnostics

- phase_to_phase_minimum_clearance_mm: 0.0
- phase_pair_overlap_area_mm2: {'A_B': 478.7205186168014, 'B_C': 478.720518616802, 'C_A': 229.29769267997344}
- A_B: minimum_clearance_mm=0.0, overlap_area_mm2=478.7205186168014
- B_C: minimum_clearance_mm=0.0, overlap_area_mm2=478.720518616802
- C_A: minimum_clearance_mm=0.0, overlap_area_mm2=229.29769267997344

## V5 Spatial Handoff

- recommended_layer_sequence: ['A', 'B', 'C', 'C', 'B', 'A']
- z_assignment_policy: reserved_for_v5
- layer_instances: [{'layer_id': 'L01', 'phase': 'A', 'z_index': 0, 'z_mm': None}, {'layer_id': 'L02', 'phase': 'B', 'z_index': 1, 'z_mm': None}, {'layer_id': 'L03', 'phase': 'C', 'z_index': 2, 'z_mm': None}, {'layer_id': 'L04', 'phase': 'C', 'z_index': 3, 'z_mm': None}, {'layer_id': 'L05', 'phase': 'B', 'z_index': 4, 'z_mm': None}, {'layer_id': 'L06', 'phase': 'A', 'z_index': 5, 'z_mm': None}]

## Terminal Keepout

- terminal keepout count: 36
- terminal keepout conflicts: []

## Not Evaluated

- aedt_evaluated: False
- dc_solve_evaluated: False
- manufacturing_evaluated: False
- physical_bridge_evaluated: False
- physical_terminal_escape_evaluated: False

## Validation

- validation: {'source_passed': True, 'overlap_area_calculated': True, 'v4_passed': True, 'v5_spatial_handoff_ready': True, 'same_plane_feasibility_passed': False, 'same_plane_issues': ['phase_pair_overlap_detected:A_B', 'phase_pair_clearance_violation:A_B', 'phase_pair_overlap_detected:B_C', 'phase_pair_clearance_violation:B_C', 'phase_pair_overlap_detected:C_A', 'phase_pair_clearance_violation:C_A'], 'blocking_issues': []}
