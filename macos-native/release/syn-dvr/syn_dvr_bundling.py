#!/usr/bin/env python3
"""Empaquetado local de Comskip, FFmpeg, FFprobe y syn-dvr-ads nativo para SYN DVR.

No cambia SYN, DVR Engine, código UI ni grabaciones. Rehúsa dependencias dinámicas
no resolubles; crea copia antes de sustituir el .app. Reversible.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

HOME = Path.home()
DEST = Path('/Applications/SYN DVR.app')
BASE = HOME / 'Developer/SYN-macOS-7.10.8/macos-native'
BACKUPS = BASE / '.syn_dvr_autonomo_ads_443_backups'
METADATA = BACKUPS / 'ultima_instalacion.json'
PACKAGE = Path(__file__).resolve().parent
HELPER_SRC = PACKAGE / 'syn-dvr-ads.swift'
EXPECTED_ID = 'com.mrseivane.SYNDVRMenu'
REQUIRED = ('comskip', 'ffmpeg', 'ffprobe')
ICON_SOURCE = BASE / 'SYNDVRMenu/Resources/SYNDVR.icns'
ICON_NAME = 'SYNDVR.icns'


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def output(args, **kwargs):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kwargs)
    if p.returncode:
        raise RuntimeError(f"Fallo ejecutando {' '.join(map(str,args))}: {p.stderr.strip()[-500:]}")
    return p.stdout


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def app_id(path):
    try:
        with (path / 'Contents/Info.plist').open('rb') as f:
            return plistlib.load(f).get('CFBundleIdentifier')
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return None


def icon_file(app):
    # Icono oficial incluido en el código fuente y ZIP de SYN DVR.
    plist = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    icon = plist.get('CFBundleIconFile', '')
    if icon not in ('SYNDVR', ICON_NAME):
        raise RuntimeError(f'El Info.plist usa un icono inesperado: {icon!r}')
    return app / 'Contents/Resources' / ICON_NAME


def app_executable(path):
    with (path / 'Contents/Info.plist').open('rb') as f:
        name = plistlib.load(f).get('CFBundleExecutable', '')
    executable = path / 'Contents/MacOS' / name
    if not name or not executable.is_file():
        raise RuntimeError('El ejecutable principal de SYN DVR no está donde indica Info.plist.')
    return executable

def running():
    p = subprocess.run(['/bin/ps', '-axo', 'command='], capture_output=True, text=True)
    needle = str(DEST) + '/Contents/MacOS/'
    return any(needle in line for line in p.stdout.splitlines())


def authority(path):
    p = subprocess.run(['/usr/bin/codesign', '-dv', '--verbose=4', str(path)], capture_output=True, text=True)
    for line in (p.stderr + '\n' + p.stdout).splitlines():
        if line.startswith('Authority=') and line[10:].startswith(('Apple Development:', 'Developer ID Application:', 'Apple Distribution:')):
            return line[10:]
    return '-'


def privileged(args):
    prefix = ['/usr/bin/sudo'] if not os.access(DEST.parent, os.W_OK) else []
    return prefix + [str(a) for a in args]


def mac_deps(path):
    text = output(['/usr/bin/otool', '-L', path])
    result = []
    for line in text.splitlines()[1:]:
        # pathname containing spaces is accepted; split at the compatibility suffix.
        dep = line.strip().split(' (compatibility version ', 1)[0].strip()
        if dep:
            result.append(dep)
    return result


def rpaths(path):
    text = output(['/usr/bin/otool', '-l', path])
    found = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == 'cmd LC_RPATH':
            for next_line in lines[i + 1:i + 5]:
                hit = re.match(r'\s*path (.+?) \(offset \d+\)', next_line)
                if hit:
                    found.append(hit.group(1))
                    break
    return found


def system_dep(dep):
    return dep.startswith(('/usr/lib/', '/System/Library/'))


def find_dependency(dep, original):
    if system_dep(dep):
        return None
    # Shared library's own ID is listed first by otool -L; never copy it as a dependency.
    if dep.startswith('/'):
        candidate = Path(dep)
        if candidate.is_file() and (str(candidate).startswith(('/opt/homebrew/', '/usr/local/'))):
            return candidate.resolve()
        if candidate.is_file():
            raise RuntimeError('Dependencia externa fuera de Homebrew: ' + str(candidate))
        raise RuntimeError('No se encuentra biblioteca enlazada: ' + dep)

    resolved_paths = []
    if dep.startswith('@loader_path/'):
        resolved_paths.append(original.parent / dep.removeprefix('@loader_path/'))
    elif dep.startswith('@executable_path/'):
        # Only original tools use this form; their executable folder is original.parent.
        resolved_paths.append(original.parent / dep.removeprefix('@executable_path/'))
    elif dep.startswith('@rpath/'):
        tail = dep.removeprefix('@rpath/')
        for raw in rpaths(original):
            root = raw.replace('@loader_path', str(original.parent))
            root = root.replace('@executable_path', str(original.parent))
            if root.startswith('/'):
                resolved_paths.append(Path(root) / tail)
        resolved_paths.extend([Path('/opt/homebrew/lib') / tail, Path('/usr/local/lib') / tail,
                               original.parent / tail])
    else:
        raise RuntimeError('No reconozco esta dependencia Mach-O: ' + dep)
    for path in resolved_paths:
        if path.is_file():
            resolved = path.resolve()
            if str(resolved).startswith(('/opt/homebrew/', '/usr/local/')):
                return resolved
            # Relative bundled dependency outside Homebrew should be checked, not silently omitted.
            if resolved.is_file():
                raise RuntimeError('Dependencia fuera de Homebrew que requiere revisión: ' + str(resolved))
    raise RuntimeError('No se puede resolver la biblioteca ' + dep + ' usada por ' + str(original))


def bundle_libraries(stage, sources):
    target = stage / 'Contents/MacOS'
    prepared = {}        # source -> destination
    by_name = {}         # name -> source
    queue = []
    # Tools are copied first; libraries are placed in the same MacOS folder so
    # @loader_path/ works for both executables and dylibs.
    for name, executable in sources.items():
        dest = target / name
        shutil.copy2(executable, dest)
        dest.chmod(dest.stat().st_mode | 0o111)
        prepared[executable] = dest
        queue.append(executable)
        by_name[name] = executable

    edits = {}
    while queue:
        original = queue.pop(0)
        dest = prepared[original]
        deps = mac_deps(original)
        # otool -L emits the dylib's own ID as first item; skip it here.
        if original.suffix == '.dylib' and deps:
            deps = deps[1:]
        for dep in deps:
            external = find_dependency(dep, original)
            if external is None:
                continue
            basename = prepared[external].name if external in prepared else Path(dep).name
            if basename in by_name and by_name[basename] != external:
                raise RuntimeError(f'Dos bibliotecas distintas tienen el mismo nombre {basename}: '
                                   f'{by_name[basename]} y {external}. No instalaré binarios ambiguos.')
            by_name[basename] = external
            if external not in prepared:
                destination = target / basename
                shutil.copy2(external, destination)
                prepared[external] = destination
                queue.append(external)
            edits.setdefault(dest, []).append((dep, '@loader_path/' + basename))

    for path, changes in edits.items():
        for old, new in changes:
            if old != new:
                run(['/usr/bin/install_name_tool', '-change', old, new, path])
    for original, path in prepared.items():
        if original.suffix == '.dylib':
            run(['/usr/bin/install_name_tool', '-id', '@loader_path/' + path.name, path])

    # Verify every dependency in the staged files now points only inside the app or
    # to Apple system frameworks. No /opt/homebrew or /usr/local at runtime.
    for path in prepared.values():
        deps = mac_deps(path)
        if path.suffix == '.dylib':
            deps = deps[1:]
        for dep in deps:
            if system_dep(dep):
                continue
            if not dep.startswith('@loader_path/'):
                raise RuntimeError('Dependencia sin empaquetar en ' + path.name + ': ' + dep)
            candidate = target / dep.removeprefix('@loader_path/')
            if not candidate.is_file():
                raise RuntimeError('Biblioteca no incluida para ' + path.name + ': ' + dep)
    return list(prepared.values())


def sign(stage, binaries):
    signer = authority(DEST)
    if signer != '-':
        identities = output(['/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning'])
        if signer not in identities:
            raise RuntimeError('No se encuentra la identidad original de firma ' + signer)
    # Sign innermost dylibs first, then executable tools, then the .app.
    for path in sorted(binaries, key=lambda p: (p.suffix != '.dylib', p.name)):
        run(['/usr/bin/codesign', '--force', '--sign', signer, '--timestamp=none', path])
    run(['/usr/bin/codesign', '--force', '--deep', '--sign', signer, '--timestamp=none', stage])
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', stage])


def swap(new, backup):
    stage = DEST.parent / '.syn-dvr-443-new.stage.app'
    old = DEST.parent / '.syn-dvr-443-old.stage.app'
    if stage.exists() or old.exists():
        raise RuntimeError('Hay una instalación de SYN DVR incompleta previa. No borraré sus datos.')
    run(privileged(['/usr/bin/ditto', new, stage]))
    if app_id(stage) != EXPECTED_ID:
        raise RuntimeError('La copia en Aplicaciones no tiene el identificador correcto.')
    switched = False
    try:
        run(privileged(['/bin/mv', DEST, old]))
        switched = True
        run(privileged(['/bin/mv', stage, DEST]))
        if app_id(DEST) != EXPECTED_ID:
            raise RuntimeError('Identificador incorrecto tras instalar.')
        if not (DEST / 'Contents/MacOS/syn-dvr-ads').is_file():
            raise RuntimeError('No se encontró el procesador tras instalar.')
    except Exception:
        if switched:
            if DEST.exists():
                run(privileged(['/bin/mv', DEST, stage]))
            run(privileged(['/bin/mv', old, DEST]))
        raise
    run(privileged(['/bin/rm', '-rf', old]))


def install():
    print('SYN DVR 4.4.3 · Comskip, FFmpeg y FFprobe integrados; procesador nativo Swift')
    print('La app funcionará después sin Homebrew ni Python. No toca grabaciones, motor ni SYN.\n')
    if not DEST.is_dir() or app_id(DEST) != EXPECTED_ID:
        raise RuntimeError('No encuentro la app SYN DVR auténtica en ' + str(DEST))
    if running():
        raise RuntimeError('SYN DVR está abierto. Espera a que terminen las grabaciones y ciérralo desde su menú.')
    if not ICON_SOURCE.is_file():
        raise RuntimeError('Falta el icono oficial en el proyecto: ' + str(ICON_SOURCE))
    icon_hash = sha(ICON_SOURCE)
    print('🎨 Icono oficial conservado: SYNDVR.icns (SHA256 ' + icon_hash[:12] + ')')
    if not HELPER_SRC.is_file() or sha(HELPER_SRC) != 'bf98ddb6b3a76d40dc19b6dcbcc8727db74ddf731f46d06e67981e7cd604f85c':
        raise RuntimeError('Falta o ha cambiado el código del procesador nativo del ZIP.')
    if not shutil.which('xcrun'):
        raise RuntimeError('Falta xcrun; se necesita Xcode completo para construir el auxiliar una sola vez.')
    if 'DEVELOPER_DIR' not in os.environ and Path('/Volumes/T7/Xcode.app/Contents/Developer').is_dir():
        os.environ['DEVELOPER_DIR'] = '/Volumes/T7/Xcode.app/Contents/Developer'
    if os.environ.get('DEVELOPER_DIR', '') == '/Library/Developer/CommandLineTools':
        raise RuntimeError('Debes tener conectado el T7 con Xcode completo.')
    sources = {}
    for name in REQUIRED:
        found = shutil.which(name)
        if not found:
            raise RuntimeError('Falta ' + name + ' en el equipo de empaquetado. No se cambia la app.')
        exe = Path(found).resolve()
        if not str(exe).startswith(('/opt/homebrew/', '/usr/local/')):
            raise RuntimeError('Herramienta fuera de Homebrew; requiere revisar la procedencia: ' + str(exe))
        sources[name] = exe
        print('  •', name, 'desde', exe)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    BACKUPS.mkdir(parents=True, exist_ok=True)
    snapshot = BACKUPS / stamp
    snapshot.mkdir(exist_ok=False)
    old_backup = snapshot / 'SYN DVR.anterior.app'
    print('\n📦 Guardando copia de la app previa...')
    run(['/usr/bin/ditto', DEST, old_backup])
    if app_id(old_backup) != EXPECTED_ID:
        raise RuntimeError('No se pudo verificar la copia de seguridad. No se ha instalado nada.')
    with tempfile.TemporaryDirectory(prefix='syn-dvr-ads443-') as tmp:
        temp = Path(tmp)
        stage = temp / 'SYN DVR.app'
        run(['/usr/bin/ditto', DEST, stage])
        executable_folder = stage / 'Contents/MacOS'
        # El .icns del ZIP/código fuente es el icono oficial, no el de SYN principal.
        icon_dest = icon_file(stage)
        icon_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ICON_SOURCE, icon_dest)
        if sha(icon_dest) != icon_hash:
            raise RuntimeError('No se pudo incorporar el icono oficial SYNDVR.icns.')
        print('🔎 Incorporando bibliotecas dinámicas de Comskip y FFmpeg...')
        bundled = bundle_libraries(stage, sources)
        helper = executable_folder / 'syn-dvr-ads'
        run(['xcrun', 'swiftc', '-O', HELPER_SRC, '-o', helper])
        bundled.append(helper)
        print('🔏 Firmando y validando ejecutables incorporados...')
        sign(stage, bundled)
        for name in ('ffmpeg', 'ffprobe'):
            p = subprocess.run([str(executable_folder / name), '-version'], capture_output=True, text=True, timeout=20)
            if p.returncode != 0 or not p.stdout.startswith(name + ' version'):
                raise RuntimeError(name + ' no arranca de forma autónoma: ' + p.stderr[-500:])
        probe = subprocess.run([str(executable_folder / 'comskip'), '--help'], capture_output=True, text=True, timeout=20)
        if probe.returncode < 0 or ('Library not loaded' in probe.stderr) or ('dyld' in probe.stderr.lower()):
            raise RuntimeError('Comskip no puede arrancar con las bibliotecas incluidas: ' + probe.stderr[-500:])
        # El procesador nativo debe arrancar sin Python; su uso sin argumentos devuelve
        # un diagnóstico inequívoco sin operar sobre archivos de grabación.
        helper_test = subprocess.run([str(helper)], capture_output=True, text=True, timeout=12)
        if helper_test.returncode != 2 or 'Argumentos incorrectos' not in helper_test.stdout:
            raise RuntimeError('El procesador nativo de anuncios no arranca correctamente: ' + helper_test.stderr[-300:])
        if sha(icon_file(stage)) != icon_hash:
            raise RuntimeError('El icono oficial cambió inesperadamente tras la firma.')
        print(f'✅ {len(bundled)} ejecutables y bibliotecas incluidos; arranque de herramientas verificado.')
        print('📦 Instalando solo SYN DVR.app...')
        swap(stage, old_backup)
    METADATA.write_text(json.dumps({
        'app_backup': str(old_backup),
        'helper_sha': sha(DEST / 'Contents/MacOS/syn-dvr-ads'),
        'app_executable_sha': sha(app_executable(DEST)),
        'icon_sha': sha(icon_file(DEST)),
        'created_at': stamp,
    }, ensure_ascii=False, indent=2))
    print('\n✅ SYN DVR tiene Comskip, FFmpeg, FFprobe y syn-dvr-ads dentro de la app.')
    print('✅ No se usará Homebrew ni Python al quitar anuncios.')
    print('✅ Grabaciones, SYN principal y motor DVR intactos.')
    print('↩ Para restaurar la app anterior: DESHACER.command')


def revert():
    if not METADATA.is_file():
        raise RuntimeError('No encuentro un respaldo creado por este instalador.')
    meta = json.loads(METADATA.read_text())
    old = Path(meta['app_backup'])
    if app_id(DEST) != EXPECTED_ID or app_id(old) != EXPECTED_ID:
        raise RuntimeError('No puedo verificar las aplicaciones actual o anterior.')
    if running():
        raise RuntimeError('Cierra SYN DVR antes de restaurar la app anterior.')
    if sha(DEST / 'Contents/MacOS/syn-dvr-ads') != meta['helper_sha'] or \
       sha(app_executable(DEST)) != meta['app_executable_sha'] or \
       sha(icon_file(DEST)) != meta['icon_sha']:
        raise RuntimeError('La aplicación se ha actualizado después de instalar: no se restaurará a ciegas.')
    restored = BACKUPS / ('antes_de_revertir_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    restored.mkdir()
    run(['/usr/bin/ditto', DEST, restored / 'SYN DVR.con-herramientas.app'])
    swap(old, restored / 'SYN DVR.con-herramientas.app')
    print('✅ SYN DVR anterior restaurado. Se conserva la versión con herramientas en:', restored)


if __name__ == '__main__':
    try:
        if len(sys.argv) == 1:
            install()
        elif len(sys.argv) == 2 and sys.argv[1] == '--revert':
            revert()
        else:
            raise RuntimeError('Uso: instalar.py [--revert]')
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print('\n❌ ' + str(exc), file=sys.stderr)
        sys.exit(1)
