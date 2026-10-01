"""Exercise the packager with a real current build and a real earlier release.

No SDK, network or hardware operation is performed. Mutations affect only an
external temporary copy. An earlier image is never flashed or executed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_release import package
from release_contract import digest, target_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-output', type=Path, required=True)
    parser.add_argument('--historical-assets', type=Path, required=True)
    parser.add_argument('--historical-assets-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('Test output must be outside the source repository')
    output.mkdir(parents=True, exist_ok=True)
    results = []
    original = json.loads((args.build_output / 'validation.json').read_text(encoding='utf-8'))
    sensor = (ROOT / 'firmware/xm125-profile.json').exists()
    image = 'target/zephyr/zephyr.hex' if sensor else 'target/carbentra_smart_switch.bin'
    member = target_files(ROOT)[image]
    with zipfile.ZipFile(args.historical_assets) as archive:
        old_image = archive.read(ROOT.name + '/' + member)
    if old_image == (args.build_output / image).read_bytes():
        raise ValueError('Regression needs a genuinely different earlier target image')
    with tempfile.TemporaryDirectory(prefix='release-regression-', dir=output) as temporary:
        workspace = Path(temporary)
        run = workspace / 'run'
        run.mkdir()

        def restore():
            for name in target_files(ROOT):
                destination = run / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(args.build_output / name, destination)
            report = copy.deepcopy(original)
            (run / 'validation.json').write_text(json.dumps(report), encoding='utf-8')
            return report

        def write(report):
            (run / 'validation.json').write_text(json.dumps(report), encoding='utf-8')

        def rejected(label, modify):
            report = restore()
            modify(report)
            write(report)
            try:
                package(ROOT, run, workspace / label)
            except (ValueError, OSError, subprocess.CalledProcessError):
                if (workspace / label).exists():
                    raise AssertionError('Rejected run created release output')
                results.append({'case': label, 'expected': 'rejected', 'passed': True})
            else:
                raise AssertionError('Unsafe package accepted: ' + label)

        restore()
        positive = package(ROOT, run, workspace / 'positive', historical=args.historical_assets,
                           historical_sha256=args.historical_assets_sha256)
        with zipfile.ZipFile(positive['path']) as archive:
            prefix = ROOT.name + '/'
            assert archive.read(prefix + member) == (args.build_output / image).read_bytes()
            assert archive.read(prefix + member) != old_image
            assert prefix + 'verification/historical-assets/origin.json' in archive.namelist()
            with zipfile.ZipFile(args.historical_assets) as historical:
                for name in ('electronics/THIRD_PARTY.md', 'electronics/reference-sources.json',
                             'electronics/bom.csv', 'electronics/pinmap.csv', 'electronics/manifest.json'):
                    assert archive.read(prefix + name) == historical.read(prefix + name)
            manifest = json.loads(archive.read(prefix + 'SHA256SUMS.json'))
            for name, identity in manifest.items():
                data = archive.read(prefix + name)
                assert len(data) == identity['bytes'] and hashlib.sha256(data).hexdigest() == identity['sha256']
        results.append({'case': 'current_target_with_historical_cad', 'expected': 'accepted', 'passed': True})
        rejected('old_target_new_report', lambda report: (run / image).write_bytes(old_image))
        rejected('old_unbound_build_record', lambda report: report.pop('firmware_binding'))
        rejected('source_drift', lambda report: report['firmware_binding']['source'].clear())
        rejected('missing_target_member', lambda report: (run / image).unlink())

        def unsafe_config(report):
            name = 'target/zephyr/.config' if sensor else 'sdkconfig'
            path = run / name
            text = path.read_text(encoding='utf-8')
            if sensor:
                text = text.replace('CONFIG_HARDWARE_DEVICE_CS_GENERATOR=y', '# CONFIG_HARDWARE_DEVICE_CS_GENERATOR is not set')
            else:
                text = text.replace('CONFIG_MBEDTLS_HAVE_TIME_DATE=y', '# CONFIG_MBEDTLS_HAVE_TIME_DATE is not set')
            path.write_text(text, encoding='utf-8')
            # Even self-consistent hashes must not bypass the semantic safety gate.
            report['firmware_binding']['artifacts'][name] = digest(path)
        rejected('unsafe_configuration_with_refreshed_hash', unsafe_config)
        if not sensor:
            def actuation(report):
                path = run / 'sdkconfig'
                path.write_text(path.read_text(encoding='utf-8').replace(
                    '# CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION is not set',
                    'CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION=y'), encoding='utf-8')
                report['firmware_binding']['artifacts']['sdkconfig'] = digest(path)
            rejected('actuation_enabled_with_refreshed_hash', actuation)
        restore()
        try:
            package(ROOT, run, workspace / 'wrong-historical-sha', historical=args.historical_assets,
                    historical_sha256='0' * 64)
        except ValueError:
            results.append({'case': 'wrong_historical_archive_hash', 'expected': 'rejected', 'passed': True})
        else:
            raise AssertionError('Wrong historical archive accepted')
    proof = {'scope': 'Actual current build and earlier release bytes; offline packaging only',
             'physical_hardware_tested': False, 'results': results}
    (output / 'release-regression.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
