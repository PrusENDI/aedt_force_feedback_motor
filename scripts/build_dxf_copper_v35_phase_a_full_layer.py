from __future__ import print_function

import json
import os

import dxf_copper_phase_chain


JSON_ARTIFACT = "dxf_copper_v35_phase_a_full_layer.json"
MARKDOWN_REPORT = "dxf_copper_v35_phase_a_full_layer.md"
SVG_PREVIEW = "dxf_copper_v35_phase_a_full_layer_preview.svg"


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def _write_json(chain, output_path):
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(chain, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _markdown_report(chain):
    validation = chain.get("validation", {})
    diagnostics = chain.get("diagnostics", {})
    transform = chain.get("phase_transform_policy", {})
    not_evaluated = chain.get("not_evaluated", {})
    metadata = chain.get("metadata", {})

    lines = [
        "# DXF Copper V3.5 Phase A Full-Layer",
        "",
        "## V4 handoff",
        "",
        "This artifact is a V4 handoff precursor for the Phase A full-layer geometry chain.",
        "Phase B/C geometry is not evaluated here; phase_b_offset_deg is recorded for downstream transforms only.",
        "The physical bridge is not evaluated and remains outside this Milestone 3.5 writer.",
        "",
        "## Summary",
        "",
        "- v35_full_layer_passed: %s" % chain.get("v35_full_layer_passed"),
        "- milestone: %s" % chain.get("milestone"),
        "- geometry_scope: %s" % chain.get("geometry_scope"),
        "- phase: %s" % chain.get("phase"),
        "- layer: %s" % chain.get("layer"),
        "- segment_count: %s" % chain.get("segment_count"),
        "- ordered_segments_with_physical_gap: %s"
        % (chain.get("logical_connection_policy") == "ordered_segments_with_physical_gap"),
        "- phase_b_offset_deg: %s" % transform.get("phase_b_offset_deg"),
        "- terminal_keepout_policy: %s" % chain.get("terminal_keepout_policy"),
        "",
        "## Validation",
        "",
        "- valid: %s" % validation.get("valid"),
        "- blocking_issues: %s" % (chain.get("blocking_issues") or []),
        "- validation_issues: %s" % (validation.get("issues") or []),
        "",
        "## Geometry Inventory",
        "",
        "- full_layer_regions: %s" % len(chain.get("full_layer_regions") or []),
        "- full_layer_outline_groups_xy_mm: %s"
        % len(chain.get("full_layer_outline_groups_xy_mm") or []),
        "- full_layer_aedt_polyline_regions_mm: %s"
        % len(chain.get("full_layer_aedt_polyline_regions_mm") or []),
        "- full_layer_centerline_points_xy_mm: %s"
        % len(chain.get("full_layer_centerline_points_xy_mm") or []),
        "- logical_connection_policy: %s" % chain.get("logical_connection_policy"),
        "- metadata.logical_connection_policy: %s" % metadata.get("logical_connection_policy"),
        "",
        "## Diagnostics",
        "",
        "- centerline_length_mm: %s" % diagnostics.get("centerline_length_mm"),
        "- copper_area_mm2: %s" % diagnostics.get("copper_area_mm2"),
        "- radial_fill_ratio: %s" % diagnostics.get("radial_fill_ratio"),
        "- angular_occupancy_ratio: %s" % diagnostics.get("angular_occupancy_ratio"),
        "",
        "## Not Evaluated",
        "",
    ]

    for key in sorted(not_evaluated):
        lines.append("- %s: %s" % (key, not_evaluated[key]))

    lines.extend(
        [
            "",
            "## Policies",
            "",
            "- terminal_keepout_policy: %s" % chain.get("terminal_keepout_policy"),
            "- terminal keepouts are reserved metadata only, not final terminal escape geometry.",
            "- physical bridge routing is intentionally not evaluated in this milestone.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_markdown(chain, output_path):
    with open(output_path, "w", encoding="utf-8") as stream:
        stream.write(_markdown_report(chain))


def build_report_artifacts(root=None):
    if root is None:
        root = _project_root()
    root = os.path.abspath(root)

    chain = dxf_copper_phase_chain.build_phase_chain_geometry()
    if chain.get("v35_full_layer_passed") is not True:
        raise RuntimeError("V3.5 Phase A full-layer chain did not pass validation")

    artifacts_dir = os.path.join(root, "artifacts")
    reports_dir = os.path.join(root, "reports")
    _ensure_dir(artifacts_dir)
    _ensure_dir(reports_dir)

    json_path = os.path.join(artifacts_dir, JSON_ARTIFACT)
    md_path = os.path.join(reports_dir, MARKDOWN_REPORT)
    svg_path = os.path.join(artifacts_dir, SVG_PREVIEW)

    _write_json(chain, json_path)
    _write_markdown(chain, md_path)
    dxf_copper_phase_chain.write_phase_full_layer_svg(chain, svg_path)

    return {
        "json": json_path,
        "md": md_path,
        "svg": svg_path,
        "v35_full_layer_passed": chain.get("v35_full_layer_passed"),
    }


if __name__ == "__main__":
    result = build_report_artifacts()
    print(result["json"])
    print(result["md"])
    print(result["svg"])
