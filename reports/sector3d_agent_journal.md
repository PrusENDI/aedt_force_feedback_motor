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

## Iteration 7

- goal: make local Windows PyAEDT attachment explicitly prefer COM over gRPC so the repo no longer depends on unstable gRPC startup for same-machine automation
- changes made:
  - added a shared AEDT connection policy to `config/project.json`
  - implemented shared PyAEDT interface fallback logic in `scripts/aedt_native_common.py`
  - updated the Maxwell 2D/3D attach helpers and probe scripts to use `COM -> gRPC` fallback instead of relying on PyAEDT defaults
  - updated environment probing and docs so the active connection policy is visible from artifacts and README/hosting guidance
- validation target:
  - source compile/import checks for the touched scripts
  - confirm environment probe now records `aedt_connection_policy` and PyAEDT runtime defaults
- expected limitation:
  - this improves local attachment stability, but the most stable path is still the in-AEDT host because it bypasses external transport entirely
- next step:
  - rerun `scripts/in_aedt_probe.py` and `launchers/Probe-Environment.ps1`, then continue the 3D baseline queue from the now COM-first host stack

## Iteration 8

- goal: make the 3D build loop recoverable and diagnosable when Maxwell hangs during geometry/variable updates
- changes made:
  - changed `scripts/build_sector3d_model.py` so stale `Auto3D_*` geometry is deleted before applying baseline variables, reducing the chance that Maxwell rebuilds old invalid geometry during variable writes
  - added progress callbacks to `scripts/build_sector3d_model.py`, `scripts/sector3d_scaffold.py`, and `scripts/aedt_native_common.py` so the running queue file records whether the build is setting variables, creating stator/support solids, creating phase belts, creating magnets, assigning magnet materials, or saving the project
  - added stale-running recovery to `scripts/agent_runtime.py` and host startup recovery in `scripts/in_aedt_agent_host.py`
  - guarded stale-running recovery with an age threshold so a duplicate host start does not immediately mark a genuinely active command as failed
- validation target:
  - `py_compile` on the host, common AEDT helpers, Sector3D scaffold, and Sector3D build script
  - restart the in-AEDT host and confirm old stale `runtime/running/*.json` entries are moved to `runtime/failed`
  - rerun `Queue-BuildSector3DModel.ps1` and verify the new running file advances past `sector3d_delete_old_geometry` and into `sector3d_build_phase_belts`
- expected limitation:
  - this iteration improves recovery and observability; it does not yet guarantee the full Maxwell solve converges
- next step:
  - rebuild the Sector3D template from a recovered host, inspect the fresh `sector3d_model_build.json`, then continue excitation/report binding only after the generated geometry matches the coreless axial-flux hybrid contract

## Iteration 9

- goal: make the hybrid-stator excitation path less like an iron-core slot winding surrogate and more like a coreless axial-flux radial-conductor macro model
- changes made:
  - updated `scripts/assign_sector3d_excitation.py` so each generated `Auto3D_Phase*` radial phase-belt solid receives its own Maxwell 3D coil terminal before being grouped into a phase winding
  - replaced the previous one-terminal-per-phase-polarity assignment, which was too coarse and failed on the 3D object groups produced by Maxwell
  - changed the fallback direct-current path to assign per-object current boundaries instead of one large object-group current boundary
  - recorded terminal/current counts in the excitation summary so the next AEDT run can show whether the winding path is physically bound or still falling back
- validation target:
  - `py_compile` on the excitation script
  - after the host rebuild succeeds, queue `Queue-AssignSector3DExcitation.ps1` and confirm each phase reports nonzero `coil_terminal_count`
- expected limitation:
  - the excitation is still a segmented radial macro-coil model, not the final manufacturable flat-copper crossover/return path
- next step:
  - once the macro terminals bind successfully, add explicit inner/outer return/crossover geometry for shortlisted cases and compare torque/back-EMF sensitivity

## Iteration 10

- goal: move the Sector3D geometry scaffold from full-annulus SSDR helper toward a true periodic-sector SSDR calibration scaffold
- changes made:
  - added a `sector_geometry` metadata contract in `scripts/sector3d_scaffold.py` for the 24-pole / 2-pole / 30-degree baseline sector
  - changed static rotor back-iron, stator support, and air-gap solids to use the same annular-sector generation path as magnets and phase belts
  - limited generated magnets and phase-belt flat-copper conductors to the active sector instead of all 24 poles / 72 belts
  - added generated periodic cut sheets named from config and a conservative `Auto3D_RotatingBand` clearance-shell scaffold
  - extended `scripts/build_sector3d_model.py` summaries with sector scope, cut-sheet objects, motion-band objects, and region trim status
  - changed the build script to write a pre-template-save geometry artifact before the potentially slow AEDT `SaveAs` path
  - kept `Auto3D_Region` as an expanded AEDT outer region instead of trying to subtract-trim the special Region object
  - updated the physics contract/playbook so full-annulus scaffold artifacts are treated as a regression
- validation target:
  - pure Python sector-metadata assertion for the 30-degree periodic sector
  - `py_compile` on `scripts/sector3d_scaffold.py`, `scripts/build_sector3d_model.py`, and `scripts/winding_geometry.py`
  - if the in-AEDT host is fresh, queue `Queue-BuildSector3DModel.ps1` and inspect `artifacts/sector3d_model_build.json`
- expected limitation:
  - the generated rotating band is a geometry scaffold and still needs live Maxwell motion assignment/solve feedback before torque or back-EMF can be trusted
  - live AEDT rebuild wrote a pre-template-save `artifacts/sector3d_model_build.json` with `sector_geometry.geometry_scope = periodic_sector`, but the host command is still running/stalled in `sector3d_save_template`
  - the artifact still blocks solve readiness on missing `Auto3D_PM_Axial_PlusZ` and `Auto3D_PM_Axial_MinusZ` project material definitions
- next step:
  - rebuild the Sector3D template in AEDT, confirm `sector_geometry.geometry_scope = periodic_sector`, then let the solve agent bind master/slave boundaries, motion, excitations, and reports from the new sector geometry

## Iteration 11

- goal: stop silent blank-project creation and reduce AEDT `file is in use` save prompts while keeping the new Maxwell-compatible rotating band flow intact
- changes made:
  - kept the Sector3D scaffold on the `Auto3D_RotatingBand` double-rotor container path that now yields `motion_assigned = true` in the latest live transient-setup artifact
  - patched `scripts/build_sector3d_model.py` so the queue build keeps `aedt_projects/sector3d_working.aedt` as the authoritative open project, closes stale open template copies before publishing, and publishes `templates/sector3d_template.aedt` by file copy instead of `SaveAs`
  - patched `scripts/aedt_native_common.py -> open_or_create_project()` so an existing working file is retried and then fails loudly if `OpenProject` cannot attach, instead of silently creating a new blank Maxwell project over the same workflow
  - updated `reports/sector3d_playbook.md` to document the new working-file discipline for queued Sector3D runs
- validation target:
  - `py_compile` on `scripts/sector3d_scaffold.py`, `scripts/build_sector3d_model.py`, `scripts/winding_geometry.py`, and the touched AEDT common helper
  - local source assertions that `build_sector3d_model.py` no longer calls `_save_template_copy()` and `open_or_create_project()` no longer uses blank-project fallback when the working file already exists
  - latest live host evidence before this final open/save patch: `artifacts/sector3d_model_build.json` at `2026-04-24T03:54:24Z` shows `motion_band_objects[0].role = rotating_band_double_rotor_container`, and `artifacts/sector3d_transient_setup.json` at `2026-04-24T03:54:28Z` shows `band_object_exists = true` and `motion_assigned = true`
- expected limitation:
  - the newest open/save-flow patch has not yet been rerun through a fresh in-AEDT host in this session, because the last host heartbeat is stale and no live host loop is currently available to drain a new queue command
  - the build still blocks physical solve signoff on missing oriented project materials `Auto3D_PM_Axial_PlusZ` and `Auto3D_PM_Axial_MinusZ`
- next step:
  - restart the in-AEDT host, queue `Queue-BuildSector3DModel.ps1`, confirm the build reuses/opens `sector3d_working.aedt` without creating a blank replacement, then queue `Queue-ApplySector3DTransientSetup.ps1` and verify `motion_assigned = true` still holds under the revised save flow

## Iteration 12

- goal: live-verify the revised Sector3D working/template save flow on a fresh in-AEDT host and confirm the Maxwell-compatible rotating band still binds after the build
- changes made:
  - no source-code changes this round; focused on live AEDT validation after the host restart
  - queued `Queue-BuildSector3DModel.ps1` through `Run-Launcher.cmd` and inspected the fresh host/build logs, heartbeat, and `artifacts/sector3d_model_build.json`
  - queued `Queue-ApplySector3DTransientSetup.ps1` through `Run-Launcher.cmd` and inspected the fresh host/setup logs, heartbeat, and `artifacts/sector3d_transient_setup.json`
- validation evidence:
  - `runtime/heartbeat.json` at `2026-04-24T04:40:58Z` showed `worker_state = sector3d_build_phase_belts` with `project_list = ["Project2", "sector3d_working"]`; `sector3d_template` was no longer open during the live build
  - `logs/in_aedt_agent_host_2026-04-24T04-38-13Z.log` recorded `Reusing working project: ...\\aedt_projects\\sector3d_working.aedt` and `Reused already-open project: sector3d_working` for both the build command and the transient-setup command
  - the same host log did not emit the old `OpenProject failed ... attempting blank-project fallback` or `Created new project` messages during either queue run
  - `logs/build_sector3d_model_2026-04-24T04-40-41Z.log` ended with `Copied Sector3D working project to canonical template path` and `Copied Sector3D template file to backup path`, confirming the queue build published by file copy instead of `SaveAs`
  - `artifacts/sector3d_model_build.json` at `2026-04-24T04:41:30Z` now keeps `project_name = sector3d_working`, `project_save_status.template_copy.working_copy_synced = true`, and `motion_band_objects[0].role = rotating_band_double_rotor_container`
  - `artifacts/sector3d_transient_setup.json` at `2026-04-24T04:42:11Z` keeps `project_name = sector3d_working`, `band_object_exists = true`, and `motion_assigned = true`
- interpretation:
  - the fresh live rerun removed the earlier evidence of silent blank-project creation for the working `.aedt` path
  - the queue build/apply path completed without any logged sign of the prior save-flow lockup; while AEDT GUI popups are not directly machine-readable here, the working-project reuse, absence of fallback logs, absence of an open template project during the run, and successful save/copy completion are all consistent with the `file is in use` prompt no longer blocking this flow
- remaining limitation:
  - the build still blocks physics-ready solve signoff on missing oriented project materials `Auto3D_PM_Axial_PlusZ` and `Auto3D_PM_Axial_MinusZ`
- next step:
  - restore or auto-generate the oriented axial PM project materials, then rerun the build/apply/solve chain to move from geometry/setup verification into real Maxwell transient validation
