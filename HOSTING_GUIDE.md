# AEDT Agent Hosting Guide

This workspace supports a hosted simulation workflow:

1. You manually start AEDT.
2. Inside AEDT, you run the in-process host script once.
3. An external agent queues commands into the workspace.
4. The live AEDT host consumes those commands and writes results back to the workspace.

This is the recommended workflow for this machine because direct external AEDT session startup through PyAEDT gRPC is not yet stable enough to rely on for long runs.

Current connection priority on this machine is:

1. in-AEDT `ScriptEnv` / hosted worker
2. external COM attach to an already running local AEDT session
3. gRPC only as a fallback

## Can this workspace detect Codex locally?

Yes, the machine already exposes a local Codex installation and active Codex-related processes.

What this means:

- A local `codex.exe` command exists.
- Codex-related processes are visible on the machine.
- The workspace can be used as a shared handoff point between the live AEDT session and the external agent.

What this does not mean:

- The workspace does not automatically take over an arbitrary local Codex GUI/terminal session.
- The hosted simulation flow is file-queue based, not process-injection based.
- The reliable handoff contract is the `runtime/` queue in this workspace.

## Recommended hosting model

Use this workspace as the control plane:

- AEDT stays open and attached to the active project.
- `scripts/in_aedt_agent_host.py` runs inside AEDT.
- External agent actions are represented as JSON command files in `runtime/pending/`.
- Results are written to:
  - `runtime/done/`
  - `runtime/failed/`
  - `runtime/heartbeat.json`
  - `runtime/session.json`
- `runtime/last_result.json`
- `reports/`
- `exports/`

While a queued batch is running, the active command file in `runtime/running/` is updated with:

- current stage
- current message
- current case index when available
- completion/failure result at the end

## One-time preparation

1. Confirm the workspace root is:
   - `C:\weizijian\documents\motor\aedt_force_feedback_motor`
2. Confirm PyAEDT environment exists:
   - `C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe`
3. Confirm AEDT templates are prepared according to:
   - `templates/TEMPLATE_CONTRACT.md`

## Start hosting

### Step 1: Probe the environment

Run in PowerShell:

```powershell
.\launchers\Probe-Environment.ps1
```

Expected artifact:

- `artifacts/environment_status.json`

### Step 2: Start AEDT manually

Open AEDT yourself and keep the target project open.

Recommended:

- Open the project you want the host to control.
- Keep AEDT running for the full batch.

### Step 3: Verify in-AEDT script execution

Inside AEDT, use `Run PyAEDT Script` and run:

- `scripts/in_aedt_probe.py`

Expected artifact:

- `artifacts/inside_aedt_probe.json`

### Step 4: Start the persistent host

Inside AEDT, use `Run PyAEDT Script` and run:

- `scripts/in_aedt_agent_host.py`

Expected behavior:

- A console/log window shows the host starting.
- `runtime/heartbeat.json` starts updating.
- `runtime/session.json` is written.
- queued scripts will now auto-open and activate the matching 2D or 3D working design before they run

## Send commands from outside AEDT

If direct `.ps1` execution is blocked by Windows execution policy, use:

```cmd
launchers\Run-Launcher.cmd Start-AEDTHost.ps1
launchers\Run-Launcher.cmd Queue-ProbeSession.ps1
launchers\Run-Launcher.cmd Queue-Sector3DBaselineSolve.ps1
launchers\Run-Launcher.cmd Get-AgentStatus.ps1
```

### Probe the live session

```powershell
.\launchers\Queue-ProbeSession.ps1
```

### Queue 2D screening

```powershell
.\launchers\Queue-2DScreening.ps1
```

### Queue 3D validation

```powershell
.\launchers\Queue-3DValidation.ps1
```

### Queue a custom script

```powershell
.\launchers\Queue-Command.ps1 -Action run_script -ScriptPath scripts/host_session_probe.py
```

### Queue the 3D baseline solve loop

```powershell
.\launchers\Queue-Sector3DBaselineSolve.ps1
```

### Stop the host

```powershell
.\launchers\Queue-StopAgent.ps1
```

## Monitor hosting status

Run:

```powershell
.\launchers\Get-AgentStatus.ps1
```

Important files:

- `runtime/heartbeat.json`: whether the host is alive
- `runtime/session.json`: current AEDT session snapshot
- `runtime/last_result.json`: most recent completed command
- `runtime/pending/`: queued commands waiting to run
- `runtime/running/`: command currently being executed
- `runtime/done/`: completed commands
- `runtime/failed/`: failed commands
- `reports/2d_screening_failures.csv`: failed 2D cases
- `reports/3d_validation_failures.csv`: failed 3D cases

## Typical operating loop

1. Start AEDT.
2. Start `in_aedt_agent_host.py` once.
3. Queue `probe_session`.
4. Queue `run_2d_screen`.
5. Review `reports/2d_screening_ranked.csv`.
6. Queue `run_3d_validation`.
7. Review `reports/3d_validation_ranked.csv`.
8. Queue custom analysis scripts as needed.

The batch scripts now support:

- leaving the active AEDT project open in host mode
- resuming from existing summary CSV files
- continuing when a single case fails
- writing failed cases to dedicated failure CSVs

## Failure handling

If a command fails:

1. Check `runtime/failed/`.
2. Check `runtime/last_result.json`.
3. Check the newest file under `logs/`.
4. Keep AEDT open unless the failure clearly corrupted the session.
5. Fix the script or template, then queue the command again.

## Current status of this workspace

This hosted model has already been validated with:

- `probe_session`
- `run_script` using `scripts/host_session_probe.py`

So the external queue -> in-AEDT execution -> result writeback chain is already working.
