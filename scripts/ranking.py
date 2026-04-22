from __future__ import print_function

import math

from winding_geometry import effective_conductor_area_mm2


def _float(row, key, default_value=0.0):
    try:
        return float(row.get(key, default_value))
    except Exception:
        return default_value


def mean_radius_mm(project_cfg, row):
    fixed = project_cfg["machine_fixed"]
    return _float(row, "coil_mean_radius_mm", (fixed["outer_diameter_mm"] + fixed["inner_diameter_mm"]) / 4.0)


def pole_pitch_mm(project_cfg):
    fixed = project_cfg["machine_fixed"]
    mean_diameter_mm = (fixed["outer_diameter_mm"] + fixed["inner_diameter_mm"]) / 2.0
    mean_circumference_mm = math.pi * mean_diameter_mm
    return mean_circumference_mm / float(fixed["pole_count"])


def estimate_phase_resistance_20c(project_cfg, row):
    proxy = project_cfg["proxy_models"]
    rho = proxy["copper_resistivity_20c_ohm_m"]
    mean_radius = mean_radius_mm(project_cfg, row)
    pole_pitch = pole_pitch_mm(project_cfg)
    turn_length_factor = proxy["turn_length_factor_vs_mean_radius"]
    end_turn_factor = proxy["end_turn_length_factor_vs_pole_pitch"]
    turns = max(1.0, _float(row, "turns_per_phase", 1.0))
    mean_turn_length_mm = turn_length_factor * mean_radius + end_turn_factor * pole_pitch
    total_length_m = (mean_turn_length_mm * turns) / 1000.0
    area_m2 = effective_conductor_area_mm2(project_cfg, row) * 1.0e-6
    return rho * total_length_m / area_m2


def estimate_hot_resistance(project_cfg, phase_resistance_20c):
    proxy = project_cfg["proxy_models"]
    hot_temperature = proxy["hot_temperature_c"]
    alpha = proxy["copper_tempco_per_c"]
    return phase_resistance_20c * (1.0 + alpha * (hot_temperature - 20.0))


def back_emf_limit_v(project_cfg):
    fixed = project_cfg["machine_fixed"]
    proxy = project_cfg["proxy_models"]
    return fixed["dc_bus_v"] * proxy["line_voltage_rms_limit_from_dc_bus_factor"]


def enrich_row(project_cfg, row, stage_name):
    fixed = project_cfg["machine_fixed"]
    current = fixed["continuous_phase_current_arms"]
    torque_avg = _float(row, "torque_avg_nm")
    if (torque_avg <= 0.0) and _float(row, "torque_loaded_avg", 0.0) > 0.0:
        torque_avg = _float(row, "torque_loaded_avg")
    row["torque_avg_nm"] = torque_avg
    row["torque_peak_nm_est"] = _float(row, "torque_peak_nm_est", torque_avg * fixed["peak_phase_current_arms"] / max(current, 1.0e-9))
    row["torque_constant_nm_per_arms"] = torque_avg / max(current, 1.0e-9)
    phase_resistance = _float(row, "phase_resistance_ohm_20c", 0.0)
    if phase_resistance <= 0.0:
        phase_resistance = estimate_phase_resistance_20c(project_cfg, row)
    row["phase_resistance_ohm_20c"] = phase_resistance
    hot_resistance = estimate_hot_resistance(project_cfg, phase_resistance)
    row["phase_resistance_ohm_hot"] = hot_resistance
    row["hot_copper_loss_w"] = 3.0 * (current ** 2) * hot_resistance
    omega = 2.0 * math.pi * fixed["max_speed_rpm"] / 60.0
    row["back_emf_ll_rms_v_est"] = 0.816 * row["torque_constant_nm_per_arms"] * omega
    row["back_emf_margin_v"] = back_emf_limit_v(project_cfg) - row["back_emf_ll_rms_v_est"]
    if _float(row, "bmax_backiron_t", 0.0) <= 0.0:
        row["bmax_backiron_t"] = _float(row, "bmax_backiron_t_est", 0.0)
    if _float(row, "torque_ripple_pct", 0.0) <= 0.0:
        avg_abs = max(abs(torque_avg), 1.0e-9)
        row["torque_ripple_pct"] = 100.0 * _float(row, "torque_loaded_p2p", 0.0) / avg_abs
    row["complexity_penalty"] = _float(row, "magnet_segments_per_pole", 1.0) - 1.0
    row["stage"] = stage_name
    return row


def hard_constraint_fail_count(row, scoring_cfg):
    cfg = scoring_cfg["hard_constraints"]
    failures = 0
    if _float(row, "torque_avg_nm") < cfg["torque_avg_nm_min"]:
        failures += 1
    if _float(row, "torque_peak_nm_est") < cfg["peak_torque_goal_nm_min"]:
        failures += 1
    if _float(row, "torque_ripple_pct") > cfg["torque_ripple_pct_max"]:
        failures += 1
    if _float(row, "cogging_peak_nm") > cfg["cogging_peak_nm_max"]:
        failures += 1
    if _float(row, "phase_resistance_ohm_20c") < cfg["phase_resistance_ohm_min"]:
        failures += 1
    if _float(row, "phase_resistance_ohm_20c") > cfg["phase_resistance_ohm_max"]:
        failures += 1
    if _float(row, "hot_copper_loss_w") > cfg["hot_copper_loss_w_max"]:
        failures += 1
    if _float(row, "bmax_backiron_t") > cfg["backiron_bmax_t_max"]:
        failures += 1
    if _float(row, "back_emf_margin_v") < cfg["back_emf_margin_v_min"]:
        failures += 1
    return failures


def weighted_score(row, scoring_cfg):
    weights = scoring_cfg["weights"]
    score = 0.0
    score += weights["torque_margin"] * _float(row, "torque_avg_nm")
    score += weights["torque_ripple_pct"] * _float(row, "torque_ripple_pct")
    score += weights["cogging_peak_nm"] * _float(row, "cogging_peak_nm")
    score += weights["hot_copper_loss_w"] * _float(row, "hot_copper_loss_w")
    score += weights["back_emf_margin_v"] * _float(row, "back_emf_margin_v")
    score += weights["backiron_bmax_t"] * _float(row, "bmax_backiron_t")
    score += weights["complexity_penalty"] * _float(row, "complexity_penalty")
    score -= 1000.0 * hard_constraint_fail_count(row, scoring_cfg)
    return score


def rank_rows(project_cfg, rows, scoring_cfg, stage_name):
    enriched = []
    for source in rows:
        row = dict(source)
        enrich_row(project_cfg, row, stage_name)
        row["constraint_fail_count"] = hard_constraint_fail_count(row, scoring_cfg)
        row["ranking_score"] = weighted_score(row, scoring_cfg)
        enriched.append(row)
    return sorted(enriched, key=lambda row: (float(row["constraint_fail_count"]), -float(row["ranking_score"])))
