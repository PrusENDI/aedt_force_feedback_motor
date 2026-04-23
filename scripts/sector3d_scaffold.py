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
    coreless_cfg = sector_cfg.get("coreless_physics", {})
    winding_cfg = sector_cfg.get("winding", {})
    padding_mm = float(coreless_cfg.get("minimum_region_padding_mm", 8.0))
    padding_airgap_multiplier = float(coreless_cfg.get("region_padding_airgap_multiplier", 4.0))
    current_angle_deg = float(winding_cfg.get("current_angle_deg", 0.0))
    return {
        "outer_radius_mm": "outer_diameter_mm/2",
        "inner_radius_mm": "inner_diameter_mm/2",
        "pole_pairs": "pole_count/2",
        "mechanical_frequency_hz": "speed_rpm/60",
        "electrical_frequency_hz": "mechanical_frequency_hz*pole_pairs",
        "mechanical_period_s": "1/mechanical_frequency_hz",
        "electrical_period_s": "1/electrical_frequency_hz",
        "current_angle_deg": "%.6gdeg" % current_angle_deg,
        "sector_pole_count": str(sector_pole_count),
        "sector_angle_deg": "360deg*sector_pole_count/pole_count",
        "sector_start_angle_deg": "-sector_angle_deg/2",
        "auto3d_pole_pitch_deg": "360deg/pole_count",
        "auto3d_magnet_arc_deg": "auto3d_pole_pitch_deg*pole_arc_ratio",
        "auto3d_phase_belt_count": "3*pole_count",
        "auto3d_phase_belt_angle_deg": "360deg/auto3d_phase_belt_count",
        "auto3d_phase_belt_gap_deg": "auto3d_phase_belt_angle_deg*0.01",
        "auto3d_phase_segment_angle_deg": "auto3d_phase_belt_angle_deg-auto3d_phase_belt_gap_deg",
        "auto3d_region_padding_mm": "%.6gmm + %.6g*airgap_mm" % (padding_mm, padding_airgap_multiplier),
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


def physics_contract(project_cfg):
    sector_cfg = project_cfg.get("sector_3d", {})
    return {
        "contract_layers": dict(sector_cfg.get("contract_layers", {})),
        "coreless_physics": dict(sector_cfg.get("coreless_physics", {})),
        "transient": dict(sector_cfg.get("transient", {})),
        "boundaries": dict(sector_cfg.get("boundaries", {})),
        "motion": dict(sector_cfg.get("motion", {})),
        "winding": dict(sector_cfg.get("winding", {})),
        "mesh": dict(sector_cfg.get("mesh", {})),
        "verification": dict(sector_cfg.get("verification", {}))
    }


def literature_basis():
    return [
        {
            "source": "Tokgoz thesis, 2022",
            "guidance": "Treat copper utilization, low inductance risk, and manufacturability as first-class design constraints in PCB-based AFPM studies.",
            "link": "https://open.metu.edu.tr/handle/11511/97372"
        },
        {
            "source": "Tokgoz et al., IEEE TEC, 2022",
            "guidance": "Keep electromagnetic, thermal, and structural feasibility coupled during optimization instead of optimizing torque in isolation.",
            "link": "https://doi.org/10.1109/TEC.2022.3213896"
        },
        {
            "source": "Wu et al., Applied Sciences, 2022",
            "guidance": "Use a Maxwell 3D sector or half-model with motion boundary, master/slave periodicity, and manual air-gap mesh refinement for practical AFPM optimization.",
            "link": "https://doi.org/10.3390/app12157863"
        },
        {
            "source": "Corey thesis, 2019",
            "guidance": "Use a small number of 3D anchor cases to decide which 2D trends remain trustworthy.",
            "link": "https://minds.wisconsin.edu/handle/1793/79090"
        },
        {
            "source": "Gong thesis, 2018 and Khatab thesis, 2019",
            "guidance": "Include transient-overload and tolerance sensitivity studies before declaring an axial-flux machine design ready for hardware.",
            "link": "https://etheses.whiterose.ac.uk/id/eprint/21412/ ; https://etheses.whiterose.ac.uk/id/eprint/24063/"
        },
        {
            "source": "Kamper et al., IEEE TIA, 2008",
            "guidance": "Treat air-cored AFPM field spread, lower inductance, and winding-layout sensitivity as intrinsic physics instead of expecting iron-core-like flux concentration.",
            "link": "https://doi.org/10.1109/TIA.2008.2002183"
        },
        {
            "source": "Wang et al., Energies, 2018",
            "guidance": "For double-rotor coreless AFPM machines, use Maxwell 3D to calibrate simplified models whenever leakage and fringing materially affect torque and back-EMF.",
            "link": "https://doi.org/10.3390/en11113162"
        },
        {
            "source": "Jeon et al., Actuators, 2025",
            "guidance": "Refine current-transfer details such as via and interconnect geometry only after the main electromagnetic path is stable.",
            "link": "https://www.mdpi.com/2076-0825/14/9/424"
        }
    ]


def _required_report_names(project_cfg):
    reports_cfg = project_cfg.get("reports", {})
    ordered_keys = [
        "torque_loaded",
        "torque_cogging",
        "back_emf_ll",
        "flux_linkage_a",
        "bmax_backiron",
        "inductance_phase_a",
        "magnet_demag_margin"
    ]
    names = []
    for key in ordered_keys:
        value = str(reports_cfg.get(key, "")).strip()
        if value:
            names.append(value)
    return names


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


def _create_rectangle(oEditor, name, x_start, y_start, z_start, width, height, axis, material, color, transparency, solve_inside):
    return oEditor.CreateRectangle(
        [
            "NAME:RectangleParameters",
            "IsCovered:=", True,
            "XStart:=", x_start,
            "YStart:=", y_start,
            "ZStart:=", z_start,
            "Width:=", width,
            "Height:=", height,
            "WhichAxis:=", axis
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


def _rotate(oEditor, selection_name, axis, angle, logger):
    try:
        oEditor.Rotate(
            [
                "NAME:Selections",
                "Selections:=", selection_name,
                "NewPartsModelFlag:=", "Model"
            ],
            [
                "NAME:RotateParameters",
                "RotateAxis:=", axis,
                "RotateAngle:=", angle
            ]
        )
        logger.log("Rotated %s around %s by %s" % (selection_name, axis, angle))
        return True
    except Exception:
        logger.log("Rotate failed for %s around %s by %s" % (selection_name, axis, angle))
        logger.log(traceback.format_exc())
        return False


def _sweep_around_axis(oEditor, selection_name, axis, sweep_angle, logger):
    try:
        oEditor.SweepAroundAxis(
            [
                "NAME:Selections",
                "Selections:=", selection_name,
                "NewPartsModelFlag:=", "Model"
            ],
            [
                "NAME:AxisSweepParameters",
                "DraftAngle:=", "0deg",
                "DraftType:=", "Round",
                "CheckFaceFaceIntersection:=", False,
                "SweepAxis:=", axis,
                "SweepAngle:=", sweep_angle,
                "NumOfSegments:=", "0"
            ]
        )
        logger.log("Swept %s around %s by %s" % (selection_name, axis, sweep_angle))
        return True
    except Exception:
        logger.log("SweepAroundAxis failed for %s around %s by %s" % (selection_name, axis, sweep_angle))
        logger.log(traceback.format_exc())
        return False


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


def _create_annular_sector_with_fallbacks(
    oEditor,
    name,
    z_start,
    inner_radius,
    outer_radius,
    height,
    start_angle_deg,
    sweep_angle_deg,
    materials,
    color,
    transparency,
    solve_inside,
    logger
):
    radial_span = "((%s)-(%s))" % (outer_radius, inner_radius)
    last_error = None
    for material in materials:
        try:
            _create_rectangle(
                oEditor,
                name,
                inner_radius,
                "0mm",
                z_start,
                radial_span,
                height,
                "Y",
                material,
                color,
                transparency,
                solve_inside
            )
            if not _sweep_around_axis(oEditor, name, "Z", "%.12gdeg" % sweep_angle_deg, logger):
                raise RuntimeError("Could not sweep sector solid %s" % name)
            if abs(float(start_angle_deg)) > 1e-9:
                if not _rotate(oEditor, name, "Z", "%.12gdeg" % start_angle_deg, logger):
                    raise RuntimeError("Could not rotate sector solid %s" % name)
            logger.log("Created %s as annular sector with material %s" % (name, material))
            return {"name": name, "material": material}
        except Exception as exc:
            last_error = exc
            logger.log("Could not create annular sector %s with material %s" % (name, material))
            logger.log(traceback.format_exc())
    if last_error:
        raise last_error
    raise RuntimeError("Could not create annular sector %s" % name)


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


def _magnet_pole_objects_definition(case_row):
    pole_count = max(2, int(round(float(case_row.get("pole_count", 24)))))
    pole_arc_ratio = max(0.05, min(0.98, float(case_row.get("pole_arc_ratio", 0.7))))
    pole_pitch_deg = 360.0 / float(pole_count)
    magnet_arc_deg = pole_pitch_deg * pole_arc_ratio
    out = []
    for index in range(pole_count):
        start_angle_deg = (index * pole_pitch_deg) - (0.5 * magnet_arc_deg)
        bottom_direction = (0, 0, 1) if (index % 2 == 0) else (0, 0, -1)
        top_direction = (0, 0, -bottom_direction[2])
        out.append(
            {
                "name": "%sMagnet_Bottom_%03d" % (AUTO3D_PREFIX, index + 1),
                "z_start": "auto3d_z_bottom_magnet_mm",
                "outer_radius": "outer_radius_mm",
                "inner_radius": "inner_radius_mm",
                "height": "magnet_thickness_mm",
                "start_angle_deg": start_angle_deg,
                "sweep_angle_deg": magnet_arc_deg,
                "materials": [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB", "vacuum"],
                "color": "(220 60 60)" if bottom_direction[2] > 0 else "(255 165 90)",
                "transparency": 0.05,
                "solve_inside": True,
                "direction": bottom_direction,
                "rotor": "bottom"
            }
        )
        out.append(
            {
                "name": "%sMagnet_Top_%03d" % (AUTO3D_PREFIX, index + 1),
                "z_start": "auto3d_z_top_magnet_mm",
                "outer_radius": "outer_radius_mm",
                "inner_radius": "inner_radius_mm",
                "height": "magnet_thickness_mm",
                "start_angle_deg": start_angle_deg,
                "sweep_angle_deg": magnet_arc_deg,
                "materials": [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB", "vacuum"],
                "color": "(60 90 220)" if top_direction[2] > 0 else "(120 190 255)",
                "transparency": 0.05,
                "solve_inside": True,
                "direction": top_direction,
                "rotor": "top"
            }
        )
    return out


def _select_existing_base_magnet_material(app):
    for material_name in [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB"]:
        if _safe_call(lambda: app.materials.exists_material(material_name), False):
            return material_name
    return PREFERRED_MAGNET_MATERIAL


def _ensure_oriented_material(app, base_material_name, new_name, direction, logger):
    material = _safe_call(lambda: app.materials.exists_material(new_name), False)
    created = False
    if not material:
        material = app.materials.duplicate_material(base_material_name, name=new_name)
        created = bool(material)
        if created:
            logger.log("Duplicated material %s -> %s" % (base_material_name, new_name))
    if not material:
        raise RuntimeError("Could not duplicate base material %s as %s" % (base_material_name, new_name))
    coercivity = _safe_call(lambda: material.get_magnetic_coercivity(), False)
    if coercivity:
        magnitude = str(coercivity[0]).replace("A_per_meter", "").strip()
    else:
        magnitude = "0"
    material.set_magnetic_coercivity(magnitude, direction[0], direction[1], direction[2])
    logger.log("Set coercivity for %s to magnitude=%s direction=%s" % (new_name, magnitude, direction))
    return {"created": created, "material_name": new_name, "magnitude": magnitude, "direction": direction}


def assign_axial_magnet_materials(oDesktop, oProject, oDesign, magnet_objects, logger):
    from sector3d_aedt import attach_maxwell3d

    if not magnet_objects:
        return {"assigned_ok": False, "results": [], "blocking_issues": ["No magnet objects were generated."]}

    app = attach_maxwell3d(oDesktop, oProject, oDesign, logger)
    object_names = [str(name) for name in _safe_call(lambda: list(app.modeler.object_names), [])]
    base_material_name = _select_existing_base_magnet_material(app)
    material_cache = {}
    results = []
    blocking_issues = []

    for item in magnet_objects:
        object_name = item["name"]
        direction = tuple(item.get("direction", (0, 0, 0)))
        material_name = "%sPM_Axial_%sZ" % (AUTO3D_PREFIX, "Plus" if direction[2] >= 0 else "Minus")
        result = {
            "object_name": object_name,
            "direction": list(direction),
            "material_name": material_name,
            "assigned": False,
            "details": ""
        }
        if object_name not in object_names:
            result["details"] = "object not found"
            blocking_issues.append("Missing required magnet object %s" % object_name)
            results.append(result)
            continue
        try:
            if material_name not in material_cache:
                material_cache[material_name] = _ensure_oriented_material(
                    app,
                    base_material_name,
                    material_name,
                    direction,
                    logger
                )
            app.modeler[object_name].material_name = material_name
            result["assigned"] = True
            result["details"] = "oriented axial magnet material assigned"
        except Exception as exc:
            result["details"] = str(exc)
            blocking_issues.append("Could not assign axial magnet orientation to %s" % object_name)
        results.append(result)

    return {
        "assigned_ok": not bool(blocking_issues),
        "base_material_name": base_material_name,
        "results": results,
        "blocking_issues": blocking_issues
    }


def build_sector_3d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False):
    scaffold_vars = scaffold_variables(project_cfg)
    apply_variables(oDesign, scaffold_vars, logger)
    oEditor = _modeler(oDesign)
    _set_model_units(oEditor, logger)

    deleted = []
    if cleanup_first:
        deleted = _delete_auto_objects(oEditor, logger)

    created = []
    magnet_objects = []
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

    for item in _magnet_pole_objects_definition(case_row):
        if (item["name"] in existing) and (not cleanup_first):
            logger.log("Reusing existing magnet pole %s" % item["name"])
            created.append({"name": item["name"], "material": "existing"})
            magnet_objects.append(item)
            continue
        created.append(
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
        )
        magnet_objects.append(item)

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

    contract = physics_contract(project_cfg)
    blocking_issues = []
    baseline_blocking_issues = []
    warnings = []
    contract_layers = contract["contract_layers"]
    coreless_cfg = contract["coreless_physics"]
    transient_cfg = contract["transient"]
    boundary_cfg = contract["boundaries"]
    motion_cfg = contract["motion"]
    winding_cfg = contract["winding"]
    mesh_cfg = contract["mesh"]
    verification_cfg = contract["verification"]
    required_reports = _required_report_names(project_cfg)
    manual_actions = [
        "Replace the full-annulus flat-copper placeholder with phase-assigned coil sectors or macro-coils before trusting torque or back-EMF results",
        "Cut the full-annulus scaffold into a periodic sector bounded by sector_angle_deg, then assign %s boundaries on the cut faces named %s and %s" % (
            boundary_cfg.get("periodic_strategy", "master_slave"),
            boundary_cfg.get("master_face_name", "Auto3D_Periodic_Master"),
            boundary_cfg.get("slave_face_name", "Auto3D_Periodic_Slave")
        ),
        "Create the %s object `%s` about axis %s with approximately %.3f mm radial clearance and %.3f mm axial clearance before trusting transient torque" % (
            motion_cfg.get("motion_type", "rotating_band"),
            motion_cfg.get("band_object_name", "Auto3D_RotatingBand"),
            motion_cfg.get("axis", "Z"),
            float(motion_cfg.get("radial_clearance_mm", 0.0)),
            float(motion_cfg.get("axial_clearance_mm", 0.0))
        ),
        "Verify that the generated bottom and top magnet pole segments really follow the intended axial SSDR polarity convention before trusting field plots or torque",
        "Create the loaded, cogging, and open-circuit cases using the configured winding connection `%s` and three-phase waveform expressions from config/project.json" % winding_cfg.get("connection", "wye"),
        "Create the required named reports: %s" % ", ".join(required_reports),
        "Apply at least %s air-gap mesh layers and magnet-corner refinement before trusting ripple or cogging" % mesh_cfg.get("airgap_layer_count", 4),
        "Review the surrounding air region after sector cutting. A coreless stator spreads flux more broadly than an iron-core machine, so region padding and cut-face placement must be checked before trusting back-EMF, inductance, or leakage results",
        "Treat Auto3D_FlatCopperPack as an envelope macro-coil only. Before any final signoff, replace it with winding segmentation that preserves phase periodicity and the real flat-copper current path",
        "Add an inductance extraction path for `%s` using flux linkage or magnetic energy, then compare the result against the target range %.3f to %.3f mH" % (
            project_cfg.get("reports", {}).get("inductance_phase_a", "Inductance_PhaseA"),
            float(coreless_cfg.get("inductance_target_range_mh", [0.0, 0.0])[0]),
            float(coreless_cfg.get("inductance_target_range_mh", [0.0, 0.0])[-1])
        ),
        "Run a peak-current loaded demagnetization review and bind the result to `%s` before trusting overload capability" % project_cfg.get("reports", {}).get("magnet_demag_margin", "MagnetDemag_Margin"),
        "Verify that the stator support material is FR4 or an equivalent non-magnetic structural material if the script had to fall back to vacuum",
        "Run the first anchor cases in order: %s" % ", ".join(verification_cfg.get("anchor_case_labels", [])),
        "Do not sign off the machine from this SSDR model alone. Correlate the shortlisted design to the final `%s` architecture with `%s` active air-gap faces before claiming hardware readiness" % (
            contract_layers.get("final_target_topology", "S1-R1-S2-R2-S3"),
            contract_layers.get("final_target_active_gap_faces", 4)
        )
    ]

    magnet_materials = [created_by_name.get(item["name"], "") for item in magnet_objects]
    support_material = created_by_name.get("%sStatorSupport" % AUTO3D_PREFIX, "")
    copper_material = created_by_name.get("%sFlatCopperPack" % AUTO3D_PREFIX, "")

    if any([str(material_name).lower() == "vacuum" for material_name in magnet_materials]):
        item = "Permanent magnets fell back to vacuum. Replace the generated Auto3D_Magnet_* pole segments with NdFeB-N42SH or another permanent-magnet material before trusting flux, torque, or back-EMF."
        blocking_issues.append(item)
        baseline_blocking_issues.append(item)
    elif magnet_materials and any([(not _looks_like_permanent_magnet(material_name)) for material_name in magnet_materials]):
        warnings.append(
            "The magnet objects were created with non-NdFeB materials. Verify that the selected materials are really permanent magnets."
        )

    if support_material.lower() == "vacuum":
        warnings.append(
            "The stator support fell back to vacuum. This is acceptable for an EM-first baseline, but replace it with FR4_epoxy or a structural support material before tolerance and thermal studies."
        )

    if copper_material.lower() == "vacuum":
        item = "The flat-copper pack fell back to vacuum. Replace Auto3D_FlatCopperPack with copper before trying to define current-carrying conductors."
        blocking_issues.append(item)
        baseline_blocking_issues.append(item)
    if len(magnet_objects) < 2:
        item = "The scaffold did not create segmented rotor magnets, so it cannot represent alternating axial poles."
        blocking_issues.append(item)
        baseline_blocking_issues.append(item)

    if coreless_cfg.get("stator_is_coreless", False):
        warnings.append(
            "This contract is for a coreless hybrid stator. Expect broader fringing fields, stronger leakage, and lower inductance than an iron-core AFPM with similar envelope dimensions."
        )
    if coreless_cfg.get("do_not_reuse_iron_core_assumptions", False):
        warnings.append(
            "Do not interpret this scaffold with iron-core assumptions such as strong slotting-driven flux concentration, naturally high inductance, or narrow flux return paths through the stator."
        )
    if coreless_cfg.get("macro_coil_is_envelope_model_only", False):
        warnings.append(
            "Auto3D_FlatCopperPack is only an envelope conductor model. It is acceptable for early correlation, but AC loss, current crowding, and periodic winding legality require a more detailed conductor layout."
        )
    if contract_layers.get("require_final_topology_correlation_before_signoff", False):
        warnings.append(
            "The current scaffold is only the calibration truth model for `%s`. Final design signoff still requires correlation to the `%s` target topology."
            % (
                contract_layers.get("calibration_topology", "SSDR"),
                contract_layers.get("final_target_topology", "S1-R1-S2-R2-S3")
            )
        )
    warnings.append(
        "The current Sector3D scaffold intentionally builds a full annular SSDR stack first. Periodic sector cutting, detailed winding segmentation, motion bands, and final report binding remain the next iteration targets."
    )
    warnings.append(
        "The active 3D physics contract expects a transient setup of `%s` stop time `%s`, with `%s` samples per electrical period, following the repo's research-backed validation strategy."
        % (
            transient_cfg.get("time_step_expression", ""),
            transient_cfg.get("stop_time_expression", ""),
            transient_cfg.get("samples_per_electrical_period_for_reports", "")
        )
    )
    if boundary_cfg.get("require_sector_cut_before_validation", False):
        blocking_issues.append(
            "The scaffold is still a full annulus. Convert it into a true sector with %s boundaries before using it as the production validation template."
            % boundary_cfg.get("periodic_strategy", "master_slave")
        )
    if coreless_cfg.get("require_inductance_check", False):
        warnings.append(
            "Inductance is a first-class validation item for this coreless machine. Do not trust current ripple, drive compatibility, or torque-per-amp conclusions until `%s` is extracted."
            % project_cfg.get("reports", {}).get("inductance_phase_a", "Inductance_PhaseA")
        )
    if coreless_cfg.get("require_demagnetization_check", False):
        warnings.append(
            "Demagnetization must be checked under the `%s` condition because the low-permeability stator path does not shield the magnets the way an iron-core stator would."
            % coreless_cfg.get("demag_check_case", "peak_current_loaded")
        )

    return {
        "cleanup_first": cleanup_first,
        "deleted_objects": deleted,
        "created_objects": created,
        "magnet_objects": magnet_objects,
        "scaffold_variables": scaffold_vars,
        "physics_contract": contract,
        "literature_basis": literature_basis(),
        "region_created_or_present": region_created,
        "baseline_blocking_issues": baseline_blocking_issues,
        "baseline_ready_for_solve": not bool(baseline_blocking_issues) and not bool(blocking_issues),
        "blocking_issues": blocking_issues,
        "validation_ready_for_template": not bool(blocking_issues),
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
            "physics_contract": physics_contract(project_cfg),
            "literature_basis": literature_basis(),
            "region_created_or_present": True,
            "baseline_blocking_issues": [],
            "baseline_ready_for_solve": False,
            "blocking_issues": [],
            "validation_ready_for_template": False,
            "warnings": [
                "Existing Sector3D geometry was reused. Re-run the dedicated 3D scaffold build if the coreless contract, sector periodicity, or conductor-envelope assumptions have changed."
            ],
            "manual_actions": [
                "Confirm that the reused geometry still satisfies the current coreless contract before launching validation."
            ]
        }
    logger.log("Building new auto-generated 3D scaffold")
    return build_sector_3d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False)
