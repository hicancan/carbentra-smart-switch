# Native editable electronics

Open the control / power `.kicad_pro` projects with KiCad 10.0.5. Schematics, routed boards, rules, local symbol/footprint libraries, BOM, pin maps and mechanical contracts are retained as editable source. These native circuit files are authoritative.

Follow [LOCAL_BUILD.md](../LOCAL_BUILD.md) and `scripts/dev.ps1 -Action electronics -BuildRoot <external-directory>`. The coordinator copies source into a fresh external directory, runs strict ERC/DRC, exports native netlists and independently compares PCB pad connections, then produces schematic PDF, Gerbers, Excellon drills and source-faithful presentation sheets. A nonzero rule check stops the workflow. Generated output and detailed JSON reports live in the build tree and Release bundle.

The export workflow also checks isolated hot/cold copper spacing and eight selected main current paths. These geometrical checks do not establish a load rating or electrical safety certification.

The validated reproducible boundary is native circuit → checks → manufacturing outputs. Earlier one-time ECO, placement-generation and autorouting scripts are retained only in Git history. Their alternate valid routings are not claimed to reproduce the current boards. After deliberate native edits, rerun the whole electronics stage and review the resulting drawings.

Third-party datasheets are linked in `reference-sources.json` and BOM/documentation rather than redistributed. Retained library files preserve their original attribution. See [THIRD_PARTY.md](THIRD_PARTY.md).

Engineering candidate only: no fabricated-board inspection, powered measurements, RF/thermal qualification or manufacturing release is implied.
