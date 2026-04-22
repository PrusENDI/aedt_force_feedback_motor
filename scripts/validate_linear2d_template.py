from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import config_paths
from aedt_native_common import ensure_dir
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import export_report_csv
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import timestamp_string
from bootstrap_linear2d_template import REQUIRED_REPORT_KEYS_2D
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _baseline_variables
from bootstrap_linear2d_template import _helper_variables
from bootstrap_linear2d_template import _list_report_names
from bootstrap_linear2d_template import _list_setup_names
from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call


def _required_variables(project_cfg, search_cfg):
    names = sorted(_baseline_variables(project_cfg, search_cfg).keys())
    return names


def _optional_helper_variables():
    return sorted(_helper_variables().keys())


def _list_local_variables(oDesign, logger):
    attempts = [
        ("GetProperties", lambda: oDesign.GetProperties("LocalVariableTab", "LocalVariables")),
        ("GetPropNames", lambda: oDesign.GetPropNames("LocalVariableTab", "LocalVariables")),
        ("GetVariables", lambda: oDesign.GetVariables())
    ]
    for label, action in attempts:
        try:
            result = action()
            if result:
                names = []
                seen = {}
                for item in list(result):
                    text = str(item)
                    if text in seen:
                        continue
                    seen[text] = True
                    names.append(text)
                logger.log("Enumerated %d local variables using %s" % (len(names), label))
                return names
        except Exception:
            continue
    logger.log("Could not enumerate local variables through AEDT API")
    return []


def _read_variable_value(oDesign, name):
    attempts = [
        lambda: oDesign.GetPropertyValue("LocalVariableTab", "LocalVariables", name),
        lambda: oDesign.GetVariableValue(name)
    ]
    for action in attempts:
        value = _safe_call(action, None)
        if value not in [None, ""]:
            return str(value)
    return ""


def _project_path_info(oProject):
    return {
        "GetPath": _safe_call(lambda: oProject.GetPath(), ""),
        "GetProjectPath": _safe_call(lambda: oProject.GetProjectPath(), ""),
        "GetProjectFile": _safe_call(lambda: oProject.GetProjectFile(), "")
    }


def _validate_reports(oDesign, report_names, export_dir, report_map, logger):
    items = []
    ensure_dir(export_dir)
    for key in REQUIRED_REPORT_KEYS_2D:
        report_name = report_map[key]
        exists = report_name in report_names
        csv_path = os.path.join(export_dir, "%s.csv" % report_name)
        export_ok = False
        if exists:
            export_ok = export_report_csv(oDesign, report_name, csv_path, logger)
        items.append(
            {
                "report_key": key,
                "report_name": report_name,
                "exists": exists,
                "export_ok": export_ok,
                "export_csv_path": csv_path if export_ok else ""
            }
        )
    return items


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Template Validation Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- template_file_exists: `%s`" % summary.get("template_file_exists", False))
    lines.append("- backup_file_exists: `%s`" % summary.get("backup_file_exists", False))
    lines.append("- setup_exists: `%s`" % summary.get("setup_exists", False))
    lines.append("")
    lines.append("## Project Path Info")
    lines.append("")
    for key in sorted(summary.get("project_path_info", {}).keys()):
        lines.append("- %s: `%s`" % (key, summary["project_path_info"][key]))
    lines.append("")
    lines.append("## Missing Required Variables")
    lines.append("")
    missing_required = summary.get("missing_required_variables", [])
    if not missing_required:
        lines.append("- None")
    else:
        for name in missing_required:
            lines.append("- %s" % name)
    lines.append("")
    lines.append("## Missing Helper Variables")
    lines.append("")
    missing_helpers = summary.get("missing_helper_variables", [])
    if not missing_helpers:
        lines.append("- None")
    else:
        for name in missing_helpers:
            lines.append("- %s" % name)
    lines.append("")
    lines.append("## Report Checks")
    lines.append("")
    for item in summary.get("report_checks", []):
        lines.append(
            "- %s: exists=`%s`, export_ok=`%s`" % (
                item.get("report_name", ""),
                item.get("exists", False),
                item.get("export_ok", False)
            )
        )
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
    logger = Logger(os.path.join(root, "logs", "validate_linear2d_template_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    paths = config_paths(root, project_cfg)

    artifact_json = os.path.join(root, "artifacts", "linear2d_template_validation.json")
    artifact_md = os.path.join(root, "reports", "linear2d_template_validation.md")
    export_dir = os.path.join(root, "artifacts", "linear2d_template_validation_exports")

    required_design_name = project_cfg["linear_2d"]["design_name"]
    required_setup_name = project_cfg["linear_2d"]["analysis_setup_name"]
    required_vars = _required_variables(project_cfg, search_cfg)
    helper_vars = _optional_helper_variables()

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    if not oProject:
        raise RuntimeError("No active AEDT project is open for validation")
    oDesign = _active_design(oProject)
    if not oDesign:
        raise RuntimeError("No active design is open for validation")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    project_name = _safe_call(lambda: oProject.GetName(), "")
    setup_names = _list_setup_names(oDesign, logger)
    report_names = _list_report_names(oDesign, logger)
    local_vars = _list_local_variables(oDesign, logger)
    project_path_info = _project_path_info(oProject)

    required_var_details = []
    missing_required_variables = []
    for name in required_vars:
        exists = (name in local_vars)
        value = _read_variable_value(oDesign, name)
        if (not exists) and value:
            exists = True
        if not exists:
            missing_required_variables.append(name)
        required_var_details.append({"name": name, "exists": exists, "value": value})

    helper_var_details = []
    missing_helper_variables = []
    for name in helper_vars:
        exists = (name in local_vars)
        value = _read_variable_value(oDesign, name)
        if (not exists) and value:
            exists = True
        if not exists:
            missing_helper_variables.append(name)
        helper_var_details.append({"name": name, "exists": exists, "value": value})

    report_checks = _validate_reports(oDesign, report_names, export_dir, project_cfg["reports"], logger)
    missing_reports = [item["report_name"] for item in report_checks if not item["exists"]]
    non_exportable_reports = [item["report_name"] for item in report_checks if item["exists"] and (not item["export_ok"])]

    manual_actions = []
    if design_name != required_design_name:
        manual_actions.append("Rename the active design to %s" % required_design_name)
    if required_setup_name not in setup_names:
        manual_actions.append("Create analysis setup %s" % required_setup_name)
    if missing_required_variables:
        manual_actions.append("Create the missing required variables: %s" % ", ".join(missing_required_variables))
    if missing_helper_variables:
        manual_actions.append("Create the missing helper variables: %s" % ", ".join(missing_helper_variables))
    if missing_reports:
        manual_actions.append("Create the missing named reports: %s" % ", ".join(missing_reports))
    if non_exportable_reports:
        manual_actions.append("Open and fix report exportability for: %s" % ", ".join(non_exportable_reports))
    if not os.path.isfile(paths["linear_2d_template"]):
        manual_actions.append("Save the project to the canonical template path %s" % paths["linear_2d_template"])
    if not os.path.isfile(os.path.join(root, "aedt_projects", "linear2d_template.aedt")):
        manual_actions.append("If desired, keep a duplicate copy at aedt_projects/linear2d_template.aedt")

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": project_name,
        "design_name": design_name,
        "required_design_name": required_design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "setup_name": required_setup_name,
        "setup_exists": (required_setup_name in setup_names),
        "setup_names": setup_names,
        "project_path_info": project_path_info,
        "template_file_exists": os.path.isfile(paths["linear_2d_template"]),
        "template_file_path": paths["linear_2d_template"],
        "backup_file_exists": os.path.isfile(os.path.join(root, "aedt_projects", "linear2d_template.aedt")),
        "backup_file_path": os.path.join(root, "aedt_projects", "linear2d_template.aedt"),
        "required_variables": required_var_details,
        "missing_required_variables": missing_required_variables,
        "helper_variables": helper_var_details,
        "missing_helper_variables": missing_helper_variables,
        "available_reports": report_names,
        "report_checks": report_checks,
        "missing_reports": missing_reports,
        "non_exportable_reports": non_exportable_reports,
        "manual_actions": manual_actions
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote validation summary: %s" % artifact_json)
    logger.log("Wrote validation markdown summary: %s" % artifact_md)


if __name__ == "__main__":
    main()
