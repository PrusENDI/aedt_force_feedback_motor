from __future__ import print_function

import os
import runpy
import shutil
import traceback
import uuid
import sys
import json
import datetime

from aedt_native_common import config_paths
from aedt_native_common import copy_template_if_needed
from aedt_native_common import ensure_design
from aedt_native_common import ensure_dir
from aedt_native_common import ensure_workspace_dirs
from aedt_native_common import load_json
from aedt_native_common import open_or_create_project
from aedt_native_common import repo_root
from aedt_native_common import save_json
from aedt_native_common import timestamp_string
from aedt_native_common import _normalize_solution_type_name


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


def _parse_runtime_timestamp(value):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ["%Y-%m-%dT%H-%M-%SZ", "%Y-%m-%dT%H:%M:%SZ"]:
        try:
            return datetime.datetime.strptime(text, fmt)
        except Exception:
            pass
    return None


def _runtime_timestamp_age_s(value):
    captured = _parse_runtime_timestamp(value)
    if not captured:
        return None
    return (datetime.datetime.utcnow() - captured).total_seconds()


def _running_command_age_s(payload):
    for key in ["progress_at", "started_at", "created_at"]:
        age = _runtime_timestamp_age_s(payload.get(key))
        if age is not None:
            return age
    return None


def recover_running_commands(context, logger=None, current_host_pid=None, stale_after_s=None):
    runtime_cfg = context.get("runtime_cfg", {})
    if stale_after_s is None:
        stale_after_s = max(60, int(runtime_cfg.get("heartbeat_interval_s", 10)) * 6)
    recovered = []
    running_files = list_command_files(context["runtime_paths"]["running_dir"])
    for running_path in running_files:
        payload = load_json_file(running_path, default_value={}) or {}
        age_s = _running_command_age_s(payload)
        if (age_s is not None) and (age_s < stale_after_s):
            if logger:
                logger.log(
                    "Keeping active running command %s age %.1fs below stale threshold %.1fs"
                    % (payload.get("command_id", ""), age_s, stale_after_s)
                )
            continue
        payload["finished_at"] = timestamp_string()
        payload["success"] = False
        payload["result"] = "stale_running_command_recovered"
        payload["error"] = "Recovered stale running command during host startup"
        payload["recovered_by_pid"] = current_host_pid
        payload["recovered_after_s"] = age_s
        payload["stale_after_s"] = stale_after_s
        basename = os.path.basename(running_path)
        target_path = os.path.join(context["runtime_paths"]["failed_dir"], basename)
        save_json(running_path, payload)
        shutil.move(running_path, target_path)
        save_last_result(context, payload)
        recovered.append(
            {
                "command_id": payload.get("command_id"),
                "action": payload.get("action"),
                "host_pid": payload.get("host_pid"),
                "target_path": target_path
            }
        )
        if logger:
            logger.log(
                "Recovered stale running command %s (%s) from previous host pid %s"
                % (
                    payload.get("command_id", ""),
                    payload.get("action", ""),
                    payload.get("host_pid", "")
                )
            )
    return recovered


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


def _script_stage(script_path):
    text = str(script_path or "").replace("\\", "/").lower()
    compact = "".join([char for char in text if char.isalnum()])
    if "build_dxf_copper_v2.py" in text or "dxf_copper_v2" in text:
        return "dxf_copper_v2"
    if (
        "dxf_copper" in text
        or "dxf-copper" in text
        or "dxfcopper" in compact
        or ("v1" in compact and "copper" in compact and "mvp" in compact)
    ):
        return "dxf_copper_mvp"
    if "linear2d" in text or "linear_2d" in text:
        return "linear_2d"
    if "sector3d" in text or "sector_3d" in text:
        return "sector_3d"
    return None


def resolve_host_target(context, command):
    project_cfg = context["project_cfg"]
    paths = context["paths"]
    action = str(command.get("action", "")).strip()
    payload = command.get("payload", {}) or {}

    stage_key = None
    if action == "run_2d_screen":
        stage_key = "linear_2d"
    elif action == "run_3d_validation":
        stage_key = "sector_3d"
    elif action == "run_script":
        stage_key = _script_stage(payload.get("script_path", ""))

    if stage_key == "linear_2d":
        stage_cfg = project_cfg.get("linear_2d", {})
        return {
            "stage_key": stage_key,
            "design_name": stage_cfg.get("design_name", "Linearized2D"),
            "design_type": stage_cfg.get("design_type", "Maxwell 2D"),
            "solution_type": stage_cfg.get("solution_type", "TransientXY"),
            "template_path": paths.get("linear_2d_template", ""),
            "working_path": paths.get("linear_2d_working", "")
        }
    if stage_key == "sector_3d":
        stage_cfg = project_cfg.get("sector_3d", {})
        return {
            "stage_key": stage_key,
            "design_name": stage_cfg.get("design_name", "Sector3D"),
            "design_type": "Maxwell 3D",
            "solution_type": "Transient",
            "template_path": paths.get("sector_3d_template", ""),
            "working_path": paths.get("sector_3d_working", "")
        }
    if stage_key == "dxf_copper_mvp":
        stage_cfg = project_cfg.get("dxf_copper_mvp", {})
        solution_type = stage_cfg.get("solution_type", "ElectroDCConduction")
        if _normalize_solution_type_name(solution_type) == "dcconduction":
            solution_type = "ElectroDCConduction"
        return {
            "stage_key": stage_key,
            "project_mode": stage_cfg.get("host_project_mode", "active_project"),
            "design_name": stage_cfg.get("design_name", "DxfCopperMvp"),
            "design_type": stage_cfg.get("design_type", "Maxwell 3D"),
            "solution_type": solution_type,
            "template_path": "",
            "working_path": ""
        }
    if stage_key == "dxf_copper_v2":
        stage_cfg = project_cfg.get("dxf_copper_v2", {})
        solution_type = stage_cfg.get("solution_type", "ElectroDCConduction")
        if _normalize_solution_type_name(solution_type) == "dcconduction":
            solution_type = "ElectroDCConduction"
        working_path = stage_cfg.get("working_path", paths.get("dxf_copper_v2_working", ""))
        template_path = stage_cfg.get("template_path", "")
        root = context.get("root") or repo_root()
        if working_path and not os.path.isabs(working_path):
            working_path = os.path.join(root, working_path)
        if template_path and not os.path.isabs(template_path):
            template_path = os.path.join(root, template_path)
        return {
            "stage_key": stage_key,
            "project_mode": stage_cfg.get("project_mode", "working_project"),
            "design_name": stage_cfg.get("design_name", "DxfCopperV2SingleLayer"),
            "design_type": stage_cfg.get("design_type", "Maxwell 3D"),
            "solution_type": solution_type,
            "template_path": template_path,
            "working_path": working_path
        }
    return None


def ensure_host_design_ready(oDesktop, context, command, logger):
    target = resolve_host_target(context, command)
    if not target:
        logger.log("No stage-specific host preparation required for action %s" % command.get("action"))
        return {
            "prepared": False,
            "stage_key": None,
            "design_name": None,
            "working_path": None,
            "template_path": None
        }

    working_path = str(target.get("working_path", "") or "")
    template_path = str(target.get("template_path", "") or "")
    if working_path:
        copy_template_if_needed(template_path, working_path, logger)
        oProject = open_or_create_project(oDesktop, working_path, logger)
    else:
        oProject = oDesktop.GetActiveProject()
        if not oProject:
            project_list = safe_call(lambda: list(oDesktop.GetProjectList()), []) or []
            if len(project_list) == 1:
                oProject = oDesktop.SetActiveProject(str(project_list[0]))
                logger.log("Selected the only open project for stage %s: %s" % (target["stage_key"], project_list[0]))
    if not oProject:
        raise RuntimeError("Could not open or create the host project for stage %s" % target["stage_key"])

    oDesign = ensure_design(
        oProject,
        target["design_name"],
        target["design_type"],
        target["solution_type"],
        logger
    )
    project_name = safe_call(lambda: oProject.GetName(), "")
    design_name = safe_call(lambda: oDesign.GetName(), "")
    logger.log(
        "Prepared host context for %s: project=%s design=%s"
        % (target["stage_key"], project_name or "unknown", design_name or "unknown")
    )
    return {
        "prepared": True,
        "stage_key": target["stage_key"],
        "project_name": project_name,
        "design_name": design_name,
        "working_path": working_path,
        "template_path": template_path
    }
