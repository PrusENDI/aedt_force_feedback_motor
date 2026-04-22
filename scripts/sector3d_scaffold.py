from __future__ import print_function


def ensure_sector_3d_design(oProject, oDesign, project_cfg, case_row, logger):
    logger.log("sector3d_scaffold.ensure_sector_3d_design is still a placeholder")
    logger.log("The 3D scaffold is now separated from the Linearized2D scaffold so it can evolve independently")
    return {
        "manual_actions": [
            "Build the Maxwell 3D sector model manually for now",
            "Keep the 3D geometry on the rigid PCB plus flat-copper hybrid route defined in config/project.json",
            "Do not reuse Linearized2D Auto2D_* geometry assumptions inside the Sector3D model"
        ]
    }
