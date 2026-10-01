# CARBENTRA Smart Switch maintenance

- Current design has three ON/OFF channels, Wi-Fi/BLE and aggregate energy metering. No independent lamp/contact feedback, per-channel meter or dimming claim.
- Preserve local control during network loss, boot default OFF, manual holds and authenticated provisioning. A device ACK is not independent contact verification. Development firmware disables physical actuation until commissioning.
- Native KiCad is the electrical authority. Parameterized mechanical source and native Blender scenes describe the same PCB/relay/PSU/module stack and proposed dimensions.
- Keep mains isolation, protection, creepage/clearance, contact and inrush assumptions explicit. No live mains operations or safety-certification/load-rating/energy-accuracy/production-ready claims from builds or DRC.
- Coordinate capabilities, Wh units and wire semantics with the platform packages/iot-contract and maintained Edge. Keep one implementation; retire replaced scripts/outputs to Git history.
- Use PowerShell 7, a project uv .venv and installed KiCad/Blender/ESP-IDF. Native Python bindings run in their owning tool's isolated process. Short-lived environments/downloads/logs use task-specific external temporary directories. Coordinate GPU work.
- Validate host safety logic, actual firmware, native ECAD/manufacturing export and assembly. Editable presentation source belongs in presentation/; generated media belongs in external build directories or releases.
- Apply LICENSES.md and upstream notices. Use the current README for maintained commands and physical verification limits.
