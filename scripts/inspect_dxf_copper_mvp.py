from __future__ import print_function

import os

from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import load_json
from aedt_native_common import Logger
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import timestamp_string


MILESTONE = "Milestone 2: DXF-Compatible 3D Copper MVP"


def _artifact_paths(root):
    return {
        "input_json": os.path.join(root, "artifacts", "dxf_copper_mvp.json"),
        "json": os.path.join(root, "artifacts", "dxf_copper_mvp_inspection.json"),
        "md": os.path.join(root, "reports", "dxf_copper_mvp_inspection.md"),
    }


def _load_build_summary(path):
    if not os.path.isfile(path):
        return None
    return load_json(path)


def build_inspection_summary(build_summary=None, input_artifact_path=""):
    blocking_issues = []
    if build_summary is None:
        build_summary = {}
        blocking_issues.append("dxf_copper_mvp_artifact_missing")

    aedt_build = build_summary.get("aedt_build", {})
    terminal_faces = list(build_summary.get("terminal_faces", []))
    terminal_faces_present = len(terminal_faces) >= 2
    if not terminal_faces_present:
        blocking_issues.append("terminal_faces_incomplete")
    if not aedt_build.get("mesh_assigned", False):
        blocking_issues.append("mesh_defense_not_assigned")
    if not build_summary.get("geometry_ready", False):
        blocking_issues.append("aedt_geometry_not_ready")

    return {
        "timestamp": timestamp_string(),
        "milestone": MILESTONE,
        "input_artifact_path": input_artifact_path,
        "mvp_object_name": aedt_build.get("object_name", ""),
        "sheet_name": aedt_build.get("sheet_name", ""),
        "sheet_created": bool(aedt_build.get("sheet_created", False)),
        "thickened": bool(aedt_build.get("thickened", False)),
        "mesh_assigned": bool(aedt_build.get("mesh_assigned", False)),
        "face_count": int(aedt_build.get("face_count", 0) or 0),
        "terminal_faces_present": terminal_faces_present,
        "terminal_faces": terminal_faces,
        "geometry_ready": bool(build_summary.get("geometry_ready", False)),
        "dxf_compatible_copper_ready": bool(build_summary.get("dxf_compatible_copper_ready", False)),
        "dc_conduction_ready": bool(build_summary.get("dc_conduction_ready", False)),
        "blocking_issues": sorted(set(blocking_issues)),
        "manual_actions": [
            "Open AEDT and visually inspect that the object is a path-derived copper plate, not a phase-belt envelope.",
            "Confirm terminal faces are on the two terminal pads before applying DC Conduction.",
        ],
    }


def markdown_text(summary):
    lines = []
    lines.append("# DXF Copper MVP Inspection")
    lines.append("")
    lines.append("This artifact inspects the V1 copper object gate before DC Conduction.")
    lines.append("")
    for key in [
        "timestamp",
        "milestone",
        "input_artifact_path",
        "mvp_object_name",
        "sheet_name",
        "sheet_created",
        "thickened",
        "mesh_assigned",
        "face_count",
        "terminal_faces_present",
        "geometry_ready",
        "dxf_compatible_copper_ready",
        "dc_conduction_ready",
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


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "inspect_dxf_copper_mvp_%s.log" % timestamp_string()))
    paths = _artifact_paths(root)
    build_summary = _load_build_summary(paths["input_json"])
    summary = build_inspection_summary(build_summary=build_summary, input_artifact_path=paths["input_json"])
    save_json(paths["json"], summary)
    write_markdown(paths["md"], summary)
    logger.log("Wrote DXF copper MVP inspection artifacts: %s" % paths["json"])
    return paths


if __name__ == "__main__":
    main()
