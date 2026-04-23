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
from sector3d_aedt import delete_named_boundaries_if_present
from sector3d_aedt import design_variable_number
from sector3d_aedt import ensure_macro_phase_belts
from sector3d_aedt import list_excitations_of_type


PHASE_NAMES = ["PhaseA", "PhaseB", "PhaseC"]


def _phase_expression(project_cfg, phase_name):
    winding_cfg = project_cfg.get("sector_3d", {}).get("winding", {})
    mapping = {
        "PhaseA": winding_cfg.get("phase_a_expression", "phase_current_rms"),
        "PhaseB": winding_cfg.get("phase_b_expression", "phase_current_rms"),
        "PhaseC": winding_cfg.get("phase_c_expression", "phase_current_rms")
    }
    return mapping[phase_name]


def _winding_name(phase_name):
    return "%s_Winding" % phase_name


def _coil_name(phase_name, polarity):
    return "%s_Coil_%s" % (phase_name, "Pos" if polarity == "Positive" else "Neg")


def _coil_terminal_name(phase_name, polarity, index):
    return "%s_%s_%03d" % (_coil_name(phase_name, polarity), "Terminal", int(index))


def _phase_boundary_name_prefix(phase_name):
    return [
        _winding_name(phase_name),
        _coil_name(phase_name, "Positive"),
        _coil_name(phase_name, "Negative"),
        "%s_Current_Pos" % phase_name,
        "%s_Current_Neg" % phase_name,
        "%s_JRadial" % phase_name
    ]


def _write_markdown(path, summary):
    lines = []
    lines.append("# Sector3D Excitation Assignment Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- phase_belt_reused: `%s`" % summary.get("phase_belt_reused", False))
    lines.append("- phase_belt_segment_count: `%s`" % summary.get("phase_belt_segment_count", 0))
    lines.append("")
    lines.append("## Phase Belt Geometry")
    lines.append("")
    lines.append("- phase_belt_angle_deg: `%s`" % summary.get("phase_belt_angle_deg", ""))
    lines.append("- phase_belt_gap_deg: `%s`" % summary.get("phase_belt_gap_deg", ""))
    lines.append("- phase_segment_angle_deg: `%s`" % summary.get("phase_segment_angle_deg", ""))
    lines.append("")
    lines.append("## Winding Results")
    lines.append("")
    for item in summary.get("winding_results", []):
        lines.append(
            "- %s: assigned=`%s`, fallback_current=`%s`, positive_objects=`%s`, negative_objects=`%s`, terminals=`%s`, direct_currents=`%s`, details=`%s`"
            % (
                item.get("phase_name", ""),
                item.get("assigned", False),
                item.get("used_fallback_current_boundaries", False),
                item.get("positive_object_count", 0),
                item.get("negative_object_count", 0),
                item.get("coil_terminal_count", 0),
                item.get("current_boundary_count", 0),
                item.get("details", "")
            )
        )
    lines.append("")
    lines.append("## Current Excitations Seen")
    lines.append("")
    excitations = summary.get("current_excitations", [])
    if not excitations:
        lines.append("- None")
    else:
        for name in excitations:
            lines.append("- %s" % name)
    lines.append("")
    lines.append("## Winding Excitations Seen")
    lines.append("")
    windings = summary.get("winding_excitations", [])
    if not windings:
        lines.append("- None")
    else:
        for name in windings:
            lines.append("- %s" % name)
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


def _assign_phase_with_winding_group(app, phase_name, current_expression, positive_objects, negative_objects, turns_per_phase, logger):
    boundary_names = _phase_boundary_name_prefix(phase_name)
    for index in range(1, max(len(positive_objects), len(negative_objects)) + 1):
        boundary_names.append(_coil_terminal_name(phase_name, "Positive", index))
        boundary_names.append(_coil_terminal_name(phase_name, "Negative", index))
    deleted = delete_named_boundaries_if_present(app, boundary_names, logger)
    conductors_per_terminal = max(1, int(round(max(1.0, turns_per_phase) / float(max(1, len(positive_objects))))))
    coil_terminal_names = []
    for polarity, objects in [("Positive", positive_objects), ("Negative", negative_objects)]:
        for index, object_name in enumerate(objects, 1):
            terminal = app.assign_coil(
                assignment=[object_name],
                conductors_number=conductors_per_terminal,
                polarity=polarity,
                name=_coil_terminal_name(phase_name, polarity, index)
            )
            if not terminal:
                raise RuntimeError("Could not create %s coil terminal %s for %s" % (polarity.lower(), object_name, phase_name))
            coil_terminal_names.append(terminal.name)
    winding = app.assign_winding(
        assignment=None,
        winding_type="Current",
        is_solid=True,
        current=current_expression,
        parallel_branches=1,
        name=_winding_name(phase_name)
    )
    if not winding:
        raise RuntimeError("Could not create winding group for %s" % phase_name)
    app.add_winding_coils(winding.name, coil_terminal_names)
    logger.log("Assigned winding %s with current=%s" % (winding.name, current_expression))
    return {
        "phase_name": phase_name,
        "assigned": True,
        "used_fallback_current_boundaries": False,
        "deleted_existing": bool(deleted),
        "winding_name": winding.name,
        "coil_terminal_count": len(coil_terminal_names),
        "coil_terminal_names": coil_terminal_names,
        "conductors_per_terminal": conductors_per_terminal,
        "positive_object_count": len(positive_objects),
        "negative_object_count": len(negative_objects),
        "details": "segmented radial macro-coil terminals assigned"
    }


def _assign_phase_with_direct_current(app, phase_name, current_expression, positive_objects, negative_objects, logger):
    boundary_names = _phase_boundary_name_prefix(phase_name)
    for index in range(1, max(len(positive_objects), len(negative_objects)) + 1):
        boundary_names.append("%s_Current_Pos_%03d" % (phase_name, index))
        boundary_names.append("%s_Current_Neg_%03d" % (phase_name, index))
    deleted = delete_named_boundaries_if_present(app, boundary_names, logger)
    current_names = []
    for polarity, objects, swap_direction, prefix in [
        ("Positive", positive_objects, False, "%s_Current_Pos" % phase_name),
        ("Negative", negative_objects, True, "%s_Current_Neg" % phase_name)
    ]:
        for index, object_name in enumerate(objects, 1):
            current = app.assign_current(
                assignment=[object_name],
                amplitude=current_expression,
                solid=True,
                swap_direction=swap_direction,
                name="%s_%03d" % (prefix, index)
            )
            if not current:
                raise RuntimeError("Could not create fallback %s current for %s object %s" % (polarity.lower(), phase_name, object_name))
            current_names.append(current.name)
    logger.log("Assigned fallback direct current boundaries for %s" % phase_name)
    return {
        "phase_name": phase_name,
        "assigned": True,
        "used_fallback_current_boundaries": True,
        "deleted_existing": bool(deleted),
        "winding_name": "",
        "current_boundary_count": len(current_names),
        "current_boundary_names": current_names,
        "positive_object_count": len(positive_objects),
        "negative_object_count": len(negative_objects),
        "details": "segmented fallback direct current boundaries assigned"
    }


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "assign_sector3d_excitation_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "sector3d_excitation_assignment.json")
    artifact_md = os.path.join(root, "reports", "sector3d_excitation_assignment.md")

    required_design_name = project_cfg["sector_3d"]["design_name"]
    manual_actions = []
    winding_results = []

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = attach_maxwell3d(oDesktop, oProject, oDesign, logger)
    phase_belts = ensure_macro_phase_belts(app, oDesign, logger)
    turns_per_phase = design_variable_number(oDesign, "turns_per_phase", 1.0)

    for phase_name in PHASE_NAMES:
        positive_objects = phase_belts["phase_groups"].get((phase_name, "Positive"), [])
        negative_objects = phase_belts["phase_groups"].get((phase_name, "Negative"), [])
        if (not positive_objects) or (not negative_objects):
            manual_actions.append("Missing positive/negative macro phase-belt objects for %s" % phase_name)
            winding_results.append(
                {
                    "phase_name": phase_name,
                    "assigned": False,
                    "used_fallback_current_boundaries": False,
                    "positive_object_count": len(positive_objects),
                    "negative_object_count": len(negative_objects),
                    "details": "missing phase-belt geometry"
                }
            )
            continue
        current_expression = _phase_expression(project_cfg, phase_name)
        try:
            result = _assign_phase_with_winding_group(
                app,
                phase_name,
                current_expression,
                positive_objects,
                negative_objects,
                turns_per_phase,
                logger
            )
        except Exception as exc:
            logger.log("Winding assignment failed for %s; falling back to direct current boundaries" % phase_name)
            logger.log(str(exc))
            manual_actions.append("%s winding-group assignment failed, used fallback direct current boundaries" % phase_name)
            try:
                result = _assign_phase_with_direct_current(
                    app,
                    phase_name,
                    current_expression,
                    positive_objects,
                    negative_objects,
                    logger
                )
            except Exception as fallback_exc:
                result = {
                    "phase_name": phase_name,
                    "assigned": False,
                    "used_fallback_current_boundaries": True,
                    "positive_object_count": len(positive_objects),
                    "negative_object_count": len(negative_objects),
                    "details": str(fallback_exc)
                }
        winding_results.append(result)

    if not all(item.get("assigned", False) for item in winding_results):
        manual_actions.append("At least one phase failed to receive a usable excitation. Recheck PyAEDT boundary compatibility before solving Setup_3D.")
    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "phase_belt_reused": bool(phase_belts.get("reused", False)),
        "phase_belt_segment_count": int(phase_belts.get("segment_count", 0)),
        "phase_belt_angle_deg": phase_belts.get("phase_belt_angle_deg", ""),
        "phase_belt_gap_deg": phase_belts.get("phase_belt_gap_deg", ""),
        "phase_segment_angle_deg": phase_belts.get("phase_segment_angle_deg", ""),
        "deleted_objects": phase_belts.get("deleted_objects", []),
        "created_objects": phase_belts.get("created_objects", []),
        "winding_results": winding_results,
        "current_excitations": list_excitations_of_type(app, "Current"),
        "winding_excitations": list_excitations_of_type(app, "Winding Group"),
        "manual_actions": manual_actions
    }
    save_project(oProject, logger)
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote sector 3D excitation summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
