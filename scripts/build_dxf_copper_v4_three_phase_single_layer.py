from __future__ import print_function

import json
import os

import dxf_copper_three_phase_single_layer


JSON_ARTIFACT = "dxf_copper_v4_three_phase_single_layer.json"
MARKDOWN_REPORT = "dxf_copper_v4_three_phase_single_layer.md"
SVG_PREVIEW = "dxf_copper_v4_three_phase_single_layer_preview.svg"


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def _write_json(geometry, output_path):
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(geometry, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _markdown_report(geometry):
    validation = geometry.get("validation", {})
    metrics = geometry.get("metrics", {})
    pair_metrics = geometry.get("phase_pair_metrics", {})
    handoff = geometry.get("v5_spatial_handoff", {})

    lines = [
        "# DXF Copper V4 Three-Phase Single-Layer",
        "",
        "## Milestone 4 diagnostic pass",
        "",
        "V4 pass means the diagnostic pipeline completed, not that same-plane three-phase copper is physically feasible.",
        "",
        "```python",
        "v4_passed = source_passed and overlap_area_calculated",
        "```",
        "",
        "## Summary",
        "",
        "- v4_passed: %s" % geometry.get("v4_passed"),
        "- source_passed: %s" % geometry.get("source_passed"),
        "- overlap_area_calculated: %s" % geometry.get("overlap_area_calculated"),
        "- same-plane feasibility passed: %s" % geometry.get("same_plane_feasibility_passed"),
        "- v5_spatial_handoff_ready: %s" % geometry.get("v5_spatial_handoff_ready"),
        "- blocking_issues: %s" % (geometry.get("blocking_issues") or []),
        "- same_plane_issues: %s" % (geometry.get("same_plane_issues") or []),
        "",
        "## Electrical And Mechanical Angles",
        "",
        "- phase_offset_angle_units: %s" % geometry.get("phase_offset_angle_units"),
        "- phase_offsets_deg: %s" % geometry.get("phase_offsets_deg"),
        "- pole_pairs_count: %s" % geometry.get("pole_pairs_count"),
        "- mechanical_phase_offsets_deg: %s" % geometry.get("mechanical_phase_offsets_deg"),
        "",
        "## Same-Plane Diagnostics",
        "",
        "- phase_to_phase_minimum_clearance_mm: %s"
        % metrics.get("phase_to_phase_minimum_clearance_mm"),
        "- phase_pair_overlap_area_mm2: %s"
        % metrics.get("phase_pair_overlap_area_mm2"),
    ]

    for pair_name in sorted(pair_metrics):
        pair = pair_metrics[pair_name]
        lines.append(
            "- %s: minimum_clearance_mm=%s, overlap_area_mm2=%s"
            % (pair_name, pair.get("minimum_clearance_mm"), pair.get("overlap_area_mm2"))
        )

    lines.extend(
        [
            "",
            "## V5 Spatial Handoff",
            "",
            "- recommended_layer_sequence: %s"
            % handoff.get("recommended_layer_sequence"),
            "- z_assignment_policy: %s" % handoff.get("z_assignment_policy"),
            "- layer_instances: %s" % handoff.get("layer_instances"),
            "",
            "## Terminal Keepout",
            "",
            "- terminal keepout count: %s" % len(geometry.get("terminal_keepouts") or []),
            "- terminal keepout conflicts: %s"
            % (geometry.get("terminal_keepout_conflicts") or []),
            "",
            "## Not Evaluated",
            "",
        ]
    )

    for key, value in sorted((geometry.get("not_evaluated") or {}).items()):
        lines.append("- %s: %s" % (key, value))

    lines.extend(
        [
            "",
            "## Validation",
            "",
            "- validation: %s" % validation,
            "",
        ]
    )
    return "\n".join(lines)


def _write_markdown(geometry, output_path):
    with open(output_path, "w", encoding="utf-8") as stream:
        stream.write(_markdown_report(geometry))


def _attach_status(geometry, status):
    geometry["validation"] = status
    for key in [
        "source_passed",
        "overlap_area_calculated",
        "same_plane_feasibility_passed",
        "v4_passed",
        "v5_spatial_handoff_ready",
        "blocking_issues",
        "same_plane_issues",
    ]:
        geometry[key] = status.get(key)


def build_report_artifacts(root=None):
    if root is None:
        root = _project_root()
    root = os.path.abspath(root)

    geometry = dxf_copper_three_phase_single_layer.build_three_phase_single_layer_geometry()
    status = dxf_copper_three_phase_single_layer.validate_three_phase_single_layer_geometry(
        geometry
    )
    _attach_status(geometry, status)

    if (
        not geometry.get("source_passed")
        or not geometry.get("overlap_area_calculated")
        or not geometry.get("v4_passed")
        or not geometry.get("v5_spatial_handoff_ready")
        or geometry.get("blocking_issues")
    ):
        raise RuntimeError("V4 three-phase diagnostic pipeline did not pass")

    artifacts_dir = os.path.join(root, "artifacts")
    reports_dir = os.path.join(root, "reports")
    _ensure_dir(artifacts_dir)
    _ensure_dir(reports_dir)

    json_path = os.path.join(artifacts_dir, JSON_ARTIFACT)
    md_path = os.path.join(reports_dir, MARKDOWN_REPORT)
    svg_path = os.path.join(artifacts_dir, SVG_PREVIEW)

    _write_json(geometry, json_path)
    _write_markdown(geometry, md_path)
    dxf_copper_three_phase_single_layer.write_three_phase_svg(geometry, svg_path)

    return {
        "json": json_path,
        "md": md_path,
        "svg": svg_path,
        "v4_passed": geometry.get("v4_passed"),
    }


if __name__ == "__main__":
    result = build_report_artifacts()
    print(result["json"])
    print(result["md"])
    print(result["svg"])
