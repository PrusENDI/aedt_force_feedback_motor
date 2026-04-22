from __future__ import print_function

import math
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
from assign_linear2d_excitation import _attach_maxwell2d
from build_hooks import ensure_linear_2d_design
from doe_engine import load_or_generate_cases
from doe_engine import write_validation_cases
from linear2d_motion import assign_linear_translate_motion
from ranking import rank_rows
from winding_geometry import design_variables


REQUIRED_REPORT_KEYS_2D = ["torque_loaded", "flux_linkage_a", "back_emf_ll", "bmax_backiron"]


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


def _slice_radius_values(project_cfg, row):
    slice_cfg = project_cfg["linear_2d"].get("radial_slices", {})
    enabled = bool(slice_cfg.get("enabled", False))
    if not enabled:
        return [float(row.get("slice_radius_mm", row.get("coil_mean_radius_mm", 0.0)))]
    positions = slice_cfg.get("relative_positions", [0.5])
    scope = str(slice_cfg.get("radius_scope", "coil_window")).lower()
    if scope == "coil_window":
        mean_radius = float(row["coil_mean_radius_mm"])
        radial_span = float(row["coil_radial_span_mm"])
        radius_min = mean_radius - 0.5 * radial_span
        radius_max = mean_radius + 0.5 * radial_span
    else:
        fixed = project_cfg["machine_fixed"]
        radius_min = 0.5 * float(fixed["inner_diameter_mm"])
        radius_max = 0.5 * float(fixed["outer_diameter_mm"])
    if radius_max <= radius_min:
        return [float(row.get("coil_mean_radius_mm", radius_min))]
    values = []
    seen = {}
    for position in positions:
        alpha = min(max(float(position), 0.0), 1.0)
        radius = radius_min + (radius_max - radius_min) * alpha
        key = round(radius, 6)
        if key in seen:
            continue
        seen[key] = True
        values.append(radius)
    return values or [float(row.get("coil_mean_radius_mm", radius_min))]


def _slice_weights(project_cfg, slice_radii):
    slice_cfg = project_cfg["linear_2d"].get("radial_slices", {})
    mode = str(slice_cfg.get("aggregation", "radius_weighted")).lower()
    power = float(slice_cfg.get("weight_power", 1.0))
    raw = []
    for radius in slice_radii:
        if mode == "equal":
            raw.append(1.0)
        else:
            raw.append(max(float(radius), 1.0e-9) ** power)
    total = sum(raw)
    if total <= 0.0:
        return [1.0 / max(len(slice_radii), 1) for _ in slice_radii]
    return [item / total for item in raw]


def _unit_motor_factor(project_cfg):
    fixed = project_cfg["machine_fixed"]
    slot_count = int(fixed.get("stator_slot_count", 0) or 0)
    pole_count = int(fixed.get("pole_count", 0) or 0)
    if slot_count <= 0 or pole_count <= 0:
        return 1
    return max(1, math.gcd(slot_count, pole_count))


def _weighted_average(items, key, weights, default_value=0.0):
    total = 0.0
    weight_sum = 0.0
    for item, weight in zip(items, weights):
        if key not in item:
            continue
        try:
            value = float(item.get(key, default_value))
        except Exception:
            continue
        total += weight * value
        weight_sum += weight
    if weight_sum <= 0.0:
        return default_value
    return total / weight_sum


def _aggregate_slice_metrics(project_cfg, slice_results):
    if not slice_results:
        return {}
    slice_radii = [item["slice_radius_mm"] for item in slice_results]
    weights = _slice_weights(project_cfg, slice_radii)
    metrics_list = [item.get("metrics", {}) for item in slice_results]
    unit_factor = _unit_motor_factor(project_cfg)
    out = {
        "slice_count": len(slice_results),
        "slice_radius_min_mm": min(slice_radii),
        "slice_radius_max_mm": max(slice_radii),
        "slice_radius_center_mm": _weighted_average(
            [{"value": radius} for radius in slice_radii],
            "value",
            weights,
            default_value=slice_radii[len(slice_radii) // 2]
        ),
        "unit_motor_factor": unit_factor
    }
    torque_avg = _weighted_average(metrics_list, "torque_avg_nm", weights, 0.0) * unit_factor
    torque_loaded_avg = _weighted_average(metrics_list, "torque_loaded_avg", weights, 0.0) * unit_factor
    torque_loaded_p2p = _weighted_average(metrics_list, "torque_loaded_p2p", weights, 0.0) * unit_factor
    cogging_peak = _weighted_average(metrics_list, "cogging_peak_nm", weights, 0.0) * unit_factor
    flux_avg = _weighted_average(metrics_list, "flux_linkage_a_avg", weights, 0.0)
    flux_p2p = _weighted_average(metrics_list, "flux_linkage_a_p2p", weights, 0.0)
    back_emf_rms = _weighted_average(metrics_list, "back_emf_ll_rms_v", weights, 0.0)
    bmax = 0.0
    for metrics in metrics_list:
        try:
            bmax = max(bmax, float(metrics.get("bmax_backiron_t", 0.0)))
        except Exception:
            continue
    out["torque_avg_nm"] = torque_avg
    out["torque_loaded_avg"] = torque_loaded_avg
    out["torque_loaded_p2p"] = torque_loaded_p2p
    out["cogging_peak_nm"] = cogging_peak
    out["flux_linkage_a_avg"] = flux_avg
    out["flux_linkage_a_p2p"] = flux_p2p
    out["back_emf_ll_rms_v"] = back_emf_rms
    out["bmax_backiron_t"] = bmax
    avg_abs = max(abs(torque_avg), 1.0e-9)
    out["torque_ripple_pct"] = 100.0 * torque_loaded_p2p / avg_abs
    return out


def _export_case_reports(oDesign, reports_cfg, case_export_dir, logger):
    exports = {}
    mapping = {
        "torque_loaded": "torque_loaded.csv",
        "torque_cogging": "torque_cogging.csv",
        "flux_linkage_a": "flux_linkage_a.csv",
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
    if "flux_linkage_a" in export_paths:
        stats = waveform_stats(export_paths["flux_linkage_a"])
        row["flux_linkage_a_avg"] = stats.get("avg", 0.0)
        row["flux_linkage_a_p2p"] = stats.get("p2p", 0.0)
    if "bmax_backiron" in export_paths:
        stats = waveform_stats(export_paths["bmax_backiron"])
        row["bmax_backiron_t"] = stats.get("max", 0.0)
    return row


def _fieldnames(search_cfg):
    fixed = [
        "case_id",
        "stage",
        "slice_count",
        "slice_radius_min_mm",
        "slice_radius_max_mm",
        "slice_radius_center_mm",
        "unit_motor_factor",
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
        "flux_linkage_a_avg",
        "flux_linkage_a_p2p",
        "bmax_backiron_t",
        "complexity_penalty",
        "exported_report_count",
        "missing_report_count"
    ]
    names = [spec["name"] for spec in search_cfg["variables"]]
    return fixed + names


def _failure_fieldnames(search_cfg):
    return ["case_id", "error", "traceback", "failed_at"] + [spec["name"] for spec in search_cfg["variables"]]


def _invalid_case_fieldnames(search_cfg):
    return ["case_id", "validation_errors"] + [spec["name"] for spec in search_cfg["variables"]]


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


def _artifact_paths(root):
    return {
        "preflight_json": os.path.join(root, "artifacts", "linear_2d_preflight.json"),
        "progress_json": os.path.join(root, "artifacts", "linear_2d_progress.json"),
        "progress_md": os.path.join(root, "reports", "2d_screening_progress.md"),
        "invalid_cases_csv": os.path.join(root, "reports", "2d_screening_invalid_cases.csv")
    }


def _write_progress_files(paths, payload):
    save_json(paths["progress_json"], payload)
    lines = []
    lines.append("# 2D Screening Progress")
    lines.append("")
    lines.append("- updated_at: `%s`" % payload.get("updated_at", ""))
    lines.append("- status: `%s`" % payload.get("status", ""))
    lines.append("- total_cases: `%s`" % payload.get("total_cases", 0))
    lines.append("- valid_cases: `%s`" % payload.get("valid_cases", 0))
    lines.append("- invalid_cases: `%s`" % payload.get("invalid_cases", 0))
    lines.append("- resumed_cases: `%s`" % payload.get("resumed_cases", 0))
    lines.append("- pending_cases: `%s`" % payload.get("pending_cases", 0))
    lines.append("- completed_new_cases: `%s`" % payload.get("completed_new_cases", 0))
    lines.append("- failed_cases_this_run: `%s`" % payload.get("failed_cases_this_run", 0))
    lines.append("- shortlisted_for_3d: `%s`" % payload.get("shortlisted_for_3d", 0))
    current_case = payload.get("current_case_id")
    if current_case:
        lines.append("- current_case_id: `%s`" % current_case)
    current_index = payload.get("current_case_index")
    if current_index:
        lines.append("- current_case_index: `%s / %s`" % (current_index, payload.get("pending_cases", 0)))
    lines.append("")
    outputs = payload.get("outputs", {})
    if outputs:
        lines.append("## Outputs")
        lines.append("")
        for key in sorted(outputs.keys()):
            lines.append("- %s: `%s`" % (key, outputs[key]))
        lines.append("")
    notes = payload.get("notes", [])
    if notes:
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            lines.append("- %s" % note)
        lines.append("")
    handle = open(paths["progress_md"], "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def _list_report_names(oDesign, logger):
    names = []
    try:
        oModule = oDesign.GetModule("ReportSetup")
    except Exception:
        logger.log("ReportSetup module unavailable during template check")
        return names
    for method_name in ["GetAllReportNames", "GetChildNames"]:
        try:
            method = getattr(oModule, method_name)
            result = method()
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
    logger.log("Template check found %d named reports" % len(cleaned))
    return cleaned


def _template_preflight(paths, project_cfg, oProject, oDesign, logger):
    report_names = _list_report_names(oDesign, logger)
    configured_reports = {}
    missing_required = []
    missing_optional = []
    for key, report_name in project_cfg["reports"].items():
        exists = report_name in report_names
        configured_reports[key] = {
            "report_name": report_name,
            "exists": exists
        }
        if exists:
            continue
        if key in REQUIRED_REPORT_KEYS_2D:
            missing_required.append(report_name)
        else:
            missing_optional.append(report_name)
    project_name = ""
    try:
        project_name = oProject.GetName()
    except Exception:
        project_name = ""
    result = {
        "template_mode": bool(project_cfg.get("template_mode", True)),
        "template_path": paths["linear_2d_template"],
        "working_project_path": paths["linear_2d_working"],
        "template_exists": os.path.isfile(paths["linear_2d_template"]),
        "working_project_exists": os.path.isfile(paths["linear_2d_working"]),
        "opened_project_name": project_name,
        "expected_design_name": project_cfg["linear_2d"]["design_name"],
        "available_report_names": report_names,
        "configured_reports": configured_reports,
        "missing_required_reports": missing_required,
        "missing_optional_reports": missing_optional
    }
    if result["template_mode"] and (not result["template_exists"]) and (not result["working_project_exists"]):
        raise RuntimeError("2D template preflight failed: neither template nor working project exists")
    if missing_required:
        raise RuntimeError("2D template preflight failed: missing required reports: %s" % ", ".join(missing_required))
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
    variable_specs = search_cfg["variables"]
    for spec in variable_specs:
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
    for raw_case in cases:
        parsed, errors = _validate_case_row(raw_case, search_cfg, project_cfg, seen_case_ids)
        if parsed.get("case_id") and parsed["case_id"] not in seen_case_ids:
            seen_case_ids[parsed["case_id"]] = True
        if errors:
            invalid_row = dict(raw_case)
            invalid_row["case_id"] = parsed.get("case_id", raw_case.get("case_id", ""))
            invalid_row["validation_errors"] = " | ".join(errors)
            invalid_rows.append(invalid_row)
        else:
            valid_rows.append(parsed)
    return valid_rows, invalid_rows


def _build_outputs(paths, artifact_paths):
    return {
        "screening_summary_csv": paths["screening_summary_csv"],
        "screening_ranked_csv": paths["screening_ranked_csv"],
        "screening_failures_csv": paths["screening_failures_csv"],
        "screening_invalid_cases_csv": artifact_paths["invalid_cases_csv"],
        "validation_cases_csv": paths["validation_cases_csv"],
        "progress_json": artifact_paths["progress_json"],
        "progress_md": artifact_paths["progress_md"],
        "preflight_json": artifact_paths["preflight_json"]
    }


def _update_progress(progress_paths, progress_state, **patch):
    progress_state.update(patch)
    progress_state["updated_at"] = timestamp_string()
    _write_progress_files(progress_paths, progress_state)


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "linear_2d_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    search_cfg = load_json(os.path.join(root, "config", "search_space.json"))
    scoring_cfg = load_json(os.path.join(root, "config", "scoring.json"))
    paths = config_paths(root, project_cfg)
    artifact_paths = _artifact_paths(root)
    fieldnames = _fieldnames(search_cfg)
    failure_fieldnames = _failure_fieldnames(search_cfg)
    invalid_case_fieldnames = _invalid_case_fieldnames(search_cfg)
    run_policy = project_cfg["run_policy"]
    resume_batches = bool(run_policy.get("resume_batches", True))
    continue_on_case_error = bool(run_policy.get("continue_on_case_error", True))
    stop_on_first_error = bool(run_policy.get("stop_on_first_error", False))
    host_mode = _host_mode()

    cases = load_or_generate_cases(search_cfg, paths["screening_cases_csv"])
    logger.log("Loaded %d 2D screening cases" % len(cases))
    valid_cases, invalid_cases = _validate_cases(cases, search_cfg, project_cfg)
    write_csv_rows(artifact_paths["invalid_cases_csv"], invalid_cases, invalid_case_fieldnames)
    if invalid_cases:
        logger.log("Found %d invalid 2D cases during precheck" % len(invalid_cases))
    if not valid_cases:
        raise RuntimeError("2D case precheck failed: no valid screening cases remain")

    existing_summary_rows = read_csv_rows(paths["screening_summary_csv"]) if resume_batches else []
    processed_map = _processed_case_map(existing_summary_rows)
    pending_cases = []
    for raw_case in valid_cases:
        if raw_case.get("case_id") in processed_map:
            continue
        pending_cases.append(raw_case)
    logger.log("2D screening pending cases: %d" % len(pending_cases))
    progress_state = {
        "status": "preflight_complete",
        "total_cases": len(cases),
        "valid_cases": len(valid_cases),
        "invalid_cases": len(invalid_cases),
        "resumed_cases": len(processed_map),
        "pending_cases": len(pending_cases),
        "completed_new_cases": 0,
        "failed_cases_this_run": 0,
        "shortlisted_for_3d": 0,
        "outputs": _build_outputs(paths, artifact_paths),
        "notes": []
    }
    if invalid_cases:
        progress_state["notes"].append("Invalid cases were excluded before solve; see reports/2d_screening_invalid_cases.csv")
    _update_progress(artifact_paths, progress_state)
    _report_progress(
        "run_2d_screen",
        "Prepared 2D screening queue",
        {
            "total_cases": len(cases),
            "valid_cases": len(valid_cases),
            "invalid_cases": len(invalid_cases),
            "pending_cases": len(pending_cases),
            "resumed_cases": len(processed_map)
        }
    )

    oDesktop = initialize_aedt(logger)
    copy_template_if_needed(paths["linear_2d_template"], paths["linear_2d_working"], logger)
    oProject = open_or_create_project(oDesktop, paths["linear_2d_working"], logger)
    oDesign = ensure_design(
        oProject,
        project_cfg["linear_2d"]["design_name"],
        project_cfg["linear_2d"].get("design_type", "Maxwell 2D"),
        project_cfg["linear_2d"].get("solution_type", "TransientXY"),
        logger
    )
    app = _attach_maxwell2d(oDesktop, oProject, oDesign, logger)
    preflight = _template_preflight(paths, project_cfg, oProject, oDesign, logger)
    preflight["checked_at"] = timestamp_string()
    preflight["valid_case_count"] = len(valid_cases)
    preflight["invalid_case_count"] = len(invalid_cases)
    save_json(artifact_paths["preflight_json"], preflight)
    notes = list(progress_state["notes"])
    if preflight.get("missing_optional_reports"):
        notes.append("Optional reports missing in template: %s" % ", ".join(preflight["missing_optional_reports"]))
    _update_progress(
        artifact_paths,
        progress_state,
        status="running",
        notes=notes
    )

    summary_rows = list(existing_summary_rows)
    failure_rows = read_csv_rows(paths["screening_failures_csv"]) if (resume_batches and os.path.isfile(paths["screening_failures_csv"])) else []
    initial_failure_count = len(failure_rows)
    autosave_period = int(run_policy["autosave_every_n_cases"])
    base_variables = design_variables(project_cfg)
    base_variables["speed_rpm"] = project_cfg["machine_fixed"]["max_speed_rpm"]
    base_variables["phase_current_rms"] = project_cfg["machine_fixed"]["continuous_phase_current_arms"]

    case_index = 0
    new_case_count = 0
    for raw_case in pending_cases:
        case_index += 1
        case_row = _case_numbers(raw_case)
        logger.log("Starting 2D case %s" % case_row["case_id"])
        _update_progress(
            artifact_paths,
            progress_state,
            status="running_case",
            current_case_id=case_row["case_id"],
            current_case_index=case_index
        )
        _report_progress(
            "run_2d_screen_case",
            "Running 2D case",
            {
                "case_id": case_row["case_id"],
                "case_index": case_index,
                "pending_cases": len(pending_cases),
                "completed_new_cases": new_case_count
            }
        )
        try:
            merged = dict(base_variables)
            merged.update(case_row)
            case_export_dir = os.path.join(root, "exports", "2d", str(case_row["case_id"]))
            slice_results = []
            slice_radii = _slice_radius_values(project_cfg, merged)
            for slice_index, slice_radius_mm in enumerate(slice_radii, start=1):
                merged_slice = dict(merged)
                merged_slice["slice_radius_mm"] = slice_radius_mm
                apply_variables(oDesign, merged_slice, logger)
                if not project_cfg.get("template_mode", True):
                    ensure_linear_2d_design(oProject, oDesign, project_cfg, merged_slice, logger)
                motion_result, motion_blocking = assign_linear_translate_motion(app, project_cfg, merged_slice, logger)
                if motion_blocking:
                    raise RuntimeError("; ".join(motion_blocking))
                analyze_setup(oDesign, project_cfg["linear_2d"]["analysis_setup_name"], logger)

                slice_export_dir = case_export_dir
                if len(slice_radii) > 1:
                    slice_export_dir = os.path.join(case_export_dir, "slice_%02d" % slice_index)
                export_paths = _export_case_reports(oDesign, project_cfg["reports"], slice_export_dir, logger)
                metrics = _metrics_from_exports(export_paths)
                slice_results.append(
                    {
                        "slice_index": slice_index,
                        "slice_radius_mm": slice_radius_mm,
                        "motion_result": motion_result,
                        "export_paths": export_paths,
                        "metrics": metrics
                    }
                )

            metrics = _aggregate_slice_metrics(project_cfg, slice_results)
            summary = dict(case_row)
            summary.update(metrics)
            exported_report_count = 0
            missing_report_count = 0
            for slice_result in slice_results:
                count = len(slice_result.get("export_paths", {}))
                exported_report_count += count
                missing_report_count += len(project_cfg["reports"]) - count
            summary["exported_report_count"] = exported_report_count
            summary["missing_report_count"] = missing_report_count
            ranked_now = rank_rows(project_cfg, [summary], scoring_cfg, "2D")[0]
            summary_rows.append(ranked_now)
            append_csv_row(paths["screening_summary_csv"], ranked_now, fieldnames)

            if project_cfg["run_policy"]["write_case_json_cache"]:
                save_json(
                    os.path.join(case_export_dir, "case_metadata.json"),
                    {
                        "case": case_row,
                        "metrics": metrics,
                        "slice_results": slice_results,
                        "ranked_row": ranked_now,
                        "slice_radii_mm": slice_radii
                    }
                )

            new_case_count += 1
            _update_progress(
                artifact_paths,
                progress_state,
                status="running_case_complete",
                completed_new_cases=new_case_count
            )
            _report_progress(
                "run_2d_screen_case_complete",
                "Completed 2D case",
                {
                    "case_id": case_row["case_id"],
                    "completed_new_cases": new_case_count,
                    "pending_cases": len(pending_cases)
                }
            )
        except Exception as exc:
            logger.log("2D case failed: %s" % case_row["case_id"])
            logger.log(traceback.format_exc())
            failure = dict(case_row)
            failure["error"] = str(exc)
            failure["traceback"] = traceback.format_exc()
            failure["failed_at"] = timestamp_string()
            failure_rows.append(failure)
            append_csv_row(paths["screening_failures_csv"], failure, failure_fieldnames)
            _update_progress(
                artifact_paths,
                progress_state,
                status="running_case_failed",
                failed_cases_this_run=len(failure_rows) - initial_failure_count,
                last_failed_case_id=case_row["case_id"]
            )
            _report_progress(
                "run_2d_screen_case_failed",
                "2D case failed",
                {"case_id": case_row["case_id"], "error": str(exc)}
            )
            if stop_on_first_error or (not continue_on_case_error):
                raise

        if autosave_period > 0 and (case_index % autosave_period == 0):
            save_project(oProject, logger)

    ranked_rows = rank_rows(project_cfg, summary_rows, scoring_cfg, "2D")
    write_csv_rows(paths["screening_ranked_csv"], ranked_rows, fieldnames)
    promote_n = int(project_cfg["linear_2d"]["promote_top_n_to_3d"])
    shortlist = []
    for row in ranked_rows[:promote_n]:
        slim = {"case_id": row["case_id"]}
        for spec in search_cfg["variables"]:
            slim[spec["name"]] = row.get(spec["name"])
        shortlist.append(slim)
    write_validation_cases(paths["validation_cases_csv"], shortlist)
    save_project(oProject, logger)
    if not host_mode:
        close_project(oDesktop, oProject, logger)
    else:
        logger.log("Host mode active; leaving 2D project open")
    logger.log("2D screening complete")
    final_notes = list(progress_state.get("notes", []))
    if ranked_rows:
        final_notes.append("Top 2D candidate: %s" % ranked_rows[0].get("case_id"))
    _update_progress(
        artifact_paths,
        progress_state,
        status="complete",
        completed_new_cases=new_case_count,
        failed_cases_this_run=len(failure_rows) - initial_failure_count,
        shortlisted_for_3d=len(shortlist),
        current_case_id="",
        current_case_index=0,
        notes=final_notes
    )
    _report_progress(
        "run_2d_screen_complete",
        "2D screening batch complete",
        {
            "total_ranked": len(ranked_rows),
            "new_cases_completed": new_case_count,
            "failures": len(failure_rows),
            "promoted_to_3d": len(shortlist)
        }
    )


if __name__ == "__main__":
    main()
