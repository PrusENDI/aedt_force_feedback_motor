from __future__ import print_function

import traceback

from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call
from aedt_native_common import pyaedt_attach
from aedt_native_common import save_project
from sector3d_scaffold import _create_annular_sector_with_fallbacks
from sector3d_scaffold import _modeler
from sector3d_scaffold import _phase_belt_objects_definition


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

    return pyaedt_attach(
        lambda **kwargs: Maxwell3d(**kwargs),
        [
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
        ],
        logger,
        "Maxwell3d",
        new_session=False
    )


def preferred_solution_name(setup_name):
    return "%s : Transient" % setup_name


def save_sector3d_project(app, oProject, logger):
    result = save_project(oProject, logger)
    result["method"] = "native"
    if result.get("saved", False):
        return result

    for method_name, callback in [
        ("pyaedt_app", lambda: app.save_project()),
        ("pyaedt_oproject", lambda: app.oproject.Save())
    ]:
        try:
            callback()
            logger.log("Project saved via %s fallback" % method_name)
            return {
                "saved": True,
                "error": "",
                "method": method_name
            }
        except Exception:
            logger.log("Project save fallback failed via %s" % method_name)
            logger.log(traceback.format_exc())

    return result


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

    oEditor = _modeler(oDesign)
    phase_belts = _phase_belt_objects_definition(
        {
            "pole_count": design_variable_number(oDesign, "pole_count", 24.0)
        }
    )
    phase_groups = phase_belts["phase_groups"]
    created_objects = []
    deleted_objects = []
    for item in phase_belts["objects"]:
        _create_annular_sector_with_fallbacks(
            oEditor,
            item["name"],
            item["z_start"],
            item["inner_radius"],
            item["outer_radius"],
            item["height"],
            item["start_angle_deg"],
            item["sweep_angle_deg"],
            item["materials"],
            item["color"],
            item["transparency"],
            item["solve_inside"],
            logger
        )
        created_objects.append(item["name"])

    envelope_names = ["Auto3D_FlatCopper_Bottom", "Auto3D_FlatCopper_Top"]
    present_envelopes = [name for name in envelope_names if object_exists(app, name)]
    if present_envelopes and delete_objects(app, present_envelopes, logger):
        deleted_objects.extend(present_envelopes)
    logger.log(
        "Created %d macro phase-belt solids across %d copper faces with %.6f deg sweep and %.6f deg insulation gap"
        % (len(created_objects), 2, phase_belts["phase_segment_angle_deg"], phase_belts["phase_belt_gap_deg"])
    )
    return {
        "reused": False,
        "deleted_objects": deleted_objects,
        "created_objects": created_objects,
        "phase_groups": phase_groups,
        "segment_count": phase_belts["segment_count"],
        "phase_belt_angle_deg": phase_belts["phase_belt_angle_deg"],
        "phase_belt_gap_deg": phase_belts["phase_belt_gap_deg"],
        "phase_segment_angle_deg": phase_belts["phase_segment_angle_deg"]
    }
