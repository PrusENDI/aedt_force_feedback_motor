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
from assign_linear2d_excitation import _attach_maxwell2d
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call
from linear2d_motion import assign_linear_translate_motion
from linear2d_motion import design_case_snapshot


BASE_MAGNET_MATERIAL = "Magnet, permanent, Neodymium N42SH"
MAGNET_OBJECTS = [
    {
        "object_name": "Auto2D_Magnet_N",
        "material_name": "FFB_N42SH_N",
        "direction": [0, 1, 0]
    },
    {
        "object_name": "Auto2D_Magnet_S",
        "material_name": "FFB_N42SH_S",
        "direction": [0, -1, 0]
    }
]
REGION_OBJECT = "Auto2D_Region"
AIRGAP_OBJECT = "Auto2D_AirGap"
PERIODIC_BOUNDARY_NAME = "Periodic_X"
AIRGAP_MESH_NAME = "AirGap_Length"
AIRGAP_TARGET_LAYERS = 4
AIRGAP_MAX_LENGTH_EXPR = "airgap_mm/%d" % AIRGAP_TARGET_LAYERS


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Physics Setup Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- physics_ready_for_screening: `%s`" % summary.get("physics_ready_for_screening", False))
    lines.append("- save_ok: `%s`" % summary.get("save_ok", False))
    lines.append("")
    lines.append("## Magnet Setup")
    lines.append("")
    for item in summary.get("magnet_results", []):
        lines.append(
            "- %s: exists=`%s`, material=`%s`, coercivity=`%s`, assigned=`%s`, details=`%s`" % (
                item.get("object_name", ""),
                item.get("exists", False),
                item.get("material_name", ""),
                item.get("coercivity_direction", []),
                item.get("assigned", False),
                item.get("details", "")
            )
        )
    lines.append("")
    lines.append("## Periodic Boundary")
    lines.append("")
    periodic = summary.get("periodic_result", {})
    if periodic:
        lines.append("- region_exists: `%s`" % periodic.get("region_exists", False))
        lines.append("- left_edge_id: `%s`" % periodic.get("left_edge_id", ""))
        lines.append("- right_edge_id: `%s`" % periodic.get("right_edge_id", ""))
        lines.append("- assigned: `%s`" % periodic.get("assigned", False))
        lines.append("- boundary_name: `%s`" % periodic.get("boundary_name", ""))
        lines.append("- details: `%s`" % periodic.get("details", ""))
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Air-Gap Mesh")
    lines.append("")
    mesh_result = summary.get("mesh_result", {})
    if mesh_result:
        lines.append("- object_exists: `%s`" % mesh_result.get("object_exists", False))
        lines.append("- assigned: `%s`" % mesh_result.get("assigned", False))
        lines.append("- mesh_name: `%s`" % mesh_result.get("mesh_name", ""))
        lines.append("- maximum_length: `%s`" % mesh_result.get("maximum_length", ""))
        lines.append("- details: `%s`" % mesh_result.get("details", ""))
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Motion Setup")
    lines.append("")
    motion_result = summary.get("motion_result", {})
    if motion_result:
        lines.append("- enabled: `%s`" % motion_result.get("enabled", False))
        lines.append("- assigned: `%s`" % motion_result.get("assigned", False))
        lines.append("- band_object_name: `%s`" % motion_result.get("band_object_name", ""))
        lines.append("- motion_name: `%s`" % motion_result.get("motion_name", ""))
        lines.append("- velocity_m_per_sec: `%s`" % motion_result.get("velocity_m_per_sec", ""))
        lines.append("- positive_limit_expression: `%s`" % motion_result.get("positive_limit_expression", ""))
        lines.append("- details: `%s`" % motion_result.get("details", ""))
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Blocking Issues")
    lines.append("")
    blocking_issues = summary.get("blocking_issues", [])
    if not blocking_issues:
        lines.append("- None")
    else:
        for item in blocking_issues:
            lines.append("- %s" % item)
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


def _object_exists(app, object_name):
    object_names = _safe_call(lambda: list(app.modeler.object_names), [])
    return object_name in [str(name) for name in object_names]


def _delete_boundary_if_present(app, boundary_name, logger):
    try:
        app.oboundary.DeleteBoundaries([boundary_name])
        logger.log("Deleted existing boundary named %s" % boundary_name)
        return True
    except Exception:
        return False


def _delete_mesh_if_present(app, mesh_name, logger):
    mesh_ops = _safe_call(lambda: list(app.mesh.meshoperations), [])
    for mesh_op in mesh_ops:
        name = _safe_call(lambda: mesh_op.name, "")
        if name != mesh_name:
            continue
        try:
            mesh_op.delete()
            logger.log("Deleted existing mesh operation named %s" % mesh_name)
            return True
        except Exception:
            logger.log("Could not delete existing mesh operation named %s" % mesh_name)
            return False
    return False


def _ensure_oriented_material(app, base_material_name, new_name, direction, logger):
    material = _safe_call(lambda: app.materials.exists_material(new_name), False)
    created = False
    if not material:
        material = app.materials.duplicate_material(base_material_name, name=new_name)
        created = bool(material)
        if created:
            logger.log("Duplicated material %s -> %s" % (base_material_name, new_name))

    if not material:
        raise RuntimeError("Could not duplicate base material %s as %s" % (base_material_name, new_name))

    coercivity = _safe_call(lambda: material.get_magnetic_coercivity(), False)
    if coercivity:
        magnitude = str(coercivity[0]).replace("A_per_meter", "").strip()
    else:
        magnitude = "0"
    material.set_magnetic_coercivity(magnitude, direction[0], direction[1], direction[2])
    logger.log("Set coercivity for %s to magnitude=%s direction=%s" % (new_name, magnitude, direction))
    return {
        "created": created,
        "material_name": new_name,
        "magnitude": magnitude,
        "direction": direction
    }


def _assign_magnet_materials(app, logger):
    results = []
    blocking_issues = []
    for magnet in MAGNET_OBJECTS:
        exists = _object_exists(app, magnet["object_name"])
        item = {
            "object_name": magnet["object_name"],
            "exists": exists,
            "material_name": magnet["material_name"],
            "coercivity_direction": magnet["direction"],
            "assigned": False,
            "details": ""
        }
        if not exists:
            item["details"] = "object not found"
            blocking_issues.append("Missing required magnet object %s" % magnet["object_name"])
            results.append(item)
            continue

        try:
            material_result = _ensure_oriented_material(
                app,
                BASE_MAGNET_MATERIAL,
                magnet["material_name"],
                magnet["direction"],
                logger
            )
            app.modeler[magnet["object_name"]].material_name = material_result["material_name"]
            item["assigned"] = True
            item["details"] = "material duplicated_or_reused and assigned"
        except Exception as exc:
            item["details"] = str(exc)
            blocking_issues.append("Could not assign oriented magnet material to %s" % magnet["object_name"])
        results.append(item)
    return results, blocking_issues


def _assign_periodic_boundaries(app, logger):
    result = {
        "region_exists": False,
        "left_edge_id": "",
        "right_edge_id": "",
        "boundary_name": PERIODIC_BOUNDARY_NAME,
        "assigned": False,
        "details": ""
    }
    if not _object_exists(app, REGION_OBJECT):
        result["details"] = "region object not found"
        return result, ["Missing required region object %s" % REGION_OBJECT]

    result["region_exists"] = True
    region = app.modeler[REGION_OBJECT]
    left_edge = _safe_call(lambda: region.bottom_edge_x, None)
    right_edge = _safe_call(lambda: region.top_edge_x, None)
    if not left_edge or not right_edge:
        result["details"] = "could not resolve left/right region edges"
        return result, ["Could not resolve left/right boundary edges on %s" % REGION_OBJECT]

    result["left_edge_id"] = _safe_call(lambda: left_edge.id, "")
    result["right_edge_id"] = _safe_call(lambda: right_edge.id, "")
    _delete_boundary_if_present(app, PERIODIC_BOUNDARY_NAME, logger)
    _delete_boundary_if_present(app, PERIODIC_BOUNDARY_NAME + "_dep", logger)

    try:
        app.assign_master_slave(
            independent=left_edge.id,
            dependent=right_edge.id,
            reverse_master=False,
            reverse_slave=False,
            same_as_master=True,
            boundary=PERIODIC_BOUNDARY_NAME
        )
        result["assigned"] = True
        result["details"] = "master/slave assigned across one linearized period"
        logger.log("Assigned periodic master/slave boundaries on region left/right edges")
        return result, []
    except Exception as exc:
        result["details"] = str(exc)
        return result, ["Could not assign periodic boundaries on %s" % REGION_OBJECT]


def _assign_airgap_mesh(app, logger):
    result = {
        "object_exists": False,
        "mesh_name": AIRGAP_MESH_NAME,
        "maximum_length": AIRGAP_MAX_LENGTH_EXPR,
        "assigned": False,
        "details": ""
    }
    if not _object_exists(app, AIRGAP_OBJECT):
        result["details"] = "air-gap object not found"
        return result, ["Missing required air-gap object %s" % AIRGAP_OBJECT]

    result["object_exists"] = True
    _delete_mesh_if_present(app, AIRGAP_MESH_NAME, logger)
    try:
        app.mesh.assign_length_mesh(
            assignment=AIRGAP_OBJECT,
            inside_selection=True,
            maximum_length=AIRGAP_MAX_LENGTH_EXPR,
            maximum_elements=None,
            name=AIRGAP_MESH_NAME
        )
        result["assigned"] = True
        result["details"] = "length mesh assigned for about %d layers across the air gap" % AIRGAP_TARGET_LAYERS
        logger.log("Assigned air-gap length mesh to %s with maximum_length=%s" % (AIRGAP_OBJECT, AIRGAP_MAX_LENGTH_EXPR))
        return result, []
    except Exception as exc:
        result["details"] = str(exc)
        return result, ["Could not assign air-gap mesh refinement to %s" % AIRGAP_OBJECT]


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "apply_linear2d_physics_setup_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "linear2d_physics_setup.json")
    artifact_md = os.path.join(root, "reports", "linear2d_physics_setup.md")

    required_design_name = project_cfg["linear_2d"]["design_name"]
    manual_actions = []
    blocking_issues = []

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = _attach_maxwell2d(oDesktop, oProject, oDesign, logger)

    magnet_results, magnet_blocking = _assign_magnet_materials(app, logger)
    periodic_result, periodic_blocking = _assign_periodic_boundaries(app, logger)
    mesh_result, mesh_blocking = _assign_airgap_mesh(app, logger)
    motion_case = design_case_snapshot(oDesign)
    motion_result, motion_blocking = assign_linear_translate_motion(app, project_cfg, motion_case, logger)
    blocking_issues.extend(magnet_blocking)
    blocking_issues.extend(periodic_blocking)
    blocking_issues.extend(mesh_blocking)
    blocking_issues.extend(motion_blocking)

    save_ok = True
    try:
        save_project(oProject, logger)
    except Exception:
        save_ok = False

    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))
    manual_actions.append("Run assign_linear2d_excitation.py next so Auto2D_Coil_Pos and Auto2D_Coil_Neg are driven by phase_current_rms")
    manual_actions.append("Solve once and then run create_linear2d_reports.py to generate the 5 required named reports")
    manual_actions.append("After the first solve, visually confirm that N/S magnet orientation, periodic field continuity, air-gap element layering, and motion-band translation all look physically correct")

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "required_design_name": required_design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "base_magnet_material": BASE_MAGNET_MATERIAL,
        "magnet_results": magnet_results,
        "periodic_result": periodic_result,
        "mesh_result": mesh_result,
        "motion_result": motion_result,
        "blocking_issues": blocking_issues,
        "physics_ready_for_screening": not bool(blocking_issues),
        "save_ok": save_ok,
        "manual_actions": manual_actions
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote linear 2D physics setup summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
