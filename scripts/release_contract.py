"""Bind a completed firmware run to source bytes, target bytes and safety checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def source_inventory(root):
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z',
                                     '--cached', '--others', '--exclude-standard']).decode().split('\0')
    selected = []
    for name in names:
        path = Path(name)
        firmware_input = (name.startswith('firmware/') and
                          not name.startswith(('firmware/licenses/', 'firmware/evidence/', 'firmware/artifacts/')) and
                          (path.suffix in {'.c', '.h', '.py', '.ps1', '.sh', '.conf', '.overlay', '.dts', '.yml', '.yaml', '.cmake'} or
                           path.name.startswith('Kconfig') or path.name.endswith('_defconfig') or
                           path.name in {'CMakeLists.txt', 'Kconfig.projbuild', 'sdkconfig', 'sdkconfig.defaults',
                                         'partitions.csv', 'sources.json', 'dependencies.lock.json', 'xm125-profile.json'}))
        if (firmware_input or name in {'scripts/engineering.py', 'scripts/dev.ps1', 'scripts/release_contract.py',
                                      'scripts/package_release.py', 'pyproject.toml', 'uv.lock'}) and (root / name).is_file():
            selected.append(name)
    return {name: digest(root / name) for name in sorted(set(selected))}


def target_files(root):
    if (root / 'firmware/xm125-profile.json').is_file():
        return {f'target/zephyr/{name}': f'firmware/{"zephyr.config" if name == ".config" else name}'
                for name in ('zephyr.hex', 'zephyr.elf', 'zephyr.dts', '.config')} | {
                    'xm125-prerequisites.json': 'verification/xm125-prerequisites.json'}
    return {f'target/{name}': f'firmware/{name}' for name in (
        'carbentra_smart_switch.bin', 'carbentra_smart_switch.elf',
        'bootloader/bootloader.bin', 'partition_table/partition-table.bin')} | {
            'sdkconfig': 'firmware/sdkconfig', 'target-tls-guard.json': 'verification/target-tls-guard.json'}


def safety_check(root, run):
    if (root / 'firmware/xm125-profile.json').is_file():
        subprocess.run([sys.executable, '-B', str(root / 'firmware/scripts/check_target.py'),
                        str(run / 'target')], check=True)
        subprocess.run([sys.executable, '-B', str(root / 'firmware/scripts/check_xm125.py'),
                        '--profile-only'], check=True, stdout=subprocess.DEVNULL)
        profile = json.loads((root / 'firmware/xm125-profile.json').read_text(encoding='utf-8'))
        evidence = json.loads((run / 'xm125-prerequisites.json').read_text(encoding='utf-8'))
        if (evidence.get('profile_id') != profile['profile_id'] or
                evidence.get('source_profile_check') != 'passed' or
                evidence.get('vendor_artifact', {}).get('status') != 'not_checked' or
                any(evidence.get(key) is not False for key in ('deployment_ready', 'module_flashing_verified',
                        'hardware_readback_verified', 'physical_qualification_verified'))):
            raise ValueError('XM125 development prerequisites do not match the current profile/scope')
    else:
        subprocess.run([sys.executable, '-B', str(root / 'firmware/tools/check_tls_config.py'),
                        str(run / 'sdkconfig')], check=True)
        config = (run / 'sdkconfig').read_text(encoding='utf-8').splitlines()
        if ('# CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION is not set' not in config or
                'CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION=y' in config):
            raise ValueError('Physical actuation must remain disabled')
        guard = json.loads((run / 'target-tls-guard.json').read_text(encoding='utf-8'))
        expected = {'generated_config': True, 'date_disabled': False,
                    'time_disabled': False, 'insecure_enabled': False}
        checks = guard.get('checks', [])
        if (guard.get('hardware_tested') is not False or guard.get('tls_handshake_tested') is not False or
                len(checks) != len(expected) or {c.get('case') for c in checks} != set(expected) or
                any(c.get('passed') is not True or c.get('expected_compile_success') is not expected[c['case']] or
                    (c.get('returncode') == 0) is not expected[c['case']] for c in checks)):
            raise ValueError('Actual target TLS compile guards are incomplete or failed')


def record_binding(root, run, before, checks):
    after = source_inventory(root)
    if not before or after != before:
        raise ValueError('Firmware inputs changed during validation; rerun the build')
    artifacts = {}
    if checks.get('target') == 'passed':
        safety_check(root, run)
        artifacts = {name: digest(run / name) for name in target_files(root)}
    return {'schema_version': 1, 'source': before, 'artifacts': artifacts}


def validate_run(root, run):
    report = json.loads((run / 'validation.json').read_text(encoding='utf-8'))
    if (report.get('physical_hardware_tested') is not False or
            any(report.get('checks', {}).get(key) != 'passed' for key in ('host', 'target'))):
        raise ValueError('A completed host and target run is required')
    binding = report.get('firmware_binding', {})
    if binding.get('schema_version') != 1 or binding.get('source') != source_inventory(root):
        raise ValueError('Target source binding is missing or stale; rebuild current firmware')
    expected = target_files(root)
    recorded = binding.get('artifacts', {})
    if set(recorded) != set(expected):
        raise ValueError('Target artifact inventory is incomplete')
    for name in expected:
        if not (run / name).is_file() or digest(run / name) != recorded[name]:
            raise ValueError(f'Target artifact bytes do not match the completed build: {name}')
    safety_check(root, run)
    return report
