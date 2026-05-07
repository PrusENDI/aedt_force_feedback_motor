import importlib
import json
import os
import re
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class DxfCopperV2BuildContractTests(unittest.TestCase):
    def test_v2_stage_config_uses_clean_project_target(self):
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            project_cfg = json.load(handle)

        stage = project_cfg["dxf_copper_v2"]

        self.assertEqual(stage["design_name"], "DxfCopperV2SingleLayer")
        self.assertEqual(stage["design_type"], "Maxwell 3D")
        self.assertEqual(stage["solution_type"], "ElectroDCConduction")
        self.assertEqual(stage["project_mode"], "working_project")
        self.assertEqual(stage["working_path"], "aedt_projects/dxf_copper_v2_single_layer.aedt")

    def test_v2_aedt_names_follow_conservative_policy(self):
        geometry = importlib.import_module("dxf_copper_geometry")
        names = geometry.v2_aedt_names("2026-05-06T00-00-00Z_bad:suffix")
        pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

        for value in names.values():
            self.assertRegex(value, pattern)
            self.assertNotIn("-", value)
            self.assertNotIn(":", value)
            self.assertNotIn(" ", value)

    def test_host_runtime_routes_v2_to_clean_project(self):
        runtime = importlib.import_module("agent_runtime")
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            project_cfg = json.load(handle)
        context = {
            "root": ROOT,
            "project_cfg": project_cfg,
            "paths": {key: os.path.join(ROOT, value) for key, value in project_cfg["paths"].items()},
        }
        command = {
            "action": "run_script",
            "payload": {"script_path": "scripts/build_dxf_copper_v2.py"},
        }

        target = runtime.resolve_host_target(context, command)
        expected_path = os.path.normpath(os.path.join(ROOT, "aedt_projects", "dxf_copper_v2_single_layer.aedt"))
        actual_path = os.path.normpath(target["working_path"])

        self.assertEqual(target["stage_key"], "dxf_copper_v2")
        self.assertEqual(target["project_mode"], "working_project")
        self.assertEqual(target["design_name"], "DxfCopperV2SingleLayer")
        self.assertEqual(target["solution_type"], "ElectroDCConduction")
        self.assertTrue(os.path.isabs(target["working_path"]))
        self.assertEqual(actual_path, expected_path)

    def test_v2_launcher_queues_v2_build_script(self):
        launcher_path = os.path.join(ROOT, "launchers", "Queue-BuildDxfCopperV2.ps1")
        self.assertTrue(os.path.isfile(launcher_path))
        with open(launcher_path, "r") as handle:
            text = handle.read()
        self.assertIn("Queue-Command.ps1", text)
        self.assertIn("scripts/build_dxf_copper_v2.py", text)

    def test_v2_build_summary_keeps_readiness_split(self):
        module = importlib.import_module("build_dxf_copper_v2")

        summary = module.build_v2_single_layer_summary(host_mode=False)

        self.assertEqual(summary["milestone"], "Milestone 3: Repeatable Single-Layer Geometry Generator")
        self.assertTrue(summary["single_layer_geometry_source_ready"])
        self.assertFalse(summary["geometry_ready"])
        self.assertFalse(summary["dc_conduction_ready"])
        self.assertFalse(summary["solve_ready"])
        self.assertFalse(summary["manufacturing_ready"])
        self.assertEqual(summary["geometry"]["metadata"]["corner_policy"], "flat_caps_mitred_joins_no_auto_rounding")
        self.assertEqual(summary["geometry_scope"], "v2_single_layer_phase_a_representative_segment")
        self.assertEqual(summary["topology_preset"], "representative_single_layer_chain")
        self.assertFalse(summary["full_phase_winding_enabled"])
        self.assertIn("geometry_diagnostics", summary)
        self.assertGreater(summary["geometry_diagnostics"]["centerline_length_mm"], 0.0)
        self.assertIn("estimate_caveat", summary)
        self.assertIn("dxf_preview", summary)
        self.assertFalse(summary["dxf_preview"].get("blocking", True))

    def test_v2_report_only_main_writes_artifacts_without_aedt(self):
        module = importlib.import_module("build_dxf_copper_v2")
        original_repo_root = module.repo_root
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as root:
                module.repo_root = lambda: root
                paths = module.main(host_mode=False, raise_on_blocking=False)
                self.assertTrue(os.path.isfile(paths["json"]))
                self.assertTrue(os.path.isfile(paths["md"]))
        finally:
            module.repo_root = original_repo_root


if __name__ == "__main__":
    unittest.main()
