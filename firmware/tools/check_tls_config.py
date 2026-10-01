"""Reject unsafe maintained/generated ESP-IDF config; does not run a TLS stack."""
from __future__ import annotations

import argparse
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parents[1]
REQUIRED = ("CONFIG_MBEDTLS_HAVE_TIME", "CONFIG_MBEDTLS_HAVE_TIME_DATE")


def check(path: Path) -> None:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            key, value = line[2:-11], "n"
        else:
            continue
        if key in values:
            raise ValueError(f"{path}: duplicate config option {key}")
        values[key] = value
    for key in REQUIRED:
        if values.get(key) != "y":
            raise ValueError(f"{path}: {key}=y is required")
    if values.get("CONFIG_ESP_TLS_INSECURE") == "y":
        raise ValueError(f"{path}: insecure TLS verification is forbidden")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configs", nargs="*", type=Path)
    args = parser.parse_args()
    try:
        for path in args.configs or [FIRMWARE / "sdkconfig.defaults", FIRMWARE / "sdkconfig"]:
            check(path)
            print(f"PASS TLS date configuration: {path}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
