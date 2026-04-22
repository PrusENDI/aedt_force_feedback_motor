from __future__ import print_function

import json
import os
import subprocess
import sys

from aedt_native_common import aedt_connection_policy


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def ensure_dir(path):
    if path and (not os.path.isdir(path)):
        os.makedirs(path)


def run_capture(command):
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        out, err = proc.communicate()
        return {
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", "ignore"),
            "stderr": err.decode("utf-8", "ignore")
        }
    except Exception as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc)
        }


def find_ansysedt():
    base = r"C:\Program Files\AnsysEM"
    hits = []
    if not os.path.isdir(base):
        return None
    for root, _dirs, files in os.walk(base):
        if "ansysedt.exe" in files:
            hits.append(os.path.join(root, "ansysedt.exe"))
    hits.sort(reverse=True)
    if hits:
        return hits[0]
    return None


def find_ansys_python():
    base = r"C:\Program Files\AnsysEM"
    hits = []
    if not os.path.isdir(base):
        return None
    for root, _dirs, files in os.walk(base):
        if "python.exe" in files and "CPython" in root:
            hits.append(os.path.join(root, "python.exe"))
    hits.sort(reverse=True)
    if hits:
        return hits[0]
    return None


def find_pyaedt_python():
    candidates = [
        os.path.join(os.environ.get("APPDATA", ""), ".pyaedt_env", "3_10", "Scripts", "python.exe"),
        os.path.join(os.environ.get("APPDATA", ""), ".pyaedt_env", "3_11", "Scripts", "python.exe")
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def find_pyaedt_cli():
    candidates = [
        os.path.join(os.environ.get("APPDATA", ""), ".pyaedt_env", "3_10", "Scripts", "pyaedt.exe"),
        os.path.join(os.environ.get("APPDATA", ""), ".pyaedt_env", "3_11", "Scripts", "pyaedt.exe")
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def main():
    root = repo_root()
    artifacts = os.path.join(root, "artifacts")
    ensure_dir(artifacts)

    status = {
        "workspace_root": root,
        "ansysedt": find_ansysedt(),
        "ansys_python": find_ansys_python(),
        "pyaedt_python": find_pyaedt_python(),
        "pyaedt_cli": find_pyaedt_cli(),
        "python_executable": sys.executable,
        "aedt_connection_policy": aedt_connection_policy(root)
    }

    if status["ansys_python"]:
        cmd = [
            status["ansys_python"],
            "-c",
            "import importlib.util,sys; "
            "print(importlib.util.find_spec('pyaedt')); "
            "print(importlib.util.find_spec('ansys.aedt.core')); "
            "print(sys.version)"
        ]
        status["ansys_python_probe"] = run_capture(cmd)
    else:
        status["ansys_python_probe"] = {"returncode": -1, "stdout": "", "stderr": "ansys python not found"}

    if status["pyaedt_python"]:
        cmd = [
            status["pyaedt_python"],
            "-c",
            "import importlib.util,sys; "
            "print(importlib.util.find_spec('pyaedt')); "
            "print(importlib.util.find_spec('ansys.aedt.core')); "
            "from ansys.aedt.core.generic.settings import settings; "
            "print('use_grpc_api=' + str(getattr(settings,'use_grpc_api',None))); "
            "print('grpc_secure_mode=' + str(getattr(settings,'grpc_secure_mode',None))); "
            "from ansys.aedt.core import Desktop; "
            "print('Desktop import ok'); "
            "print(sys.version)"
        ]
        status["pyaedt_python_probe"] = run_capture(cmd)
    else:
        status["pyaedt_python_probe"] = {"returncode": -1, "stdout": "", "stderr": "pyaedt python not found"}

    if status["pyaedt_cli"]:
        status["pyaedt_cli_probe"] = run_capture([status["pyaedt_cli"], "version"])
    else:
        status["pyaedt_cli_probe"] = {"returncode": -1, "stdout": "", "stderr": "pyaedt cli not found"}

    out_path = os.path.join(artifacts, "environment_status.json")
    handle = open(out_path, "w")
    try:
        json.dump(status, handle, indent=2, sort_keys=True)
    finally:
        handle.close()

    print(out_path)


if __name__ == "__main__":
    main()
