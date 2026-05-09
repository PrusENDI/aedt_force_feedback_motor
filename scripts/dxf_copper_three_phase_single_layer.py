from copy import deepcopy
import math

import dxf_copper_phase_chain
from shapely.geometry import Polygon


def three_phase_default_spec():
    return {
        "milestone": "Milestone 4: Three-Phase Single-Layer Geometry",
        "generation_mode": "three_phase_single_layer",
        "geometry_scope": "v4_three_phase_single_layer_2d",
        "source_generation_mode": "phase_full_layer",
        "source_geometry_scope": "v35_phase_a_full_layer_2d",
        "phase_offsets_deg": {"A": 0.0, "B": 120.0, "C": 240.0},
        "phase_offset_angle_units": "electrical_degrees",
        "pole_pairs_count": 7,
        "trace_gap_mm": 1.0,
        "minimum_phase_to_phase_clearance_mm": 1.0,
        "macro_segment_count": 6,
        "macro_guard_angle_deg": 3.0,
        "radial_lane_count": 4,
        "turn_count_per_macro_segment": 4,
        "radial_wave_min_traverses_per_region": 2,
        "terminal_keepout_radius_mm": 0.75,
    }


def normalize_three_phase_spec(spec):
    normalized = dict(spec)
    pole_pairs_count = normalized.get("pole_pairs_count")
    if not isinstance(pole_pairs_count, int) or pole_pairs_count <= 0:
        raise ValueError("pole_pairs_count must be a positive integer")

    normalized["mechanical_phase_offsets_deg"] = {
        phase: electrical_offset_deg / pole_pairs_count
        for phase, electrical_offset_deg in normalized["phase_offsets_deg"].items()
    }
    return normalized


def _rotate_xy(point, angle_deg):
    x, y = point[0], point[1]
    angle_rad = math.radians(float(angle_deg))
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return [
        float(x) * cos_a - float(y) * sin_a,
        float(x) * sin_a + float(y) * cos_a,
    ]


def _rotate_xyz(point, angle_deg):
    rotated_xy = _rotate_xy(point, angle_deg)
    return [rotated_xy[0], rotated_xy[1], float(point[2])]


def _xy_group_to_xyz(group, z_mm=0.0):
    return [[float(point[0]), float(point[1]), float(z_mm)] for point in group]


def _rotate_xy_group(group, angle_deg):
    return [_rotate_xy(point, angle_deg) for point in group]


def _rotate_xyz_group(group, angle_deg):
    return [_rotate_xyz(point, angle_deg) for point in group]


def _rotate_terminal_records(records, angle_deg):
    rotated_records = []
    for record in records:
        rotated = dict(record)
        if "center_xy_mm" in rotated:
            rotated["center_xy_mm"] = _rotate_xy(rotated["center_xy_mm"], angle_deg)
        rotated_records.append(rotated)
    return rotated_records


def _rotate_a_region_from_phase_a(region, phase, electrical_offset_deg, mechanical_rotation_deg):
    rotated = deepcopy(region)
    if "outline_points_xy_mm" in rotated:
        rotated["outline_points_xy_mm"] = _rotate_xy_group(
            rotated["outline_points_xy_mm"],
            mechanical_rotation_deg,
        )
    if "centerline_points_xy_mm" in rotated:
        rotated["centerline_points_xy_mm"] = _rotate_xy_group(
            rotated["centerline_points_xy_mm"],
            mechanical_rotation_deg,
        )
    if "aedt_polyline_points_mm" in rotated:
        rotated["aedt_polyline_points_mm"] = _rotate_xyz_group(
            rotated["aedt_polyline_points_mm"],
            mechanical_rotation_deg,
        )
    if "terminal_pads" in rotated:
        rotated["terminal_pads"] = _rotate_terminal_records(
            rotated["terminal_pads"],
            mechanical_rotation_deg,
        )
    if "terminals" in rotated:
        rotated["terminals"] = _rotate_terminal_records(
            rotated["terminals"],
            mechanical_rotation_deg,
        )
    rotated["phase"] = phase
    rotated["source_phase"] = "A"
    rotated["electrical_offset_deg"] = float(electrical_offset_deg)
    rotated["mechanical_rotation_deg"] = float(mechanical_rotation_deg)
    return rotated


def _terminal_keepouts_from_geometry(geometry):
    radius_mm = float(geometry.get("terminal_keepout_radius_mm", 0.75))
    keepouts = []
    for phase in geometry.get("phase_order", ["A", "B", "C"]):
        phase_geometry = geometry.get("phases", {}).get(phase, {})
        for region in phase_geometry.get("full_layer_regions", []):
            for pad in region.get("terminal_pads", []):
                center = pad.get("center_xy_mm")
                if not center:
                    continue
                size = pad.get("size_xy_mm", [0.0, 0.0])
                pad_radius = max(float(size[0]), float(size[1])) / 2.0 if len(size) >= 2 else 0.0
                keepouts.append(
                    {
                        "phase": phase,
                        "region_id": region.get("region_id"),
                        "terminal_name": pad.get("name"),
                        "center_xy_mm": [float(center[0]), float(center[1])],
                        "radius_mm": max(radius_mm, pad_radius),
                    }
                )
    return keepouts


def _terminal_keepout_conflicts(keepouts):
    conflicts = []
    for index, keepout_a in enumerate(keepouts):
        for keepout_b in keepouts[index + 1:]:
            if keepout_a["phase"] == keepout_b["phase"]:
                continue
            distance = _segment_length(keepout_a["center_xy_mm"], keepout_b["center_xy_mm"])
            required = keepout_a["radius_mm"] + keepout_b["radius_mm"]
            if distance < required:
                conflicts.append(
                    {
                        "terminal_a": keepout_a["terminal_name"],
                        "terminal_b": keepout_b["terminal_name"],
                        "phase_a": keepout_a["phase"],
                        "phase_b": keepout_b["phase"],
                        "center_distance_mm": float(distance),
                        "required_clearance_mm": float(required),
                    }
                )
    return conflicts


def _polygon_from_region(region):
    points = region.get("outline_points_xy_mm")
    if not points:
        raise ValueError("region missing outline_points_xy_mm")
    polygon = Polygon([(float(point[0]), float(point[1])) for point in points])
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError("region outline_points_xy_mm did not form a valid polygon")
    return polygon


def _phase_polygons(geometry, phase):
    return [_polygon_from_region(region) for region in geometry["phases"][phase]["full_layer_regions"]]


def _phase_pair_metric(geometry, phase_a, phase_b):
    polygons_a = _phase_polygons(geometry, phase_a)
    polygons_b = _phase_polygons(geometry, phase_b)
    overlap_area_mm2 = 0.0
    minimum_clearance_mm = None

    for polygon_a in polygons_a:
        for polygon_b in polygons_b:
            overlap_area_mm2 += float(polygon_a.intersection(polygon_b).area)
            clearance = float(polygon_a.distance(polygon_b))
            if minimum_clearance_mm is None or clearance < minimum_clearance_mm:
                minimum_clearance_mm = clearance

    return {
        "minimum_clearance_mm": float(minimum_clearance_mm),
        "overlap_area_mm2": float(overlap_area_mm2),
    }


def _segment_length(point_a, point_b):
    return math.hypot(float(point_b[0]) - float(point_a[0]), float(point_b[1]) - float(point_a[1]))


def _angular_delta_rad(point_a, point_b):
    angle_a = math.atan2(float(point_a[1]), float(point_a[0]))
    angle_b = math.atan2(float(point_b[1]), float(point_b[0]))
    delta = angle_b - angle_a
    while delta > math.pi:
        delta -= 2.0 * math.pi
    while delta < -math.pi:
        delta += 2.0 * math.pi
    return abs(delta)


def _radial_wave_metrics(centerline_groups):
    dominance_ratio = 1.5
    radial_dominant_length_mm = 0.0
    circumferential_dominant_length_mm = 0.0
    radial_dominant_traverses_by_region = []

    for group in centerline_groups:
        region_traverses = 0
        for start, end in zip(group, group[1:]):
            segment_length = _segment_length(start, end)
            start_radius = math.hypot(float(start[0]), float(start[1]))
            end_radius = math.hypot(float(end[0]), float(end[1]))
            delta_radius = abs(end_radius - start_radius)
            arc_equivalent = ((start_radius + end_radius) / 2.0) * _angular_delta_rad(start, end)
            if delta_radius > arc_equivalent * dominance_ratio:
                radial_dominant_length_mm += segment_length
                region_traverses += 1
            elif arc_equivalent > delta_radius * dominance_ratio:
                circumferential_dominant_length_mm += segment_length
        radial_dominant_traverses_by_region.append(region_traverses)

    total_dominant_length = radial_dominant_length_mm + circumferential_dominant_length_mm
    if total_dominant_length > 0.0:
        radial_wave_score = radial_dominant_length_mm / total_dominant_length
    else:
        radial_wave_score = 0.0

    return {
        "radial_wave_score": float(radial_wave_score),
        "radial_wave_radial_dominant_length_mm": float(radial_dominant_length_mm),
        "radial_wave_circumferential_dominant_length_mm": float(circumferential_dominant_length_mm),
        "radial_wave_radial_dominant_traverses_by_region": radial_dominant_traverses_by_region,
    }


def _phase_metrics(phase_geometry):
    centerline_groups = phase_geometry["full_layer_centerline_points_xy_mm"]
    centerline_length_mm = sum(
        _segment_length(start, end)
        for group in centerline_groups
        for start, end in zip(group, group[1:])
    )
    outline_points = [
        point
        for group in phase_geometry["full_layer_outline_groups_xy_mm"]
        for point in group
    ]
    max_radius_mm = max(math.hypot(float(point[0]), float(point[1])) for point in outline_points)
    copper_area_mm2 = sum(float(_polygon_from_region(region).area) for region in phase_geometry["full_layer_regions"])
    metrics = {
        "copper_area_mm2": float(copper_area_mm2),
        "centerline_length_mm": float(centerline_length_mm),
        "bounding_diameter_mm": float(max_radius_mm * 2.0),
    }
    metrics.update(_radial_wave_metrics(centerline_groups))
    return metrics


def _calculate_phase_pair_metrics(geometry):
    pair_phases = [("A_B", "A", "B"), ("B_C", "B", "C"), ("C_A", "C", "A")]
    return {
        pair_name: _phase_pair_metric(geometry, phase_a, phase_b)
        for pair_name, phase_a, phase_b in pair_phases
    }


def _phase_geometry_from_source(source, phase, electrical_offset_deg, mechanical_rotation_deg):
    regions = [
        _rotate_a_region_from_phase_a(region, phase, electrical_offset_deg, mechanical_rotation_deg)
        for region in source["full_layer_regions"]
    ]
    outline_groups = [_rotate_xy_group(group, mechanical_rotation_deg) for group in source["full_layer_outline_groups_xy_mm"]]
    aedt_regions = [_rotate_xyz_group(group, mechanical_rotation_deg) for group in source["full_layer_aedt_polyline_regions_mm"]]
    centerline_groups = [
        _rotate_xy_group(group, mechanical_rotation_deg)
        for group in source["full_layer_centerline_points_xy_mm"]
    ]
    centerline_points = [point for group in centerline_groups for point in group]
    return {
        "phase": phase,
        "source_phase": "A",
        "electrical_offset_deg": float(electrical_offset_deg),
        "mechanical_rotation_deg": float(mechanical_rotation_deg),
        "full_layer_regions": regions,
        "full_layer_outline_groups_xy_mm": outline_groups,
        "full_layer_outline_groups_xyz_mm": [_xy_group_to_xyz(group) for group in outline_groups],
        "full_layer_aedt_polyline_regions_mm": aedt_regions,
        "full_layer_centerline_points_xy_mm": centerline_groups,
        "full_layer_centerline_points_xyz_mm": _xy_group_to_xyz(centerline_points),
    }


def _build_v5_spatial_handoff_scaffold():
    layer_sequence = ["A", "B", "C", "C", "B", "A"]
    return {
        "recommended_layer_sequence": layer_sequence,
        "layer_instances": [
            {
                "layer_id": f"L{index + 1:02d}",
                "phase": phase,
                "z_index": index,
                "z_mm": None,
            }
            for index, phase in enumerate(layer_sequence)
        ],
        "z_assignment_policy": "reserved_for_v5",
        "interlayer_insulation_evaluated": False,
        "vias_or_physical_bridges_evaluated": False,
    }


def build_three_phase_single_layer_geometry(spec=None):
    merged = three_phase_default_spec()
    if spec:
        merged.update(spec)
    normalized = normalize_three_phase_spec(merged)
    source = dxf_copper_phase_chain.build_phase_chain_geometry()
    if source.get("v35_full_layer_passed") is not True:
        raise RuntimeError("V3.5 Phase A source did not pass validation")

    phase_order = ["A", "B", "C"]
    phases = {}
    for phase in phase_order:
        phases[phase] = _phase_geometry_from_source(
            source,
            phase,
            normalized["phase_offsets_deg"][phase],
            normalized["mechanical_phase_offsets_deg"][phase],
        )
        phases[phase]["metrics"] = _phase_metrics(phases[phase])

    return {
        "phase_offset_angle_units": normalized["phase_offset_angle_units"],
        "phase_offsets_deg": dict(normalized["phase_offsets_deg"]),
        "pole_pairs_count": normalized["pole_pairs_count"],
        "minimum_phase_to_phase_clearance_mm": normalized["minimum_phase_to_phase_clearance_mm"],
        "terminal_keepout_radius_mm": normalized["terminal_keepout_radius_mm"],
        "mechanical_phase_offsets_deg": dict(normalized["mechanical_phase_offsets_deg"]),
        "phase_order": phase_order,
        "phases": phases,
        "terminal_keepouts": [],
        "terminal_keepout_conflicts": [],
        "not_evaluated": {
            "aedt_evaluated": False,
            "dc_solve_evaluated": False,
            "manufacturing_evaluated": False,
            "physical_bridge_evaluated": False,
            "physical_terminal_escape_evaluated": False,
        },
        "v5_spatial_handoff": _build_v5_spatial_handoff_scaffold(),
        "source_v35_summary": {
            "v35_full_layer_passed": source["v35_full_layer_passed"],
            "full_layer_region_count": len(source["full_layer_regions"]),
        },
        "spec_summary": {
            "generation_mode": normalized["generation_mode"],
            "geometry_scope": normalized["geometry_scope"],
            "source_generation_mode": normalized["source_generation_mode"],
            "source_geometry_scope": normalized["source_geometry_scope"],
            "radial_wave_min_traverses_per_region": normalized["radial_wave_min_traverses_per_region"],
        },
    }


def _points_are_xyz(points):
    return all(isinstance(point, (list, tuple)) and len(point) == 3 for point in points)


def _groups_are_xyz(groups):
    return all(_points_are_xyz(group) for group in groups)


def _validate_v5_spatial_handoff_scaffold(geometry):
    issues = []
    handoff = geometry.get("v5_spatial_handoff")
    if not isinstance(handoff, dict):
        return False, ["v5_spatial_handoff_missing"]

    layer_instances = handoff.get("layer_instances")
    if not isinstance(layer_instances, list):
        issues.append("v5_spatial_handoff_layer_instances_missing")
        layer_instances = []

    phases = geometry.get("phases", {})
    for layer in layer_instances:
        phase = layer.get("phase") if isinstance(layer, dict) else None
        if phase not in phases:
            issues.append(f"v5_spatial_handoff_unknown_phase:{phase}")

    for phase in geometry.get("phase_order", ["A", "B", "C"]):
        phase_geometry = phases.get(phase, {})
        if not _groups_are_xyz(phase_geometry.get("full_layer_outline_groups_xyz_mm", [])):
            issues.append(f"v5_spatial_handoff_missing_outline_xyz:{phase}")
        if not _points_are_xyz(phase_geometry.get("full_layer_centerline_points_xyz_mm", [])):
            issues.append(f"v5_spatial_handoff_missing_centerline_xyz:{phase}")
        if not _groups_are_xyz(phase_geometry.get("full_layer_aedt_polyline_regions_mm", [])):
            issues.append(f"v5_spatial_handoff_missing_aedt_polyline_xyz:{phase}")
        for region in phase_geometry.get("full_layer_regions", []):
            if not _points_are_xyz(region.get("aedt_polyline_points_mm", [])):
                issues.append(f"v5_spatial_handoff_missing_region_polyline_xyz:{phase}")
                break

    return len(issues) == 0, issues


def validate_three_phase_single_layer_geometry(geometry):
    blocking_issues = []
    same_plane_issues = []
    minimum_clearance_required = float(geometry.get("minimum_phase_to_phase_clearance_mm", 1.0))

    try:
        source_passed = geometry["source_v35_summary"].get("v35_full_layer_passed") is True
        phase_pair_metrics = _calculate_phase_pair_metrics(geometry)
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "source_passed": False,
            "overlap_area_calculated": False,
            "v4_passed": False,
            "same_plane_feasibility_passed": False,
            "same_plane_issues": same_plane_issues,
            "blocking_issues": [f"structure_validation_failed:{exc}"],
        }

    geometry["phase_pair_metrics"] = phase_pair_metrics
    terminal_keepouts = _terminal_keepouts_from_geometry(geometry)
    geometry["terminal_keepouts"] = terminal_keepouts
    geometry["terminal_keepout_conflicts"] = _terminal_keepout_conflicts(terminal_keepouts)
    not_evaluated = geometry.setdefault("not_evaluated", {})
    not_evaluated.setdefault("aedt_evaluated", False)
    not_evaluated.setdefault("dc_solve_evaluated", False)
    not_evaluated.setdefault("manufacturing_evaluated", False)
    not_evaluated["physical_bridge_evaluated"] = False
    not_evaluated["physical_terminal_escape_evaluated"] = False
    metrics = geometry.setdefault("metrics", {})
    metrics["phase_to_phase_minimum_clearance_mm"] = min(
        pair_metric["minimum_clearance_mm"] for pair_metric in phase_pair_metrics.values()
    )
    metrics["phase_pair_overlap_area_mm2"] = {
        pair_name: pair_metric["overlap_area_mm2"]
        for pair_name, pair_metric in phase_pair_metrics.items()
    }
    radial_wave_min_traverses_per_region = int(
        geometry["spec_summary"].get("radial_wave_min_traverses_per_region", 0)
    )

    overlap_area_calculated = all(
        isinstance(pair_metric["overlap_area_mm2"], (int, float))
        and math.isfinite(pair_metric["overlap_area_mm2"])
        for pair_metric in phase_pair_metrics.values()
    )

    same_plane_feasibility_passed = True
    for pair_name, pair_metric in phase_pair_metrics.items():
        if pair_metric["overlap_area_mm2"] > 0.0:
            same_plane_feasibility_passed = False
            same_plane_issues.append(f"phase_pair_overlap_detected:{pair_name}")
        if pair_metric["minimum_clearance_mm"] < minimum_clearance_required:
            same_plane_feasibility_passed = False
            same_plane_issues.append(f"phase_pair_clearance_violation:{pair_name}")

    for phase in geometry.get("phase_order", ["A", "B", "C"]):
        phase_metrics = geometry["phases"][phase]["metrics"]
        radial_length = phase_metrics["radial_wave_radial_dominant_length_mm"]
        circumferential_length = phase_metrics["radial_wave_circumferential_dominant_length_mm"]
        if radial_length <= circumferential_length:
            blocking_issues.append(f"radial_wave_degenerate:{phase}")
        if any(
            count < radial_wave_min_traverses_per_region
            for count in phase_metrics["radial_wave_radial_dominant_traverses_by_region"]
        ):
            blocking_issues.append(f"radial_wave_traverses_below_minimum:{phase}")

    v5_spatial_handoff_ready, v5_spatial_handoff_issues = _validate_v5_spatial_handoff_scaffold(geometry)
    blocking_issues.extend(v5_spatial_handoff_issues)

    return {
        "source_passed": source_passed,
        "overlap_area_calculated": overlap_area_calculated,
        "v4_passed": source_passed and overlap_area_calculated,
        "v5_spatial_handoff_ready": v5_spatial_handoff_ready,
        "same_plane_feasibility_passed": same_plane_feasibility_passed,
        "same_plane_issues": same_plane_issues,
        "blocking_issues": blocking_issues,
    }


def _svg_points(points, scale, offset_x, offset_y):
    return " ".join(
        f"{offset_x + float(point[0]) * scale:.3f},{offset_y - float(point[1]) * scale:.3f}"
        for point in points
    )


def write_three_phase_svg(geometry, output_path):
    validate_three_phase_single_layer_geometry(geometry)
    outline_groups = [
        group
        for phase in geometry.get("phase_order", ["A", "B", "C"])
        for group in geometry["phases"][phase]["full_layer_outline_groups_xy_mm"]
    ]
    points = [point for group in outline_groups for point in group]
    keepouts = geometry.get("terminal_keepouts", [])
    points.extend(keepout["center_xy_mm"] for keepout in keepouts)
    min_x = min(float(point[0]) for point in points)
    max_x = max(float(point[0]) for point in points)
    min_y = min(float(point[1]) for point in points)
    max_y = max(float(point[1]) for point in points)
    padding = 5.0
    scale = 5.0
    width = (max_x - min_x + padding * 2.0) * scale
    height = (max_y - min_y + padding * 2.0) * scale
    offset_x = (padding - min_x) * scale
    offset_y = (max_y + padding) * scale
    phase_colors = {"A": "#2563eb", "B": "#16a34a", "C": "#9333ea"}

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">',
    ]
    for phase in geometry.get("phase_order", ["A", "B", "C"]):
        color = phase_colors.get(phase, "#111827")
        for group in geometry["phases"][phase]["full_layer_outline_groups_xy_mm"]:
            lines.append(
                f'  <polygon class="phase-outline phase-{phase}" points="{_svg_points(group, scale, offset_x, offset_y)}" fill="none" stroke="{color}" stroke-width="0.8"/>'
            )
    for keepout in keepouts:
        cx = offset_x + keepout["center_xy_mm"][0] * scale
        cy = offset_y - keepout["center_xy_mm"][1] * scale
        radius = keepout["radius_mm"] * scale
        lines.append(
            f'  <circle class="terminal-keepout phase-{keepout["phase"]}" cx="{cx:.3f}" cy="{cy:.3f}" r="{radius:.3f}" fill="#dc2626" fill-opacity="0.12" stroke="#dc2626" stroke-opacity="0.7" stroke-width="0.8" stroke-dasharray="3 2"/>'
        )
    lines.append("</svg>")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
