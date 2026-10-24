#!/usr/bin/env python3
"""SYN 2.0.7 macOS ARM64 Alpha 3: GTK/MPV frontend + launchd DVR.

Retains the validated Alpha 2 native GL bridge and private Alpha profile
store. The independent scheduler is handled by mac_dvr_worker.py via launchd.
"""
from __future__ import annotations
import ctypes
import os
import platform
import subprocess
import sys
from pathlib import Path

VERSION = '1.0.0'


def main():
    if sys.platform != 'darwin' or platform.machine().lower() != 'arm64':
        raise SystemExit('SYN macOS Alpha requiere Apple Silicon (ARM64).')
    # SYN_MAC_574_PROCESS_NAME: native menu-bar identity.
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'source'))
    from syn_mac_identity import set_process_name
    set_process_name('SYN')
    import gi, cairo
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw
    if Gtk.get_major_version() != 4:
        raise SystemExit('Se necesita GTK4.')
    resources = Path(__file__).resolve().parent
    source = resources / 'source'
    if not (source / 'syn_macos_gl.py').is_file():
        raise SystemExit('No está instalado el puente OpenGL macOS de Alpha 2.')
    sys.path.insert(0, str(source))
    private = Path.home() / 'Library' / 'Application Support' / 'SYN Alpha'
    config, cache, data = (private / p for p in ('config', 'cache', 'data'))
    for directory in (config, cache, data):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    os.umask(0o077)
    os.environ['XDG_DATA_HOME'] = str(data)
    os.environ['XDG_STATE_HOME'] = str(data / 'state')
    os.environ['SYN_DISABLE_SERVICE_AUTOSTART'] = '1'
    os.environ.setdefault('IPTV_ENABLE_GL_FENCES', '1')
    os.environ['PATH'] = '/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin'
    # Same .dylib candidates as validated Alpha 2; do not regress playback.
    candidates = (
        '/opt/homebrew/opt/mpv/lib/libmpv.dylib',
        '/opt/homebrew/lib/libmpv.dylib',
        '/opt/homebrew/opt/mpv/lib/libmpv.2.dylib',
        '/opt/homebrew/lib/libmpv.2.dylib',
    )
    lib = None
    for candidate in candidates:
        try:
            if Path(candidate).is_file():
                ctypes.CDLL(candidate).mpv_create
                lib = candidate
                break
        except (OSError, AttributeError):
            pass
    if lib is None:
        raise SystemExit('Falta libmpv ARM64: brew install mpv')
    os.environ['SYN_MACOS_LIBMPV'] = lib

    import syn_sources
    syn_sources.APP_CONFIG = config
    syn_sources.APP_CACHE = cache
    syn_sources.CONFIG_FILE = config / 'profiles.json'
    import syn_dvr
    from syn_macos_dvr_support import video_directory, notify_transient
    syn_dvr.video_directory = video_directory
    syn_dvr.notify_transient = notify_transient
    import syn_service_setup
    # macOS LaunchAgent is installed outside GTK and must outlive the window.
    syn_service_setup.ensure_services_async = lambda: None
    import syn_mac_cast_launcher
    syn_mac_cast_launcher.ensure_running(source)
    import syn
    if syn.SYN_VERSION != VERSION:
        raise SystemExit('SYN no es la versión base ' + VERSION)
    print('SYN macOS Alpha 5 · Chromecast + DVR launchd', flush=True)
    print('libmpv ARM64:', lib, flush=True)
    os.chdir(source)
    sys.argv = [str(source / 'syn.py'), *sys.argv[1:]]
    return int(syn.main() or 0)


if __name__ == '__main__':
    raise SystemExit(main())
