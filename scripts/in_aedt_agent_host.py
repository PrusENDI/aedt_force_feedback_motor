from __future__ import print_function

import os
import time
import traceback

from aedt_native_common import Logger
from aedt_native_common import initialize_aedt
from agent_runtime import claim_next_command
from agent_runtime import failure_payload
from agent_runtime import finalize_command
from agent_runtime import make_progress_callback
from agent_runtime import run_relative_workspace_script
from agent_runtime import runtime_context
from agent_runtime import ensure_host_design_ready
from agent_runtime import save_heartbeat
from agent_runtime import save_session_snapshot
from agent_runtime import session_snapshot
from agent_runtime import timestamp_string
from agent_runtime import update_running_command


def _dispatch_command(command, running_path, oDesktop, context, logger):
    action = command["action"]
    payload = command.get("payload", {})
    progress_callback = make_progress_callback(context, oDesktop, running_path)
    shared = {
        "oDesktop": oDesktop,
        "__agent_host_mode": True,
        "__agent_command": command,
        "__agent_context": context,
        "__command_progress_callback": progress_callback
    }
    preparation = None
    if action == "probe_session":
        progress_callback("probe_session", "Capturing AEDT session snapshot")
        snapshot = save_session_snapshot(oDesktop, context)
        return {"command": command, "snapshot": snapshot}
    if action == "run_2d_screen":
        progress_callback("prepare_host", "Preparing active 2D project/design for queued work")
        preparation = ensure_host_design_ready(oDesktop, context, command, logger)
        progress_callback("run_2d_screen", "Starting queued 2D screening batch")
        run_relative_workspace_script(context, os.path.join("scripts", "run_linear_2d_screen.py"), shared)
        return {
            "command": command,
            "result": "2d_screen_complete",
            "preparation": preparation,
            "snapshot": session_snapshot(oDesktop, context)
        }
    if action == "run_3d_validation":
        progress_callback("prepare_host", "Preparing active 3D project/design for queued work")
        preparation = ensure_host_design_ready(oDesktop, context, command, logger)
        progress_callback("run_3d_validation", "Starting queued 3D validation batch")
        run_relative_workspace_script(context, os.path.join("scripts", "run_sector_3d_validate.py"), shared)
        return {
            "command": command,
            "result": "3d_validation_complete",
            "preparation": preparation,
            "snapshot": session_snapshot(oDesktop, context)
        }
    if action == "run_script":
        script_path = payload.get("script_path")
        if not script_path:
            raise ValueError("run_script requires payload.script_path")
        progress_callback("prepare_host", "Preparing active project/design for queued script", {"script_path": script_path})
        preparation = ensure_host_design_ready(oDesktop, context, command, logger)
        progress_callback("run_script", "Executing custom workspace script", {"script_path": script_path})
        run_relative_workspace_script(context, script_path, shared)
        return {
            "command": command,
            "result": "script_complete",
            "preparation": preparation,
            "script_path": script_path,
            "snapshot": session_snapshot(oDesktop, context)
        }
    if action == "stop_worker":
        return {"command": command, "result": "stop_requested"}
    raise ValueError("Unsupported action: %s" % action)


def main():
    context = runtime_context()
    log_path = os.path.join(context["root"], "logs", "in_aedt_agent_host_%s.log" % timestamp_string())
    logger = Logger(log_path)
    logger.log("Starting in-AEDT agent host")
    oDesktop = initialize_aedt(logger)
    save_session_snapshot(oDesktop, context)

    runtime_cfg = context["runtime_cfg"]
    poll_interval = int(runtime_cfg["poll_interval_s"])
    heartbeat_interval = int(runtime_cfg["heartbeat_interval_s"])
    idle_log_interval = int(runtime_cfg["idle_log_interval_s"])
    last_heartbeat = 0.0
    last_idle_log = 0.0
    stop_requested = False

    while not stop_requested:
        now = time.time()
        if (now - last_heartbeat) >= heartbeat_interval:
            save_heartbeat(oDesktop, context, "idle")
            last_heartbeat = now

        running_path, command = claim_next_command(context)
        if not command:
            if (now - last_idle_log) >= idle_log_interval:
                logger.log("Agent host idle; waiting for queued commands")
                last_idle_log = now
            time.sleep(poll_interval)
            continue

        logger.log("Picked up command %s (%s)" % (command.get("command_id"), command.get("action")))
        update_running_command(
            context,
            running_path,
            {
                "started_at": timestamp_string(),
                "host_pid": os.getpid(),
                "host_state": "running"
            }
        )
        save_heartbeat(oDesktop, context, "running")
        success = False
        result = {"command": command}
        try:
            result = _dispatch_command(command, running_path, oDesktop, context, logger)
            success = True
            if command.get("action") == "stop_worker":
                stop_requested = True
        except Exception as exc:
            logger.log("Command failed: %s" % command.get("action"))
            logger.log(traceback.format_exc())
            result = failure_payload(command, exc)
        finalize_command(context, running_path, success, result)
        save_heartbeat(oDesktop, context, "idle")

    logger.log("Agent host stopped")


if __name__ == "__main__":
    main()
