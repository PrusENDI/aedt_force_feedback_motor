# DXF-Compatible 3D Copper MVP Design

Date: 2026-05-03

## Purpose

The final manufacturing goal is to produce DXF files that can be used to cut usable laminated copper stator plates. The immediate goal is narrower: build the first credible 3D copper model in AEDT from a geometry representation that can later become a DXF source.

The project must stop treating annular-sector phase-belt envelopes as detailed copper geometry. Those envelopes may remain as legacy diagnostic geometry, but they must not be reported as detailed geometry-ready or used as the basis for winding excitation validation.

## V1 Goal: DXF-Compatible 3D Copper MVP

V1 proves the minimum viable chain:

1. Generate one real 2D copper outline for a single layer of Phase A.
2. Validate that the outline is closed, non-self-intersecting, and manufacturable under initial feature rules.
3. Create an AEDT sheet from that same 2D geometry.
4. Thicken the sheet to a `0.3 mm` copper solid.
5. Assign simple terminals or current excitation for a low-risk electromagnetic sanity check.

V1 is not a complete six-layer stator, not a complete three-phase winding, and not the final Sector3D production model.

## V1 Hard Constraints

- Copper geometry must not be generated as annular-sector phase-belt envelope blocks.
- V1 builds one minimum real copper layer, preferably one Phase A layer.
- The copper model must originate from a 2D copper outline that can later be exported as DXF.
- AEDT 3D geometry and future DXF export must share the same 2D geometry source.
- Motor intent is computed by project code: radius, angle, phase, layer, terminal location, and winding path.
- 2D polygon operations should use a geometry library such as Shapely for offset, union, difference, validity, and clearance checks.
- DXF export should use a dedicated DXF layer, such as ezdxf, once export becomes part of the stage.
- V1 does not include six-layer `A-B-C-C-B-A`, full three-phase geometry, support skeletons, PI/adhesive solids, or detailed transient winding setup.
- The V1 copper layer is allowed to float in air to avoid support boolean and thin-layer meshing risks.
- Terminal regions must be part of the copper geometry definition, not ad-hoc AEDT patches added after the fact.
- Reports must distinguish `envelope_geometry_ready`, `dxf_compatible_copper_ready`, and `solve_ready`.
- V1 must not claim production Sector3D geometry readiness.

## Initial Manufacturing Constraints For V1

These are default contract fields, not final manufacturing promises:

- Copper thickness: `0.3 mm`.
- Maximum outer diameter: `<= 100 mm`.
- Minimum copper width: parameterized, initially conservative.
- Minimum copper-to-copper gap: parameterized, initially conservative.
- Minimum inside corner radius: parameterized.
- Kerf or tool compensation: represented as a parameter, even if not applied in V1.
- Terminal pad size and location: explicit geometry fields.
- Layer registration references: optional in V1, required before final manufacturing DXF.

If a cutting process is selected later, these values must be replaced by process-specific constraints.

## V1 Success Criteria

- A GUI inspection shows the copper is a real routed plate or path-derived solid, not a 4.95-degree sector block.
- The generated 2D copper geometry is closed and valid.
- The geometry report includes minimum width, minimum clearance, bounding diameter, and terminal region checks.
- AEDT can create and retain the `0.3 mm` thick copper solid.
- The model can run at least a basic magnetostatic or equivalent low-risk sanity check.
- The report clearly states that full six-layer Sector3D geometry remains incomplete.

## V2 Goal: Single-Layer Geometry Chain

V2 turns the V1 prototype into a repeatable single-layer generator.

Required capabilities:

- Parameterized Phase A copper path generation from motor design parameters.
- Stable 2D geometry model with explicit centerline, outline, terminal pads, and metadata.
- Repeatable AEDT sheet creation and thickening from the same outline.
- Optional DXF preview/export for this one layer.
- Automated geometry checks for closure, self-intersection, minimum feature size, and bounding diameter.
- Regression tests that prove changing the path parameters changes the copper shape, not only report fields.

V2 should still avoid full support structures and full transient solve complexity.

## V3 Goal: Three-Phase Single-Layer Geometry

V3 extends the generator to all three phases on one physical layer.

Required capabilities:

- Generate Phase A, Phase B, and Phase C copper outlines for the same layer.
- Enforce phase spacing and non-overlap checks.
- Preserve terminal accessibility and phase labeling.
- Report phase path length, copper area, approximate resistance, and expected current direction.
- Support GUI inspection with phase-specific names and colors.
- Export or preview separate DXF layers for phase identity if useful.

V3 is the first stage where phase balance and physical terminal layout become serious contract items.

## V4 Goal: Six-Layer Laminated Stack

V4 builds the laminated copper stack `A-B-C-C-B-A`.

Required capabilities:

- Six independent copper solids with no same-phase merge into thick blocks.
- Explicit layer order, z position, copper thickness, inter-layer allowance, and total stack height.
- C phase thermal-core identification by average absolute distance from the stack center index.
- Same-phase parallel path metadata for later circulating-current risk analysis.
- Per-layer path length, resistance estimate, terminal mapping, and phase polarity.
- Geometry checks for vertical clearance, layer registration, and terminal escape.
- Clear exclusion of PI/adhesive/support solids unless a later stage explicitly adds them.

V4 is the first point where the model can represent the intended laminated copper topology, but it is still not automatically solve-ready.

## V5 Goal: AEDT Electromagnetic Validation Model

V5 integrates the copper stack into a credible Maxwell 3D validation setup.

Required capabilities:

- Air region strategy that is either a true periodic sector or a clearly documented full/expanded model.
- Rotor, magnet, back iron, and motion setup compatible with axial-flux force and torque extraction.
- Winding Group -> Coil Terminals -> Add to Winding flow for transient winding excitation.
- No fallback to direct current assignment on arbitrary solids or sheets for transient winding validation.
- Open-circuit, loaded, and basic diagnostic setups.
- Per-layer open-circuit back-EMF magnitude and phase reporting for same-phase parallel layer risk.
- Extraction plan for dual-rotor axial Maxwell attractive force.
- Mesh and boundary checks that block solve-ready status when geometry is not suitable.

V5 may still use simplified support treatment if support material is magnetically close to air and does not change electromagnetic conclusions.

## V6 Goal: Manufacturing DXF Package

V6 turns the validated geometry source into a manufacturing-facing output package.

Required capabilities:

- DXF export for each copper layer or manufacturing sheet.
- Stable coordinate system, units, origin, and orientation.
- DXF layers for copper outline, terminal pads, optional registration features, notes, and keep-out geometry.
- Kerf/tool compensation policy documented and parameterized.
- Manufacturing checks for minimum feature size, isolated islands, sharp internal corners, cut order risks, and registration references.
- A visual/geometry report that compares DXF geometry with AEDT geometry source.
- File naming that preserves phase, layer, revision, thickness, and unit metadata.

The DXF package must be generated from the same 2D geometry source used to create AEDT copper solids.

## Final Production-Ready 3D Model Requirements

The final 3D model is production-ready only when all of the following are true:

- The six-layer copper geometry is detailed, independent, and generated from the DXF-compatible 2D source.
- The electromagnetic setup uses valid coil terminal and winding group assignments.
- Boundary conditions are geometrically valid for the chosen model scope.
- Motion, torque, back-EMF, copper loss, and axial attractive force outputs are extractable and named.
- Per-layer same-phase voltage magnitude and phase are monitored before accepting parallel connection.
- Reports do not mix legacy top/bottom PCB or phase-belt envelope language with laminated copper wave winding.
- Geometry-ready, solve-ready, and manufacturing-ready are separate status fields.
- Manufacturing DXF export and AEDT geometry can be traced back to the same parameters and geometry artifacts.

## Out Of Scope For V1

- Full six-layer laminated stator.
- Full three-phase transient excitation.
- Production periodic sector boundary proof.
- Support skeleton boolean subtraction.
- PI, adhesive, FR4, or mechanical carrier solids.
- Final cutting DXF release.
- Thermal solve.
- Full torque target validation.

## Self-Review

- No incomplete requirements are intentionally left open.
- The stage boundaries separate V1 proof, six-layer geometry, AEDT validation, and DXF manufacturing output.
- Legacy envelope geometry is allowed only as diagnostic context and is not allowed to satisfy detailed copper readiness.
- The document explicitly treats DXF as the final target while keeping V1 focused on the first usable 3D copper model.
