import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import in_aedt_agent_host


class FakeDesign(object):
    def GetName(self):
        return "Sector3D"


class FakeProject(object):
    def GetName(self):
        return "sector3d_working"

    def GetActiveDesign(self):
        return FakeDesign()


class FakeDesktop(object):
    def GetActiveProject(self):
        return FakeProject()


class HostSharedGlobalsTests(unittest.TestCase):
    def test_injects_active_project_and_design_after_host_preparation(self):
        shared = {"oDesktop": FakeDesktop()}

        in_aedt_agent_host._inject_active_project_design(shared, FakeDesktop(), preparation={"prepared": True})

        self.assertEqual(shared["oProject"].GetName(), "sector3d_working")
        self.assertEqual(shared["oDesign"].GetName(), "Sector3D")


if __name__ == "__main__":
    unittest.main()
