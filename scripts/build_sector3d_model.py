from __future__ import print_function

import math
import os

from aedt_native_common import Logger
from aedt_native_common import apply_variables
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
from bootstrap_linear2d_template import _rename_design_if_possible
from bootstrap_linear2d_template import _save_template_copy
from bootstrap_linear2d_template import _safe_call
from sector3d_scaffold import build_sector_3d_scaffold
from sector3d_scaffold import literature_basis
from sector3d_scaffold import physics_contract
from winding_geometry import flat_copper_pack_height_mm
from winding_geometry import stator_axial_build_mm


def _baseline_variables(project_cfg, search_cfg):
    fixed = project_cfg["machine_fixed"]
    hybrid = project_cfg.get("hybrid_winding", {})
    out = dict(fixed)
    out.update(hybrid)
    out["phase_current_rms"] = fixed["continuous_phase_current_arms"]
    out["speed_rpm"] = fixed["max_speed_rpm"]
    for spec in search_cfg["variables"]:
        out[spec["name"]] = spec["baseline"]
    return out


def _geometry_sanity(project_cfg, baseline):
    outer_radius = 0.5 * float(baseline["outer_diameter_mm"])
    inner_radius = 0.5 * float(baseline["inner_diameter_mm"])
    pole_count = float(baseline["pole_count"])
    sector_pole_count = float(project_cfg["sector_3d"].get("sector_model_pole_count", 2))
    coreless_cfg = project_cfg["sector_3d"].get("coreless_physics", {})
    pole_arc_ratio = float(baseline["pole_arc_ratio"])
    flat_copper_height = flat_copper_pack_height_mm(project_cfg, baseline)
    stator_height = stator_axial_build_mm(project_cfg, baseline)
    stack_height = 2.0 * float(baseline["backiron_thickness_mm"]) + 2.0 * float(baseline["magnet_thickness_mm"]) + 2.0 * float(baseline["airgap_mm"]) + stator_height
    flat_copper_inner = float(baseline["coil_mean_radius_mm"]) - 0.5 * float(baseline["coil_radial_span_mm"])
    flat_copper_outer = float(baseline["coil_mean_radius_mm"]) + 0.5 * float(baseline["coil_radial_span_mm"])
    mean_radius = 0.5 * (outer_radius + inner_radius)
    pole_pitch = 2.0 * math.pi * mean_radius / pole_count
    magnet_arc = pole_pitch * pole_arc_ratio
    region_padding = float(coreless_cfg.get("minimum_region_padding_mm", 8.0)) + float(coreless_cfg.get("region_padding_airgap_multiplier", 4.0)) * float(baseline["airgap_mm"])
    return {
        "outer_radius_mm": round(outer_radius, 6),
        "inner_radius_mm": round(inner_radius, 6),
        "sector_angle_deg_est": round(360.0 * sector_pole_count / pole_count, 6),
        "pole_pitch_mm_est": round(pole_pitch, 6),
        "magnet_arc_mm_est": round(magnet_arc, 6),
        "flat_copper_inner_radius_mm_est": round(flat_copper_inner, 6),
        "flat_copper_outer_radius_mm_est": round(flat_copper_outer, 6),
        "flat_copper_pack_height_mm_est": round(flat_copper_height, 6),
        "stator_axial_build_mm_est": round(stator_height, 6),
        "stack_height_mm_est": round(stack_height, 6),
        "region_padding_mm_est": round(region_padding, 6)
    }


def _write_markdown(path, summary):
    lines = []
    lines.append("# Sector3D Geometry Build Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- solution_type: `%s`" % summary.get("solution_type", ""))
    lines.append("- saved_template_path: `%s`" % summary.get("saved_template_path", ""))
    lines.append("- backup_copy_path: `%s`" % summary.get("backup_copy_path", ""))
    lines.append("- baseline_ready_for_solve: `%s`" % summary.get("baseline_ready_for_solve", False))
    lines.append("- physics_ready_for_validation: `%s`" % summary.get("physics_ready_for_validation", False))
    lines.append("")
    lines.append("## Geometry Sanity")
    lines.append("")
    for key in [
        "outer_radius_mm",
        "inner_radius_mm",
        "sector_angle_deg_est",
        "pole_pitch_mm_est",
        "magnet_arc_mm_est",
        "flat_copper_inner_radius_mm_est",
        "flat_copper_outer_radius_mm_est",
        "flat_copper_pack_height_mm_est",
        "stator_axial_build_mm_est",
        "stack_height_mm_est",
        "region_padding_mm_est"
    ]:
        if key in summary.get("geometry_sanity", {}):
            lines.append("- %s: `%s`" % (key, summary["geometry_sanity"][key]))
    lines.append("")
    lines.append("## Physics Contract")
    lines.append("")
    contract = summary.get("physics_contract", {})
    contract_layers = contract.get("contract_layers", {})
    coreless = contract.get("coreless_physics", {})
    transient = contract.get("transient", {})
    boundaries = contract.get("boundaries", {})
    motion = contract.get("motion", {})
    winding = contract.get("winding", {})
    mesh = contract.get("mesh", {})
    verification = contract.get("verification", {})
    lines.append("- calibration_topology: `%s`" % contract_layers.get("calibration_topology", ""))
    lines.append("- final_target_topology: `%s`" % contract_layers.get("final_target_topology", ""))
    lines.append("- final_target_active_gap_faces: `%s`" % contract_layers.get("final_target_active_gap_faces", ""))
    lines.append("- stator_is_coreless: `%s`" % coreless.get("stator_is_coreless", ""))
    lines.append("- do_not_reuse_iron_core_assumptions: `%s`" % coreless.get("do_not_reuse_iron_core_assumptions", ""))
    lines.append("- expect_strong_fringing_flux: `%s`" % coreless.get("expect_strong_fringing_flux", ""))
    lines.append("- expect_strong_leakage_flux: `%s`" % coreless.get("expect_strong_leakage_flux", ""))
    lines.append("- require_inductance_check: `%s`" % coreless.get("require_inductance_check", ""))
    lines.append("- inductance_target_range_mh: `%s`" % coreless.get("inductance_target_range_mh", ""))
    lines.append("- require_demagnetization_check: `%s`" % coreless.get("require_demagnetization_check", ""))
    lines.append("- transient_time_step_expression: `%s`" % transient.get("time_step_expression", ""))
    lines.append("- transient_stop_time_expression: `%s`" % transient.get("stop_time_expression", ""))
    lines.append("- periodic_strategy: `%s`" % boundaries.get("periodic_strategy", ""))
    lines.append("- motion_type: `%s`" % motion.get("motion_type", ""))
    lines.append("- motion_axis: `%s`" % motion.get("axis", ""))
    lines.append("- winding_connection: `%s`" % winding.get("connection", ""))
    lines.append("- loaded_current_mode: `%s`" % winding.get("loaded_current_mode", ""))
    lines.append("- airgap_layer_count: `%s`" % mesh.get("airgap_layer_count", ""))
    lines.append("- tolerance_cases: `%s`" % ", ".join(verification.get("tolerance_cases", [])))
    lines.append("")
    lines.append("## Created Objects")
    lines.append("")
    for item in summary.get("created_objects", []):
        lines.append("- %s (material=`%s`)" % (item.get("name", ""), item.get("material", "")))
    lines.append("")
    lines.append("## Literature Basis")
    lines.append("")
    for item in summary.get("literature_basis", []):
        lines.append("- %s: %s" % (item.get("source", ""), item.get("guidance", "")))
        lines.append("  link: `%s`" % item.get("link", ""))
    lines.append("")
    lines.append("## Blocking Issues")
    lines.append("")
    baseline_blocking = summary.get("baseline_blocking_issues", [])
    lines.append("### Baseline Solve")
    lines.append("")
    if not baseline_blocking:
        lines.append("- None")
    else:
        for item in baseline_blocking:
            lines.append("- %s" % item)
    lines.append("")
    lines.append("### Validation Template")
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


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "build_sector3d_model_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    paths = config_paths(root, project_cfg)

    artifact_json = os.path.join(root, "artifacts", "sector3d_model_build.json")
    artifact_md = os.path.join(root, "reports", "sector3d_model_build.md")
    backup_path = os.path.join(root, "aedt_projects", "sector3d_template.aedt")

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    if not oProject:
        oProject = oDesktop.NewProject()
        logger.log("No active project was open; created a new project")

    required_design_name = project_cfg["sector_3d"]["design_name"]
    oDesign = _active_design(oProject)
    if oDesign:
        oDesign, _ = _rename_design_if_possible(oProject, oDesign, required_design_name, logger)
    oDesign = ensure_design(
        oProject,
        required_design_name,
        "Maxwell 3D",
        "Transient",
        logger
    )

    baseline = _baseline_variables(project_cfg, search_cfg)
    apply_variables(oDesign, baseline, logger)
    build_result = build_sector_3d_scaffold(oProject, oDesign, project_cfg, baseline, logger, cleanup_first=True)
    save_project(oProject, logger)
    save_result = _save_template_copy(oProject, paths["sector_3d_template"], backup_path, logger, already_saved=True)

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": _safe_call(lambda: oDesign.GetName(), ""),
        "solution_type": get_design_solution_type(oDesign, logger),
        "baseline_variables": baseline,
        "geometry_sanity": _geometry_sanity(project_cfg, baseline),
        "created_objects": build_result.get("created_objects", []),
        "deleted_objects": build_result.get("deleted_objects", []),
        "scaffold_variables": build_result.get("scaffold_variables", {}),
        "physics_contract": build_result.get("physics_contract", physics_contract(project_cfg)),
        "literature_basis": build_result.get("literature_basis", literature_basis()),
        "baseline_blocking_issues": build_result.get("baseline_blocking_issues", []),
        "blocking_issues": build_result.get("blocking_issues", []),
        "warnings": build_result.get("warnings", []),
        "baseline_ready_for_solve": bool(build_result.get("baseline_ready_for_solve", False)),
        "physics_ready_for_validation": not bool(build_result.get("blocking_issues", [])),
        "manual_actions": build_result.get("manual_actions", []),
        "saved_template_path": save_result.get("saved_template_path", ""),
        "backup_copy_path": save_result.get("backup_copy_path", "")
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote sector 3D model build summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
