from __future__ import print_function

import os

from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import save_json
from agent_runtime import list_command_files
from agent_runtime import runtime_context
from agent_status import heartbeat_state
from agent_status import maybe_load


def _write_markdown(path, summary):
    lines = []
    lines.append("# AEDT Host Bootstrap")
    lines.append("")
    lines.append("- workspace_root: `%s`" % summary.get("workspace_root", ""))
    lines.append("- preferred_python: `%s`" % summary.get("preferred_python", ""))
    lines.append("- host_alive: `%s`" % summary.get("host", {}).get("host_alive", False))
    lines.append("- heartbeat_status: `%s`" % summary.get("host", {}).get("status", "missing"))
    lines.append("- heartbeat_age_s: `%s`" % summary.get("host", {}).get("heartbeat_age_s", ""))
    lines.append("")
    lines.append("## Inside AEDT")
    lines.append("")
    for item in summary.get("inside_aedt_scripts", []):
        lines.append("- `%s`" % item)
    lines.append("")
    lines.append("## Queue Scripts")
    lines.append("")
    for item in summary.get("queue_scripts", []):
        lines.append("- `%s`" % item)
    lines.append("")
    lines.append("## Runtime Queues")
    lines.append("")
    for key, value in summary.get("queues", {}).items():
        lines.append("- %s: `%s`" % (key, value))
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for item in summary.get("notes", []):
        lines.append("- %s" % item)
    handle = open(path, "w")
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()


def main():
    context = runtime_context()
    root = context["root"]
    ensure_workspace_dirs(root)
    paths = context["runtime_paths"]
    heartbeat = maybe_load(paths["heartbeat_json"])
    summary = {
        "workspace_root": root,
        "preferred_python": context["project_cfg"].get("python", {}).get("preferred_interpreter", ""),
        "host": heartbeat_state(context, heartbeat),
        "inside_aedt_scripts": [
            "scripts/in_aedt_probe.py",
            "scripts/in_aedt_agent_host.py"
        ],
        "queue_scripts": [
            "launchers/Queue-ProbeSession.ps1",
            "launchers/Queue-BuildSector3DModel.ps1",
            "launchers/Queue-AssignSector3DExcitation.ps1",
            "launchers/Queue-ApplySector3DTransientSetup.ps1",
            "launchers/Queue-CreateSector3DReports.ps1",
            "launchers/Queue-SolveSector3DSetup.ps1",
            "launchers/Queue-Sector3DBaselineSolve.ps1"
        ],
        "queues": {
            "pending": len(list_command_files(paths["pending_dir"])),
            "running": len(list_command_files(paths["running_dir"])),
            "done": len(list_command_files(paths["done_dir"])),
            "failed": len(list_command_files(paths["failed_dir"]))
        },
        "notes": [
            "Run this bootstrap script from PowerShell before launching the in-AEDT host if you want a fresh status snapshot.",
            "After AEDT is open, run scripts/in_aedt_agent_host.py inside AEDT to activate the live worker.",
            "The in-AEDT host now auto-prepares the matching 2D or 3D project/design before queued scripts run."
        ]
    }

    json_path = os.path.join(root, "artifacts", "agent_host_bootstrap.json")
    md_path = os.path.join(root, "reports", "agent_host_bootstrap.md")
    save_json(json_path, summary)
    _write_markdown(md_path, summary)
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
