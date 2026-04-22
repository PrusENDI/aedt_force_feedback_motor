from __future__ import print_function

import traceback

from aedt_native_common import apply_variables


AUTO3D_PREFIX = "Auto3D_"
PREFERRED_MAGNET_MATERIAL = "Magnet, permanent, Neodymium N42SH"
PREFERRED_SUPPORT_MATERIAL = "FR4_epoxy"


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


def scaffold_variables(project_cfg):
    sector_cfg = project_cfg.get("sector_3d", {})
    sector_pole_count = max(1, int(sector_cfg.get("sector_model_pole_count", 2)))
    return {
        "outer_radius_mm": "outer_diameter_mm/2",
        "inner_radius_mm": "inner_diameter_mm/2",
        "pole_pairs": "pole_count/2",
        "sector_pole_count": str(sector_pole_count),
        "sector_angle_deg": "360deg*sector_pole_count/pole_count",
        "sector_start_angle_deg": "-sector_angle_deg/2",
        "auto3d_region_padding_mm": "8mm",
        "auto3d_flat_copper_pack_height_mm": "conductor_thickness_mm*parallel_strands + flat_copper_interlayer_insulation_mm*(parallel_strands-1) + flat_copper_bondline_axial_build_mm",
        "auto3d_stator_axial_build_mm": "stator_support_thickness_mm + auto3d_flat_copper_pack_height_mm",
        "auto3d_flat_copper_inner_radius_mm": "coil_mean_radius_mm - coil_radial_span_mm/2",
        "auto3d_flat_copper_outer_radius_mm": "coil_mean_radius_mm + coil_radial_span_mm/2",
        "auto3d_z_bottom_backiron_mm": "0mm",
        "auto3d_z_bottom_magnet_mm": "backiron_thickness_mm",
        "auto3d_z_lower_airgap_mm": "backiron_thickness_mm + magnet_thickness_mm",
        "auto3d_z_stator_support_mm": "backiron_thickness_mm + magnet_thickness_mm + airgap_mm",
        "auto3d_z_flat_copper_mm": "auto3d_z_stator_support_mm + stator_support_thickness_mm",
        "auto3d_z_upper_airgap_mm": "auto3d_z_stator_support_mm + auto3d_stator_axial_build_mm",
        "auto3d_z_top_magnet_mm": "auto3d_z_upper_airgap_mm + airgap_mm",
        "auto3d_z_top_backiron_mm": "auto3d_z_top_magnet_mm + magnet_thickness_mm",
        "auto3d_total_stack_height_mm": "2*backiron_thickness_mm + 2*magnet_thickness_mm + 2*airgap_mm + auto3d_stator_axial_build_mm"
    }


def _list_auto_objects(oEditor):
    attempts = [
        lambda: list(oEditor.GetMatchedObjectName("%s*" % AUTO3D_PREFIX)),
        lambda: list(oEditor.GetMatchedObjectName("Auto3D*"))
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
            if text.startswith(AUTO3D_PREFIX) and (text not in names):
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
        logger.log("Deleted %d existing auto-generated 3D objects" % len(names))
        return names
    except Exception:
        logger.log("Could not delete existing auto-generated 3D objects")
        logger.log(traceback.format_exc())
        return names


def _solid_attributes(name, material, color, transparency, solve_inside):
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


def _create_cylinder(oEditor, name, z_start, radius, height, material, color, transparency, solve_inside):
    return oEditor.CreateCylinder(
        [
            "NAME:CylinderParameters",
            "XCenter:=", "0mm",
            "YCenter:=", "0mm",
            "ZCenter:=", z_start,
            "Radius:=", radius,
            "Height:=", height,
            "WhichAxis:=", "Z",
            "NumSides:=", "0"
        ],
        _solid_attributes(name, material, color, transparency, solve_inside)
    )


def _create_cylinder_with_fallbacks(oEditor, name, z_start, radius, height, materials, color, transparency, solve_inside, logger):
    last_error = None
    for material in materials:
        try:
            _create_cylinder(oEditor, name, z_start, radius, height, material, color, transparency, solve_inside)
            logger.log("Created %s with material %s" % (name, material))
            return {"name": name, "material": material}
        except Exception as exc:
            last_error = exc
            logger.log("CreateCylinder failed for %s with material %s" % (name, material))
    if last_error:
        raise last_error
    raise RuntimeError("Could not create cylinder %s" % name)


def _subtract(oEditor, blank_name, tool_name, logger):
    try:
        oEditor.Subtract(
            [
                "NAME:Selections",
                "Blank Parts:=", blank_name,
                "Tool Parts:=", tool_name
            ],
            [
                "NAME:SubtractParameters",
                "KeepOriginals:=", False
            ]
        )
        logger.log("Subtracted %s from %s" % (tool_name, blank_name))
        return True
    except Exception:
        logger.log("Subtract failed: %s - %s" % (blank_name, tool_name))
        logger.log(traceback.format_exc())
        return False


def _create_annulus_with_fallbacks(
    oEditor,
    name,
    z_start,
    outer_radius,
    inner_radius,
    height,
    materials,
    color,
    transparency,
    solve_inside,
    logger
):
    outer = _create_cylinder_with_fallbacks(
        oEditor, name, z_start, outer_radius, height, materials, color, transparency, solve_inside, logger
    )
    tool_name = "%s_InnerTool" % name
    try:
        _create_cylinder(oEditor, tool_name, z_start, inner_radius, height, "vacuum", "(240 240 240)", 0.95, True)
        if not _subtract(oEditor, name, tool_name, logger):
            raise RuntimeError("Subtract failed for annulus %s" % name)
        return outer
    except Exception:
        logger.log("Could not finish annulus %s automatically" % name)
        logger.log(traceback.format_exc())
        return outer


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
                "-YPadding:=", padding_expr,
                "+ZPaddingType:=", "Absolute Offset",
                "+ZPadding:=", padding_expr,
                "-ZPaddingType:=", "Absolute Offset",
                "-ZPadding:=", padding_expr
            ],
            _solid_attributes(name, "air", "(143 175 143)", 0.9, True)
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


def _sector3d_objects_definition():
    return [
        {
            "name": "%sRotorBackIron_Bottom" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_bottom_backiron_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "backiron_thickness_mm",
            "materials": ["steel_1010", "vacuum"],
            "color": "(120 120 120)",
            "transparency": 0.15,
            "solve_inside": True
        },
        {
            "name": "%sMagnet_Bottom" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_bottom_magnet_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "magnet_thickness_mm",
            "materials": [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB", "vacuum"],
            "color": "(220 60 60)",
            "transparency": 0.05,
            "solve_inside": True
        },
        {
            "name": "%sAirGap_Bottom" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_lower_airgap_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "airgap_mm",
            "materials": ["air"],
            "color": "(180 230 255)",
            "transparency": 0.82,
            "solve_inside": True
        },
        {
            "name": "%sStatorSupport" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_stator_support_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "stator_support_thickness_mm",
            "materials": [PREFERRED_SUPPORT_MATERIAL, "vacuum"],
            "color": "(80 160 80)",
            "transparency": 0.55,
            "solve_inside": True
        },
        {
            "name": "%sFlatCopperPack" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_flat_copper_mm",
            "outer_radius": "auto3d_flat_copper_outer_radius_mm",
            "inner_radius": "auto3d_flat_copper_inner_radius_mm",
            "height": "auto3d_flat_copper_pack_height_mm",
            "materials": ["copper", "vacuum"],
            "color": "(255 150 60)",
            "transparency": 0.2,
            "solve_inside": True
        },
        {
            "name": "%sAirGap_Top" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_upper_airgap_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "airgap_mm",
            "materials": ["air"],
            "color": "(180 230 255)",
            "transparency": 0.82,
            "solve_inside": True
        },
        {
            "name": "%sMagnet_Top" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_top_magnet_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "magnet_thickness_mm",
            "materials": [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB", "vacuum"],
            "color": "(60 90 220)",
            "transparency": 0.05,
            "solve_inside": True
        },
        {
            "name": "%sRotorBackIron_Top" % AUTO3D_PREFIX,
            "z_start": "auto3d_z_top_backiron_mm",
            "outer_radius": "outer_radius_mm",
            "inner_radius": "inner_radius_mm",
            "height": "backiron_thickness_mm",
            "materials": ["steel_1010", "vacuum"],
            "color": "(120 120 120)",
            "transparency": 0.15,
            "solve_inside": True
        }
    ]


def build_sector_3d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False):
    scaffold_vars = scaffold_variables(project_cfg)
    apply_variables(oDesign, scaffold_vars, logger)
    oEditor = _modeler(oDesign)
    _set_model_units(oEditor, logger)

    deleted = []
    if cleanup_first:
        deleted = _delete_auto_objects(oEditor, logger)

    created = []
    existing = _list_auto_objects(oEditor)
    for item in _sector3d_objects_definition():
        if (item["name"] in existing) and (not cleanup_first):
            logger.log("Reusing existing object %s" % item["name"])
            created.append({"name": item["name"], "material": "existing"})
            continue
        created.append(
            _create_annulus_with_fallbacks(
                oEditor,
                item["name"],
                item["z_start"],
                item["outer_radius"],
                item["inner_radius"],
                item["height"],
                item["materials"],
                item["color"],
                item["transparency"],
                item["solve_inside"],
                logger
            )
        )

    region_name = "%sRegion" % AUTO3D_PREFIX
    existing = _list_auto_objects(oEditor)
    region_created = False
    if region_name not in existing:
        region_created = _create_region(oEditor, region_name, "auto3d_region_padding_mm", logger)
    else:
        logger.log("Reusing existing region %s" % region_name)
        region_created = True

    created_by_name = {}
    for item in created:
        created_by_name[item["name"]] = item.get("material", "")

    blocking_issues = []
    warnings = []
    manual_actions = [
        "Replace the full-annulus flat-copper placeholder with phase-assigned coil sectors or macro-coils before trusting torque or back-EMF results",
        "Cut the full-annulus scaffold into a periodic sector bounded by sector_angle_deg, then assign master/slave boundaries on the cut faces",
        "Create the rotating band or equivalent motion region for the rotor assembly before trusting transient torque",
        "Assign magnet directions for Auto3D_Magnet_Bottom and Auto3D_Magnet_Top consistent with the chosen SSDR axial-flux polarity convention",
        "Create the required named reports: Torque_Loaded, Torque_Cogging, BackEMF_LL, FluxLinkage_PhaseA, and Bmax_BackIron",
        "Verify that the stator support material is FR4 or an equivalent non-magnetic structural material if the script had to fall back to vacuum"
    ]

    bottom_magnet_material = created_by_name.get("%sMagnet_Bottom" % AUTO3D_PREFIX, "")
    top_magnet_material = created_by_name.get("%sMagnet_Top" % AUTO3D_PREFIX, "")
    support_material = created_by_name.get("%sStatorSupport" % AUTO3D_PREFIX, "")
    copper_material = created_by_name.get("%sFlatCopperPack" % AUTO3D_PREFIX, "")

    if bottom_magnet_material.lower() == "vacuum" or top_magnet_material.lower() == "vacuum":
        blocking_issues.append(
            "Permanent magnets fell back to vacuum. Replace Auto3D_Magnet_Bottom and Auto3D_Magnet_Top with NdFeB-N42SH or another permanent-magnet material before trusting flux, torque, or back-EMF."
        )
    elif (not _looks_like_permanent_magnet(bottom_magnet_material)) or (not _looks_like_permanent_magnet(top_magnet_material)):
        warnings.append(
            "The magnet objects were created with non-NdFeB materials. Verify that the selected materials are really permanent magnets."
        )

    if support_material.lower() == "vacuum":
        warnings.append(
            "The stator support fell back to vacuum. This is acceptable for an EM-first baseline, but replace it with FR4_epoxy or a structural support material before tolerance and thermal studies."
        )

    if copper_material.lower() == "vacuum":
        blocking_issues.append(
            "The flat-copper pack fell back to vacuum. Replace Auto3D_FlatCopperPack with copper before trying to define current-carrying conductors."
        )

    warnings.append(
        "The current Sector3D scaffold intentionally builds a full annular SSDR stack first. Periodic sector cutting, detailed winding segmentation, motion bands, and final report binding remain the next iteration targets."
    )

    return {
        "cleanup_first": cleanup_first,
        "deleted_objects": deleted,
        "created_objects": created,
        "scaffold_variables": scaffold_vars,
        "region_created_or_present": region_created,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "manual_actions": manual_actions
    }


def ensure_sector_3d_design(oProject, oDesign, project_cfg, case_row, logger):
    existing = _list_auto_objects(_modeler(oDesign))
    if existing:
        logger.log("Auto-generated 3D scaffold already exists; reusing current geometry")
        return {
            "cleanup_first": False,
            "deleted_objects": [],
            "created_objects": [{"name": name, "material": "existing"} for name in existing],
            "scaffold_variables": scaffold_variables(project_cfg),
            "region_created_or_present": True,
            "manual_actions": []
        }
    logger.log("Building new auto-generated 3D scaffold")
    return build_sector_3d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False)
