from __future__ import print_function

from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call


PHASE_BELT_SEQUENCE = [
    ("PhaseA", "Positive"),
    ("PhaseC", "Negative"),
    ("PhaseB", "Positive"),
    ("PhaseA", "Negative"),
    ("PhaseC", "Positive"),
    ("PhaseB", "Negative")
]


def clean_list(items):
    out = []
    seen = {}
    for item in items or []:
        text = str(item)
        if text in seen:
            continue
        seen[text] = True
        out.append(text)
    return out


def attach_maxwell3d(oDesktop, oProject, oDesign, logger):
    from ansys.aedt.core import Maxwell3d

    pid = _safe_call(lambda: int(oDesktop.GetProcessID()), 0)
    project_name = _safe_call(lambda: oProject.GetName(), None)
    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))

    attempts = [
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False,
            "aedt_process_id": pid if pid else None
        },
        {
            "project": project_name,
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False
        },
        {
            "design": design_name,
            "new_desktop": False,
            "close_on_exit": False
        }
    ]
    last_error = None
    for raw_kwargs in attempts:
        kwargs = {}
        for key, value in raw_kwargs.items():
            if value not in [None, ""]:
                kwargs[key] = value
        try:
            app = Maxwell3d(**kwargs)
            logger.log("Attached Maxwell3d through PyAEDT with kwargs: %s" % kwargs)
            return app
        except Exception as exc:
            last_error = exc
            logger.log("PyAEDT Maxwell3d attachment attempt failed: %s" % kwargs)
    if last_error:
        raise last_error
    raise RuntimeError("Could not attach Maxwell3d through PyAEDT")


def preferred_solution_name(setup_name):
    return "%s : Transient" % setup_name


def list_object_names(app):
    return clean_list(_safe_call(lambda: list(app.modeler.object_names), []))


def object_exists(app, object_name):
    return object_name in list_object_names(app)


def delete_objects(app, object_names, logger):
    targets = clean_list([name for name in object_names if str(name).strip()])
    if not targets:
        return False
    try:
        app.modeler.oeditor.Delete(
            [
                "NAME:Selections",
                "Selections:=", ",".join(targets)
            ]
        )
        logger.log("Deleted %d objects: %s" % (len(targets), ", ".join(targets)))
        return True
    except Exception:
        logger.log("Could not delete objects: %s" % ", ".join(targets))
        return False


def delete_named_boundaries_if_present(app, boundary_names, logger):
    deleted = []
    for name in clean_list(boundary_names):
        try:
            app.oboundary.DeleteBoundaries([name])
            logger.log("Deleted existing boundary named %s" % name)
            deleted.append(name)
        except Exception:
            continue
    return deleted


def list_excitations_of_type(app, excitation_type):
    return clean_list(_safe_call(lambda: list(app.oboundary.GetExcitationsOfType(excitation_type)), []))


def design_variable_number(oDesign, name, default_value=0.0):
    value = _safe_call(lambda: oDesign.GetVariableValue(name), "")
    if not value:
        return default_value
    text = str(value).strip().lower()
    for token in [
        "newtonmeter",
        "newton",
        "degree",
        "ghz",
        "mhz",
        "khz",
        "deg",
        "rpm",
        "mm",
        "hz",
        "sec",
        "s",
        "a",
        "v",
        "ohm",
        "h",
        "t"
    ]:
        if text.endswith(token):
            text = text[: -len(token)].strip()
            break
    try:
        return float(text)
    except Exception:
        return default_value


def _phase_group_template():
    out = {}
    for phase_name in ["PhaseA", "PhaseB", "PhaseC"]:
        out[(phase_name, "Positive")] = []
        out[(phase_name, "Negative")] = []
    return out


def group_existing_phase_objects(app):
    object_names = list_object_names(app)
    out = _phase_group_template()
    for name in object_names:
        if not name.startswith("Auto3D_Phase"):
            continue
        matched = False
        for phase_name in ["PhaseA", "PhaseB", "PhaseC"]:
            for polarity in ["Positive", "Negative"]:
                token = "%s_%s" % (phase_name, "Pos" if polarity == "Positive" else "Neg")
                if token in name:
                    out[(phase_name, polarity)].append(name)
                    matched = True
                    break
            if matched:
                break
    return out


def ensure_macro_phase_belts(app, oDesign, logger):
    existing_groups = group_existing_phase_objects(app)
    reused = any(existing_groups.values())
    if reused:
        logger.log("Reusing existing macro phase-belt objects")
        return {
            "reused": True,
            "deleted_objects": [],
            "created_objects": [],
            "phase_groups": existing_groups,
            "segment_count": sum([len(value) for value in existing_groups.values()]),
            "phase_belt_angle_deg": design_variable_number(oDesign, "auto3d_phase_belt_angle_deg", 0.0),
            "phase_belt_gap_deg": design_variable_number(oDesign, "auto3d_phase_belt_gap_deg", 0.0),
            "phase_segment_angle_deg": design_variable_number(oDesign, "auto3d_phase_segment_angle_deg", 0.0)
        }

    envelope_name = "Auto3D_FlatCopperPack"
    if not object_exists(app, envelope_name):
        raise RuntimeError("Missing %s; build the 3D scaffold before assigning macro phase belts" % envelope_name)

    pole_count = max(2, int(round(design_variable_number(oDesign, "pole_count", 24.0))))
    segment_count = max(6, pole_count * 3)
    phase_belt_angle_deg = 360.0 / float(segment_count)
    phase_belt_gap_deg = min(0.08, max(0.01, phase_belt_angle_deg * 0.01))
    phase_segment_angle_deg = max(0.001, phase_belt_angle_deg - phase_belt_gap_deg)
    inner_radius = design_variable_number(oDesign, "auto3d_flat_copper_inner_radius_mm", 25.0)
    outer_radius = design_variable_number(oDesign, "auto3d_flat_copper_outer_radius_mm", inner_radius + 5.0)
    z_start = design_variable_number(oDesign, "auto3d_z_flat_copper_mm", 0.0)
    height = design_variable_number(oDesign, "auto3d_flat_copper_pack_height_mm", 0.5)
    radial_span = max(0.1, outer_radius - inner_radius)

    phase_groups = _phase_group_template()
    created_objects = []
    deleted_objects = []
    for index in range(segment_count):
        phase_name, polarity = PHASE_BELT_SEQUENCE[index % len(PHASE_BELT_SEQUENCE)]
        object_name = "Auto3D_%s_%s_%03d" % (
            phase_name,
            "Pos" if polarity == "Positive" else "Neg",
            index + 1
        )
        rectangle = app.modeler.create_rectangle(
            "XZ",
            [inner_radius, 0.0, z_start],
            [radial_span, height],
            name=object_name,
            material="copper"
        )
        if not rectangle:
            raise RuntimeError("Could not create macro phase-belt rectangle %s" % object_name)
        swept = rectangle.sweep_around_axis("Z", sweep_angle=phase_segment_angle_deg)
        if not swept:
            raise RuntimeError("Could not sweep macro phase-belt %s around Z" % object_name)
        rotated = app.modeler[object_name].rotate("Z", angle=(index * phase_belt_angle_deg) + 0.5 * phase_belt_gap_deg, units="deg")
        if not rotated:
            raise RuntimeError("Could not rotate macro phase-belt %s" % object_name)
        phase_groups[(phase_name, polarity)].append(object_name)
        created_objects.append(object_name)

    if delete_objects(app, [envelope_name], logger):
        deleted_objects.append(envelope_name)
    logger.log(
        "Created %d macro phase-belt solids with %.6f deg sweep and %.6f deg insulation gap"
        % (segment_count, phase_segment_angle_deg, phase_belt_gap_deg)
    )
    return {
        "reused": False,
        "deleted_objects": deleted_objects,
        "created_objects": created_objects,
        "phase_groups": phase_groups,
        "segment_count": segment_count,
        "phase_belt_angle_deg": phase_belt_angle_deg,
        "phase_belt_gap_deg": phase_belt_gap_deg,
        "phase_segment_angle_deg": phase_segment_angle_deg
    }
