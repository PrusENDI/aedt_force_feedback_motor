from __future__ import print_function

from copy import deepcopy
from math import hypot

from shapely.geometry import Polygon
from shapely.geometry import box
from shapely.ops import unary_union


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
