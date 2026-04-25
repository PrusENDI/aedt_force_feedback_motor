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

## Iteration 13

- goal: auto-generate the missing `Auto3D_PM_Axial_PlusZ` / `Auto3D_PM_Axial_MinusZ` project materials inside Maxwell and re-run the live build/apply/solve chain
- changes made:
  - updated `scripts/sector3d_scaffold.py` so `assign_axial_magnet_materials()` no longer treats missing oriented PM project materials as a hard stop without trying to create them
  - added a local 3D material-attach path that reuses the active AEDT desktop, attaches Maxwell 3D through PyAEDT, duplicates the base NdFeB material into `Auto3D_PM_Axial_PlusZ` and `Auto3D_PM_Axial_MinusZ`, and sets the coercivity vector to `+Z` / `-Z`
  - kept the final material assignment on the existing native geometry-attribute path, so the fix only changes how missing project materials are prepared
- regression check before implementation:
  - a focused one-off Python regression script against `assign_axial_magnet_materials()` failed while the project-material map only contained the base magnet material, proving the 3D entry point ignored the possibility of creating missing oriented materials
- validation evidence after implementation:
  - the same focused regression script passed after the `sector3d_scaffold.py` change
  - `py_compile scripts/sector3d_scaffold.py scripts/build_sector3d_model.py scripts/winding_geometry.py` passed
  - fresh live build at `2026-04-24T04:53:53Z` wrote `artifacts/sector3d_model_build.json` with:
    - `magnet_assignment.assigned_ok = true`
    - `magnet_assignment.ensured_materials` containing both `Auto3D_PM_Axial_PlusZ` and `Auto3D_PM_Axial_MinusZ`
    - `baseline_ready_for_solve = true`
    - `physics_ready_for_validation = true`
  - `logs/build_sector3d_model_2026-04-24T04-53-07Z.log` recorded:
    - `Duplicated material Magnet, permanent, Neodymium N42SH -> Auto3D_PM_Axial_PlusZ`
    - `Duplicated material Magnet, permanent, Neodymium N42SH -> Auto3D_PM_Axial_MinusZ`
    - `Assigned material Auto3D_PM_Axial_PlusZ to 2 objects`
    - `Assigned material Auto3D_PM_Axial_MinusZ to 2 objects`
  - fresh live transient setup at `2026-04-24T04:54:19Z` kept `artifacts/sector3d_transient_setup.json -> motion_assigned = true`
- remaining limitation:
  - the downstream solve-chain blocker has now moved out of the geometry/material path and into the Sector3D solve stack:
    - `artifacts/sector3d_excitation_assignment.json` shows all three phases failed winding assignment and even the fallback direct-current boundaries were not created
    - `logs/assign_sector3d_excitation_2026-04-24T04-54-45Z.log` then shows `Project save failed` via gRPC `Save`
    - the following queued `solve_sector3d_setup` and `create_sector3d_reports` commands failed in host preparation because `OpenProject(working)` failed three times and the no-blank-fallback guard correctly refused to create a replacement project
- next step:
  - hand the chain to the Sector3D Solve owner to fix Maxwell 3D excitation boundary creation and the post-excitation save/open failure, then rerun the full `assign -> reports -> solve` validation on the now-correct oriented-PM geometry

## Iteration 14

- goal: make the Sector3D solve stack more Maxwell 3D compatible and separate script-side excitation bugs from host-side project-open failures
- changes made:
  - updated `scripts/assign_sector3d_excitation.py` so each segmented radial phase-belt solid now resolves its inner and outer radial terminal faces before creating Maxwell 3D coil terminals or fallback current boundaries
  - changed the 3D winding assignment so each belt object contributes a positive and a negative terminal on the proper conductor end faces instead of trying to bind a whole solid as one terminal
  - added stronger traceback logging in the excitation script so future boundary failures keep the full Maxwell/PyAEDT context
  - added `save_sector3d_project()` in `scripts/sector3d_aedt.py` and switched `assign_sector3d_excitation.py`, `create_sector3d_reports.py`, and `solve_sector3d_setup.py` to use the native save path first and then a PyAEDT project-save fallback
  - updated `scripts/aedt_native_common.py -> open_or_create_project()` so the host tries `GetActiveProject()` and `SetActiveProject(project_name)` before attempting `OpenProject()` when the working project already exists
- regression checks before and after implementation:
  - one-off red/green regression for the new radial terminal-face selector in `assign_sector3d_excitation.py`; before the patch the helper did not exist, after the patch it correctly chose the minimum-radius and maximum-radius faces
  - one-off red/green regression for `open_or_create_project()` with a fake AEDT desktop where `GetProjectList()` is empty but `GetActiveProject()` already matches `sector3d_working`; before the patch it still tried `OpenProject()`, after the patch it reused the active project
- validation evidence after implementation:
  - `py_compile` passed on `scripts/aedt_native_common.py`, `scripts/sector3d_scaffold.py`, `scripts/build_sector3d_model.py`, `scripts/winding_geometry.py`, `scripts/sector3d_aedt.py`, `scripts/assign_sector3d_excitation.py`, `scripts/create_sector3d_reports.py`, and `scripts/solve_sector3d_setup.py`
  - queued `Queue-AssignSector3DExcitation.ps1` at `2026-04-24T05:26:58Z` and again at `2026-04-24T05:29:53Z`; both failed during host preparation before the excitation script body ran
  - fresh `probe_session` queue run at `2026-04-24T05:30:41Z` succeeded but still reported `active_project = null` and `project_list = []`
  - external workstation observation at the same time showed `ansysedt.exe` main window title `Ansys Electronics Desktop 2024 R1 - sector3d_working - Sector3D - 3D Modeler - [sector3d_working - Sector3D - Modeler]`, so the GUI still appears to have the project open while the in-AEDT host cannot see it through its current desktop object
- interpretation:
  - the solve-side code is now materially better aligned with Maxwell 3D radial-conductor excitation requirements
  - the current live blocker is no longer just boundary creation; the in-AEDT host's desktop object has drifted into a state where it cannot report or reactivate the already-open `sector3d_working` project, so queued solve scripts never reach their actual logic
- remaining limitation:
  - there is no fresh post-patch `sector3d_excitation_assignment.json` yet because the host never entered `scripts/assign_sector3d_excitation.py` in this round
  - until the host desktop state is refreshed, `assign -> reports -> solve` cannot be revalidated from the queue even though the script-side fixes are in place
- next step:
  - restart or reattach the in-AEDT host so the desktop object again reports the open `sector3d_working` project, then rerun `Queue-AssignSector3DExcitation.ps1`, `Queue-CreateSector3DReports.ps1`, and `Queue-SolveSector3DSetup.ps1`

## Iteration 15

- goal: rerun the live `assign -> reports -> solve` chain on a fresh host, identify the first failing Maxwell call inside the excitation script, and make the fallback path less dependent on a still-healthy PyAEDT modeler cache
- changes made:
  - no geometry-side changes this round
  - updated `scripts/assign_sector3d_excitation.py` again so each phase precomputes and caches all radial terminal-face specs before attempting any boundary creation
  - changed the fallback direct-current path to consume those cached face specs instead of re-querying `app.modeler.get_object_from_name()` after a failed coil-terminal attempt
- regression checks before and after implementation:
  - one-off red/green regression for `_assign_phase_with_direct_current(..., terminal_specs=...)`; before the patch the function did not accept cached terminal specs, after the patch it used the supplied face ids and created four fallback current boundaries in the stubbed test
- validation evidence after implementation:
  - fresh host heartbeat at `2026-04-24T08:59:04Z` and fresh queued `probe_session` at `2026-04-24T08:59:30Z` both showed `active_project = sector3d_working` and `project_list = ["Project2", "sector3d_working"]`
  - fresh queued `Queue-AssignSector3DExcitation.ps1` at `2026-04-24T08:59:52Z` now entered the script body successfully, attached Maxwell 3D, and reused the existing phase-belt objects
  - `logs/assign_sector3d_excitation_2026-04-24T08-59-55Z.log` shows the first live Maxwell boundary failure is still `AssignCoilTerminal` on `PhaseA_Coil_Pos_Terminal_001`
  - the same excitation run still ended with project save failure through all three save paths (`native`, `pyaedt_app`, `pyaedt_oproject`), after which the host heartbeat dropped back to `active_project = null` and `project_list = []`
  - after that host-state loss, rerunning `Queue-CreateSector3DReports.ps1` at `2026-04-24T09:05:44Z` and `Queue-SolveSector3DSetup.ps1` at `2026-04-24T09:06:18Z` both failed in host preparation with `Could not open existing AEDT project ... sector3d_working.aedt after retries`
- interpretation:
  - the fresh rerun narrowed the live Maxwell-side blocker to one specific call: `AssignCoilTerminal`
  - the solve-chain still has a second blocker after the boundary failure: once the excitation script reaches the failing save path, the in-AEDT host loses visibility of the open working project and the remaining queued solve stages cannot re-enter the project
  - the new cached-terminal fallback patch is in place, but it has not yet been live-validated on a fresh host because the host became unhealthy before a second excitation rerun could start
- next step:
  - restart the in-AEDT host again and rerun `Queue-AssignSector3DExcitation.ps1` once more so the new cached-fallback path can be tested against the same fresh `sector3d_working` session before attempting reports/solve again

## Iteration 16

- goal: verify the cached-terminal fallback on a fresh host using only `Queue-AssignSector3DExcitation.ps1`, then tighten the fallback so one failed phase does not poison the remaining phase discovery path
- changes made:
  - re-read the active Sector3D contract/config/journal/coordination files and reran a fresh host probe before touching the excitation flow
  - reran `Queue-ProbeSession.ps1` at `2026-04-24T09:15:19Z` and confirmed the fresh host still saw `active_project = sector3d_working` and `project_list = ["Project2", "sector3d_working"]`
  - reran `Queue-AssignSector3DExcitation.ps1` at `2026-04-24T09:15:43Z` and captured the next live failure signature from the fresh host
  - updated `scripts/assign_sector3d_excitation.py` again so all three phases cache their terminal-face specs before any winding/current boundary is attempted
  - updated the fallback direct-current path so each boundary now tries the cached terminal face first with the A-Phi internal-conductor excitation model and then retries on the cached object name if the face assignment is rejected
- regression checks before and after implementation:
  - one-off regression for `_assign_current_boundary_with_variants(...)`; after the patch it first tries the cached face with `excitation_model = "Double Potentials"` and then falls back to the cached object without re-querying the modeler
- validation evidence after implementation:
  - `runtime/heartbeat.json` at `2026-04-24T09:14:35Z` already showed `active_project = sector3d_working` and `project_list = ["Project2", "sector3d_working"]`
  - fresh queued `probe_session` at `2026-04-24T09:15:20Z` again showed `active_project = sector3d_working` and `project_list = ["Project2", "sector3d_working"]`
  - fresh queued `Queue-AssignSector3DExcitation.ps1` at `2026-04-24T09:15:43Z` entered the script body and completed at `2026-04-24T09:15:52Z`
  - `logs/assign_sector3d_excitation_2026-04-24T09-15-45Z.log` shows:
    - `AssignCoilTerminal` still fails first on `PhaseA_Coil_Pos_Terminal_001`
    - the cached fallback now progresses past the old `GetObjectsInGroup` failure and reaches a real Maxwell `AssignCurrent` call on `PhaseA_Current_Pos_001`
    - after `PhaseA` fails, `PhaseB` and `PhaseC` still lose terminal-face discovery to `GetObjectsInGroup`, proving per-phase caching was still too late in the prior patch
  - `artifacts/sector3d_excitation_assignment.json` at `2026-04-24T09:15:52Z` records:
    - `PhaseA -> used_fallback_current_boundaries = true`, `details = Failed to create boundary Current PhaseA_Current_Pos_001`
    - `PhaseB` / `PhaseC -> terminal-face discovery failed before excitation assignment` with `details = Failed to execute gRPC AEDT command: GetObjectsInGroup`
    - `save_ok = false`, `save_error = Failed to execute gRPC AEDT command: Save`
  - the same excitation run again dropped the host heartbeat back to `active_project = null` and `project_list = []`
  - `py_compile` passed on `scripts/assign_sector3d_excitation.py`, `scripts/create_sector3d_reports.py`, `scripts/solve_sector3d_setup.py`, `scripts/sector3d_aedt.py`, `scripts/aedt_native_common.py`, `scripts/sector3d_scaffold.py`, `scripts/build_sector3d_model.py`, and `scripts/winding_geometry.py`
- interpretation:
  - the cached-terminal fallback is now partially validated: it does survive the first `AssignCoilTerminal` failure well enough to attempt a real `AssignCurrent`
  - the next Maxwell-side blocker is no longer modeler refresh on `PhaseA`; it is the current boundary creation itself
  - the follow-on `PhaseB/C` `GetObjectsInGroup` failures came from the previous per-phase caching order, and the new all-phase pre-cache patch is now in place to remove that dependency on a still-healthy modeler
  - the new all-phase cache plus face/object current-variant retry has not yet been live-validated because this fresh host became unhealthy again after the failed save path
- next step:
  - restart the in-AEDT host again and rerun `Queue-AssignSector3DExcitation.ps1` once more so the new all-phase cache and internal-conductor direct-current retry path can be live-validated before attempting reports/solve

## Iteration 17

- goal: live-validate the new all-phase terminal pre-cache plus `cached face -> cached object` direct-current retry path on a fresh host, without running reports or solve
- changes made:
  - no source-code changes this round; focused on fresh host validation only
  - re-read the active git/config/physics-contract/journal/coordination state and confirmed the latest `assign_sector3d_excitation.py` patch was loaded before queueing the run
  - reran `Queue-ProbeSession.ps1` at `2026-04-24T09:24:14Z` and confirmed the fresh host saw `active_project = sector3d_working` and `project_list = ["Project2", "sector3d_working"]`
  - reran `Queue-AssignSector3DExcitation.ps1` at `2026-04-24T09:24:44Z` and captured the first full live run of the new all-phase pre-cache branch
- validation evidence:
  - `runtime/heartbeat.json` at `2026-04-24T09:24:06Z` already showed `active_project = sector3d_working` and `project_list = ["Project2", "sector3d_working"]`
  - `runtime/last_result.json` finished at `2026-04-24T09:25:07Z` with `prepared = true`, `project_name = sector3d_working`, and then the same post-script heartbeat collapse back to `active_project = null`
  - `logs/assign_sector3d_excitation_2026-04-24T09-24-46Z.log` now shows for all three phases:
    - `AssignCoilTerminal` still fails first on the first positive terminal of each phase
    - fallback direct current is attempted for `PhaseA`, `PhaseB`, and `PhaseC`, so the new all-phase pre-cache successfully removed the old `PhaseB/C -> GetObjectsInGroup` regression
    - each fallback now records both retry branches in the same failure string:
      - `PhaseA`: `face=5602 ... ; object=Auto3D_PhaseA_Pos_Bottom_001 ...`
      - `PhaseB`: `face=6038 ... ; object=Auto3D_PhaseB_Pos_Bottom_003 ...`
      - `PhaseC`: `face=6474 ... ; object=Auto3D_PhaseC_Pos_Bottom_005 ...`
  - `artifacts/sector3d_excitation_assignment.json` at `2026-04-24T09:25:06Z` now records `used_fallback_current_boundaries = true` for all three phases and no longer records any `GetObjectsInGroup` terminal-discovery failure
  - the same run still ends with `save_ok = false`, `save_error = Failed to execute gRPC AEDT command: Save`, and the host heartbeat again drops to `active_project = null`, `project_list = []`
- interpretation:
  - the new all-phase pre-cache patch is now live-validated: `PhaseB` and `PhaseC` no longer depend on a still-healthy modeler after `PhaseA` fails
  - the current root blocker has narrowed further: Maxwell 3D is rejecting both excitation creation APIs for this geometry in this transient design
    - `AssignCoilTerminal` fails on cached conductor end faces
    - `AssignCurrent` also fails on both cached face and cached object retries
  - the remaining live host-state loss is still downstream of the excitation/save failure, not upstream project opening
- next step:
  - investigate whether this `Transient` Maxwell 3D design requires a different excitation primitive for these segmented solids, or whether the conductor bodies must be rebuilt/flagged differently before `AssignCoilTerminal` / `AssignCurrent` will bind

## Iteration 18

- goal: rerun only `Queue-AssignSector3DExcitation.ps1` after another in-AEDT host restart and verify whether the cached terminal fallback can create direct-current boundaries after `AssignCoilTerminal` fails
- changes made:
  - no source-code changes this round
  - re-read the active git/config/physics-contract/journal/coordination state and the current `scripts/assign_sector3d_excitation.py` before queueing the run
  - confirmed the fresh host heartbeat at `2026-04-25T03:31:26Z` showed `active_project = sector3d_working`, `project_list = ["sector3d_working"]`, and `worker_state = idle`
  - queued only `Queue-AssignSector3DExcitation.ps1` at `2026-04-25T03:31:42Z`; did not queue reports or solve
- validation evidence:
  - `runtime/last_result.json` for command `73531a530e3e43e0a4f444596fd2be19` finished at `2026-04-25T03:32:05Z` with `prepared = true`, `project_name = sector3d_working`, and `result = script_complete`
  - `logs/assign_sector3d_excitation_2026-04-25T03-31-46Z.log` shows the same repeatable excitation failure signature:
    - `PhaseA`: `AssignCoilTerminal` fails first, then fallback `AssignCurrent` fails on both `face=5602` and `object=Auto3D_PhaseA_Pos_Bottom_001`
    - `PhaseB`: `AssignCoilTerminal` fails first, then fallback `AssignCurrent` fails on both `face=6038` and `object=Auto3D_PhaseB_Pos_Bottom_003`
    - `PhaseC`: `AssignCoilTerminal` fails first, then fallback `AssignCurrent` fails on both `face=6474` and `object=Auto3D_PhaseC_Pos_Bottom_005`
  - `artifacts/sector3d_excitation_assignment.json` at `2026-04-25T03:32:04Z` records `used_fallback_current_boundaries = true` for all three phases, but `current_excitations = []` and all phase `assigned` fields remain `false`
  - the same run still ends with `save_ok = false`, `save_error = Failed to execute gRPC AEDT command: Save`
  - post-run heartbeat again drops to `active_project = null` and `project_list = []`
- interpretation:
  - cached terminal fallback is executing consistently, but it still cannot land direct-current boundaries in this Maxwell 3D Transient design
  - the failure is now repeatable across fresh host restarts and no longer depends on stale host startup state
  - reports/solve should remain paused until the excitation primitive or conductor-body compatibility is corrected
- next step:
  - investigate Maxwell 3D Transient excitation compatibility for these generated flat-copper solids, especially whether the model needs a different excitation primitive, conductor body setup, or explicit source/sink sheet geometry before current can be applied

## Iteration 19

- goal: choose a Maxwell 3D Transient excitation primitive for the generated flat-copper radial solids and make the smallest code change before the next fresh-host assign-only rerun
- investigation:
  - `assign_winding(...)` in the installed PyAEDT Maxwell 3D layer creates a winding group, but any non-empty assignment is converted into `assign_coil(...)`, so it does not bypass the failing `AssignCoilTerminal` primitive
  - `assign_current(...)` is a legal API path, but repeated fresh-host runs show Maxwell rejects both cached curved end faces and whole conductor objects in this transient design
  - `assign_current_density(...)` is explicitly rejected by PyAEDT for Maxwell 3D `Transient`, and `assign_current_density_terminal(...)` is limited to Eddy/AC/Magnetostatic style solvers
  - stranded winding is not a physics fix for the intended flat copper solids because it still depends on accepted terminals and is less faithful to the solid flat-copper conductor path
  - the next lowest-risk primitive is explicit source/sink sheet geometry at each conductor segment's inner/outer radial end, assigned as `CoilTerminal` objects and then grouped into solid current windings
- changes made:
  - updated `scripts/assign_sector3d_excitation.py` to create deterministic `Auto3D_SourceSink_*` terminal sheets for every cached phase-belt segment before any boundary creation
  - changed winding-terminal assignment to prefer those sheet objects over the previous curved end-face ids
  - extended fallback direct-current diagnostics to try `sheet -> cached face -> cached object`
  - documented the primitive comparison in `reports/sector3d_playbook.md`
- validation evidence:
  - focused regression check proved the new source/sink helper exists and generates deterministic terminal-sheet names
  - focused fake-app check proved `_assign_phase_with_winding_group(...)` now calls `assign_coil(...)` with sheet object names rather than face ids when sheets are available
  - `py_compile scripts/assign_sector3d_excitation.py scripts/sector3d_scaffold.py scripts/build_sector3d_model.py scripts/winding_geometry.py` passed
- remaining limitation:
  - live assign-only rerun was not queued after this patch because the current in-AEDT host heartbeat still reports `active_project = null`, `project_list = []`, and `worker_state = idle`; this is not a fresh usable host state for validating the new primitive
  - the turn/coil parameter model is still a segmented macro phase-belt calibration abstraction; it follows the repo physics contract, but it is not yet a paper-faithful manufacturable winding with explicit crossover/return/interconnect geometry
- next step:
  - restart the in-AEDT host so it can see `sector3d_working`, then run only `Queue-AssignSector3DExcitation.ps1` and inspect whether `PhaseA_Coil_Pos_Terminal_001` is created from `Auto3D_SourceSink_PhaseA_Pos_Bottom_001_Inner` before attempting reports or solve
