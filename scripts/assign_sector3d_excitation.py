from __future__ import print_function

import math
import os
import traceback

from aedt_native_common import Logger
from aedt_native_common import ensure_workspace_dirs
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
from sector3d_aedt import delete_named_boundaries_if_present
from sector3d_aedt import design_variable_number
from sector3d_aedt import ensure_macro_phase_belts
from sector3d_aedt import list_excitations_of_type
from sector3d_aedt import save_sector3d_project


PHASE_NAMES = ["PhaseA", "PhaseB", "PhaseC"]


def _phase_expression(project_cfg, phase_name):
    winding_cfg = project_cfg.get("sector_3d", {}).get("winding", {})
    mapping = {
        "PhaseA": winding_cfg.get("phase_a_expression", "phase_current_rms"),
        "PhaseB": winding_cfg.get("phase_b_expression", "phase_current_rms"),
        "PhaseC": winding_cfg.get("phase_c_expression", "phase_current_rms")
    }
    return mapping[phase_name]


def _winding_name(phase_name):
    return "%s_Winding" % phase_name


def _coil_name(phase_name, polarity):
    return "%s_Coil_%s" % (phase_name, "Pos" if polarity == "Positive" else "Neg")


def _coil_terminal_name(phase_name, polarity, index):
    return "%s_%s_%03d" % (_coil_name(phase_name, polarity), "Terminal", int(index))


def _phase_boundary_name_prefix(phase_name):
    return [
        _winding_name(phase_name),
        _coil_name(phase_name, "Positive"),
        _coil_name(phase_name, "Negative"),
        "%s_Current_Pos" % phase_name,
        "%s_Current_Neg" % phase_name,
        "%s_JRadial" % phase_name
    ]


def _write_markdown(path, summary):
    lines = []
    lines.append("# Sector3D Excitation Assignment Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- design_name_matches_required: `%s`" % summary.get("design_name_matches_required", False))
    lines.append("- save_ok: `%s`" % summary.get("save_ok", False))
    lines.append("- save_method: `%s`" % summary.get("save_method", ""))
    lines.append("- save_error: `%s`" % summary.get("save_error", ""))
    lines.append("- phase_belt_reused: `%s`" % summary.get("phase_belt_reused", False))
    lines.append("- phase_belt_segment_count: `%s`" % summary.get("phase_belt_segment_count", 0))
    lines.append("")
    lines.append("## Phase Belt Geometry")
    lines.append("")
    lines.append("- phase_belt_angle_deg: `%s`" % summary.get("phase_belt_angle_deg", ""))
    lines.append("- phase_belt_gap_deg: `%s`" % summary.get("phase_belt_gap_deg", ""))
    lines.append("- phase_segment_angle_deg: `%s`" % summary.get("phase_segment_angle_deg", ""))
    lines.append("- phase_belt_angle_source: `%s`" % summary.get("phase_belt_angle_source", ""))
    lines.append("- sector_start_angle_deg: `%s`" % summary.get("sector_start_angle_deg", ""))
    lines.append("- source_sink_terminal_sheet_count: `%s`" % len(summary.get("source_sink_terminal_sheets", [])))
    lines.append("")
    lines.append("## Winding Results")
    lines.append("")
    for item in summary.get("winding_results", []):
        lines.append(
            "- %s: assigned=`%s`, fallback_current=`%s`, positive_objects=`%s`, negative_objects=`%s`, terminals=`%s`, direct_currents=`%s`, details=`%s`"
            % (
                item.get("phase_name", ""),
                item.get("assigned", False),
                item.get("used_fallback_current_boundaries", False),
                item.get("positive_object_count", 0),
                item.get("negative_object_count", 0),
                item.get("coil_terminal_count", 0),
                item.get("current_boundary_count", 0),
                item.get("details", "")
            )
        )
    lines.append("")
    lines.append("## Current Excitations Seen")
    lines.append("")
    excitations = summary.get("current_excitations", [])
    if not excitations:
        lines.append("- None")
    else:
        for name in excitations:
            lines.append("- %s" % name)
    lines.append("")
    lines.append("## Winding Excitations Seen")
    lines.append("")
    windings = summary.get("winding_excitations", [])
    if not windings:
        lines.append("- None")
    else:
        for name in windings:
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


def _raise_if_sector3d_excitation_failed(summary):
    reasons = []
    winding_results = list(summary.get("winding_results", []) or [])
    if not winding_results:
        reasons.append("no phase winding results were recorded")
    elif not all(item.get("assigned", False) for item in winding_results):
        failed_phases = [
            "%s: %s" % (item.get("phase_name", ""), item.get("details", ""))
            for item in winding_results
            if not item.get("assigned", False)
        ]
        reasons.append("one or more phases have no usable excitation (%s)" % "; ".join(failed_phases))

    current_excitations = list(summary.get("current_excitations", []) or [])
    winding_excitations = list(summary.get("winding_excitations", []) or [])
    if (not current_excitations) and (not winding_excitations):
        reasons.append("AEDT reports no Current or Winding Group excitations")

    if not summary.get("save_ok", False):
        reasons.append("project save failed: %s" % summary.get("save_error", ""))

    if reasons:
        raise RuntimeError("Sector3D excitation assignment failed: " + " | ".join(reasons))


def _xy_radius(point):
    return math.sqrt((float(point[0]) ** 2) + (float(point[1]) ** 2))


def _face_center(face):
    center = getattr(face, "center", None)
    if not center:
        return None
    try:
        out = [float(value) for value in list(center)]
    except Exception:
        return None
    while len(out) < 3:
        out.append(0.0)
    return out[:3]


def _phase_object_terminal_faces(app, object_name):
    obj = app.modeler.get_object_from_name(object_name)
    if not obj:
        raise RuntimeError("Could not resolve phase-belt object %s in the Maxwell modeler" % object_name)
    candidates = []
    for face in getattr(obj, "faces", []) or []:
        center = _face_center(face)
        if not center:
            continue
        candidates.append(
            {
                "face_id": int(getattr(face, "id")),
                "center": center,
                "radius": _xy_radius(center)
            }
        )
    if len(candidates) < 2:
        raise RuntimeError("Could not find enough usable faces on %s for radial terminal assignment" % object_name)
    ordered = sorted(candidates, key=lambda item: item["radius"])
    inner_face = ordered[0]
    outer_face = ordered[-1]
    if inner_face["face_id"] == outer_face["face_id"]:
        raise RuntimeError("Could not distinguish inner/outer terminal faces on %s" % object_name)
    if abs(float(outer_face["radius"]) - float(inner_face["radius"])) <= 1e-9:
        raise RuntimeError("Terminal face radii collapsed on %s; radial current path is ambiguous" % object_name)
    return {
        "object_name": object_name,
        "inner_face_id": inner_face["face_id"],
        "inner_face_center": inner_face["center"],
        "inner_radius": inner_face["radius"],
        "outer_face_id": outer_face["face_id"],
        "outer_face_center": outer_face["center"],
        "outer_radius": outer_face["radius"]
    }


def _phase_object_terminal_specs(app, object_name, phase_name, belt_polarity):
    faces = _phase_object_terminal_faces(app, object_name)
    if belt_polarity == "Positive":
        positive_face_id = faces["inner_face_id"]
        negative_face_id = faces["outer_face_id"]
        positive_radial_side = "Inner"
        negative_radial_side = "Outer"
    else:
        positive_face_id = faces["outer_face_id"]
        negative_face_id = faces["inner_face_id"]
        positive_radial_side = "Outer"
        negative_radial_side = "Inner"
    return {
        "phase_name": phase_name,
        "object_name": object_name,
        "belt_polarity": belt_polarity,
        "positive_face_id": positive_face_id,
        "negative_face_id": negative_face_id,
        "positive_radial_side": positive_radial_side,
        "negative_radial_side": negative_radial_side,
        "inner_face_id": faces["inner_face_id"],
        "outer_face_id": faces["outer_face_id"],
        "inner_radius": faces["inner_radius"],
        "outer_radius": faces["outer_radius"]
    }


def _collect_phase_terminal_specs(app, phase_name, positive_objects, negative_objects):
    terminal_specs = []
    for belt_polarity, objects in [("Positive", positive_objects), ("Negative", negative_objects)]:
        for object_name in objects:
            terminal_specs.append(_phase_object_terminal_specs(app, object_name, phase_name, belt_polarity))
    return terminal_specs


def _positive_float(value, default_value=None):
    try:
        number = float(value)
    except Exception:
        return default_value
    if number > 0.0:
        return number
    return default_value


def _sector_geometry_from_config(project_cfg):
    sector_cfg = project_cfg.get("sector_3d", {})
    machine_cfg = project_cfg.get("machine_fixed", {})
    pole_count = max(2, int(round(float(machine_cfg.get("pole_count", 24)))))
    sector_pole_count = max(1, int(round(float(sector_cfg.get("sector_model_pole_count", 2)))))
    sector_pole_count = min(pole_count, sector_pole_count)
    sweep_angle_deg = 360.0 * float(sector_pole_count) / float(pole_count)
    center_angle_deg = float(sector_cfg.get("sector_center_angle_deg", 0.0))
    start_angle_deg = center_angle_deg - 0.5 * sweep_angle_deg
    phase_belt_count = max(1, sector_pole_count * 3)
    return {
        "start_angle_deg": start_angle_deg,
        "sweep_angle_deg": sweep_angle_deg,
        "phase_belt_count": phase_belt_count,
    }


def _resolve_phase_belt_angle_context(phase_belts, build_metadata=None, project_cfg=None):
    build_metadata = build_metadata or {}
    sector_geometry = dict(build_metadata.get("sector_geometry", {}) or {})
    if (not sector_geometry) and project_cfg:
        sector_geometry = _sector_geometry_from_config(project_cfg)

    phase_belt_count = int(round(float(sector_geometry.get("phase_belt_count", 0) or 0)))
    sweep_angle_deg = float(sector_geometry.get("sweep_angle_deg", 0.0) or 0.0)
    if phase_belt_count <= 0 and sweep_angle_deg > 0.0:
        phase_belt_count = max(1, int(round(sweep_angle_deg / 5.0)))

    phase_belt_angle_deg = _positive_float(phase_belts.get("phase_belt_angle_deg"))
    source = "live_phase_belts"
    if phase_belt_angle_deg is None:
        phase_belt_angle_deg = _positive_float(build_metadata.get("phase_belt_angle_deg"))
        source = "build_artifact"
    if phase_belt_angle_deg is None and sweep_angle_deg > 0.0 and phase_belt_count > 0:
        phase_belt_angle_deg = sweep_angle_deg / float(phase_belt_count)
        source = "sector_geometry"
    if phase_belt_angle_deg is None:
        phase_belt_angle_deg = 5.0
        source = "default"

    phase_belt_gap_deg = _positive_float(phase_belts.get("phase_belt_gap_deg"))
    if phase_belt_gap_deg is None:
        phase_belt_gap_deg = _positive_float(build_metadata.get("phase_belt_gap_deg"))
    if phase_belt_gap_deg is None:
        phase_belt_gap_deg = min(0.08, max(0.01, phase_belt_angle_deg * 0.01))

    phase_segment_angle_deg = _positive_float(phase_belts.get("phase_segment_angle_deg"))
    if phase_segment_angle_deg is None:
        phase_segment_angle_deg = _positive_float(build_metadata.get("phase_segment_angle_deg"))
    if phase_segment_angle_deg is None:
        phase_segment_angle_deg = max(0.001, phase_belt_angle_deg - phase_belt_gap_deg)

    return {
        "source": source,
        "sector_start_angle_deg": float(sector_geometry.get("start_angle_deg", -15.0) or -15.0),
        "phase_belt_count": phase_belt_count,
        "phase_belt_angle_deg": phase_belt_angle_deg,
        "phase_belt_gap_deg": phase_belt_gap_deg,
        "phase_segment_angle_deg": phase_segment_angle_deg,
    }


def _terminal_sheet_center_angle_deg(belt_index, angle_context):
    segment_start_angle_deg = (
        float(angle_context.get("sector_start_angle_deg", -15.0))
        + (float(belt_index) - 1.0) * float(angle_context.get("phase_belt_angle_deg", 5.0))
        + 0.5 * float(angle_context.get("phase_belt_gap_deg", 0.05))
    )
    return segment_start_angle_deg + 0.5 * float(angle_context.get("phase_segment_angle_deg", 4.95))


def _object_phase_belt_index(object_name):
    try:
        return int(str(object_name).split("_")[-1])
    except Exception:
        raise RuntimeError("Could not parse phase-belt index from object name %s" % object_name)


def _object_face_label(object_name):
    text = str(object_name)
    if "_Bottom_" in text:
        return "Bottom"
    if "_Top_" in text:
        return "Top"
    raise RuntimeError("Could not parse top/bottom face label from object name %s" % object_name)


def _terminal_sheet_name(phase_name, terminal_polarity, object_name, radial_side):
    return "Auto3D_SourceSink_%s_%s_%s_%03d_%s" % (
        phase_name,
        "Pos" if terminal_polarity == "Positive" else "Neg",
        _object_face_label(object_name),
        _object_phase_belt_index(object_name),
        radial_side,
    )


def _sheet_attributes(name):
    return [
        "NAME:Attributes",
        "Name:=", name,
        "Flags:=", "",
        "Color:=", "(255 230 80)",
        "Transparency:=", 0.55,
        "PartCoordinateSystem:=", "Global",
        "UDMId:=", "",
        "MaterialValue:=", "\"vacuum\"",
        "SurfaceMaterialValue:=", "\"\"",
        "SolveInside:=", False,
    ]


def _modeler_editor(app):
    editor = getattr(getattr(app, "modeler", None), "oeditor", None)
    if editor:
        return editor
    editor = getattr(getattr(app, "modeler", None), "oEditor", None)
    if editor:
        return editor
    raise RuntimeError("Could not resolve the active Maxwell 3D modeler editor")


def _delete_source_sink_sheets(app, sheet_names, logger):
    editor = _modeler_editor(app)
    existing = []
    for sheet_name in sheet_names:
        matches = []
        try:
            matches = list(editor.GetMatchedObjectName(sheet_name))
        except Exception:
            matches = []
        for match in matches:
            text = str(match)
            if text == sheet_name and text not in existing:
                existing.append(text)
    if not existing:
        return []
    try:
        editor.Delete(["NAME:Selections", "Selections:=", ",".join(existing)])
        logger.log("Deleted %d stale Sector3D source/sink terminal sheets" % len(existing))
        return existing
    except Exception:
        logger.log("Could not delete stale source/sink terminal sheets: %s" % ", ".join(existing))
        logger.log(traceback.format_exc())
        return existing


def _create_terminal_sheet(app, sheet_name, object_name, radial_side, angle_context, logger):
    editor = _modeler_editor(app)
    belt_index = _object_phase_belt_index(object_name)
    face_label = _object_face_label(object_name)
    center_angle_deg = _terminal_sheet_center_angle_deg(belt_index, angle_context)
    if radial_side == "Inner":
        radius_expr = "auto3d_flat_copper_inner_radius_mm"
    elif radial_side == "Outer":
        radius_expr = "auto3d_flat_copper_outer_radius_mm"
    else:
        raise RuntimeError("Unexpected terminal radial side %s" % radial_side)
    if face_label == "Bottom":
        z_start_expr = "auto3d_z_lower_flat_copper_mm"
    else:
        z_start_expr = "auto3d_z_upper_flat_copper_mm"
    width_expr = "2*%s*sin(%.12gdeg/2)" % (radius_expr, float(angle_context["phase_segment_angle_deg"]))
    try:
        editor.CreateRectangle(
            [
                "NAME:RectangleParameters",
                "IsCovered:=", True,
                "XStart:=", radius_expr,
                "YStart:=", "-(%s)/2" % width_expr,
                "ZStart:=", z_start_expr,
                "Width:=", width_expr,
                "Height:=", "auto3d_flat_copper_face_pack_height_mm",
                "WhichAxis:=", "X",
            ],
            _sheet_attributes(sheet_name),
        )
        if abs(center_angle_deg) > 1.0e-9:
            editor.Rotate(
                [
                    "NAME:Selections",
                    "Selections:=", sheet_name,
                    "NewPartsModelFlag:=", "Model",
                ],
                [
                    "NAME:RotateParameters",
                    "RotateAxis:=", "Z",
                    "RotateAngle:=", "%.12gdeg" % center_angle_deg,
                ],
            )
    except Exception:
        logger.log("Could not create source/sink terminal sheet %s for %s" % (sheet_name, object_name))
        logger.log(traceback.format_exc())
        raise
    logger.log(
        "Created source/sink terminal sheet %s for %s %s at %.6gdeg"
        % (sheet_name, object_name, radial_side, center_angle_deg)
    )
    return {
        "name": sheet_name,
        "object_name": object_name,
        "radial_side": radial_side,
        "center_angle_deg": center_angle_deg,
        "face_label": face_label,
        "angle_source": angle_context.get("source", ""),
    }


def _ensure_phase_terminal_sheets(app, phase_name, terminal_specs, phase_belts, angle_context, logger):
    sheet_names = []
    for terminal_spec in terminal_specs:
        object_name = terminal_spec["object_name"]
        sheet_names.append(_terminal_sheet_name(phase_name, "Positive", object_name, terminal_spec["positive_radial_side"]))
        sheet_names.append(_terminal_sheet_name(phase_name, "Negative", object_name, terminal_spec["negative_radial_side"]))
    _delete_source_sink_sheets(app, sheet_names, logger)
    sheet_details = []
    for terminal_spec in terminal_specs:
        object_name = terminal_spec["object_name"]
        positive_sheet = _terminal_sheet_name(phase_name, "Positive", object_name, terminal_spec["positive_radial_side"])
        negative_sheet = _terminal_sheet_name(phase_name, "Negative", object_name, terminal_spec["negative_radial_side"])
        sheet_details.append(
            _create_terminal_sheet(app, positive_sheet, object_name, terminal_spec["positive_radial_side"], angle_context, logger)
        )
        sheet_details.append(
            _create_terminal_sheet(app, negative_sheet, object_name, terminal_spec["negative_radial_side"], angle_context, logger)
        )
        terminal_spec["positive_terminal_sheet"] = positive_sheet
        terminal_spec["negative_terminal_sheet"] = negative_sheet
    return list(terminal_specs), sheet_details


def _assign_current_boundary_with_variants(
    app,
    current_expression,
    object_name,
    face_id,
    sheet_name,
    swap_direction,
    boundary_name,
):
    attempts = []
    if sheet_name:
        attempts.append(("sheet", [sheet_name], "sheet=%s" % sheet_name))
    attempts.extend([
        ("face", [face_id], "face=%s" % face_id),
        ("object", [object_name], "object=%s" % object_name),
    ])
    failures = []
    for assignment_kind, assignment, description in attempts:
        try:
            current = app.assign_current(
                assignment=assignment,
                amplitude=current_expression,
                solid=True,
                swap_direction=swap_direction,
                name=boundary_name,
                excitation_model="Double Potentials",
            )
        except Exception as exc:
            failures.append("%s (%s)" % (description, exc))
            continue
        if current:
            return current, assignment_kind
        failures.append("%s (returned no boundary object)" % description)
    raise RuntimeError("; ".join(failures))


class _NativeWindingGroup(object):
    def __init__(self, name, assignment_mode):
        self.name = name
        self.assignment_mode = assignment_mode


def _native_winding_group_args(winding_name, current_expression, is_solid=True, include_phase=False):
    args = [
        "NAME:%s" % winding_name,
        "Type:=", "Current",
        "IsSolid:=", bool(is_solid),
        "Current:=", current_expression,
        "Resistance:=", "0ohm",
        "Inductance:=", "0H",
        "Voltage:=", "0V",
        "ParallelBranchesNum:=", "1",
    ]
    if include_phase:
        args.extend(["Phase:=", "0deg"])
    return args


def _assign_winding_group_native_first(app, winding_name, current_expression, logger):
    failures = []
    attempts = [
        ("native_assign_winding_group_no_phase", _native_winding_group_args(winding_name, current_expression, True, False)),
        ("native_assign_winding_group_with_phase", _native_winding_group_args(winding_name, current_expression, True, True)),
    ]
    for mode, args in attempts:
        try:
            app.oboundary.AssignWindingGroup(args)
            logger.log("Created winding group %s via %s" % (winding_name, mode))
            return _NativeWindingGroup(winding_name, mode)
        except Exception as exc:
            failures.append("%s (%s)" % (mode, exc))

    try:
        winding = app.assign_winding(
            assignment=None,
            winding_type="Current",
            is_solid=True,
            current=current_expression,
            parallel_branches=1,
            name=winding_name
        )
        if winding:
            logger.log("Created winding group %s via pyaedt_assign_winding" % winding.name)
            return _NativeWindingGroup(winding.name, "pyaedt_assign_winding")
        failures.append("pyaedt_assign_winding (returned no boundary object)")
    except Exception as exc:
        failures.append("pyaedt_assign_winding (%s)" % exc)
    raise RuntimeError("; ".join(failures))


def _add_winding_terminals_native(app, winding_name, coil_terminal_names, logger):
    failures = []
    try:
        app.oboundary.AddWindingTerminals(winding_name, coil_terminal_names)
        return "native_add_winding_terminals_list"
    except Exception as exc:
        failures.append("native_list (%s)" % exc)

    added = []
    try:
        for coil_terminal_name in coil_terminal_names:
            app.oboundary.AddWindingTerminals(winding_name, [coil_terminal_name])
            added.append(coil_terminal_name)
        return "native_add_winding_terminals_one_item_lists"
    except Exception as exc:
        failures.append("native_one_item_lists after %s (%s)" % (len(added), exc))

    added = []
    try:
        for coil_terminal_name in coil_terminal_names:
            app.oboundary.AddWindingTerminals(winding_name, coil_terminal_name)
            added.append(coil_terminal_name)
        return "native_add_winding_terminals_strings"
    except Exception as exc:
        failures.append("native_strings after %s (%s)" % (len(added), exc))

    try:
        app.add_winding_coils(winding_name, coil_terminal_names)
        return "pyaedt_add_winding_coils"
    except Exception as exc:
        failures.append("pyaedt_add_winding_coils (%s)" % exc)
    logger.log("AddWindingTerminals failed for %s terminals: %s" % (winding_name, "; ".join(failures)))
    raise RuntimeError("; ".join(failures))


def _assign_phase_with_winding_group(app, phase_name, current_expression, positive_objects, negative_objects, turns_per_phase, logger, terminal_specs=None):
    boundary_names = _phase_boundary_name_prefix(phase_name)
    total_objects = len(positive_objects) + len(negative_objects)
    for index in range(1, total_objects + 1):
        boundary_names.append(_coil_terminal_name(phase_name, "Positive", index))
        boundary_names.append(_coil_terminal_name(phase_name, "Negative", index))
    deleted = delete_named_boundaries_if_present(app, boundary_names, logger)
    conductors_per_terminal = max(1, int(round(max(1.0, turns_per_phase) / float(max(1, total_objects)))))
    coil_terminal_names = []
    if terminal_specs is None:
        terminal_specs = _collect_phase_terminal_specs(app, phase_name, positive_objects, negative_objects)
    face_assignments = list(terminal_specs)
    winding = _assign_winding_group_native_first(app, _winding_name(phase_name), current_expression, logger)
    positive_index = 0
    negative_index = 0
    for terminal_spec in terminal_specs:
        belt_polarity = terminal_spec["belt_polarity"]
        object_name = terminal_spec["object_name"]
        positive_index += 1
        positive_assignment = terminal_spec.get("positive_terminal_sheet") or terminal_spec["positive_face_id"]
        terminal = app.assign_coil(
            assignment=[positive_assignment],
            conductors_number=conductors_per_terminal,
            polarity="Positive",
            name=_coil_terminal_name(phase_name, "Positive", positive_index)
        )
        if not terminal:
            raise RuntimeError(
                "Could not create positive coil terminal on face %s for %s (%s belt)"
                % (terminal_spec["positive_face_id"], object_name, belt_polarity)
            )
        coil_terminal_names.append(terminal.name)
        logger.log("Created coil terminal %s on %s" % (terminal.name, positive_assignment))
        negative_index += 1
        negative_assignment = terminal_spec.get("negative_terminal_sheet") or terminal_spec["negative_face_id"]
        terminal = app.assign_coil(
            assignment=[negative_assignment],
            conductors_number=conductors_per_terminal,
            polarity="Negative",
            name=_coil_terminal_name(phase_name, "Negative", negative_index)
        )
        if not terminal:
            raise RuntimeError(
                "Could not create negative coil terminal on face %s for %s (%s belt)"
                % (terminal_spec["negative_face_id"], object_name, belt_polarity)
            )
        coil_terminal_names.append(terminal.name)
        logger.log("Created coil terminal %s on %s" % (terminal.name, negative_assignment))
    add_mode = _add_winding_terminals_native(app, winding.name, coil_terminal_names, logger)
    logger.log(
        "Assigned winding %s with current=%s using %s and %s"
        % (winding.name, current_expression, winding.assignment_mode, add_mode)
    )
    return {
        "phase_name": phase_name,
        "assigned": True,
        "used_fallback_current_boundaries": False,
        "deleted_existing": bool(deleted),
        "winding_name": winding.name,
        "coil_terminal_count": len(coil_terminal_names),
        "coil_terminal_names": coil_terminal_names,
        "face_assignments": face_assignments,
        "conductors_per_terminal": conductors_per_terminal,
        "winding_assignment_mode": winding.assignment_mode,
        "winding_terminal_add_mode": add_mode,
        "positive_object_count": len(positive_objects),
        "negative_object_count": len(negative_objects),
        "details": "native winding group created before segmented source/sink sheet coil terminals, then terminals added to the group"
    }


def _assign_phase_with_direct_current(app, phase_name, current_expression, positive_objects, negative_objects, logger, terminal_specs=None):
    boundary_names = _phase_boundary_name_prefix(phase_name)
    total_objects = len(positive_objects) + len(negative_objects)
    for index in range(1, total_objects + 1):
        boundary_names.append("%s_Current_Pos_%03d" % (phase_name, index))
        boundary_names.append("%s_Current_Neg_%03d" % (phase_name, index))
    deleted = delete_named_boundaries_if_present(app, boundary_names, logger)
    current_names = []
    if terminal_specs is None:
        terminal_specs = _collect_phase_terminal_specs(app, phase_name, positive_objects, negative_objects)
    face_assignments = list(terminal_specs)
    assignment_modes = []
    positive_index = 0
    negative_index = 0
    for terminal_spec in terminal_specs:
        object_name = terminal_spec["object_name"]
        positive_index += 1
        current_name = "%s_Current_Pos_%03d" % (phase_name, positive_index)
        current, assignment_mode = _assign_current_boundary_with_variants(
            app,
            current_expression,
            object_name,
            terminal_spec["positive_face_id"],
            terminal_spec.get("positive_terminal_sheet", ""),
            False,
            current_name,
        )
        current_names.append(current.name)
        assignment_modes.append(
            {
                "boundary_name": current.name,
                "mode": assignment_mode,
                "polarity": "Positive",
                "object_name": object_name,
            }
        )
        negative_index += 1
        current_name = "%s_Current_Neg_%03d" % (phase_name, negative_index)
        current, assignment_mode = _assign_current_boundary_with_variants(
            app,
            current_expression,
            object_name,
            terminal_spec["negative_face_id"],
            terminal_spec.get("negative_terminal_sheet", ""),
            True,
            current_name,
        )
        current_names.append(current.name)
        assignment_modes.append(
            {
                "boundary_name": current.name,
                "mode": assignment_mode,
                "polarity": "Negative",
                "object_name": object_name,
            }
        )
    logger.log("Assigned fallback direct current boundaries for %s" % phase_name)
    return {
        "phase_name": phase_name,
        "assigned": True,
        "used_fallback_current_boundaries": True,
        "deleted_existing": bool(deleted),
        "winding_name": "",
        "current_boundary_count": len(current_names),
        "current_boundary_names": current_names,
        "face_assignments": face_assignments,
        "current_boundary_assignment_modes": assignment_modes,
        "positive_object_count": len(positive_objects),
        "negative_object_count": len(negative_objects),
        "details": "segmented fallback direct current boundaries assigned from cached terminal specs with internal-conductor current variants"
    }


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "assign_sector3d_excitation_%s.log" % timestamp_string()))
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    artifact_json = os.path.join(root, "artifacts", "sector3d_excitation_assignment.json")
    artifact_md = os.path.join(root, "reports", "sector3d_excitation_assignment.md")
    build_artifact_json = os.path.join(root, "artifacts", "sector3d_model_build.json")

    required_design_name = project_cfg["sector_3d"]["design_name"]
    manual_actions = []
    winding_results = []
    source_sink_terminal_sheets = []

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject or not oDesign:
        raise RuntimeError("No active AEDT project/design is open")

    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    app = attach_maxwell3d(oDesktop, oProject, oDesign, logger)
    phase_belts = ensure_macro_phase_belts(app, oDesign, logger)
    build_metadata = {}
    if os.path.exists(build_artifact_json):
        try:
            build_metadata = load_json(build_artifact_json)
        except Exception:
            logger.log("Could not load Sector3D build artifact for phase-belt angle fallback")
            logger.log(traceback.format_exc())
    angle_context = _resolve_phase_belt_angle_context(phase_belts, build_metadata, project_cfg)
    logger.log(
        "Using phase-belt angle context source=%s start=%.6g belt=%.6g gap=%.6g segment=%.6g"
        % (
            angle_context["source"],
            angle_context["sector_start_angle_deg"],
            angle_context["phase_belt_angle_deg"],
            angle_context["phase_belt_gap_deg"],
            angle_context["phase_segment_angle_deg"],
        )
    )
    turns_per_phase = design_variable_number(oDesign, "turns_per_phase", 1.0)
    phase_inputs = []
    for phase_name in PHASE_NAMES:
        positive_objects = phase_belts["phase_groups"].get((phase_name, "Positive"), [])
        negative_objects = phase_belts["phase_groups"].get((phase_name, "Negative"), [])
        phase_inputs.append(
            {
                "phase_name": phase_name,
                "positive_objects": positive_objects,
                "negative_objects": negative_objects,
                "current_expression": _phase_expression(project_cfg, phase_name),
            }
        )

    phase_terminal_specs = {}
    phase_terminal_errors = {}
    for phase_input in phase_inputs:
        phase_name = phase_input["phase_name"]
        positive_objects = phase_input["positive_objects"]
        negative_objects = phase_input["negative_objects"]
        if (not positive_objects) or (not negative_objects):
            continue
        try:
            terminal_specs = _collect_phase_terminal_specs(
                app, phase_name, positive_objects, negative_objects
            )
            terminal_specs, sheet_details = _ensure_phase_terminal_sheets(
                app, phase_name, terminal_specs, phase_belts, angle_context, logger
            )
            phase_terminal_specs[phase_name] = terminal_specs
            source_sink_terminal_sheets.extend(sheet_details)
        except Exception as terminal_exc:
            phase_terminal_errors[phase_name] = {
                "error": terminal_exc,
                "traceback": traceback.format_exc(),
            }

    for phase_input in phase_inputs:
        phase_name = phase_input["phase_name"]
        positive_objects = phase_input["positive_objects"]
        negative_objects = phase_input["negative_objects"]
        if (not positive_objects) or (not negative_objects):
            manual_actions.append("Missing positive/negative macro phase-belt objects for %s" % phase_name)
            winding_results.append(
                {
                    "phase_name": phase_name,
                    "assigned": False,
                    "used_fallback_current_boundaries": False,
                    "positive_object_count": len(positive_objects),
                    "negative_object_count": len(negative_objects),
                    "details": "missing phase-belt geometry"
                }
            )
            continue
        current_expression = phase_input["current_expression"]
        terminal_specs = phase_terminal_specs.get(phase_name)
        if terminal_specs is None:
            terminal_error_info = phase_terminal_errors.get(phase_name, {})
            terminal_exc = terminal_error_info.get("error")
            logger.log("Terminal-face discovery failed for %s" % phase_name)
            logger.log(str(terminal_exc))
            logger.log(terminal_error_info.get("traceback", ""))
            manual_actions.append("%s terminal-face discovery failed before excitation assignment" % phase_name)
            winding_results.append(
                {
                    "phase_name": phase_name,
                    "assigned": False,
                    "used_fallback_current_boundaries": False,
                    "positive_object_count": len(positive_objects),
                    "negative_object_count": len(negative_objects),
                    "details": str(terminal_exc)
                }
            )
            continue
        try:
            result = _assign_phase_with_winding_group(
                app,
                phase_name,
                current_expression,
                positive_objects,
                negative_objects,
                turns_per_phase,
                logger,
                terminal_specs=terminal_specs
            )
        except Exception as exc:
            logger.log("Winding assignment failed for %s; falling back to direct current boundaries" % phase_name)
            logger.log(str(exc))
            logger.log(traceback.format_exc())
            manual_actions.append("%s winding-group assignment failed, used fallback direct current boundaries" % phase_name)
            try:
                result = _assign_phase_with_direct_current(
                    app,
                    phase_name,
                    current_expression,
                    positive_objects,
                    negative_objects,
                    logger,
                    terminal_specs=terminal_specs
                )
            except Exception as fallback_exc:
                logger.log("Fallback direct current assignment failed for %s" % phase_name)
                logger.log(str(fallback_exc))
                logger.log(traceback.format_exc())
                result = {
                    "phase_name": phase_name,
                    "assigned": False,
                    "used_fallback_current_boundaries": True,
                    "positive_object_count": len(positive_objects),
                    "negative_object_count": len(negative_objects),
                    "details": str(fallback_exc)
                }
        winding_results.append(result)

    if not all(item.get("assigned", False) for item in winding_results):
        manual_actions.append("At least one phase failed to receive a usable excitation. Recheck PyAEDT boundary compatibility before solving Setup_3D.")
    if design_name != required_design_name:
        manual_actions.append("The active design name is %s; expected %s" % (design_name, required_design_name))

    save_status = save_sector3d_project(app, oProject, logger)
    if not save_status.get("saved", False):
        manual_actions.append("Project save failed after excitation assignment: %s" % save_status.get("error", ""))

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), "") or _safe_call(lambda: app.project_name, ""),
        "design_name": design_name,
        "design_name_matches_required": (design_name == required_design_name),
        "save_ok": save_status.get("saved", False),
        "save_method": save_status.get("method", ""),
        "save_error": save_status.get("error", ""),
        "phase_belt_reused": bool(phase_belts.get("reused", False)),
        "phase_belt_segment_count": int(phase_belts.get("segment_count", 0)),
        "phase_belt_angle_deg": angle_context.get("phase_belt_angle_deg", ""),
        "phase_belt_gap_deg": angle_context.get("phase_belt_gap_deg", ""),
        "phase_segment_angle_deg": angle_context.get("phase_segment_angle_deg", ""),
        "phase_belt_angle_source": angle_context.get("source", ""),
        "sector_start_angle_deg": angle_context.get("sector_start_angle_deg", ""),
        "deleted_objects": phase_belts.get("deleted_objects", []),
        "created_objects": phase_belts.get("created_objects", []),
        "winding_results": winding_results,
        "source_sink_terminal_sheets": source_sink_terminal_sheets,
        "current_excitations": list_excitations_of_type(app, "Current"),
        "winding_excitations": list_excitations_of_type(app, "Winding Group"),
        "manual_actions": manual_actions
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote sector 3D excitation summary: %s" % artifact_json)
    _raise_if_sector3d_excitation_failed(summary)


if __name__ == "__main__":
    main()
