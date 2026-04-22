from __future__ import print_function

import traceback

from aedt_native_common import apply_variables


AUTO2D_PREFIX = "Auto2D_"
PREFERRED_MAGNET_MATERIAL = "Magnet, permanent, Neodymium N42SH"


def _safe_call(func, default_value=None):
    try:
        return func()
    except Exception:
        return default_value


def _modeler(oDesign):
    return oDesign.SetActiveEditor("3D Modeler")


def _set_model_units(oEditor, logger):
    try:
        oEditor.SetModelUnits(
            [
                "NAME:Units Parameter",
                "Units:=", "mm",
                "Rescale:=", False
            ]
        )
        logger.log("Set model units to mm")
    except Exception:
        logger.log("Could not set model units explicitly")


def _scaffold_variables():
    return {
        "auto2d_region_padding_mm": "4mm",
        "auto2d_motion_band_pad_mm": "0.2mm",
        "auto2d_flat_copper_pack_height_mm": "conductor_thickness_mm*parallel_strands + flat_copper_interlayer_insulation_mm*(parallel_strands-1) + flat_copper_bondline_axial_build_mm",
        "auto2d_coil_stack_height_mm": "stator_support_thickness_mm + auto2d_flat_copper_pack_height_mm",
        "auto2d_coil_sheet_width_mm": "0.7*pole_pitch_mm + 0.2*coil_radial_span_mm - 2.5mm",
        "auto2d_coil_center_shift_mm": "0.5*(coil_mean_radius_mm - (outer_diameter_mm + inner_diameter_mm)/4)",
        "auto2d_stack_height_mm": "backiron_thickness_mm + magnet_thickness_mm + airgap_mm + auto2d_coil_stack_height_mm",
        "auto2d_period_start_x_mm": "-period_length_mm/2",
        "auto2d_backiron_y0_mm": "0mm",
        "auto2d_magnet_y0_mm": "backiron_thickness_mm",
        "auto2d_airgap_y0_mm": "backiron_thickness_mm + magnet_thickness_mm",
        "auto2d_coil_y0_mm": "backiron_thickness_mm + magnet_thickness_mm + airgap_mm",
        "auto2d_magnet_n_x0_mm": "-period_length_mm/2 + (pole_pitch_mm - magnet_arc_mm)/2",
        "auto2d_magnet_s_x0_mm": "(pole_pitch_mm - magnet_arc_mm)/2",
        "auto2d_coil_pos_x0_mm": "-pole_pitch_mm/2 - auto2d_coil_sheet_width_mm/2 + auto2d_coil_center_shift_mm",
        "auto2d_coil_neg_x0_mm": "pole_pitch_mm/2 - auto2d_coil_sheet_width_mm/2 + auto2d_coil_center_shift_mm"
    }


def _list_auto_objects(oEditor):
    attempts = [
        lambda: list(oEditor.GetMatchedObjectName("%s*" % AUTO2D_PREFIX)),
        lambda: list(oEditor.GetMatchedObjectName("Auto2D*"))
    ]
    for action in attempts:
        names = _safe_call(action, [])
        if names:
            cleaned = []
            seen = {}
            for name in names:
                text = str(name)
                if text in seen:
                    continue
                seen[text] = True
                cleaned.append(text)
            return cleaned
    names = []
    for group in ["Solids", "Sheets", "Lines", "Unclassified", "Model"]:
        items = _safe_call(lambda: list(oEditor.GetObjectsInGroup(group)), [])
        for item in items:
            text = str(item)
            if text.startswith(AUTO2D_PREFIX) and (text not in names):
                names.append(text)
    return names


def _delete_auto_objects(oEditor, logger):
    names = _list_auto_objects(oEditor)
    if not names:
        return []
    try:
        oEditor.Delete(
            [
                "NAME:Selections",
                "Selections:=", ",".join(names)
            ]
        )
        logger.log("Deleted %d existing auto-generated 2D objects" % len(names))
        return names
    except Exception:
        logger.log("Could not delete existing auto-generated objects")
        logger.log(traceback.format_exc())
        return names


def _rectangle_attributes(name, material, color, transparency, solve_inside):
    return [
        "NAME:Attributes",
        "Name:=", name,
        "Flags:=", "",
        "Color:=", color,
        "Transparency:=", transparency,
        "PartCoordinateSystem:=", "Global",
        "UDMId:=", "",
        "MaterialValue:=", "\"%s\"" % material,
        "SurfaceMaterialValue:=", "\"\"",
        "SolveInside:=", solve_inside
    ]


def _create_rectangle(oEditor, name, x_start, y_start, width, height, material, color, transparency, solve_inside):
    return oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", x_start,
            "YStart:=", y_start,
            "ZStart:=", "0mm",
            "Width:=", width,
            "Height:=", height,
            "WhichAxis:=", "Z"
        ],
        _rectangle_attributes(name, material, color, transparency, solve_inside)
    )


def _create_rectangle_with_fallbacks(oEditor, name, x_start, y_start, width, height, materials, color, transparency, solve_inside, logger):
    last_error = None
    for material in materials:
        try:
            _create_rectangle(oEditor, name, x_start, y_start, width, height, material, color, transparency, solve_inside)
            logger.log("Created %s with material %s" % (name, material))
            return {"name": name, "material": material}
        except Exception as exc:
            last_error = exc
            logger.log("CreateRectangle failed for %s with material %s" % (name, material))
    if last_error:
        raise last_error
    raise RuntimeError("Could not create rectangle %s" % name)


def _create_region(oEditor, name, padding_expr, logger):
    try:
        oEditor.CreateRegion(
            [
                "NAME:RegionParameters",
                "+XPaddingType:=", "Absolute Offset",
                "+XPadding:=", padding_expr,
                "-XPaddingType:=", "Absolute Offset",
                "-XPadding:=", padding_expr,
                "+YPaddingType:=", "Absolute Offset",
                "+YPadding:=", padding_expr,
                "-YPaddingType:=", "Absolute Offset",
                "-YPadding:=", padding_expr
            ],
            _rectangle_attributes(name, "air", "(143 175 143)", 0.9, True)
        )
        logger.log("Created surrounding region %s" % name)
        return True
    except Exception:
        logger.log("Could not create surrounding region %s automatically" % name)
        logger.log(traceback.format_exc())
        return False


def _looks_like_permanent_magnet(material_name):
    text = str(material_name or "").strip().lower()
    if not text:
        return False
    keywords = [
        "ndfeb",
        "neodymium",
        "permanent magnet",
        "permanent, neodymium"
    ]
    for keyword in keywords:
        if keyword in text:
            return True
    return False


def _linear2d_objects_definition():
    return [
        {
            "name": "%sBackIron" % AUTO2D_PREFIX,
            "x_start": "auto2d_period_start_x_mm",
            "y_start": "auto2d_backiron_y0_mm",
            "width": "period_length_mm",
            "height": "backiron_thickness_mm",
            "materials": ["steel_1010", "vacuum"],
            "color": "(120 120 120)",
            "transparency": 0.15,
            "solve_inside": True
        },
        {
            "name": "%sMagnet_N" % AUTO2D_PREFIX,
            "x_start": "auto2d_magnet_n_x0_mm",
            "y_start": "auto2d_magnet_y0_mm",
            "width": "magnet_arc_mm",
            "height": "magnet_thickness_mm",
            "materials": [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB", "vacuum"],
            "color": "(220 60 60)",
            "transparency": 0.05,
            "solve_inside": True
        },
        {
            "name": "%sMagnet_S" % AUTO2D_PREFIX,
            "x_start": "auto2d_magnet_s_x0_mm",
            "y_start": "auto2d_magnet_y0_mm",
            "width": "magnet_arc_mm",
            "height": "magnet_thickness_mm",
            "materials": [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB", "vacuum"],
            "color": "(60 90 220)",
            "transparency": 0.05,
            "solve_inside": True
        },
        {
            "name": "%sMotionBand" % AUTO2D_PREFIX,
            "x_start": "auto2d_period_start_x_mm - auto2d_motion_band_pad_mm",
            "y_start": "auto2d_backiron_y0_mm - auto2d_motion_band_pad_mm",
            "width": "period_length_mm + 2*auto2d_motion_band_pad_mm",
            # Keep the band flush with the magnet top surface so it encloses the
            # moving rotor stack without intersecting the separate air-gap sheet.
            "height": "backiron_thickness_mm + magnet_thickness_mm + auto2d_motion_band_pad_mm",
            "materials": ["air"],
            "color": "(200 200 255)",
            "transparency": 0.88,
            "solve_inside": True
        },
        {
            "name": "%sAirGap" % AUTO2D_PREFIX,
            "x_start": "auto2d_period_start_x_mm",
            "y_start": "auto2d_airgap_y0_mm",
            "width": "period_length_mm",
            "height": "airgap_mm",
            "materials": ["air"],
            "color": "(180 230 255)",
            "transparency": 0.75,
            "solve_inside": True
        },
        {
            "name": "%sCoil_Pos" % AUTO2D_PREFIX,
            "x_start": "auto2d_coil_pos_x0_mm",
            "y_start": "auto2d_coil_y0_mm",
            "width": "auto2d_coil_sheet_width_mm",
            "height": "auto2d_coil_stack_height_mm",
            "materials": ["copper", "vacuum"],
            "color": "(255 160 60)",
            "transparency": 0.15,
            "solve_inside": True
        },
        {
            "name": "%sCoil_Neg" % AUTO2D_PREFIX,
            "x_start": "auto2d_coil_neg_x0_mm",
            "y_start": "auto2d_coil_y0_mm",
            "width": "auto2d_coil_sheet_width_mm",
            "height": "auto2d_coil_stack_height_mm",
            "materials": ["copper", "vacuum"],
            "color": "(255 210 90)",
            "transparency": 0.15,
            "solve_inside": True
        }
    ]


def build_linear_2d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False):
    scaffold_vars = _scaffold_variables()
    apply_variables(oDesign, scaffold_vars, logger)
    oEditor = _modeler(oDesign)
    _set_model_units(oEditor, logger)

    deleted = []
    if cleanup_first:
        deleted = _delete_auto_objects(oEditor, logger)

    created = []
    existing = _list_auto_objects(oEditor)
    definitions = _linear2d_objects_definition()
    for item in definitions:
        if (item["name"] in existing) and (not cleanup_first):
            logger.log("Reusing existing object %s" % item["name"])
            created.append({"name": item["name"], "material": "existing"})
            continue
        created.append(
            _create_rectangle_with_fallbacks(
                oEditor,
                item["name"],
                item["x_start"],
                item["y_start"],
                item["width"],
                item["height"],
                item["materials"],
                item["color"],
                item["transparency"],
                item["solve_inside"],
                logger
            )
        )

    region_name = "%sRegion" % AUTO2D_PREFIX
    existing = _list_auto_objects(oEditor)
    region_created = False
    if region_name not in existing:
        region_created = _create_region(oEditor, region_name, "auto2d_region_padding_mm", logger)
    else:
        logger.log("Reusing existing region %s" % region_name)
        region_created = True

    created_by_name = {}
    for item in created:
        created_by_name[item["name"]] = item.get("material", "")

    blocking_issues = []
    warnings = []
    magnet_n_material = created_by_name.get("%sMagnet_N" % AUTO2D_PREFIX, "")
    magnet_s_material = created_by_name.get("%sMagnet_S" % AUTO2D_PREFIX, "")
    if magnet_n_material.lower() == "vacuum" or magnet_s_material.lower() == "vacuum":
        blocking_issues.append(
            "Permanent magnets fell back to vacuum. Replace Auto2D_Magnet_N and Auto2D_Magnet_S with NdFeB-N42SH or another permanent-magnet material before trusting torque or back-EMF results."
        )
    elif (not _looks_like_permanent_magnet(magnet_n_material)) or (not _looks_like_permanent_magnet(magnet_s_material)):
        warnings.append(
            "The magnet objects were created with non-NdFeB materials. Verify that the selected material is really a permanent magnet."
        )

    if int(case_row.get("magnet_segments_per_pole", 1)) <= 1:
        warnings.append(
            "magnet_segments_per_pole is 1. This is acceptable for a first baseline, but it may overstate ripple/cogging relative to a segmented rotor."
        )
    warnings.append(
        "This Linearized2D scaffold is now intended to support a transient-ready workflow, but physically meaningful back-EMF still benefits from a dedicated moving-rotor/band setup rather than a purely static geometry snapshot."
    )

    return {
        "cleanup_first": cleanup_first,
        "deleted_objects": deleted,
        "created_objects": created,
        "scaffold_variables": scaffold_vars,
        "region_created_or_present": region_created,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "manual_actions": [
            "Assign %s to %sMagnet_N and %sMagnet_S if the script had to fall back to vacuum" % (PREFERRED_MAGNET_MATERIAL, AUTO2D_PREFIX, AUTO2D_PREFIX),
            "Assign permanent magnet orientation: %sMagnet_N coercivity approximately (0, 1, 0) and %sMagnet_S approximately (0, -1, 0) in the current Linearized2D coordinates" % (AUTO2D_PREFIX, AUTO2D_PREFIX),
            "Create one transient-friendly winding from %sCoil_Pos and %sCoil_Neg and drive it with the configured phase current waveform tied to phase_current_rms" % (AUTO2D_PREFIX, AUTO2D_PREFIX),
            "Verify that %sMotionBand encloses the moving rotor-side objects without clipping the stator-side coil objects" % AUTO2D_PREFIX,
            "Apply left/right periodic or master/slave boundaries across one model period based on period_length_mm",
            "Add manual mesh refinement in the 0.7 mm air gap with at least 3 to 4 layers before trusting ripple/cogging results",
            "If you need physically meaningful transient back-EMF, add a moving-rotor translation/band setup instead of relying on time-varying current alone",
            "Create the 5 required named reports after solving once"
        ]
    }


def ensure_linear_2d_design(oProject, oDesign, project_cfg, case_row, logger):
    existing = _list_auto_objects(_modeler(oDesign))
    if existing:
        logger.log("Auto-generated 2D scaffold already exists; reusing current geometry")
        return {
            "cleanup_first": False,
            "deleted_objects": [],
            "created_objects": [{"name": name, "material": "existing"} for name in existing],
            "scaffold_variables": _scaffold_variables(),
            "region_created_or_present": True,
            "manual_actions": []
        }
    logger.log("Building new auto-generated 2D scaffold")
    return build_linear_2d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False)


def ensure_sector_3d_design(oProject, oDesign, project_cfg, case_row, logger):
    logger.log("build_hooks.ensure_sector_3d_design is still a placeholder")
    logger.log("The current automated build effort is focused on the 2D linearized scaffold first")
    return {
        "manual_actions": [
            "Build the 3D sector model manually for now"
        ]
    }
