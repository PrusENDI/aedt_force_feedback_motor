# Linear2D Physics Setup Summary

- timestamp: `2026-04-21T13-44-06Z`
- project_name: `linear2d_template`
- design_name: `Linearized2D`
- design_name_matches_required: `True`
- physics_ready_for_screening: `True`
- save_ok: `True`

## Magnet Setup

- Auto2D_Magnet_N: exists=`True`, material=`FFB_N42SH_N`, coercivity=`[0, 1, 0]`, assigned=`True`, details=`material duplicated_or_reused and assigned`
- Auto2D_Magnet_S: exists=`True`, material=`FFB_N42SH_S`, coercivity=`[0, -1, 0]`, assigned=`True`, details=`material duplicated_or_reused and assigned`

## Periodic Boundary

- region_exists: `True`
- left_edge_id: `94`
- right_edge_id: `92`
- assigned: `True`
- boundary_name: `Periodic_X`
- details: `master/slave assigned across one linearized period`

## Air-Gap Mesh

- object_exists: `True`
- assigned: `True`
- mesh_name: `AirGap_Length`
- maximum_length: `airgap_mm/4`
- details: `length mesh assigned for about 4 layers across the air gap`

## Motion Setup

- enabled: `True`
- assigned: `True`
- band_object_name: `Auto2D_MotionBand`
- motion_name: `Motion_LinearRotor`
- velocity_m_per_sec: `1.03410758180664`
- positive_limit_expression: `period_length_mm`
- details: `translation motion assigned`

## Blocking Issues

- None

## Manual Actions

- Run assign_linear2d_excitation.py next so Auto2D_Coil_Pos and Auto2D_Coil_Neg are driven by phase_current_rms
- Solve once and then run create_linear2d_reports.py to generate the 5 required named reports
- After the first solve, visually confirm that N/S magnet orientation, periodic field continuity, air-gap element layering, and motion-band translation all look physically correct
