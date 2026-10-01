# Build and binary component notices

The target is built against ESP-IDF v5.4.3 commit ea1c174c1cbb7348bd8ba0ff1eb306246938dd80. The SDK and recursive submodules remain external tool installations. The exact SDK source is available at https://github.com/espressif/esp-idf/tree/ea1c174c1cbb7348bd8ba0ff1eb306246938dd80 . Preserve the SDK's component licenses when rebuilding or redistributing an image.

Bundled license texts in licenses/ cover ESP-IDF (Apache-2.0), cJSON (MIT), Mbed TLS (Apache-2.0), Apache NimBLE with NOTICE, TinyCrypt (BSD), lwIP (BSD), FreeRTOS (MIT), and the individual Newlib runtime notices. The Espressif Wi-Fi, PHY, coexistence and ESP32-C3 Bluetooth library licenses are copied verbatim from the pinned SDK; those libraries are not project-owned source.

Compiler runtime portions remain covered by their own notices and the GCC Runtime Library Exception. This ledger records the principal directly used components, not a formal exhaustive licensing audit. SDK subcomponents retain their SPDX headers and original source notices. Project-level licenses do not replace them.

Development firmware has relay actuation disabled. No private key, client certificate, Security2 secret, calibration record or per-unit commissioning record is included. Public synthetic test fixtures must not be used as production credentials.
