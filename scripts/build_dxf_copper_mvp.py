from __future__ import print_function

import os
import traceback
from math import sqrt

from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import Logger
from aedt_native_common import pyaedt_attach
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from dxf_copper_geometry import build_v1_phase_a_geometry
from dxf_copper_geometry import validate_v1_geometry


MILESTONE = "Milestone 2: DXF-Compatible 3D Copper MVP"
OBJECT_NAME = "AutoDxfCopper_PhaseA_L01"
SHEET_NAME = OBJECT_NAME + "_Sheet"
MESH_NAME = "AutoDxfCopper_LengthMesh"


def _global_value(name, default_value=None):
    if name in globals():
        return globals().get(name)
    main_globals = getattr(__import__("__main__"), "__dict__", {})
    return main_globals.get(name, default_value)


def _safe_call(callback, default_value=None):
    try:
        return callback()
    except Exception:
        return default_value


def _starts_with_any(value, prefixes):
    text = str(value or "")
    return any(text == prefix or text.startswith(prefix + "_") for prefix in prefixes)


def _cleanup_v1_build_artifacts(app, logger):
    cleanup = {"deleted_objects": [], "blocking_issues": []}
    modeler = getattr(app, "modeler", None)
    if not modeler:
        cleanup["blocking_issues"].append("aedt_modeler_missing_for_cleanup")
        return cleanup

    object_names = list(getattr(modeler, "object_names", []) or [])
    if not object_names:
        object_names = list(getattr(modeler, "objects_by_name", {}) or [])
    targets = [name for name in object_names if _starts_with_any(name, [OBJECT_NAME, SHEET_NAME])]
    if not targets:
        return cleanup

    deleted = _safe_call(lambda: modeler.delete(targets), False)
    if not deleted:
        cleanup["blocking_issues"].append("v1_copper_cleanup_failed")
        logger.log("V1 copper cleanup failed for objects: %s" % targets)
        return cleanup
    cleanup["deleted_objects"] = targets
    logger.log("Deleted prior V1 copper objects: %s" % targets)
    return cleanup


def _host_mode():
    return bool(_global_value("__agent_host_mode", False))


def _artifact_paths(root):
    return {
        "json": os.path.join(root, "artifacts", "dxf_copper_mvp.json"),
        "md": os.path.join(root, "reports", "dxf_copper_mvp.md"),
    }


def _attach_active_maxwell3d(oDesktop, oProject, oDesign, logger):
    from ansys.aedt.core import Maxwell3d

    pid = _safe_call(lambda: int(oDesktop.GetProcessID()), 0)
    project_name = _safe_call(lambda: oProject.GetName(), None)
    design_name = _safe_call(lambda: oDesign.GetName(), None)
    attempts = [
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
            "aedt_process_id": pid if pid else None,
        },
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
        },
        {
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
        },
    ]
    return pyaedt_attach(lambda **kwargs: Maxwell3d(**kwargs), attempts, logger, "Maxwell3d", new_session=False)


def _object_name(value):
    if not value:
        return ""
    name = getattr(value, "name", None)
    if name:
        return str(name)
    return str(value)


def _point_distance_xy(a, b):
    return sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def _terminal_face_targets_xy(terminal):
    center = [float(item) for item in terminal.get("center_xy_mm", [0.0, 0.0])[:2]]
    targets = []
    size = terminal.get("size_xy_mm", [])
    if len(size) >= 1 and center[0] != 0.0:
        pad_half_width = float(size[0]) / 2.0
        outward_x = center[0] + (pad_half_width if center[0] > 0.0 else -pad_half_width)
        targets.append([outward_x, center[1]])
    targets.append(center)

    unique_targets = []
    for target in targets:
        if target not in unique_targets:
            unique_targets.append(target)
    return unique_targets


def select_terminal_faces(face_infos, geometry, tolerance_mm=1.0):
    selected = []
    used_ids = {}
    for terminal in geometry.get("terminals", []):
        matched = None
        for target_index, target in enumerate(_terminal_face_targets_xy(terminal)):
            candidates = []
            for face in face_infos or []:
                face_id = face.get("id", face.get("face_id", None))
                if face_id in used_ids:
                    continue
                center = face.get("center", face.get("center_xyz_mm", []))
                if not center or len(center) < 2:
                    continue
                distance = _point_distance_xy(center, target)
                candidates.append((distance, target_index, target, face))
            if not candidates:
                continue
            candidates.sort(key=lambda item: item[0])
            distance, target_index, target, face = candidates[0]
            if distance <= float(tolerance_mm):
                matched = (distance, target_index, target, face)
                break
        if not matched:
            continue
        distance, target_index, target, face = matched
        face_id = face.get("id", face.get("face_id", None))
        used_ids[face_id] = True
        selected.append(
            {
                "name": terminal.get("name", ""),
                "role": terminal.get("role", ""),
                "face_id": face_id,
                "center_xyz_mm": list(face.get("center", face.get("center_xyz_mm", []))),
                "area_mm2": face.get("area", face.get("area_mm2", None)),
                "match_distance_mm": distance,
                "target_xy_mm": list(target),
                "target_priority": target_index,
            }
        )
    return selected


def _face_info(face):
    center = _safe_call(lambda: list(face.center), [])
    area = _safe_call(lambda: float(face.area), None)
    return {
        "id": _safe_call(lambda: int(face.id), None),
        "center": [float(item) for item in center] if center else [],
        "area": area,
    }


def collect_face_infos(obj):
    return [_face_info(face) for face in _safe_call(lambda: list(obj.faces), [])]


def _aedt_build_result(geometry, logger):
    result = {
        "attempted": True,
        "sheet_created": False,
        "thickened": False,
        "mesh_assigned": False,
        "object_name": "",
        "sheet_name": "",
        "terminal_faces": [],
        "cleanup": {"deleted_objects": [], "blocking_issues": []},
        "blocking_issues": [],
        "save_status": {"saved": False, "error": "", "method": ""},
    }
    oDesktop = _global_value("oDesktop")
    oProject = _global_value("oProject")
    oDesign = _global_value("oDesign")
    if not oDesktop or not oProject or not oDesign:
        result["blocking_issues"].append("aedt_host_globals_missing")
        return result

    try:
        app = _attach_active_maxwell3d(oDesktop, oProject, oDesign, logger)
        result["cleanup"] = _cleanup_v1_build_artifacts(app, logger)
        if result["cleanup"].get("blocking_issues"):
            result["blocking_issues"].extend(result["cleanup"]["blocking_issues"])
            return result
        points = geometry.get("aedt_polyline_points_mm", [])
        sheet = app.modeler.create_polyline(
            points,
            cover_surface=True,
            close_surface=True,
            name=SHEET_NAME,
            material="copper",
        )
        result["sheet_name"] = _object_name(sheet)
        result["sheet_created"] = bool(sheet)
        if not sheet:
            result["blocking_issues"].append("aedt_sheet_creation_returned_empty")
            return result

        thickened = app.modeler.thicken_sheet(
            result["sheet_name"],
            "%smm" % geometry["copper_thickness_mm"],
            both_sides=False,
        )
        result["object_name"] = _object_name(thickened) or result["sheet_name"]
        result["thickened"] = bool(thickened)
        if not thickened:
            result["blocking_issues"].append("aedt_sheet_thicken_returned_empty")
            return result

        mesh = app.mesh.assign_length_mesh(
            [result["object_name"]],
            inside_selection=True,
            maximum_length="%smm" % geometry["copper_thickness_mm"],
            name=MESH_NAME,
        )
        result["mesh_assigned"] = bool(mesh)
        if not mesh:
            result["blocking_issues"].append("aedt_length_mesh_assignment_failed")

        solid = _safe_call(lambda: app.modeler.get_object_from_name(result["object_name"]), None) or thickened
        face_infos = collect_face_infos(solid)
        result["face_count"] = len(face_infos)
        result["face_infos"] = face_infos
        result["terminal_faces"] = select_terminal_faces(face_infos, geometry, tolerance_mm=1.0)
        if len(result["terminal_faces"]) < 2:
            result["blocking_issues"].append("aedt_terminal_face_identification_failed")

        result["save_status"] = save_project(oProject, logger)
        if not result["save_status"].get("saved", False):
            result["blocking_issues"].append("aedt_project_save_failed")
    except Exception:
        result["blocking_issues"].append("aedt_build_exception")
        result["exception"] = traceback.format_exc()
        logger.log(result["exception"])
    return result


def _default_aedt_build_gate(host_mode):
    return {
        "attempted": False,
        "sheet_created": False,
        "thickened": False,
        "mesh_assigned": False,
        "object_name": "",
        "sheet_name": "",
        "terminal_faces": [],
        "cleanup": {"deleted_objects": [], "blocking_issues": []},
        "blocking_issues": [] if not host_mode else ["aedt_build_not_attempted"],
        "save_status": {"saved": False, "error": "", "method": ""},
    }


def build_v1_mvp_summary(host_mode=None, aedt_build_gate=None):
    if host_mode is None:
        host_mode = _host_mode()
    geometry = build_v1_phase_a_geometry()
    geometry_status = validate_v1_geometry(geometry)
    aedt_build_gate = aedt_build_gate or _default_aedt_build_gate(host_mode)
    mesh_defense = {
        "required": True,
        "assigned": bool(aedt_build_gate.get("mesh_assigned", False)),
        "target_thickness_mm": float(geometry["copper_thickness_mm"]),
    }
    blocking_issues = []
    if not geometry_status.get("valid", False):
        blocking_issues.append("geometry_source_invalid")
    if not aedt_build_gate.get("sheet_created", False):
        blocking_issues.append("aedt_sheet_not_created")
    if not aedt_build_gate.get("thickened", False):
        blocking_issues.append("copper_solid_not_thickened")
    if not mesh_defense["assigned"]:
        blocking_issues.append("mesh_defense_not_assigned")
    if len(aedt_build_gate.get("terminal_faces", [])) < 2:
        blocking_issues.append("terminal_faces_not_identified")
    blocking_issues.extend(aedt_build_gate.get("blocking_issues", []))

    geometry_ready = (
        bool(geometry_status.get("valid", False))
        and bool(aedt_build_gate.get("sheet_created", False))
        and bool(aedt_build_gate.get("thickened", False))
    )
    dxf_compatible_copper_ready = geometry_ready and mesh_defense["assigned"] and len(aedt_build_gate.get("terminal_faces", [])) >= 2
    return {
        "timestamp": timestamp_string(),
        "milestone": MILESTONE,
        "geometry_contract_version": geometry.get("geometry_contract_version", ""),
        "host_mode_detected": bool(host_mode),
        "legacy_phase_belt_used": False,
        "phase": geometry["phase"],
        "layer": geometry["layer"],
        "copper_thickness_mm": geometry["copper_thickness_mm"],
        "aedt_handshake_mode": geometry["aedt_handshake_mode"],
        "geometry_source_ready": bool(geometry_status.get("valid", False)),
        "geometry_ready": bool(geometry_ready),
        "dxf_compatible_copper_ready": bool(dxf_compatible_copper_ready),
        "dc_conduction_ready": False,
        "solve_ready": False,
        "manufacturing_ready": False,
        "mesh_defense_required": True,
        "mesh_defense": mesh_defense,
        "geometry": geometry,
        "geometry_status": geometry_status,
        "aedt_build": aedt_build_gate,
        "terminal_faces": list(aedt_build_gate.get("terminal_faces", [])),
        "blocking_issues": sorted(set(blocking_issues)),
        "manual_actions": [
            "Queue this script inside the AEDT host to create a covered sheet from aedt_polyline_points_mm.",
            "Inspect and bind the two terminal faces before running DC Conduction.",
        ],
    }


def markdown_text(summary):
    lines = []
    lines.append("# DXF Copper MVP Build")
    lines.append("")
    lines.append("This artifact tracks the V1 DXF-compatible copper path. It is not a full six-layer or transient validation.")
    lines.append("")
    for key in [
        "timestamp",
        "milestone",
        "host_mode_detected",
        "legacy_phase_belt_used",
        "phase",
        "layer",
        "copper_thickness_mm",
        "aedt_handshake_mode",
        "geometry_source_ready",
        "geometry_ready",
        "dxf_compatible_copper_ready",
        "dc_conduction_ready",
        "solve_ready",
        "manufacturing_ready",
    ]:
        lines.append("- %s: `%s`" % (key, summary.get(key, "")))
    lines.append("")
    lines.append("## Mesh Defense")
    lines.append("")
    mesh = summary.get("mesh_defense", {})
    lines.append("- required: `%s`" % mesh.get("required", False))
    lines.append("- assigned: `%s`" % mesh.get("assigned", False))
    lines.append("- target_thickness_mm: `%s`" % mesh.get("target_thickness_mm", ""))
    lines.append("")
    lines.append("## Geometry Status")
    lines.append("")
    status = summary.get("geometry_status", {})
    for key in ["closed", "valid", "bounding_diameter_mm", "terminal_count", "minimum_clearance_mm"]:
        lines.append("- %s: `%s`" % (key, status.get(key, "")))
    lines.append("")
    lines.append("## AEDT Build")
    lines.append("")
    build = summary.get("aedt_build", {})
    for key in ["attempted", "sheet_created", "thickened", "mesh_assigned", "sheet_name", "object_name"]:
        lines.append("- %s: `%s`" % (key, build.get(key, "")))
    lines.append("")
    lines.append("## Blocking Issues")
    lines.append("")
    issues = summary.get("blocking_issues", [])
    if issues:
        for issue in issues:
            lines.append("- `%s`" % issue)
    else:
        lines.append("- `None`")
    lines.append("")
    lines.append("## Manual Actions")
    lines.append("")
    for action in summary.get("manual_actions", []):
        lines.append("- %s" % action)
    return "\n".join(lines) + "\n"


def write_markdown(path, summary):
    handle = open(path, "w")
    try:
        handle.write(markdown_text(summary))
    finally:
        handle.close()


def main(host_mode=None, raise_on_blocking=True):
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "build_dxf_copper_mvp_%s.log" % timestamp_string()))
    paths = _artifact_paths(root)
    if host_mode is None:
        host_mode = _host_mode()

    aedt_build_gate = None
    if host_mode:
        geometry = build_v1_phase_a_geometry()
        aedt_build_gate = _aedt_build_result(geometry, logger)
    summary = build_v1_mvp_summary(host_mode=host_mode, aedt_build_gate=aedt_build_gate)
    save_json(paths["json"], summary)
    write_markdown(paths["md"], summary)
    logger.log("Wrote DXF copper MVP build artifacts: %s" % paths["json"])

    if host_mode and raise_on_blocking and summary.get("blocking_issues"):
        raise RuntimeError("DXF copper MVP AEDT build blocked; see %s" % paths["md"])
    return paths


if __name__ == "__main__":
    main()
