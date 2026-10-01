# SW3 proposed mechanical assembly

This is an independent engineering concept based on the supplied white, rounded three-rocker reference images. No exact manufacturer or model was reliably established. **86 × 86 mm and all housing dimensions are proposed, not manufacturer facts.** The design has no copied logo or certification markings.

## Files

- `carbentra_smart_switch.blend`: neutral, assembled metric source; front is +Z, wall/mounting rear datum Z=0
- `carbentra_smart_switch_animation.blend`: the same real subassemblies with 144 baked frames, 24 fps
- `exports/carbentra_smart_switch.glb`: portable assembly, physical meters
- `exports/*_mm.stl`: structural concept pieces, explicitly millimeter-scaled; not tooling-release files
- `source/build_switch.py` and `source/internal_layout.py`: editable parametric source; component bodies read `electronics/mechanical_interface.json`
- `verification/`: only the minimum file-open, dimensions, gross fit and media checks
- **All images, six views, annotated assembly sheets, SVG/PDF drawings and video are in root `presentation/`**

## Proposed envelope and stack

| Feature | Nominal mm |
|---|---:|
| Face envelope | 86 × 86 |
| Front projection from wall datum | 9.8 |
| Backbox outer envelope | 74 × 70 × 34 |
| Total depth | 43.8 |
| Backbox clear planar cavity | 70 × 66 |
| Main power PCB | 68 × 64 × 1.6, Z -25.6 to -24 |
| Insulating protective partition | Z 0 to +1.8 |
| Isolated control PCB | 76 × 76 × 1, Z +3.2 to +4.2 |
| Momentary rocker main underside / front | Z +7.2 / +9.8 |
| Installer mounting screw centers | X ±30, Y 0; 60 separation |

Suggested initial installation cavity is at least 76 × 72 × 45 mm, but this is **not a compatibility guarantee**. The actual wall box, screw spacing, cable entry and wire bending space must be measured. Do not assume every nominal 86-format wall box accepts this assembly.

The Omron B3U-1000P local switches reach Z +5.8. Molded rocker pushers project 1.4 mm below the main rocker underside; the intended approximately 0.2 mm operating travel still needs button-force and tolerance development.

The real package plan contains three Omron G5Q-1A DC5 relays, RECOM RAC05-05SK/277 isolated supply, MCP39F511A aggregate meter, ISOW7821 isolated interface and ESP32-C3-MINI-1 on the separate cold control PCB. Body envelopes and board coordinates come from the electronics-owned contract, not invented internal parts of the photographed product. Package cosmetic details are simplified; no manufacturer STEP fidelity is claimed.

## Isolation and radio constraints

- Accessible momentary controls are on the isolated cold PCB. A separate insulating partition closes the primary compartment. J3 is on the back of the control board in a modeled isolated-cold protective pocket; both PH8 connectors reserve 10 mm mated height. Eight wires pass sealed individual holes in the pocket floor; the qualified seal/material and harness implementation remain to be developed. The pocket floor top is Z -8.8 and outer bottom Z -10.8. Cable shapes illustrate occupied volume only; the required 5 mm bend radius is not digitally certified
- The installer screws pass through modeled polymer tubes (8 mm OD / 5.5 mm bore), with main PCB side notches and cold PCB clearance holes. Those tubes are a geometry concept, **not proof of reinforced insulation**. Polymer grade, minimum molded wall, tracking resistance, dielectric strength, creepage, clearances and accessible-metal isolation remain safety-review items
- Power board primary/secondary copper zoning, isolation components, fusing, surge protection and electrical slot geometry are owned by the ECAD design. Do not treat the illustration as the copper manufacturing source
- The rim and carrier are nonmetallic. The antenna tip overhangs the control PCB toward +Y; no copper is permitted below its antenna region on any layer. Keep metal, components and installer hardware away per the Espressif antenna guidance; validate the complete wall-box installation, nearby mains wiring and RF behavior on real hardware
- Terminal wire entries are modeled at the recessed backbox upper side. Terminal screw access requires de-energized qualified-installer service with the front/partition removed. A final production design must refine finger protection and service access; never service energized mains
- The selected PSU nominal top is Z -2.2, leaving 2.2 mm physical space below the partition; the maximum MOV envelope leaves 2.0 mm. The rear-mounted C15/C16 capacitors have only 0.6 mm nominal floor clearance and needs tolerance review. Physical space alone does not establish an adequate electrical insulation system

## Status and nonclaims

This is a compact exterior-first engineering proposal with minimum digital checks. It has not undergone mains-powered testing. No load rating, LED inrush capability, energy accuracy, fire rating, insulation certification, RF certification, thermal rating, universal wall-box fit, molding tolerance, button feel or snap-fit life is established. Screw retention, harness termination, terminal access, flame-retardant resin selection, creepage/clearance and standards review need development before any prototype energized testing. Structural STL files are for geometry review and unpowered prototypes only, not a safe live-mains enclosure.

## Reproduction

Use [LOCAL_BUILD.md](../LOCAL_BUILD.md) and `scripts/dev.ps1 -Action mechanical` for geometry/export checks or `-Action render` for presentation. Every action stages source into the specified external build directory. Generated `exports/`, `verification/`, images, PDF and video paths described above exist only in that output tree and the Release bundle, not in the source checkout.

The native assembled and animation `.blend` files stay in this repository. Parameter scripts are editable source. Video uses 37 real 3D assembly states at 1280 × 1280, 144 frames, 24 fps, six seconds, without audio; it is a simulated assembly, not recorded hardware operation. Intermediates remain in the external runtime directory. Source and output hashes record what was checked.
