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


if __name__ == "__main__":
    unittest.main()
