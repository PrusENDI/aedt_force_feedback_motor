from __future__ import print_function

import argparse
import json

from agent_runtime import enqueue_command
from agent_runtime import runtime_context


def main():
    parser = argparse.ArgumentParser(description="Queue a command for the in-AEDT agent host.")
    parser.add_argument("action", help="Command action such as probe_session, run_2d_screen, run_3d_validation, run_script, stop_worker")
    parser.add_argument("--script", dest="script_path", help="Relative workspace script path for run_script")
    parser.add_argument("--payload-json", dest="payload_json", default="", help="Extra JSON payload to merge into the command payload")
    parser.add_argument("--requested-by", dest="requested_by", default="external_agent")
    args = parser.parse_args()

    context = runtime_context()
    payload = {}
    if args.payload_json:
        payload.update(json.loads(args.payload_json))
    if args.script_path:
        payload["script_path"] = args.script_path

    command_path, command = enqueue_command(
        context,
        action=args.action,
        payload=payload,
        requested_by=args.requested_by
    )
    print(command_path)
    print(command["command_id"])


if __name__ == "__main__":
    main()
