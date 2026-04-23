from __future__ import print_function


HYBRID_DESIGN_KEYS = [
    "carrier_pcb_board_thickness_mm",
    "carrier_pcb_outer_copper_thickness_mm",
    "carrier_pcb_inner_copper_thickness_mm",
    "stator_support_thickness_mm",
    "flat_copper_active_face_count",
    "flat_copper_physical_layers_per_face",
    "flat_copper_face_bondline_mm",
    "flat_copper_interlayer_insulation_mm",
    "flat_copper_bondline_axial_build_mm",
    "flat_copper_utilization_factor",
    "carrier_pcb_role",
    "flat_copper_stack_mode"
]


def _float(row, key, default_value=0.0):
    try:
        return float(row.get(key, default_value))
    except Exception:
        return default_value


def selected_route(project_cfg):
    fabrication = project_cfg.get("fabrication", {})
    return str(fabrication.get("selected_route", "")).strip()


def is_rigid_pcb_flat_copper_hybrid(project_cfg):
    return selected_route(project_cfg) == "rigid_pcb_flat_copper_hybrid"


def design_variables(project_cfg):
    out = dict(project_cfg.get("machine_fixed", {}))
    hybrid = project_cfg.get("hybrid_winding", {})
    for key in HYBRID_DESIGN_KEYS:
        if key in hybrid:
            out[key] = hybrid[key]
    return out


def parallel_paths(row):
    return max(1.0, _float(row, "parallel_strands", 1.0))


def _hybrid_cfg(project_cfg):
    return project_cfg.get("hybrid_winding", {})


def flat_copper_active_face_count(project_cfg):
    hybrid = _hybrid_cfg(project_cfg)
    return max(1, int(round(float(hybrid.get("flat_copper_active_face_count", 2)))))


def flat_copper_layers_per_face(project_cfg):
    hybrid = _hybrid_cfg(project_cfg)
    return max(1, int(round(float(hybrid.get("flat_copper_physical_layers_per_face", 1)))))


def flat_copper_face_bondline_mm(project_cfg):
    hybrid = _hybrid_cfg(project_cfg)
    return max(
        0.0,
        float(
            hybrid.get(
                "flat_copper_face_bondline_mm",
                hybrid.get("flat_copper_bondline_axial_build_mm", 0.0)
            )
        )
    )


def physical_parallel_path_capacity(project_cfg):
    if is_rigid_pcb_flat_copper_hybrid(project_cfg):
        return float(flat_copper_active_face_count(project_cfg) * flat_copper_layers_per_face(project_cfg))
    return 1.0


def flat_copper_face_pack_height_mm(project_cfg, row):
    thickness_mm = max(0.01, _float(row, "conductor_thickness_mm", 0.01))
    if is_rigid_pcb_flat_copper_hybrid(project_cfg):
        hybrid = _hybrid_cfg(project_cfg)
        layers = float(flat_copper_layers_per_face(project_cfg))
        insulation_mm = max(0.0, float(hybrid.get("flat_copper_interlayer_insulation_mm", 0.0)))
        bondline_mm = flat_copper_face_bondline_mm(project_cfg)
        return thickness_mm * layers + insulation_mm * max(layers - 1.0, 0.0) + bondline_mm
    return thickness_mm * parallel_paths(row)


def flat_copper_pack_height_mm(project_cfg, row):
    if is_rigid_pcb_flat_copper_hybrid(project_cfg):
        return flat_copper_face_pack_height_mm(project_cfg, row) * float(flat_copper_active_face_count(project_cfg))
    thickness_mm = max(0.01, _float(row, "conductor_thickness_mm", 0.01))
    return thickness_mm * parallel_paths(row)


def stator_axial_build_mm(project_cfg, row):
    if is_rigid_pcb_flat_copper_hybrid(project_cfg):
        hybrid = _hybrid_cfg(project_cfg)
        support_mm = max(
            0.0,
            float(hybrid.get("stator_support_thickness_mm", hybrid.get("carrier_pcb_board_thickness_mm", 0.0)))
        )
        return support_mm + flat_copper_pack_height_mm(project_cfg, row)
    thickness_mm = max(0.01, _float(row, "conductor_thickness_mm", 0.01))
    return thickness_mm * parallel_paths(row)


def effective_conductor_area_mm2(project_cfg, row):
    width_mm = max(0.01, _float(row, "conductor_width_mm", 1.0))
    thickness_mm = max(0.01, _float(row, "conductor_thickness_mm", 0.01))
    paths = parallel_paths(row)
    if is_rigid_pcb_flat_copper_hybrid(project_cfg):
        hybrid = project_cfg.get("hybrid_winding", {})
        utilization = max(0.01, float(hybrid.get("flat_copper_utilization_factor", 1.0)))
        return width_mm * thickness_mm * paths * utilization
    proxy = project_cfg.get("proxy_models", {})
    copper_fill_factor = max(0.01, float(proxy.get("copper_fill_factor", 1.0)))
    return width_mm * thickness_mm * paths * copper_fill_factor
