# Sector3D Physics Contract

This document fixes the research-backed physical and electromagnetic conditions for the `Sector3D` Maxwell workflow in this repo.

It is written for the selected route:

- rigid PCB + flat-copper winding hybrid

It should be read together with:

- `reports/sector3d_playbook.md`
- `reports/sector3d_agent_prompt.md`
- `scripts/sector3d_scaffold.py`
- `config/project.json`

## Research Basis

- Tokgoz thesis, 2022:
  `https://open.metu.edu.tr/handle/11511/97372`
  Signal used here:
  PCB-based AFPM work must treat manufacturability, low copper fill factor, and low inductance risk as first-class constraints.

- Tokgoz et al., IEEE TEC, 2022:
  `https://doi.org/10.1109/TEC.2022.3213896`
  Signal used here:
  Do not optimize electromagnetic output alone; keep thermal and structural feasibility in the loop.

- Wu et al., Applied Sciences, 2022:
  `https://doi.org/10.3390/app12157863`
  Signal used here:
  A practical Maxwell 3D AFPM workflow should use a sector or half-model, motion boundary, master/slave periodicity, and manual mesh refinement near the air gap.

- Corey thesis, 2019:
  `https://minds.wisconsin.edu/handle/1793/79090`
  Signal used here:
  Use a small number of 3D anchor cases to decide which 2D trends remain trustworthy.

- Gong thesis, 2018:
  `https://etheses.whiterose.ac.uk/id/eprint/21412/`
  Signal used here:
  Low-speed transient-actuation AFPM machines need 3D FEM support before overload-capable conclusions are trusted.

- Khatab thesis, 2019:
  `https://etheses.whiterose.ac.uk/id/eprint/24063/`
  Signal used here:
  Manufacturing and assembly tolerances must be treated as validation cases, not afterthoughts.

- Jeon et al., Actuators, 2025:
  `https://www.mdpi.com/2076-0825/14/9/424`
  Signal used here:
  Current-transfer details such as via and interconnect geometry should be refined only after the main EM path is stable.

## Physical Contract

### Model Scope

- baseline topology: `SSDR`
- first production truth model: one periodic sector, not the full machine
- first geometry implementation may start from a full-annulus helper scaffold, but production validation must cut to a true sector
- stator implementation route: rigid PCB as support/interconnect plus flat copper as the main active conductor

### Magnetic Circuit

- two rotor back-irons
- two magnet layers
- two active air gaps
- one central stator build that includes:
  - rigid support thickness
  - flat copper pack
  - insulation and bondline allowance

### Motion

- solver type: `Maxwell 3D Transient`
- motion type: rotating band
- motion axis: `Z`
- production validation requires a rotor motion region before torque and back-EMF are trusted
- solve at least one electrical period per anchor case

### Periodicity

- production model must use radial cut faces and `master/slave` periodic boundaries
- current config names are:
  - `Auto3D_Periodic_Master`
  - `Auto3D_Periodic_Slave`
- full-annulus baseline geometry is acceptable only as an intermediate construction step

### Electromagnetic Excitation

Required operating cases:

- loaded case:
  - three-phase sinusoidal current
  - `3 Arms` continuous baseline
- cogging case:
  - zero stator current
  - same motion path
- open-circuit back-EMF case:
  - zero stator current
  - same motion path

Current waveform contract:

- `Ia = sqrt(2)*Irms*sin(2*pi*fe*t + theta0)`
- `Ib = sqrt(2)*Irms*sin(2*pi*fe*t - 2*pi/3 + theta0)`
- `Ic = sqrt(2)*Irms*sin(2*pi*fe*t + 2*pi/3 + theta0)`

### Mesh Contract

- manual mesh is required
- at least `4` layers in each air gap
- refine magnet corners
- refine detailed conductor thickness only on the top cases, not the whole DOE
- keep field saving off during screening unless debugging

### Anchor Cases

The first 3D anchor cases should be:

- baseline
- lower air gap
- thicker magnet
- higher turns

These cases exist to calibrate the 2D ranking logic, not to replace it immediately.

### Tolerance Cases

The first tolerance set should include:

- air-gap imbalance
- stator offset
- rotor runout
- magnet placement error

This follows the Sheffield line of work where tolerance sensitivity is part of design validation, especially for hardware-feasible AFPM structures.

### What Must Be Verified Before DOE

Before any real 3D DOE, the repo should have:

- a true periodic sector, not just a full-annulus helper
- rotating band or equivalent motion region
- loaded, cogging, and open-circuit report paths
- named reports for:
  - `Torque_Loaded`
  - `Torque_Cogging`
  - `BackEMF_LL`
  - `FluxLinkage_PhaseA`
  - `Bmax_BackIron`
- one baseline case solved end to end

## Current Repo Mapping

The physics contract is currently encoded in:

- `config/project.json -> sector_3d`
- `scripts/sector3d_scaffold.py -> physics_contract()`
- `scripts/build_sector3d_model.py`

If these locations drift apart, `config/project.json` is the source of truth and the scripts should be updated to match it.
