from __future__ import print_function

from copy import deepcopy
import math
import os
import re

from shapely.geometry import LineString
from shapely.geometry import Polygon
from shapely.geometry import box
from shapely.ops import unary_union

from dxf_copper_geometry import V2_CONTRACT_VERSION
from dxf_copper_geometry import V2_CORNER_POLICY
from dxf_copper_geometry import _polygon_from_geometry
from dxf_copper_geometry import build_single_layer_geometry
from dxf_copper_geometry import polar_point
from dxf_copper_geometry import validate_single_layer_geometry
from dxf_copper_geometry import v2_default_spec


V35_PHASE_FULL_LAYER_MILESTONE = "Milestone 3.5: Phase A Full-Layer Geometry Precursor"
V35_PHASE_FULL_LAYER_PRESET = "phase_a_full_layer_v2_constrained_segment"
V35_PHASE_FULL_LAYER_SCOPE = "v35_phase_a_full_layer_2d"
V35_LOGICAL_CONNECTION_POLICY = "ordered_segments_with_physical_gap"
V35_TERMINAL_KEEP_OUT_POLICY = "metadata_only_not_final_escape"
_AEDT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_TOL = 1e-6


def phase_chain_default_spec():
    spec = v2_default_spec()
    spec.update(
        {
            "milestone": V35_PHASE_FULL_LAYER_MILESTONE,
            "geometry_contract_version": V2_CONTRACT_VERSION,
            "generation_mode": "phase_full_layer",
            "topology_preset": V35_PHASE_FULL_LAYER_PRESET,
            "geometry_scope": V35_PHASE_FULL_LAYER_SCOPE,
            "phase": "A",
            "layer": "L01",
            "three_phase_enabled": False,
            "six_layer_stack_enabled": False,
            "inner_radius_mm": 30.0,
            "outer_radius_mm": 45.0,
            "centerline_radius_mm": 37.5,
            "radial_swing_mm": 6.0,
            "start_angle_deg": 0.0,
            "slot_pitch_deg": 12.0,
            "arc_segment_deg": 2.0,
            "max_arc_segment_count": 96,
            "trace_width_mm": 1.5,
            "trace_gap_mm": 1.0,
            "terminal_pad_width_mm": 1.0,
            "terminal_pad_height_mm": 1.0,
            "terminal_offset_mm": 0.0,
            "terminal_contact_role": "logical_contact_stub_not_terminal_escape",
            "macro_segment_count": 6,
            "macro_segment_pitch_deg": 60.0,
            "full_layer_coverage_deg": 360.0,
            "turn_count_per_macro_segment": 4,
            "radial_lane_count": 4,
            "macro_guard_angle_deg": 3.0,
            "segment_primitive_mode": "v2_constrained_full_phase_segment",
            "minimum_radial_fill_ratio": 0.60,
            "minimum_angular_occupancy_ratio": 0.70,
            "minimum_full_layer_centerline_length_mm": 280.0,
            "minimum_full_layer_area_mm2": 900.0,
            "minimum_centerline_length_mm": 280.0,
            "minimum_copper_area_mm2": 900.0,
            "minimum_bounding_diameter_mm": 70.0,
            # Backward-compatible aliases retained for older callers.
            "phase_segment_count": 6,
            "segment_pitch_deg": 60.0,
            "segment_angular_footprint_deg": 60.0,
            "full_phase_coverage_deg": 360.0,
        }
    )
    return spec


def _as_phase_chain_spec(spec):
    provided_keys = set(spec or {})
    defaults = phase_chain_default_spec()
    merged = deepcopy(defaults)
    if spec:
        merged.update(deepcopy(spec))

    if merged.get("generation_mode") != "phase_full_layer":
        raise ValueError("generation_mode must be phase_full_layer for V3.5")
    if merged.get("three_phase_enabled", False):
        raise ValueError("three_phase_enabled must remain false for V3.5")
    if merged.get("six_layer_stack_enabled", False):
        raise ValueError("six_layer_stack_enabled must remain false for V3.5")

    default_count = int(defaults["macro_segment_count"])
    default_pitch = float(defaults["macro_segment_pitch_deg"])
    has_count = "macro_segment_count" in provided_keys
    has_pitch = "macro_segment_pitch_deg" in provided_keys
    count = int(merged.get("macro_segment_count", default_count))
    pitch = float(merged.get("macro_segment_pitch_deg", default_pitch))

    if has_count and not has_pitch:
        pitch = 360.0 / float(count)
    elif has_pitch and not has_count:
        count = _derive_macro_count_from_pitch(pitch)
    elif has_count and has_pitch:
        if abs(float(count) * pitch - 360.0) > 1e-6:
            raise ValueError(
                "macro_segment_count and macro_segment_pitch_deg must cover 360 deg"
            )
    elif abs(float(count) * pitch - 360.0) > 1e-6:
        raise ValueError(
            "macro_segment_count and macro_segment_pitch_deg must cover 360 deg"
        )

    if count < 2:
        raise ValueError("macro_segment_count must be at least 2")
    merged["macro_segment_count"] = int(count)
    merged["macro_segment_pitch_deg"] = float(pitch)
    merged["full_layer_coverage_deg"] = 360.0
    merged["phase_segment_count"] = int(count)
    merged["segment_pitch_deg"] = float(pitch)
    merged["segment_angular_footprint_deg"] = float(pitch)
    merged["full_phase_coverage_deg"] = 360.0

    for key in [
        "inner_radius_mm",
        "outer_radius_mm",
        "trace_width_mm",
        "trace_gap_mm",
        "terminal_pad_width_mm",
        "terminal_pad_height_mm",
        "macro_guard_angle_deg",
    ]:
        if float(merged[key]) <= 0.0:
            raise ValueError("%s must be positive for V3.5 phase full-layer geometry" % key)

    if int(merged["turn_count_per_macro_segment"]) < 1:
        raise ValueError("turn_count_per_macro_segment must be at least 1")
    if int(merged["radial_lane_count"]) < 1:
        raise ValueError("radial_lane_count must be at least 1")

    required_radial_span = (
        int(merged["radial_lane_count"]) * float(merged["trace_width_mm"])
        + (int(merged["radial_lane_count"]) - 1) * float(merged["trace_gap_mm"])
    )
    usable_radial_span = float(merged["outer_radius_mm"]) - float(merged["inner_radius_mm"])
    if required_radial_span > usable_radial_span + 1e-9:
        raise ValueError("radius window cannot fit radial_lane_count")

    if 2.0 * float(merged["macro_guard_angle_deg"]) >= float(merged["macro_segment_pitch_deg"]):
        raise ValueError("macro_guard_angle_deg leaves no usable angular span")

    if "minimum_full_layer_centerline_length_mm" not in provided_keys:
        merged["minimum_full_layer_centerline_length_mm"] = float(
            merged.get("minimum_centerline_length_mm", defaults["minimum_centerline_length_mm"])
        )
    if "minimum_centerline_length_mm" not in provided_keys:
        merged["minimum_centerline_length_mm"] = float(
            merged["minimum_full_layer_centerline_length_mm"]
        )
    if "minimum_full_layer_area_mm2" not in provided_keys:
        merged["minimum_full_layer_area_mm2"] = float(
            merged.get("minimum_copper_area_mm2", defaults["minimum_copper_area_mm2"])
        )
    if "minimum_copper_area_mm2" not in provided_keys:
        merged["minimum_copper_area_mm2"] = float(merged["minimum_full_layer_area_mm2"])

    merged["spec_summary"] = _spec_summary(merged)
    return merged


def _derive_macro_count_from_pitch(pitch):
    if pitch <= 0.0:
        raise ValueError("macro_segment_pitch_deg must be positive")
    exact = 360.0 / float(pitch)
    count = int(round(exact))
    if count < 2 or abs(exact - float(count)) > 1e-6:
        raise ValueError("macro_segment_pitch_deg must divide 360 deg")
    return count


def _spec_summary(spec):
    keys = [
        "generation_mode",
        "topology_preset",
        "geometry_scope",
        "inner_radius_mm",
        "outer_radius_mm",
        "centerline_radius_mm",
        "radial_swing_mm",
        "trace_width_mm",
        "trace_gap_mm",
        "slot_pitch_deg",
        "arc_segment_deg",
        "max_arc_segment_count",
        "terminal_pad_width_mm",
        "terminal_pad_height_mm",
        "terminal_offset_mm",
        "mitre_limit",
        "macro_segment_count",
        "macro_segment_pitch_deg",
        "full_layer_coverage_deg",
        "turn_count_per_macro_segment",
        "radial_lane_count",
        "macro_guard_angle_deg",
        "segment_primitive_mode",
        "minimum_radial_fill_ratio",
        "minimum_angular_occupancy_ratio",
        "minimum_full_layer_centerline_length_mm",
        "minimum_full_layer_area_mm2",
        "minimum_centerline_length_mm",
        "minimum_copper_area_mm2",
        "minimum_bounding_diameter_mm",
        "max_outer_diameter_mm",
    ]
    return {key: spec[key] for key in keys if key in spec}


def _phase_chain_not_evaluated():
    return {
        "phase_b_geometry_evaluated": False,
        "phase_c_geometry_evaluated": False,
        "three_phase_spacing_evaluated": False,
        "physical_bridge_evaluated": False,
        "physical_terminal_escape_evaluated": False,
        "terminal_escape_evaluated": False,
        "aedt_sheet_creation_evaluated": False,
        "dc_conduction_evaluated": False,
        "three_phase_evaluated": False,
        "six_layer_stack_evaluated": False,
        "solve_evaluated": False,
        "manufacturing_dxf_evaluated": False,
    }


def _round_point_xy(point):
    return [round(float(point[0]), 6), round(float(point[1]), 6)]


def _append_unique_points(target, source):
    for point in source:
        rounded = _round_point_xy(point)
        if not target or target[-1] != rounded:
            target.append(rounded)


def _sample_arc_points(radius_mm, start_angle_deg, end_angle_deg, arc_segment_deg):
    span = float(end_angle_deg) - float(start_angle_deg)
    step = abs(float(arc_segment_deg)) or 2.0
    segment_count = max(1, int(math.ceil(abs(span) / step)))
    points = []
    for index in range(segment_count + 1):
        fraction = float(index) / float(segment_count)
        angle = float(start_angle_deg) + span * fraction
        points.append(polar_point(radius_mm, angle))
    return points


def _lane_radii(spec):
    lane_count = int(spec["radial_lane_count"])
    trace_half = float(spec["trace_width_mm"]) / 2.0
    inner = float(spec["inner_radius_mm"]) + trace_half
    outer = float(spec["outer_radius_mm"]) - trace_half
    if lane_count == 1:
        return [(inner + outer) / 2.0]
    return [
        inner + (outer - inner) * float(index) / float(lane_count - 1)
        for index in range(lane_count)
    ]


def _lane_index_for_turn(turn_index, lane_count):
    if lane_count <= 1:
        return 0
    cycle = list(range(lane_count)) + list(range(lane_count - 2, 0, -1))
    return cycle[turn_index % len(cycle)]


def _constrained_centerline_points(spec, macro_index):
    pitch = float(spec["macro_segment_pitch_deg"])
    guard = float(spec["macro_guard_angle_deg"])
    tile_start = float(spec.get("start_angle_deg", 0.0)) + macro_index * pitch
    usable_start = tile_start + guard
    usable_end = tile_start + pitch - guard
    if usable_end <= usable_start:
        raise ValueError("macro_guard_angle_deg leaves no usable angular span")

    radii = _lane_radii(spec)
    if len(radii) < 2:
        middle = radii[0]
        return [
            _round_point_xy(polar_point(middle, usable_start)),
            _round_point_xy(polar_point(middle, usable_end)),
        ]

    traversal_count = max(
        int(spec["turn_count_per_macro_segment"]) + int(spec["radial_lane_count"]),
        int(math.ceil((usable_end - usable_start) / float(spec["slot_pitch_deg"]))) + 1,
        3,
    )
    points = []
    inner = radii[0]
    outer = radii[-1]
    for traversal_index in range(traversal_count):
        if traversal_count == 1:
            fraction = 0.0
        else:
            fraction = float(traversal_index) / float(traversal_count - 1)
        angle = usable_start + (usable_end - usable_start) * fraction
        if traversal_index % 2 == 0:
            traversal = [polar_point(inner, angle), polar_point(outer, angle)]
        else:
            traversal = [polar_point(outer, angle), polar_point(inner, angle)]
        _append_unique_points(points, traversal)
    return points


def _polygon_points_xy(polygon):
    return [[float(x), float(y)] for x, y in polygon.exterior.coords]


def _aedt_polyline_points(points_xy):
    source = points_xy[:-1] if points_xy and points_xy[0] == points_xy[-1] else points_xy
    return [[float(x), float(y), 0.0] for x, y in source]


def _centerline_length_mm(points):
    if not points:
        return 0.0
    # V3.5 exposes full-layer centerline data as per-region groups to avoid
    # implying physical copper bridges between disconnected macro segments.
    if points and isinstance(points[0], list) and points[0] and isinstance(points[0][0], list):
        return sum(_centerline_length_mm(group) for group in points)
    length = 0.0
    for index in range(1, len(points)):
        ax, ay = points[index - 1]
        bx, by = points[index]
        length += math.hypot(float(bx) - float(ax), float(by) - float(ay))
    return length


def _box_from_center(center_x, center_y, width, height):
    half_w = float(width) / 2.0
    half_h = float(height) / 2.0
    return box(center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)


def _terminal_records(centerline, spec, segment_id):
    pad_w = float(spec["terminal_pad_width_mm"])
    pad_h = float(spec["terminal_pad_height_mm"])
    role_detail = spec["terminal_contact_role"]
    pads = []
    for suffix, role, point in [
        ("InputPad", "source", centerline[0]),
        ("ReturnPad", "sink", centerline[-1]),
    ]:
        pads.append(
            {
                "name": "%s_%s" % (segment_id, suffix),
                "role": role,
                "role_detail": role_detail,
                "center_xy_mm": [float(point[0]), float(point[1])],
                "size_xy_mm": [pad_w, pad_h],
            }
        )
    return pads


def _build_outline_polygon(centerline, spec, pads):
    route = LineString([(float(x), float(y)) for x, y in centerline]).buffer(
        float(spec["trace_width_mm"]) / 2.0,
        cap_style=2,
        join_style=2,
        mitre_limit=float(spec["mitre_limit"]),
    )
    shapes = [route] + [
        _box_from_center(
            pad["center_xy_mm"][0],
            pad["center_xy_mm"][1],
            pad["size_xy_mm"][0],
            pad["size_xy_mm"][1],
        )
        for pad in pads
    ]
    outline = unary_union(shapes)
    if outline.geom_type != "Polygon":
        outline = outline.buffer(0)
    if outline.geom_type != "Polygon":
        raise ValueError("V3.5 segment outline must resolve to one connected polygon")
    return outline


def _segment_diagnostics(centerline, outline_points, outline, spec, macro_index):
    radii = [math.hypot(float(x), float(y)) for x, y in centerline]
    pitch = float(spec["macro_segment_pitch_deg"])
    tile_start = float(spec.get("start_angle_deg", 0.0)) + macro_index * pitch
    return {
        "topology_preset": spec["topology_preset"],
        "geometry_scope": spec["geometry_scope"],
        "full_phase_winding_enabled": False,
        "centerline_length_mm": _centerline_length_mm(centerline),
        "centerline_point_count": len(centerline),
        "outline_point_count": len(outline_points),
        "angular_span_deg": pitch - 2.0 * float(spec["macro_guard_angle_deg"]),
        "tile_start_angle_deg": tile_start,
        "tile_end_angle_deg": tile_start + pitch,
        "macro_guard_angle_deg": float(spec["macro_guard_angle_deg"]),
        "radial_min_mm": min(radii) if radii else 0.0,
        "radial_max_mm": max(radii) if radii else 0.0,
        "terminal_pad_size_xy_mm": [
            float(spec["terminal_pad_width_mm"]),
            float(spec["terminal_pad_height_mm"]),
        ],
        "terminal_pad_role": spec["terminal_contact_role"],
        "arc_sampling_policy": "bounded_polyline_arc_approximation",
        "actual_arc_segment_count": max(0, len(centerline) - 1),
        "max_arc_segment_count": int(spec["max_arc_segment_count"]),
        "area_mm2": float(outline.area),
    }


def _logical_for_segment(segment_ids, index):
    return {
        "entry_from": None if index == 0 else segment_ids[index - 1],
        "exit_to": None if index == len(segment_ids) - 1 else segment_ids[index + 1],
        "connection_type": "logical_only_physical_gap",
    }


def _build_constrained_segment(spec, index, segment_ids):
    segment_id = segment_ids[index]
    centerline = _constrained_centerline_points(spec, index)
    pads = _terminal_records(centerline, spec, segment_id)
    outline = _build_outline_polygon(centerline, spec, pads)
    outline_points = _polygon_points_xy(outline)
    logical = _logical_for_segment(segment_ids, index)
    diagnostics = _segment_diagnostics(centerline, outline_points, outline, spec, index)
    segment = {
        "geometry_contract_version": spec["geometry_contract_version"],
        "milestone": spec["milestone"],
        "units": spec["units"],
        "phase": spec["phase"],
        "layer": spec["layer"],
        "copper_thickness_mm": float(spec["copper_thickness_mm"]),
        "generation_mode": "phase_full_layer",
        "segment_id": segment_id,
        "region_id": "A_L01_R%02d" % (index + 1),
        "sequence_index": index + 1,
        "current_direction": "entry_to_exit",
        "topology_preset": spec["topology_preset"],
        "geometry_scope": spec["geometry_scope"],
        "full_phase_winding_enabled": False,
        "centerline_points_xy_mm": centerline,
        "outline_points_xy_mm": outline_points,
        "aedt_polyline_points_mm": _aedt_polyline_points(outline_points),
        "terminal_pads": pads,
        "terminals": list(pads),
        "estimates": {
            "policy": "geometry_derived_estimate_not_final_validation",
            "path_length_mm": _centerline_length_mm(centerline),
            "area_mm2": float(outline.area),
            "systematic_error_sources": [
                "constrained_v2_segment_primitive",
                "mitred_corner_outline",
                "logical_terminal_stub",
                "v35_2d_scope",
            ],
        },
        "diagnostics": diagnostics,
        "metadata": {
            "source_kind": "parameterized_phase_full_layer_segment",
            "topology_preset": spec["topology_preset"],
            "geometry_scope": spec["geometry_scope"],
            "full_phase_winding_enabled": False,
            "arc_segment_deg": float(spec["arc_segment_deg"]),
            "trace_width_mm": float(spec["trace_width_mm"]),
            "trace_gap_mm": float(spec["trace_gap_mm"]),
            "terminal_pad_role": spec["terminal_contact_role"],
            "corner_policy": V2_CORNER_POLICY,
            "buffer_cap_style": "flat",
            "buffer_join_style": "mitre",
            "mitre_limit": float(spec["mitre_limit"]),
            "estimate_policy": "geometry_derived_estimate_not_final_validation",
            "dxf_export_mode": spec["dxf_export_mode"],
            "segment_primitive_mode": "v2_constrained_full_phase_segment",
            "logical_connections": logical,
        },
        "manufacturing_constraints": {
            "max_outer_diameter_mm": float(spec["max_outer_diameter_mm"]),
            "minimum_copper_width_mm": float(spec["trace_width_mm"]),
            "minimum_clearance_mm": float(spec["trace_gap_mm"]),
            "corner_policy": V2_CORNER_POLICY,
            "full_phase_winding_enabled": False,
            "three_phase_enabled": False,
            "six_layer_stack_enabled": False,
        },
        "physical_connection": "isolated_macro_segment",
        "logical_connections": logical,
    }
    return segment


def _build_unconstrained_v2_segment(spec, index, segment_ids):
    v2_spec = v2_default_spec()
    v2_spec.update(
        {
            "trace_width_mm": float(spec["trace_width_mm"]),
            "trace_gap_mm": float(spec["trace_gap_mm"]),
            "terminal_pad_width_mm": float(spec["terminal_pad_width_mm"]),
            "terminal_pad_height_mm": float(spec["terminal_pad_height_mm"]),
            "start_angle_deg": 0.0,
            "turn_count": int(spec["turn_count_per_macro_segment"]),
            "dxf_export_mode": spec["dxf_export_mode"],
        }
    )
    segment = build_single_layer_geometry(v2_spec)
    logical = _logical_for_segment(segment_ids, index)
    segment.update(
        {
            "milestone": spec["milestone"],
            "generation_mode": "phase_full_layer",
            "segment_id": segment_ids[index],
            "region_id": "A_L01_R%02d" % (index + 1),
            "sequence_index": index + 1,
            "topology_preset": spec["topology_preset"],
            "geometry_scope": spec["geometry_scope"],
            "physical_connection": "isolated_macro_segment",
            "logical_connections": logical,
        }
    )
    segment["metadata"]["generation_mode"] = "phase_full_layer"
    segment["metadata"]["segment_id"] = segment["segment_id"]
    segment["metadata"]["logical_connections"] = logical
    return segment


def build_phase_chain_geometry(spec=None):
    spec = _as_phase_chain_spec(spec)
    count = int(spec["macro_segment_count"])
    segment_ids = ["A_L01_M%02d" % (index + 1) for index in range(count)]
    segments = []
    for index in range(count):
        if spec.get("segment_primitive_mode") == "unconstrained_v2_repetition":
            segment = _build_unconstrained_v2_segment(spec, index, segment_ids)
        else:
            segment = _build_constrained_segment(spec, index, segment_ids)
        segments.append(segment)

    full_layer_regions = [_region_from_segment(segment) for segment in segments]
    outline_groups = [segment["outline_points_xy_mm"] for segment in segments]
    aedt_regions = [segment["aedt_polyline_points_mm"] for segment in segments]
    centerline_groups = [segment["centerline_points_xy_mm"] for segment in segments]
    diagnostics = _chain_diagnostics(spec, segments)
    logical_connections = _logical_connection_records(spec, segments)
    terminal_keepouts = _terminal_keepouts(segments)
    chain = {
        "milestone": spec["milestone"],
        "geometry_contract_version": spec["geometry_contract_version"],
        "generation_mode": "phase_full_layer",
        "topology_preset": spec["topology_preset"],
        "geometry_scope": spec["geometry_scope"],
        "phase": spec["phase"],
        "layer": spec["layer"],
        "units": spec["units"],
        "macro_segment_count": count,
        "macro_segment_pitch_deg": float(spec["macro_segment_pitch_deg"]),
        "segment_count": len(segments),
        "entry_segment_id": segments[0]["segment_id"],
        "exit_segment_id": segments[-1]["segment_id"],
        "order_policy": "segments_ordered_entry_to_exit",
        "logical_connection_policy": V35_LOGICAL_CONNECTION_POLICY,
        "segment_primitive_mode": "constrained_v2_segment"
        if spec.get("segment_primitive_mode") != "unconstrained_v2_repetition"
        else "unconstrained_v2_repetition",
        "segments": segments,
        "full_layer_regions": full_layer_regions,
        "full_layer_outline_groups_xy_mm": outline_groups,
        "full_layer_aedt_polyline_regions_mm": aedt_regions,
        "full_layer_centerline_points_xy_mm": centerline_groups,
        "phase_transform_policy": {
            "type": "angular_offset_from_phase_a",
            "phase_b_offset_deg": 120.0,
            "phase_c_offset_deg": 240.0,
            "candidate_generation_stage": "Milestone 4",
        },
        "terminal_keepout_policy": V35_TERMINAL_KEEP_OUT_POLICY,
        "terminal_keepouts": terminal_keepouts,
        "metadata": {
            "logical_connection_policy": V35_LOGICAL_CONNECTION_POLICY,
            "logical_connections": logical_connections,
            "trace_gap_mm": float(spec["trace_gap_mm"]),
            "terminal_keepout_policy": "reserve_only_no_terminal_escape",
            "terminal_keepouts": terminal_keepouts,
        },
        "spec_summary": deepcopy(spec["spec_summary"]),
        "diagnostics": diagnostics,
        "not_evaluated": _phase_chain_not_evaluated(),
        "blocking_issues": [],
        "v35_full_layer_passed": False,
    }
    status = validate_phase_chain_geometry(chain)
    chain["validation"] = status
    chain["blocking_issues"] = list(status["issues"])
    chain["v35_full_layer_passed"] = bool(status["valid"])
    return chain


def _region_from_segment(segment):
    return {
        "region_id": segment["region_id"],
        "source_segment_id": segment["segment_id"],
        "segment_id": segment["segment_id"],
        "geometry_contract_version": segment["geometry_contract_version"],
        "generation_mode": segment["generation_mode"],
        "outline_points_xy_mm": segment["outline_points_xy_mm"],
        "aedt_polyline_points_mm": segment["aedt_polyline_points_mm"],
        "centerline_points_xy_mm": segment["centerline_points_xy_mm"],
        "terminal_pads": segment["terminal_pads"],
        "terminals": segment["terminals"],
        "metadata": segment["metadata"],
        "diagnostics": segment["diagnostics"],
        "physical_connection": "isolated_macro_segment",
        "logical_connections": segment["logical_connections"],
        "manufacturing_constraints": segment["manufacturing_constraints"],
    }


def _logical_connection_records(spec, segments):
    records = []
    polygons = [_polygon_from_geometry(segment) for segment in segments]
    for index in range(len(segments) - 1):
        clearance = polygons[index].distance(polygons[index + 1])
        records.append(
            {
                "entry_from": segments[index]["segment_id"],
                "exit_to": segments[index + 1]["segment_id"],
                "connection_type": "logical_only_physical_gap",
                "minimum_clearance_mm": float(clearance),
            }
        )
    return records


def _terminal_keepouts(segments):
    keepouts = []
    if not segments:
        return keepouts
    for segment in [segments[0], segments[-1]]:
        for pad in segment.get("terminal_pads", []):
            keepouts.append(
                {
                    "source_segment_id": segment["segment_id"],
                    "role": pad["role"],
                    "center_xy_mm": pad["center_xy_mm"],
                    "size_xy_mm": pad["size_xy_mm"],
                    "radius_mm": max(pad["size_xy_mm"]) / 2.0,
                    "evaluation_status": "reserved_not_routed",
                    "physical_escape_evaluated": False,
                }
            )
    return keepouts


def _chain_diagnostics(spec, segments):
    polygons = [_polygon_from_geometry(segment) for segment in segments]
    centerlines = [segment["centerline_points_xy_mm"] for segment in segments]
    all_points = []
    for segment in segments:
        all_points.extend(segment["outline_points_xy_mm"])
    radial_min, radial_max = _centerline_radial_range(centerlines)
    usable_radial_span = float(spec["outer_radius_mm"]) - float(spec["inner_radius_mm"])
    radial_fill = 0.0
    if usable_radial_span > 0.0:
        radial_fill = (radial_max - radial_min + float(spec["trace_width_mm"])) / usable_radial_span
    angular_occupancy = (
        float(spec["macro_segment_pitch_deg"]) - 2.0 * float(spec["macro_guard_angle_deg"])
    ) / float(spec["macro_segment_pitch_deg"])
    radial_wave = _radial_wave_metrics(centerlines)
    return {
        "segment_count": len(segments),
        "full_layer_coverage_deg": float(spec["full_layer_coverage_deg"]),
        "macro_segment_pitch_deg": float(spec["macro_segment_pitch_deg"]),
        "centerline_length_mm": _centerline_length_mm(centerlines),
        "copper_area_mm2": sum(float(polygon.area) for polygon in polygons),
        "bounding_diameter_mm": _bounding_diameter_mm(all_points),
        "radial_fill_ratio": max(0.0, min(1.0, radial_fill)),
        "angular_occupancy_ratio": max(0.0, min(1.0, angular_occupancy)),
        "minimum_clearance_mm": _minimum_polygon_clearance(polygons),
        "radial_wave_radial_dominant_length_mm": radial_wave[
            "radial_wave_radial_dominant_length_mm"
        ],
        "radial_wave_circumferential_dominant_length_mm": radial_wave[
            "radial_wave_circumferential_dominant_length_mm"
        ],
        "radial_wave_radial_dominant_traverses_by_segment": radial_wave[
            "radial_wave_radial_dominant_traverses_by_segment"
        ],
        "physical_bridge_evaluated": False,
        "terminal_escape_evaluated": False,
    }


def _centerline_radial_range(centerlines):
    radii = []
    for centerline in centerlines:
        for x, y in centerline:
            radii.append(math.hypot(float(x), float(y)))
    if not radii:
        return 0.0, 0.0
    return min(radii), max(radii)


def _radial_wave_metrics(centerlines, dominance_ratio=1.5):
    radial_dominant_length = 0.0
    circumferential_dominant_length = 0.0
    traverses_by_segment = []
    for centerline in centerlines:
        segment_traverses = 0
        for start, end in zip(centerline, centerline[1:]):
            start_radius = math.hypot(float(start[0]), float(start[1]))
            end_radius = math.hypot(float(end[0]), float(end[1]))
            average_radius = (start_radius + end_radius) / 2.0
            delta_radius = abs(end_radius - start_radius)
            delta_theta = math.atan2(float(end[1]), float(end[0])) - math.atan2(
                float(start[1]), float(start[0])
            )
            while delta_theta > math.pi:
                delta_theta -= 2.0 * math.pi
            while delta_theta < -math.pi:
                delta_theta += 2.0 * math.pi
            arc_equivalent = average_radius * abs(delta_theta)
            segment_length = math.hypot(
                float(end[0]) - float(start[0]), float(end[1]) - float(start[1])
            )
            if delta_radius > dominance_ratio * arc_equivalent:
                radial_dominant_length += segment_length
                segment_traverses += 1
            elif arc_equivalent > dominance_ratio * delta_radius:
                circumferential_dominant_length += segment_length
        traverses_by_segment.append(segment_traverses)
    return {
        "radial_wave_radial_dominant_length_mm": radial_dominant_length,
        "radial_wave_circumferential_dominant_length_mm": circumferential_dominant_length,
        "radial_wave_radial_dominant_traverses_by_segment": traverses_by_segment,
    }


def _bounding_diameter_mm(points):
    if not points:
        return 0.0
    return 2.0 * max(math.hypot(float(point[0]), float(point[1])) for point in points)


def _minimum_polygon_clearance(polygons):
    minimum = None
    for left_index in range(len(polygons)):
        for right_index in range(left_index + 1, len(polygons)):
            distance = polygons[left_index].distance(polygons[right_index])
            minimum = distance if minimum is None else min(minimum, distance)
    return float(minimum) if minimum is not None else 0.0


def phase_chain_aedt_object_name(segment_id):
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", str(segment_id))
    if not safe_id or not safe_id[0].isalpha():
        safe_id = "Segment_%s" % safe_id
    return "AutoDxfCopperV35_PhaseA_L01_%s_Sheet" % safe_id


def _segment_min_edge_length_mm(points):
    if len(points) < 2:
        return 0.0
    distances = []
    for index in range(len(points) - 1):
        x0, y0 = points[index][0], points[index][1]
        x1, y1 = points[index + 1][0], points[index + 1][1]
        distances.append(math.hypot(float(x1) - float(x0), float(y1) - float(y0)))
    return min(distances) if distances else 0.0


def aedt_preflight_phase_chain(chain, min_edge_length_mm=0.01):
    issues = []
    names = []
    regions = chain.get("full_layer_regions") or chain.get("segments", [])
    for region in regions:
        segment_id = region.get("segment_id") or region.get("source_segment_id", "")
        name = phase_chain_aedt_object_name(segment_id)
        names.append(name)
        if len(name) > 80:
            issues.append("aedt_name_too_long:%s" % segment_id)
        if not _AEDT_NAME_PATTERN.match(name):
            issues.append("aedt_name_unsafe:%s" % segment_id)

        points = region.get("aedt_polyline_points_mm", [])
        if len(points) < 4:
            issues.append("aedt_polyline_too_short:%s" % segment_id)
            continue
        for point in points:
            if len(point) != 3:
                issues.append("aedt_point_not_xyz:%s" % segment_id)
                break
            if abs(float(point[2])) > 1e-9:
                issues.append("aedt_point_z_not_zero:%s" % segment_id)
                break
        for index in range(len(points) - 1):
            if points[index] == points[index + 1]:
                issues.append("aedt_duplicate_adjacent_point:%s" % segment_id)
                break
        if _segment_min_edge_length_mm(points) < min_edge_length_mm:
            issues.append("aedt_edge_too_short:%s" % segment_id)

    if len(names) != len(set(names)):
        issues.append("duplicate_aedt_object_name")

    return {
        "passed": len(issues) == 0,
        "object_names": names,
        "close_surface_policy": "use_create_polyline_close_surface_true",
        "cover_surface_policy": "use_create_polyline_cover_surface_true",
        "issues": issues,
    }


def validate_phase_chain_geometry(chain):
    issues = []
    segments = list(chain.get("segments", []))
    spec = chain.get("spec_summary", {})
    segment_ids = [segment.get("segment_id", "") for segment in segments]
    sequence = [segment.get("sequence_index") for segment in segments]

    if chain.get("generation_mode") != "phase_full_layer":
        issues.append("generation_mode_not_phase_full_layer")
    if len(segments) < 2:
        issues.append("segment_count_below_two")
    if len(segment_ids) != len(set(segment_ids)):
        issues.append("duplicate_segment_id")
    if sequence != list(range(1, len(segments) + 1)):
        issues.append("segment_sequence_not_contiguous")
    if chain.get("entry_segment_id") != (segment_ids[0] if segment_ids else ""):
        issues.append("entry_segment_id_mismatch")
    if chain.get("exit_segment_id") != (segment_ids[-1] if segment_ids else ""):
        issues.append("exit_segment_id_mismatch")
    if "phase_belt_envelope" in chain:
        issues.append("legacy_phase_belt_envelope_present")
    if "physical_bridges" in chain or "bridge_polylines_xy_mm" in chain:
        issues.append("physical_bridge_geometry_present")
    if "full_layer_outline_points_xy_mm" in chain or "full_layer_aedt_polyline_points_mm" in chain:
        issues.append("single_full_layer_region_present")

    diagnostics = chain.get("diagnostics", {})
    coverage = float(diagnostics.get("full_layer_coverage_deg", 0.0))
    full_layer_coverage_valid = abs(coverage - 360.0) <= 1e-6
    if not full_layer_coverage_valid:
        issues.append("full_layer_coverage_not_360_deg")

    segment_statuses = []
    polygons = []
    for segment in segments:
        status = validate_single_layer_geometry(segment)
        segment_statuses.append(status)
        if not status.get("valid", False):
            issues.append("segment_geometry_invalid:%s" % segment.get("segment_id", "unknown"))
        polygon = _polygon_from_geometry(segment)
        if polygon.is_empty or not polygon.is_valid:
            issues.append("full_layer_region_invalid:%s" % segment.get("segment_id", "unknown"))
        polygons.append(polygon)

    overlap_free = True
    for left_index in range(len(polygons)):
        for right_index in range(left_index + 1, len(polygons)):
            intersection = polygons[left_index].intersection(polygons[right_index])
            if not intersection.is_empty and intersection.area > 1e-6:
                overlap_free = False
    if not overlap_free:
        issues.append("segment_overlap_detected")
    full_layer_self_overlap_free = overlap_free

    minimum_clearance = _minimum_polygon_clearance(polygons)
    required_clearance = float(spec.get("trace_gap_mm", 0.0))
    if len(polygons) > 1 and minimum_clearance < required_clearance - 1e-9:
        issues.append("minimum_segment_clearance_violation")

    radial_fill = float(diagnostics.get("radial_fill_ratio", 0.0))
    angular_occupancy = float(diagnostics.get("angular_occupancy_ratio", 0.0))
    centerline_length = float(diagnostics.get("centerline_length_mm", 0.0))
    copper_area = float(diagnostics.get("copper_area_mm2", 0.0))
    bounding_diameter = float(diagnostics.get("bounding_diameter_mm", 0.0))
    radial_wave_radial = float(
        diagnostics.get("radial_wave_radial_dominant_length_mm", 0.0)
    )
    radial_wave_circumferential = float(
        diagnostics.get("radial_wave_circumferential_dominant_length_mm", 0.0)
    )
    radial_wave_traverses = list(
        diagnostics.get("radial_wave_radial_dominant_traverses_by_segment", [])
    )

    if radial_fill < float(spec.get("minimum_radial_fill_ratio", 0.0)):
        issues.append("radial_fill_ratio_too_low")
    if angular_occupancy < float(spec.get("minimum_angular_occupancy_ratio", 0.0)):
        issues.append("angular_occupancy_ratio_too_low")
    if centerline_length < float(spec.get("minimum_centerline_length_mm", 0.0)):
        issues.append("centerline_length_too_short")
    if copper_area < float(spec.get("minimum_copper_area_mm2", 0.0)):
        issues.append("copper_area_too_low")
    if bounding_diameter > float(spec.get("max_outer_diameter_mm", 0.0)):
        issues.append("outline_exceeds_max_outer_diameter")
    if radial_wave_radial <= radial_wave_circumferential:
        issues.append("radial_wave_not_radial_dominant")
    if any(count < 2 for count in radial_wave_traverses):
        issues.append("radial_wave_traverse_count_too_low")

    preflight = aedt_preflight_phase_chain(chain)
    issues.extend(preflight["issues"])
    blocking = list(issues)

    return {
        "valid": len(issues) == 0,
        "segment_geometry_valid": all(status.get("valid", False) for status in segment_statuses),
        "sequence_valid": sequence == list(range(1, len(segments) + 1)),
        "full_layer_coverage_valid": full_layer_coverage_valid,
        "full_layer_self_overlap_free": full_layer_self_overlap_free,
        "segment_overlap_free": overlap_free,
        "minimum_segment_clearance_mm": minimum_clearance,
        "radial_fill_ratio": radial_fill,
        "angular_occupancy_ratio": angular_occupancy,
        "centerline_length_mm": centerline_length,
        "copper_area_mm2": copper_area,
        "bounding_diameter_mm": bounding_diameter,
        "radial_wave_radial_dominant_length_mm": radial_wave_radial,
        "radial_wave_circumferential_dominant_length_mm": radial_wave_circumferential,
        "radial_wave_radial_dominant_traverses_by_segment": radial_wave_traverses,
        "aedt_preflight_passed": preflight["passed"],
        "aedt_object_names": preflight["object_names"],
        "segment_statuses": segment_statuses,
        "blocking_issues": blocking,
        "v35_full_layer_passed": len(issues) == 0,
        "issues": issues,
    }


def write_phase_full_layer_svg(chain, output_path):
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    scale = 5.0
    half = 55.0
    width = height = int(half * 2.0 * scale)

    def sx(x):
        return (float(x) + half) * scale

    def sy(y):
        return (half - float(y)) * scale

    colors = ["#0f766e", "#b45309", "#1d4ed8", "#be123c", "#4d7c0f", "#7c3aed"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (width, height, width, height),
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 4"/>'
        % (sx(0), sy(0), 50.0 * scale),
        '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#cbd5e1" stroke-width="1"/>'
        % (sx(0), sy(0), float(chain["spec_summary"]["outer_radius_mm"]) * scale),
        '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#cbd5e1" stroke-width="1"/>'
        % (sx(0), sy(0), float(chain["spec_summary"]["inner_radius_mm"]) * scale),
    ]
    for index, segment in enumerate(chain.get("segments", [])):
        color = colors[index % len(colors)]
        outline = " ".join(
            "%0.3f,%0.3f" % (sx(point[0]), sy(point[1]))
            for point in segment.get("outline_points_xy_mm", [])
        )
        centerline = " ".join(
            "%0.3f,%0.3f" % (sx(point[0]), sy(point[1]))
            for point in segment.get("centerline_points_xy_mm", [])
        )
        parts.append(
            '<polyline points="%s" fill="%s" fill-opacity="0.50" stroke="%s" stroke-width="1"/>'
            % (outline, color, color)
        )
        parts.append(
            '<polyline points="%s" fill="none" stroke="#0f172a" stroke-width="0.8" stroke-dasharray="2 2"/>'
            % centerline
        )
        first = segment["centerline_points_xy_mm"][0]
        parts.append(
            '<text x="%0.3f" y="%0.3f" font-family="monospace" font-size="11" fill="#0f172a">%s</text>'
            % (sx(first[0]), sy(first[1]), segment["segment_id"])
        )
    parts.append("</svg>")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts))
    return output_path
