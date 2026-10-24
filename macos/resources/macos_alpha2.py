#!/usr/bin/env python3
"""SYN macOS ARM64 Alpha 2 — experimental integrated libmpv + GTK GLArea.

Data is shared with Alpha 1 (own macOS profile store). This is an isolated
Apple Silicon development port of upstream v2.0.7, not a finished release.
"""
from __future__ import annotations
import os
import platform
import sys
from pathlib import Path

VERSION='2.0.7'

def setup_libmpv() -> str:
    candidates = [
        Path('/opt/homebrew/opt/mpv/lib/libmpv.dylib'),
        Path('/opt/homebrew/lib/libmpv.dylib'),
        Path('/opt/homebrew/opt/mpv/lib/libmpv.2.dylib'),
        Path('/opt/homebrew/lib/libmpv.2.dylib'),
    ]
    import ctypes
    for path in candidates:
        if path.is_file():
            try:
                lib=ctypes.CDLL(str(path))
                getattr(lib, 'mpv_create')
                return str(path)
            except (OSError, AttributeError):
                continue
    raise SystemExit('No se pudo abrir libmpv ARM64. Prueba: brew reinstall mpv')

def main():
    if sys.platform != 'darwin' or platform.machine().lower() != 'arm64':
        raise SystemExit('Solo para macOS Apple Silicon (ARM64).')
    import gi, cairo
    gi.require_version('Gtk','4.0');gi.require_version('Adw','1')
    from gi.repository import Gtk, Adw, Gdk
    if Gtk.get_major_version()!=4:
        raise SystemExit('Se necesita GTK 4.')
    base=Path(__file__).resolve().parent
    src=base/'source'
    if not (src/'syn.py').is_file():
        raise SystemExit('Código de SYN ausente en la aplicación.')
    sys.path.insert(0,str(src))
    # Strictly isolate all IPTV credentials, logos and DVR state from Linux.
    private=Path.home()/'Library'/'Application Support'/'SYN Alpha'
    config,cache,data=private/'config',private/'cache',private/'data'
    for p in (config,cache,data):
        p.mkdir(mode=0o700,parents=True,exist_ok=True)
        p.chmod(0o700)
    os.environ['XDG_DATA_HOME']=str(data)
    os.environ['XDG_STATE_HOME']=str(data/'state')
    os.environ['SYN_DISABLE_SERVICE_AUTOSTART']='1'
    os.environ['SYN_MACOS_LIBMPV']=setup_libmpv()
    # Avoid hardware decoder/Apple GL interop on first test. Software
    # decode can be enabled from preferences after the renderer works.
    os.environ.setdefault('IPTV_ENABLE_GL_FENCES','1')
    import syn_sources
    syn_sources.APP_CONFIG=config
    syn_sources.APP_CACHE=cache
    syn_sources.CONFIG_FILE=config/'profiles.json'
    import syn
    if syn.SYN_VERSION!=VERSION:
        raise SystemExit('Versión base incorrecta: '+syn.SYN_VERSION)
    import syn_dvr, syn_service_setup
    syn_service_setup.ensure_services_async=lambda:None
    syn_dvr.ensure_worker=lambda *args,**kwargs:'unavailable'
    syn_dvr.notify_transient=lambda *args,**kwargs:None
    # We intentionally do not start the Linux systemd/Flatpak Cast bridge.
    # The experimental render path uses SYN's original Gtk.GLArea.
    print('SYN '+VERSION+' · macOS Alpha 2 · prueba de vídeo integrado',flush=True)
    print('MPV: '+os.environ['SYN_MACOS_LIBMPV'],flush=True)
    print('DVR y servicios Cast: no disponibles en Alpha 2',flush=True)
    os.chdir(src)
    sys.argv=[str(src/'syn.py')]+sys.argv[1:]
    return int(syn.main() or 0)

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
