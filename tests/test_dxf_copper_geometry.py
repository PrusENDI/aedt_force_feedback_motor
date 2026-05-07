import importlib
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class DxfCopperGeometryContractTests(unittest.TestCase):
    def load_module(self):
        try:
            return importlib.import_module("dxf_copper_geometry")
        except ModuleNotFoundError as exc:
            self.fail("scripts/dxf_copper_geometry.py is required for V1 copper geometry: %s" % exc)

    def test_default_v1_geometry_identity_and_thickness(self):
        module = self.load_module()
        geometry = module.build_v1_phase_a_geometry()

        self.assertEqual(geometry["phase"], "A")
        self.assertEqual(geometry["layer"], "L01")
        self.assertAlmostEqual(geometry["copper_thickness_mm"], 0.3)

    def test_validation_status_exposes_manufacturing_contract_fields(self):
        module = self.load_module()
        geometry = module.build_v1_phase_a_geometry()
        status = module.validate_v1_geometry(geometry)

        for key in (
            "closed",
            "valid",
            "bounding_diameter_mm",
            "terminal_count",
            "minimum_clearance_mm",
        ):
            self.assertIn(key, status)
        self.assertTrue(status["closed"])
        self.assertTrue(status["valid"])
        self.assertEqual(status["terminal_count"], 2)
        self.assertGreater(status["minimum_clearance_mm"], 0.0)
        self.assertLessEqual(status["bounding_diameter_mm"], 100.0)

    def test_geometry_declares_explicit_aedt_handshake_mode(self):
        module = self.load_module()
        spec = module.v1_default_spec()
        geometry = module.build_v1_phase_a_geometry(spec)

        self.assertIn(geometry["aedt_handshake_mode"], ("polyline_points", "import_dxf"))

    def test_v1_contract_does_not_expose_phase_belt_envelope(self):
        module = self.load_module()
        spec = module.v1_default_spec()
        geometry = module.build_v1_phase_a_geometry(spec)
        status = module.validate_v1_geometry(geometry)

        self.assertNotIn("phase_belt_envelope", spec)
        self.assertNotIn("phase_belt_envelope", geometry)
        self.assertNotIn("phase_belt_envelope", status)


class DxfCopperV2GeometryContractTests(unittest.TestCase):
    def load_module(self):
        try:
            return importlib.import_module("dxf_copper_geometry")
        except ModuleNotFoundError as exc:
            self.fail("scripts/dxf_copper_geometry.py is required for V2 copper geometry: %s" % exc)

    def test_v2_default_spec_targets_single_layer_geometry_chain(self):
        module = self.load_module()

        spec = module.v2_default_spec()

        self.assertEqual(spec["milestone"], "Milestone 3: Repeatable Single-Layer Geometry Generator")
        self.assertEqual(spec["geometry_contract_version"], "dxf-copper-v2")
        self.assertEqual(spec["topology_preset"], "representative_single_layer_chain")
        self.assertEqual(spec["geometry_scope"], "v2_single_layer_phase_a_representative_segment")
        self.assertFalse(spec["full_phase_winding_enabled"])
        self.assertEqual(spec["phase"], "A")
        self.assertEqual(spec["layer"], "L01")
        self.assertFalse(spec["three_phase_enabled"])
        self.assertFalse(spec["six_layer_stack_enabled"])
        self.assertEqual(spec["terminal_pad_width_mm"], 5.0)
        self.assertEqual(spec["terminal_pad_height_mm"], 5.0)

    def test_v2_motor_intent_is_separate_from_geometry_output(self):
        module = self.load_module()

        intent = module.build_single_layer_motor_intent(module.v2_default_spec())

        self.assertEqual(intent["phase"], "A")
        self.assertEqual(intent["layer"], "L01")
        self.assertIn("radii_mm", intent)
        self.assertIn("angles_deg", intent)
        self.assertIn("path_config", intent)
        self.assertIn("terminal_config", intent)
        self.assertNotIn("outline_points_xy_mm", intent)
        self.assertNotIn("aedt_polyline_points_mm", intent)

    def test_centerline_uses_polar_points_and_records_sampling_policy(self):
        module = self.load_module()
        geometry = module.build_single_layer_geometry()

        self.assertIn("centerline_points_xy_mm", geometry)
        self.assertEqual(geometry["metadata"]["arc_segment_deg"], 2.0)
        self.assertGreater(len(geometry["centerline_points_xy_mm"]), 6)
        self.assertLess(len(geometry["centerline_points_xy_mm"]), 120)

    def test_arc_sampling_step_changes_centerline_density_in_bounded_way(self):
        module = self.load_module()
        coarse_spec = module.v2_default_spec()
        fine_spec = module.v2_default_spec()
        coarse_spec["arc_segment_deg"] = 4.0
        fine_spec["arc_segment_deg"] = 1.0

        coarse = module.build_single_layer_geometry(coarse_spec)
        fine = module.build_single_layer_geometry(fine_spec)

        self.assertLess(len(coarse["centerline_points_xy_mm"]), len(fine["centerline_points_xy_mm"]))
        self.assertLess(len(fine["centerline_points_xy_mm"]), fine_spec["max_arc_segment_count"])
        self.assertEqual(fine["metadata"]["arc_segment_deg"], 1.0)

    def test_arc_sampling_rejects_nonpositive_max_segment_count(self):
        module = self.load_module()
        spec = module.v2_default_spec()
        spec["max_arc_segment_count"] = 0

        with self.assertRaisesRegex(ValueError, "max_arc_segment_count"):
            module.build_single_layer_geometry(spec)

    def test_arc_sampling_zero_and_negative_steps_are_safe(self):
        module = self.load_module()
        zero_spec = module.v2_default_spec()
        negative_spec = module.v2_default_spec()
        positive_spec = module.v2_default_spec()
        zero_spec["arc_segment_deg"] = 0.0
        negative_spec["arc_segment_deg"] = -2.0
        positive_spec["arc_segment_deg"] = 2.0

        zero = module.build_single_layer_geometry(zero_spec)
        negative = module.build_single_layer_geometry(negative_spec)
        positive = module.build_single_layer_geometry(positive_spec)

        self.assertGreater(len(zero["centerline_points_xy_mm"]), 0)
        self.assertGreater(len(negative["centerline_points_xy_mm"]), 0)
        self.assertEqual(
            len(negative["centerline_points_xy_mm"]),
            len(positive["centerline_points_xy_mm"]),
        )

    def test_arc_sampling_preserves_endpoints_and_segment_cap(self):
        module = self.load_module()

        points = module._sample_arc_points(10, 0, 10, 2, 3)

        self.assertEqual(len(points), 4)
        self.assertAlmostEqual(points[0][0], 10.0)
        self.assertAlmostEqual(points[0][1], 0.0)
        expected_end = module.polar_point(10, 10)
        self.assertAlmostEqual(points[-1][0], expected_end[0])
        self.assertAlmostEqual(points[-1][1], expected_end[1])

    def test_v2_geometry_exposes_outline_terminals_and_aedt_points(self):
        module = self.load_module()
        geometry = module.build_single_layer_geometry()

        self.assertGreater(len(geometry["outline_points_xy_mm"]), 4)
        self.assertGreater(len(geometry["aedt_polyline_points_mm"]), 3)
        self.assertEqual(len(geometry["terminal_pads"]), 2)
        self.assertEqual(len(geometry["terminals"]), 2)
        self.assertEqual(geometry["metadata"]["corner_policy"], "flat_caps_mitred_joins_no_auto_rounding")
        self.assertEqual(geometry["metadata"]["topology_preset"], "representative_single_layer_chain")
        self.assertEqual(geometry["metadata"]["geometry_scope"], "v2_single_layer_phase_a_representative_segment")
        self.assertFalse(geometry["metadata"]["full_phase_winding_enabled"])
        self.assertEqual(
            geometry["metadata"]["terminal_pad_role"],
            "source_sink_test_contact_not_final_terminal_shape",
        )
        self.assertEqual(geometry["terminal_pads"][0]["size_xy_mm"], [5.0, 5.0])
        self.assertEqual(
            geometry["terminal_pads"][0]["role_detail"],
            "source_sink_test_contact_not_final_terminal_shape",
        )

    def test_v2_geometry_reports_diagnostics_for_path_review(self):
        module = self.load_module()
        geometry = module.build_single_layer_geometry()
        diagnostics = geometry["diagnostics"]

        self.assertGreater(diagnostics["centerline_length_mm"], 0.0)
        self.assertEqual(diagnostics["centerline_point_count"], len(geometry["centerline_points_xy_mm"]))
        self.assertEqual(diagnostics["outline_point_count"], len(geometry["outline_points_xy_mm"]))
        self.assertEqual(diagnostics["terminal_pad_size_xy_mm"], [5.0, 5.0])
        self.assertEqual(diagnostics["arc_sampling_policy"], "bounded_polyline_arc_approximation")
        self.assertGreater(diagnostics["actual_arc_segment_count"], 0)
        self.assertGreater(diagnostics["angular_span_deg"], 0.0)
        self.assertGreater(diagnostics["radial_max_mm"], diagnostics["radial_min_mm"])

    def test_v2_outline_rejects_automatic_rounded_corner_policy(self):
        module = self.load_module()
        geometry = module.build_single_layer_geometry()

        self.assertEqual(geometry["metadata"]["buffer_cap_style"], "flat")
        self.assertEqual(geometry["metadata"]["buffer_join_style"], "mitre")
        self.assertNotEqual(geometry["metadata"]["buffer_join_style"], "round")

    def test_v2_outline_fails_when_intent_uses_rounded_corner_policy(self):
        module = self.load_module()
        intent = module.build_single_layer_motor_intent()
        centerline = module.build_centerline_path(intent)
        intent["path_config"]["corner_policy"] = "round"

        with self.assertRaisesRegex(ValueError, "corner policy"):
            module._build_outline_polygon(centerline, intent)

    def test_v2_outline_fails_fast_for_disconnected_union(self):
        module = self.load_module()
        intent = module.build_single_layer_motor_intent()
        centerline = module.build_centerline_path(intent)
        original_terminal_pad_polygons = module._terminal_pad_polygons

        def disconnected_terminal_pad_polygons(_centerline, _intent):
            return [
                {
                    "name": "DisconnectedPad",
                    "role": "source",
                    "center_xy_mm": [1000.0, 1000.0],
                    "size_xy_mm": [1.0, 1.0],
                    "polygon": module._box_from_center(1000.0, 1000.0, 1.0, 1.0),
                }
            ]

        module._terminal_pad_polygons = disconnected_terminal_pad_polygons
        try:
            with self.assertRaisesRegex(ValueError, "one connected polygon.*MultiPolygon"):
                module._build_outline_polygon(centerline, intent)
        finally:
            module._terminal_pad_polygons = original_terminal_pad_polygons

    def test_v2_validation_reports_geometry_chain_checks(self):
        module = self.load_module()
        geometry = module.build_single_layer_geometry()
        status = module.validate_single_layer_geometry(geometry)

        for key in (
            "closed",
            "valid",
            "self_intersection_free",
            "area_mm2",
            "bounding_diameter_mm",
            "minimum_width_mm",
            "minimum_clearance_mm",
            "actual_width_mm",
            "actual_clearance_mm",
            "terminal_count",
            "issues",
        ):
            self.assertIn(key, status)
        self.assertTrue(status["closed"])
        self.assertTrue(status["valid"])
        self.assertTrue(status["self_intersection_free"])
        self.assertEqual(status["terminal_count"], 2)
        self.assertLessEqual(status["bounding_diameter_mm"], 100.0)

    def test_v2_validation_blocks_trace_width_below_declared_minimum(self):
        module = self.load_module()
        spec = module.v2_default_spec()
        spec["trace_width_mm"] = 3.0
        geometry = module.build_single_layer_geometry(spec)
        geometry["manufacturing_constraints"]["minimum_copper_width_mm"] = 4.0

        status = module.validate_single_layer_geometry(geometry)

        self.assertFalse(status["valid"])
        self.assertIn("minimum_copper_width_violation", status["issues"])
        self.assertEqual(status["actual_width_mm"], 3.0)

    def test_v2_validation_blocks_trace_gap_below_declared_minimum(self):
        module = self.load_module()
        spec = module.v2_default_spec()
        spec["trace_gap_mm"] = 0.4
        geometry = module.build_single_layer_geometry(spec)
        geometry["manufacturing_constraints"]["minimum_clearance_mm"] = 1.0

        status = module.validate_single_layer_geometry(geometry)

        self.assertFalse(status["valid"])
        self.assertIn("minimum_clearance_violation", status["issues"])
        self.assertEqual(status["actual_clearance_mm"], 0.4)

    def test_v2_invalid_parameters_fail_fast_before_geometry_creation(self):
        module = self.load_module()

        invalid_specs = [
            ("turn_count", 0, "turn_count"),
            ("slot_pitch_deg", 0.0, "slot_pitch_deg"),
            ("trace_width_mm", 0.0, "trace_width_mm"),
            ("terminal_pad_width_mm", 0.0, "terminal_pad_width_mm"),
        ]
        for key, value, pattern in invalid_specs:
            spec = module.v2_default_spec()
            spec[key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, pattern):
                    module.build_single_layer_geometry(spec)

    def test_v2_invalid_radius_window_fails_fast(self):
        module = self.load_module()
        spec = module.v2_default_spec()
        spec["inner_radius_mm"] = 30.0
        spec["outer_radius_mm"] = 31.0
        spec["trace_width_mm"] = 4.0

        with self.assertRaisesRegex(ValueError, "radius window"):
            module.build_single_layer_geometry(spec)

    def test_parameter_changes_modify_real_geometry_not_only_metadata(self):
        module = self.load_module()
        base_spec = module.v2_default_spec()
        variant_spec = module.v2_default_spec()
        variant_spec["turn_count"] = base_spec["turn_count"] + 1
        variant_spec["slot_pitch_deg"] = base_spec["slot_pitch_deg"] + 1.5
        variant_spec["centerline_radius_mm"] = base_spec["centerline_radius_mm"] + 1.0

        base = module.build_single_layer_geometry(base_spec)
        variant = module.build_single_layer_geometry(variant_spec)

        self.assertNotEqual(base["centerline_points_xy_mm"], variant["centerline_points_xy_mm"])
        self.assertNotEqual(base["outline_points_xy_mm"], variant["outline_points_xy_mm"])
        self.assertNotEqual(base["aedt_polyline_points_mm"], variant["aedt_polyline_points_mm"])

    def test_v2_estimates_are_marked_non_final(self):
        module = self.load_module()
        geometry = module.build_single_layer_geometry()

        self.assertIn("estimates", geometry)
        self.assertGreater(geometry["estimates"]["path_length_mm"], 0.0)
        self.assertGreater(geometry["estimates"]["area_mm2"], 0.0)
        self.assertEqual(
            geometry["estimates"]["policy"],
            "geometry_derived_estimate_not_final_validation",
        )
        self.assertIn("systematic_error_sources", geometry["estimates"])

    def test_optional_dxf_preview_missing_dependency_is_non_blocking(self):
        module = self.load_module()
        result = module.export_single_layer_dxf_preview(
            module.build_single_layer_geometry(),
            "dxf_copper_v2_phase_a_l01_preview.dxf",
        )

        self.assertIn(result["status"], ("exported", "dependency_missing", "disabled"))
        self.assertFalse(result["blocking"])


if __name__ == "__main__":
    unittest.main()
