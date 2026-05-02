# 3D Engineering Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trusted SSDR Maxwell 3D engineering-validation path that can diagnose hand-built prototype risk and prepare a disciplined correlation path to the final `S1-R1-S2-R2-S3` four-air-gap machine.

**Architecture:** Keep AEDT-facing geometry, excitation, setup, and report scripts in their current modules. Add small pure-Python helpers for engineering case generation, tolerance parsing, and derived metric/feasibility calculations so they can be tested without AEDT. The SSDR model remains the Stage 1 truth anchor; final `4 Nm @ 3 Arms` is assessed only in the final-topology feasibility report, not as a direct SSDR pass/fail.

**Tech Stack:** Python 3.10, PyAEDT/AEDT native scripting, PowerShell launchers, JSON/CSV config, `unittest` for local pure-Python checks.

---

## File Structure

- Create: `scripts/sector3d_engineering_cases.py`
  - Owns generation of the first engineering validation case table from `config/project.json` and `config/search_space.json`.
  - Produces nominal, air-gap, runout, magnet-placement, hot-resistance, peak-demag, and expanded-air-region cases.
- Create: `scripts/sector3d_engineering_metrics.py`
  - Owns derived metrics that do not require AEDT report creation: hot copper loss, `Kt_Effective`, final-topology feasibility text, and problem-analysis flags.
- Create: `tests/test_sector3d_engineering_cases.py`
  - Tests case generation and the final-topology torque-target boundary.
- Create: `tests/test_sector3d_engineering_metrics.py`
  - Tests hot resistance, copper loss, `Kt_Effective`, and feasibility classification.
- Modify: `config/project.json`
  - Adds an explicit `sector_3d.engineering_validation` contract and derived report names.
- Modify: `cases/validation_3d.csv`
  - Replaces the single baseline row with the first engineering validation set.
- Modify: `scripts/sector3d_scaffold.py`
  - Applies tolerance metadata to generated SSDR geometry variables and build artifacts.
- Modify: `scripts/build_sector3d_model.py`
  - Surfaces engineering-validation metadata in geometry sanity output and markdown.
- Modify: `scripts/run_sector_3d_validate.py`
  - Preserves engineering case metadata, exports all contract reports that exist, applies derived metrics, writes engineering assessment outputs, and prevents SSDR results from being judged against final `4 Nm @ 3 Arms`.
- Modify: `scripts/create_sector3d_reports.py`
  - Keeps AEDT report creation focused on AEDT-native quantities and records derived report names as non-AEDT metrics.
- Modify: `launchers/Queue-GenerateSector3DEngineeringCases.ps1`
  - Runs the pure-Python case generator from PowerShell without requiring a live AEDT session.
- Modify: `README.md` and `reports/sector3d_physics_contract.md`
  - Documents the Stage 1 SSDR engineering-validation path and Stage 2 final-topology correlation gate.

---

### Task 1: Add Engineering Validation Config Contract

**Files:**
- Modify: `config/project.json`
- Modify: `config/search_space.json`
- Test: `tests/test_sector3d_engineering_cases.py`

- [ ] **Step 1: Write the failing config contract test**

Create `tests/test_sector3d_engineering_cases.py` with:

```python
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class Sector3DEngineeringConfigTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def test_engineering_validation_contract_is_explicit(self):
        project_cfg = self.load_project()
        ev = project_cfg["sector_3d"]["engineering_validation"]
        self.assertEqual(ev["stage1_topology"], "SSDR")
        self.assertEqual(ev["stage2_topology"], "S1-R1-S2-R2-S3")
        self.assertEqual(ev["stage2_target_torque_nm_at_3arms"], 4.0)
        self.assertFalse(ev["apply_stage2_torque_target_to_ssdr"])
        self.assertGreaterEqual(ev["manual_tolerance_envelope_mm"], 0.2)
        self.assertGreaterEqual(ev["recommended_nominal_airgap_mm_min"], 0.8)

    def test_derived_report_names_are_configured(self):
        project_cfg = self.load_project()
        reports = project_cfg["reports"]
        self.assertEqual(reports["copper_loss_hot"], "CopperLoss_Hot")
        self.assertEqual(reports["kt_effective"], "Kt_Effective")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: FAIL with `KeyError: 'engineering_validation'`.

- [ ] **Step 3: Add the config contract**

Modify `config/project.json` under `sector_3d`:

```json
"engineering_validation": {
  "stage1_topology": "SSDR",
  "stage1_active_gap_faces": 2,
  "stage2_topology": "S1-R1-S2-R2-S3",
  "stage2_active_gap_faces": 4,
  "stage2_target_torque_nm_at_3arms": 4.0,
  "apply_stage2_torque_target_to_ssdr": false,
  "manual_tolerance_envelope_mm": 0.2,
  "recommended_nominal_airgap_mm_min": 0.8,
  "recommended_nominal_airgap_mm_max": 1.0,
  "hot_copper_temperature_c": 100.0,
  "peak_demag_current_arms": 4.0,
  "expanded_air_region_padding_multiplier": 1.5,
  "required_case_ids": [
    "baseline_nominal",
    "airgap_plus_0p2mm",
    "airgap_imbalance_0p2mm",
    "rotor_runout_0p2mm",
    "magnet_angle_error",
    "magnet_radial_offset",
    "magnet_axial_height_error",
    "hot_resistance_case",
    "peak_current_demag_case",
    "expanded_air_region_check"
  ]
}
```

Modify `config/project.json` under `reports`:

```json
"copper_loss_hot": "CopperLoss_Hot",
"kt_effective": "Kt_Effective"
```

Modify `config/search_space.json` so the baseline air gap is engineering-realistic:

```json
{
  "name": "airgap_mm",
  "type": "float",
  "min": 0.7,
  "max": 1.2,
  "baseline": 0.9,
  "decimals": 3
}
```

- [ ] **Step 4: Verify the config contract test passes**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add config/project.json config/search_space.json tests/test_sector3d_engineering_cases.py
git commit -m "Add Sector3D engineering validation contract"
```

---

### Task 2: Generate The First Engineering Validation Case Set

**Files:**
- Create: `scripts/sector3d_engineering_cases.py`
- Modify: `cases/validation_3d.csv`
- Modify: `launchers/Queue-GenerateSector3DEngineeringCases.ps1`
- Test: `tests/test_sector3d_engineering_cases.py`

- [ ] **Step 1: Extend the failing case generation tests**

Append to `tests/test_sector3d_engineering_cases.py`:

```python
from sector3d_engineering_cases import build_engineering_cases


class Sector3DEngineeringCaseGenerationTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def load_search(self):
        with open(os.path.join(ROOT, "config", "search_space.json"), "r") as handle:
            return json.load(handle)

    def test_builds_required_engineering_cases(self):
        rows = build_engineering_cases(self.load_project(), self.load_search())
        case_ids = [row["case_id"] for row in rows]
        self.assertEqual(
            case_ids,
            [
                "baseline_nominal",
                "airgap_plus_0p2mm",
                "airgap_imbalance_0p2mm",
                "rotor_runout_0p2mm",
                "magnet_angle_error",
                "magnet_radial_offset",
                "magnet_axial_height_error",
                "hot_resistance_case",
                "peak_current_demag_case",
                "expanded_air_region_check",
            ],
        )
        baseline = rows[0]
        self.assertEqual(baseline["engineering_stage"], "ssdr_truth_anchor")
        self.assertEqual(float(baseline["phase_current_rms"]), 3.0)
        self.assertEqual(float(baseline["airgap_upper_delta_mm"]), 0.0)
        self.assertEqual(float(baseline["airgap_lower_delta_mm"]), 0.0)

    def test_airgap_imbalance_case_keeps_mean_gap_but_offsets_sides(self):
        rows = build_engineering_cases(self.load_project(), self.load_search())
        row = [item for item in rows if item["case_id"] == "airgap_imbalance_0p2mm"][0]
        self.assertEqual(float(row["airgap_upper_delta_mm"]), 0.2)
        self.assertEqual(float(row["airgap_lower_delta_mm"]), -0.2)
        self.assertEqual(float(row["airgap_mm"]), 0.9)

    def test_stage2_target_is_metadata_not_ssdr_constraint(self):
        rows = build_engineering_cases(self.load_project(), self.load_search())
        for row in rows:
            self.assertEqual(row["stage2_target_torque_nm_at_3arms"], 4.0)
            self.assertEqual(row["apply_stage2_torque_target_to_ssdr"], "false")
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sector3d_engineering_cases'`.

- [ ] **Step 3: Create the case generator**

Create `scripts/sector3d_engineering_cases.py`:

```python
from __future__ import print_function

import os

from aedt_native_common import config_paths
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import write_csv_rows


BASE_EXTRA_FIELDS = [
    "engineering_stage",
    "case_intent",
    "phase_current_rms",
    "speed_rpm",
    "current_angle_deg",
    "airgap_upper_delta_mm",
    "airgap_lower_delta_mm",
    "rotor_runout_mm",
    "magnet_angle_error_deg",
    "magnet_radial_offset_mm",
    "magnet_axial_offset_mm",
    "copper_temperature_c",
    "air_region_padding_multiplier",
    "stage2_target_torque_nm_at_3arms",
    "apply_stage2_torque_target_to_ssdr",
]


def _baseline_from_search(search_cfg):
    row = {}
    for spec in search_cfg["variables"]:
        row[spec["name"]] = spec["baseline"]
    return row


def _base_case(project_cfg, search_cfg):
    fixed = project_cfg["machine_fixed"]
    ev = project_cfg["sector_3d"]["engineering_validation"]
    row = _baseline_from_search(search_cfg)
    row.update(
        {
            "engineering_stage": "ssdr_truth_anchor",
            "phase_current_rms": fixed["continuous_phase_current_arms"],
            "speed_rpm": fixed["max_speed_rpm"],
            "current_angle_deg": project_cfg["sector_3d"]["winding"].get("current_angle_deg", 0.0),
            "airgap_upper_delta_mm": 0.0,
            "airgap_lower_delta_mm": 0.0,
            "rotor_runout_mm": 0.0,
            "magnet_angle_error_deg": 0.0,
            "magnet_radial_offset_mm": 0.0,
            "magnet_axial_offset_mm": 0.0,
            "copper_temperature_c": ev["hot_copper_temperature_c"],
            "air_region_padding_multiplier": 1.0,
            "stage2_target_torque_nm_at_3arms": ev["stage2_target_torque_nm_at_3arms"],
            "apply_stage2_torque_target_to_ssdr": "false",
        }
    )
    return row


def _with_case(base, case_id, intent, **updates):
    row = dict(base)
    row["case_id"] = case_id
    row["case_intent"] = intent
    row.update(updates)
    return row


def build_engineering_cases(project_cfg, search_cfg):
    ev = project_cfg["sector_3d"]["engineering_validation"]
    tol = float(ev["manual_tolerance_envelope_mm"])
    base = _base_case(project_cfg, search_cfg)
    base["airgap_mm"] = max(float(base["airgap_mm"]), float(ev["recommended_nominal_airgap_mm_min"]))
    return [
        _with_case(base, "baseline_nominal", "Nominal SSDR engineering truth-anchor case"),
        _with_case(base, "airgap_plus_0p2mm", "Global air gap enlarged by manual-build tolerance", airgap_mm=float(base["airgap_mm"]) + tol),
        _with_case(base, "airgap_imbalance_0p2mm", "Upper and lower gaps imbalanced while nominal mean gap is preserved", airgap_upper_delta_mm=tol, airgap_lower_delta_mm=-tol),
        _with_case(base, "rotor_runout_0p2mm", "Equivalent axial rotor runout tolerance", rotor_runout_mm=tol),
        _with_case(base, "magnet_angle_error", "Magnet placement angular error", magnet_angle_error_deg=2.0),
        _with_case(base, "magnet_radial_offset", "Magnet radial placement offset", magnet_radial_offset_mm=tol),
        _with_case(base, "magnet_axial_height_error", "Magnet height or glue-line axial placement error", magnet_axial_offset_mm=tol),
        _with_case(base, "hot_resistance_case", "Long continuous operation at hot copper resistance", copper_temperature_c=ev["hot_copper_temperature_c"]),
        _with_case(base, "peak_current_demag_case", "High-temperature peak-current demagnetization check", phase_current_rms=ev["peak_demag_current_arms"]),
        _with_case(base, "expanded_air_region_check", "Expanded air region boundary sensitivity check", air_region_padding_multiplier=ev["expanded_air_region_padding_multiplier"]),
    ]


def fieldnames(search_cfg):
    names = ["case_id"]
    for spec in search_cfg["variables"]:
        names.append(spec["name"])
    names.extend(BASE_EXTRA_FIELDS)
    return names


def main():
    root = repo_root()
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    paths = config_paths(root, project_cfg)
    rows = build_engineering_cases(project_cfg, search_cfg)
    write_csv_rows(paths["validation_cases_csv"], rows, fieldnames(search_cfg))
    print("Wrote %d Sector3D engineering validation cases to %s" % (len(rows), paths["validation_cases_csv"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create the launcher**

Create `launchers/Queue-GenerateSector3DEngineeringCases.ps1`:

```powershell
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe"
& $Python (Join-Path $Root "scripts\sector3d_engineering_cases.py")
```

- [ ] **Step 5: Generate the case CSV**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' scripts\sector3d_engineering_cases.py
```

Expected: `Wrote 10 Sector3D engineering validation cases to ...cases\validation_3d.csv`.

- [ ] **Step 6: Verify tests pass**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add scripts/sector3d_engineering_cases.py launchers/Queue-GenerateSector3DEngineeringCases.ps1 cases/validation_3d.csv tests/test_sector3d_engineering_cases.py
git commit -m "Generate Sector3D engineering validation cases"
```

---

### Task 3: Preserve Engineering Case Metadata Through Validation

**Files:**
- Modify: `scripts/run_sector_3d_validate.py`
- Test: `tests/test_sector3d_engineering_cases.py`

- [ ] **Step 1: Write the failing metadata preservation test**

Append to `tests/test_sector3d_engineering_cases.py`:

```python
from run_sector_3d_validate import _fieldnames
from run_sector_3d_validate import _validate_case_row


class Sector3DValidationMetadataTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def load_search(self):
        with open(os.path.join(ROOT, "config", "search_space.json"), "r") as handle:
            return json.load(handle)

    def test_validation_accepts_engineering_metadata_columns(self):
        project_cfg = self.load_project()
        search_cfg = self.load_search()
        raw = build_engineering_cases(project_cfg, search_cfg)[2]
        parsed, errors = _validate_case_row(raw, search_cfg, project_cfg, {})
        self.assertEqual(errors, [])
        self.assertEqual(parsed["case_id"], "airgap_imbalance_0p2mm")
        self.assertEqual(parsed["engineering_stage"], "ssdr_truth_anchor")
        self.assertEqual(float(parsed["airgap_upper_delta_mm"]), 0.2)
        self.assertEqual(float(parsed["airgap_lower_delta_mm"]), -0.2)

    def test_summary_fieldnames_include_engineering_metadata(self):
        names = _fieldnames()
        self.assertIn("engineering_stage", names)
        self.assertIn("case_intent", names)
        self.assertIn("airgap_upper_delta_mm", names)
        self.assertIn("stage2_target_torque_nm_at_3arms", names)
        self.assertIn("ssdr_direct_target_fail", names)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: FAIL because `_validate_case_row` drops unknown metadata and `_fieldnames()` lacks engineering fields.

- [ ] **Step 3: Extend summary and failure fieldnames**

In `scripts/run_sector_3d_validate.py`, add:

```python
ENGINEERING_CASE_FIELDS = [
    "engineering_stage",
    "case_intent",
    "phase_current_rms",
    "speed_rpm",
    "current_angle_deg",
    "airgap_upper_delta_mm",
    "airgap_lower_delta_mm",
    "rotor_runout_mm",
    "magnet_angle_error_deg",
    "magnet_radial_offset_mm",
    "magnet_axial_offset_mm",
    "copper_temperature_c",
    "air_region_padding_multiplier",
    "stage2_target_torque_nm_at_3arms",
    "apply_stage2_torque_target_to_ssdr",
    "ssdr_direct_target_fail",
    "final_topology_feasibility",
    "problem_analysis_flags",
]
```

Append these fields in `_fieldnames()` after `stage`:

```python
        "engineering_stage",
        "case_intent",
        "phase_current_rms",
        "speed_rpm",
        "current_angle_deg",
        "airgap_upper_delta_mm",
        "airgap_lower_delta_mm",
        "rotor_runout_mm",
        "magnet_angle_error_deg",
        "magnet_radial_offset_mm",
        "magnet_axial_offset_mm",
        "copper_temperature_c",
        "air_region_padding_multiplier",
        "stage2_target_torque_nm_at_3arms",
        "apply_stage2_torque_target_to_ssdr",
        "ssdr_direct_target_fail",
        "final_topology_feasibility",
        "problem_analysis_flags",
```

Append the non-derived engineering fields in `_failure_fieldnames()` after `failed_at`.

- [ ] **Step 4: Preserve metadata during validation**

In `_validate_case_row`, after parsing search variables and before returning, add:

```python
    for name in ENGINEERING_CASE_FIELDS:
        if name in raw_case and name not in ["ssdr_direct_target_fail", "final_topology_feasibility", "problem_analysis_flags"]:
            parsed[name] = raw_case.get(name, "")
```

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add scripts/run_sector_3d_validate.py tests/test_sector3d_engineering_cases.py
git commit -m "Preserve Sector3D engineering case metadata"
```

---

### Task 4: Apply SSDR Tolerance Metadata To Geometry Variables

**Files:**
- Modify: `scripts/sector3d_scaffold.py`
- Modify: `scripts/build_sector3d_model.py`
- Test: `tests/test_sector3d_engineering_cases.py`

- [ ] **Step 1: Write the failing tolerance-variable test**

Append to `tests/test_sector3d_engineering_cases.py`:

```python
from sector3d_scaffold import scaffold_variables
from sector3d_scaffold import tolerance_metadata


class Sector3DToleranceGeometryTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def load_search(self):
        with open(os.path.join(ROOT, "config", "search_space.json"), "r") as handle:
            return json.load(handle)

    def test_scaffold_defines_tolerance_variables(self):
        variables = scaffold_variables(self.load_project())
        self.assertIn("airgap_upper_delta_mm", variables)
        self.assertIn("airgap_lower_delta_mm", variables)
        self.assertIn("rotor_runout_mm", variables)
        self.assertIn("magnet_angle_error_deg", variables)
        self.assertIn("magnet_radial_offset_mm", variables)
        self.assertIn("magnet_axial_offset_mm", variables)

    def test_tolerance_metadata_reads_engineering_case(self):
        project_cfg = self.load_project()
        search_cfg = self.load_search()
        row = [item for item in build_engineering_cases(project_cfg, search_cfg) if item["case_id"] == "rotor_runout_0p2mm"][0]
        meta = tolerance_metadata(row)
        self.assertEqual(meta["rotor_runout_mm"], 0.2)
        self.assertEqual(meta["airgap_upper_delta_mm"], 0.0)
        self.assertEqual(meta["airgap_lower_delta_mm"], 0.0)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
```

Expected: FAIL with `ImportError` or missing tolerance variable assertions.

- [ ] **Step 3: Add tolerance parsing to `sector3d_scaffold.py`**

Add near `_case_int`:

```python
def tolerance_metadata(case_row):
    return {
        "airgap_upper_delta_mm": _case_float(case_row, "airgap_upper_delta_mm", 0.0),
        "airgap_lower_delta_mm": _case_float(case_row, "airgap_lower_delta_mm", 0.0),
        "rotor_runout_mm": _case_float(case_row, "rotor_runout_mm", 0.0),
        "magnet_angle_error_deg": _case_float(case_row, "magnet_angle_error_deg", 0.0),
        "magnet_radial_offset_mm": _case_float(case_row, "magnet_radial_offset_mm", 0.0),
        "magnet_axial_offset_mm": _case_float(case_row, "magnet_axial_offset_mm", 0.0),
        "air_region_padding_multiplier": _case_float(case_row, "air_region_padding_multiplier", 1.0),
    }
```

Add these default design variables in `scaffold_variables()`:

```python
        "airgap_upper_delta_mm": "0mm",
        "airgap_lower_delta_mm": "0mm",
        "rotor_runout_mm": "0mm",
        "magnet_angle_error_deg": "0deg",
        "magnet_radial_offset_mm": "0mm",
        "magnet_axial_offset_mm": "0mm",
        "air_region_padding_multiplier": "1",
        "airgap_lower_effective_mm": "airgap_mm + airgap_lower_delta_mm",
        "airgap_upper_effective_mm": "airgap_mm + airgap_upper_delta_mm",
```

- [ ] **Step 4: Apply per-case tolerance variables before geometry creation**

In `build_sector_3d_scaffold()`, after `scaffold_vars = scaffold_variables(project_cfg)`, add:

```python
    tol_meta = tolerance_metadata(case_row)
    scaffold_vars.update(
        {
            "airgap_upper_delta_mm": "%.6gmm" % tol_meta["airgap_upper_delta_mm"],
            "airgap_lower_delta_mm": "%.6gmm" % tol_meta["airgap_lower_delta_mm"],
            "rotor_runout_mm": "%.6gmm" % tol_meta["rotor_runout_mm"],
            "magnet_angle_error_deg": "%.6gdeg" % tol_meta["magnet_angle_error_deg"],
            "magnet_radial_offset_mm": "%.6gmm" % tol_meta["magnet_radial_offset_mm"],
            "magnet_axial_offset_mm": "%.6gmm" % tol_meta["magnet_axial_offset_mm"],
            "air_region_padding_multiplier": "%.6g" % tol_meta["air_region_padding_multiplier"],
        }
    )
```

Change the relevant z expressions in `scaffold_variables()`:

```python
        "auto3d_z_lower_flat_copper_mm": "backiron_thickness_mm + magnet_thickness_mm + airgap_lower_effective_mm",
        "auto3d_z_top_magnet_mm": "auto3d_z_upper_airgap_mm + airgap_upper_effective_mm + rotor_runout_mm",
        "auto3d_region_padding_mm": "(%.6gmm + %.6g*airgap_mm)*air_region_padding_multiplier" % (padding_mm, padding_airgap_multiplier),
```

Change magnet definitions in `_magnet_pole_objects_definition()` so angle/radial/axial offsets affect the generated magnets. Add this line after `magnet_arc_deg = pole_pitch_deg * pole_arc_ratio`:

```python
    tol_meta = tolerance_metadata(case_row)
```

Then change both bottom and top magnet dictionaries:

```python
                "outer_radius": "outer_radius_mm + magnet_radial_offset_mm",
                "inner_radius": "inner_radius_mm + magnet_radial_offset_mm",
                "start_angle_deg": start_angle_deg + tol_meta["magnet_angle_error_deg"],
```

For the bottom magnet dictionary, use:

```python
                "z_start": "auto3d_z_bottom_magnet_mm + magnet_axial_offset_mm",
```

For the top magnet dictionary, use:

```python
                "z_start": "auto3d_z_top_magnet_mm + magnet_axial_offset_mm",
```

- [ ] **Step 5: Include tolerance metadata in the build artifact**

In the returned dictionary from `build_sector_3d_scaffold()`, add:

```python
        "tolerance_metadata": tol_meta,
```

In `scripts/build_sector3d_model.py`, add `tolerance_metadata` to the markdown under a new `## Engineering Tolerance Metadata` section:

```python
    lines.append("## Engineering Tolerance Metadata")
    lines.append("")
    for key, value in summary.get("tolerance_metadata", {}).items():
        lines.append("- %s: `%s`" % (key, value))
    lines.append("")
```

- [ ] **Step 6: Verify tests and compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_cases -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\sector3d_scaffold.py scripts\build_sector3d_model.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 7: Commit**

```powershell
git add scripts/sector3d_scaffold.py scripts/build_sector3d_model.py tests/test_sector3d_engineering_cases.py
git commit -m "Apply Sector3D engineering tolerances to scaffold"
```

---

### Task 5: Add Derived Engineering Metrics And Final-Topology Feasibility

**Files:**
- Create: `scripts/sector3d_engineering_metrics.py`
- Modify: `scripts/run_sector_3d_validate.py`
- Test: `tests/test_sector3d_engineering_metrics.py`

- [ ] **Step 1: Write the failing metric tests**

Create `tests/test_sector3d_engineering_metrics.py`:

```python
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from sector3d_engineering_metrics import add_engineering_metrics
from sector3d_engineering_metrics import final_topology_feasibility
from sector3d_engineering_metrics import problem_analysis_flags


class Sector3DEngineeringMetricsTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def test_adds_hot_loss_and_kt_without_ssdr_target_fail(self):
        project_cfg = self.load_project()
        row = {
            "case_id": "baseline_nominal",
            "torque_avg_nm": 1.7,
            "torque_loaded_p2p": 0.2,
            "phase_current_rms": 3.0,
            "phase_resistance_ohm_20c": 0.55,
            "copper_temperature_c": 100.0,
            "stage2_target_torque_nm_at_3arms": 4.0,
            "apply_stage2_torque_target_to_ssdr": "false",
        }
        out = add_engineering_metrics(project_cfg, row)
        self.assertAlmostEqual(out["kt_effective_nm_per_arms"], 1.7 / 3.0)
        self.assertGreater(out["phase_resistance_ohm_hot"], out["phase_resistance_ohm_20c"])
        self.assertGreater(out["hot_copper_loss_w"], 0.0)
        self.assertEqual(out["ssdr_direct_target_fail"], "false")

    def test_final_topology_feasibility_is_not_blind_times_two(self):
        project_cfg = self.load_project()
        row = {
            "torque_avg_nm": 1.8,
            "hot_copper_loss_w": 28.0,
            "torque_ripple_pct": 7.0,
            "cogging_peak_nm": 0.03,
            "back_emf_margin_v": 4.0,
            "stage2_target_torque_nm_at_3arms": 4.0,
        }
        text = final_topology_feasibility(project_cfg, row)
        self.assertIn("SSDR", text)
        self.assertIn("four-air-gap", text)
        self.assertIn("not a direct pass/fail", text)

    def test_problem_flags_are_ordered_by_diagnostic_path(self):
        row = {
            "torque_avg_nm": 0.1,
            "torque_ripple_pct": 80.0,
            "hot_copper_loss_w": 90.0,
            "back_emf_margin_v": -2.0,
            "bmax_backiron_t": 1.9,
            "magnet_demag_margin": -0.1,
        }
        flags = problem_analysis_flags(row)
        self.assertEqual(flags[0], "geometry_or_excitation_suspect")
        self.assertIn("thermal_copper_loss_high", flags)
        self.assertIn("magnet_demag_margin_low", flags)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_metrics -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the metrics module**

Create `scripts/sector3d_engineering_metrics.py`:

```python
from __future__ import print_function


def _float(row, key, default_value=0.0):
    try:
        return float(row.get(key, default_value))
    except Exception:
        return default_value


def _bool_text(value):
    return str(value).strip().lower() in ["1", "true", "yes"]


def hot_resistance(phase_resistance_20c, copper_temperature_c, tempco):
    return phase_resistance_20c * (1.0 + tempco * (copper_temperature_c - 20.0))


def problem_analysis_flags(row):
    flags = []
    if abs(_float(row, "torque_avg_nm")) < 0.2 or _float(row, "torque_ripple_pct") > 50.0:
        flags.append("geometry_or_excitation_suspect")
    if _float(row, "hot_copper_loss_w") > 35.0:
        flags.append("thermal_copper_loss_high")
    if _float(row, "magnet_demag_margin", 1.0) <= 0.0:
        flags.append("magnet_demag_margin_low")
    if _float(row, "bmax_backiron_t") > 1.6:
        flags.append("backiron_saturation_risk")
    if _float(row, "back_emf_margin_v") < 2.0:
        flags.append("back_emf_bus_margin_low")
    if not flags:
        flags.append("no_primary_flags")
    return flags


def final_topology_feasibility(project_cfg, row):
    ev = project_cfg["sector_3d"]["engineering_validation"]
    target = _float(row, "stage2_target_torque_nm_at_3arms", ev["stage2_target_torque_nm_at_3arms"])
    ssdr_torque = _float(row, "torque_avg_nm")
    flags = problem_analysis_flags(row)
    return (
        "SSDR torque %.6g Nm is a Stage 1 truth-anchor result and is not a direct pass/fail "
        "against the final four-air-gap target %.6g Nm @ 3 Arms. Correlate leakage, copper length, "
        "thermal path, tolerance accumulation, and phase balance in the final %s topology. "
        "Diagnostic flags: %s"
        % (ssdr_torque, target, ev["stage2_topology"], ", ".join(flags))
    )


def add_engineering_metrics(project_cfg, row):
    out = dict(row)
    fixed = project_cfg["machine_fixed"]
    proxy = project_cfg["proxy_models"]
    ev = project_cfg["sector_3d"]["engineering_validation"]
    current = _float(out, "phase_current_rms", fixed["continuous_phase_current_arms"])
    if current <= 0.0:
        current = fixed["continuous_phase_current_arms"]
    out["phase_current_rms"] = current
    torque = _float(out, "torque_avg_nm", _float(out, "torque_loaded_avg", 0.0))
    out["kt_effective_nm_per_arms"] = torque / max(current, 1.0e-9)
    phase_r_20c = _float(out, "phase_resistance_ohm_20c")
    copper_temp = _float(out, "copper_temperature_c", ev["hot_copper_temperature_c"])
    phase_r_hot = hot_resistance(phase_r_20c, copper_temp, proxy["copper_tempco_per_c"])
    out["phase_resistance_ohm_hot"] = phase_r_hot
    out["hot_copper_loss_w"] = 3.0 * (current ** 2) * phase_r_hot
    out["copper_loss_hot_w"] = out["hot_copper_loss_w"]
    out["ssdr_direct_target_fail"] = "true" if _bool_text(out.get("apply_stage2_torque_target_to_ssdr", "false")) and torque < ev["stage2_target_torque_nm_at_3arms"] else "false"
    out["problem_analysis_flags"] = " | ".join(problem_analysis_flags(out))
    out["final_topology_feasibility"] = final_topology_feasibility(project_cfg, out)
    return out
```

- [ ] **Step 4: Integrate metrics into validation runner**

In `scripts/run_sector_3d_validate.py`, add:

```python
from sector3d_engineering_metrics import add_engineering_metrics
```

After `summary = dict(case_row)` and after AEDT metrics have been merged, add:

```python
            summary = add_engineering_metrics(project_cfg, summary)
```

Ensure `_fieldnames()` includes:

```python
        "kt_effective_nm_per_arms",
        "copper_loss_hot_w",
```

- [ ] **Step 5: Verify tests and compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_metrics -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\sector3d_engineering_metrics.py scripts\run_sector_3d_validate.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 6: Commit**

```powershell
git add scripts/sector3d_engineering_metrics.py scripts/run_sector_3d_validate.py tests/test_sector3d_engineering_metrics.py
git commit -m "Add Sector3D engineering derived metrics"
```

---

### Task 6: Export All Contract Reports And Handle Derived Report Names

**Files:**
- Modify: `scripts/run_sector_3d_validate.py`
- Modify: `scripts/create_sector3d_reports.py`
- Test: `tests/test_sector3d_engineering_metrics.py`

- [ ] **Step 1: Write the failing report mapping test**

Append to `tests/test_sector3d_engineering_metrics.py`:

```python
from run_sector_3d_validate import _case_report_mapping
from create_sector3d_reports import DERIVED_REPORT_KEYS


class Sector3DReportContractTests(unittest.TestCase):
    def test_validation_exports_all_aedt_contract_reports(self):
        mapping = _case_report_mapping()
        self.assertIn("torque_loaded", mapping)
        self.assertIn("torque_cogging", mapping)
        self.assertIn("flux_linkage_a", mapping)
        self.assertIn("back_emf_ll", mapping)
        self.assertIn("bmax_backiron", mapping)
        self.assertIn("inductance_phase_a", mapping)
        self.assertIn("magnet_demag_margin", mapping)

    def test_derived_reports_are_not_created_as_aedt_reports(self):
        self.assertEqual(DERIVED_REPORT_KEYS, ["copper_loss_hot", "kt_effective"])
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_metrics -v
```

Expected: FAIL because `_case_report_mapping` and `DERIVED_REPORT_KEYS` do not exist.

- [ ] **Step 3: Add explicit report mapping**

In `scripts/run_sector_3d_validate.py`, add:

```python
def _case_report_mapping():
    return {
        "torque_loaded": "torque_loaded.csv",
        "torque_cogging": "torque_cogging.csv",
        "flux_linkage_a": "flux_linkage_a.csv",
        "back_emf_ll": "back_emf_ll.csv",
        "bmax_backiron": "bmax_backiron.csv",
        "inductance_phase_a": "inductance_phase_a.csv",
        "magnet_demag_margin": "magnet_demag_margin.csv",
    }
```

Change `_export_case_reports()` to use it:

```python
    mapping = _case_report_mapping()
```

Update `_metrics_from_exports()` so optional reports add metrics when present:

```python
    if "flux_linkage_a" in export_paths:
        stats = waveform_stats(export_paths["flux_linkage_a"])
        row["flux_linkage_a_avg_wb"] = stats.get("avg", 0.0)
    if "inductance_phase_a" in export_paths:
        stats = waveform_stats(export_paths["inductance_phase_a"])
        row["inductance_phase_a_h"] = stats.get("avg", 0.0)
    if "magnet_demag_margin" in export_paths:
        stats = waveform_stats(export_paths["magnet_demag_margin"])
        row["magnet_demag_margin"] = stats.get("min", 0.0)
```

- [ ] **Step 4: Mark derived report keys in report creation**

In `scripts/create_sector3d_reports.py`, add near constants:

```python
DERIVED_REPORT_KEYS = ["copper_loss_hot", "kt_effective"]
```

In the loop over report keys, skip derived report keys with a manual action:

```python
        if report_key in DERIVED_REPORT_KEYS:
            manual_actions.append("%s (%s) is derived after CSV export and is not created as an AEDT-native report." % (report_key, report_name))
            continue
```

- [ ] **Step 5: Verify tests and compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_metrics -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\run_sector_3d_validate.py scripts\create_sector3d_reports.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 6: Commit**

```powershell
git add scripts/run_sector_3d_validate.py scripts/create_sector3d_reports.py tests/test_sector3d_engineering_metrics.py
git commit -m "Export Sector3D engineering report contract"
```

---

### Task 7: Write Engineering Assessment Artifacts

**Files:**
- Modify: `scripts/run_sector_3d_validate.py`
- Test: `tests/test_sector3d_engineering_metrics.py`

- [ ] **Step 1: Write the failing assessment writer test**

Append to `tests/test_sector3d_engineering_metrics.py`:

```python
from run_sector_3d_validate import _engineering_assessment_markdown


class Sector3DEngineeringAssessmentTests(unittest.TestCase):
    def test_assessment_states_ssdr_boundary_and_problem_path(self):
        text = _engineering_assessment_markdown(
            [
                {
                    "case_id": "baseline_nominal",
                    "torque_avg_nm": 1.8,
                    "hot_copper_loss_w": 28.0,
                    "problem_analysis_flags": "no_primary_flags",
                    "final_topology_feasibility": "SSDR result is not a direct pass/fail against the final four-air-gap target.",
                }
            ]
        )
        self.assertIn("SSDR Engineering Assessment", text)
        self.assertIn("not a direct pass/fail", text)
        self.assertIn("Problem Analysis Path", text)
        self.assertIn("geometry and motion", text)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_metrics -v
```

Expected: FAIL because `_engineering_assessment_markdown` does not exist.

- [ ] **Step 3: Add assessment paths and writer**

In `_artifact_paths(root)` add:

```python
        "engineering_assessment_md": os.path.join(root, "reports", "sector3d_engineering_assessment.md"),
```

Add:

```python
def _engineering_assessment_markdown(rows):
    lines = []
    lines.append("# Sector3D SSDR Engineering Assessment")
    lines.append("")
    lines.append("This report summarizes Stage 1 SSDR evidence. It is not a direct pass/fail against the final four-air-gap `4 Nm @ 3 Arms` target.")
    lines.append("")
    lines.append("## Case Summary")
    lines.append("")
    for row in rows:
        lines.append("- `%s`: torque_avg_nm=`%s`, hot_copper_loss_w=`%s`, flags=`%s`" % (
            row.get("case_id", ""),
            row.get("torque_avg_nm", ""),
            row.get("hot_copper_loss_w", ""),
            row.get("problem_analysis_flags", ""),
        ))
    lines.append("")
    lines.append("## Final Topology Feasibility")
    lines.append("")
    for row in rows:
        if row.get("final_topology_feasibility"):
            lines.append("- `%s`: %s" % (row.get("case_id", ""), row.get("final_topology_feasibility", "")))
    lines.append("")
    lines.append("## Problem Analysis Path")
    lines.append("")
    lines.append("1. Check geometry and motion: air gap, rotating band, sector cuts, and air-region size.")
    lines.append("2. Check excitation: phase order, winding polarity, current angle, and current amplitude.")
    lines.append("3. Check copper and heat: resistance, end connections, parallel paths, and hot copper loss.")
    lines.append("4. Check magnets: high-temperature coercivity and demagnetization margin.")
    lines.append("5. Check magnetic circuit: back-iron saturation, leakage, fringing, and boundary sensitivity.")
    lines.append("6. Check manufacturing tolerance: air-gap imbalance, runout, magnet placement, and winding position.")
    lines.append("7. Check SSDR-to-final-topology correlation before drawing hardware conclusions.")
    return "\n".join(lines) + "\n"
```

After `_write_recommendation(paths["recommendation_md"], ranked_rows)` at the end of `main()`, write:

```python
    assessment_text = _engineering_assessment_markdown(ranked_rows)
    handle = open(artifact_paths["engineering_assessment_md"], "w")
    try:
        handle.write(assessment_text)
    finally:
        handle.close()
```

- [ ] **Step 4: Verify tests and compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_engineering_metrics -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\run_sector_3d_validate.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 5: Commit**

```powershell
git add scripts/run_sector_3d_validate.py tests/test_sector3d_engineering_metrics.py
git commit -m "Write Sector3D engineering assessment report"
```

---

### Task 8: Document And Smoke-Test The Engineering Validation Workflow

**Files:**
- Modify: `README.md`
- Modify: `reports/sector3d_physics_contract.md`
- Test: local compile and unit test suite

- [ ] **Step 1: Update README workflow**

In `README.md`, add a short section after the Sector3D launcher list:

```markdown
## Sector3D Engineering Validation Path

Before restarting DOE ranking, use the SSDR engineering-validation path:

1. Generate the first engineering case set with `launchers\Queue-GenerateSector3DEngineeringCases.ps1`.
2. Build or refresh the SSDR Sector3D model.
3. Assign three-phase winding excitation.
4. Apply transient motion setup.
5. Create AEDT-native reports.
6. Solve the nominal and tolerance cases.
7. Review `reports/sector3d_engineering_assessment.md`.

The SSDR model is a truth anchor, not the final machine signoff. The final `4 Nm @ 3 Arms` target belongs to the `S1-R1-S2-R2-S3` four-air-gap topology or to an explicitly correlated final-topology model.
```

- [ ] **Step 2: Update the physics contract**

In `reports/sector3d_physics_contract.md`, add under `## Physical Contract`:

```markdown
### Manual-Build Engineering Validation

The first engineering-validation stage assumes manual assembly with roughly `+-0.20 mm` or worse tolerance. The SSDR model must include tolerance cases for global air-gap increase, upper/lower air-gap imbalance, rotor runout, magnet angular placement error, magnet radial offset, magnet axial height error, hot copper resistance, peak-current demagnetization, and expanded air-region sensitivity.

The SSDR stage must not be judged directly against the final `4 Nm @ 3 Arms` target. That target belongs to the final `S1-R1-S2-R2-S3` four-air-gap topology. SSDR evidence must instead state whether the final topology appears feasible after accounting for leakage, fringing, copper length, thermal path, air-gap tolerance accumulation, and phase-balance risk.
```

- [ ] **Step 3: Run local verification**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest discover -s tests -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\sector3d_engineering_cases.py scripts\sector3d_engineering_metrics.py scripts\sector3d_scaffold.py scripts\build_sector3d_model.py scripts\run_sector_3d_validate.py scripts\create_sector3d_reports.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 4: Generate cases and inspect the CSV**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' scripts\sector3d_engineering_cases.py
Get-Content cases\validation_3d.csv
```

Expected: 10 rows with `baseline_nominal`, `airgap_plus_0p2mm`, `airgap_imbalance_0p2mm`, `rotor_runout_0p2mm`, `magnet_angle_error`, `magnet_radial_offset`, `magnet_axial_height_error`, `hot_resistance_case`, `peak_current_demag_case`, and `expanded_air_region_check`.

- [ ] **Step 5: Commit**

```powershell
git add README.md reports/sector3d_physics_contract.md cases/validation_3d.csv
git commit -m "Document Sector3D engineering validation workflow"
```

---

## Live AEDT Validation Checkpoint

After Tasks 1-8 pass locally, run the AEDT host workflow in this order:

```powershell
launchers\Run-Launcher.cmd Start-AEDTHost.ps1
launchers\Run-Launcher.cmd Queue-GenerateSector3DEngineeringCases.ps1
launchers\Run-Launcher.cmd Queue-BuildSector3DModel.ps1
launchers\Run-Launcher.cmd Queue-AssignSector3DExcitation.ps1
launchers\Run-Launcher.cmd Queue-ApplySector3DTransientSetup.ps1
launchers\Run-Launcher.cmd Queue-CreateSector3DReports.ps1
launchers\Run-Launcher.cmd Queue-SolveSector3DSetup.ps1
launchers\Run-Launcher.cmd Get-AgentStatus.ps1
```

Expected live result:

- `artifacts/sector3d_model_build.json` includes `tolerance_metadata`.
- `reports/sector3d_model_build.md` includes engineering tolerance metadata.
- `reports/sector3d_excitation_assignment.md` shows whether the winding API blocker is resolved or still blocks solve readiness.
- `reports/sector3d_reports_creation.md` records AEDT-native reports and skips derived metrics as expected.
- `reports/sector3d_solve_status.md` exports available report CSVs.
- `reports/sector3d_engineering_assessment.md` states SSDR evidence and final-topology feasibility without direct SSDR pass/fail against `4 Nm @ 3 Arms`.

If `Queue-AssignSector3DExcitation.ps1` still fails at `AddWindingTerminals`, stop the live run there and treat excitation compatibility as the next focused implementation plan.

---

## Self-Review Notes

- Spec coverage: The plan covers the SSDR truth anchor, final-topology torque boundary, manual tolerance cases, hot copper loss, demagnetization check, report outputs, and the ordered problem-analysis path.
- Scope: This plan prepares the engineering-validation path. It does not solve the existing Maxwell `AddWindingTerminals` blocker directly; the live checkpoint turns that into the next focused plan if it remains.
- Type consistency: Engineering case fields are defined once in the generator and mirrored in validation fieldnames. Derived metric keys use `kt_effective_nm_per_arms`, `hot_copper_loss_w`, and `copper_loss_hot_w` consistently.
