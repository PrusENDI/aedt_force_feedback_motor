from __future__ import print_function

import os
import runpy
import shutil
import traceback
import uuid
import sys
import json

from aedt_native_common import config_paths
from aedt_native_common import ensure_dir
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import load_json
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import timestamp_string


def runtime_context(root=None):
    root = root or repo_root()
    ensure_workspace_dirs(root)
    project_cfg = load_json(os.path.join(root, "config", "project.json"))
    paths = config_paths(root, project_cfg)
    runtime_cfg = project_cfg["agent_runtime"]
    runtime_paths = {}
    for key, relpath in runtime_cfg["paths"].items():
        runtime_paths[key] = os.path.join(root, relpath)
    for key in ["pending_dir", "running_dir", "done_dir", "failed_dir"]:
        ensure_dir(runtime_paths[key])
    return {
        "root": root,
        "project_cfg": project_cfg,
        "paths": paths,
        "runtime_cfg": runtime_cfg,
        "runtime_paths": runtime_paths
    }


def safe_call(func, default_value=None):
    try:
        return func()
    except Exception:
        return default_value


def session_snapshot(oDesktop, context):
    root = context["root"]
    pending_dir = context["runtime_paths"]["pending_dir"]
    running_dir = context["runtime_paths"]["running_dir"]
    done_dir = context["runtime_paths"]["done_dir"]
    failed_dir = context["runtime_paths"]["failed_dir"]
    data = {
        "captured_at": timestamp_string(),
        "workspace_root": root,
        "desktop_pid": os.getpid(),
        "desktop_version": safe_call(lambda: oDesktop.GetVersion()),
        "active_project": None,
        "project_list": [],
        "queue_counts": {
            "pending": len(list_command_files(pending_dir)),
            "running": len(list_command_files(running_dir)),
            "done": len(list_command_files(done_dir)),
            "failed": len(list_command_files(failed_dir))
        }
    }
    project = safe_call(lambda: oDesktop.GetActiveProject())
    if project:
        data["active_project"] = safe_call(lambda: project.GetName())
    project_list = safe_call(lambda: list(oDesktop.GetProjectList()), [])
    if project_list:
        data["project_list"] = project_list
    return data


def save_session_snapshot(oDesktop, context):
    snapshot = session_snapshot(oDesktop, context)
    save_json(context["runtime_paths"]["session_json"], snapshot)
    return snapshot


def save_heartbeat(oDesktop, context, state):
    heartbeat = session_snapshot(oDesktop, context)
    heartbeat["worker_state"] = state
    save_json(context["runtime_paths"]["heartbeat_json"], heartbeat)
    session_data = dict(heartbeat)
    if "worker_state" in session_data:
        del session_data["worker_state"]
    save_json(context["runtime_paths"]["session_json"], session_data)
    return heartbeat


def save_last_result(context, payload):
    save_json(context["runtime_paths"]["last_result_json"], payload)


def load_json_file(path, default_value=None):
    if not os.path.isfile(path):
        return default_value
    handle = open(path, "r")
    try:
        return json.load(handle)
    finally:
        handle.close()


def _command_basename(action):
    return "%s_%s_%s.json" % (
        timestamp_string(),
        action,
        uuid.uuid4().hex[:8]
    )


def enqueue_command(context, action, payload=None, requested_by="external_agent"):
    payload = payload or {}
    command = {
        "command_id": uuid.uuid4().hex,
        "created_at": timestamp_string(),
        "requested_by": requested_by,
        "action": action,
        "payload": payload
    }
    basename = _command_basename(action)
    command_path = os.path.join(context["runtime_paths"]["pending_dir"], basename)
    save_json(command_path, command)
    return command_path, command


def list_command_files(folder):
    if not os.path.isdir(folder):
        return []
    names = []
    for name in os.listdir(folder):
        if name.lower().endswith(".json"):
            names.append(os.path.join(folder, name))
    names.sort()
    return names


def claim_next_command(context):
    pending = list_command_files(context["runtime_paths"]["pending_dir"])
    if not pending:
        return None, None
    source_path = pending[0]
    basename = os.path.basename(source_path)
    target_path = os.path.join(context["runtime_paths"]["running_dir"], basename)
    shutil.move(source_path, target_path)
    return target_path, load_json(target_path)


def finalize_command(context, running_path, success, result):
    folder_key = "done_dir" if success else "failed_dir"
    basename = os.path.basename(running_path)
    target_path = os.path.join(context["runtime_paths"][folder_key], basename)
    result["finished_at"] = timestamp_string()
    result["success"] = success
    save_json(running_path, result)
    shutil.move(running_path, target_path)
    save_last_result(context, result)
    return target_path


def update_running_command(context, running_path, patch):
    payload = load_json_file(running_path, default_value={}) or {}
    payload.update(patch or {})
    save_json(running_path, payload)
    return payload


def make_progress_callback(context, oDesktop, running_path):
    def _callback(stage, message="", details=None):
        details = details or {}
        progress = {
            "progress_at": timestamp_string(),
            "progress_stage": stage,
            "progress_message": message,
            "progress_details": details
        }
        update_running_command(context, running_path, progress)
        save_heartbeat(oDesktop, context, stage)
        return progress
    return _callback


def run_workspace_script(script_path, shared_globals=None):
    shared_globals = dict(shared_globals or {})
    shared_globals["__file__"] = script_path
    main_module = sys.modules.get("__main__")
    old_main_odesktop = getattr(main_module, "oDesktop", None) if main_module else None
    had_main_odesktop = bool(main_module and hasattr(main_module, "oDesktop"))
    try:
        import builtins
        old_builtins_odesktop = getattr(builtins, "oDesktop", None)
        had_builtins_odesktop = hasattr(builtins, "oDesktop")
    except Exception:
        builtins = None
        old_builtins_odesktop = None
        had_builtins_odesktop = False

    try:
        if "oDesktop" in shared_globals and main_module is not None:
            setattr(main_module, "oDesktop", shared_globals["oDesktop"])
        if "oDesktop" in shared_globals and builtins is not None:
            setattr(builtins, "oDesktop", shared_globals["oDesktop"])
        return runpy.run_path(script_path, init_globals=shared_globals, run_name="__main__")
    finally:
        if main_module is not None:
            if had_main_odesktop:
                setattr(main_module, "oDesktop", old_main_odesktop)
            elif hasattr(main_module, "oDesktop"):
                delattr(main_module, "oDesktop")
        if builtins is not None:
            if had_builtins_odesktop:
                setattr(builtins, "oDesktop", old_builtins_odesktop)
            elif hasattr(builtins, "oDesktop"):
                delattr(builtins, "oDesktop")


def run_relative_workspace_script(context, rel_script_path, shared_globals=None):
    script_path = os.path.join(context["root"], rel_script_path)
    if not os.path.isfile(script_path):
        raise IOError("Script not found: %s" % script_path)
    return run_workspace_script(script_path, shared_globals=shared_globals)


def failure_payload(command, exc):
    return {
        "command": command,
        "error": str(exc),
        "traceback": traceback.format_exc()
    }
