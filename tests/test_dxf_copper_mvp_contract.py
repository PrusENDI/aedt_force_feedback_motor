import importlib
import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class DxfCopperMvpContractTests(unittest.TestCase):
    def load_module(self):
        try:
            return importlib.import_module("build_dxf_copper_mvp")
        except ModuleNotFoundError as exc:
            self.fail("scripts/build_dxf_copper_mvp.py is required for V1 build contract: %s" % exc)

    def test_build_summary_keeps_v1_readiness_gates_separate(self):
        module = self.load_module()
        summary = module.build_v1_mvp_summary(host_mode=False)

        self.assertEqual(summary["milestone"], "Milestone 2: DXF-Compatible 3D Copper MVP")
        self.assertFalse(summary["legacy_phase_belt_used"])
        self.assertIn("dxf_compatible_copper_ready", summary)
        self.assertFalse(summary["geometry_ready"])
        self.assertFalse(summary["dc_conduction_ready"])
        self.assertTrue(summary["mesh_defense_required"])
        self.assertIn(summary["aedt_handshake_mode"], ("polyline_points", "import_dxf"))

    def test_v2_contract_does_not_relabel_v1_mvp_artifacts(self):
        module = self.load_module()
        summary = module.build_v1_mvp_summary(host_mode=False)

        self.assertEqual(summary["milestone"], "Milestone 2: DXF-Compatible 3D Copper MVP")
        self.assertIn("dxf_compatible_copper_ready", summary)
        self.assertNotEqual(summary.get("geometry_contract_version"), "dxf-copper-v2")
        self.assertNotEqual(summary.get("geometry", {}).get("geometry_contract_version"), "dxf-copper-v2")
        self.assertNotIn("single_layer_geometry_source_ready", summary)
        for field in ("project_name", "design_name", "design"):
            self.assertNotEqual(summary.get(field), "DxfCopperV2SingleLayer")
        self.assertNotEqual(summary.get("aedt_build", {}).get("design_name"), "DxfCopperV2SingleLayer")

    def test_build_summary_records_mesh_defense_as_blocking_until_assigned(self):
        module = self.load_module()
        summary = module.build_v1_mvp_summary(host_mode=False)

        self.assertEqual(
            summary["mesh_defense"],
            {"required": True, "assigned": False, "target_thickness_mm": 0.3},
        )
        self.assertIn("mesh_defense_not_assigned", summary["blocking_issues"])

    def test_terminal_face_selection_uses_terminal_pad_centers(self):
        module = self.load_module()
        geometry_module = importlib.import_module("dxf_copper_geometry")
        geometry = geometry_module.build_v1_phase_a_geometry()
        faces = [
            {"id": 10, "center": [-29.0, 0.0, 0.15], "area": 32.0},
            {"id": 11, "center": [29.0, 0.0, 0.15], "area": 32.0},
            {"id": 12, "center": [0.0, 0.0, 0.3], "area": 200.0},
        ]

        terminals = module.select_terminal_faces(faces, geometry, tolerance_mm=1.0)

        self.assertEqual([item["role"] for item in terminals], ["source", "sink"])
        self.assertEqual([item["face_id"] for item in terminals], [10, 11])

    def test_terminal_face_selection_prefers_outer_contact_faces_from_aedt(self):
        module = self.load_module()
        geometry_module = importlib.import_module("dxf_copper_geometry")
        geometry = geometry_module.build_v1_phase_a_geometry()
        faces = [
            {"id": 34, "center": [-33.0, 0.0, -0.15], "area": 2.4},
            {"id": 35, "center": [-29.0, 4.0, -0.15], "area": 2.4},
            {"id": 39, "center": [29.0, 4.0, -0.15], "area": 2.4},
            {"id": 40, "center": [33.0, 0.0, -0.15], "area": 2.4},
            {"id": 47, "center": [0.0, 0.0, 0.0], "area": 328.0},
        ]

        terminals = module.select_terminal_faces(faces, geometry, tolerance_mm=1.0)

        self.assertEqual([item["role"] for item in terminals], ["source", "sink"])
        self.assertEqual([item["face_id"] for item in terminals], [34, 40])

    def test_build_cleanup_removes_prior_v1_copper_objects_before_rebuild(self):
        module = self.load_module()

        class Modeler(object):
            object_names = [
                "AutoDxfCopper_PhaseA_L01_Sheet",
                "AutoDxfCopper_PhaseA_L01_Sheet_5",
                "RotorFixture",
            ]

            def __init__(self):
                self.deleted = []

            def delete(self, names):
                self.deleted.extend(names)
                return True

        class App(object):
            def __init__(self):
                self.modeler = Modeler()

        class Logger(object):
            def log(self, message):
                pass

        app = App()
        cleanup = module._cleanup_v1_build_artifacts(app, Logger())

        self.assertEqual(
            app.modeler.deleted,
            ["AutoDxfCopper_PhaseA_L01_Sheet", "AutoDxfCopper_PhaseA_L01_Sheet_5"],
        )
        self.assertEqual(cleanup["deleted_objects"], app.modeler.deleted)
        self.assertEqual(cleanup["blocking_issues"], [])

    def test_report_only_main_writes_artifacts_without_aedt(self):
        module = self.load_module()
        original_repo_root = module.repo_root
        try:
            with tempfile.TemporaryDirectory() as root:
                module.repo_root = lambda: root
                paths = module.main(host_mode=False, raise_on_blocking=False)

                self.assertTrue(os.path.isfile(paths["json"]))
                self.assertTrue(os.path.isfile(paths["md"]))
                with open(paths["json"], "r") as handle:
                    summary = json.load(handle)
                self.assertFalse(summary["geometry_ready"])
                self.assertFalse(summary["dc_conduction_ready"])
                self.assertFalse(summary["host_mode_detected"])
        finally:
            module.repo_root = original_repo_root

    def test_build_launcher_uses_new_v1_script(self):
        launcher_path = os.path.join(ROOT, "launchers", "Queue-BuildDxfCopperMvp.ps1")
        self.assertTrue(os.path.isfile(launcher_path))
        with open(launcher_path, "r") as handle:
            text = handle.read()
        self.assertIn("Queue-Command.ps1", text)
        self.assertIn("scripts/build_dxf_copper_mvp.py", text)
        self.assertNotIn("build_sector3d_geometry_ready.py", text)

    def test_host_runtime_routes_dxf_copper_scripts_to_isolated_project(self):
        runtime = importlib.import_module("agent_runtime")
        with open(os.path.join(ROOT, "config", "project.json"), "r") as handle:
            project_cfg = json.load(handle)
        context = {
            "project_cfg": project_cfg,
            "paths": {key: os.path.join(ROOT, value) for key, value in project_cfg["paths"].items()},
        }
        command = {
            "action": "run_script",
            "payload": {"script_path": "scripts/build_dxf_copper_mvp.py"},
        }

        target = runtime.resolve_host_target(context, command)

        self.assertEqual(target["stage_key"], "dxf_copper_mvp")
        self.assertEqual(target["design_name"], "DxfCopperMvp")
        self.assertEqual(target["design_type"], "Maxwell 3D")
        self.assertEqual(target["solution_type"], "ElectroDCConduction")
        self.assertEqual(target["project_mode"], "active_project")
        self.assertEqual(target["working_path"], "")
        self.assertEqual(target["template_path"], "")

    def test_host_runtime_dxf_route_survives_stale_host_config_context(self):
        runtime = importlib.import_module("agent_runtime")
        context = {
            "root": ROOT,
            "project_cfg": {},
            "paths": {},
        }
        command = {
            "action": "run_script",
            "payload": {"script_path": "scripts/apply_dxf_copper_dc_conduction.py"},
        }

        target = runtime.resolve_host_target(context, command)

        self.assertEqual(target["stage_key"], "dxf_copper_mvp")
        self.assertEqual(target["design_name"], "DxfCopperMvp")
        self.assertEqual(target["solution_type"], "ElectroDCConduction")
        self.assertEqual(target["project_mode"], "active_project")
        self.assertEqual(target["working_path"], "")
        self.assertEqual(target["template_path"], "")

    def test_host_runtime_normalizes_stale_v1_dc_conduction_config(self):
        runtime = importlib.import_module("agent_runtime")
        context = {
            "root": ROOT,
            "project_cfg": {"dxf_copper_mvp": {"solution_type": "DC Conduction"}},
            "paths": {},
        }
        command = {
            "action": "run_script",
            "payload": {"script_path": "scripts/build_dxf_copper_mvp.py"},
        }

        target = runtime.resolve_host_target(context, command)

        self.assertEqual(target["solution_type"], "ElectroDCConduction")

    def test_maxwell3d_electric_dc_solution_aliases_match(self):
        native = importlib.import_module("aedt_native_common")

        self.assertTrue(native.solution_type_matches("Electric DC Conduction", "ElectroDCConduction"))
        self.assertTrue(native.solution_type_matches("ElectroDCConduction", "Electric DC Conduction"))

    def test_maxwell3d_electric_dc_creation_uses_default_design_before_solution_switch(self):
        native = importlib.import_module("aedt_native_common")

        attempts = native._design_creation_solution_attempts("Maxwell 3D", "ElectroDCConduction")

        self.assertEqual(attempts[0], ("default_maxwell3d", "Magnetostatic"))
        self.assertIn(("requested", "ElectroDCConduction"), attempts)

    def test_maxwell3d_electric_dc_set_solution_tries_display_name_alias(self):
        native = importlib.import_module("aedt_native_common")

        values = native._set_solution_type_values("ElectroDCConduction")

        self.assertEqual(values[0], "ElectroDCConduction")
        self.assertIn("Electric DC Conduction", values)

    def test_host_runtime_routes_v1_script_aliases_to_dxf_copper_mvp(self):
        runtime = importlib.import_module("agent_runtime")
        context = {
            "root": ROOT,
            "project_cfg": {},
            "paths": {},
        }
        aliases = [
            "scripts/build_v1_copper_mvp.py",
            "scripts/inspect_v1_dxf_copper.py",
            "scripts/apply_dxf-copper-v1-dc-conduction.py",
        ]

        for script_path in aliases:
            command = {
                "action": "run_script",
                "payload": {"script_path": script_path},
            }
            target = runtime.resolve_host_target(context, command)
            self.assertIsNotNone(target, script_path)
            self.assertEqual(target["stage_key"], "dxf_copper_mvp")
            self.assertEqual(target["design_name"], "DxfCopperMvp")

    def test_host_runtime_uses_single_open_project_when_active_project_is_missing(self):
        runtime = importlib.import_module("agent_runtime")

        class Project(object):
            def GetName(self):
                return "Project4"

        class Design(object):
            def GetName(self):
                return "DxfCopperMvp"

        class Desktop(object):
            def __init__(self):
                self.selected = []

            def GetActiveProject(self):
                return None

            def GetProjectList(self):
                return ["Project4"]

            def SetActiveProject(self, name):
                self.selected.append(name)
                return Project()

        class Logger(object):
            def __init__(self):
                self.messages = []

            def log(self, message):
                self.messages.append(message)

        context = {
            "root": ROOT,
            "project_cfg": {"dxf_copper_mvp": {"solution_type": "ElectroDCConduction"}},
            "paths": {},
        }
        command = {
            "action": "run_script",
            "payload": {"script_path": "scripts/build_dxf_copper_mvp.py"},
        }
        desktop = Desktop()
        original_ensure_design = runtime.ensure_design
        try:
            runtime.ensure_design = lambda oProject, design_name, design_type, solution_type, logger: Design()
            preparation = runtime.ensure_host_design_ready(desktop, context, command, Logger())
        finally:
            runtime.ensure_design = original_ensure_design

        self.assertEqual(desktop.selected, ["Project4"])
        self.assertTrue(preparation["prepared"])
        self.assertEqual(preparation["project_name"], "Project4")
        self.assertEqual(preparation["design_name"], "DxfCopperMvp")

    def test_dc_conduction_refuses_missing_or_unready_build_artifact(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")
        missing_summary = module.build_dc_conduction_summary(build_summary=None)
        self.assertFalse(missing_summary["dc_conduction_ready"])
        self.assertIn("dxf_copper_mvp_artifact_missing", missing_summary["blocking_issues"])

        unready_build = {
            "dxf_compatible_copper_ready": False,
            "terminal_faces": [{"id": 1}, {"id": 2}],
        }
        unready_summary = module.build_dc_conduction_summary(build_summary=unready_build)
        self.assertFalse(unready_summary["dc_conduction_ready"])
        self.assertIn("dxf_compatible_copper_not_ready", unready_summary["blocking_issues"])

    def test_dc_conduction_requires_two_terminal_faces(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")
        build_summary = {
            "dxf_compatible_copper_ready": True,
            "terminal_faces": [{"id": 1}],
        }
        summary = module.build_dc_conduction_summary(build_summary=build_summary)
        self.assertFalse(summary["dc_conduction_ready"])
        self.assertFalse(summary["terminal_faces_present"])
        self.assertIn("terminal_faces_missing", summary["blocking_issues"])

    def test_dc_setup_ready_does_not_replace_current_density_sanity_check(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")
        build_summary = {
            "dxf_compatible_copper_ready": True,
            "terminal_faces": [{"role": "source", "face_id": 1}, {"role": "sink", "face_id": 2}],
        }
        dc_setup_gate = {
            "attempted": True,
            "voltage_assigned": True,
            "sink_assigned": True,
            "setup_created": True,
            "blocking_issues": [],
        }

        summary = module.build_dc_conduction_summary(build_summary=build_summary, dc_setup_gate=dc_setup_gate)

        self.assertTrue(summary["dc_setup_ready"])
        self.assertFalse(summary["dc_conduction_ready"])
        self.assertFalse(summary["solved"])
        self.assertFalse(summary["current_density_continuity_checked"])
        self.assertIn("dc_solve_missing", summary["blocking_issues"])
        self.assertIn("current_density_continuity_not_checked", summary["blocking_issues"])

    def test_dc_conduction_ready_requires_solve_and_current_density_evidence(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")
        build_summary = {
            "dxf_compatible_copper_ready": True,
            "terminal_faces": [{"role": "source", "face_id": 1}, {"role": "sink", "face_id": 2}],
        }
        dc_setup_gate = {
            "attempted": True,
            "voltage_assigned": True,
            "sink_assigned": True,
            "setup_created": True,
            "solved": True,
            "current_density_continuity_checked": True,
            "current_density_evidence": {
                "solution": "AutoDxfCopper_DC : LastAdaptive",
                "quantity": "CurrentDensity",
                "available_quantities": ["CurrentDensity", "CurrentDensityX"],
                "field_export_path": "artifacts/current_density.fld",
                "field_exported": True,
            },
            "blocking_issues": [],
        }

        summary = module.build_dc_conduction_summary(build_summary=build_summary, dc_setup_gate=dc_setup_gate)

        self.assertTrue(summary["dc_setup_ready"])
        self.assertTrue(summary["dc_conduction_ready"])
        self.assertTrue(summary["solved"])
        self.assertTrue(summary["current_density_continuity_checked"])
        self.assertEqual(summary["current_density_evidence"]["quantity"], "CurrentDensity")
        self.assertEqual(summary["blocking_issues"], [])

    def test_dc_conduction_run_names_are_unique_and_solution_tracks_setup(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")

        first = module.dc_run_names("2026-05-05T03-32-37Z_abc123")
        second = module.dc_run_names("2026-05-05T03-32-38Z_def456")

        self.assertNotEqual(first["voltage_assignment"], second["voltage_assignment"])
        self.assertTrue(first["voltage_assignment"].startswith("AutoDxfCopper_Voltage_"))
        self.assertTrue(first["sink_assignment"].startswith("AutoDxfCopper_Sink_"))
        self.assertTrue(first["setup_name"].startswith("AutoDxfCopper_DC_"))
        self.assertEqual(first["solution"], "%s : LastAdaptive" % first["setup_name"])
        self.assertNotIn("-", first["voltage_assignment"])
        self.assertNotIn(":", first["voltage_assignment"])

    def test_dc_cleanup_removes_prior_v1_boundaries_setups_and_field_plots(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")

        class Deletable(object):
            def __init__(self, name):
                self.name = name
                self.deleted = False

            def delete(self):
                self.deleted = True
                return True

        class App(object):
            def __init__(self):
                self.boundaries = [
                    Deletable("AutoDxfCopper_Voltage"),
                    Deletable("AutoDxfCopper_Sink_20260505T034016Z_40dc6daa"),
                    Deletable("ExternalBoundary"),
                ]
                self.setups = [
                    Deletable("AutoDxfCopper_DC_20260505T034016Z_40dc6daa"),
                    Deletable("OtherSetup"),
                ]
                self.post = type("Post", (), {})()
                self.post.field_plots = {
                    "AutoDxfCopper_MagJ_AutoDxfCopper_DC_20260505T034016Z_40dc6daaLastAdaptive": Deletable(
                        "AutoDxfCopper_MagJ_AutoDxfCopper_DC_20260505T034016Z_40dc6daaLastAdaptive"
                    ),
                    "OtherPlot": Deletable("OtherPlot"),
                }

        class Logger(object):
            def log(self, message):
                pass

        app = App()
        cleanup = module._cleanup_v1_dc_artifacts(app, Logger())

        self.assertEqual(
            cleanup["deleted_boundaries"],
            ["AutoDxfCopper_Voltage", "AutoDxfCopper_Sink_20260505T034016Z_40dc6daa"],
        )
        self.assertEqual(cleanup["deleted_setups"], ["AutoDxfCopper_DC_20260505T034016Z_40dc6daa"])
        self.assertEqual(
            cleanup["deleted_field_plots"],
            ["AutoDxfCopper_MagJ_AutoDxfCopper_DC_20260505T034016Z_40dc6daaLastAdaptive"],
        )
        self.assertFalse(app.boundaries[2].deleted)
        self.assertFalse(app.setups[1].deleted)
        self.assertFalse(app.post.field_plots["OtherPlot"].deleted)

    def test_current_density_evidence_tries_candidate_quantities_when_report_list_is_context_only(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")

        class Post(object):
            def __init__(self):
                self.export_attempts = []

            def available_report_quantities(self, **kwargs):
                return ["Volume(AutoDxfCopper_PhaseA_L01_Sheet_3)"]

            def export_field_file(self, **kwargs):
                self.export_attempts.append(kwargs["quantity"])
                return kwargs["quantity"] == "CurrentDensity"

        class App(object):
            def __init__(self):
                self.post = Post()

        class Logger(object):
            def log(self, message):
                pass

        with tempfile.TemporaryDirectory() as field_dir:
            app = App()
            evidence = module._current_density_evidence(app, "AutoDxfCopper_DC : LastAdaptive", field_dir, Logger())

        self.assertEqual(evidence["available_quantities"], ["Volume(AutoDxfCopper_PhaseA_L01_Sheet_3)"])
        self.assertIn("CurrentDensity", app.post.export_attempts)
        self.assertEqual(evidence["quantity"], "CurrentDensity")
        self.assertTrue(evidence["field_exported"])
        self.assertEqual(evidence["blocking_issues"], [])

    def test_current_density_evidence_prefers_mag_j_field_plot_export(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")

        class Plot(object):
            name = "AutoDxfCopper_JMagPlot"

        class Post(object):
            def __init__(self):
                self.fieldplot_calls = []
                self.field_exports = []
                self.field_file_attempts = []

            def available_report_quantities(self, **kwargs):
                return ["Volume(AutoDxfCopper_PhaseA_L01_Sheet_4)"]

            def create_fieldplot_volume(self, assignment, quantity, setup, plot_name=None, **kwargs):
                self.fieldplot_calls.append(
                    {
                        "assignment": assignment,
                        "quantity": quantity,
                        "setup": setup,
                        "plot_name": plot_name,
                    }
                )
                return Plot()

            def export_field_plot(self, plot_name, output_dir, file_name="", file_format="aedtplt"):
                self.field_exports.append(
                    {
                        "plot_name": plot_name,
                        "output_dir": output_dir,
                        "file_name": file_name,
                        "file_format": file_format,
                    }
                )
                return os.path.join(output_dir, file_name + "." + file_format)

            def export_field_file(self, **kwargs):
                self.field_file_attempts.append(kwargs["quantity"])
                return False

        class App(object):
            def __init__(self):
                self.post = Post()

        class Logger(object):
            def log(self, message):
                pass

        with tempfile.TemporaryDirectory() as field_dir:
            app = App()
            evidence = module._current_density_evidence(
                app,
                "AutoDxfCopper_DC : LastAdaptive",
                field_dir,
                Logger(),
                object_name="AutoDxfCopper_PhaseA_L01_Sheet_4",
            )

        self.assertEqual(app.post.fieldplot_calls[0]["assignment"], ["AutoDxfCopper_PhaseA_L01_Sheet_4"])
        self.assertEqual(app.post.fieldplot_calls[0]["quantity"], "Mag_J")
        self.assertEqual(app.post.fieldplot_calls[0]["setup"], "AutoDxfCopper_DC : LastAdaptive")
        self.assertEqual(app.post.field_exports[0]["file_format"], "aedtplt")
        self.assertEqual(evidence["method"], "field_plot")
        self.assertEqual(evidence["quantity"], "Mag_J")
        self.assertTrue(evidence["field_export_path"].endswith(".aedtplt"))
        self.assertTrue(evidence["field_exported"])
        self.assertEqual(evidence["blocking_issues"], [])
        self.assertEqual(app.post.field_file_attempts, [])

    def test_centerline_current_density_sample_exports_mag_j_points(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")

        class Post(object):
            def __init__(self):
                self.export_call = None

            def export_field_file(self, **kwargs):
                self.export_call = kwargs
                with open(kwargs["output_file"], "w") as handle:
                    handle.write("Unit=mm\n")
                    for point in kwargs["sample_points"]:
                        handle.write("%s %s %s 2.500000e+08\n" % (point[0], point[1], point[2]))
                return True

        class App(object):
            def __init__(self):
                self.post = Post()

        class Logger(object):
            def log(self, message):
                pass

        with tempfile.TemporaryDirectory() as field_dir:
            app = App()
            evidence = module._centerline_current_density_evidence(
                app,
                "AutoDxfCopper_DC : LastAdaptive",
                field_dir,
                Logger(),
            )

        self.assertTrue(evidence["sample_exported"])
        self.assertTrue(evidence["sample_continuity_checked"])
        self.assertEqual(evidence["quantity"], "Mag_J")
        self.assertEqual(evidence["sample_count"], 13)
        self.assertEqual(evidence["nonzero_sample_count"], 13)
        self.assertGreater(evidence["min_mag_j_a_per_m2"], 0.0)
        self.assertEqual(app.post.export_call["sample_points"], module._centerline_sample_points())
        self.assertEqual(app.post.export_call["export_with_sample_points"], True)

    def test_current_density_evidence_records_field_plot_errors(self):
        module = importlib.import_module("apply_dxf_copper_dc_conduction")

        class Post(object):
            def available_report_quantities(self, **kwargs):
                return []

            def create_fieldplot_volume(self, *args, **kwargs):
                raise RuntimeError("Mag_J is not valid here")

            def export_field_file(self, **kwargs):
                return False

        class App(object):
            post = Post()

        class Logger(object):
            def log(self, message):
                pass

        with tempfile.TemporaryDirectory() as field_dir:
            evidence = module._current_density_evidence(
                App(),
                "AutoDxfCopper_DC : LastAdaptive",
                field_dir,
                Logger(),
                object_name="AutoDxfCopper_PhaseA_L01_Sheet_5",
            )

        self.assertFalse(evidence["field_exported"])
        self.assertIn("field_plot_creation_failed", evidence["blocking_issues"])
        self.assertIn("Mag_J is not valid here", evidence["field_plot_error"])

    def test_dc_launcher_uses_new_v1_script(self):
        launcher_path = os.path.join(ROOT, "launchers", "Queue-ApplyDxfCopperDcConduction.ps1")
        self.assertTrue(os.path.isfile(launcher_path))
        with open(launcher_path, "r") as handle:
            text = handle.read()
        self.assertIn("Queue-Command.ps1", text)
        self.assertIn("scripts/apply_dxf_copper_dc_conduction.py", text)
        self.assertNotIn("apply_sector3d_transient_setup.py", text)

    def test_inspection_summary_reports_v1_object_and_terminal_gate(self):
        module = importlib.import_module("inspect_dxf_copper_mvp")
        build_summary = {
            "dxf_compatible_copper_ready": False,
            "aedt_build": {"object_name": "AutoDxfCopper_PhaseA_L01", "mesh_assigned": True},
            "terminal_faces": [{"role": "source", "face_id": 10}],
        }

        summary = module.build_inspection_summary(build_summary=build_summary)

        self.assertEqual(summary["mvp_object_name"], "AutoDxfCopper_PhaseA_L01")
        self.assertFalse(summary["terminal_faces_present"])
        self.assertFalse(summary["dxf_compatible_copper_ready"])
        self.assertIn("terminal_faces_incomplete", summary["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
