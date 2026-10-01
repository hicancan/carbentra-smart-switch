# Firmware and remote-control contract

## Implemented scope

Three independent lighting ON/OFF channels use normally-open relay drives. Three active-low, momentary local contacts toggle their corresponding commanded state after35ms of stable debounce. The contact must be released before its first accepted press after reboot. Maintained/latching rocker contacts need a different local-control policy and are not assumed by this implementation. Offline switching does not depend on network initialization. Reset starts all outputs OFF; no previous ON state is restored.

Wi-Fi carries authenticated MQTT control and state. BLE provides Espressif's official Wi-Fi provisioning service using Security2 (SRP6a and AES-GCM), with per-unit salt/verifier loaded from factory NVS. Security0/1 are disabled; no plaintext provisioning fallback or shared password is compiled in. BLE stops after successful provisioning. Changing provisioned Wi-Fi requires a deliberate service operation on the Wi-Fi NVS partition; the command protocol has no remote credential-reset or factory-reset operation.

The three logical switch channels share one aggregate meter covering the sum of their lighting loads. Future campus integration must register three controllable channels plus one parent aggregate energy boundary, without fabricating per-channel energy or counting the aggregate three times. The shared campus Edge adapter maps physical channel IDs lighting-1..3 to canonical relay.1..3 and preserves the single aggregate energy boundary.

## Cold-domain GPIO contract

| Function | ESP32-C3 GPIO | Electrical interpretation |
| --- | ---: | --- |
| Relay1 / Relay2 / Relay3 | 0 / 1 / 3 | Active-high NMOS drives, external100k pulldowns |
| Key1 / Key2 / Key3 | 4 / 5 / 6 | Active-low, external10k pullups and10nF |
| Meter UART RX / TX | 7 / 10 | UART1,9600baud,8N1, isolated channel |
| Reserved boot straps | 2 / 8 / 9 | No application output use |
| USB | 18 / 19 | Reserved |
| Service UART0 | 20 / 21 | Console; firmware does not log secrets |

GPIO latch levels are cleared before enabling output direction. External pulldowns cover reset/boot-ROM intervals. Software state and an electrical GPIO request do not prove relay-contact closure, load current or lamp illumination. Acknowledgements explicitly have `physical_verification:false`; per-channel state has `physically_verified_on:null`.

The MCP39F511A and its analog input circuit are in the hot mains domain. UART crosses the TI ISOW7821 isolation boundary; its isolated supply powers the meter side. The cold controller has no isolation-readiness GPIO and cannot certify insulation, creepage, clearance, relay inrush suitability or safe mains conditions. Calibration/readback only addresses measurement configuration. Firmware is not a substitute for the electronics safety review or physical commissioning.

## MQTT wire protocol

All connections use `mqtts://hostname[:port]`, a supplied CA trust anchor, server-hostname validation and a supplied client certificate/private key. Firmware rejects insecure MQTT URIs and never enables skip-CN checks. Broker ACLs must bind the client identity to its own namespace; authenticated controller clients may publish only to the intended device command topics. SNTP establishes usable wall time for certificate checks before MQTT starts. Command freshness uses a boot-relative clock and does not trust an arbitrary controller wall clock.

Topics:

- `carbentra/switch/<device_id>/command`: controller→device, QoS1, **not retained**
- `carbentra/switch/<device_id>/ack`: device→controller, QoS1, not retained
- `carbentra/switch/<device_id>/state`: device→controller, latest retained snapshot every2s while connected
- `carbentra/switch/<device_id>/availability`: retained online/offline, MQTT last will

A command is an object with exactly these six properties. The example values are illustrative protocol data, not executable commissioning instructions:

```json
{"id":"request-42","boot_id":"0123456789abcdef0123456789abcdef","seq":"42","channel":2,"on":true,"expires_uptime_ms":"125000"}
```

`boot_id` must equal the current state message's32-hex-character boot ID. Firmware obtains fresh128-bit random data from the SDK's explicitly enabled boot-time entropy source before Wi-Fi starts. `seq` and `expires_uptime_ms` are unsigned decimal strings, avoiding JSON double precision loss. Channel is the integer1,2 or3; on is an actual boolean. ID accepts1..48 ASCII alphanumerics, hyphens and underscores. Maximum payload768bytes. Unexpected/duplicate fields, embedded NUL, malformed fragments, invalid types, retained commands and oversized payloads cannot actuate a relay.

Expiry must be strictly after current uptime and at most30s ahead. Controllers should obtain fresh uptime from state and allow transport latency. Sequences increase globally per device boot; coordinate multiple controller clients through one sequence allocator. The last16 accepted command IDs are cached. An identical retry returns `duplicate` without reapplying the output, even if a local key subsequently changed it. Reusing an ID with different content returns `id_conflict`. An evicted old sequence is still rejected. New boot IDs invalidate commands from earlier sessions; the first command in a boot can start at sequence1. No acknowledgement claims measured physical success.

Example acknowledgement fields are device_id, boot_id, id, seq, channel, result, uptime_ms and physical_verification:false. Results are commanded, duplicate, invalid_command, wrong_boot, expired, stale_sequence or id_conflict. A malformed request without a valid ID may receive an invalid_command acknowledgement without id/seq/channel. Rejected retained/oversized/wrong-topic input is discarded. The next state snapshot reports all three current commanded states.

## Meter parsing and calibration

The driver implements MCP39F511A SSI requests:0xA5 header, complete-frame byte count, big-endian address pointer,0x4E register read, and modulo256 sum checksum. A read response must have0x06 ACK, exact count, complete payload and valid checksum. Register data is little-endian. Read blocks never exceed32data bytes.0x15 NAK,0x51 checksum failure, bad lengths, truncation and timeouts cannot become valid samples. The documented unframed0x5A identification probe must return0x15,0x04 before the factory profile is trusted.

Measurement reads cover0x0002..0x001D and import/export active counters0x001E..0x002D. Active power direction comes from System Status SIGN_PA, rather than treating the unsigned magnitude as signed. There is no per-channel energy estimate. UART is polled about once per second; values become unavailable after failure or a5s freshness limit.

A factory calibration record contains an immutable per-unit calibration ID, verified output-unit scales and exactly146bytes from registers0x0050..0x00E1. Firmware compares the full snapshot at startup and every60s, and requires AC mode, live ADCs, energy accumulation enabled, two-wire operation and9600baud. A mismatch, missing record or wrong device identity yields null physical values. The record must be captured after the qualified process has set the correct current polarity,50Hz calibration/reference and gain/range values, saved them and verified readback. The final electronics reference uses a Vishay WSK25122L000FEA2mΩ four-terminal shunt,997:1 voltage divider and the internal4MHz oscillator. Current and voltage input polarities are both negative for positive import in the selected topology, so their product must be verified positive by the fixture. The PSU branch precedes the shunt and is excluded from aggregate lighting energy. These analog values are not hardcoded as unverified firmware conversion constants. Factory default values or the datasheet's nominal resolution are not a calibration result.

Scale fields are positive integer microvolts per voltage count, microamps per current count, milliwatts per active-power count and milliwatt-hours per energy count. Their accepted range is1..1,000,000. The datasheet describes a default1mWh energy step; the actual record must confirm the configured system. The firmware performs no calibration/configuration writes or energy-counter EEPROM writes. No accuracy percentage or regulatory energy-billing suitability is claimed.

## Persistent energy semantics

The firmware adds only observed, monotonic import-counter deltas with known scale. It does not integrate estimated power or invent energy across reboot, lost communication, counter rollback or rejected jumps. The first sample after each such interruption establishes a new baseline. An internal50kW plausibility ceiling rejects corrupted jumps; it is not a hardware load or relay rating.

Known energy is checkpointed in a separate `energy` NVS partition every60s using a versioned binary format, profile fingerprint and CRC32. After an unexpected power loss, up to60s of newly accumulated known energy can be absent from the saved lower bound, in addition to unknown boot/gap intervals. Telemetry labels it `energy_quality:"partial_lower_bound"`, includes unknown_intervals and checkpoint_interval_seconds, and represents exact known_energy_wh as a decimal string. Missing calibration/storage integrity yields null. A valid measured zero is allowed only within this qualified known-energy context.

A corrupt checkpoint or changed calibration fingerprint is not silently erased or assigned to a new meter. Energy accumulation is disabled pending a deliberate service workflow that archives prior records and provisions a new energy epoch. NVS initialization failures do not erase data automatically. Storage failures are exposed by persistent_storage_ok:false. The flash endurance/checkpoint interval must be validated for the physical product's required service life.

## Factory data and setup

The custom4MiB partition table allocates Wi-Fi NVS, a read-only-by-application `factory` NVS partition, a2.5MiB app slot, and separate energy NVS. It has no OTA partition. Credentials are absent from the source tree. The factory namespace is `switchcfg` (9characters); energy namespace is `energy`.

Prepare a private JSON specification outside Git with device_id, mqtt_uri and paths to prov_salt (16binary bytes), prov_verifier (384binary bytes), ca_pem, client_cert and client_key. Use unique SRP credentials and a unique broker client identity for every device. Espressif's official `tools/esp_prov/esp_prov.py` supports Security2 credential generation through an operator-controlled manufacturing process; this deliverable did not generate or provision credentials. Do not place passwords in shell history or logs.

Optional `calibration` contains id, profile_file and voltage_uv/current_ua/power_mw/energy_mwh. Omit it for uncalibrated logic bring-up; physical values will remain null. The preparation helper validates file lengths and profile fields, then emits a private CSV containing file references. It does not generate secrets, flash, connect or transmit.

```sh
python firmware/tools/prepare_factory_csv.py /private/unit-spec.json /private/unit-factory.csv
python "$IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py" generate \
  /private/unit-factory.csv /private/unit-factory.bin 0x10000
```

The factory binary must be installed at its explicit partition offset0x10000 by an authorized technician, together with the ordinary SDK build outputs. An ordinary `idf.py flash` does not supply factory credentials. Use official Espressif provisioning clients with Security2 and the matching username/password supplied separately to the owner; no credential-bearing QR is emitted to logs. Broker ACLs and certificate issuance belong to the operator, not this repository.

The default bench build does not burn security eFuses, enable irreversible Secure Boot, or provision flash-encryption keys. Factory credentials are therefore physically readable unless a product-specific encrypted-NVS/flash-encryption and debug-access policy is provisioned. Network transport/authentication is implemented; physical extraction resistance is not claimed by this default build. Deploying that security policy requires the appropriate authorized manufacturing procedure.

## Verification and remaining physical work

Host regression groups compile the real C core and cJSON decoder with strict warnings and CTest on Windows. They cover offline keys/held-key boot, debounce, all channel bounds, maximum64-bit sequence and overflow, replay/idempotency/conflicts, old-boot rejection, expiry, official meter request bytes, little-endian decoding, checksum/length errors, import/export sign, missing intervals, monotonic delta handling, checkpoint corruption/profile mismatch, strict JSON and2,000 malformed-input cases. Current Windows evidence does not claim UBSan or LeakSanitizer. Earlier Linux sanitizer results remain historical.

Target build status is recorded in firmware/build-report.json when compilation completes. No ESP32 board, relay, lamp, radio link, broker deployment, live credentials or mains meter was exercised here. Hardware UART timing, polarity, real calibration, RF coexistence, power-loss behavior, contact/inrush performance and physical safety remain bench/engineering validation tasks. Generated images and presentation assets are owned by the root presentation workflow, not firmware.

## Primary references

- [ESP-IDF5.4.3 ESP32-C3 documentation](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32c3/index.html)
- [ESP-IDF5.4.3 provisioning example/source](https://github.com/espressif/esp-idf/tree/v5.4.3/examples/provisioning/wifi_prov_mgr)
- [ESP-IDF5.4.3 MQTT client](https://docs.espressif.com/projects/esp-idf/en/v5.4.3/esp32c3/api-reference/protocols/mqtt.html)
- [MCP39F511A datasheet DS20006044A](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MCP39F511A-Data-Sheet-20006044A.pdf), sections4,5.6,6and9
- [MCP39F511A demonstration-board user guide](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/UserGuides/MCP39F511A-Demo-Board-User-Guide-50002770A.pdf)


## Classroom control upgrade (2026-10-01)

The six-property command remains unchanged. A genuine debounced local key press records its channel, event sequence, uptime and result, and establishes a channel-local manual hold (default 900,000 ms; factory bounds 1..3,600,000 ms). Commands to another channel are independent. Remote ON and OFF are rejected during manual hold, maintenance or a protected channel policy. No remote override flag is accepted. Hold expiry permits future commands but does not itself switch a relay. Exact accepted retries still return duplicate without replaying the action.

Protected channels reject automation while retaining physical local control. Maintenance blocks energizing and forces all commanded states OFF. A GPIO write error latches a software fault and requests all outputs OFF; this does not prove mains disconnection. No electronic overcurrent/overtemperature protection or independent feedback sensor has been invented. Physical protection and qualification remain separate release requirements.

CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION defaults OFF. The application also requires explicit per-unit factory commissioned=true before any local or remote ON. Factory values maintenance, protected_mask (bits0..2) and manual_hold_ms are read once at boot; missing values use safe defaults. Merely supplying BLE/MQTT credentials, calibration data or compiling this source does not commission hardware. No release build enabling actuation is produced here.

State adds schema_version=1, device_type=smart_switch and sample_seq (monotonic uint64 decimal string, distinct from last_seq command replay counter). Each state publication gets a sequence; boot_id separates restarts. Each channel carries channel_id lighting-1..3, control_mode auto/manual/maintenance/protected, manual_hold_until_uptime_ms, commanded_on, and physically_verified_on=null with feedback_quality=unavailable_no_independent_sensor. Root fields include actuation_enabled, fault_latched, maintenance, protected_channel_mask and last_local_input {channel,event_seq,uptime_ms,pressed,result}. Event sequence 0 means no press observed. A periodic snapshot does not turn a retained local-input record into a new event; consumers deduplicate by boot_id/event_seq.

Additional rejection results: manual_hold, maintenance, protected, not_commissioned, fault_latched. Aggregate energy remains a partial lower bound and must not be allocated to individual channels.
