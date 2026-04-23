# Sector3D Playbook

This note compresses the current repo intent and the most relevant AFPM/PCB-stator literature into a practical `Sector3D` build checklist for this workspace.

The current selected route for this repo is:

- `rigid PCB + flat-copper winding hybrid`

It is written to support the current placeholder hook:

- `scripts/build_hooks.py -> ensure_sector_3d_design(...)`

It assumes the current workflow remains:

- `Linearized2D` for coarse screening
- `Sector3D` for truth-model validation of shortlisted cases

## 1. Recommended first 3D baseline

Do not start with the full `S1-R1-S2-R2-S3` machine.

Build a first truth model as:

- topology: `SSDR` (single stator, double rotor)
- stator type: `coreless PCB stator`
- model span: one mechanical sector covering `sector_model_pole_count = 2`
- solver: `Maxwell 3D -> Transient`
- goal: calibrate torque, back-EMF, ripple, cogging, and back-iron saturation against the 2D ranking flow

Reasoning:

- the current repo already expects a `Maxwell 3D` sector validation stage
- the current 3D automation hook is still a placeholder, so the first model should minimize geometry risk
- the AFPM PCB literature is strongest for `SSDR coreless PCB` machines

## 2. Parameter table

## 2A. Manufacturing constraints from the current project

The current prototype routes are no longer abstract.

Available options from the project owner:

- rigid PCB: `6-layer`, outer layers `1 oz`, inner layers `0.5 oz`, board thickness `1.6 mm`
- FPC: copper thickness `1/3 oz`, total thickness about `0.11 mm`

For Maxwell and for this repo, these constraints must be reflected explicitly.

Derived copper thickness values:

- `1 oz ~= 0.035 mm`
- `0.5 oz ~= 0.0175 mm`
- `1/3 oz ~= 0.0117 mm`

Equivalent copper per rigid 6-layer board if all layers are counted:

- `2 * 0.035 + 4 * 0.0175 = 0.14 mm`

This has two immediate consequences:

1. The current `config/search_space.json` range for `conductor_thickness_mm = 0.3 to 1.1 mm` is not physically consistent with a single manufacturable PCB board.
2. A `1.6 mm` rigid board sitting in the active AFPM gap is a much larger axial penalty than the copper it carries.

Therefore, before implementing the `Sector3D` skeleton, the project should treat:

- `conductor_thickness_mm`

as:

- `equivalent_copper_thickness_mm_per_parallel_path`

instead of:

- a single solid conductor block thickness

And the project should add:

- `stator_axial_build_mm`

to represent the real thickness seen by the magnetic circuit, including:

- substrate
- copper
- adhesive or prepreg
- coverlay or solder mask if relevant
- spacer or insulation films

### 2.1 Carry over from current repo

These should remain the first-class design variables because they already exist in:

- `config/search_space.json`
- `scripts/run_linear_2d_screen.py`
- `scripts/run_sector_3d_validate.py`

For the selected `rigid PCB + flat-copper winding hybrid` route, interpret the current conductor variables as:

- `conductor_width_mm`: flat-copper strip width
- `conductor_thickness_mm`: flat-copper strip thickness, not PCB copper foil thickness
- `parallel_strands`: stacked parallel flat-copper paths per effective turn

| Variable | Keep in Sector3D | Notes |
| --- | --- | --- |
| `magnet_thickness_mm` | yes | First-order air-gap flux lever. |
| `pole_arc_ratio` | yes | Strong impact on torque, ripple, and back-EMF. |
| `airgap_mm` | yes | Highest sensitivity item for AFPM torque density. |
| `backiron_thickness_mm` | yes | Needed for saturation control. |
| `coil_radial_span_mm` | yes | Controls active conductor length and torque arm usage. |
| `coil_mean_radius_mm` | yes | Controls tangential force radius and copper length. |
| `turns_per_phase` | yes | Must stay explicit because it affects torque constant, inductance, and resistance. |
| `conductor_width_mm` | yes | Relevant for copper loss and PCB AC loss. |
| `conductor_thickness_mm` | yes | Relevant for resistance and manufacturability. |
| `parallel_strands` | yes | Use as a general "parallel path count" field. |
| `magnet_segments_per_pole` | yes | Needed if ripple/cogging suppression is explored later. |

### 2.2 Sector3D geometry and topology variables

These are not in the current 2D search space, but they are needed in 3D.

| Variable | Recommended role | First-pass range |
| --- | --- | --- |
| `rotor_outer_radius_mm` | machine envelope | fixed from packaging |
| `rotor_inner_radius_mm` | machine envelope | fixed from shaft and hub |
| `stator_outer_radius_mm` | active annulus outer edge | fixed or derived |
| `stator_inner_radius_mm` | active annulus inner edge | fixed or derived |
| `pole_count_total` | electrical periodicity | fix first |
| `slot_or_coil_count_total` | winding periodicity | fix first |
| `rotor_backiron_thickness_mm` | rotor saturation margin | 2-level DOE |
| `stator_support_thickness_mm` | carrier stiffness only | fixed first |
| `magnet_skew_deg` | later ripple suppression | hold at `0` in baseline |
| `axial_stack_type` | `SSDR`, later `MSMR` | baseline `SSDR` |
| `rotor_stator_misalignment_mm` | tolerance sensitivity | verification only |
| `axial_clearance_tol_mm` | prototype robustness | verification only |

### 2.3 PCB-only implementation variables

These are the most important missing variables if the prototype remains PCB-dominant.

| Variable | Why it matters | First-pass range |
| --- | --- | --- |
| `stator_fabrication_mode` | `rigid6_fr4`, `thin_fpc`, `rigid_flat_copper_hybrid` | categorical |
| `pcb_board_count` | direct cost and modularity lever | `1-4` |
| `pcb_active_layers_per_board` | copper count vs board price | `4-6` for rigid, project-specific for FPC |
| `pcb_outer_copper_thickness_mm` | real copper thickness | `0.035` for rigid board |
| `pcb_inner_copper_thickness_mm` | real copper thickness | `0.0175` for rigid board |
| `fpc_copper_thickness_mm` | real copper thickness | `0.0117` |
| `pcb_board_thickness_mm` | effective stator thickness / magnetic spacing | `1.6` for rigid board |
| `fpc_total_thickness_mm` | effective stator thickness / magnetic spacing | `0.11` |
| `pcb_series_board_groups` | raises turns and inductance | `1-4` |
| `pcb_parallel_board_groups` | lowers phase resistance | `1-4` |
| `via_diameter_mm` | resistance and current crowding | board-rule driven |
| `via_grid_rows` | current spreading | `1-4` |
| `via_grid_cols` | current spreading | `1-4` |
| `phase_layer_grouping` | AC loss and imbalance control | categorical |
| `trace_shape_type` | `trapezoid`, `wave`, `distributed`, `radial` | categorical |
| `trace_width_profile` | constant or unequal width | categorical |

Suggested categorical values:

- `stator_fabrication_mode`: `rigid6_fr4`, `thin_fpc`, `rigid_flat_copper_hybrid`
- `phase_layer_grouping`: `interleaved`, `phase-grouped`
- `trace_shape_type`: `trapezoid`, `wave`, `distributed`
- `trace_width_profile`: `constant`, `unequal`

### 2.4 Hybrid PCB + flat-copper implementation variables

If the project explores PCB as carrier plus added formed copper conductors, add these only after the PCB-only baseline is calibrated.

| Variable | Why it matters | First-pass status |
| --- | --- | --- |
| `winding_technology` | `pcb_only` vs `pcb_flat_copper_hybrid` | keep explicit |
| `flat_copper_enabled` | feature flag | off in baseline |
| `flat_copper_thickness_mm` | DC resistance lever | later DOE |
| `flat_copper_width_mm` | fill factor / AC loss tradeoff | later DOE |
| `flat_copper_turns_per_phase` | MMF / inductance / resistance | later DOE |
| `flat_copper_segment_count` | eddy-current mitigation | later DOE |
| `flat_copper_axial_offset_mm` | effective air-gap impact | later DOE |
| `flat_copper_insulation_mm` | manufacturability and safety | later DOE |
| `bondline_thickness_mm` | tolerance stack-up | later DOE |
| `carrier_pcb_routing_share_pct` | how much current stays on PCB | later DOE |

## 3. Boundary and setup checklist

The first `Sector3D` template should use the simplest robust transient setup that matches common AFPM Maxwell practice.

### 3.1 Geometry scope

- Build one periodic sector, not the full annulus.
- Include both rotor back-irons, all magnets in the sector, the full stator conductive region, and a surrounding air region.
- Use explicit rotor and stator solids, even if the final loss evaluation is exported rather than field-saved.
- The scaffold artifact should report `sector_geometry.geometry_scope = periodic_sector`; a full-annulus build artifact is a geometry regression.

### 3.1A Coreless caution

- Do not borrow the usual iron-core simplifications about narrow flux paths or naturally high inductance.
- In this project the stator is coreless, so magnetic flux spreads more broadly in air and leakage matters more.
- Keep the outer air region deliberately generous during baseline correlation because back-EMF and inductance can move if the boundary is too close.
- Treat any macro-coil conductor block as an envelope model only; it is useful for first-pass torque correlation, not as the final truth model for current crowding or AC loss.

### 3.2 Symmetry and periodicity

- Use a periodic sector based on `gcd(pole_count_total, slot_or_coil_count_total)`.
- Use `Master/Slave` periodic boundaries on the two radial cut faces of the sector.
- If an additional mirror plane exists, use it only after the full sector solution is validated once.

### 3.3 Motion

- Use a 3D rotating band enclosing rotor steel and magnets.
- The band should include enough radial and axial clearance to avoid touching magnets, rotor back-iron, or the stator conductors.
- Start with one mechanical revolution fraction equal to at least one electrical period.

### 3.4 Excitations

- Loaded case: three-phase sinusoidal current excitation.
- Cogging case: same geometry, zero stator current, same motion.
- Open-circuit case: zero stator current, same motion, back-EMF export enabled.

Phase current law:

- `Ia = sqrt(2) * I_rms * sin(omega_e * t + theta0)`
- `Ib = sqrt(2) * I_rms * sin(omega_e * t - 2*pi/3 + theta0)`
- `Ic = sqrt(2) * I_rms * sin(omega_e * t + 2*pi/3 + theta0)`

### 3.5 Coil modeling choice

Use two model tiers.

Tier A, envelope DOE model:

- use simplified stranded "macro coil" solids for the PCB winding
- preserve active conductor region, mean radius, radial span, and equivalent copper area
- use this tier for most 3D DOE points

For this project, the macro-coil must be parameterized from real stack data.

Recommended equivalent-area rule:

- `Aeq = copper_utilization_factor * sum(width_i * thickness_i for all active parallel copper paths)`

Do not set `Aeq` from the old `conductor_thickness_mm` search range alone.

For the current manufacturing options:

- rigid 6-layer PCB baseline: derive `Aeq` from `2 x 0.035 mm + 4 x 0.0175 mm`
- FPC baseline: derive `Aeq` from `0.0117 mm x active layer count x parallel path count`

Tier B, detailed verification model:

- model the actual PCB trace layout or the hybrid copper layout
- use this only for the top few shortlisted designs
- use it to check AC loss, circulating current risk, layer imbalance, and local current crowding

### 3.6 Mesh priorities

- fine mesh in air gaps
- fine mesh in magnet corners
- fine mesh through conductor thickness only for detailed verification
- coarser mesh in remote air region
- keep field saving disabled for DOE unless debugging

### 3.7 Outputs required by this repo

Match the current report names where possible:

- `Torque_Loaded`
- `Torque_Cogging`
- `BackEMF_LL`
- `Bmax_BackIron`

Also add:

- `FluxLinkage_PhaseA`
- `Inductance_PhaseA`
- `MagnetDemag_Margin`
- `PhaseResistance_Est` if using post-processing
- `CopperLoss_DC_Est`
- `CopperLoss_AC_Est` for detailed verification cases

## 4. DOE priority

### Phase 0: trust-model baseline

Run only one baseline and two perturbation cases.

Objectives:

- make `Sector3D` solve reliably
- verify report creation and CSV export
- compare 3D torque and back-EMF against the current 2D baseline logic

Parameters to move:

- `airgap_mm`
- `magnet_thickness_mm`
- `turns_per_phase`

But first freeze the fabrication mode.

Recommended order:

- baseline A: `thin_fpc`
- baseline B: `rigid6_fr4`
- baseline C: only if needed, `rigid_flat_copper_hybrid`

This prevents mixing topology effects with fabrication effects too early.

### Phase 1: envelope DOE

Only after the template solves.

Priority 1 variables:

- `airgap_mm`
- `magnet_thickness_mm`
- `pole_arc_ratio`
- `coil_mean_radius_mm`
- `coil_radial_span_mm`
- `turns_per_phase`

Priority 2 variables:

- `backiron_thickness_mm`
- `conductor_width_mm`
- `conductor_thickness_mm`
- `parallel_strands`

Priority 3 variables:

- `magnet_segments_per_pole`
- `rotor_backiron_thickness_mm`
- `phase_layer_grouping`
- `trace_width_profile`

Recommended screening design:

- `12-20` points with Latin hypercube or low-discrepancy sampling
- hold topology fixed at `SSDR`
- keep the detailed trace layout abstracted as macro coils

### Phase 2: PCB realization DOE

Only for the top `3-5` electromagnetic envelopes.

Priority variables:

- `stator_fabrication_mode`
- `pcb_board_count`
- `pcb_active_layers_per_board`
- `pcb_series_board_groups`
- `pcb_parallel_board_groups`
- `via_diameter_mm`
- `via_grid_rows`
- `via_grid_cols`
- `trace_shape_type`
- `trace_width_profile`

Primary outputs:

- `phase_resistance_ohm_hot`
- `hot_copper_loss_w`
- `back_emf_ll_rms_v`
- `torque_constant_nm_per_arms`
- `copper_loss_ac_est`

### Phase 3: topology DOE

Only after one PCB-only design is credible.

Compare:

- `SSDR single PCB stator`
- `two thinner PCB stators with reused boards`
- `same total board count but different rotor/stator arrangement`

Use equal magnet mass and equal total copper mass where possible.

This follows the literature pattern where topology is compared under matched resource constraints.

### Phase 4: tolerance DOE

Run only on the final `1-2` candidates.

Perturb:

- rotor axial runout
- stator offset
- air-gap imbalance
- magnet placement error
- board thickness tolerance

This is essential for low-cost prototypes because AFPM performance is very sensitive to gap variation.

## 5. Recommendation on winding strategy for this project

Question:

- should the project add flat copper coils on a PCB carrier to avoid very expensive high-layer boards
- or should it use multiple optimized PCB boards in series/parallel

### Updated short answer under the actual fabrication limits

The answer is now conditional.

If the available stator substrate is:

- `1.6 mm` rigid 6-layer FR4 PCB

then do **not** make stacked rigid PCBs the main active stator path.

Prefer:

- `rigid PCB + added flat-copper winding`

or:

- `single rigid PCB only as carrier/interconnect`, not as the bulk torque-producing copper

If the available stator substrate is:

- `0.11 mm` FPC with `1/3 oz` copper

then the better first route is:

- `multiple optimized FPC boards in series/parallel`

and only move to:

- `FPC + flat-copper hybrid`

if the calibrated FPC-only route still misses the copper-loss target.

### Why rigid 6-layer FR4 changes the recommendation

The rigid board option is copper-poor and thickness-heavy.

- total copper per board is only about `0.14 mm`
- substrate thickness is `1.6 mm`
- the thickness-to-copper ratio is poor for a coreless AFPM stator
- stacking several rigid boards in the active gap quickly destroys flux density and torque density

For the rigid-board route, hybrid copper becomes much more attractive than it was under the earlier generic assumption set.

### Why thin FPC keeps the modular-board route attractive

The thin-FPC route has the opposite tradeoff.

- copper per layer is small
- but axial penalty is also much smaller
- multiple FPC layers or multiple FPC boards can still preserve a compact magnetic path
- repeatability and Maxwell modeling are still cleaner than a bonded flat-copper hybrid

So for pure PCB-like stators, `multi-FPC series/parallel` is still the best first-principles route.

### Why inductance still matters here

- the current repo targets a force-feedback machine operating mostly at stall and low speed
- PCB motors already suffer from low inductance
- series-connected modular boards naturally help increase turns and inductance
- a hybrid flat-copper approach can reduce resistance, but it does not automatically fix low inductance and may push the drive toward higher ripple or higher switching-frequency requirements

### Why hybrid flat copper is still attractive later

Electromagnetically, a well-executed flat-copper approach can be better in:

- copper fill factor
- DC resistance
- end-turn length
- current rating

This is consistent with AFPM flat-winding work using stamped or cut conductor sheet.

However, for this specific project, the hybrid route adds new risks:

- larger modeling gap versus the current repo
- harder insulation and adhesive stack-up control
- more sensitivity to local eddy-current loops
- more custom assembly work per sample
- weaker direct literature coverage for a PCB-carrier plus added flat-copper AFPM compared with pure PCB stators

### Decision rule

Choose `multi-FPC series/parallel` first if the priority is:

- fastest path to a trustworthy 3D model
- lowest prototype integration risk
- keeping the control problem manageable
- preserving the current repo variable set

Choose `rigid PCB + flat copper hybrid` first if the dominant manufacturing option is the `1.6 mm` rigid 6-layer board.

Choose `PCB + flat copper hybrid` for the FPC route only if:

- the calibrated PCB-only design cannot satisfy `Rph` and hot copper loss simultaneously
- board quote cost grows sharply with layer count and copper weight
- the team can tolerate custom mechanical assembly and a second modeling branch

## 6. Literature signals behind these choices

- PCB AFPM design and optimization for `SSDR` is well represented in the METU and Kentucky work.
- PCB motors are limited mainly by low copper fill factor and low inductance; these are explicitly called out in the METU thesis.
- Detailed PCB loss mitigation work strongly favors optimization of via layout, trace layout, and parallel-path balance before changing the winding technology.
- Recent topology comparison work shows that reusing identical PCB boards in different AFPM stack arrangements can improve output under matched magnet and board constraints.
- Flat conductor-sheet winding is promising for AFPM, but the direct evidence is stronger for standalone flat-winding AFPM machines than for the exact PCB-carrier hybrid architecture.

## 7. Immediate next step for this repo

Implement the first `Sector3D` template around a fabrication-aware `SSDR` macro-coil model with:

- current repo carry-over variables
- `stator_fabrication_mode`
- real copper thickness per layer
- real stator axial build
- periodic sector boundaries
- rotating band motion
- loaded, cogging, and open-circuit report paths

Do not keep the old `conductor_thickness_mm = 0.3 to 1.1 mm` interpretation when building the Maxwell skeleton.
