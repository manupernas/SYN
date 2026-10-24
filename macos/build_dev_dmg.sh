#!/bin/bash
# SYN 1.0: experimental Homebrew-dependent DMG; NOT a self-contained release.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
[ "$(uname -s)" = Darwin ] || { echo 'Solo macOS'; exit 1; }
[ "$(uname -m)" = arm64 ] || { echo 'Se necesita runner ARM64'; exit 1; }
[ -f macos/resources/macos_alpha.py ] || { echo 'Falta el código real de SYN para macOS'; exit 1; }
[ -f macos/resources/source/syn.py ] || { echo 'Falta syn.py'; exit 1; }
[ -f macos/resources/Info.plist ] || { echo 'Falta Info.plist'; exit 1; }
command -v brew >/dev/null || { echo 'Falta Homebrew'; exit 1; }
for formula in glib mpv gtk4 libadwaita gobject-introspection; do
  brew list --versions "$formula" >/dev/null || { echo "Falta brew $formula"; exit 1; }
done

PYBIN="$(/usr/bin/python3 - <<'PY'
import subprocess
candidates=['/opt/homebrew/bin/python3.15','/opt/homebrew/bin/python3','/opt/homebrew/bin/python3.14']
for candidate in candidates:
    code="import gi,cairo;gi.require_version('Gtk','4.0');gi.require_version('Adw','1');from gi.repository import Gtk,Adw;assert Gtk.get_major_version()==4"
    try:
        r=subprocess.run([candidate,'-c',code],capture_output=True,text=True,timeout=15)
        if r.returncode==0:
            print(candidate)
            break
    except (OSError,subprocess.TimeoutExpired):pass
PY
)"
[ -n "$PYBIN" ] || { echo 'Ningún Python de Homebrew importa PyGObject/GTK4/Adw/cairo'; exit 1; }

PYCONF="$("$PYBIN" - <<'PY'
import pathlib,sys,sysconfig
v=f'{sys.version_info.major}.{sys.version_info.minor}'
candidates=[pathlib.Path(sysconfig.get_config_var('BINDIR') or '')/f'python{v}-config',
            pathlib.Path(sys.executable).parent/f'python{v}-config',
            pathlib.Path('/opt/homebrew/bin')/f'python{v}-config']
print(next((str(p) for p in candidates if p.is_file()),''))
PY
)"
[ -n "$PYCONF" ] || { echo 'Falta python-config del mismo intérprete'; exit 1; }
PYEXE="$("$PYBIN" -c 'import sys;print(sys.executable)')"
PYHOME="$("$PYBIN" -c 'import sys;print(sys.prefix)')"
GLIBDIR="$(brew --prefix glib)/lib"
[ -f "$GLIBDIR/libglib-2.0.0.dylib" ] || { echo 'Falta GLib dylib'; exit 1; }

ROOT_TMP="$(mktemp -d "${TMPDIR:-/tmp}/syn1-build.XXXXXX")"
trap 'rm -rf "$ROOT_TMP"' EXIT
APP="$ROOT_TMP/SYN.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
ditto macos/resources/Info.plist "$APP/Contents/Info.plist"
for item in macos/resources/*; do
  [ "$(basename "$item")" = Info.plist ] && continue
  ditto "$item" "$APP/Contents/Resources/$(basename "$item")"
done

# Compile the proven PyConfig + GLib preload launcher for this runner.
mapfile_compat() { :; }
CFLAGS="$("$PYCONF" --embed --cflags)"
LDFLAGS="$("$PYCONF" --embed --ldflags)"
# python-config flags are provided by Python itself; no untrusted text inputs.
# shellcheck disable=SC2086
clang -O2 -arch arm64 -mmacosx-version-min=14.0 \
 -DSYN_PYTHON_HOME=\"$PYHOME\" -DSYN_PYTHON_EXE=\"$PYEXE\" -DSYN_GLIB_DIR=\"$GLIBDIR\" \
 $CFLAGS macos/native/syn_launcher.c -o "$APP/Contents/MacOS/SYN" $LDFLAGS
chmod 755 "$APP/Contents/MacOS/SYN"
"$APP/Contents/MacOS/SYN" --syn-bootstrap-check | grep -q SYN_NATIVE_GTK_OK || {
  echo 'El nuevo lanzador no puede cargar GTK en el runner'; exit 1;
}

# Native helper sources are bundled for further integration; the present DMG
# still expects Homebrew and does not install the independent DVR LaunchAgent.
mkdir -p "$APP/Contents/Resources/native"
ditto macos/native "$APP/Contents/Resources/native"

/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 1.0.0' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleVersion 10000' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleName SYN' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleDisplayName SYN' "$APP/Contents/Info.plist"
codesign --force --deep --sign - "$APP" >/dev/null
codesign --verify --deep "$APP"
mkdir -p dist "$ROOT_TMP/dmg"
ditto "$APP" "$ROOT_TMP/dmg/SYN.app"
ln -s /Applications "$ROOT_TMP/dmg/Applications"
DMG="$ROOT/dist/SYN-1.0-macOS-arm64.dmg"
rm -f "$DMG"
hdiutil create -quiet -ov -volname 'SYN 1.0' -srcfolder "$ROOT_TMP/dmg" -format UDZO "$DMG"
hdiutil verify "$DMG" >/dev/null
printf 'DMG generado: %s\n' "$DMG"
echo 'AVISO: DMG experimental; necesita Homebrew y aún no incluye runtime independiente ni servicio DVR.'
