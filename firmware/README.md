# Three-channel smart light switch firmware

ESP32-C3-MINI-1 / ESP-IDF **5.4.3**. Three normally-open relay channels; active-low momentary rocker contacts; secure BLE Wi-Fi provisioning; authenticated MQTT ON/OFF; one isolated MCP39F511A aggregate lighting meter. No dimming, per-channel energy allocation, physical relay feedback or OTA implementation.

The initial image boots all outputs OFF. Physical key sensing works without Wi-Fi, BLE or a broker. Energizing a relay additionally requires the default-OFF build gate and deliberate per-unit factory commissioning; network credentials never grant that release. Local OFF remains available on commissioned units without network service. A key held at boot must first be released. Factory data is intentionally absent from this repository. Missing network credentials disable remote operation; missing or mismatching meter calibration produces null readings.

## Build and host checks

Follow [LOCAL_BUILD.md](../LOCAL_BUILD.md) for the uv + PowerShell + MSVC workflow and pinned ESP-IDF 5.4.3 SDK. The SDK's cJSON compiles with the actual control, meter and command decoder sources. CTest checks commissioning, channel-local holds, maintenance/protection, offline local keys, strict uint64 JSON, replay, meter framing and 2,000 malformed inputs.

See [remediation-report.json](remediation-report.json) for the fresh Linux ESP32-C3
build and TLS remediation evidence. It includes target compile-negative controls
and separately labeled host certificate behavior tests. [build-report.json](build-report.json)
retains the earlier Windows build's original hashes and scope. Development images
and compiler logs are generated outside Git and included in the matching Release.
The build keeps actuation disabled. No board was flashed, calibrated, energized or
physically tested.

## Setup

1. Build the firmware and review [firmware documentation](../docs/firmware.md), the pin map and electronics design. Flash only a safely isolated low-voltage bench target. No live mains commissioning was performed for this deliverable.
2. Prepare a unique device identity, broker client certificate/key, broker CA and per-device BLE Security2 salt/verifier through the operator's approved manufacturing process. Reusable example secrets are not provided. The firmware never prints these values.
3. Store the supplied inputs using `tools/prepare_factory_csv.py` and the official ESP-IDF NVS generator, as documented below. Provision Wi-Fi with Espressif's official BLE provisioning client using Security2, the matching username and unique per-device password. BLE is used for provisioning; MQTT performs remote switching.
4. Configure broker topic ACLs for the device certificate identity. Read its current `state` message, then send a non-retained command with the current boot ID, a strictly increasing decimal sequence and a short boot-relative expiry. Use the acknowledgement to distinguish commanded, duplicate and rejected results. There is no physical-contact verification.
5. A qualified factory process must establish and verify meter calibration and the exact register profile before energy values become available. Firmware does not run automatic calibration or change meter EEPROM/configuration.

See [docs/firmware.md](../docs/firmware.md) for the protocol, factory partition format, calibration units, persistence limitations and official references.

Current Windows firmware/release validation is recorded in `../verification/current-firmware-validation.json`. `remediation-report.json` preserves the earlier Linux run; it is packaged only as historical evidence. See `../LOCAL_BUILD.md` for the source-bound `firmware` action and release checks.
