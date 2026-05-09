# Milestone 3.5 Phase A Full-Layer Geometry Precursor Design

Date: 2026-05-07

## Current Milestone

V2 / Roadmap Milestone 3, `Repeatable Single-Layer Geometry Generator`, is complete and passed its stage gate.

The active local stage is:

```text
Milestone 3.5: Phase A Full-Layer Geometry Precursor
```

This stage sits between V2's representative single-layer Phase A segment and Milestone 4's three-phase single-layer geometry. The shorthand "V3" may appear in local branch names or filenames, but the roadmap milestone is 3.5.

## Purpose

Milestone 4 needs a Phase A geometry source that can be rotated or otherwise transformed into Phase B and Phase C, then checked for phase-to-phase spacing, non-overlap, terminal accessibility, path length, copper area, and approximate resistance.

Therefore Milestone 3.5 must produce a complete Phase A 2D full-layer geometry source. It is not enough to generate a sparse topology smoke primitive, a representative V2 segment repeated around a circle, or six isolated blocks that merely avoid overlap.

The full-layer source must be a parameterized generator, not a fixed drawing. Changing a small set of design numbers should immediately regenerate a compliant Phase A 2D geometry, update diagnostics, and produce a new SVG for review.

Milestone 3.5 remains pure Python and 2D. It should not launch AEDT, create 3D sheets, run DC Conduction, build three phases, or claim solve/manufacturing readiness.

## V4-Derived Requirements

Milestone 4 can only start cleanly if Milestone 3.5 hands off:

- A complete `360 deg` Phase A layer inside the `100 mm` diameter limit.
- Dense routed copper, with multiple slot/turn features inside each macro segment.
- Stable `outline_points_xy_mm` and `aedt_polyline_points_mm` for the full layer and for debug segments.
- A deterministic angular transform policy that Milestone 4 can use to create Phase B and Phase C candidates.
- Phase entry/exit metadata, current direction metadata, terminal keepout metadata, path length, copper area, and approximate resistance inputs.
- Pure 2D validation for self-overlap, segment overlap, clearance, radial fill, angular occupancy, bounding diameter, and AEDT polyline/name preflight.
- SVG preview detailed enough that sparse or underfilled copper is visually obvious.

## Key Design Decision

Milestone 3.5 keeps the existing V2 geometry contract version and adds a more specific generation mode:

```json
{
  "geometry_contract_version": "dxf-copper-v2",
  "generation_mode": "phase_full_layer"
}
```

The artifact should still expose `segments[]`, but segments are macro debug tiles, not the whole deliverable. The top-level artifact must also expose the complete Phase A full-layer geometry:

- `full_layer_regions[]`
- `full_layer_outline_groups_xy_mm`
- `full_layer_aedt_polyline_regions_mm`
- `full_layer_centerline_points_xy_mm`
- `segments[]` with per-segment V2-compatible geometry fields

The old sparse `pitch_owned_tile` output is useful only as a topology smoke pattern. It must not satisfy the Milestone 3.5 exit gate.

Milestone 3.5 should not replace V2 with a separate geometry language. It should factor the useful V2 behavior into a constrained full-phase segment primitive:

```text
V2 representative segment generator
  -> keep V2 naming, validation, Shapely outline construction, terminal records, diagnostics, AEDT polyline format
  -> replace only the centerline construction with a tile-constrained full-phase centerline
  -> assemble constrained segments into one Phase A full-layer source
```

This keeps V4 on the same geometry lineage as V2 while fixing the reason simple V2 segment copying failed: the representative V2 segment was not constrained to fit a reusable angular ownership window.

## V2 Parameter And Naming Continuity

Milestone 3.5 should be built on V2's naming and parameter vocabulary so V4 does not need a second geometry language.

V2 fields that remain authoritative:

- `geometry_contract_version`
- `units`
- `phase`
- `layer`
- `copper_thickness_mm`
- `max_outer_diameter_mm`
- `inner_radius_mm`
- `outer_radius_mm`
- `centerline_radius_mm`
- `radial_swing_mm`
- `slot_pitch_deg`
- `arc_segment_deg`
- `max_arc_segment_count`
- `trace_width_mm`
- `trace_gap_mm`
- `mitre_limit`
- `terminal_pad_width_mm`
- `terminal_pad_height_mm`
- `terminal_offset_mm`
- `aedt_handshake_mode`
- `dxf_export_mode`

Milestone 3.5 adds only the parameters needed to scale from one representative segment to a complete Phase A layer:

- `generation_mode`
- `macro_segment_count`
- `macro_segment_pitch_deg`
- `full_layer_coverage_deg`
- `turn_count_per_macro_segment`
- `radial_lane_count`
- `macro_guard_angle_deg`
- `phase_transform_policy`
- `terminal_keepout_policy`
- `minimum_radial_fill_ratio`
- `minimum_angular_occupancy_ratio`
- `minimum_full_layer_centerline_length_mm`
- `minimum_full_layer_area_mm2`

The default spec should be self-consistent. If a user changes only radius window, trace width/gap, slot pitch, turn count, lane count, guard angle, or macro segment count, the generator should either produce a valid new full-layer geometry or fail fast with a specific parameter validation error.

## Geometry Model

Default geometry should use six macro segments because that is a convenient full-circle partition:

```text
macro_segment_count = 6
macro_segment_pitch_deg = 60.0
full_layer_coverage_deg = 360.0
```

The six macro segments are not the pole/slot count. Each macro segment must be a V2-style routed copper segment whose centerline is constrained to its angular ownership window and derived from parameters such as:

- `slot_pitch_deg`
- `turn_count_per_macro_segment`
- `radial_lane_count`
- `inner_radius_mm`
- `outer_radius_mm`
- `trace_width_mm`
- `trace_gap_mm`
- `macro_guard_angle_deg`

The default target should visually resemble a dense Phase A routed copper layer around the full circle. Narrow clearances are acceptable when they meet the configured minimum; large empty wedges or flower-like sparse blocks are not acceptable.

## Segment Boundary And Continuity Policy

Milestone 3.5 must keep neighboring macro segments physically separated in the 2D copper geometry. Segment boundaries should preserve at least the configured `trace_gap_mm` unless a stricter boundary-clearance parameter is added later.

Because the macro segments are physically separated, the full layer is a set of copper regions, not one continuous polygon. The artifact must not pretend that disconnected copper can be represented by one `full_layer_outline_points_xy_mm` or one `full_layer_aedt_polyline_points_mm` list.

Continuity is logical only:

- Segment `S01` may declare `logical_connections.exit_to = "A_L01_S02"`.
- Segment `S02` may declare `logical_connections.entry_from = "A_L01_S01"`.
- The top-level artifact may include `logical_connection_policy = "ordered_segments_with_physical_gap"`.
- SVG previews may draw dashed arrows or labels to show logical current direction.
- SVG previews must not draw solid copper bridges at segment boundaries.

Milestone 3.5 must not generate bridge polygons, jumper traces, terminal escape routes, or any other physical copper that connects neighboring macro segments. Physical bridges require Phase B/C spacing and terminal keepout knowledge, so they belong to a later stage after Milestone 4 has checked three-phase layout constraints.

## Parameterization Contract

Milestone 3.5 succeeds only if parameter changes affect real geometry, not just metadata.

Required parameter-change behavior:

- Changing `inner_radius_mm` or `outer_radius_mm` changes radial fill and outline coordinates.
- Changing `trace_width_mm` changes copper area and outline width.
- Changing `trace_gap_mm` changes validation thresholds and may fail previously valid full-layer geometry.
- Changing `slot_pitch_deg` changes the V2-style turn spacing within each constrained segment.
- Changing `turn_count_per_macro_segment` changes path length, centerline point count, and copper area.
- Changing `radial_lane_count` changes radial lane usage and radial fill ratio.
- Changing `macro_guard_angle_deg` changes angular occupancy and segment-to-segment clearance.
- Changing `macro_segment_count` updates `macro_segment_pitch_deg` or fails fast unless the caller explicitly overrides both consistently.

The report must include a `spec_summary` section with the effective values used to generate the artifact. V4 should consume the generated geometry and `phase_transform_policy`, not re-derive hidden defaults.

Parameter normalization rules:

- If the caller provides `macro_segment_count` only, derive `macro_segment_pitch_deg = 360.0 / macro_segment_count`.
- If the caller provides both `macro_segment_count` and `macro_segment_pitch_deg`, require their product to equal `360.0` within tolerance.
- If the caller provides `macro_segment_pitch_deg` only, fail fast unless it divides `360.0` into an integer macro segment count; if it does, derive `macro_segment_count`.
- Use `provided_keys = set(spec or {})` so caller intent is explicit and default values are not mistaken for overrides.

Radial lane fit rule:

```text
usable_radial_span_mm = outer_radius_mm - inner_radius_mm
required_radial_span_mm = radial_lane_count * trace_width_mm + (radial_lane_count - 1) * trace_gap_mm
required_radial_span_mm <= usable_radial_span_mm
```

If the rule fails, the generator must raise `ValueError("radius window cannot fit radial_lane_count")` before creating geometry.

Length and area thresholds are default spec fields, not universal constants. Callers may override `minimum_full_layer_centerline_length_mm` and `minimum_full_layer_area_mm2` when intentionally exploring smaller radius windows or lower turn counts.

## Data Contract

Required top-level fields:

- `milestone`: `Milestone 3.5: Phase A Full-Layer Geometry Precursor`.
- `geometry_contract_version`: `dxf-copper-v2`.
- `generation_mode`: `phase_full_layer`.
- `topology_preset`: `phase_a_full_layer_v2_constrained_segment`.
- `geometry_scope`: `v35_phase_a_full_layer_2d`.
- `phase`: `A`.
- `layer`: `L01`.
- `segment_count`: default `6`.
- `segments`: ordered macro segment array from phase entry toward phase exit.
- `logical_connection_policy`: `ordered_segments_with_physical_gap`.
- `full_layer_regions`: one region per physically disconnected copper macro segment.
- `full_layer_outline_groups_xy_mm`: list of closed outline point lists, one per region.
- `full_layer_aedt_polyline_regions_mm`: list of AEDT-ready point lists, one per region.
- `full_layer_centerline_points_xy_mm`: ordered logical centerline points for diagnostics only; physical discontinuities remain defined by `segments[]`.
- `phase_transform_policy`: metadata for Milestone 4 Phase B/C angular transforms.
- `terminal_keepout_policy`: `metadata_only_not_final_escape`.
- `terminal_keepouts`: keepout markers around logical entry/exit contacts for V4 spacing awareness.
- `v35_full_layer_passed`: one compact pass/fail gate.
- `blocking_issues`: exact issue codes when the gate is false.
- `diagnostics`: density, fill, path length, area, resistance estimate, bounding, and clearance metrics.
- `not_evaluated`: explicit false-scope fields.

Each item in `full_layer_regions[]` should include:

- `region_id`
- `source_segment_id`
- `outline_points_xy_mm`
- `aedt_polyline_points_mm`
- `physical_connection`: `isolated_macro_segment`
- `logical_connections`

Required `not_evaluated` values:

```json
{
  "phase_b_geometry_evaluated": false,
  "phase_c_geometry_evaluated": false,
  "three_phase_spacing_evaluated": false,
  "physical_bridge_evaluated": false,
  "physical_terminal_escape_evaluated": false,
  "aedt_sheet_creation_evaluated": false,
  "dc_conduction_evaluated": false,
  "six_layer_stack_evaluated": false,
  "solve_evaluated": false,
  "manufacturing_dxf_evaluated": false
}
```

## Diagnostics And Acceptance Metrics

Milestone 3.5 should fail unless the default geometry reports all of:

- `full_layer_coverage_deg == 360.0`.
- `segment_count == 6`.
- `minimum_clearance_mm >= trace_gap_mm`.
- `bounding_diameter_mm <= max_outer_diameter_mm`.
- `full_layer_self_overlap_free == true`.
- `segment_overlap_free == true`.
- `radial_fill_ratio` above a configured minimum.
- `angular_occupancy_ratio` above a configured minimum.
- `centerline_length_mm` above a configured minimum derived from V2 baseline length and segment count.
- `copper_area_mm2` above a configured minimum derived from the routed full-layer target.
- `aedt_preflight_passed == true`.

Initial numeric thresholds should be conservative but must reject the current sparse smoke primitive. The implementation plan should introduce the thresholds as named spec fields rather than magic constants.

## SVG Review Contract

Every geometry-changing implementation step must write an SVG preview.

The expected SVG should show:

- One complete Phase A full-layer routed copper source around the full circle.
- Six labeled macro segments for debug identity.
- Dense V2-style turn detail inside each constrained macro segment.
- Physical gaps between neighboring macro segments.
- Dashed or textual logical connection markers are allowed.
- Solid copper bridges across macro segment boundaries are not allowed.
- No quadrant-size voids.
- No isolated flower-petal blocks.
- Visible but not excessive gaps between neighboring copper features.
- Small logical contact markers that do not dominate the winding geometry.
- Optional inner/outer radius guide circles and the `100 mm` bounding circle.

The SVG is a blocking review artifact for Milestone 3.5. A mathematically valid but visually sparse preview is not acceptable.

## AEDT Preflight

Milestone 3.5 should not launch AEDT or create a clean AEDT project/design.

It should run offline AEDT preflight over both segment and full-layer point data:

- Points are `[x, y, 0.0]` in millimeters.
- Names are deterministic, unique, and use conservative ASCII letters, digits, and underscores.
- Polylines have enough points for sheet creation.
- Every entry in `full_layer_aedt_polyline_regions_mm` passes preflight independently.
- Adjacent duplicate points and near-zero edges are rejected.
- Open outline point lists are acceptable only when paired with the documented V4 policy to call `create_polyline(..., close_surface=True, cover_surface=True)`.

## Artifacts

Milestone 3.5 should generate:

- `artifacts/dxf_copper_v35_phase_a_full_layer.json`
- `reports/dxf_copper_v35_phase_a_full_layer.md`
- `artifacts/dxf_copper_v35_phase_a_full_layer_preview.svg`

Debug SVGs may also be generated under `artifacts/debug_*`, but only the full-layer preview is the milestone artifact.

## V4 Handoff

Milestone 4 may use the Milestone 3.5 artifact as input only when `v35_full_layer_passed=True`.

The handoff includes:

- Phase A full-layer outline and AEDT polyline points.
- Phase A full-layer region groups and per-region AEDT polyline points.
- Ordered macro segment geometry for debugging and local clearance diagnostics.
- Logical connection metadata from each segment exit to the next segment entry.
- Angular transform metadata for Phase B/C candidate generation.
- Terminal keepout metadata and phase entry/exit points.
- Path length, copper area, approximate resistance inputs, radial fill, angular occupancy, and clearance diagnostics.
- Explicit unresolved warnings that Phase B/C, terminal escape, AEDT sheet creation, and solve readiness are not yet evaluated.

Milestone 4 should begin by generating Phase B/C candidates from this Phase A source and checking three-phase 2D spacing before any AEDT build.

## Non-Goals

Milestone 3.5 must not implement or claim:

- Phase B or Phase C geometry.
- Three-phase single-layer readiness.
- Six-layer `A-B-C-C-B-A` laminated stack.
- AEDT sheet creation, thickening, mesh assignment, or host queue execution.
- DC Conduction, transient winding excitation, winding groups, coil terminals, torque, back-EMF, losses, demagnetization, thermal validation, or axial force extraction.
- Physical bridge geometry between macro segments.
- Final physical terminal escape geometry.
- Final production DXF package.
- Legacy annular-sector phase-belt geometry as detailed copper.
- Old `Sector3D` scaffold changes as the primary geometry route.

## Tests

Milestone 3.5 should use `unittest` with the PyAEDT environment Python.

Required test categories:

- Default spec declares `generation_mode="phase_full_layer"` and `geometry_scope="v35_phase_a_full_layer_2d"`.
- Default build produces six macro segments and one full-layer Phase A geometry source.
- The full-layer geometry covers `360 deg` and stays within the `100 mm` diameter limit.
- Directly repeating the unconstrained V2 representative segment fails the full-layer gate through overlap or clearance issues.
- The constrained V2-style segment primitive passes the full-layer gate.
- Segment boundary tests prove neighboring macro segments keep physical gaps while exposing logical connection metadata.
- Dense geometry thresholds reject the old sparse smoke primitive.
- Each macro segment remains V2-compatible enough for existing geometry validation fields.
- Full-layer and segment validations catch overlap, clearance violations, too-low radial fill, too-low angular occupancy, too-short path length, and legacy phase-belt fields.
- AEDT preflight catches unsafe names, duplicate names, nonzero Z, too few points, duplicate adjacent points, and near-zero edges.
- Parameter changes modify real geometry and diagnostics, not only metadata.
- The SVG writer produces the full-layer preview artifact after geometry changes.
- Existing V1/V2 tests continue to pass.

## Exit Gate

Milestone 3.5 is complete when:

- The default artifact is a complete, dense Phase A full-layer 2D geometry source.
- `v35_full_layer_passed=True`.
- Blocking issues are empty.
- The SVG preview passes human review as a dense full-circle Phase A layer.
- Full-layer and per-segment AEDT preflight pass.
- The report contains V4 handoff fields for Phase B/C angular transform, path length, copper area, resistance estimate, fill metrics, terminal keepouts, and unresolved non-goals.
- Existing V1/V2 tests still pass.

## Self-Review

- This design does not let the sparse `pitch_owned_tile` smoke primitive satisfy Milestone 3.5.
- This design keeps the V2 contract version and V2 geometry lineage while making the generation mode specific to a full-layer Phase A source.
- This design remains pure Python and does not move AEDT work into Milestone 3.5.
- This design explicitly serves Milestone 4's three-phase single-layer geometry needs.
