# Current Simulation Requirements

This file summarizes the current motor design targets and optimization constraints used by the workspace.

## Application

- Force-feedback steering wheel motor
- Operates mostly at stall or near-zero speed
- Maximum speed is only a ceiling, not the main operating point
- Smoothness and controllability matter as much as raw torque

## Topology intent

- Axial-flux permanent-magnet motor
- Baseline stator concept:
  - slotless / coreless
  - PCB + flat copper winding
- Stack:
  - `S1 - R1 - S2 - R2 - S3`
  - 3 stators
  - 2 rotors
  - 4 active air-gap interaction faces

## Fixed geometry baseline

- Outer diameter: `98 mm`
- Inner diameter: `60 mm`
- Pole count baseline: `24 poles`
- DC bus: `48 V`
- Target max speed: `230 to 250 rpm`
- Baseline magnet layout: alternating `N/S` surface-mounted magnets
- Single mechanical air gap target: `0.6 to 0.8 mm`
- Stator total thickness target: `4 to 5 mm`
- Rotor back iron target: `4 to 5 mm`

## Main performance targets

- Normal usable stall torque: `4.0 Nm`
- Current at main working point: about `3.0 Arms / phase`
- Short peak torque target: `5.0 to 5.5 Nm`
- Peak current target: about `4.0 Arms / phase`
- Target torque constant `Kt`: `1.30 to 1.40 Nm/Arms`
- Phase resistance `Rph`: `0.80 to 0.90 ohm @ 20 C`
- Phase inductance `Lph`: `0.6 to 1.2 mH`
- Effective air-gap flux density `Bg`: `0.45 to 0.60 T`
- 250 rpm back-EMF must remain compatible with a `48 V` bus

## Hard constraints

- Average torque at `3.0 Arms` must be `>= 4.0 Nm`
- Average torque at `4.0 Arms` should be `>= 5.0 Nm` if feasible
- Torque ripple target at `3.0 Arms`: `<= 8%`
- Cogging torque target: `<= 0.05 Nm`
- Hot copper loss target at main point: `<= 35 W`
- Back iron peak flux density target: `<= 1.6 T`
- Magnet demagnetization risk must be checked
- Sensitivity to air-gap and magnet placement errors must be checked

## Optimization priorities

Priority order:

1. Meet usable stall torque target
2. Reduce torque ripple
3. Reduce cogging torque
4. Keep copper loss and thermal risk under control
5. Preserve back-EMF margin at 250 rpm
6. Limit saturation
7. Prefer simpler and more manufacturable solutions

## 2D screening strategy

The workspace is set up to:

- Use a linearized `Maxwell 2D` transient-oriented model for coarse screening
- Export lightweight CSV metrics instead of keeping large field datasets
- Prefer winding/flux-linkage/back-EMF capable outputs over purely magnetostatic field snapshots
- Rank candidates before promoting only the best few to 3D

## 3D validation strategy

The workspace is set up to:

- Use a `Maxwell 3D` sector model
- Validate only top shortlisted cases
- Focus 3D cost on torque, ripple, cogging, back-EMF, and saturation confirmation

## Variable search space

Current main search variables:

- `magnet_thickness_mm`
- `pole_arc_ratio`
- `airgap_mm`
- `backiron_thickness_mm`
- `coil_radial_span_mm`
- `coil_mean_radius_mm`
- `turns_per_phase`
- `conductor_width_mm`
- `conductor_thickness_mm`
- `parallel_strands`
- `magnet_segments_per_pole`

## Reporting outputs expected from the workflow

- `reports/2d_screening_summary.csv`
- `reports/2d_screening_ranked.csv`
- `reports/3d_validation_summary.csv`
- `reports/3d_validation_ranked.csv`
- `reports/recommended_design.md`

## Current modeling philosophy

- Disk use must stay controlled
- 2D is for cheap search and transient-friendly signal extraction
- 3D is for expensive confirmation
- The hosted AEDT workflow should support long-running iterative agent-driven exploration without repeatedly reopening AEDT
