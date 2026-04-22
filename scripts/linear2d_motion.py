from __future__ import print_function

import math

from bootstrap_linear2d_template import _safe_call


def _parse_numeric(value, default_value=0.0):
    if value is None:
        return default_value
    text = str(value).strip().lower()
    for suffix in ["mm", "a", "rpm", "deg", "hz", "s", "m_per_sec", "kg", "newton"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    try:
        return float(text)
    except Exception:
        return default_value


def design_case_snapshot(oDesign):
    names = [
        "slice_radius_mm",
        "speed_rpm",
        "period_length_mm"
    ]
    out = {}
    for name in names:
        out[name] = _parse_numeric(_safe_call(lambda n=name: oDesign.GetVariableValue(n), 0.0), 0.0)
    return out


def tangential_velocity_m_per_sec(case_row):
    radius_m = float(case_row.get("slice_radius_mm", 0.0)) / 1000.0
    speed_rpm = float(case_row.get("speed_rpm", 0.0))
    return 2.0 * math.pi * radius_m * speed_rpm / 60.0


def _delete_motion_if_present(app, motion_name, logger):
    try:
        app.omodelsetup.DeleteMotionSetup([motion_name])
        logger.log("Deleted existing motion setup named %s" % motion_name)
        return True
    except Exception:
        return False


def assign_linear_translate_motion(app, project_cfg, case_row, logger):
    motion_cfg = project_cfg["linear_2d"].get("motion", {})
    if not motion_cfg.get("enabled", False):
        return {
            "enabled": False,
            "assigned": False,
            "details": "motion disabled in project configuration"
        }, []

    band_object_name = motion_cfg.get("band_object_name", "Auto2D_MotionBand")
    motion_name = motion_cfg.get("motion_name", "Motion_LinearRotor")
    object_names = [str(name) for name in _safe_call(lambda: list(app.modeler.object_names), [])]
    if band_object_name not in object_names:
        return {
            "enabled": True,
            "assigned": False,
            "band_object_name": band_object_name,
            "motion_name": motion_name,
            "details": "motion band object not found"
        }, ["Missing motion band object %s" % band_object_name]

    velocity_mps = tangential_velocity_m_per_sec(case_row)
    deleted_existing = _delete_motion_if_present(app, motion_name, logger)
    try:
        app.assign_translate_motion(
            assignment=band_object_name,
            coordinate_system="Global",
            axis=motion_cfg.get("axis", "X"),
            positive_movement=bool(motion_cfg.get("positive_movement", True)),
            start_position=motion_cfg.get("start_position_mm", 0.0),
            periodic_translate=bool(motion_cfg.get("periodic_translate", True)),
            negative_limit=motion_cfg.get("negative_limit_expression", "0mm"),
            positive_limit=motion_cfg.get("positive_limit_expression", "period_length_mm"),
            velocity=velocity_mps,
            mechanical_transient=bool(motion_cfg.get("mechanical_transient", True)),
            mass=float(motion_cfg.get("mass_kg", 1.0)),
            damping=float(motion_cfg.get("damping", 0.0)),
            load_force=float(motion_cfg.get("load_force_newton", 0.0)),
            motion_name=motion_name
        )
        logger.log("Assigned linear translate motion %s to %s at %.6f m_per_sec" % (motion_name, band_object_name, velocity_mps))
        return {
            "enabled": True,
            "assigned": True,
            "band_object_name": band_object_name,
            "motion_name": motion_name,
            "deleted_existing": deleted_existing,
            "axis": motion_cfg.get("axis", "X"),
            "periodic_translate": bool(motion_cfg.get("periodic_translate", True)),
            "velocity_m_per_sec": velocity_mps,
            "positive_limit_expression": motion_cfg.get("positive_limit_expression", "period_length_mm"),
            "details": "translation motion assigned"
        }, []
    except Exception as exc:
        return {
            "enabled": True,
            "assigned": False,
            "band_object_name": band_object_name,
            "motion_name": motion_name,
            "deleted_existing": deleted_existing,
            "velocity_m_per_sec": velocity_mps,
            "details": str(exc)
        }, ["Could not assign linear translation motion to %s" % band_object_name]
