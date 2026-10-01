"""Refresh/check current checkout byte identity; does not rerun engineering checks."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'verification/source-manifest.json'
EXCLUDED = {'verification/source-manifest.json', 'firmware/build-report.json', 'verification/local-validation.json'}


def inventory():
    names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).decode('utf-8').split('\0')
    return {name: {'bytes': (ROOT / name).stat().st_size,
                   'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
            for name in sorted(set(names)) if name and name not in EXCLUDED and (ROOT / name).is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Explicitly refresh the source inventory')
    args = parser.parse_args()
    files = inventory()
    if args.write:
        report = {'schema_version': 2, 'binding': 'Exact current checkout bytes for release staging; this inventory does not claim any new CAD, media or physical validation.',
                  'excluded_historical_reports_and_self': sorted(EXCLUDED), 'files': files}
        MANIFEST.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    else:
        recorded = json.loads(MANIFEST.read_text(encoding='utf-8'))['files']
        changed = sorted(name for name in recorded.keys() | files.keys() if recorded.get(name) != files.get(name))
        if changed:
            parser.exit(1, 'Source manifest mismatch: ' + ', '.join(changed) + '\n')
    print(f'PASS: {len(files)} source byte identities; no additional engineering qualification implied')


if __name__ == '__main__':
    main()
