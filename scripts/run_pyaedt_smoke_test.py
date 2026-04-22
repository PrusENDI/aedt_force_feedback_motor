from __future__ import print_function

import json
import os
import sys
import traceback


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def ensure_dir(path):
    if path and (not os.path.isdir(path)):
        os.makedirs(path)


def load_json(path):
    handle = open(path, "r")
    try:
        return json.load(handle)
    finally:
        handle.close()


def write_text(path, text):
    ensure_dir(os.path.dirname(path))
    handle = open(path, "w")
    try:
        handle.write(text)
    finally:
        handle.close()


def release_desktop_compat(desktop, close_projects=True, keep_session=False):
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
    ensure_dir(os.path.join(root, "artifacts"))
    ensure_dir(os.path.join(root, "logs"))
    marker_path = os.path.join(root, "artifacts", "pyaedt_smoke_marker.txt")
    log_path = os.path.join(root, "artifacts", "pyaedt_smoke_test.log")
    write_text(log_path, "script_loaded\n")

    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    version = "2024.1"
    target_project = os.path.join(root, "artifacts", "pyaedt_smoke_test.aedt")

    from ansys.aedt.core import Desktop

    desktop = None
    try:
        with open(log_path, "a") as handle:
            handle.write("desktop_import_ok\n")
        desktop = Desktop(
            version=version,
            non_graphical=True,
            new_desktop=True,
            close_on_exit=False
        )
        with open(log_path, "a") as handle:
            handle.write("desktop_started\n")
        project_name = project_cfg.get("project_prefix", "ffb_axial_flux") + "_pyaedt_smoke"
        odesktop = desktop.odesktop
        oproject = odesktop.NewProject()
        oproject.Rename(project_name, True)
        oproject.SaveAs(target_project, True)
        with open(marker_path, "w") as handle:
            handle.write("success\n")
        with open(log_path, "a") as handle:
            handle.write("project_saved\n")
    finally:
        if desktop is not None:
            try:
                release_desktop_compat(desktop, close_projects=True, keep_session=False)
                with open(log_path, "a") as handle:
                    handle.write("desktop_released\n")
            except Exception:
                with open(log_path, "a") as handle:
                    handle.write(traceback.format_exc() + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        root = repo_root()
        ensure_dir(os.path.join(root, "artifacts"))
        write_text(os.path.join(root, "artifacts", "pyaedt_smoke_test_error.txt"), traceback.format_exc())
        raise
