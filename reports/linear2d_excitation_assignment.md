# Linear2D Excitation Assignment Summary

- timestamp: `2026-04-21T13-47-54Z`
- project_name: `linear2d_template`
- design_name: `Linearized2D`
- design_name_matches_required: `True`
- save_ok: `True`

## Object Checks

- Auto2D_Coil_Pos: exists=`True`
- Auto2D_Coil_Neg: exists=`True`

## Boundary Results

- Current_Coil_Pos on Auto2D_Coil_Pos: assigned=`True`, deleted_existing=`False`, direction_reversed=`False`, details=`assigned with amplitude=phase_current_rms*cos(2*pi*electrical_frequency_hz*time)`
- Current_Coil_Neg on Auto2D_Coil_Neg: assigned=`True`, deleted_existing=`False`, direction_reversed=`True`, details=`assigned with amplitude=phase_current_rms*cos(2*pi*electrical_frequency_hz*time)`

## Winding Result

- winding_name: `PhaseA_Winding`
- assigned: `True`
- used_fallback_current_boundaries: `False`
- details: `transient-friendly winding group assigned`

## Current Excitations Seen

- Current_Coil_Pos
- Current_Coil_Neg

## Manual Actions

- Verify that changing phase_current_rms from 3A to 0A changes the loaded torque result
- If the current direction looks flipped, swap the positive/negative current orientation once in AEDT
