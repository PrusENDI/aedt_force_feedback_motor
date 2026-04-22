# Linear2D Report Creation Summary

- timestamp: `2026-04-21T14-21-25Z`
- project_name: `linear2d_template`
- design_name: `Linearized2D`
- design_name_matches_required: `True`
- setup_name: `Setup_2D`
- preferred_solution: `Setup_2D : Transient`

## Report Results

- Torque_Loaded: created=`True`, reused=`False`, export_ok=`False`, category=`Transient`, quantity=`Moving1.Force_mag`, context=``, note=`existing report deleted and recreated | created from discovered quantity using domain=Time | no CSV written by SolutionData, manual fallback, or ExportToFile`
- Torque_Cogging: created=`True`, reused=`False`, export_ok=`False`, category=`Transient`, quantity=`Moving1.Force_mag`, context=``, note=`existing report deleted and recreated | created from discovered quantity using domain=Time | no CSV written by SolutionData, manual fallback, or ExportToFile`
- FluxLinkage_PhaseA: created=`True`, reused=`False`, export_ok=`False`, category=`Transient`, quantity=`FluxLinkage(PhaseA_Winding)`, context=``, note=`existing report deleted and recreated | created from discovered quantity using domain=Time | no CSV written by SolutionData, manual fallback, or ExportToFile`
- BackEMF_LL: created=`True`, reused=`False`, export_ok=`False`, category=`Transient`, quantity=`InducedVoltage(PhaseA_Winding)`, context=``, note=`existing report deleted and recreated | created from discovered quantity using domain=Time | no CSV written by SolutionData, manual fallback, or ExportToFile`
- Bmax_BackIron: created=`True`, reused=`False`, export_ok=`False`, category=`Transient`, quantity=`VolumePercentageAbove10Percent`, context=``, note=`existing report deleted and recreated | created from discovered quantity using domain=Time | no CSV written by SolutionData, manual fallback, or ExportToFile`

## Available Report Types

- Transient
- Fields
- Time Averaged Fields

## Manual Actions

- Review report Torque_Loaded manually; selected category=Transient quantity=Moving1.Force_mag context=
- Review report Torque_Cogging manually; selected category=Transient quantity=Moving1.Force_mag context=
- Review report FluxLinkage_PhaseA manually; selected category=Transient quantity=FluxLinkage(PhaseA_Winding) context=
- Review report BackEMF_LL manually; selected category=Transient quantity=InducedVoltage(PhaseA_Winding) context=
- Review report Bmax_BackIron manually; selected category=Transient quantity=VolumePercentageAbove10Percent context=
- Torque_Cogging is currently only a named report target; true cogging extraction still needs a zero-current transient solve path
