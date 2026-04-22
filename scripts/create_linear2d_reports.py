from __future__ import print_function

import os
import csv

from aedt_native_common import Logger
from aedt_native_common import ensure_dir
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import export_report_csv
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import pyaedt_attach
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from bootstrap_linear2d_template import REQUIRED_REPORT_KEYS_2D
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _list_report_names
from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call


REPORT_MATCH_RULES = {
    "torque_loaded": {
        "exact": ["Torque", "Moving1.Torque"],
        "contains": ["torque", "force"]
    },
    "torque_cogging": {
        "exact": ["Torque", "Moving1.Torque"],
        "contains": ["torque", "force"]
    },
    "flux_linkage_a": {
        "exact": ["FluxLinkage(PhaseA_Winding)", "FluxLinkage(PhaseA)", "FluxLinkage", "Psi"],
        "contains": ["fluxlinkage", "flux linkage", "psi", "winding"]
    },
    "back_emf_ll": {
        "exact": ["Back EMF", "BackEMF", "InducedVoltage", "LineVoltage", "InducedVoltage(PhaseA_Winding)"],
        "contains": ["back emf", "backemf", "inducedvoltage", "induced voltage", "line voltage", "voltage", "winding"]
    },
    "bmax_backiron": {
        "exact": ["Mag_B", "B", "B_Mag"],
        "contains": ["mag_b", "|b|", "flux density", "b"]
    }
}


def _write_markdown(path, summary):
    lines = []
    lines.append("# Linear2D Report Creation Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- setup_name: `%s`" % summary.get("setup_name", ""))
    lines.append("- preferred_solution: `%s`" % summary.get("preferred_solution", ""))
    lines.append("")
    lines.append("## Report Results")
    lines.append("")
    for item in summary.get("report_results", []):
        lines.append(
            "- %s: created=`%s`, reused=`%s`, export_ok=`%s`, category=`%s`, quantity=`%s`, context=`%s`, note=`%s`" % (
                item.get("report_name", ""),
                item.get("created", False),
                item.get("reused", False),
                item.get("export_ok", False),
                item.get("report_category", ""),
                item.get("quantity", ""),
                item.get("context", ""),
                item.get("note", "")
            )
        )
    lines.append("")
    lines.append("## Available Report Types")
    lines.append("")
    for name in summary.get("available_report_types", []):
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


def _clean_list(items):
    out = []
    seen = {}
    for item in items or []:
        text = str(item)
        if text in seen:
            continue
        seen[text] = True
        out.append(text)
    return out


def _preferred_solution(app, setup_name, report_category):
    solutions = _clean_list(_safe_call(lambda: app.post.available_report_solutions(report_category), []))
    for name in solutions:
        if setup_name in name:
            return name
    nominal = _safe_call(lambda: app.nominal_adaptive, "")
    if nominal and ((not solutions) or (nominal in solutions)):
        return nominal
    if solutions:
        return solutions[0]
    return setup_name


def _ordered_report_types(available_report_types, preferred_report_types):
    ordered = []
    preferred_lookup = [str(item).lower() for item in preferred_report_types or []]
    for preferred in preferred_lookup:
        for report_type in available_report_types:
            if str(report_type).lower() == preferred and report_type not in ordered:
                ordered.append(report_type)
    for report_type in available_report_types:
        if report_type not in ordered:
            ordered.append(report_type)
    return ordered


def _available_quantities_for_context(app, report_category, solution_name, context):
    display_type = "Rectangular Plot"
    quantity_categories = _clean_list(
        _safe_call(
            lambda: app.post.available_quantities_categories(
                report_category=report_category,
                display_type=display_type,
                solution=solution_name,
                context=context
            ),
            []
        )
    )
    out = []
    if not quantity_categories:
        quantity_categories = [None]
    for quantity_category in quantity_categories:
        quantities = _clean_list(
            _safe_call(
                lambda: app.post.available_report_quantities(
                    report_category=report_category,
                    display_type=display_type,
                    solution=solution_name,
                    quantities_category=quantity_category,
                    context=context
                ),
                []
            )
        )
        for quantity in quantities:
            out.append(
                {
                    "quantity": quantity,
                    "quantity_category": quantity_category or ""
                }
            )
    return out


def _match_score(quantity, rules):
    text = str(quantity).strip()
    text_lower = text.lower()
    best = 0
    for candidate in rules.get("exact", []):
        if text_lower == candidate.lower():
            return 100
    for candidate in rules.get("contains", []):
        token = candidate.lower()
        if token and (token in text_lower):
            score = 60 + min(len(token), 20)
            if score > best:
                best = score
    return best


def _object_names(app):
    return _clean_list(_safe_call(lambda: list(app.modeler.object_names), []))


def _candidate_contexts(report_key, object_names):
    contexts = [None]
    if report_key in ["flux_linkage_a", "back_emf_ll"]:
        for name in ["PhaseA_Winding", "PhaseA_Coil_Pos", "PhaseA_Coil_Neg"]:
            contexts.append(name)
    if report_key == "bmax_backiron":
        for name in ["Auto2D_BackIron", "BackIron"]:
            if name in object_names:
                contexts.append(name)
    return contexts


def _find_report_match(app, report_key, setup_name, object_names, available_report_types, preferred_report_types):
    rules = REPORT_MATCH_RULES[report_key]
    best = None
    for report_category in _ordered_report_types(available_report_types, preferred_report_types):
        solution_name = _preferred_solution(app, setup_name, report_category)
        for context in _candidate_contexts(report_key, object_names):
            quantities = _available_quantities_for_context(app, report_category, solution_name, context)
            for item in quantities:
                score = _match_score(item["quantity"], rules)
                if not score:
                    continue
                match = {
                    "report_category": report_category,
                    "solution_name": solution_name,
                    "context": context,
                    "quantity": item["quantity"],
                    "quantity_category": item["quantity_category"],
                    "score": score
                }
                if (not best) or (score > best["score"]):
                    best = match
    return best


def _create_named_report(app, oDesign, report_name, match, export_dir, logger):
    export_csv = os.path.join(export_dir, "%s.csv" % report_name)
    app.post.delete_report(report_name)
    is_transient = str(match.get("report_category", "")).lower() == "transient" or "transient" in str(match.get("solution_name", "")).lower()
    domain = "Time" if is_transient else "Sweep"
    primary_sweep_variable = "Time" if is_transient else None
    variations = {"Time": ["All"]} if is_transient else None
    try:
        created = app.post.create_report(
            expressions=match["quantity"],
            setup_sweep_name=match["solution_name"],
            domain=domain,
            variations=variations,
            primary_sweep_variable=primary_sweep_variable,
            report_category=match["report_category"],
            plot_type="Rectangular Plot",
            context=match["context"],
            plot_name=report_name,
            show=False
        )
        export_ok = False
        note = "created from discovered quantity using domain=%s" % domain
        solution_data = None
        try:
            if created:
                solution_data = created.get_solution_data()
                if solution_data:
                    logger.log(
                        "Fetched solution data for %s: primary_sweep=%s, expressions=%s"
                        % (
                            report_name,
                            getattr(solution_data, "primary_sweep", ""),
                            getattr(solution_data, "expressions", [])
                        )
                    )
                else:
                    logger.log("No solution data available for report %s" % report_name)
        except Exception as exc:
            logger.log("Report object solution-data fetch failed for %s: %s" % (report_name, exc))
        if solution_data:
            try:
                export_ok = bool(solution_data.export_data_to_csv(export_csv, delimiter=","))
                if export_ok and os.path.isfile(export_csv):
                    logger.log("Exported report data through SolutionData -> %s" % export_csv)
                else:
                    export_ok = False
            except Exception as exc:
                logger.log("SolutionData CSV export failed for %s: %s" % (report_name, exc))
            if (not export_ok) and solution_data:
                try:
                    sweep_name = getattr(solution_data, "primary_sweep", "") or "Time"
                    sweep_values = list(getattr(solution_data, "primary_sweep_values", []))
                    y_values = list(solution_data.get_expression_data(match["quantity"])[1])
                    if sweep_values and y_values and (len(sweep_values) == len(y_values)):
                        with open(export_csv, "w", newline="") as handle:
                            writer = csv.writer(handle)
                            writer.writerow([sweep_name, match["quantity"]])
                            for x_value, y_value in zip(sweep_values, y_values):
                                writer.writerow([x_value, y_value])
                        export_ok = os.path.isfile(export_csv)
                        if export_ok:
                            logger.log("Exported report data through manual CSV fallback -> %s" % export_csv)
                except Exception as exc:
                    logger.log("Manual CSV fallback failed for %s: %s" % (report_name, exc))
        if not export_ok:
            export_ok = export_report_csv(oDesign, report_name, export_csv, logger)
            if export_ok:
                note = "%s | fallback ExportToFile succeeded" % note
            else:
                note = "%s | no CSV written by SolutionData, manual fallback, or ExportToFile" % note
        return {
            "created": bool(created),
            "export_ok": export_ok,
            "export_csv_path": export_csv if export_ok else "",
            "note": note
        }
    except Exception as exc:
        return {
            "created": False,
            "export_ok": False,
            "export_csv_path": "",
            "note": str(exc)
        }


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "create_linear2d_reports_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "linear2d_reports_creation.json")
    artifact_md = os.path.join(root, "reports", "linear2d_reports_creation.md")
    export_dir = os.path.join(root, "artifacts", "linear2d_report_exports")
    ensure_dir(export_dir)

    required_design_name = project_cfg["linear_2d"]["design_name"]
    setup_name = project_cfg["linear_2d"]["analysis_setup_name"]
    preferred_report_types = project_cfg["linear_2d"].get("preferred_report_types", [])
    reports_cfg = project_cfg["reports"]

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = _attach_maxwell2d(oDesktop, oProject, oDesign, logger)
    existing_reports = _list_report_names(oDesign, logger)
    available_report_types = _clean_list(_safe_call(lambda: list(app.post.available_report_types), []))
    object_names = _object_names(app)
    manual_actions = []
    report_results = []

    if not available_report_types:
        manual_actions.append("Run Setup_2D once before attempting automatic report creation")
    if "Transient" not in available_report_types:
        manual_actions.append("Transient report type is not exposed yet. Verify that Linearized2D uses a transient solution type and solve Setup_2D once")

    shared_torque_match = None
    for report_key in project_cfg["reports"].keys():
        report_name = reports_cfg[report_key]
        had_existing_report = report_name in existing_reports
        result = {
            "report_key": report_key,
            "report_name": report_name,
            "created": False,
            "reused": False,
            "export_ok": False,
            "export_csv_path": "",
            "report_category": "",
            "quantity": "",
            "quantity_category": "",
            "context": "",
            "solution_name": "",
            "note": ""
        }

        if had_existing_report:
            result["note"] = "existing report deleted and recreated"

        match = _find_report_match(app, report_key, setup_name, object_names, available_report_types, preferred_report_types)
        if (not match) and (report_key == "torque_cogging") and shared_torque_match:
            match = dict(shared_torque_match)
            result["note"] = "reused loaded torque quantity as a placeholder for cogging"

        if (not match) and (report_key == "torque_loaded"):
            for other in report_results:
                if other.get("report_key") == "torque_loaded" and other.get("quantity"):
                    match = {
                        "report_category": other.get("report_category", ""),
                        "solution_name": other.get("solution_name", ""),
                        "context": other.get("context") or None,
                        "quantity": other.get("quantity", ""),
                        "quantity_category": other.get("quantity_category", ""),
                        "score": 1
                    }
                    break

        if not match:
            result["note"] = result["note"] or "no matching quantity found automatically"
            manual_actions.append("Manually create report %s in AEDT" % report_name)
            report_results.append(result)
            continue

        result["report_category"] = match["report_category"]
        result["quantity"] = match["quantity"]
        result["quantity_category"] = match["quantity_category"]
        result["context"] = match["context"] or ""
        result["solution_name"] = match["solution_name"]

        created = _create_named_report(app, oDesign, report_name, match, export_dir, logger)
        result["created"] = created["created"]
        result["export_ok"] = created["export_ok"]
        result["export_csv_path"] = created["export_csv_path"]
        if result["note"]:
            result["note"] = "%s | %s" % (result["note"], created["note"])
        else:
            result["note"] = created["note"]

        if (report_key == "torque_loaded") and result["quantity"]:
            shared_torque_match = dict(match)

        if (not result["created"]) or (not result["export_ok"]):
            manual_actions.append(
                "Review report %s manually; selected category=%s quantity=%s context=%s" % (
                    report_name,
                    result["report_category"],
                    result["quantity"],
                    result["context"]
                )
            )
        report_results.append(result)

    missing_required = []
    for key in REQUIRED_REPORT_KEYS_2D:
        report_name = reports_cfg[key]
        ok = False
        for item in report_results:
            if item["report_name"] == report_name and (item["created"] or item["reused"]):
                ok = True
                break
        if not ok:
            missing_required.append(report_name)

    if missing_required:
        manual_actions.append("Required 2D reports still missing: %s" % ", ".join(missing_required))
    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))
    manual_actions.append("Torque_Cogging is currently only a named report target; true cogging extraction still needs a zero-current transient solve path")

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "required_design_name": required_design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "setup_name": setup_name,
        "preferred_solution": _safe_call(lambda: app.nominal_adaptive, ""),
        "available_report_types": available_report_types,
        "existing_reports_before": existing_reports,
        "object_names": object_names,
        "report_results": report_results,
        "manual_actions": manual_actions
    }
    save_project(oProject, logger)
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote report creation summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
