from __future__ import print_function

from copy import deepcopy
import math
from math import hypot
import re

from shapely.geometry import Polygon
from shapely.geometry import LineString
from shapely.geometry import box
from shapely.ops import unary_union


V2_MILESTONE = "Milestone 3: Repeatable Single-Layer Geometry Generator"
V2_CONTRACT_VERSION = "dxf-copper-v2"
V2_CORNER_POLICY = "flat_caps_mitred_joins_no_auto_rounding"
V2_TOPOLOGY_PRESET = "representative_single_layer_chain"
V2_GEOMETRY_SCOPE = "v2_single_layer_phase_a_representative_segment"
V2_TERMINAL_PAD_ROLE = "source_sink_test_contact_not_final_terminal_shape"
_AEDT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def v1_default_spec():
    return {
        "milestone": "Milestone 2: DXF-Compatible 3D Copper MVP",
        "geometry_contract_version": "dxf-copper-v1",
        "units": "mm",
        "phase": "A",
        "layer": "L01",
        "copper_thickness_mm": 0.3,
        "max_outer_diameter_mm": 100.0,
        "minimum_copper_width_mm": 4.0,
        "minimum_clearance_mm": 1.0,
        "terminal_pad_width_mm": 8.0,
        "terminal_pad_height_mm": 8.0,
        "route_length_mm": 50.0,
        "route_width_mm": 4.0,
        "aedt_handshake_mode": "polyline_points",
        "terminal_count": 2,
    }


def _as_spec(spec):
    base = v1_default_spec()
    if spec:
        base.update(deepcopy(spec))
    return base


def v2_default_spec():
    return {
        "milestone": V2_MILESTONE,
        "geometry_contract_version": V2_CONTRACT_VERSION,
        "units": "mm",
        "topology_preset": V2_TOPOLOGY_PRESET,
        "geometry_scope": V2_GEOMETRY_SCOPE,
        "full_phase_winding_enabled": False,
        "phase": "A",
        "layer": "L01",
        "three_phase_enabled": False,
        "six_layer_stack_enabled": False,
        "copper_thickness_mm": 0.3,
        "max_outer_diameter_mm": 100.0,
        "inner_radius_mm": 22.0,
        "outer_radius_mm": 33.0,
        "centerline_radius_mm": 27.5,
        "radial_swing_mm": 3.0,
        "start_angle_deg": -18.0,
        "slot_pitch_deg": 12.0,
        "turn_count": 5,
        "arc_segment_deg": 2.0,
        "max_arc_segment_count": 96,
        "trace_width_mm": 4.0,
        "trace_gap_mm": 1.0,
        "mitre_limit": 5.0,
        "terminal_pad_width_mm": 5.0,
        "terminal_pad_height_mm": 5.0,
        "terminal_offset_mm": 0.0,
        "aedt_handshake_mode": "polyline_points",
        "dxf_export_mode": "disabled",
    }


def _as_v2_spec(spec):
    base = v2_default_spec()
    if spec:
        base.update(deepcopy(spec))
    return base


def _require_positive(spec, key):
    if float(spec[key]) <= 0.0:
        raise ValueError("%s must be positive for V2 single-layer geometry" % key)


def _validate_v2_spec_values(spec):
    for key in [
        "copper_thickness_mm",
        "inner_radius_mm",
        "outer_radius_mm",
        "centerline_radius_mm",
        "radial_swing_mm",
        "slot_pitch_deg",
        "trace_width_mm",
        "trace_gap_mm",
        "terminal_pad_width_mm",
        "terminal_pad_height_mm",
        "mitre_limit",
    ]:
        _require_positive(spec, key)
    if int(spec["turn_count"]) < 1:
        raise ValueError("turn_count must be at least 1 for V2 single-layer geometry")
    if int(spec["max_arc_segment_count"]) < 1:
        raise ValueError("max_arc_segment_count must be at least 1")

    trace_half = float(spec["trace_width_mm"]) / 2.0
    inner_available = float(spec["inner_radius_mm"]) + trace_half
    outer_available = float(spec["outer_radius_mm"]) - trace_half
    if inner_available >= outer_available:
        raise ValueError("radius window must leave room for trace_width_mm")
    if not inner_available <= float(spec["centerline_radius_mm"]) <= outer_available:
        raise ValueError("centerline_radius_mm must stay inside the usable radius window")


def aedt_safe_name(value, fallback="AutoName"):
    fallback = str(fallback or "AutoName")
    fallback = "".join(
        char if char.isascii() and (char.isalnum() or char == "_") else "_"
        for char in fallback
    )
    fallback = re.sub(r"_+", "_", fallback).strip("_") or "AutoName"
    if not fallback[0].isascii() or not fallback[0].isalpha():
        fallback = "AutoName_" + fallback

    text = str(value or "")
    cleaned = "".join(
        char if char.isascii() and (char.isalnum() or char == "_") else "_"
        for char in text
    )
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = fallback
    elif not cleaned[0].isalpha():
        cleaned = "%s_%s" % (fallback, cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)

    if not _AEDT_NAME_PATTERN.match(cleaned):
        cleaned = fallback
    return cleaned


def v2_aedt_names(run_suffix=""):
    suffix = ""
    if run_suffix:
        suffix = "_" + aedt_safe_name(run_suffix, fallback="Run")

    return {
        "project_name": "DxfCopperV2SingleLayer",
        "design_name": "DxfCopperV2SingleLayer",
        "object_name": "AutoDxfCopperV2_PhaseA_L01",
        "sheet_name": "AutoDxfCopperV2_PhaseA_L01_Sheet",
        "mesh_name": "AutoDxfCopperV2_LengthMesh",
        "setup_name": "AutoDxfCopperV2_DC%s" % suffix,
        "voltage_assignment": "AutoDxfCopperV2_Voltage%s" % suffix,
        "sink_assignment": "AutoDxfCopperV2_Sink%s" % suffix,
    }


def build_single_layer_motor_intent(spec=None):
    spec = _as_v2_spec(spec)
    _validate_v2_spec_values(spec)
    return {
        "milestone": spec["milestone"],
        "geometry_contract_version": spec["geometry_contract_version"],
        "units": spec["units"],
        "topology_preset": spec["topology_preset"],
        "geometry_scope": spec["geometry_scope"],
        "full_phase_winding_enabled": bool(spec["full_phase_winding_enabled"]),
        "phase": spec["phase"],
        "layer": spec["layer"],
        "copper_thickness_mm": float(spec["copper_thickness_mm"]),
        "radii_mm": {
            "inner_radius_mm": float(spec["inner_radius_mm"]),
            "outer_radius_mm": float(spec["outer_radius_mm"]),
            "centerline_radius_mm": float(spec["centerline_radius_mm"]),
            "radial_swing_mm": float(spec["radial_swing_mm"]),
            "inner": float(spec["inner_radius_mm"]),
            "outer": float(spec["outer_radius_mm"]),
            "centerline": float(spec["centerline_radius_mm"]),
            "radial_swing": float(spec["radial_swing_mm"]),
        },
        "angles_deg": {
            "start_angle_deg": float(spec["start_angle_deg"]),
            "slot_pitch_deg": float(spec["slot_pitch_deg"]),
            "arc_segment_deg": float(spec["arc_segment_deg"]),
            "start": float(spec["start_angle_deg"]),
            "slot_pitch": float(spec["slot_pitch_deg"]),
        },
        "path_config": {
            "turn_count": int(spec["turn_count"]),
            "trace_width_mm": float(spec["trace_width_mm"]),
            "trace_gap_mm": float(spec["trace_gap_mm"]),
            "arc_segment_deg": float(spec["arc_segment_deg"]),
            "max_arc_segment_count": int(spec["max_arc_segment_count"]),
            "mitre_limit": float(spec["mitre_limit"]),
            "corner_policy": V2_CORNER_POLICY,
            "aedt_handshake_mode": spec["aedt_handshake_mode"],
            "dxf_export_mode": spec["dxf_export_mode"],
        },
        "terminal_config": {
            "terminal_pad_width_mm": float(spec["terminal_pad_width_mm"]),
            "terminal_pad_height_mm": float(spec["terminal_pad_height_mm"]),
            "terminal_offset_mm": float(spec["terminal_offset_mm"]),
            "pad_width_mm": float(spec["terminal_pad_width_mm"]),
            "pad_height_mm": float(spec["terminal_pad_height_mm"]),
            "offset_mm": float(spec["terminal_offset_mm"]),
            "role_detail": V2_TERMINAL_PAD_ROLE,
        },
        "manufacturing_constraints": {
            "max_outer_diameter_mm": float(spec["max_outer_diameter_mm"]),
            "minimum_copper_width_mm": float(spec["trace_width_mm"]),
            "minimum_clearance_mm": float(spec["trace_gap_mm"]),
            "corner_policy": V2_CORNER_POLICY,
            "full_phase_winding_enabled": bool(spec["full_phase_winding_enabled"]),
            "three_phase_enabled": bool(spec["three_phase_enabled"]),
            "six_layer_stack_enabled": bool(spec["six_layer_stack_enabled"]),
        },
    }


def polar_point(radius_mm, angle_deg):
    radians = math.radians(float(angle_deg))
    return [float(radius_mm) * math.cos(radians), float(radius_mm) * math.sin(radians)]


def _sample_arc_points(radius_mm, start_angle_deg, end_angle_deg, arc_segment_deg, max_count):
    start = float(start_angle_deg)
    end = float(end_angle_deg)
    step = abs(float(arc_segment_deg)) or 2.0
    max_segments = int(max_count)
    if max_segments < 1:
        raise ValueError("max_arc_segment_count must be at least 1")
    span = end - start
    segment_count = max(1, int(math.ceil(abs(span) / step)))
    # max_arc_segment_count limits arc segments, so returned points are segments + 1.
    segment_count = min(segment_count, max_segments)
    points = []
    for index in range(segment_count + 1):
        fraction = float(index) / float(segment_count)
        points.append(polar_point(radius_mm, start + span * fraction))
    return points


def _append_unique_points(target, source):
    for point in source:
        rounded = [round(float(point[0]), 6), round(float(point[1]), 6)]
        if not target or target[-1] != rounded:
            target.append(rounded)


def build_centerline_path(intent):
    radii = intent["radii_mm"]
    angles = intent["angles_deg"]
    path = intent["path_config"]
    terminal = intent["terminal_config"]
    turn_count = int(path["turn_count"])
    pitch = float(angles["slot_pitch"])
    start = float(angles["start"])
    center = float(radii["centerline"])
    swing = float(radii["radial_swing"])
    outer = min(float(radii["outer"]) - path["trace_width_mm"] / 2.0, center + swing)
    inner = max(float(radii["inner"]) + path["trace_width_mm"] / 2.0, center - swing)
    points = []
    max_count = int(path["max_arc_segment_count"])
    for turn_index in range(turn_count):
        arc_start = start + turn_index * pitch
        arc_end = arc_start + pitch
        radius = outer if turn_index % 2 == 0 else inner
        _append_unique_points(
            points,
            _sample_arc_points(radius, arc_start, arc_end, path["arc_segment_deg"], max_count),
        )
        if turn_index < turn_count - 1:
            next_radius = inner if radius == outer else outer
            _append_unique_points(points, [polar_point(next_radius, arc_end)])
    lead_offset = float(terminal["offset_mm"])
    if points:
        first = [points[0][0] - terminal["pad_width_mm"], points[0][1] + lead_offset]
        last = [points[-1][0] + terminal["pad_width_mm"], points[-1][1] + lead_offset]
        points.insert(0, [round(first[0], 6), round(first[1], 6)])
        points.append([round(last[0], 6), round(last[1], 6)])
    return points


def _line_from_centerline(points):
    if len(points) < 2:
        return LineString()
    return LineString([(float(x), float(y)) for x, y in points])


def _terminal_pad_polygons(centerline, intent):
    terminal = intent["terminal_config"]
    if len(centerline) < 2:
        return []
    pad_w = terminal["pad_width_mm"]
    pad_h = terminal["pad_height_mm"]
    first = centerline[0]
    last = centerline[-1]
    return [
        {
            "name": "PhaseA_L01_InputPad",
            "role": "source",
            "role_detail": terminal["role_detail"],
            "center_xy_mm": [first[0], first[1]],
            "size_xy_mm": [pad_w, pad_h],
            "polygon": _box_from_center(first[0], first[1], pad_w, pad_h),
        },
        {
            "name": "PhaseA_L01_ReturnPad",
            "role": "sink",
            "role_detail": terminal["role_detail"],
            "center_xy_mm": [last[0], last[1]],
            "size_xy_mm": [pad_w, pad_h],
            "polygon": _box_from_center(last[0], last[1], pad_w, pad_h),
        },
    ]


def _build_outline_polygon(centerline, intent):
    path = intent["path_config"]
    if path.get("corner_policy") != V2_CORNER_POLICY:
        raise ValueError("V2 corner policy must be flat_caps_mitred_joins_no_auto_rounding")
    line = _line_from_centerline(centerline)
    route = line.buffer(
        path["trace_width_mm"] / 2.0,
        cap_style=2,
        join_style=2,
        mitre_limit=path["mitre_limit"],
    )
    pad_infos = _terminal_pad_polygons(centerline, intent)
    shapes = [route] + [pad["polygon"] for pad in pad_infos]
    outline = unary_union(shapes)
    if outline.geom_type != "Polygon":
        raise ValueError(
            "V2 copper outline must resolve to one connected polygon; got %s"
            % outline.geom_type
        )
    return outline, pad_infos


def _terminal_records(pad_infos):
    return [
        {
            "name": pad["name"],
            "role": pad["role"],
            "role_detail": pad.get("role_detail", ""),
            "center_xy_mm": pad["center_xy_mm"],
            "size_xy_mm": pad["size_xy_mm"],
        }
        for pad in pad_infos
    ]


def _centerline_length_mm(points):
    length = 0.0
    for index in range(1, len(points)):
        ax, ay = points[index - 1]
        bx, by = points[index]
        length += math.hypot(float(bx) - float(ax), float(by) - float(ay))
    return length


def _geometry_estimates(geometry, polygon):
    return {
        "policy": "geometry_derived_estimate_not_final_validation",
        "path_length_mm": _centerline_length_mm(geometry.get("centerline_points_xy_mm", [])),
        "area_mm2": float(polygon.area),
        "systematic_error_sources": [
            "polyline_arc_approximation",
            "mitred_corner_outline",
            "terminal_pad_current_path_simplification",
            "single_layer_v2_scope",
        ],
    }


def _actual_arc_segment_count(intent):
    path = intent["path_config"]
    angles = intent["angles_deg"]
    step = abs(float(path["arc_segment_deg"])) or 2.0
    per_turn = max(1, int(math.ceil(abs(float(angles["slot_pitch"])) / step)))
    per_turn = min(per_turn, int(path["max_arc_segment_count"]))
    return int(path["turn_count"]) * per_turn


def _geometry_diagnostics(centerline, outline_points, intent):
    radii = [math.hypot(float(x), float(y)) for x, y in centerline]
    terminal = intent["terminal_config"]
    return {
        "topology_preset": intent["topology_preset"],
        "geometry_scope": intent["geometry_scope"],
        "full_phase_winding_enabled": bool(intent["full_phase_winding_enabled"]),
        "centerline_length_mm": _centerline_length_mm(centerline),
        "centerline_point_count": len(centerline),
        "outline_point_count": len(outline_points),
        "angular_span_deg": float(intent["path_config"]["turn_count"])
        * float(intent["angles_deg"]["slot_pitch"]),
        "radial_min_mm": min(radii) if radii else 0.0,
        "radial_max_mm": max(radii) if radii else 0.0,
        "terminal_pad_size_xy_mm": [terminal["pad_width_mm"], terminal["pad_height_mm"]],
        "terminal_pad_role": terminal["role_detail"],
        "arc_sampling_policy": "bounded_polyline_arc_approximation",
        "actual_arc_segment_count": _actual_arc_segment_count(intent),
        "max_arc_segment_count": int(intent["path_config"]["max_arc_segment_count"]),
    }


def build_single_layer_geometry(spec=None):
    spec = _as_v2_spec(spec)
    intent = build_single_layer_motor_intent(spec)
    centerline = build_centerline_path(intent)
    outline, pad_infos = _build_outline_polygon(centerline, intent)
    outline_points = _polygon_points_xy(outline)
    terminal_pads = _terminal_records(pad_infos)
    return {
        "geometry_contract_version": spec["geometry_contract_version"],
        "milestone": spec["milestone"],
        "units": spec["units"],
        "phase": spec["phase"],
        "layer": spec["layer"],
        "copper_thickness_mm": float(spec["copper_thickness_mm"]),
        "topology_preset": intent["topology_preset"],
        "geometry_scope": intent["geometry_scope"],
        "full_phase_winding_enabled": bool(intent["full_phase_winding_enabled"]),
        "centerline_points_xy_mm": centerline,
        "outline_points_xy_mm": outline_points,
        "aedt_polyline_points_mm": _aedt_polyline_points(outline_points),
        "terminal_pads": terminal_pads,
        "terminals": _terminal_records(pad_infos),
        "estimates": _geometry_estimates({"centerline_points_xy_mm": centerline}, outline),
        "diagnostics": _geometry_diagnostics(centerline, outline_points, intent),
        "metadata": {
            "source_kind": "parameterized_single_layer",
            "topology_preset": intent["topology_preset"],
            "geometry_scope": intent["geometry_scope"],
            "full_phase_winding_enabled": bool(intent["full_phase_winding_enabled"]),
            "arc_segment_deg": float(spec["arc_segment_deg"]),
            "trace_width_mm": float(spec["trace_width_mm"]),
            "trace_gap_mm": float(spec["trace_gap_mm"]),
            "terminal_pad_role": V2_TERMINAL_PAD_ROLE,
            "corner_policy": V2_CORNER_POLICY,
            "buffer_cap_style": "flat",
            "buffer_join_style": "mitre",
            "mitre_limit": float(spec["mitre_limit"]),
            "estimate_policy": "geometry_derived_estimate_not_final_validation",
            "dxf_export_mode": spec["dxf_export_mode"],
        },
        "manufacturing_constraints": intent["manufacturing_constraints"],
    }


def export_single_layer_dxf_preview(geometry, output_path):
    if geometry.get("metadata", {}).get("dxf_export_mode", "disabled") == "disabled":
        return {"status": "disabled", "blocking": False, "output_path": output_path}
    try:
        import ezdxf
    except Exception:
        return {"status": "dependency_missing", "blocking": False, "output_path": output_path}
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    points = [(float(x), float(y)) for x, y in geometry.get("outline_points_xy_mm", [])]
    if points:
        msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "COPPER_OUTLINE"})
    doc.saveas(output_path)
    return {"status": "exported", "blocking": False, "output_path": output_path}


def _box_from_center(center_x, center_y, width, height):
    half_w = float(width) / 2.0
    half_h = float(height) / 2.0
    return box(center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)


def _polygon_points_xy(polygon):
    return [[float(x), float(y)] for x, y in polygon.exterior.coords]


def _aedt_polyline_points(points_xy):
    source = points_xy[:-1] if points_xy and points_xy[0] == points_xy[-1] else points_xy
    return [[float(x), float(y), 0.0] for x, y in source]


def build_v1_phase_a_geometry(spec=None):
    spec = _as_spec(spec)
    route_length = float(spec["route_length_mm"])
    route_width = float(spec["route_width_mm"])
    pad_width = float(spec["terminal_pad_width_mm"])
    pad_height = float(spec["terminal_pad_height_mm"])

    left_pad_center = [-(route_length + pad_width) / 2.0, 0.0]
    right_pad_center = [(route_length + pad_width) / 2.0, 0.0]

    route = _box_from_center(0.0, 0.0, route_length, route_width)
    left_pad = _box_from_center(left_pad_center[0], left_pad_center[1], pad_width, pad_height)
    right_pad = _box_from_center(right_pad_center[0], right_pad_center[1], pad_width, pad_height)
    outline = unary_union([route, left_pad, right_pad])
    if outline.geom_type != "Polygon":
        raise ValueError("V1 copper outline must resolve to one connected polygon")

    outline_points = _polygon_points_xy(outline)
    terminals = [
        {
            "name": "PhaseA_L01_InputPad",
            "role": "source",
            "center_xy_mm": left_pad_center,
            "size_xy_mm": [pad_width, pad_height],
        },
        {
            "name": "PhaseA_L01_ReturnPad",
            "role": "sink",
            "center_xy_mm": right_pad_center,
            "size_xy_mm": [pad_width, pad_height],
        },
    ]

    return {
        "geometry_contract_version": spec["geometry_contract_version"],
        "units": spec["units"],
        "phase": spec["phase"],
        "layer": spec["layer"],
        "copper_thickness_mm": float(spec["copper_thickness_mm"]),
        "aedt_handshake_mode": spec["aedt_handshake_mode"],
        "outline_points_xy_mm": outline_points,
        "aedt_polyline_points_mm": _aedt_polyline_points(outline_points),
        "terminals": terminals,
        "manufacturing_constraints": {
            "max_outer_diameter_mm": float(spec["max_outer_diameter_mm"]),
            "minimum_copper_width_mm": float(spec["minimum_copper_width_mm"]),
            "minimum_clearance_mm": float(spec["minimum_clearance_mm"]),
        },
        "source_note": (
            "Minimal V1 Phase A copper plate generated from one 2D polygon source. "
            "This is not the legacy phase-belt sector envelope."
        ),
    }


def _polygon_from_geometry(geometry):
    points = geometry.get("outline_points_xy_mm", [])
    if len(points) < 4:
        return Polygon()
    return Polygon(points)


def _bounding_diameter_mm(points):
    if not points:
        return 0.0
    return 2.0 * max(hypot(float(x), float(y)) for x, y in points)


def validate_v1_geometry(geometry):
    polygon = _polygon_from_geometry(geometry)
    points = geometry.get("outline_points_xy_mm", [])
    constraints = geometry.get("manufacturing_constraints", {})
    terminals = geometry.get("terminals", [])
    closed = bool(points) and points[0] == points[-1]
    bounding_diameter = _bounding_diameter_mm(points)
    minimum_clearance = float(constraints.get("minimum_clearance_mm", 0.0))
    max_diameter = float(constraints.get("max_outer_diameter_mm", 0.0))

    issues = []
    if not closed:
        issues.append("outline is not explicitly closed")
    if not polygon.is_valid:
        issues.append("outline polygon is not valid")
    if polygon.is_empty or polygon.area <= 0.0:
        issues.append("outline polygon has no usable area")
    if max_diameter > 0.0 and bounding_diameter > max_diameter:
        issues.append("outline exceeds maximum outer diameter")
    if len(terminals) != 2:
        issues.append("V1 requires exactly two terminal pads")

    return {
        "closed": closed,
        "valid": len(issues) == 0,
        "shapely_valid": bool(polygon.is_valid),
        "area_mm2": float(polygon.area),
        "bounding_diameter_mm": bounding_diameter,
        "terminal_count": len(terminals),
        "minimum_clearance_mm": minimum_clearance,
        "aedt_handshake_mode": geometry.get("aedt_handshake_mode"),
        "issues": issues,
    }


def validate_single_layer_geometry(geometry):
    polygon = _polygon_from_geometry(geometry)
    points = geometry.get("outline_points_xy_mm", [])
    constraints = geometry.get("manufacturing_constraints", {})
    terminals = geometry.get("terminals", [])
    closed = bool(points) and points[0] == points[-1]
    bounding_diameter = _bounding_diameter_mm(points)
    max_diameter = float(constraints.get("max_outer_diameter_mm", 0.0))
    minimum_width = float(constraints.get("minimum_copper_width_mm", 0.0))
    minimum_clearance = float(constraints.get("minimum_clearance_mm", 0.0))
    metadata = geometry.get("metadata", {})
    actual_width = float(metadata.get("trace_width_mm", 0.0))
    actual_clearance = float(metadata.get("trace_gap_mm", 0.0))
    issues = []
    if not closed:
        issues.append("outline_not_closed")
    if not polygon.is_valid:
        issues.append("outline_polygon_invalid")
    if polygon.is_empty or polygon.area <= 0.0:
        issues.append("outline_polygon_empty")
    if max_diameter > 0.0 and bounding_diameter > max_diameter:
        issues.append("outline_exceeds_max_outer_diameter")
    if len(terminals) != 2:
        issues.append("terminal_count_not_two")
    if minimum_width > 0.0 and actual_width < minimum_width:
        issues.append("minimum_copper_width_violation")
    if minimum_clearance > 0.0 and actual_clearance < minimum_clearance:
        issues.append("minimum_clearance_violation")
    return {
        "closed": closed,
        "valid": len(issues) == 0,
        "self_intersection_free": bool(polygon.is_valid),
        "area_mm2": float(polygon.area),
        "bounding_diameter_mm": bounding_diameter,
        "minimum_width_mm": minimum_width,
        "minimum_clearance_mm": minimum_clearance,
        "actual_width_mm": actual_width,
        "actual_clearance_mm": actual_clearance,
        "terminal_count": len(terminals),
        "issues": issues,
    }
