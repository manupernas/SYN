#!/usr/bin/env python3
"""SYN DVR optional commercials remover. NEVER writes to / replaces input.

Args: original-video comskip ffmpeg ffprobe
Prints OK|<path>, NONE|<message>, or ERROR|<message>.
Requires a working Comskip build and FFmpeg binaries installed on host.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(argv: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          check=False, stdin=subprocess.DEVNULL)


def duration_of(path: Path, ffprobe: str) -> float:
    p = run([ffprobe, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], timeout=90)
    if p.returncode != 0:
        raise RuntimeError('FFprobe no pudo leer la duración del vídeo.')
    try:
        value = float(p.stdout.strip())
    except ValueError:
        raise RuntimeError('El vídeo no tiene una duración válida.') from None
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError('Duración de vídeo no válida.')
    return value


def parse_edl(path: Path, duration: float) -> list[tuple[float, float]]:
    intervals = []
    for raw in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        fields = raw.strip().split()
        if len(fields) < 3 or fields[2] != '0':
            continue
        try:
            start, end = float(fields[0]), float(fields[1])
        except ValueError:
            continue
        if not math.isfinite(start) or not math.isfinite(end):
            continue
        start, end = max(0., start), min(duration, end)
        if end > start + 0.3:
            intervals.append((start, end))
    intervals.sort()
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1] + 0.1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def keep_ranges(cuts: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    keep = []
    pos = 0.
    for start, end in cuts:
        if start - pos >= 0.4:
            keep.append((pos, start))
        pos = max(pos, end)
    if duration - pos >= 0.4:
        keep.append((pos, duration))
    return keep


def unique_output(original: Path) -> Path:
    root = original.parent / f'{original.stem} - sin anuncios.mkv'
    if not root.exists():
        return root
    for i in range(2, 1000):
        candidate = original.parent / f'{original.stem} - sin anuncios {i}.mkv'
        if not candidate.exists():
            return candidate
    raise RuntimeError('Demasiadas copias existentes; cambia de carpeta.')


def process(video: Path, comskip: str, ffmpeg: str, ffprobe: str) -> tuple[str, str]:
    if not video.is_file() or video.suffix.lower() not in {'.mkv', '.mp4', '.ts', '.mov'}:
        raise RuntimeError('Archivo original no disponible o formato no compatible.')
    total = duration_of(video, ffprobe)
    if total < 120:
        return ('NONE', 'La grabación es demasiado corta para buscar cortes.')
    # Comskip and segments work in isolated folders, not beside the source.
    with tempfile.TemporaryDirectory(prefix='syn-dvr-ads-') as scratch:
        root = Path(scratch)
        ini = root / 'comskip.ini'
        ini.write_text('output_default=0\noutput_edl=1\nverbose=0\n', encoding='utf-8')
        analysed = run([comskip, f'--ini={ini}', f'--output={root}', str(video)], timeout=14400)
        if analysed.returncode != 0:
            short = (analysed.stderr or analysed.stdout or '').strip()[-240:]
            raise RuntimeError('Comskip no pudo analizar el vídeo. ' + short)
        edl_files = sorted(root.glob('*.edl'))
        if not edl_files:
            return ('NONE', 'Comskip no detectó pausas comerciales.')
        cuts = parse_edl(edl_files[0], total)
        if not cuts:
            return ('NONE', 'No se detectaron cortes comerciales fiables.')
        kept = keep_ranges(cuts, total)
        seconds = sum(end-start for start,end in kept)
        removed = total-seconds
        # Refuse excessive cuts: a false positive should never silently gut a program.
        if not kept or seconds < 60 or removed / total > 0.55:
            raise RuntimeError('Detección dudosa: se canceló para proteger el contenido.')
        if len(kept) > 80:
            raise RuntimeError('Demasiados cortes; se canceló por seguridad.')
        paths = []
        for i, (start, end) in enumerate(kept):
            piece = root / f'segment-{i:03d}.mkv'
            result = run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin',
                          '-i', str(video), '-ss', f'{start:.3f}', '-t', f'{end-start:.3f}',
                          '-map', '0', '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                          '-y', str(piece)], timeout=7200)
            if result.returncode != 0 or not piece.is_file() or piece.stat().st_size == 0:
                raise RuntimeError('FFmpeg no pudo generar un tramo: ' + result.stderr.strip()[-200:])
            paths.append(piece)
        concat = root / 'unir.txt'
        concat.write_text(''.join("file '" + p.as_posix() + "'\n" for p in paths), encoding='utf-8')
        output = unique_output(video)
        # Use temporary final in recording's folder for atomic rename and no source mutation.
        partial = output.with_name('.syn-dvr-' + os.urandom(8).hex() + '.mkv')
        try:
            result = run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin',
                          '-f', 'concat', '-safe', '0', '-i', str(concat),
                          '-map', '0', '-c', 'copy', '-y', str(partial)], timeout=7200)
            if result.returncode != 0 or not partial.is_file() or partial.stat().st_size == 0:
                raise RuntimeError('No se pudo unir el vídeo: ' + result.stderr.strip()[-200:])
            actual_length = duration_of(partial, ffprobe)
            if abs(actual_length - seconds) > max(12.0, seconds * 0.08):
                raise RuntimeError('La duración del montaje no coincide con los cortes. Se ha descartado.')
            # Selected output is always different from original.
            if output.exists():
                output = unique_output(video)
            os.rename(partial, output)
            return ('OK', str(output))
        finally:
            partial.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 5:
        print('ERROR|Argumentos incorrectos.')
        return 2
    try:
        status, message = process(Path(sys.argv[1]).expanduser(), *sys.argv[2:])
        print(status + '|' + message)
        return 0 if status in ('OK', 'NONE') else 1
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
        print('ERROR|' + str(exc).replace('\n', ' ')[:360])
        return 1


if __name__ == '__main__':
    sys.exit(main())
