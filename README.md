# AEDT Force Feedback Motor Skeleton

This folder is a lightweight automation skeleton for an axial-flux force-feedback steering motor study in AEDT.

The workflow is intentionally disk-conscious and now aims for a more transient-friendly 2D baseline:

1. Use one reusable `Maxwell 2D` linearized transient-ready project for coarse screening.
2. Export CSV reports for each case instead of keeping heavy field data.
3. Promote only the best cases into a `Maxwell 3D` sector validation stage.
4. Keep one working project per stage and store results mainly in `reports/` and `exports/`.
5. Support a manual-launch workflow where you start AEDT yourself and an in-AEDT host script accepts queued commands from an external AI agent.

## Folder layout

- `config/` holds the design targets, search space, and ranking rules.
- `scripts/` holds AEDT-native Python scripts meant to run through `ansysedt.exe -RunScriptAndExit`.
  - `scripts/linear2d_scaffold.py` owns the `Linearized2D` auto-generated scaffold.
  - `scripts/sector3d_scaffold.py` owns the `Sector3D` scaffold and is intentionally separated from the 2D geometry logic.
  - `scripts/build_hooks.py` remains only as a thin compatibility wrapper.
- `launchers/` holds PowerShell helpers that detect `ansysedt.exe` and start the correct stage.
- `cases/` holds the generated or edited case tables.
- `templates/` documents the one-time AEDT template contract.
- `aedt_projects/` is where the reusable working `.aedt` projects are stored.
- `exports/` stores per-case CSV exports from AEDT reports.
- `reports/` stores summary CSV and markdown recommendations.
- `logs/` stores run logs.
- `artifacts/` stores optional snapshots and cached metadata.
- `runtime/` stores the external-agent handoff queue, session state, heartbeat, and completed command records.

## Preferred operating mode

The recommended mode on this machine is:

1. Start AEDT yourself.
2. Inside AEDT, use `Run PyAEDT Script` to run `scripts/in_aedt_agent_host.py`.
3. Let the external AI agent queue commands into `runtime/pending/`.
4. Let the in-AEDT host consume those commands and write results into `runtime/done/`, `runtime/failed/`, `reports/`, and `exports/`.

The project still uses `template_mode`.

In this mode you build two small AEDT template projects once, then let the scripts handle:

1. case generation
2. variable updates
3. solve calls
4. report export
5. ranking
6. shortlist handoff from 2D to 3D

This is more reliable than trying to generate a full axial-flux model from scratch only through script.

For environment control, the workspace now prefers the user-level PyAEDT environment:

- `C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe`
- `C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\pyaedt.exe`

If external gRPC startup is unstable on this machine, treat AEDT as a manually launched host process and use the in-AEDT worker scripts instead of trying to create fresh AEDT sessions from the shell.

The repo now also prefers `COM -> gRPC` for external PyAEDT attachment on Windows when it must attach from outside AEDT.

See `templates/TEMPLATE_CONTRACT.md` for the required design names, variables, and report names.
For the first 2D template build, also see `templates/LINEAR2D_TEMPLATE_SETUP.md`.
For step-by-step manual building, also see:

- `templates/AEDT_LINEAR2D_MODEL_BUILD_GUIDE.md`
- `templates/AEDT_5_REPORTS_SETUP_GUIDE.md`

Additional reference files:

- `HOSTING_GUIDE.md`
- `CURRENT_SIM_REQUIREMENTS.md`
- `reports/sector3d_playbook.md`
- `reports/sector3d_physics_contract.md`
- `reports/sector3d_agent_prompt.md`
- `reports/sector3d_agent_journal.md`

## External Launch Workflow

1. Edit `config/project.json` if you want to change the default paths or screening limits.
2. Run `launchers/Probe-Environment.ps1` to capture the current AEDT and PyAEDT status.
3. Run `launchers/Start-AEDTHost.ps1` to prepare the runtime queue and write the host bootstrap summary.
4. Start AEDT manually from the desktop or Start menu.
5. Inside AEDT, use `Run PyAEDT Script` and run `scripts/in_aedt_probe.py` once if you want a quick attachment check.
6. Inside AEDT, use `Run PyAEDT Script` and run `scripts/in_aedt_agent_host.py` to start the persistent in-AEDT worker.
6. From outside AEDT, queue work with:
   - `launchers/Queue-ProbeSession.ps1`
   - `launchers/Queue-BootstrapLinear2DTemplate.ps1`
   - `launchers/Queue-ValidateLinear2DTemplate.ps1`
   - `launchers/Queue-BuildLinear2DModel.ps1`
   - `launchers/Queue-BuildSector3DModel.ps1`
   - `launchers/Queue-AssignSector3DExcitation.ps1`
   - `launchers/Queue-ApplySector3DTransientSetup.ps1`
   - `launchers/Queue-CreateSector3DReports.ps1`
   - `launchers/Queue-SolveSector3DSetup.ps1`
   - `launchers/Queue-Sector3DBaselineSolve.ps1`
   - `launchers/Queue-ApplyLinear2DPhysicsSetup.ps1`
   - `launchers/Queue-AssignLinear2DExcitation.ps1`
   - `launchers/Queue-CreateLinear2DReports.ps1`
   - `launchers/Queue-2DScreening.ps1`
   - `launchers/Queue-3DValidation.ps1`
   - `launchers/Queue-Command.ps1 -Action run_script -ScriptPath scripts/your_script.py`
7. Inspect state with `launchers/Get-AgentStatus.ps1`.
8. Stop the worker with `launchers/Queue-StopAgent.ps1`.

If Windows PowerShell execution policy blocks direct `.ps1` launches on this machine, use:

- `launchers\Run-Launcher.cmd Start-AEDTHost.ps1`
- `launchers\Run-Launcher.cmd Queue-Sector3DBaselineSolve.ps1`
- `launchers\Run-Launcher.cmd Get-AgentStatus.ps1`

## What The Agent Controls

When the in-AEDT host is running, the external AI agent can safely:

1. Check whether AEDT is alive and attached.
2. Trigger the 2D screening pipeline.
3. Trigger the 3D validation pipeline.
4. Queue a custom workspace script for execution inside the live AEDT session.
5. Observe live progress, completion, and failures through the `runtime/` state files.
6. Resume long 2D/3D batches from prior summary files instead of restarting from zero.

## Disk-saving defaults

- `Maxwell 2D` uses a single reusable transient-ready project file.
- 2D report export is CSV-only by default.
- 2D field saving is disabled by policy.
- Only the top `N` cases are promoted to 3D.
- 3D is intended for sector validation, not full-machine brute-force search.

## Notes

- The existing `Start-2DScreening.ps1` and `Start-3DValidation.ps1` launchers are still present for direct-launch experiments, but the queue-based host mode is the preferred workflow here.
- The scripts are written to stay compatible with AEDT native scripting first and to be callable from an in-AEDT Python host.
- If you later decide to switch launch strategies again, the same `config/` and `cases/` files can still be reused.
- The ranking layer uses proxy metrics when a report is missing, so the pipeline can still move forward while you flesh out the template.
- Long-running host-mode batches now support per-command progress updates, resumable summaries, and dedicated failure CSVs.
- The 2D baseline is now being pushed toward a transient workflow with windings, flux linkage, and back-EMF outputs, but physically rigorous back-EMF still benefits from a later motion/band refinement step.
