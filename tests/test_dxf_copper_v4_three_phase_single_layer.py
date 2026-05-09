import importlib
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class DxfCopperV4ThreePhaseSingleLayerTests(unittest.TestCase):
    def _module(self):
        return importlib.import_module("dxf_copper_three_phase_single_layer")

    def test_v4_default_spec_declares_three_phase_contract(self):
        spec = self._module().three_phase_default_spec()

        self.assertEqual(spec["milestone"], "Milestone 4: Three-Phase Single-Layer Geometry")
        self.assertEqual(spec["generation_mode"], "three_phase_single_layer")
        self.assertEqual(spec["geometry_scope"], "v4_three_phase_single_layer_2d")
        self.assertEqual(spec["source_generation_mode"], "phase_full_layer")
        self.assertEqual(spec["source_geometry_scope"], "v35_phase_a_full_layer_2d")
        self.assertEqual(spec["phase_offsets_deg"], {"A": 0.0, "B": 120.0, "C": 240.0})
        self.assertEqual(spec["phase_offset_angle_units"], "electrical_degrees")
        self.assertEqual(spec["pole_pairs_count"], 7)
        self.assertEqual(spec["trace_gap_mm"], 1.0)
        self.assertEqual(spec["minimum_phase_to_phase_clearance_mm"], 1.0)
        self.assertEqual(spec["macro_segment_count"], 6)
        self.assertEqual(spec["macro_guard_angle_deg"], 3.0)
        self.assertEqual(spec["radial_lane_count"], 4)
        self.assertEqual(spec["turn_count_per_macro_segment"], 4)
        self.assertEqual(spec["radial_wave_min_traverses_per_region"], 2)
        self.assertEqual(spec["terminal_keepout_radius_mm"], 0.75)

    def test_v4_converts_electrical_offsets_to_mechanical_rotation(self):
        module = self._module()
        spec = module.three_phase_default_spec()
        spec["pole_pairs_count"] = 8
        spec["phase_offsets_deg"] = {"A": 0.0, "B": 120.0, "C": 240.0}

        normalized = module.normalize_three_phase_spec(spec)

        self.assertEqual(
            normalized["mechanical_phase_offsets_deg"],
            {"A": 0.0, "B": 15.0, "C": 30.0},
        )

    def test_v4_rejects_invalid_pole_pairs_count(self):
        module = self._module()
        for invalid_value in [0, -1, 1.5, "7"]:
            spec = module.three_phase_default_spec()
            spec["pole_pairs_count"] = invalid_value
            with self.subTest(pole_pairs_count=invalid_value):
                with self.assertRaisesRegex(ValueError, "pole_pairs_count must be a positive integer"):
                    module.normalize_three_phase_spec(spec)

    def test_v4_generates_b_c_by_rotating_phase_a_regions(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 6})

        self.assertEqual(geometry["phase_offset_angle_units"], "electrical_degrees")
        self.assertEqual(geometry["mechanical_phase_offsets_deg"]["B"], 20.0)
        self.assertEqual(geometry["mechanical_phase_offsets_deg"]["C"], 40.0)
        self.assertEqual(geometry["phase_order"], ["A", "B", "C"])
        self.assertEqual(
            len(geometry["phases"]["A"]["full_layer_regions"]),
            len(geometry["phases"]["B"]["full_layer_regions"]),
        )
        self.assertEqual(
            len(geometry["phases"]["A"]["full_layer_regions"][0]["outline_points_xy_mm"]),
            len(geometry["phases"]["B"]["full_layer_regions"][0]["outline_points_xy_mm"]),
        )
        self.assertEqual(geometry["phases"]["B"]["full_layer_regions"][0]["source_phase"], "A")
        self.assertEqual(geometry["phases"]["B"]["full_layer_regions"][0]["mechanical_rotation_deg"], 20.0)
        self.assertNotEqual(
            geometry["phases"]["A"]["full_layer_regions"][0]["terminal_pads"][0]["center_xy_mm"],
            geometry["phases"]["B"]["full_layer_regions"][0]["terminal_pads"][0]["center_xy_mm"],
        )

    def test_v4_preserves_xyz_points_with_zero_z_for_v5_handoff(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 6})

        for phase in ["A", "B", "C"]:
            phase_geometry = geometry["phases"][phase]
            self.assertIn("full_layer_outline_groups_xyz_mm", phase_geometry)
            self.assertIn("full_layer_centerline_points_xyz_mm", phase_geometry)
            self.assertIn("full_layer_aedt_polyline_regions_mm", phase_geometry)
            for group in phase_geometry["full_layer_outline_groups_xyz_mm"]:
                for point in group:
                    self.assertEqual(len(point), 3)
                    self.assertEqual(point[2], 0.0)
            for group in phase_geometry["full_layer_aedt_polyline_regions_mm"]:
                for point in group:
                    self.assertEqual(len(point), 3)
                    self.assertEqual(point[2], 0.0)
            for point in phase_geometry["full_layer_centerline_points_xyz_mm"]:
                self.assertEqual(len(point), 3)
                self.assertEqual(point[2], 0.0)
            for region in phase_geometry["full_layer_regions"]:
                for point in region["aedt_polyline_points_mm"]:
                    self.assertEqual(len(point), 3)
                    self.assertEqual(point[2], 0.0)

    def test_v4_passes_when_source_passes_and_overlap_area_is_calculated(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 12})
        status = module.validate_three_phase_single_layer_geometry(geometry)

        self.assertIn("phase_pair_metrics", geometry)
        self.assertEqual(set(geometry["phase_pair_metrics"]), {"A_B", "B_C", "C_A"})
        for pair in ["A_B", "B_C", "C_A"]:
            self.assertIn("minimum_clearance_mm", geometry["phase_pair_metrics"][pair])
            self.assertIn("overlap_area_mm2", geometry["phase_pair_metrics"][pair])
        self.assertIn("phase_to_phase_minimum_clearance_mm", geometry["metrics"])
        self.assertIn("phase_pair_overlap_area_mm2", geometry["metrics"])
        self.assertIs(status["source_passed"], True)
        self.assertIs(status["overlap_area_calculated"], True)
        self.assertIs(status["v4_passed"], True)
        self.assertIs(status["same_plane_feasibility_passed"], False)
        self.assertGreater(len(status["same_plane_issues"]), 0)
        self.assertEqual(status["blocking_issues"], [])

    def test_v4_records_same_plane_overlap_as_diagnostic_not_blocking_issue(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry(
            {
                "pole_pairs_count": 1,
                "phase_offsets_deg": {"A": 0.0, "B": 0.0, "C": 240.0},
            }
        )
        status = module.validate_three_phase_single_layer_geometry(geometry)

        self.assertIs(status["v4_passed"], True)
        self.assertIs(status["same_plane_feasibility_passed"], False)
        self.assertIn("phase_pair_overlap_detected:A_B", status["same_plane_issues"])
        self.assertNotIn("phase_pair_overlap_detected:A_B", status["blocking_issues"])

    def test_v4_all_phases_remain_radial_wave_valid(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 12})
        status = module.validate_three_phase_single_layer_geometry(geometry)

        for phase in ["A", "B", "C"]:
            metrics = geometry["phases"][phase]["metrics"]
            self.assertIn("copper_area_mm2", metrics)
            self.assertIn("centerline_length_mm", metrics)
            self.assertIn("bounding_diameter_mm", metrics)
            self.assertIn("radial_wave_score", metrics)
            self.assertIn("radial_wave_radial_dominant_length_mm", metrics)
            self.assertIn("radial_wave_circumferential_dominant_length_mm", metrics)
            self.assertIn("radial_wave_radial_dominant_traverses_by_region", metrics)
            self.assertGreater(
                metrics["radial_wave_radial_dominant_length_mm"],
                metrics["radial_wave_circumferential_dominant_length_mm"],
            )
            self.assertTrue(
                all(
                    count >= geometry["spec_summary"]["radial_wave_min_traverses_per_region"]
                    for count in metrics["radial_wave_radial_dominant_traverses_by_region"]
                )
            )
        self.assertIs(status["v4_passed"], True)
        self.assertEqual(status["blocking_issues"], [])

    def test_v4_exports_v5_spatial_handoff_scaffold(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 12})
        status = module.validate_three_phase_single_layer_geometry(geometry)

        self.assertIn("v5_spatial_handoff", geometry)
        handoff = geometry["v5_spatial_handoff"]
        self.assertEqual(handoff["recommended_layer_sequence"], ["A", "B", "C", "C", "B", "A"])
        self.assertEqual(
            [layer["phase"] for layer in handoff["layer_instances"]],
            ["A", "B", "C", "C", "B", "A"],
        )
        self.assertEqual(
            [layer["layer_id"] for layer in handoff["layer_instances"]],
            ["L01", "L02", "L03", "L04", "L05", "L06"],
        )
        self.assertTrue(all(layer["z_mm"] is None for layer in handoff["layer_instances"]))
        self.assertEqual(handoff["z_assignment_policy"], "reserved_for_v5")
        self.assertIs(handoff["interlayer_insulation_evaluated"], False)
        self.assertIs(handoff["vias_or_physical_bridges_evaluated"], False)
        self.assertIs(status["v5_spatial_handoff_ready"], True)
        self.assertIs(status["v4_passed"], True)

    def test_v4_terminal_keepouts_are_feasibility_checks_not_escape_geometry(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 12})
        module.validate_three_phase_single_layer_geometry(geometry)

        self.assertIn("terminal_keepout_conflicts", geometry)
        self.assertNotIn("terminal_escape_routes", geometry)
        self.assertNotIn("physical_bridges", geometry)
        self.assertIs(geometry["not_evaluated"]["physical_bridge_evaluated"], False)
        self.assertIs(geometry["not_evaluated"]["physical_terminal_escape_evaluated"], False)

    def test_v4_svg_draws_terminal_keepout_markers(self):
        module = self._module()

        geometry = module.build_three_phase_single_layer_geometry({"pole_pairs_count": 12})

        with tempfile.TemporaryDirectory() as tmpdir:
            svg_path = os.path.join(tmpdir, "three_phase.svg")
            module.write_three_phase_svg(geometry, svg_path)

            self.assertTrue(os.path.exists(svg_path))
            with open(svg_path, "r", encoding="utf-8") as handle:
                svg = handle.read()
        self.assertIn("stroke-dasharray", svg)
        self.assertIn("#dc2626", svg)
        self.assertIn("terminal-keepout", svg)

    def test_v4_writer_exports_json_markdown_svg(self):
        writer = importlib.import_module("build_dxf_copper_v4_three_phase_single_layer")

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = writer.build_report_artifacts(root=tmpdir)

            self.assertTrue(os.path.exists(artifacts["json"]))
            self.assertTrue(os.path.exists(artifacts["md"]))
            self.assertTrue(os.path.exists(artifacts["svg"]))
            self.assertTrue(artifacts["v4_passed"])

            with open(artifacts["md"], "r", encoding="utf-8") as handle:
                report = handle.read()
        self.assertIn("Milestone 4", report)
        self.assertIn("v4_passed", report)
        self.assertIn("source_passed", report)
        self.assertIn("overlap_area_calculated", report)
        self.assertIn("same-plane", report.lower())
        self.assertIn("electrical", report.lower())
        self.assertIn("mechanical", report.lower())
        self.assertIn("pole_pairs_count", report)
        self.assertIn("v5_spatial_handoff_ready", report)
        self.assertIn("terminal keepout", report.lower())


if __name__ == "__main__":
    unittest.main()
