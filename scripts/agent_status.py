from __future__ import print_function

import json
import os
import datetime

from agent_runtime import list_command_files
from agent_runtime import runtime_context


def maybe_load(path):
    if not os.path.isfile(path):
        return None
    handle = open(path, "r")
    try:
        return json.load(handle)
    finally:
        handle.close()


def maybe_parse_timestamp(text):
    if not text:
        return None
    try:
        return datetime.datetime.strptime(str(text), "%Y-%m-%dT%H-%M-%SZ")
    except Exception:
        return None


def heartbeat_state(context, heartbeat):
    runtime_cfg = context["runtime_cfg"]
    poll_interval = int(runtime_cfg.get("heartbeat_interval_s", 10))
    stale_after_s = max(30, poll_interval * 3)
    captured = maybe_parse_timestamp((heartbeat or {}).get("captured_at"))
    if not captured:
        return {
            "host_seen": False,
            "host_alive": False,
            "heartbeat_age_s": None,
            "stale_after_s": stale_after_s,
            "status": "missing"
        }
    now = datetime.datetime.utcnow()
    age_s = max(0.0, (now - captured).total_seconds())
    return {
        "host_seen": True,
        "host_alive": age_s <= stale_after_s,
        "heartbeat_age_s": round(age_s, 3),
        "stale_after_s": stale_after_s,
        "status": "alive" if age_s <= stale_after_s else "stale"
    }


def main():
    context = runtime_context()
    paths = context["runtime_paths"]
    heartbeat = maybe_load(paths["heartbeat_json"])
    status = {
        "session": maybe_load(paths["session_json"]),
        "heartbeat": heartbeat,
        "host": heartbeat_state(context, heartbeat),
        "last_result": maybe_load(paths["last_result_json"]),
        "queues": {
            "pending": len(list_command_files(paths["pending_dir"])),
            "running": len(list_command_files(paths["running_dir"])),
            "done": len(list_command_files(paths["done_dir"])),
            "failed": len(list_command_files(paths["failed_dir"]))
        }
    }
    print(json.dumps(status, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
