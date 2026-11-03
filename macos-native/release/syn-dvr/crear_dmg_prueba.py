#!/usr/bin/env python3
"""SYN DVR: reproduce a test DMG from ALREADY INTEGRATED repository sources.

This builder does not patch source, install apps, or touch recording data.
Run from macos-native/release/syn-dvr/CREAR_DMG_PRUEBA.command on macOS.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
HOME = Path.home()


def call(args: list[str | Path], *, env: dict | None = None) -> None:
    subprocess.run([str(x) for x in args], env=env, check=True)


def build() -> None:
    if sys.platform != 'darwin':
        raise RuntimeError('El DMG se genera en un Mac con Xcode completo.')
    app_info = PROJECT / 'SYNDVRMenu/Resources/Info.plist'
    with app_info.open('rb') as fd:
        version = str(plistlib.load(fd)['CFBundleShortVersionString'])
    if not shutil.which('git') or not shutil.which('xcodegen'):
        raise RuntimeError('El Mac constructor necesita git y xcodegen. No el usuario final.')
    for name in ('ffmpeg', 'ffprobe', 'comskip'):
        if not shutil.which(name):
            raise RuntimeError(f'Falta {name} en el Mac CONSTRUCTOR; no es requisito del usuario final.')
    env = os.environ.copy()
    developer = Path('/Volumes/T7/Xcode.app/Contents/Developer')
    if developer.is_dir():
        env['DEVELOPER_DIR'] = str(developer)
    if env.get('DEVELOPER_DIR') == '/Library/Developer/CommandLineTools':
        raise RuntimeError('Se necesita Xcode completo, no solo las Command Line Tools.')
    if not (env.get('DEVELOPER_DIR') or Path('/Applications/Xcode.app/Contents/Developer').is_dir()):
        raise RuntimeError('Conecta el T7 con Xcode o instala Xcode completo.')
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    output = HOME / 'Downloads' / f'SYN-DVR-{version}-{platform.machine()}-{stamp}-PRUEBA-NO-PUBLICAR.dmg'
    if output.exists():
        raise RuntimeError(f'No sobreescribiré un DMG existente: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f'=== SYN DVR {version}: DMG desde código integrado ===', flush=True)
    print('No se modifican apps, datos, grabaciones ni GitHub.', flush=True)
    with tempfile.TemporaryDirectory(prefix='syn-dvr-dmg-456-') as tmp:
        temp = Path(tmp)
        py = shutil.which('python3')
        if not py:
            raise RuntimeError('Falta Python 3 en el equipo de compilación.')
        probe = subprocess.run([py, '-c', 'import PyInstaller'], capture_output=True)
        if probe.returncode:
            virtual = temp / 'venv'
            print('Preparando PyInstaller temporal (solo equipo constructor)…', flush=True)
            venv.EnvBuilder(with_pip=True).create(virtual)
            py = str(virtual / 'bin/python3')
            call([py, '-m', 'pip', 'install', '--disable-pip-version-check', 'PyInstaller'], env=env)
            env['PATH'] = str(virtual / 'bin') + ':' + env.get('PATH', '')
        source_builder = ROOT / 'GENERAR_DISTRIBUCION.command'
        if not source_builder.is_file():
            raise RuntimeError('Falta GENERAR_DISTRIBUCION.command.')
        print('Compilando app, motor, herramientas y runtime; probando primera configuración…', flush=True)
        call(['/bin/bash', source_builder, '--development', '--output', temp], env=env)
        zips = list(temp.glob(f'SYN-DVR-{version}-*-PRUEBAS-NO-PUBLICAR.zip'))
        if len(zips) != 1:
            raise RuntimeError(f'Paquete ZIP inesperado: {len(zips)}. Se esperaba un único ZIP {version}.')
        extracted = temp / 'dmg'
        extracted.mkdir()
        with zipfile.ZipFile(zips[0]) as z:
            failed = z.testzip()
            if failed:
                raise RuntimeError('ZIP defectuoso: ' + failed)
            required = {
                'SYN DVR.app/Contents/MacOS/syn-dvr-worker',
                'SYN DVR.app/Contents/MacOS/syn-dvr-python',
                'SYN DVR.app/Contents/MacOS/ffmpeg',
                'SYN DVR.app/Contents/MacOS/ffprobe',
                'SYN DVR.app/Contents/Resources/SYNDVR.icns',
                'SYN DVR.app/Contents/Resources/SYN-DVR-Runtime/standalone_supervisor.py',
            }
            missing = required - set(z.namelist())
            if missing:
                raise RuntimeError('Faltan componentes en el ZIP: ' + ', '.join(sorted(missing)))
        call(['/usr/bin/ditto', '-xk', zips[0], extracted], env=env)
        installed_info = extracted / 'SYN DVR.app/Contents/Info.plist'
        with installed_info.open('rb') as fd:
            bundled_version = str(plistlib.load(fd).get('CFBundleShortVersionString'))
        if bundled_version != version:
            raise RuntimeError('La app y el código tienen versiones distintas.')
        (extracted / 'LEEME-PRUEBA.txt').write_text(
            f'SYN DVR {version} — Prueba local, NO PUBLICAR\n\n'
            'La aplicación incluye motor, FFmpeg y Python integrado. No requiere Homebrew\n'
            'ni Xcode para quien la instale. No está notarizada.\n'
            'Copia la app en ~/Applications de la cuenta de pruebas, NO en /Applications.\n'
            'Con macOS Gatekeeper, autoriza su apertura en Ajustes > Privacidad y seguridad.\n'
            'No desactives Gatekeeper globalmente.\n', encoding='utf-8')
        print('Creando DMG de prueba…', flush=True)
        call(['/usr/bin/hdiutil', 'create', '-volname', f'SYN DVR {version} prueba',
              '-srcfolder', extracted, '-format', 'UDZO', output], env=env)
        call(['/usr/bin/hdiutil', 'verify', output], env=env)
        if output.stat().st_size < 1024 * 1024:
            raise RuntimeError('DMG incompleto o demasiado pequeño.')
        with output.open('rb') as fin:
            digest = hashlib.file_digest(fin, 'sha256').hexdigest() if sys.version_info >= (3, 11) else hashlib.sha256(fin.read()).hexdigest()
        output.with_suffix('.dmg.sha256').write_text(digest + '  ' + output.name + '\n', encoding='utf-8')
        print('✅ DMG de prueba:', output, flush=True)
        shared = Path('/Users/Shared') / output.name
        if shared.parent.is_dir() and os.access(shared.parent, os.W_OK):
            shutil.copy2(output, shared)
            print('✅ Copia compartida:', shared, flush=True)
        else:
            print('ℹ️ /Users/Shared no permite escribir; el DMG sigue en Descargas.', flush=True)
        print('SHA-256:', digest, flush=True)
        print('⚠️ Falta validar la nueva compilación en la cuenta de pruebas antes de publicar.', flush=True)


if __name__ == '__main__':
    try:
        build()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        print('❌ ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
