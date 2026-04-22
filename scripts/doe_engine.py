from __future__ import print_function

import csv
import os

from aedt_native_common import read_csv_rows
from aedt_native_common import write_csv_rows


PRIMES = [0.6180339887, 0.7548776662, 0.5698402909, 0.4385796339, 0.3283715653]


def _round_value(spec, raw_value):
    value_type = spec["type"]
    if value_type == "int":
        return int(round(raw_value))
    decimals = spec.get("decimals", 6)
    return round(raw_value, decimals)


def _sample_value(spec, sample_index, dim_index):
    if spec["type"] == "discrete":
        choices = spec["values"]
        fraction = ((sample_index + 1) * PRIMES[dim_index % len(PRIMES)]) % 1.0
        idx = int(round(fraction * (len(choices) - 1)))
        return choices[idx]
    fraction = ((sample_index + 1) * PRIMES[dim_index % len(PRIMES)]) % 1.0
    raw = spec["min"] + fraction * (spec["max"] - spec["min"])
    return _round_value(spec, raw)


def baseline_case(search_cfg):
    row = {"case_id": "baseline"}
    for spec in search_cfg["variables"]:
        row[spec["name"]] = spec["baseline"]
    return row


def generate_cases(search_cfg):
    limit = int(search_cfg.get("screening_case_count", 24))
    rows = [baseline_case(search_cfg)]
    for sample_index in range(limit - 1):
        row = {"case_id": "screen_%03d" % (sample_index + 1)}
        dim_index = 0
        for spec in search_cfg["variables"]:
            row[spec["name"]] = _sample_value(spec, sample_index, dim_index)
            dim_index += 1
        rows.append(row)
    return rows


def load_or_generate_cases(search_cfg, csv_path):
    existing = read_csv_rows(csv_path)
    if existing:
        return existing
    rows = generate_cases(search_cfg)
    fieldnames = ["case_id"] + [spec["name"] for spec in search_cfg["variables"]]
    write_csv_rows(csv_path, rows, fieldnames)
    return rows


def write_validation_cases(csv_path, rows):
    if not rows:
        return
    fieldnames = ["case_id"] + [key for key in rows[0].keys() if key != "case_id"]
    write_csv_rows(csv_path, rows, fieldnames)
