from __future__ import print_function

import os
import shutil
import traceback

from aedt_native_common import Logger
from aedt_native_common import apply_variables
from aedt_native_common import config_paths
from aedt_native_common import ensure_design
from aedt_native_common import ensure_dir
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import get_design_solution_type
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from winding_geometry import design_variables


REQUIRED_REPORT_KEYS_2D = [
    "torque_loaded",
    "flux_linkage_a",
    "back_emf_ll",
    "bmax_backiron",
    "torque_cogging"
]


def _normalize_design_name(name):
    if not name:
        return ""
    return str(name).split(";")[0]


def _safe_call(func, default_value=None):
    try:
        return func()
    except Exception:
        return default_value


def _active_project(oDesktop):
    return _safe_call(lambda: oDesktop.GetActiveProject())


def _active_design(oProject):
    if not oProject:
        return None
    return _safe_call(lambda: oProject.GetActiveDesign())


def _rename_design_if_possible(oProject, oDesign, required_name, logger):
    if not oProject or not oDesign:
        return oDesign, False
    current_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    if current_name == required_name:
        return oDesign, True

    attempts = [
        ("Project.RenameDesignInstance(old,new)", lambda: oProject.RenameDesignInstance(current_name, required_name)),
        ("Design.RenameDesignInstance(new)", lambda: oDesign.RenameDesignInstance(required_name)),
        ("Design.RenameDesign(new)", lambda: oDesign.RenameDesign(required_name))
    ]
    for label, action in attempts:
        try:
            action()
            renamed = _safe_call(lambda: oProject.SetActiveDesign(required_name))
            if renamed:
                logger.log("Renamed active design from %s to %s using %s" % (current_name, required_name, label))
                return renamed, True
        except Exception:
            continue
    logger.log("Could not rename active design from %s to %s automatically" % (current_name, required_name))
    return oDesign, False


def _list_setup_names(oDesign, logger):
    names = []
    try:
        oModule = oDesign.GetModule("AnalysisSetup")
        result = oModule.GetSetups()
        if result:
            names = list(result)
    except Exception:
        logger.log("Could not enumerate analysis setups")
    out = []
    seen = {}
    for name in names:
        text = str(name)
        if text in seen:
            continue
        seen[text] = True
        out.append(text)
    return out


def _ensure_setup(oDesign, project_cfg, setup_name, logger):
    existing = _list_setup_names(oDesign, logger)
    deleted_existing = False
    if setup_name in existing:
        try:
            oModule = oDesign.GetModule("AnalysisSetup")
            oModule.DeleteSetups([setup_name])
            deleted_existing = True
            logger.log("Deleted existing setup %s so it can be recreated as the configured type" % setup_name)
            existing = _list_setup_names(oDesign, logger)
        except Exception:
            logger.log("Could not delete existing setup %s before recreation" % setup_name)
            logger.log(traceback.format_exc())
            return {
                "exists": True,
                "created": False,
                "deleted_existing": False,
                "setup_names": existing
            }
    linear_cfg = project_cfg["linear_2d"]
    setup_type = linear_cfg.get("analysis_setup_type", "Magnetostatic")
    setup_payload = [
        "NAME:%s" % setup_name,
        "Enabled:=", True
    ]
    if setup_type == "Transient":
        transient_cfg = linear_cfg.get("transient", {})
        setup_payload.extend(
            [
                "StopTime:=", transient_cfg.get("stop_time_expression", "electrical_period_s"),
                "TimeStep:=", transient_cfg.get("time_step_expression", "electrical_period_s/48"),
                "SaveFieldsType:=", transient_cfg.get("save_fields_type", "None"),
                "OutputError:=", False
            ]
        )
    try:
        oModule = oDesign.GetModule("AnalysisSetup")
        oModule.InsertSetup(setup_type, setup_payload)
        logger.log("Created analysis setup %s" % setup_name)
        return {
            "exists": True,
            "created": True,
            "deleted_existing": deleted_existing,
            "setup_names": _list_setup_names(oDesign, logger)
        }
    except Exception:
        logger.log("Automatic setup creation failed for %s" % setup_name)
        logger.log(traceback.format_exc())
        return {
            "exists": False,
            "created": False,
            "deleted_existing": deleted_existing,
            "setup_names": existing
        }


def _list_report_names(oDesign, logger):
    names = []
    try:
        oModule = oDesign.GetModule("ReportSetup")
    except Exception:
        logger.log("ReportSetup module unavailable")
        return names
    for method_name in ["GetAllReportNames", "GetChildNames"]:
        try:
            result = getattr(oModule, method_name)()
            if result:
                names = list(result)
                break
        except Exception:
            continue
    out = []
    seen = {}
    for name in names:
        text = str(name)
        if text in seen:
            continue
        seen[text] = True
        out.append(text)
    return out


def _baseline_variables(project_cfg, search_cfg):
    fixed = project_cfg["machine_fixed"]
    out = dict(design_variables(project_cfg))
    out["phase_current_rms"] = fixed["continuous_phase_current_arms"]
    out["speed_rpm"] = fixed["max_speed_rpm"]
    for spec in search_cfg["variables"]:
        out[spec["name"]] = spec["baseline"]
    out["slice_radius_mm"] = search_cfg and out.get("coil_mean_radius_mm", (fixed["outer_diameter_mm"] + fixed["inner_diameter_mm"]) / 4.0)
    return out


def _helper_variables():
    return {
        "outer_radius_mm": "outer_diameter_mm/2",
        "inner_radius_mm": "inner_diameter_mm/2",
        "mean_radius_mm": "coil_mean_radius_mm",
        "mean_diameter_mm": "(outer_diameter_mm + inner_diameter_mm)/2",
        "slice_diameter_mm": "2*slice_radius_mm",
        "pole_pairs": "pole_count/2",
        "pole_pitch_mm": "pi*slice_diameter_mm/pole_count",
        "coil_inner_radius_mm": "coil_mean_radius_mm - coil_radial_span_mm/2",
        "coil_outer_radius_mm": "coil_mean_radius_mm + coil_radial_span_mm/2",
        "period_length_mm": "2*pole_pitch_mm",
        "magnet_arc_mm": "pole_pitch_mm*pole_arc_ratio",
        "mechanical_frequency_hz": "speed_rpm/60",
        "electrical_frequency_hz": "mechanical_frequency_hz*pole_pairs",
        "mechanical_period_s": "1/mechanical_frequency_hz",
        "electrical_period_s": "1/electrical_frequency_hz",
        "transient_stop_time_s": "electrical_period_s",
        "transient_time_step_s": "electrical_period_s/48"
    }


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Template Bootstrap Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name_before: `%s`" % summary.get("design_name_before", ""))
    lines.append("- design_name_after: `%s`" % summary.get("design_name_after", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- solution_type_before: `%s`" % summary.get("solution_type_before", ""))
    lines.append("- solution_type_after: `%s`" % summary.get("solution_type_after", ""))
    lines.append("- saved_template_path: `%s`" % summary.get("saved_template_path", ""))
    lines.append("- backup_copy_path: `%s`" % summary.get("backup_copy_path", ""))
    lines.append("- setup_name: `%s`" % summary.get("setup_name", ""))
    lines.append("- setup_exists: `%s`" % summary.get("setup_exists", False))
    lines.append("- setup_created: `%s`" % summary.get("setup_created", False))
    lines.append("- setup_deleted_existing: `%s`" % summary.get("setup_deleted_existing", False))
    lines.append("")
    lines.append("## Missing Reports")
    lines.append("")
    missing = summary.get("missing_reports", [])
    if not missing:
        lines.append("- None")
    else:
        for name in missing:
            lines.append("- %s" % name)
    lines.append("")
    lines.append("## Manual Actions")
    lines.append("")
    actions = summary.get("manual_actions", [])
    if not actions:
        lines.append("- None")
    else:
        for item in actions:
            lines.append("- %s" % item)
    lines.append("")
    lines.append("## Applied Variables")
    lines.append("")
    for key in sorted(summary.get("baseline_variables", {}).keys()):
        lines.append("- %s = `%s`" % (key, summary["baseline_variables"][key]))
    lines.append("")
    lines.append("## Applied Helper Variables")
    lines.append("")
    for key in sorted(summary.get("helper_variables", {}).keys()):
        lines.append("- %s = `%s`" % (key, summary["helper_variables"][key]))
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def _save_template_copy(oProject, template_path, backup_path, logger, already_saved=False):
    result = {
        "saved_template_path": "",
        "backup_copy_path": "",
        "backup_copy_ok": False,
        "current_project_file": ""
    }
    current_project_file = _safe_call(lambda: oProject.GetProjectFile(), "")
    if not current_project_file:
        current_project_dir = _safe_call(lambda: oProject.GetPath(), "") or _safe_call(lambda: oProject.GetProjectPath(), "")
        current_project_name = _safe_call(lambda: oProject.GetName(), "")
        if current_project_dir and current_project_name:
            filename = current_project_name
            if not filename.lower().endswith(".aedt"):
                filename += ".aedt"
            current_project_file = os.path.join(current_project_dir, filename)
    result["current_project_file"] = current_project_file

    normalized_current = os.path.normcase(os.path.abspath(current_project_file)) if current_project_file else ""
    normalized_template = os.path.normcase(os.path.abspath(template_path))
    normalized_backup = os.path.normcase(os.path.abspath(backup_path))

    try:
        ensure_dir(os.path.dirname(template_path))
        if normalized_current and (normalized_current == normalized_template):
            if already_saved:
                logger.log("Current project already points to canonical template path and caller already saved; skipping duplicate Save")
            else:
                oProject.Save()
                logger.log("Current project already points to canonical template path; used Save instead of SaveAs")
        else:
            oProject.SaveAs(template_path, True)
        result["saved_template_path"] = template_path
        logger.log("Saved project to canonical template path: %s" % template_path)
    except Exception:
        logger.log("SaveAs to canonical template path failed")
        logger.log(traceback.format_exc())
        save_project(oProject, logger)

    if result["saved_template_path"]:
        try:
            if normalized_backup and (normalized_backup == normalized_template):
                logger.log("Backup path matches template path; skipping duplicate copy")
                result["backup_copy_path"] = backup_path
                result["backup_copy_ok"] = True
                return result
            ensure_dir(os.path.dirname(backup_path))
            shutil.copyfile(result["saved_template_path"], backup_path)
            result["backup_copy_path"] = backup_path
            result["backup_copy_ok"] = True
            logger.log("Copied template file to backup path: %s" % backup_path)
        except Exception:
            logger.log("Backup copy sync failed: %s" % backup_path)
            logger.log(traceback.format_exc())
    return result


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "bootstrap_linear2d_template_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    paths = config_paths(root, project_cfg)

    artifact_json = os.path.join(root, "artifacts", "linear2d_template_bootstrap.json")
    artifact_md = os.path.join(root, "reports", "linear2d_template_bootstrap.md")
    backup_path = os.path.join(root, "aedt_projects", "linear2d_template.aedt")

    required_design_name = project_cfg["linear_2d"]["design_name"]
    required_setup_name = project_cfg["linear_2d"]["analysis_setup_name"]
    baseline = _baseline_variables(project_cfg, search_cfg)
    helpers = _helper_variables()

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    if not oProject:
        oProject = oDesktop.NewProject()
        logger.log("No active project was open; created a new project")

    oDesign = _active_design(oProject)
    design_before = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    solution_before = get_design_solution_type(oDesign, logger) if oDesign else ""
    manual_actions = []

    if oDesign:
        oDesign, renamed = _rename_design_if_possible(oProject, oDesign, required_design_name, logger)
        if (not renamed) and (_normalize_design_name(_safe_call(lambda: oDesign.GetName(), "")) != required_design_name):
            manual_actions.append("Manually rename the active design to %s" % required_design_name)

    oDesign = ensure_design(
        oProject,
        required_design_name,
        project_cfg["linear_2d"].get("design_type", "Maxwell 2D"),
        project_cfg["linear_2d"].get("solution_type", "TransientXY"),
        logger
    )

    design_after = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    solution_after = get_design_solution_type(oDesign, logger)
    logger.log("Applying baseline variables to active design")
    apply_variables(oDesign, baseline, logger)
    logger.log("Applying helper variables to active design")
    apply_variables(oDesign, helpers, logger)

    setup_status = _ensure_setup(oDesign, project_cfg, required_setup_name, logger)
    if not setup_status.get("exists"):
        manual_actions.append("Manually create analysis setup %s" % required_setup_name)

    report_names = _list_report_names(oDesign, logger)
    required_reports = [project_cfg["reports"][key] for key in REQUIRED_REPORT_KEYS_2D]
    missing_reports = [name for name in required_reports if name not in report_names]
    if missing_reports:
        manual_actions.append("Create the missing named reports: %s" % ", ".join(missing_reports))
    manual_actions.append("For transient 2D, prefer a winding-style Phase A excitation over loose Current boundaries so FluxLinkage and BackEMF quantities are exposed")
    manual_actions.append("Verify that Setup_2D is a Transient setup and that StopTime/TimeStep resolve to one electrical period with adequate sampling")

    save_result = _save_template_copy(oProject, paths["linear_2d_template"], backup_path, logger)
    if (not save_result.get("saved_template_path")):
        manual_actions.append("Manually save the active project to %s" % paths["linear_2d_template"])
    if (not save_result.get("backup_copy_ok")):
        manual_actions.append("If you still want a duplicate copy, manually save or copy the project to %s" % backup_path)

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name_before": design_before,
        "design_name_after": design_after,
        "design_name_matches_required": (design_after == required_design_name),
        "solution_type_before": solution_before,
        "solution_type_after": solution_after,
        "required_design_name": required_design_name,
        "setup_name": required_setup_name,
        "setup_exists": setup_status.get("exists", False),
        "setup_created": setup_status.get("created", False),
        "setup_deleted_existing": setup_status.get("deleted_existing", False),
        "setup_names": setup_status.get("setup_names", []),
        "baseline_variables": baseline,
        "helper_variables": helpers,
        "required_reports": required_reports,
        "available_reports": report_names,
        "missing_reports": missing_reports,
        "saved_template_path": save_result.get("saved_template_path", ""),
        "backup_copy_path": save_result.get("backup_copy_path", ""),
        "manual_actions": manual_actions
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote bootstrap summary: %s" % artifact_json)
    logger.log("Wrote bootstrap markdown summary: %s" % artifact_md)


if __name__ == "__main__":
    main()
