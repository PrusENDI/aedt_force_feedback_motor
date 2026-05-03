# DXF Copper MVP Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the repository for Milestone 2, the DXF-compatible 3D copper MVP, without extending the legacy phase-belt Sector3D scaffold.

**Architecture:** Keep the AEDT host/runtime queue as the execution transport. Build the new V1 copper path as a separate pipeline that starts from 2D geometry and feeds AEDT sheet/thicken creation through an explicit 2D-to-3D handshake. Treat existing phase-belt Sector3D scripts as legacy diagnostics unless a future task explicitly extracts a reusable helper.

**Tech Stack:** Python 3.10/3.11, AEDT in-process host, PyAEDT/AEDT native APIs, Shapely for 2D geometry, ezdxf for later DXF export, unittest.

---

## Current Milestone

Active roadmap node: `Milestone 2: DXF-Compatible 3D Copper MVP`.

Target exit gate for this prep phase:

- The old phase-belt implementation has a git anchor.
- New work happens on the `agent/dxf-copper-mvp` branch.
- The new V1 work has a documented file boundary.
- Future implementation starts from tests and does not modify old `sector3d_scaffold.py` as the primary geometry engine.

## File Boundary

Files to preserve as shared infrastructure:

- `scripts/in_aedt_agent_host.py`: keep as the in-AEDT command runner.
- `scripts/agent_runtime.py`: keep command queue, runtime paths, host preparation, and result finalization.
- `scripts/aedt_native_common.py`: keep AEDT attach/project/report helpers, with small additions only when they are generic.
- `scripts/queue_command.py`: keep local command queue writer.
- `launchers/Queue-Command.ps1`: keep generic queued script launcher.

Legacy files not to extend for V1 copper geometry:

- `scripts/sector3d_scaffold.py`
- `scripts/sector3d_aedt.py`
- `scripts/assign_sector3d_excitation.py`
- `scripts/build_sector3d_geometry_ready.py`

New files for the V1 implementation phase:

- Create `scripts/dxf_copper_geometry.py`: pure 2D copper geometry and validation.
- Create `scripts/build_dxf_copper_mvp.py`: AEDT-side build command for sheet creation, thickening, and mesh defense.
- Create `scripts/apply_dxf_copper_dc_conduction.py`: AEDT-side DC Conduction setup and report export.
- Create `scripts/inspect_dxf_copper_mvp.py`: AEDT-side object and result inspection.
- Create `launchers/Queue-BuildDxfCopperMvp.ps1`: queue builder for the V1 copper MVP.
- Create `launchers/Queue-ApplyDxfCopperDcConduction.ps1`: queue DC Conduction setup.
- Create `tests/test_dxf_copper_geometry.py`: pure Python geometry contract tests.
- Create `tests/test_dxf_copper_mvp_contract.py`: report/status contract tests.

## Task 1: Git Anchors

**Files:**
- No file changes.

- [x] **Step 1: Create legacy tag for the phase-belt lineage**

Run:

```powershell
git tag legacy/phase-belt-sector3d 71aff99
```

Expected: command exits successfully and `git tag --list legacy/phase-belt-sector3d` prints `legacy/phase-belt-sector3d`.

- [x] **Step 2: Create and switch to the new V1 branch**

Run:

```powershell
git switch -c agent/dxf-copper-mvp
```

Expected: command exits successfully and `git branch --show-current` prints `agent/dxf-copper-mvp`.

## Task 2: Pure Geometry Contract Skeleton

**Files:**
- Create: `scripts/dxf_copper_geometry.py`
- Test: `tests/test_dxf_copper_geometry.py`

- [ ] **Step 1: Write failing tests for the V1 geometry contract**

Create `tests/test_dxf_copper_geometry.py` with tests that require:

- default V1 geometry has `phase == "A"` and `layer == "L01"`;
- copper thickness is `0.3`;
- geometry status contains `closed`, `valid`, `bounding_diameter_mm`, `terminal_count`, and `minimum_clearance_mm`;
- `aedt_handshake_mode` is either `polyline_points` or `import_dxf`;
- the result does not expose `phase_belt_envelope`.

Run:

```powershell
python -m unittest tests.test_dxf_copper_geometry -v
```

Expected now: FAIL because `dxf_copper_geometry.py` does not exist yet.

- [ ] **Step 2: Implement minimal pure Python contract functions**

Create `scripts/dxf_copper_geometry.py` with:

- `v1_default_spec()`
- `build_v1_phase_a_geometry(spec=None)`
- `validate_v1_geometry(geometry)`

The implementation may start with a simple closed rectangular copper path with two terminal pads. The first implementation does not need full wave winding; it must establish the data structure and validation fields.

- [ ] **Step 3: Verify pure geometry contract tests pass**

Run:

```powershell
python -m unittest tests.test_dxf_copper_geometry -v
```

Expected: PASS.

## Task 3: AEDT Build Command Boundary

**Files:**
- Create: `scripts/build_dxf_copper_mvp.py`
- Create: `launchers/Queue-BuildDxfCopperMvp.ps1`
- Test: `tests/test_dxf_copper_mvp_contract.py`

- [ ] **Step 1: Write failing tests for build report semantics**

Create `tests/test_dxf_copper_mvp_contract.py` with tests that assert the V1 build summary contains:

- `milestone == "Milestone 2: DXF-Compatible 3D Copper MVP"`;
- `legacy_phase_belt_used == False`;
- `dxf_compatible_copper_ready` exists;
- `geometry_ready == False` until AEDT confirms sheet/thicken/object inspection;
- `dc_conduction_ready == False` until DC setup succeeds;
- `mesh_defense_required == True`;
- `aedt_handshake_mode` is recorded.

Run:

```powershell
python -m unittest tests.test_dxf_copper_mvp_contract -v
```

Expected now: FAIL because `build_dxf_copper_mvp.py` does not exist yet.

- [ ] **Step 2: Implement report-only build skeleton**

Create `scripts/build_dxf_copper_mvp.py` with a `main()` that:

- imports `dxf_copper_geometry`;
- writes `artifacts/dxf_copper_mvp.json`;
- writes `reports/dxf_copper_mvp.md`;
- does not call old `sector3d_scaffold.py`;
- reports that AEDT construction is not yet complete.

- [ ] **Step 3: Add queue launcher**

Create `launchers/Queue-BuildDxfCopperMvp.ps1` that queues:

```json
{
  "action": "run_script",
  "payload": {
    "script_path": "scripts/build_dxf_copper_mvp.py"
  }
}
```

Use the existing queue launcher style in `launchers/Queue-BuildSector3DGeometryReady.ps1` as reference, but do not call that old script.

- [ ] **Step 4: Verify build contract tests pass**

Run:

```powershell
python -m unittest tests.test_dxf_copper_mvp_contract -v
```

Expected: PASS.

## Task 4: AEDT Sheet/Thicken Prep

**Files:**
- Modify: `scripts/build_dxf_copper_mvp.py`
- Optionally modify: `scripts/aedt_native_common.py`

- [ ] **Step 1: Add guarded AEDT host detection**

Modify `scripts/build_dxf_copper_mvp.py` so that:

- when run outside the AEDT host, it only writes the geometry/report artifact;
- when `__agent_host_mode` is present, it attempts AEDT sheet creation;
- all AEDT failures stop the build and write a blocking issue.

- [ ] **Step 2: Add explicit 2D-to-3D handshake field**

Record one of:

```text
polyline_points
import_dxf
```

For V1 prep, use `polyline_points` unless DXF export is implemented in the same task.

- [ ] **Step 3: Add mesh defense status as a blocking contract field**

The report must include:

```json
"mesh_defense": {
  "required": true,
  "assigned": false,
  "target_thickness_mm": 0.3
}
```

The report must describe this as a blocking contract field until mesh control is assigned.

## Task 5: DC Conduction Prep

**Files:**
- Create: `scripts/apply_dxf_copper_dc_conduction.py`
- Create: `launchers/Queue-ApplyDxfCopperDcConduction.ps1`

- [ ] **Step 1: Create DC Conduction setup script skeleton**

The script must:

- read `artifacts/dxf_copper_mvp.json`;
- refuse to run if `dxf_compatible_copper_ready` is not true;
- refuse to run if terminal faces are missing;
- write `artifacts/dxf_copper_dc_conduction.json`;
- write `reports/dxf_copper_dc_conduction.md`.

- [ ] **Step 2: Create DC queue launcher**

Create `launchers/Queue-ApplyDxfCopperDcConduction.ps1` that queues `scripts/apply_dxf_copper_dc_conduction.py`.

## Task 6: Verification Before AEDT GUI Build

**Files:**
- No new files beyond previous tasks.

- [ ] **Step 1: Run pure Python tests**

Run:

```powershell
python -m unittest tests.test_dxf_copper_geometry tests.test_dxf_copper_mvp_contract -v
```

Expected: PASS.

- [ ] **Step 2: Compile new scripts**

Run:

```powershell
python -m py_compile scripts\dxf_copper_geometry.py scripts\build_dxf_copper_mvp.py scripts\apply_dxf_copper_dc_conduction.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Commit the V1 prep implementation**

Run:

```powershell
git add docs\superpowers\plans\2026-05-03-dxf-copper-mvp-prep.md scripts\dxf_copper_geometry.py scripts\build_dxf_copper_mvp.py scripts\apply_dxf_copper_dc_conduction.py launchers\Queue-BuildDxfCopperMvp.ps1 launchers\Queue-ApplyDxfCopperDcConduction.ps1 tests\test_dxf_copper_geometry.py tests\test_dxf_copper_mvp_contract.py
git commit -m "Prepare DXF copper MVP pipeline"
```

Expected: commit contains only the new V1 pipeline files and the plan.

## Self-Review

- This plan keeps host/runtime infrastructure and avoids extending the old phase-belt geometry engine.
- The V1 implementation starts from pure geometry tests before AEDT calls.
- The first AEDT validation target is DC Conduction, not magnetostatic solve.
- The plan keeps later six-layer, transient, and manufacturing DXF work outside V1 prep.
