# Smart light switch A: electronics candidate

**Unenergized engineering prototype. Do not install, connect to mains, or treat the Gerbers as a production release.** ERC/DRC and source consistency checks are digital design checks, not product safety, EMC, RF, thermal, LED-inrush, or accuracy certification.

## Scope and interfaces

- Proposed 220–240 V AC, 50 Hz supply **with neutral available in the switch box**; three independent normally-open relay channels
- Wi-Fi remote commands, BLE commissioning, and three local momentary buttons through ESP32-C3-MINI-1-N4X; no dimming
- J1 pins 1–5: **L input, N input, switched L1, switched L2, switched L3**. Lamp neutrals return directly to the supply; they do not need to traverse this switch
- The meter records aggregate lighting energy. It cannot attribute power or Wh to an individual channel, verify a welded relay, or prove a lamp is physically on
- Firmware reports commanded relay state separately from absent physical feedback; uncalibrated, stale, malformed or missing meter readings remain unavailable. See `docs/firmware.md`

## Native deliverables

`electronics/power.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, `.kicad_dru` and corresponding `control.*` are editable KiCad 10 sources. Symbols, footprints and library tables are local and portable. `manifest.json`, `bom.csv`, `pinmap.csv`, and `mechanical_interface.json` describe the same design. The BOM identifies selected major components; commodity passive purchasing substitutions still require voltage, tolerance, temperature, pulse and package review.

- Power PCB: 68 × 64 × 1.6 mm, four copper layers, two open side notches for insulating mounting-screw tubes
- Control PCB: 76 × 76 × 1.0 mm, four copper layers, Ø8.5 mm screw-tube clearances
- Fabrication candidate: `electronics/fabrication/{power,control}/`, including all four copper layers, masks, paste, board outline, Excellon PTH/NPTH drills and placement CSV
- Presentation assets, native schematic PDFs, native SVG plots and drill maps are exclusively under root `presentation/`

No power trace, component or module value is a finished-switch load rating. The **T2 A fuse is a selected protective component, not a certified 2 A product label**. Its time-current curve, prospective fault current, upstream branch protection and enclosure containment must be coordinated in physical qualification.

## Actual circuit

### 1. Protection and cold power

F1 is SCHURTER 3403.0277.23, a time-lag 2 A UMT-H part. RV1 is a thermally protected Littelfuse TMOV14RP275E across the **fused** supply. PS1 is RECOM RAC05-05SK/277, a 5 V/5 W supply selected for reinforced insulation and the manufacturer's OVC III application envelope. A certified component does not certify the assembled wall switch.

The cold 5 V rail supplies three relay coils and a TLV1117LV33DCYR regulator on the control board. The regulator has ceramic input/output capacitors and connected top/inner-layer copper for heat spreading. Wi-Fi peak current, isolated-converter startup, all-coils-on dissipation, brownout behavior and sealed-box temperature rise remain bench tests. No mains neutral is connected to the cold rail.

### 2. Three relay outputs

K1–K3 are Omron G5Q-1A DC5, normally-open contacts driven by AO3400A NMOS devices. Gate series resistors, independent 100 kΩ pull-downs and SS14 coil flyback diodes are implemented. Reset/boot/high-impedance GPIO states therefore bias coils OFF. GPIO0/1/3 control channels 1/2/3.

Generic G5Q contact ratings are not transferred into an LED-load claim. LED driver input capacitance can create severe inrush. Actual lamp types, repetitive make/break endurance, welded-contact faults, arc behavior and temperature rise must be qualified. There is no contact-feedback sensor or safety-disconnect function; the device cannot be used as an isolation switch for servicing.

### 3. Aggregate lighting meter

The current path is:

L_IN → F1 → **H_GND (fused live)** → R7 four-terminal 2 mΩ shunt → H_LOAD → the three relay common contacts → L1/L2/L3.

PS1 branches off before R7, so the intended measured quantity excludes the switch's own electronics consumption. **H_GND is dangerous live potential, not neutral, earth, or accessible digital ground.** Every `H_*` net belongs to that live-referenced meter domain. `C_*` nets belong to the isolated cold domain.

MCP39F511A current input I+ samples the load side of the shunt through 1 kΩ; I− samples its fused-live side through 1 kΩ. V+ receives neutral through four 249 kΩ resistors and a 1 kΩ lower resistor, giving 997:1 nominal attenuation. V− has a matching 1 kΩ return to H_GND. Each channel uses the documented 33 nF input filtering. The 2 mΩ shunt has true separate Kelvin sense pads. Analog decoupling, reference decoupling, RESET/MCLR pull-ups and the COMMONA-to-COMMONB link are present; unused mandatory-NC pins stay floating. The optional external crystal is not fitted; the internal oscillator must be accounted for by the verified factory profile.

For positive lamp consumption both input waveforms have matching negative polarity relative to fused live, yielding positive imported active power. At 2 A, nominal shunt signal is 4 mV RMS, not mains common mode applied to an ADC pin. Validate polarity with a known resistive load and then a nonlinear LED load. Calibration must verify the ADC gain and profile, voltage/current/power/energy scales, frequency, offset and temperature behavior. This design makes **no measured-accuracy claim** and does not rely on zero-calibration defaults.

### 4. Reinforced meter bridge

U3 is **ISOW7821DWER**, a two-direction digital isolator with integrated isolated power. Cold 3.3 V enters VCC/GND1. SEL is tied to hot GND2 for a 3.3 V isolated output. UART idle-high default is intentionally selected by the non-F device variant. The manufacturer's specified working insulation voltage is distinct from its short-duration withstand test; the selected part lists 1000 V RMS working insulation and >8 mm package clearance/creepage.

The local footprint follows the manufacturer's **HV/isolation pad option**, 9.75 mm row-center spacing and 1.65 mm pad length, leaving 8.1 mm between facing copper lands. Bulk input capacitance exceeds the isolated-side output capacitance by more than 100 µF. The hot and cold grounds are not joined, including through the harness, programming pads or inner layers.

### 5. Radio and local control

U1 is ESP32-C3-MINI-1-N4X. GPIO4/5/6 are active-low local buttons, each with external 10 kΩ pull-up and 10 nF capacitor. GPIO7 is isolated-meter UART RX; GPIO10 is TX. GPIO2/8/9 boot straps are not used to drive relays. EN has external pull-up and capacitor. Service pogo pads expose cold ground, 3.3 V, EN, BOOT, UART0 and native USB signals; no USB connector or mains-referenced debug port is exposed to the user.

The module uses the manufacturer's 53-pin land pattern, a top-edge antenna overhang, and an all-layer copper exclusion below the antenna area. The enclosure carrier is polymer. RF matching through the actual plastic/rocker stack, conducted/radiated coexistence, range, interference and regulatory testing remain unperformed. Do not infer radio performance from renderings.

### 6. Cold harness and assembly

J2 and J3 are keyed JST PH 8-way connectors with the same pin map:

1. C_5V
2. C_GND
3. C_3V3
4. C_RELAY1
5. C_RELAY2
6. C_RELAY3
7. C_UART_TX
8. C_UART_RX

J3 is on the control board's **bottom** face, with a local cold-side pocket through the solid partition. The mechanical file budgets the mated connector, not just the bare header. C15/C16 are on the power board rear face and have only 0.6 mm nominal rear-floor clearance; lead trimming, capacitor tolerances, board bow and assembly stack-up must be checked. The 17 major package envelopes in `mechanical_interface.json` are maximum or conservative bodies, not detailed vendor STEP models.

## Insulation assumptions and limits

The final mains spacing assumption is **220–240 V AC nominal, overvoltage category III, 4 kV rated impulse, pollution degree 2, altitude ≤2000 m, uncoated FR4**. The initial 2 mm routing screen was not a justified fixed-installation qualification and is superseded. Native custom rules now require **3 mm** between raw input line, the unattenuated neutral or a switched output and other hot copper that may sit at full mains differential. Hot-domain 3.3 V circuitry retains a 0.2 mm low-voltage rule; graded divider nodes and certified component internals are not blindly treated as independent full-mains conductors.

The whole hot-to-cold PCB copper target is **8 mm**. The router enforces it on the XY projection across every copper layer, and a separate conservative geometric checker covers pads, tracks, vias and otherwise unconnected isolator-side leads. This is stronger than only comparing same-layer copper. It does not assess 3D paths around relay bodies, solder contamination, creepage over supports, screws, wiring, enclosure seams, pollution, material CTI, fire containment or solid-insulation thickness. The final product standard and its applicable creepage/clearance rules still require qualified review. No conformal-coating credit is assumed.

The primary basis is TI's *Demystifying Clearance and Creepage Distance for High-Voltage End Equipment*, especially its IEC 60664-1 4 kV example and altitude treatment. Required creepage also depends on actual working voltage and material group; specify and verify laminate CTI rather than assuming every FR4 grade is equivalent.

## Verification and reproduction

Machine-readable evidence is in `electronics/verification/`:

- Both schematics: actual KiCad ERC output
- Both boards: actual KiCad DRC output, including unconnected-item lists
- `validation.json`: all native schematic nodes compared with PCB pad nets, separate by board, and eight-pin cold harness agreement
- `isolation_xy.json`: independent all-layer conservative hot/cold geometry check
- `load_paths.json`: native connectivity of all eight main lamp-current paths after removing every trace narrower than 1.2 mm and every via smaller than 1.6 mm. The fuse-to-shunt path is an explicit current trunk; narrow hot-reference branches do not carry the intended lamp current. This is no temperature-rise, surge or load-rating validation
- `presentation.json`: SHA-256 of native files used for unchanged-source SVG/PNG generation

Follow [LOCAL_BUILD.md](../LOCAL_BUILD.md) and run the PowerShell electronics stage. It checks authoritative native sources and writes all exports to an explicit external build tree. One-time circuit-generation/autorouting scripts were retired to Git history. The report filenames listed above exist in that generated tree or Release bundle. No hardware is energized.

### Manufacturing candidate notes

Suggested stack-ups (fabricator must approve dielectric construction and tolerances):

- Power 1.60 mm: F.Cu 70 µm / prepreg 0.20 mm / In1 35 µm / core 0.99 mm / In2 35 µm / prepreg 0.20 mm / B.Cu 70 µm
- Control 1.00 mm: F.Cu 35 µm / prepreg 0.18 mm / In1 18 µm / core 0.534 mm / In2 18 µm / prepreg 0.18 mm / B.Cu 35 µm
- Fine-pitch meter escape uses 0.13 mm tracks and 0.45/0.20 mm via diameter/drill. Ordinary routing is wider. Main candidate current routes use 1.2 mm tracks and, where needed, 1.6/0.8 mm vias; these dimensions do not establish a load rating
- Relay and terminal PTH lands are 2.0 mm on 1.3 mm drills; verify the 0.35 mm nominal annulus against hole and registration tolerances
- Copper masks and inner-layer clearances must survive fabricator CAM review. The board outlines include open power-board mounting notches; do not substitute plated mounting holes
- No soldermask, coating, component approval or fuse value is a substitute for complete end-product qualification

## Primary references

- [Microchip MCP39F511A datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP39F511A-Data-Sheet-20006044A.pdf), pin table, application circuit, protocol and calibration
- [Microchip ADM00667 reference board](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/UserGuides/MCP39F511A-Demo-Board-User-Guide-50002770A.pdf)
- [TI ISOW7821 datasheet](https://www.ti.com/lit/ds/symlink/isow7821.pdf), insulation table, HV land pattern and input bulk capacitance guidance
- [RECOM RAC05-K/277 datasheet](https://recom-power.com/pdf/Powerline_AC-DC/RAC05-K_277.pdf)
- [Omron G5Q datasheet](https://components.omron.com/sites/default/files/datasheet_pdf/J155-E1.pdf)
- [Espressif ESP32-C3-MINI-1 datasheet](https://documentation.espressif.com/esp32-c3-mini-1_datasheet_en.pdf)
- [Vishay WSK2512 datasheet](https://www.vishay.com/docs/30108/wsk2512.pdf)
- [SCHURTER UMT-H datasheet](https://www.schurter.com/en/datasheet/typ_UMT-H.pdf)
- [Littelfuse TMOV datasheet](https://www.littelfuse.com/assetdocs/varistors-tmov-datasheet?assetguid=bd475732-1071-4352-b8aa-f78b0007eb05)
- [TI TLV1117LV datasheet](https://www.ti.com/lit/ds/symlink/tlv1117lv.pdf)
- [Omron B3U datasheet](https://components.omron.com/us-en/system/files/2023-01/datasheet_pdf/A162-E1.pdf)
- [TI clearance and creepage design seminar](https://www.ti.com/lit/ml/slup419/slup419.pdf)
