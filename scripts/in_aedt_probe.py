from __future__ import print_function

import json
import os


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def ensure_dir(path):
    if path and (not os.path.isdir(path)):
        os.makedirs(path)


def write_json(path, data):
    ensure_dir(os.path.dirname(path))
    handle = open(path, "w")
    try:
        json.dump(data, handle, indent=2, sort_keys=True)
    finally:
        handle.close()


def release_desktop_compat(desktop, close_projects=False, keep_session=True):
    close_flag = not bool(keep_session)
    attempts = [
        {"close_projects": close_projects, "close_on_exit": close_flag},
        {"close_projects": close_projects, "close_desktop": close_flag},
        {"close_projects": close_projects}
    ]
    last_error = None
    for kwargs in attempts:
        try:
            return desktop.release_desktop(**kwargs)
        except TypeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return False


def main():
    root = repo_root()
    artifacts = os.path.join(root, "artifacts")
    ensure_dir(artifacts)

    data = {
        "mode": "inside_aedt",
        "workspace_root": root
    }

    if "oDesktop" in globals():
        desk = oDesktop
        data["desktop_version"] = desk.GetVersion()
        try:
            proj = desk.GetActiveProject()
            data["active_project"] = proj.GetName() if proj else None
        except Exception:
            data["active_project"] = None
        write_json(os.path.join(artifacts, "inside_aedt_probe.json"), data)
        return

    from ansys.aedt.core import Desktop
    desktop = Desktop(new_desktop=False, close_on_exit=False)
    try:
        desk = desktop.odesktop
        data["desktop_version"] = desk.GetVersion()
        try:
            proj = desk.GetActiveProject()
            data["active_project"] = proj.GetName() if proj else None
        except Exception:
            data["active_project"] = None
        write_json(os.path.join(artifacts, "inside_aedt_probe.json"), data)
    finally:
        release_desktop_compat(desktop, close_projects=False, keep_session=True)


if __name__ == "__main__":
    main()
