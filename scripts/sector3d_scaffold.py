from __future__ import print_function

import traceback

from aedt_native_common import apply_variables
from winding_geometry import flat_copper_active_face_count
from winding_geometry import flat_copper_face_pack_height_mm
from winding_geometry import flat_copper_layers_per_face
from winding_geometry import physical_parallel_path_capacity


AUTO3D_PREFIX = "Auto3D_"
PREFERRED_MAGNET_MATERIAL = "Magnet, permanent, Neodymium N42SH"
PREFERRED_SUPPORT_MATERIAL = "FR4_epoxy"
PHASE_BELT_SEQUENCE = [
    ("PhaseA", "Positive"),
    ("PhaseC", "Negative"),
    ("PhaseB", "Positive"),
    ("PhaseA", "Negative"),
    ("PhaseC", "Positive"),
    ("PhaseB", "Negative")
]


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
        "auto3d_flat_copper_face_count": str(max(1, int(sector_cfg.get("winding", {}).get("active_conductor_face_count", flat_copper_active_face_count(project_cfg))))),
        "auto3d_flat_copper_layers_per_face": str(flat_copper_layers_per_face(project_cfg)),
        "auto3d_phase_belt_count": "3*pole_count",
        "auto3d_phase_belt_angle_deg": "360deg/auto3d_phase_belt_count",
        "auto3d_phase_belt_gap_deg": "auto3d_phase_belt_angle_deg*0.01",
        "auto3d_phase_segment_angle_deg": "auto3d_phase_belt_angle_deg-auto3d_phase_belt_gap_deg",
        "auto3d_region_padding_mm": "%.6gmm + %.6g*airgap_mm" % (padding_mm, padding_airgap_multiplier),
        "auto3d_flat_copper_face_pack_height_mm": "conductor_thickness_mm*auto3d_flat_copper_layers_per_face + flat_copper_interlayer_insulation_mm*(auto3d_flat_copper_layers_per_face-1) + flat_copper_face_bondline_mm",
        "auto3d_stator_axial_build_mm": "stator_support_thickness_mm + auto3d_flat_copper_face_count*auto3d_flat_copper_face_pack_height_mm",
        "auto3d_flat_copper_inner_radius_mm": "coil_mean_radius_mm - coil_radial_span_mm/2",
        "auto3d_flat_copper_outer_radius_mm": "coil_mean_radius_mm + coil_radial_span_mm/2",
        "auto3d_z_bottom_backiron_mm": "0mm",
        "auto3d_z_bottom_magnet_mm": "backiron_thickness_mm",
        "auto3d_z_lower_airgap_mm": "backiron_thickness_mm + magnet_thickness_mm",
        "auto3d_z_lower_flat_copper_mm": "backiron_thickness_mm + magnet_thickness_mm + airgap_mm",
        "auto3d_z_stator_support_mm": "auto3d_z_lower_flat_copper_mm + auto3d_flat_copper_face_pack_height_mm",
        "auto3d_z_upper_flat_copper_mm": "auto3d_z_stator_support_mm + stator_support_thickness_mm",
        "auto3d_z_upper_airgap_mm": "auto3d_z_upper_flat_copper_mm + auto3d_flat_copper_face_pack_height_mm",
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


def _create_box(oEditor, name, x_position, y_position, z_position, x_size, y_size, z_size, material, color, transparency, solve_inside):
    return oEditor.CreateBox(
        [
            "NAME:BoxParameters",
            "XPosition:=", x_position,
            "YPosition:=", y_position,
            "ZPosition:=", z_position,
            "XSize:=", x_size,
            "YSize:=", y_size,
            "ZSize:=", z_size
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
    try:
        sweep = float(sweep_angle_deg)
        start = float(start_angle_deg)
        if sweep <= 0.0:
            raise RuntimeError("Non-positive sector sweep is invalid for %s" % name)
        if sweep >= 180.0:
            raise RuntimeError("Sector sweep %.6gdeg is too large for stable half-space trimming of %s" % (sweep, name))

        sector = _create_annulus_with_fallbacks(
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
        )

        end = start + sweep
        keep_from_start_angle = start + 90.0
        keep_to_end_angle = end - 90.0
        cutter_specs = [
            ("%s_TrimStart" % name, keep_from_start_angle),
            ("%s_TrimEnd" % name, keep_to_end_angle)
        ]
        for cutter_name, rotation_deg in cutter_specs:
            _create_box(
                oEditor,
                cutter_name,
                "-2*(%s)" % outer_radius,
                "-2*(%s)" % outer_radius,
                "((%s)-0.2mm)" % z_start,
                "2*(%s)" % outer_radius,
                "4*(%s)" % outer_radius,
                "((%s)+0.4mm)" % height,
                "vacuum",
                "(240 240 240)",
                0.96,
                True
            )
            if abs(rotation_deg) > 1e-9:
                if not _rotate(oEditor, cutter_name, "Z", "%.12gdeg" % rotation_deg, logger):
                    raise RuntimeError("Could not rotate trimming cutter %s" % cutter_name)
            if not _subtract(oEditor, name, cutter_name, logger):
                raise RuntimeError("Could not trim annular sector %s using %s" % (name, cutter_name))

        logger.log(
            "Created %s as annular sector by trimming an axial annulus between %.6gdeg and %.6gdeg"
            % (name, start, end)
        )
        return sector
    except Exception:
        logger.log("Could not create annular sector %s" % name)
        logger.log(traceback.format_exc())
        raise


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


def _phase_group_template():
    out = {}
    for phase_name in ["PhaseA", "PhaseB", "PhaseC"]:
        out[(phase_name, "Positive")] = []
        out[(phase_name, "Negative")] = []
    return out


def _phase_object_color(phase_name, polarity, face_label):
    face_scale = 0.0 if face_label == "Bottom" else 35.0
    table = {
        ("PhaseA", "Positive"): (230, 95, 45),
        ("PhaseA", "Negative"): (255, 175, 120),
        ("PhaseB", "Positive"): (235, 185, 40),
        ("PhaseB", "Negative"): (245, 225, 130),
        ("PhaseC", "Positive"): (70, 120, 230),
        ("PhaseC", "Negative"): (145, 185, 255)
    }
    red, green, blue = table[(phase_name, polarity)]
    return "(%d %d %d)" % (
        min(255, int(red + face_scale)),
        min(255, int(green + face_scale)),
        min(255, int(blue + face_scale))
    )


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


def _phase_belt_objects_definition(case_row):
    pole_count = max(2, int(round(float(case_row.get("pole_count", 24)))))
    segment_count = max(6, pole_count * 3)
    phase_belt_angle_deg = 360.0 / float(segment_count)
    phase_belt_gap_deg = min(0.08, max(0.01, phase_belt_angle_deg * 0.01))
    phase_segment_angle_deg = max(0.001, phase_belt_angle_deg - phase_belt_gap_deg)
    face_specs = [
        ("Bottom", "auto3d_z_lower_flat_copper_mm"),
        ("Top", "auto3d_z_upper_flat_copper_mm")
    ]
    objects = []
    phase_groups = _phase_group_template()
    for index in range(segment_count):
        phase_name, polarity = PHASE_BELT_SEQUENCE[index % len(PHASE_BELT_SEQUENCE)]
        start_angle_deg = (index * phase_belt_angle_deg) + (0.5 * phase_belt_gap_deg)
        for face_label, z_start in face_specs:
            name = "Auto3D_%s_%s_%s_%03d" % (
                phase_name,
                "Pos" if polarity == "Positive" else "Neg",
                face_label,
                index + 1
            )
            objects.append(
                {
                    "name": name,
                    "z_start": z_start,
                    "outer_radius": "auto3d_flat_copper_outer_radius_mm",
                    "inner_radius": "auto3d_flat_copper_inner_radius_mm",
                    "height": "auto3d_flat_copper_face_pack_height_mm",
                    "start_angle_deg": start_angle_deg,
                    "sweep_angle_deg": phase_segment_angle_deg,
                    "materials": ["copper", "vacuum"],
                    "color": _phase_object_color(phase_name, polarity, face_label),
                    "transparency": 0.18,
                    "solve_inside": True,
                    "phase_name": phase_name,
                    "polarity": polarity,
                    "face_label": face_label
                }
            )
            phase_groups[(phase_name, polarity)].append(name)
    return {
        "objects": objects,
        "phase_groups": phase_groups,
        "segment_count": segment_count,
        "phase_belt_angle_deg": phase_belt_angle_deg,
        "phase_belt_gap_deg": phase_belt_gap_deg,
        "phase_segment_angle_deg": phase_segment_angle_deg
    }


def _project_material_name_map(oProject):
    definition_manager = _safe_call(lambda: oProject.GetDefinitionManager(), None)
    names = _safe_call(lambda: list(definition_manager.GetProjectMaterialNames()), []) if definition_manager else []
    out = {}
    for name in names:
        text = str(name).strip()
        if text:
            out[text.lower()] = text
    return out


def _select_existing_base_magnet_material(oProject):
    available = _project_material_name_map(oProject)
    for material_name in [PREFERRED_MAGNET_MATERIAL, "NdFeB-N42SH", "NdFeB"]:
        matched = available.get(str(material_name).lower())
        if matched:
            return matched
    return PREFERRED_MAGNET_MATERIAL


def _change_geometry_material(oEditor, object_names, material_name, logger):
    names = [str(name) for name in object_names if str(name).strip()]
    if not names:
        return False
    try:
        oEditor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DAttributeTab",
                    ["NAME:PropServers"] + names,
                    ["NAME:ChangedProps", ["NAME:Material", "Value:=", "\"%s\"" % material_name]]
                ]
            ]
        )
        logger.log("Assigned material %s to %d objects" % (material_name, len(names)))
        return True
    except Exception:
        logger.log("Could not assign material %s to objects: %s" % (material_name, ", ".join(names)))
        logger.log(traceback.format_exc())
        return False


def assign_axial_magnet_materials(oProject, oDesign, magnet_objects, logger):
    if not magnet_objects:
        return {"assigned_ok": False, "results": [], "blocking_issues": ["No magnet objects were generated."]}

    oEditor = _modeler(oDesign)
    object_names = _list_auto_objects(oEditor)
    project_materials = _project_material_name_map(oProject)
    base_material_name = _select_existing_base_magnet_material(oProject)
    results = []
    blocking_issues = []
    grouped = {}
    for item in magnet_objects:
        direction = tuple(item.get("direction", (0, 0, 0)))
        material_name = "%sPM_Axial_%sZ" % (AUTO3D_PREFIX, "Plus" if direction[2] >= 0 else "Minus")
        grouped.setdefault(material_name, []).append(item["name"])

    for material_name, names in grouped.items():
        if str(material_name).lower() not in project_materials:
            blocking_issues.append(
                "Missing project material definition %s. Recreate the oriented magnet materials before solving the 3D model."
                % material_name
            )

    for item in magnet_objects:
        object_name = item["name"]
        direction = tuple(item.get("direction", (0, 0, 0)))
        material_name = "%sPM_Axial_%sZ" % (AUTO3D_PREFIX, "Plus" if direction[2] >= 0 else "Minus")
        result = {
            "object_name": object_name,
            "direction": list(direction),
            "material_name": material_name,
            "base_material_name": base_material_name,
            "assigned": False,
            "details": ""
        }
        if object_name not in object_names:
            result["details"] = "object not found"
            blocking_issues.append("Missing required magnet object %s" % object_name)
        elif str(material_name).lower() not in project_materials:
            result["details"] = "required oriented material is missing from project definitions"
        else:
            result["details"] = "pending grouped material assignment"
        results.append(result)

    if not blocking_issues:
        for material_name, names in grouped.items():
            if not _change_geometry_material(oEditor, names, project_materials[str(material_name).lower()], logger):
                blocking_issues.append("Could not assign axial magnet orientation material %s" % material_name)
        if not blocking_issues:
            for result in results:
                result["assigned"] = True
                result["details"] = "oriented axial magnet material assigned via native geometry attributes"

    return {
        "assigned_ok": not bool(blocking_issues),
        "base_material_name": base_material_name,
        "project_materials_seen": sorted(project_materials.values()),
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
    phase_belts = _phase_belt_objects_definition(case_row)
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

    for item in phase_belts["objects"]:
        if (item["name"] in existing) and (not cleanup_first):
            logger.log("Reusing existing phase-belt conductor %s" % item["name"])
            created.append({"name": item["name"], "material": "existing"})
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
        "Review the generated Auto3D_Phase*_Top/Bottom segmented conductors against the intended hybrid winding path before trusting torque or back-EMF results",
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
        "The generated Auto3D_Phase*_Top/Bottom phase-belt solids are a segmented macro-coil truth model, not a finished manufacturable winding. Before final signoff, add explicit crossover/return/interconnect geometry that preserves the chosen hybrid current path.",
        "Keep the rigid PCB carrier as a non-magnetic support/interconnect body, not as the main active conductor, to stay aligned with the selected hybrid route and the cited PCB AFPM literature",
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
    phase_object_names = []
    for names in phase_belts["phase_groups"].values():
        phase_object_names.extend(names)
    copper_materials = [created_by_name.get(name, "") for name in phase_object_names]

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

    if any([str(material_name).lower() == "vacuum" for material_name in copper_materials]):
        item = "At least one segmented flat-copper phase-belt conductor fell back to vacuum. Replace the Auto3D_Phase* conductor solids with copper before trying to define current-carrying conductors."
        blocking_issues.append(item)
        baseline_blocking_issues.append(item)
    if len(magnet_objects) < 2:
        item = "The scaffold did not create segmented rotor magnets, so it cannot represent alternating axial poles."
        blocking_issues.append(item)
        baseline_blocking_issues.append(item)
    expected_copper_faces = max(1, int(winding_cfg.get("active_conductor_face_count", flat_copper_active_face_count(project_cfg))))
    existing_phase_faces = {}
    for item in phase_belts["objects"]:
        if created_by_name.get(item["name"], ""):
            existing_phase_faces[item["face_label"]] = True
    if len(existing_phase_faces) < expected_copper_faces:
        item = "The scaffold did not create the expected separated double-sided phase-belt conductors for the hybrid stator."
        blocking_issues.append(item)
        baseline_blocking_issues.append(item)
    path_capacity = physical_parallel_path_capacity(project_cfg)
    actual_parallel_paths = float(case_row.get("parallel_strands", 1.0))
    if actual_parallel_paths > path_capacity:
        item = (
            "parallel_strands=%.3f exceeds the configured physical flat-copper capacity %.3f. "
            "The literature-backed hybrid contract keeps electrical parallel paths separate from axial stacking, so update the face/layer configuration before trusting this case."
            % (actual_parallel_paths, path_capacity)
        )
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
            "The conductor model is still a macro-coil abstraction. Even with discrete phase belts, AC loss, current crowding, and the exact hybrid return/interconnect path still require a more detailed conductor layout."
        )
    if winding_cfg.get("require_support_and_conductor_separation", False):
        warnings.append(
            "The active 3D contract requires the rigid PCB support and the flat-copper conductors to remain separate solids so the coreless hybrid stator does not collapse back into a single copper block surrogate."
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
        "phase_groups": phase_belts["phase_groups"],
        "phase_belt_segment_count": phase_belts["segment_count"],
        "phase_belt_angle_deg": phase_belts["phase_belt_angle_deg"],
        "phase_belt_gap_deg": phase_belts["phase_belt_gap_deg"],
        "phase_segment_angle_deg": phase_belts["phase_segment_angle_deg"],
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
                "Existing Sector3D geometry was reused. Re-run the dedicated 3D scaffold build if the coreless contract, sector periodicity, or segmented-conductor assumptions have changed."
            ],
            "manual_actions": [
                "Confirm that the reused geometry still satisfies the current coreless contract before launching validation."
            ]
        }
    logger.log("Building new auto-generated 3D scaffold")
    return build_sector_3d_scaffold(oProject, oDesign, project_cfg, case_row, logger, cleanup_first=False)
