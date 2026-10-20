#!/usr/bin/env python3
"""Preparar una release de SYN; seis nativos obligatorios, extras por parejas.

Nunca publica un artefacto suelto de una única arquitectura opcional.
Genera SHA256SUMS.txt de los ficheros realmente seleccionados y notas coherentes.
"""
import hashlib
import os
from pathlib import Path
import re
import sys


def prepare(directory: Path, notes_source: Path, notes_destination: Path, tag: str):
    version = tag.removeprefix('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Versión de etiqueta inválida: ' + tag)
    if not directory.is_dir():
        raise ValueError('No existe la carpeta con artefactos')
    required = [
        f'syn-iptv-{version}-1.x86_64.rpm',
        f'syn-iptv-{version}-1.aarch64.rpm',
        f'syn-iptv_{version}-1_amd64.deb',
        f'syn-iptv_{version}-1_arm64.deb',
        f'syn-iptv-{version}-1-x86_64.pkg.tar.zst',
        f'syn-iptv-{version}-1-aarch64.pkg.tar.zst',
    ]
    missing = [name for name in required if not (directory / name).is_file() or (directory / name).stat().st_size < 1024]
    if missing:
        raise ValueError('Faltan paquetes NATIVOS obligatorios: ' + ', '.join(missing))

    optional = {
        'Flatpak': [f'SYN-{version}-x86_64.flatpak', f'SYN-{version}-aarch64.flatpak'],
        'AppImage': [f'SYN-{version}-x86_64.AppImage', f'SYN-{version}-aarch64.AppImage'],
    }
    allowed = set(required)
    for pair in optional.values():
        allowed.update(pair)
    unknown = sorted(p.name for p in directory.iterdir() if p.name not in allowed)
    if unknown:
        raise ValueError('Artefactos desconocidos o sobrantes: ' + ', '.join(unknown))

    included = []
    omitted = []
    for label, pair in optional.items():
        if all((directory / file).is_file() and (directory / file).stat().st_size >= 1024 for file in pair):
            included.append(label)
        else:
            # Solo limpiar extras DESPUÉS de validar los seis obligatorios.
            for name in pair:
                (directory / name).unlink(missing_ok=True)
            omitted.append(label)

    published = sorted(p for p in directory.iterdir() if p.is_file())
    assert len(published) in (6, 8, 10), f'Tamaño de Release inesperado: {len(published)}'
    checksum_lines = []
    for p in published:
        with p.open('rb') as fp:
            digest = hashlib.file_digest(fp, 'sha256').hexdigest()
        checksum_lines.append(f'{digest}  {p.name}')
    (directory / 'SHA256SUMS.txt').write_text('\n'.join(checksum_lines) + '\n', encoding='utf-8')
    base_notes = notes_source.read_text(encoding='utf-8')
    status = [
        '', '## Resultado real de la compilación',
        f'**{len(published)} paquetes publicados** (siempre los seis nativos RPM, DEB y Pacman para x86_64 y ARM64).',
    ]
    for label in optional:
        if label in included:
            status.append(f'- **{label}:** incluidos x86_64 y ARM64.')
        else:
            status.append(f'- **{label}:** excluidos de esta Release; no se completaron correctamente ambas arquitecturas.')
    status.append('Todos los archivos publicados figuran en `SHA256SUMS.txt`.')
    notes_destination.write_text(base_notes.rstrip() + '\n' + '\n'.join(status) + '\n', encoding='utf-8')
    print('RELEASE:')
    for p in sorted(directory.iterdir()):
        print(' ', p.name, p.stat().st_size, 'bytes')
    print('Incluidos:', ', '.join(included) or '(ningún opcional)')
    print('Omitidos:', ', '.join(omitted) or '(ninguno)')
    return [p.name for p in published]


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Uso: prepare-release.py <artefactos> <notas originales> <notas generadas>')
    try:
        prepare(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), os.environ['SYN_RELEASE_VERSION'])
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
