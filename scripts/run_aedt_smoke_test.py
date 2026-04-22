from __future__ import print_function

import os
import traceback

SMOKE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER_PATH = os.path.join(SMOKE_ROOT, "artifacts", "smoke_test_marker.txt")
EARLY_LOG_PATH = os.path.join(SMOKE_ROOT, "artifacts", "smoke_test_early.log")


def _append(path, message):
    folder = os.path.dirname(path)
    if folder and (not os.path.isdir(folder)):
        os.makedirs(folder)
    handle = open(path, "a")
    try:
        handle.write(message + "\n")
    finally:
        handle.close()


_append(EARLY_LOG_PATH, "script_loaded")

from aedt_native_common import Logger
from aedt_native_common import close_project
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import initialize_aedt
from aedt_native_common import open_or_create_project
from aedt_native_common import repo_root
from aedt_native_common import save_project
from aedt_native_common import timestamp_string


def main():
    root = repo_root()
    ensure_workspace_dirs(root)
    _append(EARLY_LOG_PATH, "workspace_ready")
    logger = Logger(os.path.join(root, "logs", "smoke_test_%s.log" % timestamp_string()))
    logger.log("Starting AEDT smoke test")
    oDesktop = initialize_aedt(logger)
    _append(EARLY_LOG_PATH, "desktop_initialized")
    target_project = os.path.join(root, "artifacts", "smoke_test.aedt")
    oProject = open_or_create_project(oDesktop, target_project, logger)
    save_project(oProject, logger)
    close_project(oDesktop, oProject, logger)
    _append(MARKER_PATH, "success")
    logger.log("AEDT smoke test finished successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _append(EARLY_LOG_PATH, traceback.format_exc())
        raise
