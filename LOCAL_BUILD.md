# Windows local build

The supported local workflow is PowerShell 7, uv-managed Python 3.12, MSVC 2022, KiCad 10.0.5 (including its own pcbnew Python), Blender 5.2.2 LTS, Inkscape 1.4.4, FFmpeg, CMake and Ninja. Blender and KiCad retain their own embedded interpreters; they are not installed into the general Python environment.

```powershell
uv venv --python 3.12
uv sync --frozen
$env:KICAD_BIN = 'D:\Dev\KiCad\10.0\bin'
$env:BLENDER_EXE = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$env:INKSCAPE_BIN = 'D:\Dev\Inkscape-1.4.4\inkscape\bin'
$build = 'D:\Temp\codex\carbentra-local-build'
```

Paths above are examples of the verified workstation. Set each variable to your own installed tool. CMake, Ninja and FFmpeg must be callable; `INKSCAPE_BIN` is added to PATH by the coordinator. The project never installs CAD Python packages into its venv. `dev.ps1` loads the installed MSVC developer shell for host checks.

## ESP32-C3 target

Install official [ESP-IDF 5.4.3](https://github.com/espressif/esp-idf/tree/v5.4.3), including recursive submodules, at the exact commit in `firmware/dependencies.lock.json`. Use official `tools/idf_tools.py install --targets esp32c3` for matching Windows tools. The SDK needs a separate Python 3.12 environment: create it with `uv venv <IDF_PYTHON_ENV_PATH>` **before** installing the SDK's official `requirements.core.txt` under its official v5.4 constraints. Preserve SDK metadata and check `idf_tools.py check-python-dependencies`. Do not put SDK packages into the project's CAD/report venv.

```powershell
$env:IDF_PATH = 'D:\Dev\esp-idf-v5.4.3'
$env:IDF_TOOLS_PATH = 'D:\Dev\esp-tools-v5.4.3'
$env:IDF_PYTHON_ENV_PATH = 'D:\Dev\esp-tools-v5.4.3\python_env\idf5.4_py3.12_env'
```

The coordinator uses the SDK's official tool-path export and builds an external copy of `sdkconfig`. It refuses an unpinned SDK. The resulting image has `CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION` disabled; no credentials or commissioning records are generated.

## Run

```powershell
.\scripts\dev.ps1 -Action all -BuildRoot $build
.\scripts\dev.ps1 -Action render -BuildRoot $build
```

`all` runs native C host tests, a real MCU target build, strict ERC/DRC and native schematic/PCB connectivity checks, manufacturing exports, parametric mechanical rebuild, exported-file reopening and geometric checks. `render` separately regenerates geometry and presentation media, with OptiX then CUDA preferred when supported and CPU fallback. Run GPU render jobs sequentially on an 8 GB device.

Each invocation prints `VALIDATED_OUTPUT` and creates an independent timestamped directory with `validation.json`. Outputs, temporary files and child-process TEMP/TMP stay under the explicit external build root. The source checkout is not overwritten. To run one stage, use `host`, `target`, `electronics` or `mechanical`.

Native KiCad files are the circuit source of truth. The reproducible boundary is **native circuit → strict checks → fabrication/presentation exports**, not re-running an old autorouter to recover identical routing. One-time ECO and placement/autorouting tools were retired into Git history. Blender parameter scripts recreate the engineering model; saved `.blend` files remain editable reference sources. Geometric checks do not establish production tolerances.

The current Windows host run uses MSVC strict warnings and CTest; it does not claim UBSan or LeakSanitizer coverage. Source history contains earlier Linux sanitizer runs, which are not substituted for current evidence. Nothing here flashes hardware, provisions keys or actuates a load. Compact current evidence is in `verification/local-validation.json`; binary/media bundles belong in GitHub Releases. Delete your external build directory after preserving results you need.

## Host CI without CAD or target SDKs

The Windows GitHub Actions workflow pins uv 0.11.17 and Python 3.12, creates the venv before dependency installation, and runs the same PowerShell host entry. It installs no KiCad, Blender, Zephyr or ESP-IDF toolchain. Local verification of this path passed; a GitHub run is a separate result.

For Switch, set CJSON_ROOT to a standalone checkout at the exact sdk_submodules.cJSON commit in firmware/dependencies.lock.json. The coordinator verifies the commit before compiling. If that variable is absent, the existing IDF_PATH/components/json/cJSON source is used. CI fetches only this small upstream dependency and does not alter the pin.

CTest additionally runs `firmware/tests/check_tls_config.py`, which checks both
maintained TLS date configurations and compiles the actual `tls_policy.h` against
positive/negative host fixtures. The target coordinator checks its generated
sdkconfig after building; the real network translation unit includes the guard.

The independent certificate behavior test is a separate host-library gate. With
a development mbedTLS installation and Python `cryptography`, compile
`firmware/tests/test_certificate_policy.c` against that installation's `mbedx509`
and `mbedcrypto` libraries, then run:

```sh
python firmware/tests/check_certificate_policy.py --verifier /external-build/switch_certificate_policy
```

The binary argument is mandatory and missing binaries are errors, not skips.
This checks valid/expired/future/wrong-CA/wrong-hostname certificates using that
host library. Record its version. It does not replace a pinned ESP-IDF target
build or MQTT handshake tests on the ESP32-C3.

On POSIX hosts, target builds additionally run `firmware/tools/check_target_tls_guard.py`
against the generated compilation database. It recompiles the actual `network.c`
with its real ESP32-C3 compiler/SDK headers, checks the successful generated config,
and requires compilation to fail when time/date checks are disabled or insecure
TLS is enabled in a temporary header overlay. It writes only external temporary
objects and `target-tls-guard.json`; it never links or flashes an unsafe image.
This is target **compile** evidence, not certificate-handshake execution evidence.

## Source byte identity

The checked-in .gitattributes keeps native KiCad/JSON bytes unchanged and checks ordinary code out with LF on every platform. verification/source-manifest.json hashes the published source bytes; those hashes are checked against Git blobs, not only one Windows working tree. The complete build was rerun after text normalization. Earlier render-execution hashes are explicitly historical working-tree hashes; CAD bytes and geometric inputs did not change, so media was not rerendered solely for newline conversion.

Current source byte inventory is checked with `python scripts/source_manifest.py`.
After intentional source changes and completed relevant tests, refresh it using
`python scripts/source_manifest.py --write`. This records exact checkout bytes; it
does not rerun or renew the historical Windows/CAD/media qualification reports.
The current firmware-only evidence is `firmware/remediation-report.json`.
