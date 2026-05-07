from __future__ import print_function

import os
import traceback

from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import Logger
from aedt_native_common import pyaedt_attach
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from dxf_copper_geometry import build_single_layer_geometry
from dxf_copper_geometry import export_single_layer_dxf_preview
from dxf_copper_geometry import validate_single_layer_geometry
from dxf_copper_geometry import v2_aedt_names


MILESTONE = "Milestone 3: Repeatable Single-Layer Geometry Generator"
ARTIFACT_JSON = "dxf_copper_v2_single_layer.json"
REPORT_MD = "dxf_copper_v2_single_layer.md"
PREVIEW_DXF = "dxf_copper_v2_phase_a_l01_preview.dxf"
ESTIMATE_CAVEAT = (
    "V2 resistance, area, length, and inductance-like values are geometry-derived estimates. "
    "They include systematic shape error from polyline arc approximation, mitred joins, terminal pads, and V2-only scope."
)


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


def _host_mode():
    return bool(_global_value("__agent_host_mode", False))


def _artifact_paths(root):
    return {
        "json": os.path.join(root, "artifacts", ARTIFACT_JSON),
        "md": os.path.join(root, "reports", REPORT_MD),
        "dxf_preview": os.path.join(root, "artifacts", PREVIEW_DXF),
    }


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
        "object_debug": {},
        "post_build_object_names": [],
        "fit_all_called": False,
        "blocking_issues": [] if not host_mode else ["aedt_build_not_attempted"],
        "save_status": {"saved": False, "error": "", "method": ""},
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


def _object_name(value, fallback=""):
    if not value:
        return fallback
    if isinstance(value, bool):
        return fallback
    name = getattr(value, "name", None)
    if name:
        return str(name)
    return str(value)


def _starts_with_any(value, prefixes):
    text = str(value or "")
    return any(text == prefix or text.startswith(prefix + "_") for prefix in prefixes)


def _cleanup_v2_build_artifacts(app, logger):
    cleanup = {"deleted_objects": [], "blocking_issues": []}
    modeler = getattr(app, "modeler", None)
    if not modeler:
        cleanup["blocking_issues"].append("aedt_modeler_missing_for_cleanup")
        return cleanup

    object_names = list(getattr(modeler, "object_names", []) or [])
    if not object_names:
        object_names = list(getattr(modeler, "objects_by_name", {}) or [])
    targets = [name for name in object_names if _starts_with_any(name, ["AutoDxfCopperV2"])]
    if not targets:
        return cleanup

    deleted = _safe_call(lambda: modeler.delete(targets), False)
    if not deleted:
        cleanup["blocking_issues"].append("v2_copper_cleanup_failed")
        logger.log("V2 copper cleanup failed for objects: %s" % targets)
        return cleanup
    cleanup["deleted_objects"] = targets
    logger.log("Deleted prior V2 copper objects: %s" % targets)
    return cleanup


def _object_debug_info(app, object_name):
    obj = _safe_call(lambda: app.modeler.get_object_from_name(object_name), None)
    if not obj:
        return {
            "exists": False,
            "name": object_name,
            "bounding_box": [],
            "face_count": 0,
            "visible": None,
        }
    faces = _safe_call(lambda: list(obj.faces), [])
    return {
        "exists": True,
        "name": _object_name(obj, object_name),
        "bounding_box": _safe_call(lambda: list(obj.bounding_box), []),
        "face_count": len(faces),
        "visible": _safe_call(lambda: bool(obj.visible), None),
    }


def _aedt_build_result(geometry, logger):
    names = v2_aedt_names()
    result = {
        "attempted": True,
        "sheet_created": False,
        "thickened": False,
        "mesh_assigned": False,
        "object_name": "",
        "sheet_name": "",
        "terminal_faces": [],
        "cleanup": {"deleted_objects": [], "blocking_issues": []},
        "object_debug": {},
        "post_build_object_names": [],
        "fit_all_called": False,
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
        result["cleanup"] = _cleanup_v2_build_artifacts(app, logger)
        if result["cleanup"].get("blocking_issues"):
            result["blocking_issues"].extend(result["cleanup"]["blocking_issues"])
            return result
        points = geometry.get("aedt_polyline_points_mm", [])
        sheet = app.modeler.create_polyline(
            points,
            cover_surface=True,
            close_surface=True,
            name=names["sheet_name"],
            material="copper",
        )
        result["sheet_name"] = _object_name(sheet, names["sheet_name"])
        result["sheet_created"] = bool(sheet)
        if not sheet:
            result["blocking_issues"].append("aedt_sheet_creation_returned_empty")
            return result

        thickness = "%smm" % geometry["copper_thickness_mm"]
        thickened = app.modeler.thicken_sheet(
            result["sheet_name"],
            thickness,
            both_sides=False,
        )
        result["object_name"] = _object_name(thickened, result["sheet_name"])
        result["thickened"] = bool(thickened)
        if not thickened:
            result["blocking_issues"].append("aedt_sheet_thicken_returned_empty")
            return result

        mesh = app.mesh.assign_length_mesh(
            [result["object_name"]],
            inside_selection=True,
            maximum_length=thickness,
            name=names["mesh_name"],
        )
        result["mesh_assigned"] = bool(mesh)
        if not mesh:
            result["blocking_issues"].append("aedt_length_mesh_assignment_failed")

        result["post_build_object_names"] = [
            name for name in list(getattr(app.modeler, "object_names", []) or [])
            if _starts_with_any(name, ["AutoDxfCopperV2"])
        ]
        _safe_call(lambda: app.modeler.get_object_from_name(result["object_name"]).show(), None)
        _safe_call(lambda: app.modeler.fit_all(), None)
        result["fit_all_called"] = True
        result["object_debug"] = _object_debug_info(app, result["object_name"])
        logger.log("V2 copper object debug: %s" % result["object_debug"])

        result["save_status"] = save_project(oProject, logger)
        if not result["save_status"].get("saved", False):
            result["blocking_issues"].append("aedt_project_save_failed")
    except Exception:
        result["blocking_issues"].append("aedt_build_exception")
        result["exception"] = traceback.format_exc()
        logger.log(result["exception"])
    return result


def build_v2_single_layer_summary(host_mode=None, aedt_build_gate=None, spec=None, dxf_preview_path=None):
    if host_mode is None:
        host_mode = _host_mode()
    geometry = build_single_layer_geometry(spec=spec)
    geometry_status = validate_single_layer_geometry(geometry)
    names = v2_aedt_names()
    aedt_build_gate = aedt_build_gate or _default_aedt_build_gate(host_mode)
    source_ready = bool(geometry_status.get("valid", False))
    geometry_ready = (
        source_ready
        and bool(aedt_build_gate.get("sheet_created", False))
        and bool(aedt_build_gate.get("thickened", False))
    )

    blocking_issues = []
    if not source_ready:
        blocking_issues.append("single_layer_geometry_source_invalid")
    if host_mode:
        if not aedt_build_gate.get("sheet_created", False):
            blocking_issues.append("aedt_sheet_not_created")
        if not aedt_build_gate.get("thickened", False):
            blocking_issues.append("copper_solid_not_thickened")
        if not aedt_build_gate.get("mesh_assigned", False):
            blocking_issues.append("mesh_defense_not_assigned")
    blocking_issues.extend(aedt_build_gate.get("blocking_issues", []))

    metadata = geometry.get("metadata", {})
    if dxf_preview_path is None:
        dxf_preview_path = PREVIEW_DXF
    if metadata.get("dxf_export_mode", "disabled") == "disabled":
        dxf_preview = {"status": "disabled", "blocking": False, "output_path": dxf_preview_path}
    else:
        dxf_preview = export_single_layer_dxf_preview(geometry, dxf_preview_path)
    return {
        "timestamp": timestamp_string(),
        "milestone": MILESTONE,
        "geometry_contract_version": geometry.get("geometry_contract_version", ""),
        "host_mode_detected": bool(host_mode),
        "project_name": names["project_name"],
        "design_name": names["design_name"],
        "legacy_phase_belt_used": False,
        "phase": geometry.get("phase", ""),
        "layer": geometry.get("layer", ""),
        "topology_preset": geometry.get("topology_preset", ""),
        "geometry_scope": geometry.get("geometry_scope", ""),
        "full_phase_winding_enabled": bool(geometry.get("full_phase_winding_enabled", False)),
        "copper_thickness_mm": geometry.get("copper_thickness_mm", ""),
        "aedt_handshake_mode": "polyline_points",
        "single_layer_geometry_source_ready": source_ready,
        "geometry_ready": bool(geometry_ready),
        "dxf_preview_ready": dxf_preview["status"] == "exported",
        "dxf_preview": dxf_preview,
        "dc_conduction_ready": False,
        "solve_ready": False,
        "manufacturing_ready": False,
        "corner_policy": metadata.get("corner_policy", ""),
        "arc_segment_deg": metadata.get("arc_segment_deg", ""),
        "estimate_caveat": ESTIMATE_CAVEAT,
        "geometry": geometry,
        "geometry_diagnostics": geometry.get("diagnostics", {}),
        "geometry_status": geometry_status,
        "aedt_build": aedt_build_gate,
        "terminal_faces": list(aedt_build_gate.get("terminal_faces", [])),
        "blocking_issues": sorted(set(blocking_issues)),
        "manual_actions": [
            "Queue this script inside the AEDT host to create and thicken the V2 single-layer copper sheet.",
            "Treat V2 geometry-derived estimates as preliminary until DC Conduction and manufacturing checks are added.",
        ],
    }


def markdown_text(summary):
    lines = []
    lines.append("# DXF Copper V2 Single-Layer Build")
    lines.append("")
    lines.append("This artifact tracks the V2 repeatable single-layer geometry source and optional AEDT sheet creation.")
    lines.append("")
    for key in [
        "timestamp",
        "milestone",
        "project_name",
        "design_name",
        "host_mode_detected",
        "legacy_phase_belt_used",
        "phase",
        "layer",
        "topology_preset",
        "geometry_scope",
        "full_phase_winding_enabled",
        "copper_thickness_mm",
        "aedt_handshake_mode",
        "single_layer_geometry_source_ready",
        "geometry_ready",
        "dxf_preview_ready",
        "dc_conduction_ready",
        "solve_ready",
        "manufacturing_ready",
        "corner_policy",
        "arc_segment_deg",
    ]:
        lines.append("- %s: `%s`" % (key, summary.get(key, "")))
    lines.append("")
    lines.append("## DXF Preview")
    lines.append("")
    dxf_preview = summary.get("dxf_preview", {})
    for key in ["status", "blocking", "output_path"]:
        lines.append("- %s: `%s`" % (key, dxf_preview.get(key, "")))
    lines.append("")
    lines.append("## Estimate Caveat")
    lines.append("")
    lines.append(summary.get("estimate_caveat", ""))
    lines.append("")
    lines.append("## Geometry Status")
    lines.append("")
    status = summary.get("geometry_status", {})
    for key in [
        "closed",
        "valid",
        "self_intersection_free",
        "area_mm2",
        "bounding_diameter_mm",
        "minimum_width_mm",
        "minimum_clearance_mm",
        "terminal_count",
    ]:
        lines.append("- %s: `%s`" % (key, status.get(key, "")))
    issues = status.get("issues", [])
    lines.append("- issues: `%s`" % (", ".join(issues) if issues else "None"))
    lines.append("")
    lines.append("## Geometry Diagnostics")
    lines.append("")
    diagnostics = summary.get("geometry_diagnostics", {})
    for key in [
        "centerline_length_mm",
        "centerline_point_count",
        "outline_point_count",
        "angular_span_deg",
        "radial_min_mm",
        "radial_max_mm",
        "terminal_pad_size_xy_mm",
        "terminal_pad_role",
        "arc_sampling_policy",
        "actual_arc_segment_count",
        "max_arc_segment_count",
    ]:
        lines.append("- %s: `%s`" % (key, diagnostics.get(key, "")))
    lines.append("")
    lines.append("## AEDT Build")
    lines.append("")
    build = summary.get("aedt_build", {})
    for key in ["attempted", "sheet_created", "thickened", "mesh_assigned", "sheet_name", "object_name"]:
        lines.append("- %s: `%s`" % (key, build.get(key, "")))
    save_status = build.get("save_status", {})
    lines.append("- save_status.saved: `%s`" % save_status.get("saved", False))
    lines.append("- terminal_faces: `%s`" % len(build.get("terminal_faces", [])))
    cleanup = build.get("cleanup", {})
    lines.append("- cleanup.deleted_objects: `%s`" % cleanup.get("deleted_objects", []))
    lines.append("- cleanup.blocking_issues: `%s`" % cleanup.get("blocking_issues", []))
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
    logger = Logger(os.path.join(root, "logs", "build_dxf_copper_v2_%s.log" % timestamp_string()))
    paths = _artifact_paths(root)
    if host_mode is None:
        host_mode = _host_mode()

    aedt_build_gate = None
    if host_mode:
        geometry = build_single_layer_geometry()
        aedt_build_gate = _aedt_build_result(geometry, logger)
    summary = build_v2_single_layer_summary(
        host_mode=host_mode,
        aedt_build_gate=aedt_build_gate,
        dxf_preview_path=paths["dxf_preview"],
    )
    save_json(paths["json"], summary)
    write_markdown(paths["md"], summary)
    logger.log("Wrote DXF copper V2 single-layer build artifacts: %s" % paths["json"])

    if host_mode and raise_on_blocking and summary.get("blocking_issues"):
        raise RuntimeError("DXF copper V2 AEDT build blocked; see %s" % paths["md"])
    return paths


if __name__ == "__main__":
    main()
