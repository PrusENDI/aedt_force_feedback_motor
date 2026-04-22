from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import analyze_setup
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
from create_linear2d_reports import _attach_maxwell2d


VERIFY_SIGNALS = [
    {
        "key": "torque_loaded_probe",
        "expression": "Moving1.Force_mag",
        "report_category": "Transient"
    },
    {
        "key": "flux_linkage_a_probe",
        "expression": "FluxLinkage(PhaseA_Winding)",
        "report_category": "Transient"
    },
    {
        "key": "back_emf_probe",
        "expression": "InducedVoltage(PhaseA_Winding)",
        "report_category": "Transient"
    }
]


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Solve Status")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- setup_name: `%s`" % summary.get("setup_name", ""))
    lines.append("- analyze_invoked: `%s`" % summary.get("analyze_invoked", False))
    lines.append("- solve_ok: `%s`" % summary.get("solve_ok", False))
    lines.append("")
    lines.append("## Probe Checks")
    lines.append("")
    for item in summary.get("probe_results", []):
        lines.append(
            "- %s: data_available=`%s`, primary_sweep=`%s`, sample_count=`%s`, note=`%s`" % (
                item.get("key", ""),
                item.get("data_available", False),
                item.get("primary_sweep", ""),
                item.get("sample_count", 0),
                item.get("note", "")
            )
        )
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
    lines.append("## AEDT Messages")
    lines.append("")
    error_messages = summary.get("error_messages", [])
    if not error_messages:
        lines.append("- None")
    else:
        for item in error_messages:
            lines.append("- %s" % item)
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def _preferred_solution_name(setup_name):
    return "%s : Transient" % setup_name


def _desktop_messages(oDesktop, oProject, design_name, level):
    project_name = _safe_call(lambda: oProject.GetName(), "")
    try:
        return [str(item) for item in list(oDesktop.GetMessages(project_name, design_name, level))]
    except Exception:
        return []


def _probe_solution_data(app, setup_name, probe, logger):
    result = {
        "key": probe["key"],
        "expression": probe["expression"],
        "report_category": probe.get("report_category", "Transient"),
        "solution_name": _preferred_solution_name(setup_name),
        "primary_sweep": "",
        "sample_count": 0,
        "data_available": False,
        "note": ""
    }
    try:
        data = app.post.get_solution_data(
            expressions=probe["expression"],
            setup_sweep_name=result["solution_name"],
            domain="Time",
            variations={"Time": ["All"]},
            primary_sweep_variable="Time",
            report_category=result["report_category"]
        )
    except Exception as exc:
        result["note"] = "get_solution_data failed: %s" % exc
        return result

    if not data:
        result["note"] = "no solution data returned"
        logger.log("No solution data returned for %s" % probe["expression"])
        return result

    try:
        result["primary_sweep"] = getattr(data, "primary_sweep", "") or ""
        sweep_values = list(getattr(data, "primary_sweep_values", []))
        y_values = list(data.get_expression_data(probe["expression"])[1])
        result["sample_count"] = min(len(sweep_values), len(y_values))
        result["data_available"] = result["sample_count"] > 0
        if result["data_available"]:
            result["note"] = "solution data available"
            logger.log(
                "Probe %s returned %d samples on sweep %s"
                % (probe["expression"], result["sample_count"], result["primary_sweep"] or "unknown")
            )
        else:
            result["note"] = "solution data object returned, but no samples were found"
            logger.log("Probe %s returned a solution object but no samples" % probe["expression"])
    except Exception as exc:
        result["note"] = "solution data parse failed: %s" % exc
    return result


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "solve_linear2d_setup_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "linear2d_solve_status.json")
    artifact_md = os.path.join(root, "reports", "linear2d_solve_status.md")

    required_design_name = project_cfg["linear_2d"]["design_name"]
    setup_name = project_cfg["linear_2d"]["analysis_setup_name"]

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = _attach_maxwell2d(oDesktop, oProject, oDesign, logger)

    analyze_invoked = False
    solve_ok = False
    manual_actions = []
    error_messages = []
    info_messages = []
    try:
        analyze_invoked = True
        analyze_setup(oDesign, setup_name, logger)
        solve_ok = True
    except Exception as exc:
        manual_actions.append("Setup_2D solve failed: %s" % exc)
        error_messages = _desktop_messages(oDesktop, oProject, design_name, 2)
        info_messages = _desktop_messages(oDesktop, oProject, design_name, 0)
        for item in error_messages[-10:]:
            logger.log("AEDT error message: %s" % item)
        if (not error_messages) and info_messages:
            for item in info_messages[-10:]:
                logger.log("AEDT info message: %s" % item)

    probe_results = []
    for probe in VERIFY_SIGNALS:
        probe_results.append(_probe_solution_data(app, setup_name, probe, logger))

    if not any(item.get("data_available", False) for item in probe_results):
        manual_actions.append("No transient solution data was returned. Recheck that Setup_2D really solved and that the solution contains Time samples.")
    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "setup_name": setup_name,
        "analyze_invoked": analyze_invoked,
        "solve_ok": solve_ok,
        "probe_results": probe_results,
        "manual_actions": manual_actions,
        "error_messages": error_messages,
        "info_messages": info_messages
    }
    save_project(oProject, logger)
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote solve status summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
