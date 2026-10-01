"""Package successful external build and render runs without rebuilding or flashing."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-output', type=Path, required=True)
    parser.add_argument('--render-output', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    for folder, expected in [(args.build_output, {'host', 'target', 'electronics', 'mechanical'}), (args.render_output, {'render'})]:
        result = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
        assert expected <= {key for key, value in result['checks'].items() if value == 'passed'}
        assert result['physical_hardware_tested'] is False
    destination = args.destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit('Release output must be outside the source checkout')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (ROOT.name + '-engineering-20261001.zip')
    if archive.exists():
        raise SystemExit(f'Refusing to replace existing release: {archive}')
    sensor = ROOT.name.endswith('sensor')
    with tempfile.TemporaryDirectory(prefix='package-', dir=destination) as temp:
        base = Path(temp) / ROOT.name
        base.mkdir()
        def copy(source, relative):
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.work', '__pycache__', '*.blend1', '*.blend2', '*.kicad_prl'))
            else:
                shutil.copy2(source, target)
        for name in ['LICENSE', 'LICENSE-HARDWARE', 'LICENSE-DOCUMENTATION', 'LICENSES.md', 'LOCAL_BUILD.md']:
            copy(ROOT / name, name)
        copy(ROOT / 'firmware/licenses', 'firmware/licenses')
        copy(ROOT / 'firmware/THIRD_PARTY_NOTICES.md', 'firmware/THIRD_PARTY_NOTICES.md')
        copy(ROOT / 'firmware/build-report.json', 'firmware/build-report.json')
        copy(ROOT / 'electronics/THIRD_PARTY.md', 'electronics/THIRD_PARTY.md')
        copy(ROOT / 'electronics/reference-sources.json', 'electronics/reference-sources.json')
        copy(ROOT / 'verification/local-validation.json', 'verification/local-validation.json')
        copy(args.build_output / 'validation.json', 'verification/build-run.json')
        # Retain the original execution hashes explicitly: that render predates
        # portable line-ending normalization, while geometry is unchanged.
        render_report = json.loads((args.render_output / 'validation.json').read_text(encoding='utf-8'))
        render_report['historical_as_executed_source_sha256'] = render_report.pop('source_sha256', {})
        render_report['published_source_manifest'] = 'source-manifest.json'
        render_report['source_binding_note'] = 'Render execution predates text EOL normalization. Native CAD bytes and render geometry are unchanged; historical execution hashes describe the earlier working tree, not the published checkout.'
        (base / 'verification/render-run.json').write_text(json.dumps(render_report, indent=2) + '\n', encoding='utf-8')
        copy(ROOT / 'verification/source-manifest.json', 'verification/source-manifest.json')
        for name in ['bom.csv', 'pinmap.csv', 'manifest.json']:
            copy(ROOT / 'electronics' / name, 'electronics/' + name)
        ecad = args.build_output / 'electronics'
        model = args.build_output / 'mechanical' / 'mechanical'
        rendered = args.render_output / 'render'
        copy(ecad / 'electronics' / ('output' if sensor else 'verification'), 'electronics/generated')
        copy(model / 'exports', 'mechanical/exports')
        copy(model / 'verification', 'verification/mechanical-build')
        copy(rendered / 'mechanical/verification', 'verification/mechanical-render')
        if sensor:
            copy(model / 'dimensioned_layout.pdf', 'mechanical/dimensioned_layout.pdf')
            copy(rendered / 'visuals', 'visuals')
            copy(ecad / 'visuals', 'visuals')
            for name in ['zephyr.hex', 'zephyr.elf', 'zephyr.dts', '.config']:
                copy(args.build_output / 'target/zephyr' / name, 'firmware/' + ('zephyr.config' if name == '.config' else name))
            copy(ROOT / 'firmware/sources.json', 'firmware/sources.json')
        else:
            copy(rendered / 'presentation', 'presentation')
            copy(ecad / 'presentation', 'presentation')
            for name in ['carbentra_smart_switch.bin', 'bootloader/bootloader.bin', 'partition_table/partition-table.bin']:
                copy(args.build_output / 'target' / name, 'firmware/' + name)
            copy(args.build_output / 'sdkconfig', 'firmware/sdkconfig')
            copy(ROOT / 'firmware/dependencies.lock.json', 'firmware/dependencies.lock.json')
        (base / 'README.txt').write_text(
            'Engineering development outputs; not a physically validated or certified product.\n'
            'Native editable source and full instructions are in the corresponding GitHub repository.\n'
            'No production keys, vendor XM125 application, flashing, or load actuation is included.\n'
            'Each verification manifest states its source hashes and tested scope. Raw build logs are not source truth.\n'
            'Assembly video is simulated 3D geometry, not hardware footage.\n', encoding='utf-8')
        manifest = {p.relative_to(base).as_posix(): {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in sorted(base.rglob('*')) if p.is_file()}
        (base / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in sorted(base.rglob('*')):
                if path.is_file():
                    output.write(path, path.relative_to(Path(temp)).as_posix())
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps({'path': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest}, indent=2))


if __name__ == '__main__':
    main()
