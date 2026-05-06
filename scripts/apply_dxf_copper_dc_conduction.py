from __future__ import print_function

import os
from uuid import uuid4

from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import load_json
from aedt_native_common import Logger
from aedt_native_common import pyaedt_attach
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import save_project
from aedt_native_common import timestamp_string


MILESTONE = "Milestone 2: DXF-Compatible 3D Copper MVP"
SETUP_NAME = "AutoDxfCopper_DC"
VOLTAGE_ASSIGNMENT = "AutoDxfCopper_Voltage"
SINK_ASSIGNMENT = "AutoDxfCopper_Sink"
CURRENT_DENSITY_QUANTITY_CANDIDATES = ["CurrentDensity", "Mag_J", "J"]
CENTERLINE_SAMPLE_COUNT = 13
CENTERLINE_SAMPLE_MIN_MAG_J_A_PER_M2 = 1.0


def _global_value(name, default_value=None):
    if name in globals():
        return globals().get(name)
    main_globals = getattr(__import__("__main__"), "__dict__", {})
    return main_globals.get(name, default_value)


def _host_mode():
    return bool(_global_value("__agent_host_mode", False))


def _safe_call(callback, default_value=None):
    try:
        return callback()
    except Exception:
        return default_value


def _call_with_error(callback):
    try:
        return callback(), ""
    except Exception as exc:
        return None, str(exc)


def _name_of(value):
    return str(getattr(value, "name", value) or "")


def _starts_with_any(value, prefixes):
    text = str(value or "")
    return any(text == prefix or text.startswith(prefix + "_") for prefix in prefixes)


def _iter_named_items(values):
    if isinstance(values, dict):
        return list(values.items())
    return [(_name_of(value), value) for value in list(values or [])]


def _delete_named_item(item, fallback_delete=None):
    try:
        delete = getattr(item, "delete", None)
        if callable(delete):
            return bool(delete())
        if callable(fallback_delete):
            return bool(fallback_delete())
    except Exception:
        return False
    return False


def _cleanup_v1_dc_artifacts(app, logger):
    cleanup = {
        "deleted_boundaries": [],
        "deleted_setups": [],
        "deleted_field_plots": [],
        "blocking_issues": [],
    }
    boundary_prefixes = [VOLTAGE_ASSIGNMENT, SINK_ASSIGNMENT]
    for name, boundary in _iter_named_items(getattr(app, "boundaries", [])):
        if not _starts_with_any(name, boundary_prefixes):
            continue
        if _delete_named_item(boundary):
            cleanup["deleted_boundaries"].append(name)
        else:
            cleanup["blocking_issues"].append("v1_boundary_cleanup_failed:%s" % name)

    for name, setup in _iter_named_items(getattr(app, "setups", [])):
        if not _starts_with_any(name, [SETUP_NAME]):
            continue
        if _delete_named_item(setup, lambda n=name: app.delete_setup(n)):
            cleanup["deleted_setups"].append(name)
        else:
            cleanup["blocking_issues"].append("v1_setup_cleanup_failed:%s" % name)

    post = getattr(app, "post", None)
    field_plots = getattr(post, "field_plots", {}) if post else {}
    for name, plot in _iter_named_items(field_plots):
        if not _starts_with_any(name, ["AutoDxfCopper_MagJ"]):
            continue
        if _delete_named_item(plot, lambda n=name: post.delete_field_plot(n)):
            cleanup["deleted_field_plots"].append(name)
        else:
            cleanup["blocking_issues"].append("v1_field_plot_cleanup_failed:%s" % name)

    if cleanup["deleted_boundaries"] or cleanup["deleted_setups"] or cleanup["deleted_field_plots"]:
        logger.log("Deleted prior V1 DC artifacts: %s" % cleanup)
    return cleanup


def _safe_name_suffix(value):
    text = str(value or "")
    chars = []
    for char in text:
        if char.isalnum() or char == "_":
            chars.append(char)
    suffix = "".join(chars).strip("_")
    return suffix or "run"


def dc_run_names(run_suffix):
    suffix = _safe_name_suffix(run_suffix)
    setup_name = "%s_%s" % (SETUP_NAME, suffix)
    return {
        "setup_name": setup_name,
        "voltage_assignment": "%s_%s" % (VOLTAGE_ASSIGNMENT, suffix),
        "sink_assignment": "%s_%s" % (SINK_ASSIGNMENT, suffix),
        "solution": "%s : LastAdaptive" % setup_name,
    }


def _new_dc_run_names():
    return dc_run_names("%s_%s" % (timestamp_string(), uuid4().hex[:8]))


def _artifact_paths(root):
    return {
        "input_json": os.path.join(root, "artifacts", "dxf_copper_mvp.json"),
        "json": os.path.join(root, "artifacts", "dxf_copper_dc_conduction.json"),
        "md": os.path.join(root, "reports", "dxf_copper_dc_conduction.md"),
        "field_dir": os.path.join(root, "artifacts", "dxf_copper_dc_conduction_fields"),
    }


def _attach_active_maxwell3d(oDesktop, oProject, oDesign, logger):
    from ansys.aedt.core import Maxwell3d

    pid = _safe_call(lambda: int(oDesktop.GetProcessID()), 0)
    project_name = _safe_call(lambda: oProject.GetName(), None)
    design_name = _safe_call(lambda: oDesign.GetName(), None)
    attempts = [
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
            "aedt_process_id": pid if pid else None,
        },
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
        },
        {
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
        },
    ]
    return pyaedt_attach(lambda **kwargs: Maxwell3d(**kwargs), attempts, logger, "Maxwell3d", new_session=False)


def _terminal_face_by_role(terminal_faces, role):
    for face in terminal_faces or []:
        if str(face.get("role", "")).lower() == role:
            return face
    return {}


def _default_dc_setup_gate():
    return {
        "attempted": False,
        "voltage_assigned": False,
        "sink_assigned": False,
        "setup_created": False,
        "solved": False,
        "setup_name": SETUP_NAME,
        "voltage_assignment": VOLTAGE_ASSIGNMENT,
        "sink_assignment": SINK_ASSIGNMENT,
        "solution": "%s : LastAdaptive" % SETUP_NAME,
        "current_density_continuity_checked": False,
        "current_density_evidence": {
            "solution": "%s : LastAdaptive" % SETUP_NAME,
            "available_quantities": [],
            "quantity": "",
            "field_export_path": "",
            "field_exported": False,
            "centerline_sample": {},
        },
        "cleanup": {
            "deleted_boundaries": [],
            "deleted_setups": [],
            "deleted_field_plots": [],
            "blocking_issues": [],
        },
        "blocking_issues": [],
        "save_status": {"saved": False, "error": "", "method": ""},
    }


def _select_current_density_quantity(quantities):
    normalized = [(str(quantity), str(quantity).lower()) for quantity in quantities or []]
    priorities = [quantity.lower() for quantity in CURRENT_DENSITY_QUANTITY_CANDIDATES]
    for priority in priorities:
        for original, lowered in normalized:
            if lowered == priority:
                return original
    for original, lowered in normalized:
        if "currentdensity" in lowered or lowered.startswith("j") or lowered.endswith("_j"):
            return original
    return ""


def _centerline_sample_points():
    points = []
    start_x = -24.0
    stop_x = 24.0
    step = (stop_x - start_x) / float(CENTERLINE_SAMPLE_COUNT - 1)
    for index in range(CENTERLINE_SAMPLE_COUNT):
        points.append([round(start_x + step * index, 6), 0.0, -0.15])
    return points


def _parse_sample_values(path):
    values = []
    if not path or not os.path.isfile(path):
        return values
    handle = open(path, "r")
    try:
        for line in handle:
            pieces = line.replace(",", " ").split()
            numeric = []
            for piece in pieces:
                try:
                    numeric.append(float(piece))
                except ValueError:
                    pass
            if len(numeric) >= 4:
                values.append(float(numeric[-1]))
    finally:
        handle.close()
    return values


def _centerline_current_density_evidence(app, solution, field_dir, logger):
    evidence = {
        "solution": solution,
        "quantity": "Mag_J",
        "sample_points": _centerline_sample_points(),
        "sample_export_path": os.path.join(field_dir, "dxf_copper_centerline_mag_j_samples.fld"),
        "sample_exported": False,
        "sample_continuity_checked": False,
        "sample_count": 0,
        "nonzero_sample_count": 0,
        "min_mag_j_a_per_m2": 0.0,
        "max_mag_j_a_per_m2": 0.0,
        "blocking_issues": [],
        "error": "",
    }
    if not os.path.isdir(field_dir):
        os.makedirs(field_dir)

    exported, error = _call_with_error(
        lambda: app.post.export_field_file(
            quantity="Mag_J",
            solution=solution,
            output_file=evidence["sample_export_path"],
            sample_points=evidence["sample_points"],
            export_with_sample_points=True,
        )
    )
    if error:
        evidence["error"] = error
        evidence["blocking_issues"].append("centerline_current_density_sample_export_failed")
        logger.log("Centerline Mag_J sample export failed: %s" % error)
        return evidence

    evidence["sample_exported"] = bool(exported)
    values = _parse_sample_values(evidence["sample_export_path"])
    evidence["sample_count"] = len(values)
    if values:
        evidence["min_mag_j_a_per_m2"] = min(values)
        evidence["max_mag_j_a_per_m2"] = max(values)
        evidence["nonzero_sample_count"] = len(
            [value for value in values if abs(value) >= CENTERLINE_SAMPLE_MIN_MAG_J_A_PER_M2]
        )
    evidence["sample_continuity_checked"] = (
        evidence["sample_exported"]
        and evidence["sample_count"] == len(evidence["sample_points"])
        and evidence["nonzero_sample_count"] == evidence["sample_count"]
    )
    if not evidence["sample_exported"]:
        evidence["blocking_issues"].append("centerline_current_density_sample_export_failed")
    if evidence["sample_count"] != len(evidence["sample_points"]):
        evidence["blocking_issues"].append("centerline_current_density_sample_count_mismatch")
    if evidence["sample_count"] and evidence["nonzero_sample_count"] != evidence["sample_count"]:
        evidence["blocking_issues"].append("centerline_current_density_has_zero_samples")
    logger.log(
        "Centerline Mag_J sample: exported=%s count=%s nonzero=%s min=%s max=%s path=%s"
        % (
            evidence["sample_exported"],
            evidence["sample_count"],
            evidence["nonzero_sample_count"],
            evidence["min_mag_j_a_per_m2"],
            evidence["max_mag_j_a_per_m2"],
            evidence["sample_export_path"],
        )
    )
    return evidence


def _current_density_evidence(app, solution, field_dir, logger, object_name="AllObjects"):
    evidence = {
        "solution": solution,
        "object_name": object_name,
        "method": "",
        "available_quantities": [],
        "attempted_quantities": [],
        "quantity": "",
        "field_export_path": "",
        "field_exported": False,
        "field_plot_name": "",
        "field_plot_error": "",
        "centerline_sample": {},
        "blocking_issues": [],
    }
    quantities = _safe_call(
        lambda: app.post.available_report_quantities(
            report_category="Fields",
            display_type="Data Table",
            solution=solution,
        ),
        [],
    )
    evidence["available_quantities"] = [str(quantity) for quantity in quantities or []]
    if not os.path.isdir(field_dir):
        os.makedirs(field_dir)

    plot_name = "AutoDxfCopper_MagJ_%s" % _safe_name_suffix(solution)
    field_plot, field_plot_error = _call_with_error(
        lambda: app.post.create_fieldplot_volume(
            [object_name],
            "Mag_J",
            solution,
            plot_name=plot_name,
        )
    )
    if field_plot_error:
        evidence["field_plot_error"] = field_plot_error
        logger.log("Current density field plot creation failed: %s" % field_plot_error)
    elif field_plot:
        exported_plot, field_plot_export_error = _call_with_error(
            lambda: app.post.export_field_plot(
                plot_name=getattr(field_plot, "name", plot_name),
                output_dir=field_dir,
                file_name=plot_name,
                file_format="aedtplt",
            )
        )
        if field_plot_export_error:
            evidence["field_plot_error"] = field_plot_export_error
            logger.log("Current density field plot export failed: %s" % field_plot_export_error)
        if exported_plot:
            evidence["method"] = "field_plot"
            evidence["quantity"] = "Mag_J"
            evidence["field_plot_name"] = getattr(field_plot, "name", plot_name)
            evidence["field_export_path"] = str(exported_plot)
            evidence["field_exported"] = True
            logger.log(
                "Current density evidence: method=field_plot quantity=Mag_J exported=True path=%s"
                % evidence["field_export_path"]
            )
            return evidence

    selected = _select_current_density_quantity(evidence["available_quantities"])
    candidates = []
    if selected:
        candidates.append(selected)
    for candidate in CURRENT_DENSITY_QUANTITY_CANDIDATES:
        if candidate not in candidates:
            candidates.append(candidate)

    for quantity in candidates:
        output_file = os.path.join(field_dir, "dxf_copper_current_density_%s.fld" % _safe_name_suffix(quantity))
        evidence["attempted_quantities"].append(quantity)
        exported = _safe_call(
            lambda q=quantity, path=output_file: app.post.export_field_file(
                quantity=q,
                solution=solution,
                output_file=path,
                assignment="AllObjects",
                objects_type="Vol",
            ),
            False,
        )
        if exported:
            evidence["method"] = "field_file"
            evidence["quantity"] = quantity
            evidence["field_export_path"] = output_file
            evidence["field_exported"] = True
            break

    if not evidence["field_exported"]:
        if evidence["field_plot_error"]:
            if field_plot:
                evidence["blocking_issues"].append("field_plot_export_failed")
            else:
                evidence["blocking_issues"].append("field_plot_creation_failed")
        if not selected:
            evidence["blocking_issues"].append("current_density_quantity_unavailable")
        evidence["blocking_issues"].append("current_density_field_export_failed")
    logger.log(
        "Current density evidence: quantity=%s exported=%s path=%s"
        % (evidence["quantity"], evidence["field_exported"], evidence["field_export_path"])
    )
    return evidence


def _dc_setup_gate(build_summary, logger, field_dir):
    gate = _default_dc_setup_gate()
    gate["attempted"] = True
    run_names = _new_dc_run_names()
    gate.update(run_names)
    oDesktop = _global_value("oDesktop")
    oProject = _global_value("oProject")
    oDesign = _global_value("oDesign")
    if not oDesktop or not oProject or not oDesign:
        gate["blocking_issues"].append("aedt_host_globals_missing")
        return gate

    terminal_faces = list(build_summary.get("terminal_faces", []))
    source = _terminal_face_by_role(terminal_faces, "source")
    sink = _terminal_face_by_role(terminal_faces, "sink")
    if not source or not sink:
        gate["blocking_issues"].append("terminal_face_roles_missing")
        return gate

    try:
        app = _attach_active_maxwell3d(oDesktop, oProject, oDesign, logger)
        gate["cleanup"] = _cleanup_v1_dc_artifacts(app, logger)
        if gate["cleanup"].get("blocking_issues"):
            gate["blocking_issues"].extend(gate["cleanup"]["blocking_issues"])
            return gate
        voltage = app.assign_voltage(
            [int(source["face_id"])],
            amplitude="1000mV",
            name=gate["voltage_assignment"],
        )
        gate["voltage_assigned"] = bool(voltage)
        if not voltage:
            gate["blocking_issues"].append("voltage_assignment_failed")

        sink_assignment = app.assign_sink([int(sink["face_id"])], name=gate["sink_assignment"])
        gate["sink_assigned"] = bool(sink_assignment)
        if not sink_assignment:
            gate["blocking_issues"].append("sink_assignment_failed")

        setup = app.create_setup(name=gate["setup_name"])
        gate["setup_created"] = bool(setup)
        if not setup:
            gate["blocking_issues"].append("dc_setup_creation_failed")

        if gate["setup_created"]:
            gate["solved"] = bool(app.analyze_setup(gate["setup_name"], blocking=True))
            if not gate["solved"]:
                gate["blocking_issues"].append("dc_solve_failed")

        if gate["solved"]:
            object_name = build_summary.get("aedt_build", {}).get("object_name", "AllObjects")
            evidence = _current_density_evidence(app, gate["solution"], field_dir, logger, object_name=object_name)
            centerline_evidence = _centerline_current_density_evidence(app, gate["solution"], field_dir, logger)
            evidence["centerline_sample"] = centerline_evidence
            gate["current_density_evidence"] = evidence
            gate["current_density_continuity_checked"] = bool(
                evidence.get("quantity", "") and evidence.get("field_exported", False)
                and centerline_evidence.get("sample_continuity_checked", False)
            )
            gate["blocking_issues"].extend(evidence.get("blocking_issues", []))
            gate["blocking_issues"].extend(centerline_evidence.get("blocking_issues", []))

        gate["save_status"] = save_project(oProject, logger)
        if not gate["save_status"].get("saved", False):
            gate["blocking_issues"].append("aedt_project_save_failed")
    except Exception as exc:
        gate["blocking_issues"].append("dc_setup_exception: %s" % exc)
    return gate


def build_dc_conduction_summary(build_summary=None, input_artifact_path="", dc_setup_gate=None):
    blocking_issues = []
    if build_summary is None:
        build_summary = {}
        blocking_issues.append("dxf_copper_mvp_artifact_missing")
    dc_setup_gate = dc_setup_gate or _default_dc_setup_gate()

    dxf_ready = bool(build_summary.get("dxf_compatible_copper_ready", False))
    terminal_faces = list(build_summary.get("terminal_faces", []))
    terminal_faces_present = len(terminal_faces) >= 2
    voltage_assigned = bool(dc_setup_gate.get("voltage_assigned", False))
    sink_assigned = bool(dc_setup_gate.get("sink_assigned", False))
    setup_created = bool(dc_setup_gate.get("setup_created", False))
    solved = bool(dc_setup_gate.get("solved", False))
    current_density_continuity_checked = bool(dc_setup_gate.get("current_density_continuity_checked", False))

    if not dxf_ready:
        blocking_issues.append("dxf_compatible_copper_not_ready")
    if not terminal_faces_present:
        blocking_issues.append("terminal_faces_missing")
    if dxf_ready and terminal_faces_present and not voltage_assigned:
        blocking_issues.append("voltage_assignment_missing")
    if dxf_ready and terminal_faces_present and not sink_assigned:
        blocking_issues.append("sink_assignment_missing")
    if dxf_ready and terminal_faces_present and not setup_created:
        blocking_issues.append("dc_setup_missing")
    if dxf_ready and terminal_faces_present and voltage_assigned and sink_assigned and setup_created and not solved:
        blocking_issues.append("dc_solve_missing")
    if dxf_ready and terminal_faces_present and voltage_assigned and sink_assigned and setup_created and solved and not current_density_continuity_checked:
        blocking_issues.append("current_density_continuity_not_checked")
    if dxf_ready and terminal_faces_present and voltage_assigned and sink_assigned and setup_created and not current_density_continuity_checked:
        blocking_issues.append("current_density_continuity_not_checked")
    blocking_issues.extend(dc_setup_gate.get("blocking_issues", []))

    dc_setup_ready = dxf_ready and terminal_faces_present and voltage_assigned and sink_assigned and setup_created
    dc_ready = dc_setup_ready and solved and current_density_continuity_checked and not blocking_issues

    return {
        "timestamp": timestamp_string(),
        "milestone": MILESTONE,
        "host_mode_detected": _host_mode(),
        "input_artifact_path": input_artifact_path,
        "dc_setup_ready": bool(dc_setup_ready),
        "dc_conduction_ready": bool(dc_ready),
        "dxf_compatible_copper_ready": dxf_ready,
        "terminal_faces_present": terminal_faces_present,
        "solved": solved,
        "current_density_continuity_checked": current_density_continuity_checked,
        "current_density_evidence": dc_setup_gate.get("current_density_evidence", {}),
        "terminal_faces": terminal_faces,
        "setup_name": dc_setup_gate.get("setup_name", SETUP_NAME),
        "voltage_assignment": dc_setup_gate.get("voltage_assignment", VOLTAGE_ASSIGNMENT),
        "sink_assignment": dc_setup_gate.get("sink_assignment", SINK_ASSIGNMENT),
        "dc_setup_gate": dc_setup_gate,
        "blocking_issues": sorted(set(blocking_issues)),
        "manual_actions": [
            "Run the V1 copper MVP build inside AEDT and identify two terminal faces before applying DC Conduction.",
            "After terminal faces are available, assign voltage and sink boundaries in a Maxwell 3D DC Conduction design.",
        ],
    }


def markdown_text(summary):
    lines = []
    lines.append("# DXF Copper DC Conduction")
    lines.append("")
    lines.append("This V1 artifact is a DC Conduction sanity-check gate for current-density continuity.")
    lines.append("")
    for key in [
        "timestamp",
        "milestone",
        "host_mode_detected",
        "input_artifact_path",
        "dc_conduction_ready",
        "dxf_compatible_copper_ready",
        "terminal_faces_present",
        "dc_setup_ready",
        "solved",
        "current_density_continuity_checked",
        "setup_name",
        "voltage_assignment",
        "sink_assignment",
    ]:
        lines.append("- %s: `%s`" % (key, summary.get(key, "")))
    lines.append("")
    lines.append("## Terminal Faces")
    lines.append("")
    terminal_faces = summary.get("terminal_faces", [])
    if terminal_faces:
        for face in terminal_faces:
            lines.append("- `%s`" % face)
    else:
        lines.append("- `None`")
    lines.append("")
    lines.append("## Current Density Evidence")
    lines.append("")
    evidence = summary.get("current_density_evidence", {})
    for key in [
        "solution",
        "object_name",
        "method",
        "quantity",
        "field_plot_name",
        "field_plot_error",
        "field_export_path",
        "field_exported",
    ]:
        lines.append("- %s: `%s`" % (key, evidence.get(key, "")))
    lines.append("- available_quantities: `%s`" % evidence.get("available_quantities", []))
    lines.append("")
    lines.append("## Centerline Current Density Sample")
    lines.append("")
    centerline = evidence.get("centerline_sample", {})
    for key in [
        "quantity",
        "sample_export_path",
        "sample_exported",
        "sample_continuity_checked",
        "sample_count",
        "nonzero_sample_count",
        "min_mag_j_a_per_m2",
        "max_mag_j_a_per_m2",
        "error",
    ]:
        lines.append("- %s: `%s`" % (key, centerline.get(key, "")))
    lines.append("- sample_points: `%s`" % centerline.get("sample_points", []))
    lines.append("")
    lines.append("## Blocking Issues")
    lines.append("")
    issues = summary.get("blocking_issues", [])
    if issues:
        for issue in issues:
            lines.append("- `%s`" % issue)
    else:
        lines.append("- `None`")
    lines.append("")
    lines.append("## Manual Actions")
    lines.append("")
    for action in summary.get("manual_actions", []):
        lines.append("- %s" % action)
    return "\n".join(lines) + "\n"


def write_markdown(path, summary):
    handle = open(path, "w")
    try:
        handle.write(markdown_text(summary))
    finally:
        handle.close()


def _load_build_summary(path):
    if not os.path.isfile(path):
        return None
    return load_json(path)


def main(raise_on_blocking=False):
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "apply_dxf_copper_dc_conduction_%s.log" % timestamp_string()))
    paths = _artifact_paths(root)
    build_summary = _load_build_summary(paths["input_json"])
    dc_setup_gate = None
    if _host_mode() and build_summary and build_summary.get("dxf_compatible_copper_ready", False):
        dc_setup_gate = _dc_setup_gate(build_summary, logger, paths["field_dir"])
    summary = build_dc_conduction_summary(
        build_summary=build_summary,
        input_artifact_path=paths["input_json"],
        dc_setup_gate=dc_setup_gate,
    )
    save_json(paths["json"], summary)
    write_markdown(paths["md"], summary)
    logger.log("Wrote DXF copper DC Conduction artifacts: %s" % paths["json"])
    if raise_on_blocking and summary.get("blocking_issues"):
        raise RuntimeError("DXF copper DC Conduction blocked; see %s" % paths["md"])
    return paths


if __name__ == "__main__":
    main()
