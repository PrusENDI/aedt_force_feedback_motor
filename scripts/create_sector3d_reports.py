from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import ensure_dir
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import export_report_csv
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
from sector3d_aedt import clean_list
from sector3d_aedt import list_excitations_of_type
from sector3d_aedt import list_object_names


REPORT_MATCH_RULES = {
    "torque_loaded": {
        "exact": ["Torque", "Torque_z", "Moving1.Torque"],
        "contains": ["torque", "force"]
    },
    "torque_cogging": {
        "exact": ["Torque", "Torque_z", "Moving1.Torque"],
        "contains": ["torque", "force"]
    },
    "flux_linkage_a": {
        "exact": ["FluxLinkage(PhaseA_Winding)", "FluxLinkage(PhaseA)", "FluxLinkage"],
        "contains": ["fluxlinkage", "flux linkage", "psi", "winding"]
    },
    "back_emf_ll": {
        "exact": ["InducedVoltage(PhaseA_Winding)", "InducedVoltage(PhaseA)", "Back EMF", "BackEMF", "LineVoltage"],
        "contains": ["back emf", "backemf", "inducedvoltage", "line voltage", "voltage"]
    },
    "bmax_backiron": {
        "exact": ["Mag_B", "B", "B_Mag"],
        "contains": ["mag_b", "|b|", "flux density", "b"]
    },
    "inductance_phase_a": {
        "exact": ["L(PhaseA_Winding)", "Inductance(PhaseA_Winding)", "Inductance"],
        "contains": ["inductance", "matrix", " l("]
    },
    "magnet_demag_margin": {
        "exact": ["MagnetDemag", "DemagMargin", "Demagnetization"],
        "contains": ["demag", "demagnet", "margin", "operating point"]
    }
}


DEFAULT_PREFERRED_REPORT_TYPES = ["Transient", "Fields", "Matrix", "Magnetostatic"]


def _write_markdown(path, summary):
    lines = []
    lines.append("# Sector3D Report Creation Summary")
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
            "- %s: created=`%s`, reused=`%s`, export_ok=`%s`, category=`%s`, quantity=`%s`, context=`%s`, note=`%s`"
            % (
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


def _preferred_solution(app, setup_name, report_category):
    solutions = clean_list(_safe_call(lambda: app.post.available_report_solutions(report_category), []))
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
    quantity_categories = clean_list(
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
        quantities = clean_list(
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


def _candidate_contexts(report_key, object_names, winding_names):
    contexts = [None]
    if report_key in ["flux_linkage_a", "back_emf_ll", "inductance_phase_a"]:
        for name in ["PhaseA_Winding", "PhaseA", "PhaseB_Winding", "PhaseC_Winding"]:
            if (name in winding_names) or (name == "PhaseA_Winding"):
                contexts.append(name)
    if report_key == "bmax_backiron":
        for name in ["Auto3D_RotorBackIron_Bottom", "Auto3D_RotorBackIron_Top"]:
            if name in object_names:
                contexts.append(name)
    if report_key == "magnet_demag_margin":
        for name in object_names:
            if str(name).startswith("Auto3D_Magnet_"):
                contexts.append(name)
    return contexts


def _find_report_match(app, report_key, setup_name, object_names, winding_names, available_report_types, preferred_report_types):
    rules = REPORT_MATCH_RULES[report_key]
    best = None
    for report_category in _ordered_report_types(available_report_types, preferred_report_types):
        solution_name = _preferred_solution(app, setup_name, report_category)
        for context in _candidate_contexts(report_key, object_names, winding_names):
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
        if not export_ok:
            export_ok = export_report_csv(oDesign, report_name, export_csv, logger)
            if export_ok:
                note = "created and exported through ReportSetup.ExportToFile"
        return {
            "report_name": report_name,
            "created": True,
            "reused": False,
            "export_ok": export_ok,
            "report_category": match["report_category"],
            "quantity": match["quantity"],
            "context": match["context"] or "",
            "solution_name": match["solution_name"],
            "note": note
        }
    except Exception as exc:
        return {
            "report_name": report_name,
            "created": False,
            "reused": False,
            "export_ok": False,
            "report_category": match.get("report_category", ""),
            "quantity": match.get("quantity", ""),
            "context": match.get("context", "") or "",
            "solution_name": match.get("solution_name", ""),
            "note": "create_report failed: %s" % exc
        }


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "create_sector3d_reports_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "sector3d_reports_creation.json")
    artifact_md = os.path.join(root, "reports", "sector3d_reports_creation.md")
    export_dir = os.path.join(root, "artifacts", "sector3d_report_exports")
    ensure_dir(export_dir)

    required_design_name = project_cfg["sector_3d"]["design_name"]
    setup_name = project_cfg["sector_3d"]["analysis_setup_name"]
    preferred_report_types = project_cfg["sector_3d"].get("preferred_report_types", DEFAULT_PREFERRED_REPORT_TYPES)
    manual_actions = []

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = attach_maxwell3d(oDesktop, oProject, oDesign, logger)
    object_names = list_object_names(app)
    winding_names = list_excitations_of_type(app, "Winding Group")
    available_report_types = clean_list(_safe_call(lambda: app.post.available_report_types, []))
    report_results = []

    for report_key in [
        "torque_loaded",
        "torque_cogging",
        "flux_linkage_a",
        "back_emf_ll",
        "bmax_backiron",
        "inductance_phase_a",
        "magnet_demag_margin"
    ]:
        report_name = project_cfg["reports"].get(report_key, "")
        if not report_name:
            continue
        match = _find_report_match(
            app,
            report_key,
            setup_name,
            object_names,
            winding_names,
            available_report_types,
            preferred_report_types
        )
        if not match:
            manual_actions.append("Could not discover a usable quantity for %s (%s)" % (report_key, report_name))
            report_results.append(
                {
                    "report_name": report_name,
                    "created": False,
                    "reused": False,
                    "export_ok": False,
                    "report_category": "",
                    "quantity": "",
                    "context": "",
                    "solution_name": "",
                    "note": "no matching quantity discovered"
                }
            )
            continue
        report_results.append(_create_named_report(app, oDesign, report_name, match, export_dir, logger))

    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "setup_name": setup_name,
        "preferred_solution": _preferred_solution(app, setup_name, "Transient"),
        "available_report_types": available_report_types,
        "report_results": report_results,
        "manual_actions": manual_actions
    }
    save_project(oProject, logger)
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote sector 3D report creation summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
