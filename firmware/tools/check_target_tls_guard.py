"""Compile-only negative controls using a completed ESP-IDF target build.

Recompiles the actual network.c command into temporary objects with an isolated
sdkconfig.h overlay. Does not edit the build/source configuration, link an unsafe
image, execute target code, perform a TLS handshake or access hardware.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def split_command(command):
    if os.name != "nt":
        return shlex.split(command)
    # CMake emits Windows command-line quoting, not POSIX shell quoting.
    import ctypes
    from ctypes import wintypes
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    argv = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not argv:
        raise OSError(ctypes.get_last_error(), "Cannot parse CMake compiler command")
    try:
        return [argv[i] for i in range(count.value)]
    finally:
        kernel = ctypes.WinDLL("kernel32")
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(argv)


def check(build: Path) -> list[dict]:
    build = build.resolve(strict=True)
    commands = json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))
    source = Path(__file__).resolve().parents[1] / "main/network.c"
    matches = [entry for entry in commands if Path(entry["file"]).resolve() == source]
    if len(matches) != 1:
        raise ValueError("Expected exactly one actual Switch network.c compilation entry")
    entry = matches[0]
    command = entry.get("arguments") or split_command(entry["command"])
    config = build / "config/sdkconfig.h"
    if not config.is_file() or "-c" not in command or "-o" not in command:
        raise ValueError("Incomplete ESP-IDF compile database/configuration")
    result = []
    with tempfile.TemporaryDirectory(prefix="switch-target-tls-") as temp:
        overlay = Path(temp)
        for name, suffix, should_pass in [
            ("generated_config", "", True),
            ("date_disabled", "#undef CONFIG_MBEDTLS_HAVE_TIME_DATE\n", False),
            ("time_disabled", "#undef CONFIG_MBEDTLS_HAVE_TIME\n", False),
            ("insecure_enabled", "#define CONFIG_ESP_TLS_INSECURE 1\n", False),
        ]:
            (overlay / "sdkconfig.h").write_text(f'#include "{config.as_posix()}"\n' + suffix)
            args = list(command)
            args[args.index("-o") + 1] = str(overlay / f"{name}.o")
            # Keep dependency files external too, including generators that put
            # -MF in compile_commands.json. Insert after optional compiler wrappers.
            if "-MF" in args:
                args[args.index("-MF") + 1] = str(overlay / f"{name}.d")
            first_option = next(i for i, arg in enumerate(args) if arg.startswith("-"))
            args.insert(first_option, "-I" + str(overlay))
            process = subprocess.run(args, cwd=entry["directory"], capture_output=True, text=True)
            if (process.returncode == 0) != should_pass:
                raise ValueError(f"Unexpected target compile result ({name}):\n{process.stdout}\n{process.stderr}")
            if not should_pass and "Switch TLS" not in process.stderr:
                raise ValueError(f"Target negative control failed for an unrelated reason ({name}):\n{process.stderr}")
            result.append({"case": name, "expected_compile_success": should_pass,
                           "returncode": process.returncode, "passed": True})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        content = json.dumps({"scope": "actual_target_network_compile_only", "hardware_tested": False,
                              "tls_handshake_tested": False, "checks": check(args.build)}, indent=2) + "\n"
        if args.report:
            args.report.write_text(content, encoding="utf-8")
        print(content, end="")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
