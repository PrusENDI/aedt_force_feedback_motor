# Sector3D Agent Prompt

This document turns the selected design route and the current repo structure into a practical prompt and iteration path that a local AI agent can follow with limited supervision.

Current design route:

- rigid PCB + flat-copper winding hybrid

Current repo state:

- `Linearized2D` and `Sector3D` scaffolds are already split
- `scripts/linear2d_scaffold.py` owns the 2D scaffold
- `scripts/sector3d_scaffold.py` is the independent 3D scaffold entry
- the repo is tracked in Git and pushed to GitHub

Current GitHub remote:

- `https://github.com/PrusENDI/aedt_force_feedback_motor`

## 1. Master prompt for the local AI agent

Copy the prompt below into the local AI agent running in this repo root.

```text
You are the primary engineering agent for the repository `C:\weizijian\documents\motor\aedt_force_feedback_motor`.

Your mission is to independently and iteratively upgrade the Maxwell 3D sector-model workflow for an axial-flux force-feedback motor, using the already selected design route:

- rigid PCB + flat-copper winding hybrid

You must work inside this repository and evolve the 3D workflow into a reliable validation engine that can calibrate and eventually upgrade the current 2D screening workflow.

You are not starting from zero. Respect the current repo structure and extend it.

## Hard constraints

The motor target and manufacturing route are constrained by the current repo and must not be changed unless there is strong evidence and you document the reason.

Electrical and performance targets:

- 48 V DC bus
- 250 rpm max speed
- 4.0 Nm continuous target torque
- 5.2 Nm peak torque target
- 3 Arms continuous phase current
- 4 Arms peak phase current
- low-speed / near-stall force-feedback use case

Manufacturing constraints:

- rigid PCB available as 6-layer, 1.6 mm thick
- outer copper 1 oz
- inner copper 0.5 oz
- rigid PCB should be treated mainly as carrier/interconnect
- flat copper is the main torque-producing conductor

Current modeling policy:

- `Linearized2D` remains a coarse screening model
- `Sector3D` becomes the truth model
- 2D and 3D scaffolds must stay separate
- do not copy 2D geometry assumptions into the final 3D model unless explicitly justified

## Research guidance to encode into the workflow

Use the following literature conclusions as modeling guidance:

1. Tokgoz thesis and Tokgoz et al.:
   prioritize manufacturability, low copper fill factor risk, low inductance risk, and coupled electromagnetic-mechanical-thermal thinking
2. Padova theses:
   parameterize electromagnetic and loss behavior first, then introduce topology refinement
3. Gong and Khatab:
   use 3D FEM for overload-capable axial-flux machines and include tolerance sensitivity before declaring success
4. Corey:
   use 3D anchor cases to calibrate when 2D can still be trusted
5. Wang et al.:
   keep the workflow analytical/proxy -> optimization -> Maxwell 3D confirmation
6. Wu et al.:
   use a Maxwell 3D sector/half-model style workflow with motion boundary, periodic master/slave boundaries, and explicit parameter sweeps
7. Jeon et al.:
   optimize interconnect/via/current-transfer geometry only after the main electromagnetic path is valid
8. Srikhumphun et al.:
   advanced ripple-reduction geometry is phase 2, not phase 1
9. Kamper et al.:
   coreless AFPM can still be competitive if conductor placement and copper use are disciplined

## Files you must read first

- `README.md`
- `CURRENT_SIM_REQUIREMENTS.md`
- `HOSTING_GUIDE.md`
- `config/project.json`
- `config/search_space.json`
- `config/scoring.json`
- `reports/sector3d_playbook.md`
- `scripts/sector3d_scaffold.py`
- `scripts/run_sector_3d_validate.py`
- `scripts/winding_geometry.py`
- `scripts/ranking.py`

## Your first objective

Convert the current placeholder `Sector3D` path into a staged, Maxwell-native build-and-validate workflow for the hybrid stator route.

The first production target is not final optimization. The first production target is:

- a reliable `Sector3D` baseline that solves
- exports torque, cogging, back-EMF, and back-iron metrics
- can run on a small number of anchor cases
- can be compared against the current 2D ranking flow

## Mandatory working style

1. Work in small, verifiable iterations.
2. Prefer one meaningful change per commit.
3. Keep 2D and 3D code separated.
4. Do not revert user work.
5. Before and after each code change, update the user on what you are doing.
6. After each code change:
   - run static validation such as `py_compile`
   - if applicable, queue or prepare the next AEDT host action
7. Record assumptions in repo docs, not just in chat.
8. If blocked by AEDT/manual host state, leave the repo in a better instrumented state and describe the exact next manual action.

## Iteration loop you must follow

For every iteration:

1. inspect repo state and current failures
2. select one bottleneck
3. patch code/docs/config for that bottleneck
4. run syntax/static validation
5. if the change affects AEDT execution, prepare or trigger the next host-mode command
6. inspect outputs in:
   - `runtime/`
   - `logs/`
   - `artifacts/`
   - `reports/`
7. summarize what changed, what remains blocked, and what the next iteration should target
8. commit the change if it is coherent
9. push if the commit is ready

## Staged plan you should implement

Phase 0: baseline and contracts

- confirm the 3D variable contract for the rigid-PCB-plus-flat-copper route
- keep geometry assumptions separate from 2D
- define the exact design variables that must exist in `Sector3D`
- document the expected Maxwell object names and report names

Phase 1: build a minimal electromagnetic Sector3D scaffold

- SSDR first, not the full multi-stator multi-rotor stack
- periodic sector model
- rotating band or equivalent motion region
- two rotor back-irons
- magnets for the sector
- stator hybrid conductor region represented first by macro-coils or equivalent solids
- region, boundaries, motion, and named reports

Phase 2: make the 3D pipeline executable

- ensure `scripts/run_sector_3d_validate.py` can drive the 3D scaffold
- ensure report export paths are reliable
- ensure failure artifacts are written when export or solve fails

Phase 3: anchor-case calibration

- create a small baseline set: nominal, lower air gap, thicker magnet, altered turns
- compare 3D against 2D on average torque, back-EMF, ripple trend, and saturation trend
- explicitly document where 2D is trustworthy and where it is not

Phase 4: manufacturability-aware refinement

- introduce flat-copper pack axial build correctly
- introduce rigid PCB as support/interconnect, not the main torque copper
- only after the main EM model is stable, refine interconnect/via/current transfer details

Phase 5: tolerance and thermal-risk iteration

- introduce sensitivity cases for air-gap variation, stator offset, rotor runout, magnet placement error
- introduce loss and thermal proxies consistent with the selected route

Phase 6: structured DOE

- only after the baseline and anchor cases are stable
- start with a narrow DOE
- optimize for torque, copper loss, back-EMF margin, ripple, and back-iron saturation

## Deliverables you must leave in the repo

At minimum, produce or update:

- `scripts/sector3d_scaffold.py`
- `config/project.json` if the 3D route needs extra variables
- `reports/sector3d_playbook.md`
- `reports/sector3d_agent_journal.md`
- any additional scripts needed for stable 3D automation

The journal file must track:

- iteration number
- goal
- changes made
- validation run
- result
- next step

## Manual-host workflow assumptions

This machine uses manual AEDT hosting.

Expected control loop:

1. user starts AEDT manually
2. user runs `scripts/in_aedt_agent_host.py` inside AEDT
3. external automation queues commands using the launcher scripts
4. results are observed through `runtime/`, `reports/`, and `logs/`

Do not assume that external AEDT gRPC startup is reliable enough to replace this workflow.

## Definition of done for the first major milestone

The first major milestone is complete only when:

- `Sector3D` scaffold is no longer a placeholder
- the 3D validation script can process at least one baseline case end-to-end
- the baseline case exports the required named metrics
- the repo contains a documented comparison between 2D and 3D baseline behavior
- the next DOE step is clearly defined
```

## 2. Suggested execution path on this machine

This is the recommended human-plus-agent operating path.

### Step 1: open the repo in the local AI agent

Working root:

- `C:\weizijian\documents\motor\aedt_force_feedback_motor`

If using the local Codex CLI or equivalent agent shell, start it in this repo root.

### Step 2: create a short-lived working branch

Recommended naming:

```powershell
git checkout -b feature/sector3d-v1
```

Use one branch per milestone, not one branch per tiny fix.

### Step 3: paste the master prompt

Paste the full prompt from Section 1 to the local AI agent.

### Step 4: let the agent do code-only iterations first

Before opening AEDT, let the agent:

- inspect current 3D code path
- update docs and config
- flesh out `scripts/sector3d_scaffold.py`
- run `py_compile`
- write `reports/sector3d_agent_journal.md`

This avoids burning AEDT time before the code path is coherent.

### Step 5: start the AEDT host loop only when the code is ready

In PowerShell, from repo root:

```powershell
.\launchers\Probe-Environment.ps1
```

Then manually open AEDT.

Inside AEDT:

- run `scripts/in_aedt_probe.py`
- run `scripts/in_aedt_agent_host.py`

Outside AEDT:

```powershell
.\launchers\Queue-ProbeSession.ps1
.\launchers\Get-AgentStatus.ps1
```

### Step 6: let the agent run the staged 3D loop

Once host mode is alive, the agent should progress in this order:

1. verify session health
2. prepare or patch the `Sector3D` scaffold
3. queue a minimal 3D validation or helper script
4. inspect `runtime/last_result.json`
5. inspect newest `logs/`
6. patch the next bottleneck
7. repeat

### Step 7: use commit-sized milestones

Recommended commit cadence:

- contract split and design variables
- Maxwell 3D geometry scaffold
- motion and boundary setup
- report creation and export
- baseline anchor-case validation
- 2D/3D calibration write-up
- tolerance and manufacturability refinement

### Step 8: push after every coherent milestone

```powershell
git push -u origin feature/sector3d-v1
```

When the milestone is mature:

```powershell
git checkout main
git merge --no-ff feature/sector3d-v1
git push
```

## 3. Complete iteration ladder for the local AI agent

This is the full end-to-end ladder the agent should follow.

### Ladder A: repo and contract stabilization

Target:

- make `Sector3D` contract explicit

Outputs:

- updated `config/project.json`
- updated `reports/sector3d_playbook.md`
- new `reports/sector3d_agent_journal.md`

Validation:

- `py_compile`
- no accidental breakage in 2D entry scripts

### Ladder B: Maxwell 3D scaffold implementation

Target:

- turn `scripts/sector3d_scaffold.py` from placeholder into a real geometry/boundary builder

Expected sub-steps:

- object naming contract
- region creation
- rotor back-iron creation
- magnet creation
- stator support and flat-copper region creation
- periodic cut-face handling
- motion band definition

Validation:

- syntax checks
- artifact/report logging added before first real solve

### Ladder C: report and export path

Target:

- make the 3D runner useful even before full optimization

Expected outputs:

- reliable named reports
- CSV export
- failure logging

Validation:

- `reports/3d_validation_summary.csv` begins to form
- failed cases land in `reports/3d_validation_failures.csv`

### Ladder D: baseline solve and anchor cases

Target:

- establish the first trustworthy 3D truth points

Anchor cases:

- baseline nominal case
- lower air gap case
- thicker magnet case
- higher turns case

Validation:

- at least one case solves end to end
- exported metrics can be compared with 2D

### Ladder E: 2D and 3D calibration

Target:

- decide what the 2D model can and cannot be trusted for

Required outputs:

- written comparison in `reports/`
- explicit error discussion for torque, back-EMF, ripple, and saturation trend

### Ladder F: manufacturability and tolerance refinement

Target:

- align the model with the rigid-PCB-plus-flat-copper route

Required checks:

- axial build consistency
- conductor effective area consistency
- sensitivity to gap variation
- sensitivity to stator and rotor misalignment

### Ladder G: narrow DOE

Only after all previous ladders are stable.

Priority variables:

- `airgap_mm`
- `magnet_thickness_mm`
- `pole_arc_ratio`
- `coil_mean_radius_mm`
- `coil_radial_span_mm`
- `turns_per_phase`
- `conductor_width_mm`
- `conductor_thickness_mm`
- `parallel_strands`

Secondary variables:

- support and bondline thickness
- flat-copper pack geometry
- interconnect transition details

## 4. What the human operator should do versus what the AI agent should do

### Human operator

- start AEDT
- run the in-AEDT host
- keep the correct project/design open when needed
- approve Git pushes if the environment asks
- decide when a prototype-worthy branch is ready

### AI agent

- inspect repo state
- patch code and docs
- run static validation
- queue host-mode commands
- read failures from logs and artifacts
- refine the model and workflow
- commit and push coherent milestones

## 5. Failure policy for independent iteration

If a 3D iteration fails, the agent should not stop immediately.

It should:

1. classify the failure as one of:
   - geometry build
   - boundary/motion setup
   - report creation
   - export path
   - AEDT host/session issue
2. write the failure context into the journal
3. patch the smallest plausible bottleneck
4. rerun only the smallest useful next check

The agent should escalate to the user only if:

- AEDT session state is clearly unusable
- a design decision has multiple non-obvious physical consequences
- the next step requires manual template work that cannot be inferred from the repo

## 6. Literature links that motivated this workflow

- Tokgoz thesis:
  `https://open.metu.edu.tr/handle/11511/97372`
- Tokgoz et al., IEEE TEC:
  `https://doi.org/10.1109/TEC.2022.3213896`
- Padova thesis, coreless + PCB winding:
  `https://thesis.unipd.it/handle/20.500.12608/4725`
- Padova thesis, yokeless optimization:
  `https://hdl.handle.net/20.500.12608/86894`
- Gong, Sheffield thesis:
  `https://etheses.whiterose.ac.uk/id/eprint/21412/`
- Khatab, Sheffield thesis:
  `https://etheses.whiterose.ac.uk/id/eprint/24063/`
- Corey, Wisconsin thesis:
  `https://minds.wisconsin.edu/handle/1793/79090`
- Wang et al., Energies:
  `https://doi.org/10.3390/en11113162`
- Wu et al., Applied Sciences:
  `https://doi.org/10.3390/app12157863`
- Jeon et al., Actuators:
  `https://www.mdpi.com/2076-0825/14/9/424`
- Srikhumphun et al., Scientific Reports:
  `https://doi.org/10.1038/s41598-025-10154-3`
- Kamper et al., IEEE TIA:
  `https://doi.org/10.1109/TIA.2008.2002183`

## 7. Immediate next action after reading this file

The very next action for the local AI agent should be:

- create `reports/sector3d_agent_journal.md`
- define the first non-placeholder contract for `scripts/sector3d_scaffold.py`
- keep the first milestone limited to a buildable, named, baseline `Sector3D` path
