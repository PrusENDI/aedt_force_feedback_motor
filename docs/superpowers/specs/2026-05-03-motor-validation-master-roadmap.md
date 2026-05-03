# Motor Validation Master Roadmap

Date: 2026-05-03

## Mission

The project goal is to validate whether a low-cost, manually manufacturable axial-flux force-feedback motor is physically and practically feasible, then produce manufacturing-ready artifacts for a real prototype.

The final deliverables are not only simulation screenshots. The project must converge to:

- a credible Maxwell 3D electromagnetic validation model;
- traceable reports for torque, back-EMF, losses, demagnetization, thermal risk, and axial attractive force;
- manufacturable laminated stator copper geometry;
- DXF files that can be used to cut usable copper stator layers;
- rotor, magnet, back-iron, air-gap, and assembly constraints that match the low-cost prototype route.

## Long-Term Source Of Truth

This roadmap is the top-level execution anchor. Future work should state which milestone it is advancing and should not skip milestone gates unless the roadmap is explicitly revised.

Detailed milestone specs and plans may exist in separate files, but they must not contradict this roadmap. If a detailed spec conflicts with this roadmap, update the roadmap first or mark the detailed spec obsolete.

## Non-Negotiable Project Constraints

- The model represents an axial-flux motor path intended for physical prototype validation.
- The manufacturable diameter limit is `100 mm` for the relevant circular stator/rotor/back-iron parts.
- The first physical route assumes low-cost, manually assembled hardware with imperfect tolerances.
- The copper stator route is laminated copper, not a purely simulated macro coil.
- Final copper geometry must be compatible with real DXF output.
- AEDT 3D copper solids and final DXF files must trace back to the same 2D copper geometry source.
- Six-layer laminated copper stack order is `A-B-C-C-B-A`.
- Copper layers remain independent; same-phase neighboring layers must not be merged into thick blocks.
- C phase thermal-core identification is based on average absolute distance from the stack center index.
- Same-phase parallel layers require per-layer open-circuit back-EMF magnitude and phase checks before accepting parallel connection.
- The final electromagnetic validation must support extraction of dual-rotor axial Maxwell attractive force.
- Transient winding excitation must follow `Winding Group -> Coil Terminals -> Add to Winding`; do not fall back to assigning current directly to arbitrary solids or sheets for the final winding model.
- Geometry-ready, solve-ready, and manufacturing-ready are separate states.

## Readiness Gates

### Geometry-Ready

Geometry-ready means the geometry matches the intended physical abstraction for that milestone. A visually present object is not enough.

For detailed copper milestones, annular-sector phase-belt envelopes are not geometry-ready.

### Solve-Ready

Solve-ready means the Maxwell setup is credible for the requested result: valid air region, boundary strategy, motion setup, winding assignment, materials, mesh risk checks, and named outputs.

Geometry-ready does not automatically imply solve-ready.

### Manufacturing-Ready

Manufacturing-ready means the geometry source can generate production-facing artifacts such as DXF, with units, orientation, feature limits, kerf/tool policy, registration references, and manufacturability checks.

Solve-ready does not automatically imply manufacturing-ready.

## Milestone 0: Contract Stabilization And Legacy Containment

Goal: prevent old phase-belt envelope geometry from being mistaken for detailed copper geometry.

Required outcomes:

- Mark annular-sector phase-belt copper as legacy or diagnostic geometry only.
- Stop reporting envelope copper as detailed `geometry_ready`.
- Split readiness fields into envelope, detailed copper, solve, and manufacturing readiness where needed.
- Clean report language that still references old top/bottom PCB or double-sided macro-coil assumptions.
- Keep useful AEDT host and queue mechanisms, but do not let host success imply physics success.

Exit gate:

- A report can clearly explain what current geometry is and is not.
- A failed detailed-copper gate blocks excitation/solve claims.

## Milestone 1: SSDR Physics Anchor Scope

Goal: keep the total motor validation problem grounded in the intended electromagnetic architecture.

Required outcomes:

- Define the SSDR axial-flux truth-anchor model: central stator, two rotors, two magnet layers, two active air gaps.
- Preserve the distinction between SSDR validation and final `S1-R1-S2-R2-S3` topology.
- Track torque, back-EMF, cogging, flux linkage, magnetic density, losses, demagnetization margin, and axial attractive force as eventual outputs.
- Keep the `4 Nm @ 3 Arms` target associated with the final topology, not blindly imposed on the first SSDR checkpoint.

Exit gate:

- The project can explain why SSDR is being built first and how it will later correlate to the final topology.

## Milestone 2: DXF-Compatible 3D Copper MVP

Goal: build the first usable 3D copper model without committing to full six-layer geometry.

Required outcomes:

- Generate one real 2D copper outline for a single Phase A layer.
- Use this outline as the source for AEDT sheet creation and `0.3 mm` thickened copper.
- Include terminal regions in the geometry definition.
- Apply initial checks for closed geometry, self-intersection, bounding diameter, minimum feature size, and terminal presence.
- Allow the copper layer to float in air; no support skeleton, adhesive, PI, or FR4 solids are required.
- Run only a low-risk sanity electromagnetic check.

Exit gate:

- GUI inspection shows a real path-derived copper plate, not a sector envelope block.
- The same 2D geometry source can plausibly feed future DXF export.

Current active node:

- This is the current detailed implementation target.
- Do not fill in later milestones before this node can produce a credible first 3D copper solid.

## Milestone 3: Repeatable Single-Layer Geometry Generator

Goal: turn the MVP into a parameterized single-layer toolchain.

Required outcomes:

- Represent motor intent separately from 2D polygon geometry.
- Compute path geometry from radius, angle, phase, layer, terminal, and winding parameters.
- Use a robust 2D geometry library for offset, union, validity, and clearance checks.
- Add optional single-layer DXF preview/export.
- Add regression tests proving geometry changes when design parameters change.

Exit gate:

- A Phase A layer can be regenerated repeatably from parameters and inspected in both 2D and AEDT 3D form.

## Milestone 4: Three-Phase Single-Layer Geometry

Goal: generate A/B/C copper for one physical layer.

Required outcomes:

- Generate three independent phase geometries on one layer.
- Check phase-to-phase spacing and non-overlap.
- Preserve terminal accessibility and current direction metadata.
- Estimate copper area, path length, and approximate phase resistance.

Exit gate:

- The project has a credible one-layer three-phase stator geometry, even before full laminated stacking.

## Milestone 5: Six-Layer Laminated Copper Stack

Goal: represent the intended `A-B-C-C-B-A` laminated stator.

Required outcomes:

- Generate six independent copper layers with correct z positions.
- Preserve separate layer identities and phase metadata.
- Compute stack height from design variables rather than hard-coded numbers.
- Identify the C phase as thermal-core phase using average absolute distance from stack center index.
- Track same-phase parallel layer relationships for later circulating-current risk checks.

Exit gate:

- AEDT geometry shows six real independent copper plates, not merged phase blocks.
- Reports expose layer order, z positions, stack height, phase mapping, and thermal-core phase.

## Milestone 6: Maxwell 3D Solve Validation

Goal: make the model credible for electromagnetic results.

Required outcomes:

- Build valid air region and boundary strategy for either full model or true periodic sector.
- Add rotor, magnets, back iron, motion setup, and material definitions.
- Assign winding excitation through winding groups and coil terminals.
- Define open-circuit, loaded, and diagnostic cases.
- Export named reports for torque, back-EMF, flux linkage, magnetic density, losses, and axial attractive force.
- Block solve-ready status when boundary, motion, mesh, or winding assignment is not valid.

Exit gate:

- The first credible solve can run with named outputs that answer a specific validation question.

## Milestone 7: Risk Validation And Sensitivity

Goal: test whether the model survives realistic prototype risks.

Required outcomes:

- Air-gap tolerance cases.
- Unequal upper/lower gap cases.
- Rotor runout or axial wobble approximation.
- Magnet demagnetization margin at elevated temperature and peak current.
- Back-iron saturation checks.
- Copper loss and thermal risk estimates.
- Per-layer open-circuit back-EMF magnitude and phase comparison for same-phase parallel paths.

Exit gate:

- The project can identify the dominant feasibility risk instead of only reporting ideal performance.

## Milestone 8: Final Topology Correlation

Goal: connect the SSDR truth anchor to the intended `S1-R1-S2-R2-S3` final topology.

Required outcomes:

- Account for four active air-gap faces in the final topology.
- Avoid blind scaling from SSDR.
- Compare leakage, fringing, shared magnetic paths, copper length, resistance, thermal paths, and tolerance accumulation.
- Decide whether the final topology can plausibly reach the target operating point.

Exit gate:

- The project has an explicit correlation argument from SSDR validation to final motor feasibility.

## Milestone 9: Manufacturing DXF Package

Goal: produce fabrication-facing stator copper files.

Required outcomes:

- Export DXF files for each copper layer or manufacturing sheet.
- Preserve units, origin, orientation, phase, layer, thickness, and revision metadata.
- Include terminal pads, registration references, keep-outs, and process notes where required.
- Check minimum feature size, islands, inside corners, clearance, kerf/tool policy, and bounding diameter.
- Compare exported DXF geometry with the AEDT geometry source.

Exit gate:

- The DXF package is traceable to the validated geometry source and can be sent for manufacturing review.

## Execution Rule For Future Work

At the start of each implementation session, the agent should:

1. Read this roadmap.
2. State the current milestone.
3. State the exact exit gate being targeted.
4. Check the current git worktree.
5. Refuse to claim a later readiness state unless the current milestone gate is satisfied.

For the current project state, the active target is Milestone 2: DXF-Compatible 3D Copper MVP.

