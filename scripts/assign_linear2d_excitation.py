from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import pyaedt_attach
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call


COIL_OBJECTS = [
    {
        "object_name": "Auto2D_Coil_Pos",
        "boundary_name": "Current_Coil_Pos",
        "coil_name": "PhaseA_Coil_Pos",
        "swap_direction": False,
        "polarity": "Positive"
    },
    {
        "object_name": "Auto2D_Coil_Neg",
        "boundary_name": "Current_Coil_Neg",
        "coil_name": "PhaseA_Coil_Neg",
        "swap_direction": True,
        "polarity": "Negative"
    }
]


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Excitation Assignment Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- save_ok: `%s`" % summary.get("save_ok", False))
    lines.append("")
    lines.append("## Object Checks")
    lines.append("")
    for item in summary.get("object_checks", []):
        lines.append("- %s: exists=`%s`" % (item.get("object_name", ""), item.get("exists", False)))
    lines.append("")
    lines.append("## Boundary Results")
    lines.append("")
    for item in summary.get("boundary_results", []):
        lines.append(
            "- %s on %s: assigned=`%s`, deleted_existing=`%s`, direction_reversed=`%s`, details=`%s`" % (
                item.get("boundary_name", ""),
                item.get("object_name", ""),
                item.get("assigned", False),
                item.get("deleted_existing", False),
                item.get("swap_direction", False),
                item.get("details", "")
            )
        )
    lines.append("")
    lines.append("## Winding Result")
    lines.append("")
    winding = summary.get("winding_result", {})
    if winding:
        lines.append("- winding_name: `%s`" % winding.get("winding_name", ""))
        lines.append("- assigned: `%s`" % winding.get("assigned", False))
        lines.append("- used_fallback_current_boundaries: `%s`" % winding.get("used_fallback_current_boundaries", False))
        lines.append("- details: `%s`" % winding.get("details", ""))
    else:
        lines.append("- None")
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


def _attach_maxwell2d(oDesktop, oProject, oDesign, logger):
    from ansys.aedt.core import Maxwell2d

    pid = _safe_call(lambda: int(oDesktop.GetProcessID()), 0)
    project_name = _safe_call(lambda: oProject.GetName(), None)
    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    return pyaedt_attach(
        lambda **kwargs: Maxwell2d(**kwargs),
        [
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
            "aedt_process_id": pid if pid else None
        },
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False
        },
        {
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False
        }
        ],
        logger,
        "Maxwell2d",
        new_session=False
    )


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


def _list_current_excitations(app, logger):
    names = _safe_call(lambda: list(app.oboundary.GetExcitationsOfType("Current")), [])
    if names:
        logger.log("Found %d current excitations" % len(names))
    return [str(name) for name in names]


def _list_winding_excitations(app):
    return [str(name) for name in _safe_call(lambda: list(app.oboundary.GetExcitationsOfType("Winding Group")), [])]


def _design_variable_value(oDesign, name, default_value):
    value = _safe_call(lambda: oDesign.GetVariableValue(name), "")
    if not value:
        return default_value
    text = str(value).strip().lower()
    for token in ["mm", "a", "rpm", "deg", "hz", "s"]:
        if text.endswith(token):
            text = text[: -len(token)].strip()
            break
    try:
        return max(1, int(round(float(text))))
    except Exception:
        return default_value


def _delete_named_boundary_if_present(app, boundary_name, logger):
    try:
        app.oboundary.DeleteBoundaries([boundary_name])
        logger.log("Deleted existing boundary named %s" % boundary_name)
        return True
    except Exception:
        return False


def _assign_winding_group(app, oDesign, project_cfg, logger):
    winding_cfg = project_cfg["linear_2d"].get("winding", {})
    winding_name = winding_cfg.get("phase_a_winding_name", "PhaseA_Winding")
    current_expression = winding_cfg.get("current_waveform_expression", "phase_current_rms")
    turns_per_phase = _design_variable_value(oDesign, "turns_per_phase", 2)
    conductors_per_terminal = max(1, int(round(float(turns_per_phase) / 2.0)))
    deleted = _delete_named_boundary_if_present(app, winding_name, logger)
    deleted_pos = _delete_named_boundary_if_present(app, winding_cfg.get("coil_positive_name", "PhaseA_Coil_Pos"), logger)
    deleted_neg = _delete_named_boundary_if_present(app, winding_cfg.get("coil_negative_name", "PhaseA_Coil_Neg"), logger)
    coil_names = []
    for item in COIL_OBJECTS:
        coil = app.assign_coil(
            assignment=[item["object_name"]],
            conductors_number=conductors_per_terminal,
            polarity=item["polarity"],
            name=winding_cfg.get("coil_positive_name", "PhaseA_Coil_Pos") if item["polarity"] == "Positive" else winding_cfg.get("coil_negative_name", "PhaseA_Coil_Neg")
        )
        if not coil:
            raise RuntimeError("Could not create coil terminal for %s" % item["object_name"])
        coil_names.append(coil.name)
        logger.log("Assigned coil terminal %s to %s with polarity %s" % (coil.name, item["object_name"], item["polarity"]))
    winding = app.assign_winding(
        assignment=None,
        winding_type="Current",
        is_solid=False,
        current=current_expression,
        parallel_branches=1,
        name=winding_name
    )
    if not winding:
        raise RuntimeError("Could not create winding group %s" % winding_name)
    app.add_winding_coils(winding.name, coil_names)
    logger.log("Assigned winding group %s with current=%s" % (winding.name, current_expression))
    return {
        "winding_name": winding.name,
        "assigned": True,
        "used_fallback_current_boundaries": False,
        "deleted_existing": any([deleted, deleted_pos, deleted_neg]),
        "coil_names": coil_names,
        "conductors_per_terminal": conductors_per_terminal,
        "current_expression": current_expression,
        "details": "transient-friendly winding group assigned"
    }


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "assign_linear2d_excitation_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "linear2d_excitation_assignment.json")
    artifact_md = os.path.join(root, "reports", "linear2d_excitation_assignment.md")

    required_design_name = project_cfg["linear_2d"]["design_name"]
    current_expression = project_cfg["linear_2d"].get("winding", {}).get("current_waveform_expression", "phase_current_rms")
    manual_actions = []
    object_checks = []
    boundary_results = []
    winding_result = {}

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = _attach_maxwell2d(oDesktop, oProject, oDesign, logger)

    all_objects_exist = True
    for item in COIL_OBJECTS:
        exists = _object_exists(app, item["object_name"])
        object_checks.append({"object_name": item["object_name"], "exists": exists})
        all_objects_exist = all_objects_exist and exists

    if all_objects_exist:
        try:
            winding_result = _assign_winding_group(app, oDesign, project_cfg, logger)
        except Exception as exc:
            logger.log("Winding-group assignment failed; falling back to direct current boundaries")
            logger.log(str(exc))
            winding_result = {
                "winding_name": project_cfg["linear_2d"].get("winding", {}).get("phase_a_winding_name", "PhaseA_Winding"),
                "assigned": False,
                "used_fallback_current_boundaries": True,
                "details": str(exc)
            }
    else:
        winding_result = {
            "winding_name": project_cfg["linear_2d"].get("winding", {}).get("phase_a_winding_name", "PhaseA_Winding"),
            "assigned": False,
            "used_fallback_current_boundaries": True,
            "details": "coil objects missing"
        }

    for item in COIL_OBJECTS:
        exists = any(check["object_name"] == item["object_name"] and check["exists"] for check in object_checks)
        if not exists:
            manual_actions.append("Create or rename the coil object %s before assigning excitation" % item["object_name"])
            boundary_results.append(
                {
                    "object_name": item["object_name"],
                    "boundary_name": item["boundary_name"],
                    "assigned": False,
                    "deleted_existing": False,
                    "swap_direction": item["swap_direction"],
                    "details": "object not found"
                }
            )
            continue

        deleted_existing = _delete_boundary_if_present(app, item["boundary_name"], logger)
        try:
            app.assign_current(
                assignment=item["object_name"],
                amplitude=current_expression,
                solid=False,
                swap_direction=item["swap_direction"],
                name=item["boundary_name"]
            )
            logger.log("Assigned current excitation %s to %s" % (item["boundary_name"], item["object_name"]))
            boundary_results.append(
                {
                    "object_name": item["object_name"],
                    "boundary_name": item["boundary_name"],
                    "assigned": True,
                    "deleted_existing": deleted_existing,
                    "swap_direction": item["swap_direction"],
                    "details": "assigned with amplitude=%s" % current_expression
                }
            )
        except Exception as exc:
            logger.log("Failed to assign current excitation %s" % item["boundary_name"])
            boundary_results.append(
                {
                    "object_name": item["object_name"],
                    "boundary_name": item["boundary_name"],
                    "assigned": False,
                    "deleted_existing": deleted_existing,
                    "swap_direction": item["swap_direction"],
                    "details": str(exc)
                }
            )
            manual_actions.append(
                "Manually assign a current excitation named %s to %s using %s and reversed=%s" % (
                    item["boundary_name"],
                    item["object_name"],
                    current_expression,
                    item["swap_direction"]
                )
            )

    save_ok = True
    try:
        save_project(oProject, logger)
    except Exception:
        save_ok = False

    current_excitations = _list_current_excitations(app, logger)
    winding_excitations = _list_winding_excitations(app)
    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))
    manual_actions.append("Verify that changing phase_current_rms from 3A to 0A changes the loaded torque result")
    manual_actions.append("If the current direction looks flipped, swap the positive/negative current orientation once in AEDT")
    if not winding_result.get("assigned", False):
        manual_actions.append("The model fell back to direct Current boundaries. For flux linkage and back-EMF extraction, prefer a successful winding-group assignment")

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "required_design_name": required_design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "current_expression": current_expression,
        "object_checks": object_checks,
        "boundary_results": boundary_results,
        "winding_result": winding_result,
        "current_excitations": current_excitations,
        "winding_excitations": winding_excitations,
        "save_ok": save_ok,
        "manual_actions": manual_actions
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote excitation assignment summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
