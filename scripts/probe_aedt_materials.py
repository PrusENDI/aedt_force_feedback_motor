from __future__ import print_function

import os

from aedt_native_common import Logger
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import initialize_aedt
from aedt_native_common import pyaedt_attach
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import timestamp_string
from bootstrap_linear2d_template import _active_design
from bootstrap_linear2d_template import _active_project
from bootstrap_linear2d_template import _normalize_design_name
from bootstrap_linear2d_template import _safe_call


MATCH_TOKENS = ["ndfeb", "magnet"]


def _write_markdown(path, summary):
    lines = []
    lines.append("# AEDT Material Probe Summary")
    lines.append("")
    lines.append("- timestamp: `%s`" % summary.get("timestamp", ""))
    lines.append("- project_name: `%s`" % summary.get("project_name", ""))
    lines.append("- design_name: `%s`" % summary.get("design_name", ""))
    lines.append("- total_aedt_materials: `%s`" % len(summary.get("all_aedt_materials", [])))
    lines.append("- total_project_materials: `%s`" % len(summary.get("project_materials", [])))
    lines.append("")
    lines.append("## Matching Materials")
    lines.append("")
    matches = summary.get("matching_materials", [])
    if not matches:
        lines.append("- None")
    else:
        for item in matches:
            lines.append("- %s" % item)
    lines.append("")
    lines.append("## Project Materials")
    lines.append("")
    project_materials = summary.get("project_materials", [])
    if not project_materials:
        lines.append("- None")
    else:
        for item in project_materials:
            lines.append("- %s" % item)
    lines.append("")
    lines.append("## Suggested Magnet Candidates")
    lines.append("")
    candidates = summary.get("suggested_magnet_candidates", [])
    if not candidates:
        lines.append("- None")
    else:
        for item in candidates:
            lines.append("- %s" % item)
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def _attach_maxwell2d(oDesktop, oProject, oDesign, logger):
    from ansys.aedt.core import Maxwell2d

    pid = _safe_call(lambda: int(oDesktop.GetProcessID()), 0)
    project_name = _safe_call(lambda: oProject.GetName(), None)
    design_name = _normalize_design_name(_safe_call(lambda: oDesign.GetName(), ""))
    return pyaedt_attach(
        lambda **kwargs: Maxwell2d(**kwargs),
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
        "Maxwell2d",
        new_session=False
    )


def _clean_list(items):
    out = []
    seen = {}
    for item in items or []:
        text = str(item)
        if text in seen:
            continue
        seen[text] = True
        out.append(text)
    out.sort(key=lambda name: name.lower())
    return out


def _matching_materials(all_names):
    matches = []
    for name in all_names:
        lower_name = name.lower()
        if any(token in lower_name for token in MATCH_TOKENS):
            matches.append(name)
    return _clean_list(matches)


def _suggested_candidates(matches):
    preferred = []
    secondary = []
    for name in matches:
        lower_name = name.lower()
        if "ndfeb" in lower_name:
            preferred.append(name)
        else:
            secondary.append(name)
    return _clean_list(preferred) + _clean_list(secondary)


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    logger = Logger(os.path.join(root, "logs", "probe_aedt_materials_%s.log" % timestamp_string()))
    artifact_json = os.path.join(root, "artifacts", "aedt_material_probe.json")
    artifact_md = os.path.join(root, "reports", "aedt_material_probe.md")

    oDesktop = initialize_aedt(logger)
    oProject = _active_project(oDesktop)
    oDesign = _active_design(oProject)
    if not oProject:
        raise RuntimeError("No active AEDT project is open")
    if not oDesign:
        raise RuntimeError("No active AEDT design is open")

    app = _attach_maxwell2d(oDesktop, oProject, oDesign, logger)
    all_aedt_materials = _clean_list(_safe_call(lambda: list(app.materials.mat_names_aedt), []))
    project_materials = _clean_list(_safe_call(lambda: list(app.odefinition_manager.GetProjectMaterialNames()), []))
    matching_materials = _matching_materials(all_aedt_materials)
    suggested_candidates = _suggested_candidates(matching_materials)

    summary = {
        "timestamp": timestamp_string(),
        "workspace_root": root,
        "project_name": _safe_call(lambda: oProject.GetName(), ""),
        "design_name": _normalize_design_name(_safe_call(lambda: oDesign.GetName(), "")),
        "all_aedt_materials": all_aedt_materials,
        "project_materials": project_materials,
        "matching_tokens": MATCH_TOKENS,
        "matching_materials": matching_materials,
        "suggested_magnet_candidates": suggested_candidates
    }
    save_json(artifact_json, summary)
    _write_markdown(artifact_md, summary)
    logger.log("Wrote AEDT material probe summary: %s" % artifact_json)


if __name__ == "__main__":
    main()
