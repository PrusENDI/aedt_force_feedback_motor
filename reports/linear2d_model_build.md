# Linear2D Geometry Build Summary

- timestamp: `2026-04-21T13-43-46Z`
- project_name: `linear2d_template`
- design_name: `Linearized2D`
- solution_type: `Transient`
- saved_template_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\templates/linear2d_template.aedt`
- backup_copy_path: `C:\weizijian\documents\motor\aedt_force_feedback_motor\aedt_projects\linear2d_template.aedt`
- physics_ready_for_screening: `True`

## Geometry Sanity

- mean_diameter_mm: `79.0`
- pole_pitch_mm_est: `10.341076`
- magnet_arc_mm_est: `7.445575`
- pole_arc_ratio: `0.72`
- coil_stack_height_mm_est: `1.2`
- stack_height_mm_est: `9.8`

## Created Objects

- Auto2D_BackIron (material=`steel_1010`)
- Auto2D_Magnet_N (material=`Magnet, permanent, Neodymium N42SH`)
- Auto2D_Magnet_S (material=`Magnet, permanent, Neodymium N42SH`)
- Auto2D_MotionBand (material=`air`)
- Auto2D_AirGap (material=`air`)
- Auto2D_Coil_Pos (material=`copper`)
- Auto2D_Coil_Neg (material=`copper`)

## Blocking Issues

- None

## Warnings

- magnet_segments_per_pole is 1. This is acceptable for a first baseline, but it may overstate ripple/cogging relative to a segmented rotor.
- This Linearized2D scaffold is now intended to support a transient-ready workflow, but physically meaningful back-EMF still benefits from a dedicated moving-rotor/band setup rather than a purely static geometry snapshot.

## Manual Actions

- Assign Magnet, permanent, Neodymium N42SH to Auto2D_Magnet_N and Auto2D_Magnet_S if the script had to fall back to vacuum
- Assign permanent magnet orientation: Auto2D_Magnet_N coercivity approximately (0, 1, 0) and Auto2D_Magnet_S approximately (0, -1, 0) in the current Linearized2D coordinates
- Create one transient-friendly winding from Auto2D_Coil_Pos and Auto2D_Coil_Neg and drive it with the configured phase current waveform tied to phase_current_rms
- Verify that Auto2D_MotionBand encloses the moving rotor-side objects without clipping the stator-side coil objects
- Apply left/right periodic or master/slave boundaries across one model period based on period_length_mm
- Add manual mesh refinement in the 0.7 mm air gap with at least 3 to 4 layers before trusting ripple/cogging results
- If you need physically meaningful transient back-EMF, add a moving-rotor translation/band setup instead of relying on time-varying current alone
- Create the 5 required named reports after solving once
