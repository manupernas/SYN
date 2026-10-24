#!/usr/bin/env python3
"""Independent macOS recording scheduler launched by launchd (not GTK).

This process keeps running when SYN Alpha.app closes. Uses upstream SYN DVR's
existing scheduler, lock, FFmpeg tee outputs, retries and job database.
"""
from __future__ import annotations
import os
import platform
import sys
from pathlib import Path


def main():
    if sys.platform != 'darwin' or platform.machine().lower() != 'arm64':
        raise SystemExit('El trabajador DVR solo funciona en macOS Apple Silicon.')
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'source'))
    data = Path.home() / 'Library' / 'Application Support' / 'SYN Alpha' / 'data'
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    data.chmod(0o700)
    os.environ['XDG_DATA_HOME'] = str(data)
    os.environ['PATH'] = '/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin'
    from syn_macos_dvr_support import video_directory, notify_transient
    import syn_dvr
    syn_dvr.video_directory = video_directory
    syn_dvr.notify_transient = notify_transient
    ffmpeg = Path('/opt/homebrew/bin/ffmpeg')
    if not ffmpeg.is_file() or not os.access(ffmpeg, os.X_OK):
        print('SYN DVR: falta FFmpeg ARM64 en /opt/homebrew/bin/ffmpeg', file=sys.stderr)
        return 78  # launchd retries; no data mutation before FFmpeg exists
    print('SYN macOS DVR: servicio independiente activo (FFmpeg sin recodificar)', flush=True)
    return syn_dvr.run_worker(poll_seconds=2)


if __name__ == '__main__':
    raise SystemExit(main())
