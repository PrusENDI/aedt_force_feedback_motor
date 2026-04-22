from __future__ import print_function

import os
import math

from aedt_native_common import Logger
from aedt_native_common import config_paths
from aedt_native_common import ensure_design
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import get_design_solution_type
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _baseline_variables
from bootstrap_linear2d_template import _helper_variables
from bootstrap_linear2d_template import _rename_design_if_possible
from bootstrap_linear2d_template import _save_template_copy
from bootstrap_linear2d_template import _safe_call
from build_hooks import build_linear_2d_scaffold
from aedt_native_common import apply_variables
from winding_geometry import flat_copper_pack_height_mm
from winding_geometry import stator_axial_build_mm


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Geometry Build Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- solution_type: `%s`" % summary.get("solution_type", ""))
    lines.append("- saved_template_path: `%s`" % summary.get("saved_template_path", ""))
    lines.append("- backup_copy_path: `%s`" % summary.get("backup_copy_path", ""))
    lines.append("- physics_ready_for_screening: `%s`" % summary.get("physics_ready_for_screening", False))
    lines.append("")
    lines.append("## Geometry Sanity")
    lines.append("")
    for key in [
        "mean_diameter_mm",
        "pole_pitch_mm_est",
        "magnet_arc_mm_est",
        "pole_arc_ratio",
        "flat_copper_pack_height_mm_est",
        "coil_stack_height_mm_est",
        "stator_axial_build_mm_est",
        "stack_height_mm_est"
    ]:
        if key in summary.get("geometry_sanity", {}):
            lines.append("- %s: `%s`" % (key, summary["geometry_sanity"][key]))
    lines.append("")
    lines.append("## Created Objects")
    lines.append("")
    for item in summary.get("created_objects", []):
        lines.append("- %s (material=`%s`)" % (item.get("name", ""), item.get("material", "")))
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
    lines.append("## Warnings")
    lines.append("")
    warnings = summary.get("warnings", [])
    if not warnings:
        lines.append("- None")
    else:
        for item in warnings:
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


def _geometry_sanity(project_cfg, baseline):
    outer_diameter = float(baseline["outer_diameter_mm"])
    inner_diameter = float(baseline["inner_diameter_mm"])
    pole_count = float(baseline["pole_count"])
    pole_arc_ratio = float(baseline["pole_arc_ratio"])
    slice_radius = float(baseline.get("slice_radius_mm", baseline.get("coil_mean_radius_mm", (outer_diameter + inner_diameter) / 4.0)))
    backiron_thickness = float(baseline["backiron_thickness_mm"])
    magnet_thickness = float(baseline["magnet_thickness_mm"])
    airgap = float(baseline["airgap_mm"])

    mean_diameter = 0.5 * (outer_diameter + inner_diameter)
    pole_pitch = 2.0 * math.pi * slice_radius / pole_count
    magnet_arc = pole_pitch * pole_arc_ratio
    flat_copper_height = flat_copper_pack_height_mm(project_cfg, baseline)
    coil_stack_height = stator_axial_build_mm(project_cfg, baseline)
    stack_height = backiron_thickness + magnet_thickness + airgap + coil_stack_height
    return {
        "mean_diameter_mm": round(mean_diameter, 6),
        "slice_radius_mm": round(slice_radius, 6),
        "pole_pitch_mm_est": round(pole_pitch, 6),
        "magnet_arc_mm_est": round(magnet_arc, 6),
        "pole_arc_ratio": pole_arc_ratio,
        "flat_copper_pack_height_mm_est": round(flat_copper_height, 6),
        "coil_stack_height_mm_est": round(coil_stack_height, 6),
        "stator_axial_build_mm_est": round(coil_stack_height, 6),
        "stack_height_mm_est": round(stack_height, 6)
    }


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "build_linear2d_model_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    paths = config_paths(root, project_cfg)

    artifact_json = os.path.join(root, "artifacts", "linear2d_model_build.json")
    artifact_md = os.path.join(root, "reports", "linear2d_model_build.md")
    backup_path = os.path.join(root, "aedt_projects", "linear2d_template.aedt")

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    if not oProject:
        oProject = oDesktop.NewProject()
        logger.log("No active project was open; created a new project")

    required_design_name = project_cfg["linear_2d"]["design_name"]
    oDesign = _active_design(oProject)
    if oDesign:
        oDesign, _ = _rename_design_if_possible(oProject, oDesign, required_design_name, logger)
    oDesign = ensure_design(
        oProject,
        required_design_name,
        project_cfg["linear_2d"].get("design_type", "Maxwell 2D"),
        project_cfg["linear_2d"].get("solution_type", "TransientXY"),
        logger
    )

    baseline = _baseline_variables(project_cfg, search_cfg)
    helpers = _helper_variables()
    apply_variables(oDesign, baseline, logger)
    apply_variables(oDesign, helpers, logger)

    build_result = build_linear_2d_scaffold(oProject, oDesign, project_cfg, baseline, logger, cleanup_first=True)
    save_project(oProject, logger)
    save_result = _save_template_copy(oProject, paths["linear_2d_template"], backup_path, logger, already_saved=True)

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": _safe_call(lambda: oDesign.GetName(), ""),
        "solution_type": get_design_solution_type(oDesign, logger),
        "baseline_variables": baseline,
        "helper_variables": helpers,
        "geometry_sanity": _geometry_sanity(project_cfg, baseline),
        "created_objects": build_result.get("created_objects", []),
        "deleted_objects": build_result.get("deleted_objects", []),
        "scaffold_variables": build_result.get("scaffold_variables", {}),
        "blocking_issues": build_result.get("blocking_issues", []),
        "warnings": build_result.get("warnings", []),
        "physics_ready_for_screening": not bool(build_result.get("blocking_issues", [])),
        "manual_actions": build_result.get("manual_actions", []),
        "saved_template_path": save_result.get("saved_template_path", ""),
        "backup_copy_path": save_result.get("backup_copy_path", "")
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote linear 2D model build summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
