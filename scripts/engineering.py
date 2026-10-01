"""Local build coordinator. Generated output stays in an explicit build directory."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def run(args, *, cwd=ROOT, env=None):
    if Path(str(args[0])).name.lower() in ('blender', 'blender.exe'):
        args = [args[0], '--python-exit-code', '1', *args[1:]]
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)

def stage(destination):
    destination.mkdir(parents=True, exist_ok=False)
    files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    for name in files:
        if not name or not (ROOT / name).is_file():
            continue
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, path)
    return destination

def host(build):
    if os.environ.get('CJSON_ROOT'):
        expected = json.loads((ROOT / 'firmware/dependencies.lock.json').read_text(encoding='utf-8'))['sdk_submodules']['cJSON']
        actual = subprocess.check_output(['git', '-C', os.environ['CJSON_ROOT'], 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise RuntimeError('Host checks require the exact cJSON commit pinned by ESP-IDF 5.4.3')
    run(['cmake', '-S', ROOT / 'firmware/host', '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Debug'])
    run(['cmake', '--build', build, '--parallel', '4'])
    run(['ctest', '--test-dir', build, '--output-on-failure'])

def target(build):
    sdk = Path(os.environ['IDF_PATH'])
    expected = json.loads((ROOT / 'firmware/dependencies.lock.json').read_text(encoding='utf-8'))['sdk']['git_commit']
    commit = subprocess.check_output(['git', '-C', str(sdk), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != expected:
        raise RuntimeError('The target requires the pinned ESP-IDF 5.4.3 commit')
    python = Path(os.environ['IDF_PYTHON_ENV_PATH']) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    exported = subprocess.check_output([str(python), str(sdk / 'tools/idf_tools.py'), 'export', '--format', 'key-value'], text=True)
    for line in exported.splitlines():
        if '=' in line and line.split('=', 1)[0] in ('PATH', 'OPENOCD_SCRIPTS', 'IDF_CCACHE_ENABLE', 'ESP_ROM_ELF_DIR', 'ESP_IDF_VERSION', 'IDF_DEACTIVATE_FILE_PATH'):
            key, value = line.split('=', 1)
            os.environ[key] = value.replace('%PATH%', os.environ.get('PATH', ''))
    os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = '6'
    config = build.parent / 'sdkconfig'
    shutil.copy2(ROOT / 'firmware/sdkconfig', config)
    run([python, sdk / 'tools/idf.py', '-C', ROOT / 'firmware', '-B', build,
         '-D', 'SDKCONFIG=' + config.as_posix(), '-D', 'IDF_TARGET=esp32c3', 'build'])
    content = config.read_text(encoding='utf-8')
    assert 'CONFIG_CARBENTRA_SWITCH_ALLOW_ACTUATION=y' not in content
    print('PASS: ESP32-C3 image built with physical actuation disabled')


def electronics(work):
    kbin = Path(os.environ['KICAD_BIN'])
    cli = kbin / ('kicad-cli.exe' if os.name == 'nt' else 'kicad-cli')
    python = kbin / ('python.exe' if os.name == 'nt' else 'python3')
    e = work / 'electronics'
    os.environ['PATH'] = str(kbin) + os.pathsep + os.environ['PATH']
    output = e / 'verification'
    output.mkdir(exist_ok=True)
    for board in ('control', 'power'):
        for kind, ext in [('sch', 'kicad_sch'), ('pcb', 'kicad_pcb')]:
            check = 'erc' if kind == 'sch' else 'drc'
            run([cli, kind, check, '--exit-code-violations', '--format', 'json', '-o', output / f'{board}-{check}.json', e / f'{board}.{ext}'], cwd=work)
        run([cli, 'sch', 'export', 'netlist', '-o', output / f'{board}.net', e / f'{board}.kicad_sch'], cwd=work)
        run([cli, 'sch', 'export', 'pdf', '-o', output / f'{board}-schematic.pdf', e / f'{board}.kicad_sch'], cwd=work)
        raw = work / 'presentation/electronics_sources'
        raw.mkdir(parents=True, exist_ok=True)
        run([cli, 'sch', 'export', 'svg', '--exclude-drawing-sheet', '--no-background-color', '-o', str(raw) + os.sep, e / f'{board}.kicad_sch'], cwd=work)
        layers = 'F.Cu,In1.Cu,In2.Cu,B.Cu'
        fab = output / f'gerbers-{board}'
        fab.mkdir(exist_ok=True)
        run([cli, 'pcb', 'export', 'gerbers', '-l', layers + ',F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts', '-o', str(fab) + os.sep, e / f'{board}.kicad_pcb'], cwd=work)
        run([cli, 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '-o', str(fab) + os.sep, e / f'{board}.kicad_pcb'], cwd=work)
    for check in ('check_connectivity.py', 'check_isolation.py', 'check_load_paths.py'):
        run([python, '-X', 'utf8', e / 'scripts' / check], cwd=work)
    run([sys.executable, e / 'scripts/presentation_sheets.py'], cwd=work)

def mechanical(work, render=False):
    blender = os.environ.get('BLENDER_EXE', 'blender')
    source = work / 'mechanical/source'
    for directory in ('mechanical/exports', 'mechanical/verification', 'presentation'):
        (work / directory).mkdir(parents=True, exist_ok=True)
    run([blender, '--background', '--factory-startup', '--python', source / 'build_switch.py'], cwd=work)
    if render:
        run([blender, '--background', '--factory-startup', '--python', source / 'render_presentation.py'], cwd=work)
        run([sys.executable, source / 'compose_presentation.py', '--all'], cwd=work)
    run([blender, '--background', '--factory-startup', '--python', source / 'verify_files.py'], cwd=work)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['host', 'target', 'electronics', 'mechanical', 'render', 'all'])
    parser.add_argument('--build-root', type=Path, required=True)
    args = parser.parse_args()
    base = args.build_root.resolve()
    if base == ROOT or ROOT in base.parents:
        raise SystemExit('Build root must be outside the source repository')
    base.mkdir(parents=True, exist_ok=True)
    run_dir = base / (args.action + '-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    run_dir.mkdir()
    os.environ.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', TEMP=str(run_dir), TMP=str(run_dir))
    os.environ['CARBENTRA_RUNTIME'] = str(run_dir / 'runtime')
    Path(os.environ['CARBENTRA_RUNTIME']).mkdir()
    os.environ['PYTHONPATH'] = str(ROOT / 'scripts')
    if os.environ.get('INKSCAPE_BIN'):
        os.environ['PATH'] = os.environ['INKSCAPE_BIN'] + os.pathsep + os.environ['PATH']
    actions = ['host', 'target', 'electronics', 'mechanical'] if args.action == 'all' else [args.action]
    report = {'schema_version': 1, 'platform': sys.platform, 'python': sys.version, 'checks': {}, 'physical_hardware_tested': False}
    for action in actions:
        if action in ('host', 'target'):
            globals()[action](run_dir / action)
        else:
            work = stage(run_dir / action)
            electronics(work) if action == 'electronics' else mechanical(work, render=action == 'render')
        report['checks'][action] = 'passed'
    report['source_sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and '.venv' not in p.parts and p.suffix in ('.c', '.h', '.py', '.ps1', '.kicad_pcb', '.kicad_sch')}
    (run_dir / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('VALIDATED_OUTPUT', run_dir, flush=True)

if __name__ == '__main__':
    main()
