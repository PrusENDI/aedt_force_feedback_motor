# 3D Engineering Validation Design

Date: 2026-05-02

## Purpose

This phase establishes a physically credible, engineering-oriented Maxwell 3D validation path for the axial-flux force-feedback motor project. The priority is not DOE throughput. The priority is a 3D model and analysis workflow that can answer whether a low-cost, hand-built prototype can rotate, avoid overheating, and expose the real limiting factors before the final machine topology is treated as feasible.

The first validated model is an SSDR periodic-sector truth anchor: one central stator, two rotors, two magnet layers, and two active air gaps. The final torque target of `4 Nm @ 3 Arms` belongs to the final `S1-R1-S2-R2-S3` topology with four active air-gap faces. The SSDR model must not be required to meet that final-machine torque target directly.

## Confirmed Engineering Assumptions

- Manufacturing and assembly are low precision, nearly fully manual.
- A practical tolerance envelope is `+-0.20 mm` or worse for air-gap and assembly errors.
- Simple machining is available, such as turning, milling, and basic fixtures, but precision manufacturing is not assumed.
- The maximum machinable part diameter is `100 mm`, so the motor outer diameter and any single circular rotor/stator/back-iron part must stay at or below `100 mm`.
- The first prototype should be open and easy to debug, with external fan cooling favored over sealed packaging.
- The winding route is hybrid: the PCB provides support, positioning, and interconnect; the main current path uses flat copper or relatively heavy copper wire.
- Magnet material should be modeled as a heat-resistant NdFeB class, such as `N42SH` or `N35SH`.
- Back iron and structural steel should be modeled conservatively as low-cost machinable material, not ideal high-performance magnetic steel.
- The motor must be evaluated for long continuous operation at `3 Arms`, with `4 Arms` treated as a short peak and demagnetization check condition.

## Model Scope

### Stage 1: SSDR 3D Truth Anchor

The SSDR model must be a real Maxwell 3D transient model, not only a geometric visualization. It must support:

- true axial air gaps;
- rotating band or equivalent motion;
- master/slave or equivalent periodic sector boundaries;
- loaded, cogging, and open-circuit cases;
- named report export for torque, flux linkage, back-EMF, magnetic density, losses, and demagnetization margin;
- tolerance cases for manual manufacturing risk.

The SSDR model is used to calibrate physical behavior, not to declare the final hardware design complete.

### Stage 2: Final Topology Correlation

The final `S1-R1-S2-R2-S3` topology has three stators, two rotors, and four active air-gap faces. It is the topology that must ultimately meet `4 Nm @ 3 Arms`.

The path from SSDR to final topology must be explicit. SSDR results cannot be scaled by a blind factor of two. The correlation must account for:

- leakage and fringing changes;
- shared rotor and stator magnetic paths;
- the `100 mm` maximum part diameter constraint;
- copper length and resistance changes;
- thermal path changes;
- air-gap tolerance accumulation;
- winding interconnect and phase balance effects.

## Physical Objects That Must Be Credible

### Air Gap And Motion

- Nominal air gap should not be overly aggressive. For manual assembly, `0.8 mm` to `1.0 mm` is a more realistic starting range than `0.5 mm` to `0.6 mm`.
- The model must include a valid motion region before torque or back-EMF results are trusted.
- The tolerance path must include increased air gap, unequal upper/lower air gaps, and rotor runout or equivalent axial wobble.

### Magnets And Back Iron

- Magnet temperature behavior and coercivity must be conservative enough for long operation and peak current checks.
- Demagnetization margin must be evaluated at high temperature and `4 Arms` peak current.
- Back iron must be checked for peak flux density and saturation using conservative material assumptions.
- The model must not hide weak performance behind idealized magnet or infinite-permeability assumptions.

### Winding And Copper Loss

- PCB copper is not the primary active conductor in the first engineering prototype.
- Main copper geometry must preserve enough information to estimate cross-section, mean path length, end-connection length, and phase resistance.
- Hot copper loss must be estimated using thermal resistance assumptions and hot resistance at roughly `80 C` to `100 C`.
- End connections, solder or clamp joints, and parallel path imbalance require resistance margin.
- Double-sided conductors, insulation, adhesive, and spacing must remain manufacturable under manual assembly.

### Excitation

- The loaded operating point is three-phase sinusoidal `3 Arms`.
- The peak check point is `4 Arms`.
- Open-circuit back-EMF and zero-current cogging cases must use the same motion path as the loaded case.
- Current angle must be sweepable. A fixed `0 deg` current angle must not be assumed to be optimal.
- Winding polarity and phase order must be diagnosable from flux linkage, torque sign, and back-EMF phase behavior.

### Air Region And Boundaries

- Coreless axial-flux machines have strong leakage and fringing fields, so the air region must be deliberately large.
- At least one expanded-air-region verification case must confirm that torque and back-EMF are not boundary artifacts.
- Periodic-sector validity requires the phase pattern and magnet pattern to repeat correctly across the selected sector.

## Required Outputs

The stage-1 SSDR workflow must export or compute:

- `Torque_Loaded`: average torque, peak-to-peak ripple, and ripple percentage at `3 Arms`;
- `Torque_Cogging`: zero-current torque ripple;
- `FluxLinkage_PhaseA`: phase flux linkage;
- `BackEMF_LL`: line-line back-EMF and 48 V bus margin at the target speed;
- `Bmax_BackIron`: peak back-iron flux density;
- `Inductance_PhaseA`: phase inductance estimate when available;
- `MagnetDemag_Margin`: high-temperature and peak-current demagnetization margin;
- `CopperLoss_Hot`: hot-resistance continuous copper loss estimate;
- `Kt_Effective`: effective torque constant inferred from loaded torque and phase current.

## Stage-1 Acceptance Criteria

- Maxwell 3D transient solves at least one electrical period for the nominal SSDR case.
- Loaded, cogging, and open-circuit cases produce usable report data.
- The model can distinguish geometry, excitation, material, thermal, and boundary-condition failures.
- Hot copper loss is evaluated conservatively even before a full CFD or thermal FEA model exists.
- Demagnetization margin is checked at high temperature and `4 Arms`.
- Tolerance cases produce interpretable changes rather than unexplained solver artifacts.
- The SSDR result includes a written final-topology feasibility assessment rather than a direct pass/fail against `4 Nm @ 3 Arms`.

## First Tolerance And Risk Cases

The first engineering validation set should include:

- `baseline_nominal`;
- `airgap_plus_0p2mm`;
- `airgap_imbalance_0p2mm`;
- `rotor_runout_0p2mm`;
- `magnet_angle_error`;
- `magnet_radial_offset`;
- `magnet_axial_height_error`;
- `hot_resistance_case`;
- `peak_current_demag_case`;
- `expanded_air_region_check`.

These cases are intended to reveal manufacturing and physics risk before DOE is restarted.

## Problem Analysis Path

When the model or design fails to meet expectations, debug in this order:

1. Check geometry, air-gap dimensions, rotating band, sector cuts, and air-region size.
2. Check three-phase excitation, winding polarity, phase order, current angle, and current amplitude.
3. Check whether copper resistance, end connections, parallel paths, and hot copper loss make the design thermally unrealistic.
4. Check magnet strength, high-temperature coercivity, and demagnetization margin.
5. Check back-iron saturation, leakage flux, fringing flux, and outer air-boundary sensitivity.
6. Check manufacturing tolerance sensitivity: air-gap imbalance, runout, magnet placement, and winding position errors.
7. Check whether SSDR-to-final-topology correlation is still valid or whether the final four-air-gap model must be built before drawing conclusions.

## Relationship To The Current Repository

- `config/project.json` remains the parameter source of truth.
- `reports/sector3d_physics_contract.md` remains the existing physics contract, but this design adds the manual-manufacturing and final-topology torque-target clarifications.
- The current Sector3D geometry and material path is close to usable for Stage 1.
- The current highest technical blocker is Maxwell 3D winding and terminal excitation assignment.
- 2D screening and DOE ranking are deferred until the 3D engineering validation path can produce trusted baseline and tolerance evidence.

## Non-Goals For This Phase

- Do not optimize a large DOE before the SSDR 3D truth anchor is trustworthy.
- Do not declare the final motor hardware-ready from SSDR results alone.
- Do not rely on idealized manufacturing tolerances, ideal magnet material, or ideal thermal paths.
- Do not spend effort on sealed final packaging before the open prototype proves the electromagnetic and thermal path.
