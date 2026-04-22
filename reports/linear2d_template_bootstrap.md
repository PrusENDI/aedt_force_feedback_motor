# Linear2D Template Bootstrap Summary

- timestamp: `2026-04-21T13-37-33Z`
- project_name: `linear2d_template`
- design_name_before: `Linearized2D`
- design_name_after: `Linearized2D`
- design_name_matches_required: `True`
- solution_type_before: `Magnetostatic`
- solution_type_after: `Transient`
- saved_template_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\templates/linear2d_template.aedt`
- backup_copy_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\aedt_projects\linear2d_template.aedt`
- setup_name: `Setup_2D`
- setup_exists: `True`
- setup_created: `True`
- setup_deleted_existing: `False`

## Missing Reports

- Torque_Loaded
- FluxLinkage_PhaseA
- BackEMF_LL
- Bmax_BackIron
- Torque_Cogging

## Manual Actions

- Create the missing named reports: Torque_Loaded, FluxLinkage_PhaseA, BackEMF_LL, Bmax_BackIron, Torque_Cogging
- For transient 2D, prefer a winding-style Phase A excitation over loose Current boundaries so FluxLinkage and BackEMF quantities are exposed
- Verify that Setup_2D is a Transient setup and that StopTime/TimeStep resolve to one electrical period with adequate sampling

## Applied Variables

- airgap_mm = `0.7`
- backiron_thickness_mm = `4.5`
- coil_mean_radius_mm = `39.5`
- coil_radial_span_mm = `12.5`
- conductor_thickness_mm = `0.6`
- conductor_width_mm = `2.6`
- inner_diameter_mm = `60.0`
- magnet_segments_per_pole = `1`
- magnet_thickness_mm = `3.4`
- outer_diameter_mm = `98.0`
- parallel_strands = `2`
- phase_current_rms = `3.0`
- pole_arc_ratio = `0.72`
- pole_count = `24`
- slice_radius_mm = `39.5`
- speed_rpm = `250.0`
- turns_per_phase = `66`

## Applied Helper Variables

- coil_inner_radius_mm = `coil_mean_radius_mm - coil_radial_span_mm/2`
- coil_outer_radius_mm = `coil_mean_radius_mm + coil_radial_span_mm/2`
- electrical_frequency_hz = `mechanical_frequency_hz*pole_pairs`
- electrical_period_s = `1/electrical_frequency_hz`
- inner_radius_mm = `inner_diameter_mm/2`
- magnet_arc_mm = `pole_pitch_mm*pole_arc_ratio`
- mean_diameter_mm = `(outer_diameter_mm + inner_diameter_mm)/2`
- mean_radius_mm = `coil_mean_radius_mm`
- mechanical_frequency_hz = `speed_rpm/60`
- mechanical_period_s = `1/mechanical_frequency_hz`
- outer_radius_mm = `outer_diameter_mm/2`
- period_length_mm = `2*pole_pitch_mm`
- pole_pairs = `pole_count/2`
- pole_pitch_mm = `pi*slice_diameter_mm/pole_count`
- slice_diameter_mm = `2*slice_radius_mm`
- transient_stop_time_s = `electrical_period_s`
- transient_time_step_s = `electrical_period_s/48`
