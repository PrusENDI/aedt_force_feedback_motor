# DXF Copper DC Conduction

This V1 artifact is a DC Conduction sanity-check gate for current-density continuity.

- timestamp: `2026-05-06T12-30-46Z`
- milestone: `Milestone 2: DXF-Compatible 3D Copper MVP`
- host_mode_detected: `True`
- input_artifact_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\artifacts\dxf_copper_mvp.json`
- dc_conduction_ready: `True`
- dxf_compatible_copper_ready: `True`
- terminal_faces_present: `True`
- dc_setup_ready: `True`
- solved: `True`
- current_density_continuity_checked: `True`
- setup_name: `AutoDxfCopper_DC_20260506T122953Z_3791c0f4`
- voltage_assignment: `AutoDxfCopper_Voltage_20260506T122953Z_3791c0f4`
- sink_assignment: `AutoDxfCopper_Sink_20260506T122953Z_3791c0f4`

## Terminal Faces

- `{'area_mm2': 2.4, 'center_xyz_mm': [-33.0, 0.0, -0.15], 'face_id': 137, 'match_distance_mm': 0.0, 'name': 'PhaseA_L01_InputPad', 'role': 'source', 'target_priority': 0, 'target_xy_mm': [-33.0, 0.0]}`
- `{'area_mm2': 2.4, 'center_xyz_mm': [33.0, 0.0, -0.15], 'face_id': 143, 'match_distance_mm': 0.0, 'name': 'PhaseA_L01_ReturnPad', 'role': 'sink', 'target_priority': 0, 'target_xy_mm': [33.0, 0.0]}`

## Current Density Evidence

- solution: `AutoDxfCopper_DC_20260506T122953Z_3791c0f4 : LastAdaptive`
- object_name: `AutoDxfCopper_PhaseA_L01_Sheet`
- method: `field_plot`
- quantity: `Mag_J`
- field_plot_name: `AutoDxfCopper_MagJ_AutoDxfCopper_DC_20260506T122953Z_3791c0f4LastAdaptive`
- field_plot_error: ``
- field_export_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\artifacts\dxf_copper_dc_conduction_fields\AutoDxfCopper_MagJ_AutoDxfCopper_DC_20260506T122953Z_3791c0f4LastAdaptive.aedtplt`
- field_exported: `True`
- available_quantities: `['Volume(AutoDxfCopper_PhaseA_L01_Sheet)']`

## Centerline Current Density Sample

- quantity: `Mag_J`
- sample_export_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\artifacts\dxf_copper_dc_conduction_fields\dxf_copper_centerline_mag_j_samples.fld`
- sample_exported: `True`
- sample_continuity_checked: `True`
- sample_count: `13`
- nonzero_sample_count: `13`
- min_mag_j_a_per_m2: `938577985.9956883`
- max_mag_j_a_per_m2: `983731084.0777106`
- error: ``
- sample_points: `[[-24.0, 0.0, -0.15], [-20.0, 0.0, -0.15], [-16.0, 0.0, -0.15], [-12.0, 0.0, -0.15], [-8.0, 0.0, -0.15], [-4.0, 0.0, -0.15], [0.0, 0.0, -0.15], [4.0, 0.0, -0.15], [8.0, 0.0, -0.15], [12.0, 0.0, -0.15], [16.0, 0.0, -0.15], [20.0, 0.0, -0.15], [24.0, 0.0, -0.15]]`

## Blocking Issues

- `None`

## Manual Actions

- Run the V1 copper MVP build inside AEDT and identify two terminal faces before applying DC Conduction.
- After terminal faces are available, assign voltage and sink boundaries in a Maxwell 3D DC Conduction design.
