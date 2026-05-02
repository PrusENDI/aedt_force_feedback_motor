# Sector3D Geometry-Valid Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a host-only Sector3D Geometry-valid generator for a `<=100 mm` SSDR axial-flux model with arc magnets and an `A-B-C-C-B-A` six-layer laminated copper phase-belt envelope, while making first-prototype manufacturing and thermal risks visible without overclaiming solve readiness.

**Architecture:** Add a new `scripts/build_sector3d_geometry_ready.py` entry point instead of extending the older mixed-purpose `build_sector3d_model.py`. Reuse low-level helpers from `sector3d_scaffold.py` where they are still correct, but move the new manufacturing contract, coil stack checks, geometry gates, and artifact writing into focused pure-Python helpers that can be tested without AEDT. The script runs only inside the in-AEDT host against an already-open correct `sector3d_working` / `Sector3D` design.

**Tech Stack:** Python 3.10, AEDT native scripting through the in-AEDT host, JSON/CSV configuration, PowerShell queue launchers, `unittest` for pure-Python gates.

---

## Scope Reset

This plan supersedes the earlier case-generation-first flow. The next implementation must first make the Sector3D engineering geometry trustworthy. Case generation, report creation, excitation assignment, and solve automation come after the Geometry-valid generator is stable.

The first version must not try to solve every real engineering problem. It must instead separate requirements into three buckets:

- **Hard Gate:** Must pass before the geometry can be called `geometry_ready`.
- **Risk Gate:** Must be reported clearly, but does not block first geometry generation.
- **Future Validation:** Must not be silently assumed solved.

## Gap Check From Brainstorming

The current plan had these gaps:

- It still assumed a `rigid_pcb_flat_copper_hybrid` route, but the selected first prototype is now laminated thin copper sheet, no PCB carrier.
- It treated `build_sector3d_model.py` as mostly usable, but the user needs a stricter host-only engineering generator.
- It did not encode the `A-B-C-C-B-A` six-layer mirror stack.
- It did not budget Z-axis expansion from insulation paint, PI film, glue, and press-cure residual thickness.
- It did not make single-side mechanical clearance a hard gate.
- It did not flag the C-layer thermal core as the likely stall-current bottleneck.
- It did not mark busbar/contact resistance and parallel current imbalance as risk gates.
- It did not prevent the bad strategy of running 10/20/40 kHz PWM directly in Maxwell 3D Transient.
- It did not require a future frequency-domain AC-loss path for PWM ripple loss.

## First-Version Modeling Contract

### Fabrication Route

- `fabrication.selected_route = laminated_copper_wave_winding`
- No PCB carrier in the active stator.
- Effective zone support is fiberglass/G10/FR4-style nonconductive skeleton, not loose independent strips.
- Low-field inner and outer CNC aluminum pieces provide positioning and heat spreading, but their detailed CAD is a future validation item.

### Magnet Geometry

- First mode: `magnet_geometry_mode = arc_segment`
- Magnets are sector/arc magnets fitted to the annulus.
- The geometry must support pole arc ratio, thickness, segment count, axial magnet direction, and placement error metadata.

### Coil Geometry

- First mode: `coil_geometry_mode = phase_stacked_mirror_parallel`
- Maxwell geometry uses active conductor envelope only: `active_conductor_geometry_mode = phase_belt_envelope`
- Axial layer sequence: `A-B-C-C-B-A`
- Each layer contains both polarities of its own phase, for example an A layer includes `A+` and `A-` active belts.
- Same-phase layers are parallel:
  - L1-A // L6-A
  - L2-B // L5-B
  - L3-C // L4-C
- End busbar and return geometry are not modeled in Maxwell v1:
  - `end_connection_geometry_mode = estimated_not_modeled`
  - `terminal_busbar_geometry_present = false`
  - `busbar_loss_estimated = true`

### Hard Gates

- Script is running inside the in-AEDT host.
- Active project and design match the expected working project and `Sector3D` design.
- The script does not create a project, create a design, or fall back to external COM/gRPC attach.
- Only `Auto3D_*` objects are deleted during rebuild.
- Required `Auto3D_*` objects exist after rebuild.
- Motor outer diameter and any generated circular part diameter are `<= 100 mm`.
- Copper layer stack includes copper, insulation/film, adhesive, and compressed residual glue thickness.
- Single-side mechanical clearance after stack expansion and axial runout allowance is `>= 0.8 mm`.
- Magnet, copper, back iron, support, region, periodic helper sheets, and motion-band geometry exist.
- Functional solid materials are assigned explicitly: magnets use a permanent-magnet material, copper belts use copper, back iron uses steel, and support uses a nonconductive structural material. Air region, motion-band helper solids, and periodic helper sheets may use air/vacuum-class materials only when they are explicitly listed as helper geometry.

### Risk Gates

- C-layer core thermal bottleneck is reported.
- A/B/C average Z position and layer-distance imbalance are reported.
- Parallel bridge/contact resistance and current-sharing risk are reported.
- Aluminum support eddy-current risk is reported as future validation if aluminum forms closed or near-closed conductive paths.
- PWM ripple AC loss is reported as a frequency-domain future validation path, not as a 3D Transient PWM solve.

### Future Validation

- Detailed wave-winding copper path.
- CNC fiberglass skeleton CAD with slots/ribs.
- U-shaped 3D copper busbar/bridge geometry.
- Complete radial thermal-resistance network for A/B/C layers.
- Twin Builder/Simplorer or equivalent PWM circuit extraction.
- Maxwell Eddy Current frequency-domain AC copper loss at PWM harmonic currents.
- Final `S1-R1-S2-R2-S3` four-gap topology correlation.

---

## File Structure

- Create: `scripts/sector3d_geometry_contract.py`
  - Pure-Python configuration normalization and validation for the new fabrication route, magnet mode, coil mode, stack-up, and hard/risk/future gates.
- Create: `scripts/sector3d_thermal_risk.py`
  - Pure-Python DC/hot resistance, contact margin, skin-depth, PWM-risk classification, and C-layer bottleneck flags.
- Create: `scripts/build_sector3d_geometry_ready.py`
  - Host-only AEDT entry point. Performs session gate, cleans `Auto3D_*`, builds geometry, runs gates, writes artifacts, and saves the working project.
- Create: `launchers/Queue-BuildSector3DGeometryReady.ps1`
  - Queues `scripts/build_sector3d_geometry_ready.py`.
- Create: `tests/test_sector3d_geometry_contract.py`
  - Tests the pure-Python geometry contract and hard/risk gate math.
- Create: `tests/test_sector3d_thermal_risk.py`
  - Tests skin-depth and thermal-risk calculations.
- Modify: `config/project.json`
  - Changes the selected fabrication route and adds geometry-ready contract fields.
- Modify: `scripts/sector3d_scaffold.py`
  - Adds/reuses low-level geometry generation for `arc_segment` magnets and `A-B-C-C-B-A` phase-belt envelope layers.
- Modify: `README.md`
  - Documents the new Geometry-valid workflow.
- Modify: `reports/sector3d_physics_contract.md`
  - Records the new fabrication route, first-version limitations, and future validation path.

---

### Task 1: Define The Geometry Contract And Manufacturing Gates

**Files:**
- Create: `tests/test_sector3d_geometry_contract.py`
- Create: `scripts/sector3d_geometry_contract.py`
- Modify: `config/project.json`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sector3d_geometry_contract.py`:

```python
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from sector3d_geometry_contract import build_geometry_contract
from sector3d_geometry_contract import clearance_budget
from sector3d_geometry_contract import layer_phase_statistics
from sector3d_geometry_contract import validate_geometry_contract


class Sector3DGeometryContractTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def test_geometry_contract_matches_selected_first_prototype(self):
        contract = build_geometry_contract(self.load_project())
        self.assertEqual(contract["fabrication_route"], "laminated_copper_wave_winding")
        self.assertEqual(contract["magnet_geometry_mode"], "arc_segment")
        self.assertEqual(contract["coil_geometry_mode"], "phase_stacked_mirror_parallel")
        self.assertEqual(contract["active_conductor_geometry_mode"], "phase_belt_envelope")
        self.assertEqual(contract["axial_layer_phase_sequence"], ["A", "B", "C", "C", "B", "A"])
        self.assertTrue(contract["phase_layer_contains_both_polarities"])
        self.assertFalse(contract["terminal_busbar_geometry_present"])
        self.assertEqual(contract["max_part_outer_diameter_mm"], 100.0)

    def test_stack_expansion_and_clearance_budget_are_not_idealized(self):
        contract = build_geometry_contract(self.load_project())
        budget = clearance_budget(contract)
        self.assertGreater(budget["non_copper_stack_allowance_mm"], 0.0)
        self.assertGreaterEqual(budget["single_side_clearance_required_mm"], 0.8)
        self.assertIn("mechanical_clearance_ok", budget)

    def test_layer_statistics_mark_c_as_core_layer(self):
        stats = layer_phase_statistics(["A", "B", "C", "C", "B", "A"])
        self.assertEqual(stats["parallel_layers_per_phase"]["A"], 2)
        self.assertEqual(stats["parallel_layers_per_phase"]["B"], 2)
        self.assertEqual(stats["parallel_layers_per_phase"]["C"], 2)
        self.assertEqual(stats["core_phase"], "C")
        self.assertGreater(stats["c_layer_thermal_bottleneck_risk"], 0.0)

    def test_contract_validation_reports_risk_gates_separately(self):
        result = validate_geometry_contract(self.load_project())
        self.assertIn("hard_gates", result)
        self.assertIn("risk_gates", result)
        self.assertIn("future_validation", result)
        self.assertIn("pwm_ac_loss_requires_frequency_domain_check", result["risk_gates"])
        self.assertIn("detailed_wave_winding_geometry", result["future_validation"])
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sector3d_geometry_contract'`.

- [ ] **Step 3: Add the geometry-ready config**

Modify `config/project.json`:

```json
"fabrication": {
  "selected_route": "laminated_copper_wave_winding",
  "notes": "No PCB carrier in the active stator. Use laminated thin copper wave-winding sheets, fiberglass active-zone support, and aluminum support only in lower-field heat-spreading zones."
}
```

Add under `sector_3d`:

```json
"geometry_ready": {
  "host_only": true,
  "strict_active_project": true,
  "expected_project_name_contains": "sector3d_working",
  "expected_design_name": "Sector3D",
  "delete_generated_prefix": "Auto3D_",
  "artifact_json": "artifacts/sector3d_geometry_ready.json",
  "artifact_md": "reports/sector3d_geometry_ready.md",
  "magnet_geometry_mode": "arc_segment",
  "coil_geometry_mode": "phase_stacked_mirror_parallel",
  "active_conductor_geometry_mode": "phase_belt_envelope",
  "axial_layer_phase_sequence": ["A", "B", "C", "C", "B", "A"],
  "phase_layer_contains_both_polarities": true,
  "terminal_busbar_geometry_present": false,
  "end_connection_geometry_mode": "estimated_not_modeled",
  "busbar_loss_estimated": true,
  "max_part_outer_diameter_mm": 100.0,
  "single_side_clearance_required_mm": 0.8,
  "copper_sheet_thickness_mm": 0.3,
  "insulation_per_layer_mm": 0.03,
  "adhesive_residual_per_interface_mm": 0.05,
  "axial_runout_allowance_mm": 0.2,
  "press_cure_required": true,
  "support_strategy": "fiberglass_active_zone_aluminum_low_field_heat_spreader"
}
```

- [ ] **Step 4: Implement the pure-Python contract module**

Create `scripts/sector3d_geometry_contract.py`:

```python
from __future__ import print_function


def _float(value, default_value=0.0):
    try:
        return float(value)
    except Exception:
        return default_value


def build_geometry_contract(project_cfg):
    fixed = project_cfg["machine_fixed"]
    geometry_cfg = project_cfg["sector_3d"]["geometry_ready"]
    return {
        "fabrication_route": project_cfg["fabrication"]["selected_route"],
        "magnet_geometry_mode": geometry_cfg["magnet_geometry_mode"],
        "coil_geometry_mode": geometry_cfg["coil_geometry_mode"],
        "active_conductor_geometry_mode": geometry_cfg["active_conductor_geometry_mode"],
        "axial_layer_phase_sequence": list(geometry_cfg["axial_layer_phase_sequence"]),
        "phase_layer_contains_both_polarities": bool(geometry_cfg["phase_layer_contains_both_polarities"]),
        "terminal_busbar_geometry_present": bool(geometry_cfg["terminal_busbar_geometry_present"]),
        "end_connection_geometry_mode": geometry_cfg["end_connection_geometry_mode"],
        "busbar_loss_estimated": bool(geometry_cfg["busbar_loss_estimated"]),
        "max_part_outer_diameter_mm": _float(geometry_cfg["max_part_outer_diameter_mm"]),
        "outer_diameter_mm": _float(fixed["outer_diameter_mm"]),
        "single_side_clearance_required_mm": _float(geometry_cfg["single_side_clearance_required_mm"]),
        "copper_sheet_thickness_mm": _float(geometry_cfg["copper_sheet_thickness_mm"]),
        "insulation_per_layer_mm": _float(geometry_cfg["insulation_per_layer_mm"]),
        "adhesive_residual_per_interface_mm": _float(geometry_cfg["adhesive_residual_per_interface_mm"]),
        "axial_runout_allowance_mm": _float(geometry_cfg["axial_runout_allowance_mm"]),
        "support_strategy": geometry_cfg["support_strategy"],
        "press_cure_required": bool(geometry_cfg["press_cure_required"]),
    }


def layer_phase_statistics(sequence):
    counts = {}
    z_sum = {}
    for index, phase in enumerate(sequence):
        counts[phase] = counts.get(phase, 0) + 1
        z_sum[phase] = z_sum.get(phase, 0.0) + float(index)
    average_index = {}
    for phase, count in counts.items():
        average_index[phase] = z_sum[phase] / float(count)
    middle = (len(sequence) - 1.0) / 2.0
    core_phase = min(average_index.keys(), key=lambda phase: abs(average_index[phase] - middle))
    return {
        "parallel_layers_per_phase": counts,
        "average_layer_index": average_index,
        "core_phase": core_phase,
        "c_layer_thermal_bottleneck_risk": 1.0 if core_phase == "C" else 0.5,
    }


def clearance_budget(contract):
    layer_count = len(contract["axial_layer_phase_sequence"])
    interface_count = layer_count + 1
    copper_stack = layer_count * contract["copper_sheet_thickness_mm"]
    non_copper = (
        layer_count * contract["insulation_per_layer_mm"]
        + interface_count * contract["adhesive_residual_per_interface_mm"]
    )
    expanded_stator_stack = copper_stack + non_copper
    required_total_gap_allowance = (
        2.0 * contract["single_side_clearance_required_mm"]
        + contract["axial_runout_allowance_mm"]
    )
    return {
        "copper_stack_mm": copper_stack,
        "non_copper_stack_allowance_mm": non_copper,
        "expanded_stator_stack_mm": expanded_stator_stack,
        "single_side_clearance_required_mm": contract["single_side_clearance_required_mm"],
        "axial_runout_allowance_mm": contract["axial_runout_allowance_mm"],
        "required_total_gap_allowance_mm": required_total_gap_allowance,
        "mechanical_clearance_ok": contract["single_side_clearance_required_mm"] >= 0.8,
    }


def validate_geometry_contract(project_cfg):
    contract = build_geometry_contract(project_cfg)
    hard = {}
    hard["outer_diameter_within_100mm"] = contract["outer_diameter_mm"] <= contract["max_part_outer_diameter_mm"]
    hard["six_layer_sequence"] = contract["axial_layer_phase_sequence"] == ["A", "B", "C", "C", "B", "A"]
    hard["mechanical_clearance_ok"] = clearance_budget(contract)["mechanical_clearance_ok"]
    hard["no_terminal_busbar_geometry_in_v1"] = not contract["terminal_busbar_geometry_present"]
    risk = [
        "c_layer_thermal_bottleneck",
        "parallel_bridge_balance_risk",
        "aluminum_eddy_current_risk",
        "pwm_ac_loss_requires_frequency_domain_check",
    ]
    future = [
        "detailed_wave_winding_geometry",
        "fiberglass_skeleton_cad",
        "u_shaped_busbar_geometry",
        "full_layer_thermal_resistance_network",
        "frequency_domain_eddy_current_ac_loss",
        "final_four_gap_topology_correlation",
    ]
    return {
        "geometry_ready_contract_ok": all(hard.values()),
        "hard_gates": hard,
        "risk_gates": risk,
        "future_validation": future,
    }
```

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\sector3d_geometry_contract.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 6: Commit**

```powershell
git add config/project.json scripts/sector3d_geometry_contract.py tests/test_sector3d_geometry_contract.py
git commit -m "Define Sector3D geometry-ready manufacturing contract"
```

---

### Task 2: Add Thermal And PWM Risk Screening

**Files:**
- Create: `tests/test_sector3d_thermal_risk.py`
- Create: `scripts/sector3d_thermal_risk.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sector3d_thermal_risk.py`:

```python
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from sector3d_thermal_risk import copper_skin_depth_mm
from sector3d_thermal_risk import classify_pwm_risk
from sector3d_thermal_risk import hot_resistance
from sector3d_thermal_risk import layer_thermal_risk_summary


class Sector3DThermalRiskTests(unittest.TestCase):
    def test_skin_depth_decreases_with_frequency(self):
        d10 = copper_skin_depth_mm(10000.0)
        d20 = copper_skin_depth_mm(20000.0)
        d40 = copper_skin_depth_mm(40000.0)
        self.assertGreater(d10, d20)
        self.assertGreater(d20, d40)

    def test_pwm_risk_classification_uses_thickness_to_skin_depth(self):
        low = classify_pwm_risk(0.05, 20000.0)
        high = classify_pwm_risk(1.0, 40000.0)
        self.assertEqual(low["risk"], "low")
        self.assertEqual(high["risk"], "high")

    def test_hot_resistance_increases_with_temperature_and_contact_margin(self):
        out = hot_resistance(0.5, 100.0, contact_resistance_ohm=0.01)
        self.assertGreater(out, 0.5)

    def test_c_layer_is_reported_as_thermal_bottleneck(self):
        summary = layer_thermal_risk_summary(["A", "B", "C", "C", "B", "A"])
        self.assertEqual(summary["core_phase"], "C")
        self.assertIn("C layer is the likely stall-current bottleneck", summary["risk_note"])
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_thermal_risk -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sector3d_thermal_risk'`.

- [ ] **Step 3: Implement the thermal risk helper**

Create `scripts/sector3d_thermal_risk.py`:

```python
from __future__ import print_function

import math


COPPER_RESISTIVITY_20C_OHM_M = 1.724e-8
COPPER_RELATIVE_PERMEABILITY = 1.0
MU0 = 4.0 * math.pi * 1.0e-7
COPPER_TEMPCO_PER_C = 0.00393


def copper_skin_depth_mm(frequency_hz):
    frequency = max(float(frequency_hz), 1.0)
    omega = 2.0 * math.pi * frequency
    depth_m = math.sqrt(2.0 * COPPER_RESISTIVITY_20C_OHM_M / (omega * MU0 * COPPER_RELATIVE_PERMEABILITY))
    return depth_m * 1000.0


def classify_pwm_risk(copper_thickness_mm, frequency_hz):
    depth = copper_skin_depth_mm(frequency_hz)
    ratio = float(copper_thickness_mm) / max(depth, 1.0e-9)
    if ratio < 0.3:
        risk = "low"
    elif ratio <= 1.0:
        risk = "medium"
    else:
        risk = "high"
    return {
        "frequency_hz": float(frequency_hz),
        "skin_depth_mm": depth,
        "thickness_to_skin_depth": ratio,
        "risk": risk,
    }


def hot_resistance(resistance_20c_ohm, copper_temperature_c, contact_resistance_ohm=0.0):
    return float(resistance_20c_ohm) * (1.0 + COPPER_TEMPCO_PER_C * (float(copper_temperature_c) - 20.0)) + float(contact_resistance_ohm)


def pwm_sweep(copper_thickness_mm, frequencies_hz):
    return [classify_pwm_risk(copper_thickness_mm, frequency) for frequency in frequencies_hz]


def layer_thermal_risk_summary(sequence):
    middle = (len(sequence) - 1.0) / 2.0
    phase_distances = {}
    for index, phase in enumerate(sequence):
        phase_distances.setdefault(phase, []).append(abs(float(index) - middle))
    avg_distance = {}
    for phase, values in phase_distances.items():
        avg_distance[phase] = sum(values) / float(len(values))
    core_phase = min(avg_distance.keys(), key=lambda phase: avg_distance[phase])
    return {
        "core_phase": core_phase,
        "average_distance_from_midplane": avg_distance,
        "risk_note": "%s layer is the likely stall-current bottleneck; compute continuous current from this layer first." % core_phase,
    }
```

- [ ] **Step 4: Verify tests pass**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_thermal_risk -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\sector3d_thermal_risk.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 5: Commit**

```powershell
git add scripts/sector3d_thermal_risk.py tests/test_sector3d_thermal_risk.py
git commit -m "Add Sector3D thermal and PWM risk screening"
```

---

### Task 3: Build Host-Only Geometry-Ready Entry Point

**Files:**
- Create: `scripts/build_sector3d_geometry_ready.py`
- Create: `launchers/Queue-BuildSector3DGeometryReady.ps1`
- Test: `tests/test_sector3d_geometry_contract.py`

- [ ] **Step 1: Add pure-Python artifact tests**

Append to `tests/test_sector3d_geometry_contract.py`:

```python
from build_sector3d_geometry_ready import geometry_ready_summary


class Sector3DGeometryReadySummaryTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def test_summary_does_not_claim_solve_ready(self):
        summary = geometry_ready_summary(
            self.load_project(),
            session_gate={"ok": True, "active_project": "sector3d_working", "active_design": "Sector3D"},
            object_gate={"ok": True, "created_count": 20, "deleted_count": 10, "missing_objects": []},
            material_gate={"ok": True, "vacuum_objects": []},
        )
        self.assertTrue(summary["geometry_ready"])
        self.assertFalse(summary["solve_ready"])
        self.assertIn("pwm_ac_loss_requires_frequency_domain_check", summary["risk_gates"])
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'build_sector3d_geometry_ready'`.

- [ ] **Step 3: Implement the entry point skeleton**

Create `scripts/build_sector3d_geometry_ready.py`:

```python
from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from sector3d_geometry_contract import validate_geometry_contract


def _host_mode():
    return bool(globals().get("__agent_host_mode", False))


def _active_project_name():
    project = globals().get("oProject")
    if project:
        try:
            return project.GetName()
        except Exception:
            return ""
    return ""


def _active_design_name():
    design = globals().get("oDesign")
    if design:
        try:
            return design.GetName()
        except Exception:
            return ""
    return ""


def session_gate(project_cfg):
    geometry_cfg = project_cfg["sector_3d"]["geometry_ready"]
    active_project = _active_project_name()
    active_design = _active_design_name()
    ok = (
        _host_mode()
        and geometry_cfg["expected_project_name_contains"].lower() in active_project.lower()
        and active_design == geometry_cfg["expected_design_name"]
    )
    return {
        "ok": ok,
        "host_mode": _host_mode(),
        "active_project": active_project,
        "active_design": active_design,
        "expected_project_name_contains": geometry_cfg["expected_project_name_contains"],
        "expected_design": geometry_cfg["expected_design_name"],
    }


def geometry_ready_summary(project_cfg, session_gate, object_gate, material_gate):
    contract = validate_geometry_contract(project_cfg)
    geometry_ready = bool(session_gate.get("ok")) and bool(object_gate.get("ok")) and bool(material_gate.get("ok")) and bool(contract["geometry_ready_contract_ok"])
    return {
        "timestamp": timestamp_string(),
        "geometry_ready": geometry_ready,
        "solve_ready": False,
        "session_gate": session_gate,
        "object_gate": object_gate,
        "material_gate": material_gate,
        "hard_gates": contract["hard_gates"],
        "risk_gates": contract["risk_gates"],
        "future_validation": contract["future_validation"],
    }


def write_markdown(path, summary):
    lines = []
    lines.append("# Sector3D Geometry Ready Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- geometry_ready: `%s`" % summary.get("geometry_ready", False))
    lines.append("- solve_ready: `%s`" % summary.get("solve_ready", False))
    lines.append("")
    lines.append("## Session Gate")
    lines.append("")
    for key, value in summary.get("session_gate", {}).items():
        lines.append("- %s: `%s`" % (key, value))
    lines.append("")
    lines.append("## Hard Gates")
    lines.append("")
    for key, value in summary.get("hard_gates", {}).items():
        lines.append("- %s: `%s`" % (key, value))
    lines.append("")
    lines.append("## Risk Gates")
    lines.append("")
    for item in summary.get("risk_gates", []):
        lines.append("- %s" % item)
    lines.append("")
    lines.append("## Future Validation")
    lines.append("")
    for item in summary.get("future_validation", []):
        lines.append("- %s" % item)
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "build_sector3d_geometry_ready_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    gate = session_gate(project_cfg)
    if not gate["ok"]:
        summary = geometry_ready_summary(project_cfg, gate, {"ok": False, "created_count": 0, "deleted_count": 0}, {"ok": False})
        artifact_json = os.path.join(root, project_cfg["sector_3d"]["geometry_ready"]["artifact_json"])
        artifact_md = os.path.join(root, project_cfg["sector_3d"]["geometry_ready"]["artifact_md"])
        save_json(artifact_json, summary)
        write_markdown(artifact_md, summary)
        raise RuntimeError("Sector3D geometry-ready session gate failed; see %s" % artifact_md)
    raise RuntimeError("Geometry build body is implemented in the next task; session gate passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add the launcher**

Create `launchers/Queue-BuildSector3DGeometryReady.ps1`:

```powershell
& (Join-Path $PSScriptRoot 'Queue-Command.ps1') -Action run_script -ScriptPath scripts/build_sector3d_geometry_ready.py
```

- [ ] **Step 5: Verify tests and compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\build_sector3d_geometry_ready.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 6: Commit**

```powershell
git add scripts/build_sector3d_geometry_ready.py launchers/Queue-BuildSector3DGeometryReady.ps1 tests/test_sector3d_geometry_contract.py
git commit -m "Add host-only Sector3D geometry-ready entry point"
```

---

### Task 4: Generate Arc Magnets And Six-Layer Phase-Belt Envelope Geometry

**Files:**
- Modify: `scripts/sector3d_scaffold.py`
- Modify: `scripts/build_sector3d_geometry_ready.py`
- Test: `tests/test_sector3d_geometry_contract.py`

- [ ] **Step 1: Add geometry-definition tests**

Append to `tests/test_sector3d_geometry_contract.py`:

```python
from sector3d_scaffold import _magnet_pole_objects_definition
from sector3d_scaffold import _phase_belt_objects_definition
from sector3d_scaffold import _sector_geometry_metadata


class Sector3DLayeredGeometryDefinitionTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def baseline_case(self):
        return {
            "pole_count": 24,
            "pole_arc_ratio": 0.72,
            "airgap_mm": 0.9,
            "coil_mean_radius_mm": 39.5,
            "coil_radial_span_mm": 12.5,
            "conductor_thickness_mm": 0.3,
        }

    def test_arc_segment_magnets_remain_first_mode(self):
        project_cfg = self.load_project()
        sector_meta = _sector_geometry_metadata(project_cfg, self.baseline_case())
        magnets = _magnet_pole_objects_definition(project_cfg, self.baseline_case(), sector_meta)
        self.assertGreaterEqual(len(magnets), 4)
        self.assertTrue(all(item["name"].startswith("Auto3D_Magnet_") for item in magnets))

    def test_phase_belts_follow_abc_cba_layers_and_polarities(self):
        project_cfg = self.load_project()
        sector_meta = _sector_geometry_metadata(project_cfg, self.baseline_case())
        belts = _phase_belt_objects_definition(project_cfg, self.baseline_case(), sector_meta)
        layers = belts["axial_layers"]
        self.assertEqual([item["phase"] for item in layers], ["A", "B", "C", "C", "B", "A"])
        for layer in layers:
            self.assertEqual(sorted(layer["polarities"]), ["Negative", "Positive"])
        self.assertEqual(belts["geometry_mode"], "phase_stacked_mirror_parallel")
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
```

Expected: FAIL because `_phase_belt_objects_definition()` still represents the old per-face phase-belt model.

- [ ] **Step 3: Update the scaffold phase-belt definition**

Modify `_phase_belt_objects_definition(project_cfg, case_row, sector_meta=None)` to read:

```python
geometry_ready_cfg = project_cfg.get("sector_3d", {}).get("geometry_ready", {})
layer_sequence = list(geometry_ready_cfg.get("axial_layer_phase_sequence", []))
```

When `coil_geometry_mode == "phase_stacked_mirror_parallel"`, create axial layer definitions:

```python
layer_pitch_expr = "copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm"
for layer_index, phase_letter in enumerate(layer_sequence):
    phase_name = "Phase%s" % phase_letter
    z_expr = "auto3d_z_lower_flat_copper_mm + %d*(%s)" % (layer_index, layer_pitch_expr)
    create only the positive and negative angular belts belonging to phase_name.
```

The returned dictionary must include:

```python
"geometry_mode": "phase_stacked_mirror_parallel",
"axial_layers": [
  {"index": 1, "phase": "A", "z_start": "auto3d_z_lower_flat_copper_mm + 0*(copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm)", "polarities": ["Positive", "Negative"]},
  {"index": 2, "phase": "B", "z_start": "auto3d_z_lower_flat_copper_mm + 1*(copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm)", "polarities": ["Positive", "Negative"]},
  {"index": 3, "phase": "C", "z_start": "auto3d_z_lower_flat_copper_mm + 2*(copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm)", "polarities": ["Positive", "Negative"]},
  {"index": 4, "phase": "C", "z_start": "auto3d_z_lower_flat_copper_mm + 3*(copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm)", "polarities": ["Positive", "Negative"]},
  {"index": 5, "phase": "B", "z_start": "auto3d_z_lower_flat_copper_mm + 4*(copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm)", "polarities": ["Positive", "Negative"]},
  {"index": 6, "phase": "A", "z_start": "auto3d_z_lower_flat_copper_mm + 5*(copper_sheet_thickness_mm + insulation_per_layer_mm + adhesive_residual_per_interface_mm)", "polarities": ["Positive", "Negative"]}
]
```

Use object names that preserve the generated prefix and layer identity:

```python
Auto3D_PhaseA_L01_Pos_001
Auto3D_PhaseA_L01_Neg_001
Auto3D_PhaseC_L03_Pos_001
```

- [ ] **Step 4: Update geometry-ready build body**

In `build_sector3d_geometry_ready.py`, after the session gate passes:

```python
from sector3d_scaffold import build_sector_3d_scaffold
```

Call the existing scaffold in cleanup mode:

```python
FUNCTIONAL_NONVACUUM_PREFIXES = (
    "Auto3D_Magnet_",
    "Auto3D_Phase",
    "Auto3D_BottomBackIron",
    "Auto3D_TopBackIron",
    "Auto3D_StatorSupport",
)


def created_vacuum_functional_objects(created_objects):
    vacuum_objects = []
    for item in created_objects:
        name = str(item.get("name", ""))
        material = str(item.get("material", "")).strip().lower()
        requires_functional_material = any(name.startswith(prefix) for prefix in FUNCTIONAL_NONVACUUM_PREFIXES)
        if requires_functional_material and material in ("", "vacuum"):
            vacuum_objects.append({"name": name, "material": material})
    return vacuum_objects


result = build_sector_3d_scaffold(oProject, oDesign, project_cfg, {}, logger, cleanup_first=True)
vacuum_functional_objects = created_vacuum_functional_objects(result.get("created_objects", []))
object_gate = {
    "ok": not bool(result.get("blocking_issues")),
    "created_count": len(result.get("created_objects", [])),
    "deleted_count": len(result.get("deleted_objects", [])),
    "missing_objects": result.get("blocking_issues", []),
}
material_gate = {
    "ok": not bool(vacuum_functional_objects),
    "vacuum_functional_objects": vacuum_functional_objects,
    "helper_air_vacuum_allowed": ["Auto3D_Region", "Auto3D_RotatingBand", "Auto3D_Periodic_Master", "Auto3D_Periodic_Slave"],
}
summary = geometry_ready_summary(project_cfg, gate, object_gate, material_gate)
```

Save JSON/Markdown and `save_project(oProject, logger)`.

- [ ] **Step 5: Verify tests and compile**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\sector3d_scaffold.py scripts\build_sector3d_geometry_ready.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 6: Commit**

```powershell
git add scripts/sector3d_scaffold.py scripts/build_sector3d_geometry_ready.py tests/test_sector3d_geometry_contract.py
git commit -m "Generate six-layer Sector3D geometry-ready envelope"
```

---

### Task 5: Emit Dedicated Geometry-Ready Artifacts

**Files:**
- Modify: `scripts/build_sector3d_geometry_ready.py`
- Test: `tests/test_sector3d_geometry_contract.py`

- [ ] **Step 1: Add artifact content tests**

Append to `tests/test_sector3d_geometry_contract.py`:

```python
class Sector3DGeometryArtifactContentTests(unittest.TestCase):
    def load_project(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            return json.load(handle)

    def test_markdown_mentions_limits_and_non_goals(self):
        summary = geometry_ready_summary(
            self.load_project(),
            session_gate={"ok": True, "active_project": "sector3d_working", "active_design": "Sector3D"},
            object_gate={"ok": True, "created_count": 20, "deleted_count": 10, "missing_objects": []},
            material_gate={"ok": True, "vacuum_objects": []},
        )
        from build_sector3d_geometry_ready import markdown_text
        text = markdown_text(summary)
        self.assertIn("Geometry Ready Summary", text)
        self.assertIn("A-B-C-C-B-A", text)
        self.assertIn("100 mm", text)
        self.assertIn("not solve-ready", text)
        self.assertIn("PWM", text)
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
```

Expected: FAIL because `markdown_text()` does not exist.

- [ ] **Step 3: Refactor markdown writer**

In `build_sector3d_geometry_ready.py`, extract markdown content:

```python
def markdown_text(summary):
    lines = []
    lines.append("# Sector3D Geometry Ready Summary")
    lines.append("")
    lines.append("This artifact proves geometry validity only. It is not solve-ready.")
    lines.append("")
    lines.append("- layer_sequence: `A-B-C-C-B-A`")
    lines.append("- max_part_outer_diameter_mm: `100 mm`")
    lines.append("- pwm_loss_strategy: `frequency-domain future validation, not 3D Transient PWM`")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("- geometry_ready: `%s`" % summary.get("geometry_ready", False))
    lines.append("- solve_ready: `%s`" % summary.get("solve_ready", False))
    lines.append("- session_gate_ok: `%s`" % summary.get("session_gate", {}).get("ok", False))
    lines.append("- object_gate_ok: `%s`" % summary.get("object_gate", {}).get("ok", False))
    lines.append("- material_gate_ok: `%s`" % summary.get("material_gate", {}).get("ok", False))
    lines.append("")
    lines.append("## Risk Gates")
    lines.append("")
    for item in summary.get("risk_gates", []):
        lines.append("- %s" % item)
    lines.append("")
    lines.append("## Future Validation")
    lines.append("")
    for item in summary.get("future_validation", []):
        lines.append("- %s" % item)
    return "\n".join(lines) + "\n"
```

Make `write_markdown()` call `markdown_text(summary)`.

- [ ] **Step 4: Verify tests pass**

Run:

```powershell
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m unittest tests.test_sector3d_geometry_contract -v
& 'C:\Users\fjcy\AppData\Roaming\.pyaedt_env\3_10\Scripts\python.exe' -m py_compile scripts\build_sector3d_geometry_ready.py
```

Expected: PASS and no py_compile output.

- [ ] **Step 5: Commit**

```powershell
git add scripts/build_sector3d_geometry_ready.py tests/test_sector3d_geometry_contract.py
git commit -m "Write Sector3D geometry-ready artifacts"
```

---

### Task 6: Document The Revised Workflow

**Files:**
- Modify: `README.md`
- Modify: `reports/sector3d_physics_contract.md`

- [ ] **Step 1: Update README**

Add a section:

```markdown
## Sector3D Geometry-Valid Workflow

The first Sector3D stage is now geometry validity, not solve readiness.

Use:

- `launchers\Queue-BuildSector3DGeometryReady.ps1`

This command must run through the in-AEDT host. It expects the correct `sector3d_working` project and `Sector3D` design to already be open. It deletes only `Auto3D_*` objects, rebuilds the SSDR geometry, and writes:

- `artifacts/sector3d_geometry_ready.json`
- `reports/sector3d_geometry_ready.md`

The first coil model is an active-zone envelope for a six-layer laminated copper stack with `A-B-C-C-B-A` axial order. It does not include detailed busbar, real wave-winding end turns, or PWM AC loss.
```

- [ ] **Step 2: Update the physics contract**

Add:

```markdown
### Laminated Copper Geometry-Ready Stage

The first geometry-valid model uses laminated thin copper sheets, not a PCB carrier. The active conductor envelope follows an `A-B-C-C-B-A` six-layer mirror stack. Each layer contains both positive and negative active belts for its own phase. Same-phase layers are parallel.

The first version must include Z-axis expansion from insulation and adhesive, and it must enforce a single-side mechanical clearance of at least `0.8 mm`. The C-layer core thermal bottleneck, busbar current-sharing risk, aluminum eddy-current risk, and PWM AC-loss path are risk gates. They must be reported, but they are not solved by the geometry-ready stage.

Do not run 10/20/40 kHz PWM directly in Maxwell 3D Transient. Use a decoupled path: low-frequency transient for torque/flux linkage, matrix or energy extraction for L/R, circuit simulation for PWM ripple current, FFT for harmonic current amplitudes, and Maxwell Eddy Current frequency-domain solves for AC copper loss on shortlisted designs.
```

- [ ] **Step 3: Verify docs mention required terms**

Run:

```powershell
rg -n "Geometry-valid|A-B-C-C-B-A|0.8 mm|PWM|Eddy Current|sector3d_geometry_ready" README.md reports\sector3d_physics_contract.md
```

Expected: all terms appear.

- [ ] **Step 4: Commit**

```powershell
git add README.md reports/sector3d_physics_contract.md
git commit -m "Document Sector3D geometry-valid workflow"
```

---

## Live AEDT Validation Checkpoint

After Tasks 1-6 pass locally, run:

```powershell
launchers\Run-Launcher.cmd Start-AEDTHost.ps1
launchers\Run-Launcher.cmd Queue-BuildSector3DGeometryReady.ps1
launchers\Run-Launcher.cmd Get-AgentStatus.ps1
```

Expected:

- The script refuses to run unless the in-AEDT host is active and the expected working project/design are active.
- Old generated `Auto3D_*` objects are deleted; non-`Auto3D_*` objects are preserved.
- `artifacts/sector3d_geometry_ready.json` exists.
- `reports/sector3d_geometry_ready.md` exists.
- The report says `geometry_ready = true` only when all hard gates pass.
- The report says `solve_ready = false`.
- The report lists C-layer thermal risk, busbar/current-sharing risk, aluminum eddy-current risk, and PWM frequency-domain AC-loss validation as unresolved risk/future items.

If the geometry-ready live run fails before object creation, fix session/project/design gating first. If it fails after object creation, inspect object/material/gate diagnostics before moving to excitation, reports, or solve planning.

---

## Self-Review Notes

- This revised plan avoids making first version too heavy: it enforces only geometry/manufacturing hard gates and reports deeper risks without solving them.
- It removes PCB-carrier assumptions from the first geometry target.
- It keeps `build_sector3d_model.py` intact and creates a clearer `build_sector3d_geometry_ready.py` entry point.
- It explicitly prevents the expensive and misleading strategy of running PWM square waves directly in Maxwell 3D Transient.
- It preserves the final `4 Nm @ 3 Arms` boundary: the SSDR geometry-valid stage does not judge final four-gap machine performance.
