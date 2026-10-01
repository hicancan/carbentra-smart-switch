"""Small host adapters; geometry and electronics remain in their native sources."""
import os
from pathlib import Path

def runtime(name=''):
    root = os.environ.get('CARBENTRA_RUNTIME')
    if not root:
        raise RuntimeError('Use scripts/dev.ps1 with an explicit external BuildRoot')
    path = Path(root) / name
    path.mkdir(parents=True, exist_ok=True)
    return path

def configure_cycles(scene):
    import bpy
    preferences = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA'):
        try:
            preferences.compute_device_type = backend
            preferences.get_devices()
            devices = [d for d in preferences.devices if d.type == backend]
            if devices:
                for device in preferences.devices:
                    device.use = device.type == backend
                scene.cycles.device = 'GPU'
                print('CYCLES_DEVICE', backend, ', '.join(d.name for d in devices), flush=True)
                return
        except (TypeError, RuntimeError):
            continue
    scene.cycles.device = 'CPU'
    print('CYCLES_DEVICE CPU (no supported GPU available)', flush=True)

def memory_kib():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:
        return None

def drawing_font(bold=False):
    explicit = os.environ.get('CARBENTRA_FONT_BOLD' if bold else 'CARBENTRA_FONT')
    candidates = [explicit] if explicit else []
    candidates += [str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('arialbd.ttf' if bold else 'arial.ttf')),
                   '/usr/share/fonts/truetype/dejavu/DejaVuSans' + ('-Bold' if bold else '') + '.ttf']
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError('Set CARBENTRA_FONT and CARBENTRA_FONT_BOLD to TrueType font files')
