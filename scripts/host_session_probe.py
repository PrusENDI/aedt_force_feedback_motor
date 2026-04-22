from __future__ import print_function

import json
import os
import sys


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def ensure_dir(path):
    if path and (not os.path.isdir(path)):
        os.makedirs(path)


def main():
    root = repo_root()
    output_path = os.path.join(root, "artifacts", "host_session_probe.json")
    ensure_dir(os.path.dirname(output_path))

    desk = None
    if "oDesktop" in globals():
        desk = oDesktop
    else:
        main_mod = sys.modules.get("__main__")
        if main_mod and hasattr(main_mod, "oDesktop"):
            desk = getattr(main_mod, "oDesktop")

    data = {
        "workspace_root": root,
        "has_odesktop": bool(desk)
    }
    if desk:
        data["desktop_version"] = desk.GetVersion()
        try:
            project = desk.GetActiveProject()
            data["active_project"] = project.GetName() if project else None
        except Exception:
            data["active_project"] = None

    handle = open(output_path, "w")
    try:
        json.dump(data, handle, indent=2, sort_keys=True)
    finally:
        handle.close()


if __name__ == "__main__":
    main()
