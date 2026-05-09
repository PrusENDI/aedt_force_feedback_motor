import importlib
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class DxfCopperV35PhaseFullLayerTests(unittest.TestCase):
    def _module(self):
        return importlib.import_module("dxf_copper_phase_chain")

    def _v2_module(self):
        return importlib.import_module("dxf_copper_geometry")

    def _default_spec(self, **overrides):
        spec = self._module().phase_chain_default_spec()
        spec.update(overrides)
        return spec

    def _build(self, **overrides):
        return self._module().build_phase_chain_geometry(self._default_spec(**overrides))

    def _validate(self, geometry):
        return self._module().validate_phase_chain_geometry(geometry)

    def _require_keys(self, mapping, keys):
        for key in keys:
            if key not in mapping:
                self.fail("missing expected key %r; present keys: %s" % (key, sorted(mapping.keys())))

    def test_phase_full_layer_default_spec_declares_v35_contract(self):
        spec = self._module().phase_chain_default_spec()

        self.assertEqual(spec["milestone"], "Milestone 3.5: Phase A Full-Layer Geometry Precursor")
        self.assertEqual(spec["geometry_contract_version"], "dxf-copper-v2")
        self.assertEqual(spec["generation_mode"], "phase_full_layer")
        self.assertEqual(spec["topology_preset"], "phase_a_full_layer_v2_constrained_segment")
        self.assertEqual(spec["geometry_scope"], "v35_phase_a_full_layer_2d")
        self.assertEqual(spec["phase"], "A")
        self.assertEqual(spec["layer"], "L01")
        self.assertEqual(spec["macro_segment_count"], 6)
        self.assertEqual(spec["macro_segment_pitch_deg"], 60.0)
        self.assertEqual(spec["full_layer_coverage_deg"], 360.0)
        self.assertGreaterEqual(spec["turn_count_per_macro_segment"], 4)
        self.assertGreaterEqual(spec["radial_lane_count"], 3)
        for key in [
            "minimum_radial_fill_ratio",
            "minimum_angular_occupancy_ratio",
            "minimum_centerline_length_mm",
            "minimum_copper_area_mm2",
            "minimum_bounding_diameter_mm",
        ]:
            self.assertIn(key, spec)
        self.assertFalse(spec["three_phase_enabled"])
        self.assertFalse(spec["six_layer_stack_enabled"])

    def test_phase_full_layer_outputs_grouped_regions_not_single_outline(self):
        geometry = self._build()
        status = self._validate(geometry)

        self._require_keys(
            geometry,
            [
                "full_layer_regions",
                "full_layer_outline_groups_xy_mm",
                "full_layer_aedt_polyline_regions_mm",
                "full_layer_centerline_points_xy_mm",
                "logical_connection_policy",
            ],
        )
        self._require_keys(
            status,
            ["full_layer_coverage_valid", "full_layer_self_overlap_free", "segment_overlap_free"],
        )
        self.assertEqual(len(geometry["full_layer_regions"]), 6)
        self.assertEqual(len(geometry["full_layer_outline_groups_xy_mm"]), 6)
        self.assertEqual(len(geometry["full_layer_aedt_polyline_regions_mm"]), 6)
        self.assertEqual(len(geometry["full_layer_centerline_points_xy_mm"]), 6)
        self.assertNotIn("full_layer_outline_points_xy_mm", geometry)
        self.assertNotIn("full_layer_aedt_polyline_points_mm", geometry)
        for group in geometry["full_layer_outline_groups_xy_mm"]:
            self.assertGreaterEqual(len(group), 8)
        for centerline in geometry["full_layer_centerline_points_xy_mm"]:
            self.assertGreaterEqual(len(centerline), 10)
        self.assertEqual(geometry["diagnostics"]["full_layer_coverage_deg"], 360.0)
        self.assertTrue(status["valid"])
        self.assertTrue(status["full_layer_coverage_valid"])
        self.assertTrue(status["full_layer_self_overlap_free"])
        self.assertTrue(status["segment_overlap_free"])
        self.assertEqual(geometry["logical_connection_policy"], "ordered_segments_with_physical_gap")

    def test_sparse_smoke_primitive_fails_radial_fill_and_centerline_thresholds(self):
        geometry = self._build(turn_count_per_macro_segment=1, radial_lane_count=1)
        status = self._validate(geometry)

        self.assertFalse(status["valid"])
        self.assertIn("radial_fill_ratio_too_low", status["issues"])
        self.assertIn("centerline_length_too_short", status["issues"])

    def test_unconstrained_v2_repetition_fails_overlap_or_clearance(self):
        geometry = self._build(segment_primitive_mode="unconstrained_v2_repetition")
        status = self._validate(geometry)

        self.assertFalse(status["valid"])
        self.assertTrue(
            any("overlap" in issue or "clearance" in issue for issue in status["issues"]),
            status["issues"],
        )

    def test_constrained_segments_keep_v2_style_fields_and_validate_as_v2(self):
        v2_module = self._v2_module()
        geometry = self._build()

        self._require_keys(geometry, ["segment_primitive_mode", "full_layer_regions"])
        self.assertEqual(geometry["segment_primitive_mode"], "constrained_v2_segment")
        for segment in geometry["full_layer_regions"]:
            self.assertEqual(segment["geometry_contract_version"], "dxf-copper-v2")
            self.assertEqual(segment["generation_mode"], "phase_full_layer")
            self.assertRegex(segment["segment_id"], r"^A_L01_M\d\d$")
            self.assertIn("centerline_points_xy_mm", segment)
            self.assertIn("outline_points_xy_mm", segment)
            self.assertIn("aedt_polyline_points_mm", segment)
            self.assertIn("terminal_pads", segment)
            self.assertIn("terminals", segment)
            self.assertIn("metadata", segment)
            self.assertIn("diagnostics", segment)
            self.assertTrue(v2_module.validate_single_layer_geometry(segment)["valid"])

    def test_logical_connections_link_adjacent_segments_with_physical_gaps(self):
        geometry = self._build()
        self._require_keys(geometry, ["metadata", "validation"])
        self._require_keys(geometry["metadata"], ["logical_connections", "trace_gap_mm"])
        connections = geometry["metadata"]["logical_connections"]

        self.assertEqual(len(connections), 5)
        for index, connection in enumerate(connections):
            self.assertEqual(connection["entry_from"], "A_L01_M%02d" % (index + 1))
            self.assertEqual(connection["exit_to"], "A_L01_M%02d" % (index + 2))
            self.assertEqual(connection["connection_type"], "logical_only_physical_gap")
            self.assertGreaterEqual(connection["minimum_clearance_mm"], geometry["metadata"]["trace_gap_mm"])
        self.assertGreaterEqual(
            geometry["validation"]["minimum_segment_clearance_mm"],
            geometry["metadata"]["trace_gap_mm"],
        )

    def test_default_full_layer_centerlines_are_radial_wave_dominant(self):
        geometry = self._build()
        status = self._validate(geometry)

        self._require_keys(
            geometry,
            ["diagnostics", "full_layer_regions", "full_layer_centerline_points_xy_mm", "spec_summary"],
        )
        self.assertEqual(
            [region["centerline_points_xy_mm"] for region in geometry["full_layer_regions"]],
            geometry["full_layer_centerline_points_xy_mm"],
        )

        radial_dominant_length_mm = 0.0
        circumferential_dominant_length_mm = 0.0
        radial_dominant_traverses_by_segment = []
        dominance_ratio = 1.5

        for centerline in geometry["full_layer_centerline_points_xy_mm"]:
            segment_radial_dominant_traverses = 0
            for start, end in zip(centerline, centerline[1:]):
                start_radius = math.hypot(start[0], start[1])
                end_radius = math.hypot(end[0], end[1])
                average_radius = (start_radius + end_radius) / 2.0
                delta_radius = abs(end_radius - start_radius)
                delta_theta = math.atan2(end[1], end[0]) - math.atan2(start[1], start[0])
                while delta_theta > math.pi:
                    delta_theta -= 2.0 * math.pi
                while delta_theta < -math.pi:
                    delta_theta += 2.0 * math.pi
                arc_equivalent_mm = average_radius * abs(delta_theta)
                segment_length_mm = math.hypot(end[0] - start[0], end[1] - start[1])

                if delta_radius > dominance_ratio * arc_equivalent_mm:
                    radial_dominant_length_mm += segment_length_mm
                    segment_radial_dominant_traverses += 1
                elif arc_equivalent_mm > dominance_ratio * delta_radius:
                    circumferential_dominant_length_mm += segment_length_mm

            radial_dominant_traverses_by_segment.append(segment_radial_dominant_traverses)

        self.assertGreater(
            radial_dominant_length_mm,
            circumferential_dominant_length_mm,
            "default full-layer should spend more centerline length on radial-wave traverses than circular arcs",
        )
        for segment_index, radial_traverses in enumerate(radial_dominant_traverses_by_segment):
            self.assertGreaterEqual(
                radial_traverses,
                2,
                "macro segment %d should include several radial-dominant traverses, not just a long arc"
                % (segment_index + 1),
            )

        self._require_keys(
            geometry["diagnostics"],
            [
                "radial_wave_radial_dominant_length_mm",
                "radial_wave_circumferential_dominant_length_mm",
                "radial_wave_radial_dominant_traverses_by_segment",
            ],
        )
        self._require_keys(
            status,
            [
                "radial_wave_radial_dominant_length_mm",
                "radial_wave_circumferential_dominant_length_mm",
                "radial_wave_radial_dominant_traverses_by_segment",
            ],
        )

    def test_physical_bridge_fields_are_absent_and_not_evaluated(self):
        geometry = self._build()

        self.assertNotIn("physical_bridges", geometry)
        self.assertNotIn("bridge_polylines_xy_mm", geometry)
        self.assertFalse(geometry["not_evaluated"]["physical_bridge_evaluated"])

    def test_terminal_keepout_policy_and_keepouts_are_recorded_in_metadata(self):
        geometry = self._build()

        self._require_keys(geometry, ["metadata"])
        metadata = geometry["metadata"]
        self._require_keys(metadata, ["terminal_keepout_policy", "terminal_keepouts"])
        self.assertEqual(metadata["terminal_keepout_policy"], "reserve_only_no_terminal_escape")
        self.assertIn("terminal_keepouts", metadata)
        self.assertGreaterEqual(len(metadata["terminal_keepouts"]), 2)
        for keepout in metadata["terminal_keepouts"]:
            self.assertIn("center_xy_mm", keepout)
            self.assertIn("size_xy_mm", keepout)
            self.assertEqual(keepout["evaluation_status"], "reserved_not_routed")

    def test_parameter_changes_modify_geometry_diagnostics_and_spec_summary(self):
        base = self._build()
        variant = self._build(
            turn_count_per_macro_segment=5,
            radial_lane_count=4,
            trace_gap_mm=1.25,
            arc_segment_deg=1.0,
        )

        self._require_keys(
            base,
            ["full_layer_centerline_points_xy_mm", "full_layer_outline_groups_xy_mm", "diagnostics"],
        )
        self._require_keys(
            variant,
            [
                "full_layer_centerline_points_xy_mm",
                "full_layer_outline_groups_xy_mm",
                "diagnostics",
                "spec_summary",
            ],
        )
        self.assertNotEqual(
            base["full_layer_centerline_points_xy_mm"],
            variant["full_layer_centerline_points_xy_mm"],
        )
        self.assertNotEqual(
            base["full_layer_outline_groups_xy_mm"],
            variant["full_layer_outline_groups_xy_mm"],
        )
        self.assertNotEqual(base["diagnostics"], variant["diagnostics"])
        self.assertEqual(variant["spec_summary"]["turn_count_per_macro_segment"], 5)
        self.assertEqual(variant["spec_summary"]["radial_lane_count"], 4)
        self.assertEqual(variant["spec_summary"]["trace_gap_mm"], 1.25)
        self.assertEqual(variant["spec_summary"]["arc_segment_deg"], 1.0)

    def test_fail_fast_rejects_inconsistent_macro_count_pitch_and_bad_radius_window(self):
        with self.assertRaises(ValueError):
            self._build(macro_segment_count=6, macro_segment_pitch_deg=45.0)

        with self.assertRaises(ValueError):
            self._build(inner_radius_mm=30.0, outer_radius_mm=31.0, trace_width_mm=4.0)

    def test_fail_fast_derives_macro_count_from_pitch_45(self):
        spec = self._module().phase_chain_default_spec()
        del spec["macro_segment_count"]
        spec["macro_segment_pitch_deg"] = 45.0
        geometry = self._module().build_phase_chain_geometry(spec)

        self._require_keys(geometry, ["macro_segment_count", "full_layer_regions", "diagnostics"])
        self.assertEqual(geometry["macro_segment_count"], 8)
        self.assertEqual(len(geometry["full_layer_regions"]), 8)
        self.assertEqual(geometry["diagnostics"]["full_layer_coverage_deg"], 360.0)

    def test_artifact_writer_exports_json_md_svg_with_v4_handoff_language(self):
        try:
            writer = importlib.import_module("build_dxf_copper_v35_phase_a_full_layer")
        except ImportError as exc:
            self.fail("missing artifact writer module: %s" % exc)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = writer.build_report_artifacts(root=temp_dir)

            json_path = artifacts["json"]
            md_path = artifacts["md"]
            svg_path = artifacts["svg"]
            self.assertTrue(os.path.exists(json_path))
            self.assertTrue(os.path.exists(md_path))
            self.assertTrue(os.path.exists(svg_path))
            with open(md_path, "r", encoding="utf-8") as handle:
                report = handle.read()
            self.assertIn("V4 handoff", report)
            self.assertIn("not evaluated", report.lower())
            self.assertIn("physical bridge", report.lower())

    def test_validation_pass_exposes_v35_metrics_and_blocking_issue_summary(self):
        geometry = self._build()
        status = self._validate(geometry)

        self._require_keys(geometry, ["spec_summary"])
        self._require_keys(
            status,
            [
                "radial_fill_ratio",
                "angular_occupancy_ratio",
                "centerline_length_mm",
                "copper_area_mm2",
                "bounding_diameter_mm",
                "blocking_issues",
                "v35_full_layer_passed",
            ],
        )
        self.assertTrue(status["valid"])
        self.assertGreaterEqual(status["radial_fill_ratio"], geometry["spec_summary"]["minimum_radial_fill_ratio"])
        self.assertGreaterEqual(
            status["angular_occupancy_ratio"],
            geometry["spec_summary"]["minimum_angular_occupancy_ratio"],
        )
        self.assertGreaterEqual(
            status["centerline_length_mm"],
            geometry["spec_summary"]["minimum_centerline_length_mm"],
        )
        self.assertGreaterEqual(status["copper_area_mm2"], geometry["spec_summary"]["minimum_copper_area_mm2"])
        self.assertGreaterEqual(
            status["bounding_diameter_mm"],
            geometry["spec_summary"]["minimum_bounding_diameter_mm"],
        )
        self.assertEqual(status["blocking_issues"], [])
        self.assertTrue(status["v35_full_layer_passed"])


if __name__ == "__main__":
    unittest.main()
