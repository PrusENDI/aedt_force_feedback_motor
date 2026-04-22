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
from aedt_native_common import initialize_aedt
from aedt_native_common import load_json
from aedt_native_common import open_or_create_project
from aedt_native_common import read_csv_rows
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string
from aedt_native_common import waveform_stats
from aedt_native_common import write_csv_rows
from build_hooks import ensure_sector_3d_design
from ranking import rank_rows
from winding_geometry import design_variables


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
    scoring_cfg = load_json(os.path.join(root, "config", "scoring.json"))
    paths = config_paths(root, project_cfg)
    fieldnames = _fieldnames()
    failure_fieldnames = _failure_fieldnames()
    run_policy = project_cfg["run_policy"]
    resume_batches = bool(run_policy.get("resume_batches", True))
    continue_on_case_error = bool(run_policy.get("continue_on_case_error", True))
    stop_on_first_error = bool(run_policy.get("stop_on_first_error", False))
    host_mode = _host_mode()

    cases = read_csv_rows(paths["validation_cases_csv"])
    validate_top_n = int(project_cfg["sector_3d"]["validate_top_n"])
    cases = cases[:validate_top_n]
    logger.log("Loaded %d 3D validation cases" % len(cases))

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
                ensure_sector_3d_design(oProject, oDesign, project_cfg, case_row, logger)
            analyze_setup(oDesign, project_cfg["sector_3d"]["analysis_setup_name"], logger)

            case_export_dir = os.path.join(root, "exports", "3d", str(case_row["case_id"]))
            export_paths = _export_case_reports(oDesign, project_cfg["reports"], case_export_dir, logger)
            metrics = _metrics_from_exports(export_paths)
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
