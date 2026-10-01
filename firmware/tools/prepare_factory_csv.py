#!/usr/bin/env python3
"""Validate user-supplied factory files and write an ESP-IDF NVS CSV locally.
Does not generate credentials, contact a service, flash, or copy private key contents.
"""
import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def prepare(spec_path: Path, output: Path) -> None:
    spec = json.loads(spec_path.read_text())
    device_id = spec.get("device_id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", device_id):
        raise ValueError("device_id must contain 1..32 ASCII letters, numbers, underscore or hyphen")
    uri = urlsplit(spec.get("mqtt_uri", ""))
    if uri.scheme != "mqtts" or not uri.hostname or uri.username or uri.password or uri.path or uri.query or uri.fragment or ":" in uri.hostname:
        raise ValueError("mqtt_uri must be mqtts://hostname[:port], without credentials or path")
    if uri.port is not None and not 1 <= uri.port <= 65535:
        raise ValueError("Invalid broker port")
    rows = [["key", "type", "encoding", "value"], ["switchcfg", "namespace", "", ""],
            ["device_id", "data", "string", device_id], ["mqtt_uri", "data", "string", spec["mqtt_uri"]]]
    for key, size, encoding in (("prov_salt", 16, "binary"), ("prov_verifier", 384, "binary"),
                                ("ca_pem", None, "string"), ("client_cert", None, "string"), ("client_key", None, "string")):
        path = (spec_path.parent / spec[key]).resolve()
        content = path.read_bytes()
        if size is not None and (len(content) != size or not any(content)):
            raise ValueError(f"{key}: incorrect length or empty credential")
        if size is None and (len(content) < 32 or len(content) >= 8192 or b"-----BEGIN " not in content or b"PLACEHOLDER" in content):
            raise ValueError(f"{key}: expected a supplied PEM file below 8192 bytes")
        rows.append([key, "file", encoding, str(path)])
    # Qualification is explicit per-unit data, never inferred from network credentials.
    for key in ("commissioned", "maintenance"):
        value = spec.get(key, False)
        if type(value) is not bool:
            raise ValueError(f"{key} must be boolean")
        rows.append([key, "data", "u8", str(int(value))])
    for key, default, minimum, maximum in (("protected_mask", 0, 0, 7), ("manual_hold_ms", 900000, 1, 3600000)):
        value = spec.get(key, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{key} outside supported range")
        rows.append([key, "data", "u8" if key == "protected_mask" else "u32", str(value)])
    calibration = spec.get("calibration")
    if calibration is not None:
        cal_id = calibration.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", cal_id):
            raise ValueError("Invalid calibration ID")
        path = (spec_path.parent / calibration["profile_file"]).resolve()
        profile = path.read_bytes()
        if len(profile) != 146:
            raise ValueError("meter_profile must contain exactly registers0x0050..0x00E1 (146 bytes)")
        sys = int.from_bytes(profile[0x94-0x50:0x98-0x50], "little")
        if not sys & 1 or sys & 0x178 or sys & 0xE000 != 0x8000:
            raise ValueError("Profile needs energy enabled, live ADCs and two-wire9600 UART")
        rows.extend([["cal_id", "data", "string", cal_id], ["meter_profile", "file", "binary", str(path)]])
        for key in ("voltage_uv", "current_ua", "power_mw", "energy_mwh"):
            value = calibration[key]
            if type(value) is not int or not 1 <= value <= 1000000:
                raise ValueError(f"{key} must be a verified integer scale1..1000000")
            rows.append([key, "data", "u32", str(value)])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", newline="") as f:
        csv.writer(f).writerows(rows)
    output.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.spec.resolve(), args.output.resolve())
    print("Factory CSV validated and written locally; no credentials generated or transmitted")


if __name__ == "__main__":
    main()
