from __future__ import print_function

import os
import traceback

from aedt_native_common import Logger
from aedt_native_common import analyze_setup
from aedt_native_common import apply_variables
from aedt_native_common import append_csv_row
from aedt_native_common import close_project
from aedt_native_common import config_paths
from aedt_native_common import copy_template_if_needed
from aedt_native_common import ensure_design
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import export_report_csv
from aedt_native_common import get_design_solution_type
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import open_or_create_project
from aedt_native_common import read_csv_rows
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import solution_type_matches
from aedt_native_common import timestamp_string
from aedt_native_common import waveform_stats
from aedt_native_common import write_csv_rows
from ranking import rank_rows
from sector3d_scaffold import ensure_sector_3d_design
from winding_geometry import design_variables


REQUIRED_REPORT_KEYS_3D_SOLVE = ["torque_loaded", "torque_cogging", "back_emf_ll", "bmax_backiron"]
CONTRACT_REPORT_KEYS_3D = [
    "torque_loaded",
    "torque_cogging",
    "flux_linkage_a",
    "back_emf_ll",
    "bmax_backiron",
    "inductance_phase_a",
    "magnet_demag_margin"
]
REQUIRED_EXPORT_METRIC_KEYS_3D = {
    "torque_loaded": ["torque_loaded_avg", "torque_loaded_p2p", "torque_avg_nm", "torque_ripple_pct"],
    "torque_cogging": ["cogging_peak_nm"],
    "back_emf_ll": ["back_emf_ll_rms_v"],
    "bmax_backiron": ["bmax_backiron_t"]
}


def _float_value(value):
    try:
        return float(value)
    except Exception:
        return value


def _case_numbers(row):
    out = {}
    for key, value in row.items():
        out[key] = _float_value(value)
    return out


def _fieldnames():
    return [
        "case_id",
        "stage",
        "constraint_fail_count",
        "ranking_score",
        "torque_avg_nm",
        "torque_loaded_avg",
        "torque_loaded_p2p",
        "torque_ripple_pct",
        "cogging_peak_nm",
        "torque_constant_nm_per_arms",
        "torque_peak_nm_est",
        "phase_resistance_ohm_20c",
        "phase_resistance_ohm_hot",
        "hot_copper_loss_w",
        "back_emf_ll_rms_v",
        "back_emf_ll_rms_v_est",
        "back_emf_margin_v",
        "bmax_backiron_t",
        "complexity_penalty",
        "magnet_thickness_mm",
        "pole_arc_ratio",
        "airgap_mm",
        "backiron_thickness_mm",
        "coil_radial_span_mm",
        "coil_mean_radius_mm",
        "turns_per_phase",
        "conductor_width_mm",
        "conductor_thickness_mm",
        "parallel_strands",
        "magnet_segments_per_pole"
    ]


def _failure_fieldnames():
    return [
        "case_id",
        "error",
        "traceback",
        "failed_at",
        "magnet_thickness_mm",
        "pole_arc_ratio",
        "airgap_mm",
        "backiron_thickness_mm",
        "coil_radial_span_mm",
        "coil_mean_radius_mm",
        "turns_per_phase",
        "conductor_width_mm",
        "conductor_thickness_mm",
        "parallel_strands",
        "magnet_segments_per_pole"
    ]


def _invalid_case_fieldnames(search_cfg):
    out = ["case_id", "validation_errors"]
    for spec in search_cfg["variables"]:
        out.append(spec["name"])
    return out


def _artifact_paths(root):
    return {
        "preflight_json": os.path.join(root, "artifacts", "sector3d_validation_preflight.json"),
        "invalid_cases_csv": os.path.join(root, "reports", "3d_validation_invalid_cases.csv"),
        "model_build_json": os.path.join(root, "artifacts", "sector3d_model_build.json")
    }


def _list_report_names(oDesign, logger):
    names = []
    try:
        oModule = oDesign.GetModule("ReportSetup")
    except Exception:
        logger.log("ReportSetup module unavailable during 3D preflight")
        return names
    attempts = [
        lambda: oModule.GetAllReportNames(),
        lambda: oModule.ListReports(),
        lambda: oModule.GetAvailableReportNames()
    ]
    for action in attempts:
        try:
            result = action()
            if result:
                names = list(result)
                break
        except Exception:
            continue
    cleaned = []
    seen = {}
    for name in names:
        text = str(name)
        if text in seen:
            continue
        seen[text] = True
        cleaned.append(text)
    logger.log("3D preflight found %d named reports" % len(cleaned))
    return cleaned


def _template_preflight(paths, artifact_paths, project_cfg, oProject, oDesign, logger):
    report_names = _list_report_names(oDesign, logger)
    configured_reports = {}
    missing_required = []
    missing_contract = []
    for key, report_name in project_cfg["reports"].items():
        exists = report_name in report_names
        configured_reports[key] = {
            "report_name": report_name,
            "exists": exists
        }
        if exists:
            continue
        if key in REQUIRED_REPORT_KEYS_3D_SOLVE:
            missing_required.append(report_name)
        if key in CONTRACT_REPORT_KEYS_3D:
            missing_contract.append(report_name)

    project_name = ""
    try:
        project_name = oProject.GetName()
    except Exception:
        project_name = ""

    build_summary = {}
    build_summary_exists = os.path.isfile(artifact_paths["model_build_json"])
    if build_summary_exists:
        try:
            build_summary = load_json(artifact_paths["model_build_json"])
        except Exception:
            logger.log("Could not load sector3d_model_build.json during preflight")
    build_blocking = list(build_summary.get("blocking_issues", []))
    build_warnings = list(build_summary.get("warnings", []))
    actual_solution_type = get_design_solution_type(oDesign, logger)
    expected_solution_type = "Transient"

    result = {
        "checked_at": timestamp_string(),
        "template_mode": bool(project_cfg.get("template_mode", True)),
        "template_path": paths["sector_3d_template"],
        "working_project_path": paths["sector_3d_working"],
        "template_exists": os.path.isfile(paths["sector_3d_template"]),
        "working_project_exists": os.path.isfile(paths["sector_3d_working"]),
        "opened_project_name": project_name,
        "expected_design_name": project_cfg["sector_3d"]["design_name"],
        "expected_solution_type": expected_solution_type,
        "actual_solution_type": actual_solution_type,
        "available_report_names": report_names,
        "configured_reports": configured_reports,
        "missing_required_reports": missing_required,
        "missing_contract_reports": missing_contract,
        "model_build_summary_path": artifact_paths["model_build_json"],
        "model_build_summary_exists": build_summary_exists,
        "model_build_physics_ready_for_validation": bool(build_summary.get("physics_ready_for_validation", False)),
        "model_build_blocking_issues": build_blocking,
        "model_build_warnings": build_warnings
    }

    if result["template_mode"] and (not result["template_exists"]) and (not result["working_project_exists"]):
        raise RuntimeError("3D template preflight failed: neither template nor working project exists")
    if not solution_type_matches(actual_solution_type, expected_solution_type):
        raise RuntimeError(
            "3D template preflight failed: active design solution type is %s, expected %s"
            % (actual_solution_type or "unknown", expected_solution_type)
        )
    if missing_required:
        raise RuntimeError("3D template preflight failed: missing required reports: %s" % ", ".join(missing_required))
    if build_summary_exists and build_blocking:
        raise RuntimeError(
            "3D template preflight failed: latest scaffold build still has blocking issues: %s"
            % " | ".join(build_blocking)
        )
    if (not build_summary_exists) and result["template_mode"]:
        logger.log("3D preflight warning: no sector3d_model_build.json artifact was found; template provenance is weaker than expected")
    return result


def _coerce_numeric(spec, raw_value):
    if raw_value is None:
        raise ValueError("missing value")
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if text == "":
            raise ValueError("blank value")
    value = float(raw_value)
    if spec["type"] == "int":
        rounded = int(round(value))
        if abs(value - rounded) > 1.0e-6:
            raise ValueError("expected integer")
        return rounded
    return value


def _coil_window_is_valid(project_cfg, row):
    outer_radius = float(project_cfg["machine_fixed"]["outer_diameter_mm"]) / 2.0
    inner_radius = float(project_cfg["machine_fixed"]["inner_diameter_mm"]) / 2.0
    mean_radius = float(row["coil_mean_radius_mm"])
    radial_span = float(row["coil_radial_span_mm"])
    coil_inner = mean_radius - 0.5 * radial_span
    coil_outer = mean_radius + 0.5 * radial_span
    return (coil_inner >= inner_radius) and (coil_outer <= outer_radius) and (coil_inner < coil_outer)


def _validate_case_row(raw_case, search_cfg, project_cfg, seen_case_ids):
    errors = []
    case_id = str(raw_case.get("case_id", "")).strip()
    if not case_id:
        errors.append("missing case_id")
    elif case_id in seen_case_ids:
        errors.append("duplicate case_id")
    parsed = {"case_id": case_id}
    for spec in search_cfg["variables"]:
        name = spec["name"]
        try:
            value = _coerce_numeric(spec, raw_case.get(name))
            if value < spec["min"] or value > spec["max"]:
                errors.append("%s out of range [%s, %s]" % (name, spec["min"], spec["max"]))
            parsed[name] = value
        except Exception as exc:
            errors.append("%s invalid: %s" % (name, exc))
    if not errors:
        if float(parsed["airgap_mm"]) <= 0.0:
            errors.append("airgap_mm must be positive")
        if float(parsed["conductor_width_mm"]) <= 0.0:
            errors.append("conductor_width_mm must be positive")
        if float(parsed["conductor_thickness_mm"]) <= 0.0:
            errors.append("conductor_thickness_mm must be positive")
        if int(parsed["turns_per_phase"]) <= 0:
            errors.append("turns_per_phase must be > 0")
        if int(parsed["parallel_strands"]) <= 0:
            errors.append("parallel_strands must be > 0")
        if int(parsed["magnet_segments_per_pole"]) <= 0:
            errors.append("magnet_segments_per_pole must be > 0")
        if not _coil_window_is_valid(project_cfg, parsed):
            errors.append("coil window exceeds available annulus")
    return parsed, errors


def _validate_cases(cases, search_cfg, project_cfg):
    valid_rows = []
    invalid_rows = []
    seen_case_ids = {}
    invalid_names = _invalid_case_fieldnames(search_cfg)
    for raw_case in cases:
        parsed, errors = _validate_case_row(raw_case, search_cfg, project_cfg, seen_case_ids)
        if parsed.get("case_id") and parsed["case_id"] not in seen_case_ids:
            seen_case_ids[parsed["case_id"]] = True
        if errors:
            invalid_row = {}
            for field_name in invalid_names:
                if field_name == "validation_errors":
                    invalid_row[field_name] = " | ".join(errors)
                elif field_name == "case_id":
                    invalid_row[field_name] = parsed.get("case_id", raw_case.get("case_id", ""))
                else:
                    invalid_row[field_name] = raw_case.get(field_name, parsed.get(field_name, ""))
            invalid_rows.append(invalid_row)
        else:
            valid_rows.append(parsed)
    return valid_rows, invalid_rows


def _export_case_reports(oDesign, reports_cfg, case_export_dir, logger):
    exports = {}
    mapping = {
        "torque_loaded": "torque_loaded.csv",
        "torque_cogging": "torque_cogging.csv",
        "back_emf_ll": "back_emf_ll.csv",
        "bmax_backiron": "bmax_backiron.csv"
    }
    for key, filename in mapping.items():
        csv_path = os.path.join(case_export_dir, filename)
        ok = export_report_csv(oDesign, reports_cfg[key], csv_path, logger)
        if ok:
            exports[key] = csv_path
    return exports


def _metrics_from_exports(export_paths):
    row = {}
    if "torque_loaded" in export_paths:
        stats = waveform_stats(export_paths["torque_loaded"])
        row["torque_loaded_avg"] = stats.get("avg", 0.0)
        row["torque_loaded_p2p"] = stats.get("p2p", 0.0)
        row["torque_avg_nm"] = stats.get("avg", 0.0)
        avg_abs = max(abs(stats.get("avg", 0.0)), 1.0e-9)
        row["torque_ripple_pct"] = 100.0 * stats.get("p2p", 0.0) / avg_abs
    if "torque_cogging" in export_paths:
        stats = waveform_stats(export_paths["torque_cogging"])
        row["cogging_peak_nm"] = stats.get("abs_max", 0.0)
    if "back_emf_ll" in export_paths:
        stats = waveform_stats(export_paths["back_emf_ll"])
        row["back_emf_ll_rms_v"] = stats.get("rms", 0.0)
    if "bmax_backiron" in export_paths:
        stats = waveform_stats(export_paths["bmax_backiron"])
        row["bmax_backiron_t"] = stats.get("max", 0.0)
    return row


def _missing_metric_exports(metrics):
    missing = []
    for report_key, metric_keys in REQUIRED_EXPORT_METRIC_KEYS_3D.items():
        report_ready = True
        for metric_key in metric_keys:
            if metric_key not in metrics:
                report_ready = False
                break
        if not report_ready:
            missing.append(report_key)
    return missing


def _write_recommendation(path, ranked_rows):
    if not ranked_rows:
        return
    top = ranked_rows[0]
    lines = []
    lines.append("# Recommended Design")
    lines.append("")
    lines.append("Top case: `%s`" % top["case_id"])
    lines.append("")
    lines.append("## Key metrics")
    lines.append("")
    lines.append("- torque_avg_nm: %s" % top.get("torque_avg_nm", ""))
    lines.append("- torque_ripple_pct: %s" % top.get("torque_ripple_pct", ""))
    lines.append("- cogging_peak_nm: %s" % top.get("cogging_peak_nm", ""))
    lines.append("- hot_copper_loss_w: %s" % top.get("hot_copper_loss_w", ""))
    lines.append("- back_emf_margin_v: %s" % top.get("back_emf_margin_v", ""))
    lines.append("- bmax_backiron_t: %s" % top.get("bmax_backiron_t", ""))
    lines.append("")
    lines.append("## Geometry variables")
    lines.append("")
    for key in [
        "magnet_thickness_mm",
        "pole_arc_ratio",
        "airgap_mm",
        "backiron_thickness_mm",
        "coil_radial_span_mm",
        "coil_mean_radius_mm",
        "turns_per_phase",
        "conductor_width_mm",
        "conductor_thickness_mm",
        "parallel_strands",
        "magnet_segments_per_pole"
    ]:
        lines.append("- %s: %s" % (key, top.get(key, "")))
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def _processed_case_map(rows):
    out = {}
    for row in rows:
        if row.get("case_id"):
            out[row["case_id"]] = row
    return out


def _host_mode():
    return bool(globals().get("__agent_host_mode", False))


def _progress_callback():
    return globals().get("__command_progress_callback")


def _report_progress(stage, message, details=None):
    callback = _progress_callback()
    if callback:
        callback(stage, message, details or {})


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "sector_3d_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    scoring_cfg = load_json(os.path.join(root, "config", "scoring.json"))
    paths = config_paths(root, project_cfg)
    artifact_paths = _artifact_paths(root)
    fieldnames = _fieldnames()
    failure_fieldnames = _failure_fieldnames()
    invalid_case_fieldnames = _invalid_case_fieldnames(search_cfg)
    run_policy = project_cfg["run_policy"]
    resume_batches = bool(run_policy.get("resume_batches", True))
    continue_on_case_error = bool(run_policy.get("continue_on_case_error", True))
    stop_on_first_error = bool(run_policy.get("stop_on_first_error", False))
    host_mode = _host_mode()

    cases = read_csv_rows(paths["validation_cases_csv"])
    logger.log("Loaded %d raw 3D validation cases" % len(cases))
    valid_cases, invalid_cases = _validate_cases(cases, search_cfg, project_cfg)
    write_csv_rows(artifact_paths["invalid_cases_csv"], invalid_cases, invalid_case_fieldnames)
    if invalid_cases:
        logger.log("Found %d invalid 3D validation cases during precheck" % len(invalid_cases))
    if not valid_cases:
        raise RuntimeError("3D case precheck failed: no valid validation cases remain")
    validate_top_n = int(project_cfg["sector_3d"]["validate_top_n"])
    cases = valid_cases[:validate_top_n]
    logger.log("Prepared %d validated 3D cases after precheck and top-N truncation" % len(cases))

    existing_summary_rows = read_csv_rows(paths["validation_summary_csv"]) if resume_batches else []
    processed_map = _processed_case_map(existing_summary_rows)
    pending_cases = []
    for raw_case in cases:
        if raw_case.get("case_id") in processed_map:
            continue
        pending_cases.append(raw_case)
    logger.log("3D validation pending cases: %d" % len(pending_cases))
    _report_progress(
        "run_3d_validation",
        "Prepared 3D validation queue",
        {"total_cases": len(cases), "pending_cases": len(pending_cases), "resumed_cases": len(processed_map)}
    )

    oDesktop = initialize_aedt(logger)
    copy_template_if_needed(paths["sector_3d_template"], paths["sector_3d_working"], logger)
    oProject = open_or_create_project(oDesktop, paths["sector_3d_working"], logger)
    oDesign = ensure_design(
        oProject,
        project_cfg["sector_3d"]["design_name"],
        "Maxwell 3D",
        "Transient",
        logger
    )
    preflight = _template_preflight(paths, artifact_paths, project_cfg, oProject, oDesign, logger)
    save_json(artifact_paths["preflight_json"], preflight)
    _report_progress(
        "run_3d_validation_preflight",
        "3D validation preflight complete",
        {
            "pending_cases": len(pending_cases),
            "invalid_cases": len(invalid_cases),
            "missing_required_reports": len(preflight.get("missing_required_reports", []))
        }
    )

    summary_rows = list(existing_summary_rows)
    failure_rows = read_csv_rows(paths["validation_failures_csv"]) if (resume_batches and os.path.isfile(paths["validation_failures_csv"])) else []
    autosave_period = int(run_policy["autosave_every_n_cases"])
    base_variables = design_variables(project_cfg)
    base_variables["speed_rpm"] = project_cfg["machine_fixed"]["max_speed_rpm"]
    base_variables["phase_current_rms"] = project_cfg["machine_fixed"]["continuous_phase_current_arms"]

    case_index = 0
    new_case_count = 0
    for raw_case in pending_cases:
        case_index += 1
        case_row = _case_numbers(raw_case)
        logger.log("Starting 3D case %s" % case_row["case_id"])
        _report_progress(
            "run_3d_validation_case",
            "Running 3D case",
            {
                "case_id": case_row["case_id"],
                "case_index": case_index,
                "pending_cases": len(pending_cases)
            }
        )
        try:
            merged = dict(base_variables)
            merged.update(case_row)
            apply_variables(oDesign, merged, logger)
            if not project_cfg.get("template_mode", True):
                scaffold_result = ensure_sector_3d_design(oProject, oDesign, project_cfg, case_row, logger)
                if scaffold_result.get("blocking_issues"):
                    raise RuntimeError(
                        "3D scaffold is not ready for solve: %s" % " | ".join(scaffold_result.get("blocking_issues", []))
                    )
            analyze_setup(oDesign, project_cfg["sector_3d"]["analysis_setup_name"], logger)

            case_export_dir = os.path.join(root, "exports", "3d", str(case_row["case_id"]))
            export_paths = _export_case_reports(oDesign, project_cfg["reports"], case_export_dir, logger)
            missing_exports = [key for key in REQUIRED_REPORT_KEYS_3D_SOLVE if key not in export_paths]
            if missing_exports:
                raise RuntimeError(
                    "3D solve completed but required report exports are missing: %s"
                    % ", ".join([project_cfg["reports"][key] for key in missing_exports])
                )
            metrics = _metrics_from_exports(export_paths)
            missing_metric_exports = _missing_metric_exports(metrics)
            if missing_metric_exports:
                raise RuntimeError(
                    "3D report exports were created but contain insufficient waveform data for: %s"
                    % ", ".join([project_cfg["reports"][key] for key in missing_metric_exports])
                )
            summary = dict(case_row)
            summary.update(metrics)
            ranked_now = rank_rows(project_cfg, [summary], scoring_cfg, "3D")[0]
            summary_rows.append(ranked_now)
            append_csv_row(paths["validation_summary_csv"], ranked_now, fieldnames)

            if project_cfg["run_policy"]["write_case_json_cache"]:
                save_json(os.path.join(case_export_dir, "case_metadata.json"), ranked_now)

            new_case_count += 1
            _report_progress(
                "run_3d_validation_case_complete",
                "Completed 3D case",
                {
                    "case_id": case_row["case_id"],
                    "completed_new_cases": new_case_count,
                    "pending_cases": len(pending_cases)
                }
            )
        except Exception as exc:
            logger.log("3D case failed: %s" % case_row["case_id"])
            logger.log(traceback.format_exc())
            failure = dict(case_row)
            failure["error"] = str(exc)
            failure["traceback"] = traceback.format_exc()
            failure["failed_at"] = timestamp_string()
            failure_rows.append(failure)
            append_csv_row(paths["validation_failures_csv"], failure, failure_fieldnames)
            _report_progress(
                "run_3d_validation_case_failed",
                "3D case failed",
                {"case_id": case_row["case_id"], "error": str(exc)}
            )
            if stop_on_first_error or (not continue_on_case_error):
                raise

        if autosave_period > 0 and (case_index % autosave_period == 0):
            save_project(oProject, logger)

    ranked_rows = rank_rows(project_cfg, summary_rows, scoring_cfg, "3D")
    write_csv_rows(paths["validation_ranked_csv"], ranked_rows, fieldnames)
    _write_recommendation(paths["recommendation_md"], ranked_rows)
    save_project(oProject, logger)
    if not host_mode:
        close_project(oDesktop, oProject, logger)
    else:
        logger.log("Host mode active; leaving 3D project open")
    logger.log("3D validation complete")
    _report_progress(
        "run_3d_validation_complete",
        "3D validation batch complete",
        {
            "total_ranked": len(ranked_rows),
            "new_cases_completed": new_case_count,
            "failures": len(failure_rows)
        }
    )


if __name__ == "__main__":
    main()
