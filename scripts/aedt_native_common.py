from __future__ import print_function

import csv
import datetime
import json
import math
import os
import shutil
import sys
import traceback

try:
    basestring
except NameError:
    basestring = str


_DESKTOP_SESSION_HOLD = None
_AEDT_CONNECTION_POLICY_CACHE = None


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def ensure_dir(path):
    if path and (not os.path.isdir(path)):
        os.makedirs(path)


def ensure_workspace_dirs(root):
    names = [
        "aedt_projects",
        "artifacts",
        "cases",
        "exports",
        "logs",
        "reports",
        "runtime",
        "templates"
    ]
    out = {}
    for name in names:
        path = os.path.join(root, name)
        ensure_dir(path)
        out[name] = path
    ensure_dir(os.path.join(root, "exports", "2d"))
    ensure_dir(os.path.join(root, "exports", "3d"))
    ensure_dir(os.path.join(root, "runtime", "pending"))
    ensure_dir(os.path.join(root, "runtime", "running"))
    ensure_dir(os.path.join(root, "runtime", "done"))
    ensure_dir(os.path.join(root, "runtime", "failed"))
    return out


def load_json(path):
    handle = open(path, "r")
    try:
        return json.load(handle)
    finally:
        handle.close()


def save_json(path, data):
    ensure_dir(os.path.dirname(path))
    handle = open(path, "w")
    try:
        json.dump(data, handle, indent=2, sort_keys=True)
    finally:
        handle.close()


def read_csv_rows(path):
    if not os.path.isfile(path):
        return []
    handle = open(path, "r")
    try:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(row)
        return rows
    finally:
        handle.close()


def write_csv_rows(path, rows, fieldnames):
    ensure_dir(os.path.dirname(path))
    handle = open(path, "w")
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    finally:
        handle.close()


def append_csv_row(path, row, fieldnames):
    ensure_dir(os.path.dirname(path))
    file_exists = os.path.isfile(path)
    handle = open(path, "a")
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    finally:
        handle.close()


def timestamp_string():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")


class Logger(object):
    def __init__(self, path):
        self.path = path
        ensure_dir(os.path.dirname(path))

    def log(self, message):
        stamp = timestamp_string()
        line = "[%s] %s" % (stamp, message)
        print(line)
        handle = open(self.path, "a")
        try:
            handle.write(line + "\n")
        finally:
            handle.close()

    def exception(self):
        self.log(traceback.format_exc())


def config_paths(root, project_cfg):
    paths = {}
    for key, relpath in project_cfg["paths"].items():
        paths[key] = os.path.join(root, relpath)
    return paths


def aedt_connection_policy(root=None):
    global _AEDT_CONNECTION_POLICY_CACHE
    if _AEDT_CONNECTION_POLICY_CACHE:
        return dict(_AEDT_CONNECTION_POLICY_CACHE)
    policy = {
        "preferred_host_mode": "in_process",
        "external_attach_order": ["com", "grpc"],
        "new_session_order": ["com", "grpc"],
        "grpc_secure_mode": False
    }
    root = root or repo_root()
    config_path = os.path.join(root, "config", "project.json")
    if os.path.isfile(config_path):
        try:
            project_cfg = load_json(config_path)
            config_policy = dict(project_cfg.get("aedt_connection", {}))
            for key in ["preferred_host_mode", "grpc_secure_mode"]:
                if key in config_policy:
                    policy[key] = config_policy[key]
            for key in ["external_attach_order", "new_session_order"]:
                if config_policy.get(key):
                    policy[key] = list(config_policy[key])
        except Exception:
            pass
    _AEDT_CONNECTION_POLICY_CACHE = dict(policy)
    return dict(policy)


def _normalized_interface_order(order):
    out = []
    for item in order or []:
        text = str(item).strip().lower()
        if text not in ["com", "grpc"]:
            continue
        if text in out:
            continue
        out.append(text)
    if not out:
        out = ["com", "grpc"]
    return out


def _pyaedt_settings_snapshot():
    from ansys.aedt.core.generic.settings import settings

    return {
        "use_grpc_api": getattr(settings, "use_grpc_api", None),
        "grpc_secure_mode": getattr(settings, "grpc_secure_mode", None)
    }


def _restore_pyaedt_settings(snapshot):
    from ansys.aedt.core.generic.settings import settings

    try:
        settings.use_grpc_api = snapshot.get("use_grpc_api")
    except Exception:
        pass
    if hasattr(settings, "grpc_secure_mode"):
        try:
            settings.grpc_secure_mode = snapshot.get("grpc_secure_mode")
        except Exception:
            pass


def _apply_pyaedt_interface(interface_name, policy, logger, label):
    from ansys.aedt.core.generic.settings import settings

    snapshot = _pyaedt_settings_snapshot()
    interface_name = str(interface_name).strip().lower()
    if interface_name == "com":
        settings.use_grpc_api = False
        logger.log("Using PyAEDT COM attach for %s" % label)
    elif interface_name == "grpc":
        settings.use_grpc_api = True
        if hasattr(settings, "grpc_secure_mode"):
            settings.grpc_secure_mode = bool(policy.get("grpc_secure_mode", False))
        logger.log(
            "Using PyAEDT gRPC attach for %s (secure=%s)"
            % (label, getattr(settings, "grpc_secure_mode", None))
        )
    else:
        logger.log("Unknown interface %s requested for %s; leaving PyAEDT defaults untouched" % (interface_name, label))
    return snapshot


def pyaedt_attach(factory, attempt_kwargs_list, logger, label, new_session=False):
    policy = aedt_connection_policy()
    order_key = "new_session_order" if new_session else "external_attach_order"
    interfaces = _normalized_interface_order(policy.get(order_key, ["com", "grpc"]))
    last_error = None
    for interface_name in interfaces:
        snapshot = _apply_pyaedt_interface(interface_name, policy, logger, label)
        try:
            for raw_kwargs in attempt_kwargs_list:
                kwargs = {}
                for key, value in (raw_kwargs or {}).items():
                    if value not in [None, ""]:
                        kwargs[key] = value
                try:
                    app = factory(**kwargs)
                    logger.log("Attached %s with interface=%s kwargs=%s" % (label, interface_name, kwargs))
                    return app
                except Exception as exc:
                    last_error = exc
                    logger.log("Attach attempt failed for %s with interface=%s kwargs=%s" % (label, interface_name, kwargs))
        finally:
            _restore_pyaedt_settings(snapshot)
    if last_error:
        raise last_error
    raise RuntimeError("Could not attach %s through PyAEDT" % label)


def initialize_aedt(logger):
    global _DESKTOP_SESSION_HOLD
    try:
        oDesktop
        logger.log("Using existing AEDT desktop context")
        return oDesktop
    except NameError:
        pass

    main_module = sys.modules.get("__main__")
    if main_module and hasattr(main_module, "oDesktop"):
        logger.log("Using oDesktop from __main__ module")
        return getattr(main_module, "oDesktop")

    try:
        import builtins
        if hasattr(builtins, "oDesktop"):
            logger.log("Using oDesktop from builtins")
            return getattr(builtins, "oDesktop")
    except Exception:
        pass

    try:
        import ScriptEnv
        ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
        logger.log("Initialized AEDT through ScriptEnv")
        return oDesktop
    except Exception:
        logger.log("ScriptEnv unavailable, trying PyAEDT attachment")

    try:
        from ansys.aedt.core import Desktop
        _DESKTOP_SESSION_HOLD = pyaedt_attach(
            lambda **kwargs: Desktop(**kwargs),
            [
                {
                    "new_desktop": False,
                    "close_on_exit": False
                }
            ],
            logger,
            "Desktop",
            new_session=False
        )
        logger.log("Attached to AEDT through PyAEDT Desktop")
        return _DESKTOP_SESSION_HOLD.odesktop
    except Exception:
        logger.exception()
        raise


def copy_template_if_needed(template_path, working_path, logger):
    ensure_dir(os.path.dirname(working_path))
    if os.path.isfile(working_path):
        logger.log("Reusing working project: %s" % working_path)
        return
    if os.path.isfile(template_path):
        shutil.copyfile(template_path, working_path)
        logger.log("Copied template into working project: %s" % working_path)
        return
    logger.log("Template not found, a blank project will be created: %s" % template_path)


def open_or_create_project(oDesktop, working_path, logger):
    project_name = os.path.splitext(os.path.basename(working_path))[0]
    existing_names = []
    try:
        existing_names = [str(name) for name in list(oDesktop.GetProjectList())]
    except Exception:
        existing_names = []
    if project_name in existing_names:
        try:
            oProject = oDesktop.SetActiveProject(project_name)
            if oProject:
                logger.log("Reused already-open project: %s" % project_name)
                return oProject
        except Exception:
            logger.exception()
    if os.path.isfile(working_path):
        try:
            oDesktop.OpenProject(working_path)
            logger.log("Opened project: %s" % working_path)
            return oDesktop.SetActiveProject(project_name)
        except Exception:
            logger.log("OpenProject failed for %s; attempting blank-project fallback" % working_path)
            logger.exception()
    oProject = oDesktop.NewProject()
    if not oProject:
        raise RuntimeError("Could not create a new AEDT project for %s" % working_path)
    oProject.SaveAs(working_path, True)
    logger.log("Created new project: %s" % working_path)
    return oProject


def _normalize_solution_type_name(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        text = " ".join([str(item) for item in value])
    else:
        text = str(value)
    return "".join([char.lower() for char in text if char.isalnum()])


def solution_type_matches(actual_value, expected_value):
    actual = _normalize_solution_type_name(actual_value)
    expected = _normalize_solution_type_name(expected_value)
    if not expected:
        return True
    if actual == expected:
        return True
    if ("transient" in actual) and ("transient" in expected):
        return True
    return False


def get_design_solution_type(oDesign, logger=None):
    attempts = [
        lambda: oDesign.GetSolutionType(),
        lambda: oDesign.GetProblemType()
    ]
    for action in attempts:
        try:
            value = action()
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                text = " ".join([str(item) for item in value if item is not None]).strip()
            else:
                text = str(value).strip()
            if text:
                return text
        except Exception:
            continue
    if logger:
        logger.log("Could not resolve active design solution type")
    return ""


def _normalized_design_name(name):
    if not name:
        return ""
    return str(name).split(";")[0]


def _rename_design_internal(oProject, oDesign, new_name, logger):
    current_name = _normalized_design_name(getattr(oDesign, "GetName", lambda: "")())
    if current_name == new_name:
        return oProject.SetActiveDesign(new_name)

    attempts = [
        ("Project.RenameDesignInstance(old,new)", lambda: oProject.RenameDesignInstance(current_name, new_name)),
        ("Design.RenameDesignInstance(new)", lambda: oDesign.RenameDesignInstance(new_name)),
        ("Design.RenameDesign(new)", lambda: oDesign.RenameDesign(new_name))
    ]
    for label, action in attempts:
        try:
            action()
            renamed = oProject.SetActiveDesign(new_name)
            logger.log("Renamed design %s -> %s using %s" % (current_name, new_name, label))
            return renamed
        except Exception:
            continue
    return None


def _set_design_solution_type(oDesign, solution_type, logger):
    attempts = []
    if solution_type:
        text = str(solution_type)
        if text.endswith("XY"):
            attempts.append(
                ("SetSolutionType(base, XY)", lambda: oDesign.SetSolutionType(text[:-2], "XY"))
            )
        elif text.endswith("Z"):
            attempts.append(
                ("SetSolutionType(base, about Z)", lambda: oDesign.SetSolutionType(text[:-1], "about Z"))
            )
        attempts.append(("SetSolutionType(solution, empty)", lambda: oDesign.SetSolutionType(text, "")))
        attempts.append(("SetSolutionType(solution)", lambda: oDesign.SetSolutionType(text)))
    for label, action in attempts:
        try:
            action()
            logger.log("Changed active design solution type using %s -> %s" % (label, solution_type))
            return True
        except Exception:
            continue
    logger.log("Could not change active design solution type in place to %s" % solution_type)
    return False


def _legacy_design_name(base_name):
    return "%s_legacy_%s" % (base_name, datetime.datetime.utcnow().strftime("%H%M%S"))


def _create_design_with_fallbacks(oProject, design_name, design_type, solution_type, logger):
    create_attempts = [
        ("requested", solution_type),
        ("base_transient", "Transient" if "transient" in _normalize_solution_type_name(solution_type) else solution_type),
        ("blank_magnetostatic", "Magnetostatic"),
        ("blank_magnetostatic_xy", "MagnetostaticXY")
    ]
    attempted = []
    for label, create_solution in create_attempts:
        if not create_solution:
            continue
        if create_solution in attempted:
            continue
        attempted.append(create_solution)
        try:
            logger.log("Trying InsertDesign for %s with solution %s" % (label, create_solution))
            oProject.InsertDesign(design_type, design_name, create_solution, "")
            oDesign = oProject.SetActiveDesign(design_name)
            actual_solution_type = get_design_solution_type(oDesign, logger)
            logger.log("Created design %s with initial solution type %s" % (design_name, actual_solution_type or "unknown"))
            if solution_type_matches(actual_solution_type, solution_type):
                return oDesign
            if _set_design_solution_type(oDesign, solution_type, logger):
                refreshed_solution = get_design_solution_type(oDesign, logger)
                logger.log(
                    "Updated freshly created design %s to solution type %s"
                    % (design_name, refreshed_solution or "unknown")
                )
                if solution_type_matches(refreshed_solution, solution_type):
                    return oDesign
            logger.log(
                "Freshly created design %s still does not match requested solution type %s"
                % (design_name, solution_type)
            )
            try:
                oProject.DeleteDesign(design_name)
                logger.log("Deleted mismatched freshly created design %s before trying the next fallback" % design_name)
            except Exception:
                logger.log("Could not delete mismatched freshly created design %s" % design_name)
        except Exception:
            logger.log("InsertDesign attempt failed for %s using %s" % (design_name, create_solution))
            logger.log(traceback.format_exc())
    raise RuntimeError("Could not create design %s with a transient-compatible solution type" % design_name)


def ensure_design(oProject, design_name, design_type, solution_type, logger):
    must_create_design = False
    try:
        oDesign = oProject.SetActiveDesign(design_name)
        actual_solution_type = get_design_solution_type(oDesign, logger)
        if solution_type_matches(actual_solution_type, solution_type):
            logger.log("Using existing design: %s (solution=%s)" % (design_name, actual_solution_type or "unknown"))
            return oDesign

        logger.log(
            "Existing design %s has incompatible solution type %s (expected %s)"
            % (design_name, actual_solution_type or "unknown", solution_type)
        )

        if _set_design_solution_type(oDesign, solution_type, logger):
            refreshed_design = oProject.SetActiveDesign(design_name)
            refreshed_solution = get_design_solution_type(refreshed_design, logger)
            if solution_type_matches(refreshed_solution, solution_type):
                logger.log("Reused existing design after in-place solution update: %s" % design_name)
                return refreshed_design
            logger.log(
                "Design %s still reports solution type %s after in-place update"
                % (design_name, refreshed_solution or "unknown")
            )

        legacy_name = _legacy_design_name(design_name)
        preserved_design = _rename_design_internal(oProject, oDesign, legacy_name, logger)
        if preserved_design:
            logger.log("Preserved incompatible design as %s before creating a replacement" % legacy_name)
            must_create_design = True
        else:
            try:
                oProject.DeleteDesign(design_name)
                logger.log("Deleted incompatible design %s before recreating it" % design_name)
                must_create_design = True
            except Exception:
                logger.log("Could not preserve or delete incompatible design %s" % design_name)
                raise RuntimeError(
                    "Active design %s is not transient-compatible and could not be replaced automatically" % design_name
                )
    except Exception:
        must_create_design = True
    if must_create_design:
        logger.log("Creating design %s (%s / %s)" % (design_name, design_type, solution_type))
        oDesign = _create_design_with_fallbacks(oProject, design_name, design_type, solution_type, logger)
    else:
        oDesign = oProject.SetActiveDesign(design_name)
    actual_solution_type = get_design_solution_type(oDesign, logger)
    logger.log("Active design %s is now using solution type %s" % (design_name, actual_solution_type or "unknown"))
    return oDesign


def _change_property(oDesign, tab_name, group_name, prop_name, value, mode_name):
    payload = [
        "NAME:AllTabs",
        [
            "NAME:%s" % tab_name,
            ["NAME:PropServers", group_name],
            [
                "NAME:%s" % mode_name,
                ["NAME:%s" % prop_name, "Value:=", value]
            ]
        ]
    ]
    oDesign.ChangeProperty(payload)


def _list_local_variables(oDesign):
    attempts = [
        lambda: oDesign.GetProperties("LocalVariableTab", "LocalVariables"),
        lambda: oDesign.GetPropNames("LocalVariableTab", "LocalVariables"),
        lambda: oDesign.GetVariables()
    ]
    for action in attempts:
        try:
            result = action()
            if result:
                names = []
                seen = {}
                for item in list(result):
                    text = str(item)
                    if text in seen:
                        continue
                    seen[text] = True
                    names.append(text)
                return names
        except Exception:
            continue
    return []


def _new_variable_payload(name, value):
    return [
        "NAME:AllTabs",
        [
            "NAME:LocalVariableTab",
            ["NAME:PropServers", "LocalVariables"],
            [
                "NAME:NewProps",
                [
                    "NAME:%s" % name,
                    "PropType:=", "VariableProp",
                    "UserDef:=", True,
                    "Value:=", value,
                    "Description:=", "",
                    "ReadOnly:=", False,
                    "Hidden:=", False,
                    "Sweep:=", False
                ]
            ]
        ]
    ]


def _changed_variable_payload(name, value):
    return [
        "NAME:AllTabs",
        [
            "NAME:LocalVariableTab",
            ["NAME:PropServers", "LocalVariables"],
            [
                "NAME:ChangedProps",
                [
                    "NAME:%s" % name,
                    "Value:=", value
                ]
            ]
        ]
    ]


def set_design_variable(oDesign, name, value, logger=None):
    existing_names = _list_local_variables(oDesign)
    lower_case_names = [item.lower() for item in existing_names]
    last_error = None

    if name.lower() in lower_case_names:
        try:
            oDesign.ChangeProperty(_changed_variable_payload(name, value))
            return
        except Exception as exc:
            last_error = exc
            if logger:
                logger.log("ChangedProps failed for %s" % name)

    try:
        oDesign.ChangeProperty(_new_variable_payload(name, value))
        return
    except Exception as exc:
        last_error = exc
        if logger:
            logger.log("NewProps failed for %s" % name)

    try:
        oDesign.ChangeProperty(_changed_variable_payload(name, value))
        return
    except Exception as exc:
        last_error = exc
        if logger:
            logger.log("Fallback ChangedProps failed for %s" % name)

    if logger:
        logger.log("Could not set design variable %s = %s" % (name, value))
    raise last_error


def format_aedt_value(name, value):
    if isinstance(value, basestring):
        return value
    suffix_map = {
        "_mm": "mm",
        "_deg": "deg",
        "_arms": "A",
        "_a": "A",
        "_rpm": "rpm",
        "_hz": "Hz",
        "_s": "s",
        "_v": "V",
        "_t": "T"
    }
    for suffix, unit in suffix_map.items():
        if name.endswith(suffix):
            return "%s%s" % (_format_number(value), unit)
    return _format_number(value)


def _format_number(value):
    if isinstance(value, int):
        return "%d" % value
    return ("%.8f" % float(value)).rstrip("0").rstrip(".")


def apply_variables(oDesign, mapping, logger):
    keys = list(mapping.keys())
    for key in keys:
        formatted = format_aedt_value(key, mapping[key])
        logger.log("Setting design variable %s = %s" % (key, formatted))
        try:
            set_design_variable(oDesign, key, formatted, logger=logger)
        except Exception:
            logger.log("Variable write failed for %s = %s" % (key, formatted))
            logger.exception()
            raise RuntimeError("Failed to set design variable %s = %s" % (key, formatted))
    logger.log("Applied %d design variables" % len(keys))


def analyze_setup(oDesign, setup_name, logger):
    try:
        oDesign.Analyze(setup_name)
        logger.log("Analyze finished: %s" % setup_name)
    except Exception:
        logger.log("Analyze(setup) failed, falling back to AnalyzeAll")
        oDesign.AnalyzeAll()
        logger.log("AnalyzeAll finished")


def export_report_csv(oDesign, report_name, output_path, logger):
    ensure_dir(os.path.dirname(output_path))
    try:
        oModule = oDesign.GetModule("ReportSetup")
        oModule.ExportToFile(report_name, output_path)
        if os.path.isfile(output_path):
            logger.log("Exported report %s -> %s" % (report_name, output_path))
            return True
        logger.log("Report export returned without error but no file was created: %s" % output_path)
        return False
    except Exception:
        logger.log("Report export skipped or failed: %s" % report_name)
        return False


def numeric_series_from_csv(path):
    if not os.path.isfile(path):
        return []
    values = []
    handle = open(path, "r")
    try:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            numeric = []
            for part in parts:
                try:
                    numeric.append(float(part))
                except Exception:
                    pass
            if numeric:
                values.append(numeric[-1])
    finally:
        handle.close()
    return values


def waveform_stats(path):
    series = numeric_series_from_csv(path)
    if not series:
        return {}
    minimum = min(series)
    maximum = max(series)
    average = sum(series) / float(len(series))
    peak_to_peak = maximum - minimum
    rms = math.sqrt(sum([value * value for value in series]) / float(len(series)))
    return {
        "count": len(series),
        "min": minimum,
        "max": maximum,
        "avg": average,
        "p2p": peak_to_peak,
        "rms": rms,
        "abs_max": max(abs(minimum), abs(maximum))
    }


def save_project(oProject, logger):
    result = {
        "saved": False,
        "error": ""
    }
    try:
        oProject.Save()
        logger.log("Project saved")
        result["saved"] = True
    except Exception as exc:
        logger.log("Project save failed")
        logger.log(traceback.format_exc())
        result["error"] = str(exc)
    return result


def close_project(oDesktop, oProject, logger):
    try:
        project_name = oProject.GetName()
        oDesktop.CloseProject(project_name)
        logger.log("Closed project: %s" % project_name)
    except Exception:
        logger.log("Project close skipped")


def sort_rows_desc(rows, key_name):
    return sorted(rows, key=lambda row: float(row.get(key_name, 0.0)), reverse=True)
