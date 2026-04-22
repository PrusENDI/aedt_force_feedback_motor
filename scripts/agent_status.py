from __future__ import print_function

import json
import os

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


def main():
    context = runtime_context()
    paths = context["runtime_paths"]
    status = {
        "session": maybe_load(paths["session_json"]),
        "heartbeat": maybe_load(paths["heartbeat_json"]),
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
