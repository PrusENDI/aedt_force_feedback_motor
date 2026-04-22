# AEDT Template Contract

The automation scripts assume two small AEDT template projects exist:

- `templates/linear2d_template.aedt`
- `templates/sector3d_template.aedt`

Recommended setup notes:

- `templates/LINEAR2D_TEMPLATE_SETUP.md`
- `templates/AEDT_5_REPORTS_SETUP_GUIDE.md`
- `templates/AEDT_LINEAR2D_MODEL_BUILD_GUIDE.md`

They do not need solved data checked in. They only need the design scaffold, named variables, and named reports.

## Required design names

- The 2D project must contain a design named `Linearized2D`.
- The 3D project must contain a design named `Sector3D`.

## Required local design variables

Use these variable names exactly so the scripts can update them:

- `outer_diameter_mm`
- `inner_diameter_mm`
- `pole_count`
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
- `phase_current_rms`
- `speed_rpm`

Optional but recommended:

- `rotor_offset_deg`
- `sector_mech_angle_deg`
- `stator_thickness_mm`
- `magnet_grade`

## Required reports

Create these report names inside each template if you want the pipeline to extract real metrics automatically:

- `Torque_Loaded`
- `Torque_Cogging`
- `FluxLinkage_PhaseA`
- `BackEMF_LL`
- `Bmax_BackIron`

The scripts will export these report names to CSV if present.

Recommended intent per report:

- `Torque_Loaded`: torque waveform with `phase_current_rms = 3 A`
- `Torque_Cogging`: torque waveform with `phase_current_rms = 0 A`
- `FluxLinkage_PhaseA`: flux linkage or equivalent waveform for quick sanity checks
- `BackEMF_LL`: line-to-line back-EMF waveform at `speed_rpm = 250`
- `Bmax_BackIron`: peak flux density trace or scalar export for back iron saturation checks

## Recommended setup naming

- 2D setup name: `Setup_2D`
- 3D setup name: `Setup_3D`

## Minimal practical workflow

1. Build the 2D linearized template by hand or from recorder output.
2. Make sure the named variables above drive the geometry and excitations.
3. Add the required report names.
4. Do the same for the 3D sector template.
5. Run the automation scripts.

If you are building the first 2D template now, start with:

- `templates/LINEAR2D_TEMPLATE_SETUP.md`

## Why template mode is the default

For this motor, the geometry and excitation definitions are specific enough that template-driven automation is safer than trying to generate every object from scratch in a first script pass.

The included `scripts/build_hooks.py` file is where you can later paste recorder-generated geometry commands if you want full from-scratch creation.
