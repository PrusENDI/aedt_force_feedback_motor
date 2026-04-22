# Sector3D Agent Journal

This file is the running journal for independent `Sector3D` iterations.

## Iteration 0

- goal: establish the first non-placeholder `Sector3D` contract for the rigid-PCB-plus-flat-copper hybrid route
- repo baseline:
  - `scripts/sector3d_scaffold.py` is still a placeholder
  - `scripts/linear2d_scaffold.py` and `scripts/sector3d_scaffold.py` are already separated
  - GitHub remote is configured and active
- expected next outputs:
  - explicit 3D design variables
  - Maxwell object naming contract
  - first buildable baseline geometry path
- validation target:
  - `py_compile` on all touched scripts
  - no regression in 2D entry scripts
- next step:
  - turn the 3D scaffold from placeholder into a baseline geometry builder

## Iteration 1

- goal: replace the placeholder `Sector3D` scaffold with a buildable baseline geometry path and give it a dedicated host-mode build entry
- changes made:
  - implemented `scripts/sector3d_scaffold.py` as a real 3D scaffold builder for a full-annulus SSDR baseline
  - added annular solids for rotor back-irons, magnets, air gaps, stator support, and flat-copper pack
  - added scaffold variables for the rigid-PCB-plus-flat-copper stack
  - added `scripts/build_sector3d_model.py`
  - added `launchers/Queue-BuildSector3DModel.ps1`
- validation target:
  - `py_compile` on the new and touched scripts
  - confirm no regression in the existing 2D scripts
- expected limitation:
  - the new scaffold is still a full-annulus baseline, not yet a true periodic sector with phase-separated conductors and motion bands
- next step:
  - add the first explicit Maxwell 3D contract for sector cut faces, motion-region placeholders, and named report preparation

## Iteration 2

- goal: encode the research-backed physical and electromagnetic contract into the repo instead of leaving it as free-text guidance
- changes made:
  - extended `config/project.json -> sector_3d` with transient, boundaries, motion, winding, mesh, and verification sections
  - added `physics_contract()` and `literature_basis()` in `scripts/sector3d_scaffold.py`
  - updated `scripts/build_sector3d_model.py` to write the active physics contract and literature basis into the build summary
  - added `reports/sector3d_physics_contract.md`
- validation target:
  - `py_compile` on the touched scripts
  - confirm the 3D build summary now carries the contract that future iterations must obey
- expected limitation:
  - the code now knows the physical contract, but the actual sector cut, motion object creation, and named report binding still need implementation
- next step:
  - make the scaffold produce or reserve the first explicit sector-cut and motion-region objects that satisfy this contract

## Iteration 3

- goal: remove hidden iron-core assumptions from the 3D contract and make the coreless hybrid route explicit in both config and scaffold warnings
- changes made:
  - split the `Sector3D` contract into an `SSDR` calibration layer and a final `S1-R1-S2-R2-S3` target layer
  - added `coreless_physics` fields in `config/project.json` for flux spreading, leakage, inductance, demagnetization, and air-region review
  - expanded `scripts/sector3d_scaffold.py` warnings and manual actions so the scaffold now reminds future iterations not to trust iron-core-style field concentration assumptions
  - added `Inductance_PhaseA` and `MagnetDemag_Margin` to the required report contract
  - updated the physics contract and playbook docs to state explicitly that the stator is coreless and the macro-coil conductor is only an early envelope model
- validation target:
  - `py_compile` on the touched scripts
  - confirm the build summary now exposes the coreless contract, not just the transient setup
- expected limitation:
  - the geometry is still a helper scaffold; the actual sector cut, winding legality, and demag/inductance report binding still need Maxwell-side implementation
- next step:
  - reserve or build the first explicit sector-cut and motion-band objects, then bind the new inductance and demag report paths

## Iteration 4

- goal: make the 3D validation entrypoint fail early when the model is not actually solve-ready
- changes made:
  - added 3D case precheck in `scripts/run_sector_3d_validate.py` so invalid geometry rows are excluded before Maxwell solve
  - added `sector3d_validation_preflight.json` and `3d_validation_invalid_cases.csv`
  - added template preflight checks for transient solution type, required report presence, and unresolved blocking issues recorded by the latest 3D scaffold build
  - made the validation runner fail if required report exports are missing or if exported CSV files do not contain usable waveform data
- validation target:
  - `py_compile` on the touched scripts
  - confirm the 3D runner now stops before `Analyze` when the template is not solve-ready
- expected limitation:
  - this still does not prove the Maxwell model converges physically; it proves the repo will stop early instead of silently treating a non-ready template as valid
- next step:
  - implement the actual sector cut, motion band objects, and report binding so the new preflight can pass on a real solve-ready template

## Iteration 5

- goal: create a Maxwell-usable 3D baseline loop that can build geometry, assign a coarse three-phase macro-coil, configure `Setup_3D`, attempt a transient solve, and export named reports
- changes made:
  - extended `scripts/sector3d_scaffold.py` with transient timing variables, phase-belt helper variables, and separate `baseline_ready_for_solve` versus validation-template readiness
  - updated `scripts/build_sector3d_model.py` so the build summary now distinguishes baseline-fatal blockers from stricter validation blockers
  - added `scripts/sector3d_aedt.py` as a shared Maxwell 3D helper layer for PyAEDT attachment, design-variable parsing, object deletion, and macro phase-belt generation
  - added `scripts/assign_sector3d_excitation.py` to replace the full-annulus copper envelope with repeated `A+ / C- / B+ / A- / C+ / B-` phase belts and then assign winding groups or fallback direct-current boundaries
  - added `scripts/apply_sector3d_transient_setup.py`, `scripts/create_sector3d_reports.py`, and `scripts/solve_sector3d_setup.py`
  - added the corresponding launchers for queue-driven AEDT host execution
- validation target:
  - `py_compile` on all new and touched 3D scripts
  - direct import check for the new 3D script set inside the preferred PyAEDT interpreter
- expected limitation:
  - the model now has a baseline solve/report loop, but axial-flux rotating-band geometry is still conservative and may still require manual Maxwell refinement before back-EMF and torque waveforms are fully trustworthy
- next step:
  - run the new 3D script chain inside AEDT, inspect the first real `sector3d_transient_setup`, `sector3d_excitation_assignment`, `sector3d_reports_creation`, and `sector3d_solve_status` artifacts, then tighten the motion-band and periodic-sector implementation from real solver feedback

## Iteration 6

- goal: make the queue-based host practical enough that the new 3D `.ps1` launchers can reliably drive AEDT without manual project/design re-selection
- changes made:
  - extended `scripts/agent_runtime.py` with stage-aware host target resolution and automatic working-project/design preparation
  - updated `scripts/in_aedt_agent_host.py` so queued `run_script`, `run_2d_screen`, and `run_3d_validation` commands prepare the matching 2D or 3D AEDT context before script execution
  - updated `scripts/agent_status.py` to report heartbeat freshness instead of only dumping raw queue JSON
  - added `scripts/bootstrap_agent_host.py` and `launchers/Start-AEDTHost.ps1` to produce a host bootstrap summary for the external PowerShell side
  - added `launchers/Queue-Sector3DBaselineSolve.ps1` as a FIFO queue wrapper around the full 3D baseline chain
  - added `launchers/Run-Launcher.cmd` so launcher usage still works when Windows execution policy blocks direct `.ps1` invocation
- validation target:
  - source compile check for the touched host scripts
  - direct runtime check for `bootstrap_agent_host.py`
  - direct status check for the new heartbeat freshness output
- expected limitation:
  - this iteration removes the obvious host/session blocker, but real Maxwell solve robustness still depends on the first live AEDT run of the new 3D queue chain
- next step:
  - restart the in-AEDT host, queue `Queue-Sector3DBaselineSolve.ps1`, and use the resulting solve/report artifacts to refine motion-band and periodic-sector details from actual Maxwell feedback
