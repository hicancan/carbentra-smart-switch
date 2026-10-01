"""Package a source-bound firmware run and optional unchanged historical CAD/media."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

from release_contract import source_inventory, target_files, validate_run

ROOT = Path(__file__).resolve().parents[1]
CAD_PREFIXES = ('electronics/', 'mechanical/', 'interfaces/', 'presentation/')


def historical_assets(root, archive, expected_sha256):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('Historical archive SHA256 does not match its recorded release')
    with zipfile.ZipFile(archive) as source:
        prefix = root.name + '/'
        manifest = json.loads(source.read(prefix + 'SHA256SUMS.json'))
        entries = {}
        for name, identity in manifest.items():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Unsafe historical archive member')
            data = source.read(prefix + name)
            if len(data) != identity['bytes'] or hashlib.sha256(data).hexdigest() != identity['sha256']:
                raise ValueError(f'Historical member hash mismatch: {name}')
            entries[name] = data
    old_sources = json.loads(entries['verification/source-manifest.json'])['files']
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                                     '--others', '--exclude-standard']).decode().split('\0')
    current = {name for name in names if name.startswith(CAD_PREFIXES) and (root / name).is_file()}
    historical = {name for name in old_sources if name.startswith(CAD_PREFIXES)}
    if current != historical:
        raise ValueError('Historical CAD/media source inventory differs from current checkout')
    for name in current:
        data = (root / name).read_bytes()
        if {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} != old_sources[name]:
            raise ValueError(f'Historical CAD/media input changed: {name}')
    selected = {name: data for name, data in entries.items()
                if name.startswith(('electronics/generated/', 'mechanical/', 'visuals/', 'presentation/'))}
    for name in ('electronics/THIRD_PARTY.md', 'electronics/reference-sources.json',
                 'electronics/bom.csv', 'electronics/pinmap.csv', 'electronics/manifest.json'):
        selected[name] = entries[name]
    for name, data in entries.items():
        if name.startswith('verification/'):
            selected['verification/historical-assets/' + name.removeprefix('verification/')] = data
    selected['verification/historical-assets/origin.json'] = (json.dumps({
        'archive': archive.name, 'sha256': expected_sha256, 'source_files_matched': len(current),
        'scope': 'Unchanged CAD and media reused from this earlier release; not rerun for the current firmware build.',
        'current_firmware_inherited': False}, indent=2) + '\n').encode()
    return selected


def package(root, build, destination, *, historical=None, historical_sha256=None):
    report = validate_run(root, build)
    if bool(historical) != bool(historical_sha256):
        raise ValueError('Historical assets require both an archive and its published SHA256')
    destination = destination.resolve()
    if destination == root or root in destination.parents:
        raise ValueError('Release output must be outside the source checkout')
    entries = historical_assets(root, historical, historical_sha256) if historical else {}
    for name in ('LICENSE', 'LICENSE-HARDWARE', 'LICENSE-DOCUMENTATION', 'LICENSES.md', 'LOCAL_BUILD.md',
                 'firmware/THIRD_PARTY_NOTICES.md', 'verification/source-manifest.json'):
        entries[name] = (root / name).read_bytes()
    for path in (root / 'firmware/licenses').rglob('*'):
        if path.is_file():
            entries[path.relative_to(root).as_posix()] = path.read_bytes()
    for relative, packaged in target_files(root).items():
        data = (build / relative).read_bytes()
        if {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} != report['firmware_binding']['artifacts'][relative]:
            raise ValueError(f'Target changed while packaging: {relative}')
        entries[packaged] = data
    for name in ('sources.json', 'dependencies.lock.json', 'xm125-profile.json'):
        if (root / 'firmware' / name).is_file():
            entries['firmware/' + name] = (root / 'firmware' / name).read_bytes()
    entries['verification/firmware-build-run.json'] = (json.dumps(report, indent=2) + '\n').encode()
    # Earlier reports retain their original scope and hashes; they never label current target bytes.
    for name, label in [('firmware/build-report.json', 'windows-build-report.json'),
                        ('firmware/remediation-report.json', 'linux-remediation-report.json')]:
        entries['verification/historical-firmware/' + label] = (root / name).read_bytes()
    entries['README.txt'] = (
        'Current firmware: verification/firmware-build-run.json binds current source, target bytes and safety checks.\n'
        'CAD/media, when present, are historical unchanged assets; see verification/historical-assets/origin.json.\n'
        'Historical firmware reports do not attest the current binaries. No physical hardware was tested.\n'
        'No flashing, actuation, production keys or external XM125 vendor application is included.\n').encode()
    inventory = json.loads(entries['verification/source-manifest.json'])['files']
    for name, identity in inventory.items():
        data = (root / name).read_bytes()
        if {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} != identity:
            raise ValueError(f'Published source manifest is stale: {name}')
    if source_inventory(root) != report['firmware_binding']['source']:
        raise ValueError('Firmware sources changed while packaging')
    manifest = {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                for name, data in sorted(entries.items())}
    entries['SHA256SUMS.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (root.name + '-engineering.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for name, data in sorted(entries.items()):
            output.writestr(root.name + '/' + name, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii', newline='\n')
    return {'path': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-output', type=Path, required=True, help='Current firmware/all run with host and target checks')
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--historical-assets', type=Path)
    parser.add_argument('--historical-assets-sha256')
    args = parser.parse_args()
    try:
        print(json.dumps(package(ROOT, args.build_output, args.destination,
                                 historical=args.historical_assets,
                                 historical_sha256=args.historical_assets_sha256), indent=2))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Release blocked: {error}\n')


if __name__ == '__main__':
    main()
