from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call
from sector3d_aedt import attach_maxwell3d
from sector3d_aedt import design_variable_number
from sector3d_aedt import object_exists


def _write_markdown(path, summary):
    lines = []
    lines.append("# Sector3D Transient Setup Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- setup_name: `%s`" % summary.get("setup_name", ""))
    lines.append("- setup_created: `%s`" % summary.get("setup_created", False))
    lines.append("- setup_updated: `%s`" % summary.get("setup_updated", False))
    lines.append("- motion_requested: `%s`" % summary.get("motion_requested", False))
    lines.append("- motion_assigned: `%s`" % summary.get("motion_assigned", False))
    lines.append("")
    lines.append("## Setup Properties")
    lines.append("")
    for key in ["StopTime", "TimeStep", "SaveFieldsType", "SolveFieldOnly", "UseControlProgram"]:
        lines.append("- %s: `%s`" % (key, summary.get("setup_properties", {}).get(key, "")))
    lines.append("")
    lines.append("## Motion")
    lines.append("")
    lines.append("- band_object_exists: `%s`" % summary.get("band_object_exists", False))
    lines.append("- band_object_name: `%s`" % summary.get("band_object_name", ""))
    lines.append("- motion_note: `%s`" % summary.get("motion_note", ""))
    lines.append("")
    lines.append("## Manual Actions")
    lines.append("")
    manual_actions = summary.get("manual_actions", [])
    if not manual_actions:
        lines.append("- None")
    else:
        for item in manual_actions:
            lines.append("- %s" % item)
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def _get_or_create_setup(app, setup_name, logger):
    existing_names = [str(item.name) for item in getattr(app, "setups", [])]
    if setup_name in existing_names:
        logger.log("Reusing existing setup %s" % setup_name)
        return app.get_setup(setup_name), False
    setup = app.create_setup(name=setup_name, setup_type="Transient")
    if not setup:
        raise RuntimeError("Could not create transient setup %s" % setup_name)
    logger.log("Created transient setup %s" % setup_name)
    return setup, True


def _apply_setup_properties(setup, transient_cfg, logger):
    setup.auto_update = False
    setup.props["StopTime"] = transient_cfg.get("stop_time_expression", "electrical_period_s")
    setup.props["TimeStep"] = transient_cfg.get("time_step_expression", "electrical_period_s/72")
    setup.props["SaveFieldsType"] = transient_cfg.get("save_fields_type", "None")
    setup.props["UseControlProgram"] = False
    setup.props["SolveFieldOnly"] = False
    try:
        setup.update()
    finally:
        setup.auto_update = True
    logger.log(
        "Updated transient setup %s with StopTime=%s TimeStep=%s SaveFieldsType=%s"
        % (
            setup.name,
            setup.props.get("StopTime"),
            setup.props.get("TimeStep"),
            setup.props.get("SaveFieldsType")
        )
    )
    return {
        "StopTime": setup.props.get("StopTime", ""),
        "TimeStep": setup.props.get("TimeStep", ""),
        "SaveFieldsType": setup.props.get("SaveFieldsType", ""),
        "SolveFieldOnly": setup.props.get("SolveFieldOnly", ""),
        "UseControlProgram": setup.props.get("UseControlProgram", "")
    }


def _assign_rotate_motion_if_possible(app, oDesign, motion_cfg, logger):
    band_object_name = motion_cfg.get("band_object_name", "Auto3D_RotatingBand")
    if not motion_cfg.get("enabled", True):
        return False, bool(object_exists(app, band_object_name)), "motion disabled in config"
    if not object_exists(app, band_object_name):
        return False, False, "band object is missing"

    speed_rpm = design_variable_number(oDesign, "speed_rpm", 0.0)
    try:
        motion = app.assign_rotate_motion(
            assignment=band_object_name,
            axis=motion_cfg.get("axis", "Z"),
            positive_movement=bool(motion_cfg.get("positive_rotation", True)),
            start_position="0deg",
            has_rotation_limits=False,
            mechanical_transient=bool(motion_cfg.get("mechanical_transient", True)),
            angular_velocity="%.6grpm" % speed_rpm,
            inertia=1.0,
            damping=0.0,
            load_torque=0.0
        )
        if motion:
            logger.log("Assigned rotate motion on %s at %.6g rpm" % (band_object_name, speed_rpm))
            return True, True, "rotate motion assigned"
    except Exception as exc:
        logger.log("Rotate motion assignment failed: %s" % exc)
        return False, True, str(exc)
    return False, True, "rotate motion assignment returned False"


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "apply_sector3d_transient_setup_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "sector3d_transient_setup.json")
    artifact_md = os.path.join(root, "reports", "sector3d_transient_setup.md")

    required_design_name = project_cfg["sector_3d"]["design_name"]
    setup_name = project_cfg["sector_3d"]["analysis_setup_name"]
    transient_cfg = project_cfg["sector_3d"].get("transient", {})
    motion_cfg = project_cfg["sector_3d"].get("motion", {})
    manual_actions = []

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = attach_maxwell3d(oDesktop, oProject, oDesign, logger)
    setup, created = _get_or_create_setup(app, setup_name, logger)
    setup_properties = _apply_setup_properties(setup, transient_cfg, logger)
    motion_assigned, band_object_exists, motion_note = _assign_rotate_motion_if_possible(app, oDesign, motion_cfg, logger)

    if not band_object_exists and motion_cfg.get("enabled", True):
        manual_actions.append(
            "Motion band `%s` is still missing. Create a Maxwell-compatible axial-flux rotating band before trusting back-EMF or torque waveforms."
            % motion_cfg.get("band_object_name", "Auto3D_RotatingBand")
        )
    if not motion_assigned and band_object_exists:
        manual_actions.append("Rotate motion was not assigned cleanly. Recheck the band container and moving-body enclosure before solving Setup_3D.")
    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "setup_name": setup_name,
        "setup_created": created,
        "setup_updated": True,
        "setup_properties": setup_properties,
        "motion_requested": bool(motion_cfg.get("enabled", True)),
        "motion_assigned": motion_assigned,
        "band_object_exists": band_object_exists,
        "band_object_name": motion_cfg.get("band_object_name", "Auto3D_RotatingBand"),
        "motion_note": motion_note,
        "manual_actions": manual_actions
    }
    save_project(oProject, logger)
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote sector 3D transient setup summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
