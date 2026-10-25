#!/bin/bash
# SYN 1.0 standalone beta - fresh macOS ARM64 runner; no private IPTV data.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
test "$(uname -s)" = Darwin
[ "$(uname -m)" = arm64 ] || { echo 'Se necesita macOS ARM64'; exit 1; }
[ -f macos/resources/source/syn.py ] && [ -f macos/resources/macos_alpha.py ] || {
  echo 'Falta el snapshot de código macOS'; exit 1;
}
[ -f macos/resources/SYN_Carta_Ajuste.icns ] || { echo 'Falta el icono'; exit 1; }
command -v brew >/dev/null
export HOMEBREW_NO_AUTO_UPDATE=1
PREFIX="$(brew --prefix)"
PYBIN="$PREFIX/bin/python3.15"
test -x "$PYBIN" || { echo 'Falta Homebrew python@3.15'; exit 1; }
"$PYBIN" -c 'import gi,cairo;gi.require_version("Gtk","4.0");gi.require_version("Adw","1");from gi.repository import Gtk,Adw; assert Gtk.get_major_version()==4'
PYCONFIG="$PREFIX/bin/python3.15-config"
test -x "$PYCONFIG"

# Staging is always temporary; no modifications to the installed /Applications/SYN.app.
TMP="$(mktemp -d "${TMPDIR:-/tmp}/syn1-standalone.XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT
APP="$TMP/SYN.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Frameworks" \
 "$APP/Contents/Resources" "$APP/Contents/Helpers" "$APP/Contents/Resources/bin"
ditto macos/resources/Info.plist "$APP/Contents/Info.plist"
for item in macos/resources/*; do
  test "$(basename "$item")" = Info.plist && continue
  ditto "$item" "$APP/Contents/Resources/$(basename "$item")"
done
# SYN branding lives at repository root, outside macos/resources.
for name in logo_dark_ui.png logo_light_ui.png icono_header_ui.png icono_3.png; do
  test -s "branding/$name" || { echo "Falta branding/$name" >&2; exit 1; }
done
ditto branding "$APP/Contents/Resources/source/branding"
for name in logo_dark_ui.png logo_light_ui.png icono_header_ui.png icono_3.png; do
  test -s "$APP/Contents/Resources/source/branding/$name" || {
    echo "ERROR: branding sin copiar: $name" >&2; exit 1;
  }
done
echo STANDALONE_BRANDING_OK
# Full CPython framework with stdlib/encodings/extension modules. Global Homebrew
# PyGObject/pycairo are installed outside the framework and copied separately.
FW_SRC="$(brew --prefix python@3.15)/Frameworks/Python.framework"
test -d "$FW_SRC/Versions/3.15/lib/python3.15"
ditto "$FW_SRC" "$APP/Contents/Frameworks/Python.framework"
"$PYBIN" - "$APP" <<'PY'
from pathlib import Path
import importlib, shutil, sys
app=Path(sys.argv[1]); dst=app/'Contents/Resources/python-site'
dst.mkdir(parents=True,exist_ok=True)
for module in ('gi','cairo'):
    m=importlib.import_module(module)
    source=Path(m.__file__).resolve().parent
    shutil.copytree(source,dst/module,dirs_exist_ok=True,symlinks=False)
print('PyGObject + pycairo bundled')
PY
# Cast dependency, installed exclusively into the staged app (never pip install globally).
"$PYBIN" -m pip install --disable-pip-version-check --no-input \
  --target "$APP/Contents/Resources/python-site" 'PyChromecast>=14,<16'
# Remove development/package metadata, never Python modules.
find "$APP/Contents/Resources/python-site" -type d \( -name __pycache__ -o -name '*.dist-info' \) -prune -exec rm -rf {} +

# Typelib lookup (GIRepository dlopen() needs these and their libraries).
mkdir -p "$APP/Contents/Resources/girepository-1.0"
for typepath in "$PREFIX/lib/girepository-1.0"/*.typelib; do
  test -f "$typepath" || continue
  cp "$typepath" "$APP/Contents/Resources/girepository-1.0/"
done
test -f "$APP/Contents/Resources/girepository-1.0/Gtk-4.0.typelib"
test -f "$APP/Contents/Resources/girepository-1.0/GLib-2.0.typelib"

# GTK assets, GLib schemas and dynamically loaded image modules.
mkdir -p "$APP/Contents/Resources/share/glib-2.0" "$APP/Contents/Resources/lib"
for component in icons gtk-4.0; do
  test -d "$PREFIX/share/$component" && \
    cp -RL "$PREFIX/share/$component" "$APP/Contents/Resources/share/$component"
done
if test -d "$PREFIX/share/glib-2.0/schemas"; then
  cp -RL "$PREFIX/share/glib-2.0/schemas" "$APP/Contents/Resources/share/glib-2.0/schemas"
  "$PREFIX/bin/glib-compile-schemas" "$APP/Contents/Resources/share/glib-2.0/schemas"
fi
if test -d "$PREFIX/lib/gdk-pixbuf-2.0/2.10.0/loaders"; then
  mkdir -p "$APP/Contents/Resources/lib/gdk-pixbuf-2.0/2.10.0"
  cp -RL "$PREFIX/lib/gdk-pixbuf-2.0/2.10.0/loaders" \
    "$APP/Contents/Resources/lib/gdk-pixbuf-2.0/2.10.0/loaders"
fi
if test -d "$PREFIX/lib/gio/modules"; then
  mkdir -p "$APP/Contents/Resources/lib/gio"
  cp -RL "$PREFIX/lib/gio/modules" "$APP/Contents/Resources/lib/gio/modules"
fi
# Bundled transcoder/recorder. The worker and Chromecast will discover it on PATH.
ditto "$PREFIX/bin/ffmpeg" "$APP/Contents/Resources/bin/ffmpeg"
chmod +x "$APP/Contents/Resources/bin/ffmpeg"
# Bridge layer for GDK loader cache + non-destructive DVR registration.
ditto macos/syn_macos_bootstrap.py "$APP/Contents/Resources/syn_macos_bootstrap.py"
"$PYBIN" macos/patch_staged_sources.py "$APP"

# Use the proven PyConfig/GLib preload architecture, but dynamically resolve
# Python, GI, FFmpeg and libmpv relative to SYN.app at runtime.
CFLAGS="$("$PYCONFIG" --embed --cflags)"
LDFLAGS="$("$PYCONFIG" --embed --ldflags)"
# shellcheck disable=SC2086
clang -O2 -arch arm64 -mmacosx-version-min=26.0 -Wl,-headerpad_max_install_names \
 -DSYN_PYTHON_HOME=\"embedded\" -DSYN_PYTHON_EXE=\"embedded\" \
 $CFLAGS macos/standalone_launcher.c -o "$APP/Contents/MacOS/SYN" $LDFLAGS
chmod +x "$APP/Contents/MacOS/SYN"

build_swift_app() {
  local folder="$1" exe="$2" swift="$3" bundle="$4"
  local dest="$APP/Contents/Helpers/$folder.app"
  mkdir -p "$dest/Contents/MacOS" "$dest/Contents/Resources"
  /usr/bin/xcrun swiftc -O -sdk "$(xcrun --sdk macosx --show-sdk-path)" \
    -target arm64-apple-macos26.0 \
    "macos/native/$swift" -o "$dest/Contents/MacOS/$exe"
  "$PYBIN" - "$dest/Contents/Info.plist" "$folder" "$exe" "$bundle" <<'PY'
import plistlib,sys
with open(sys.argv[1],'wb') as f:
    plistlib.dump({'CFBundleDevelopmentRegion':'en', 'CFBundleExecutable':sys.argv[3],
        'CFBundleIdentifier':sys.argv[4], 'CFBundleIconFile':'SYN_Carta_Ajuste.icns',
        'CFBundleName':sys.argv[2], 'CFBundleDisplayName':sys.argv[2],
        'CFBundlePackageType':'APPL','CFBundleShortVersionString':'1.0.0',
        'CFBundleVersion':'10000','LSMinimumSystemVersion':'26.0'},f)
PY
  ditto macos/resources/SYN_Carta_Ajuste.icns "$dest/Contents/Resources/SYN_Carta_Ajuste.icns"
}
build_swift_app 'SYN Notifications' SYNNotify SYNNotify.swift com.mrseivane.syn.notifications

# Rewrite all Mach-O links, including Python extensions and dynamically
# dlopen()-ed GTK/GLib/Pixbuf libraries; reject any remaining /opt/homebrew/ LC_LOAD.
"$PYBIN" macos/macho_relocate.py "$APP"

# Reject symlinks accidentally pointing back to the runner Homebrew tree.
"$PYBIN" - "$APP" <<'PYCODE'
from pathlib import Path
import sys
app=Path(sys.argv[1]).resolve()
for p in app.rglob('*'):
  if p.is_symlink():
    target=p.resolve()
    if not target.is_relative_to(app):
      raise SystemExit(f'External symlink in standalone app: {p} -> {target}')
print('STANDALONE_SYMLINKS_OK')
PYCODE

# Generate the Pixbuf cache *after* dylibs have been relocated; replace the
# staging app path with a token expanded by syn_macos_bootstrap.py at runtime.
LOADERS=("$APP"/Contents/Resources/lib/gdk-pixbuf-2.0/2.10.0/loaders/*.so)
if test -f "${LOADERS[0]}"; then
  "$PREFIX/bin/gdk-pixbuf-query-loaders" "${LOADERS[@]}" \
    > "$APP/Contents/Resources/gdk-pixbuf.loaders.template"
  "$PYBIN" - "$APP/Contents/Resources/gdk-pixbuf.loaders.template" "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text('utf-8')
if sys.argv[2] not in s: raise SystemExit('Pixbuf cache sin rutas de los módulos')
p.write_text(s.replace(sys.argv[2], '__SYN_APP_PATH__'))
PY
fi

# An app produced on a macOS 26 Homebrew runner contains bottles built for
# macOS 26: report the honest minimum instead of promising unsupported macOS 14.
/usr/libexec/PlistBuddy -c 'Set :LSMinimumSystemVersion 26.0' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 1.0.0' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleName SYN' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleDisplayName SYN' "$APP/Contents/Info.plist"

# Sign ad hoc only (not Apple Developer ID/notarization).
# IMPORTANT: Mach-O extensions in Resources/python-site (PyGObject, pycairo,
# zeroconf, protobuf, etc.) must be signed individually, not just bundled.
# A clean DMG can pass --deep while dyld kills an unsigned Python .so on
# the installed Mac with CODESIGNING/Invalid Page.
# Make a manifest of EVERY native Mach-O, independent of filename suffix.
NATIVE_MANIFEST="$TMP/syn-native-machos.bin"
"$PYBIN" - "$APP" "$NATIVE_MANIFEST" <<'PY_NATIVE_MANIFEST'
from pathlib import Path
import os, sys
app, manifest = Path(sys.argv[1]), Path(sys.argv[2])
MAGIC = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
         b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
         b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}
with manifest.open('wb') as out:
    for p in sorted(app.rglob('*')):
        if p.is_symlink() or not p.is_file():
            continue
        with p.open('rb') as f:
            if f.read(4) in MAGIC:
                out.write(os.fsencode(p) + b'\0')
print('STANDALONE_NATIVE_MANIFEST_OK')
PY_NATIVE_MANIFEST

signed_count=0
while IFS= read -r -d '' binary; do
  # Never suppress signing failures: missing signatures become runtime crashes.
  codesign --force --sign - --timestamp=none "$binary" >/dev/null
  signed_count=$((signed_count + 1))
done < "$NATIVE_MANIFEST"
test "$signed_count" -gt 150 || {
  echo "❌ Solo $signed_count binarios nativos; empaquetado incompleto" >&2
  exit 1
}
for helper in "$APP/Contents/Helpers"/*.app; do
  codesign --force --deep --sign - --timestamp=none "$helper"
done
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --verbose=2 "$APP"
# Bundle executables (SYN, helpers and Python.framework) are validated
# by codesign --verify --deep on the enclosing .app. Verify loadable leaf
# libraries individually: these are dlopen()-ed and were invalid on the Mac.
# Never run bare-file --strict verification on a framework's main executable:
# codesign treats it as bundle code and may return ENOENT spuriously.
while IFS= read -r -d '' binary; do
  case "$binary" in
    *.dylib|*.so|"$APP/Contents/Resources/bin/ffmpeg") ;;
    *) continue ;;
  esac
  if ! codesign --verify --strict "$binary" >/dev/null 2>&1; then
    echo "❌ Firma nativa inválida: $binary" >&2
    codesign --verify --strict --verbose=2 "$binary" >&2 || true
    exit 1
  fi
done < "$NATIVE_MANIFEST"
printf 'STANDALONE_NATIVE_SIGNATURES_OK %s\n' "$signed_count"
"$APP/Contents/MacOS/SYN" --syn-bootstrap-check | grep SYN_NATIVE_GTK_OK
# The bootstrap must not mutate any resource after signing.
codesign --verify --deep --verbose=2 "$APP"
echo STANDALONE_POST_BOOTSTRAP_SIGNATURE_OK
# No staged Mach-O is permitted to reference the developer Homebrew prefix.
"$PYBIN" - "$APP" <<'PY'
from pathlib import Path
import subprocess,sys
app=Path(sys.argv[1]); count=0
for p in app.rglob('*'):
  if not p.is_file() or p.is_symlink(): continue
  with p.open('rb') as f: magic=f.read(4)
  if magic not in (b'\xfe\xed\xfa\xce',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):continue
  out=subprocess.run(['/usr/bin/otool','-L',str(p)],capture_output=True,text=True,check=True).stdout
  if '\t/opt/homebrew/' in out:raise SystemExit(f'REFUSES external Homebrew dylib: {p}')
  count+=1
print(f'STANDALONE_MACHO_VALIDATION_OK: {count} files')
PY
mkdir -p dist "$TMP/dmg"
ditto "$APP" "$TMP/dmg/SYN.app"
for name in logo_dark_ui.png logo_light_ui.png icono_header_ui.png icono_3.png; do
  test -s "$TMP/dmg/SYN.app/Contents/Resources/source/branding/$name" || {
    echo "ERROR: logo ausente del DMG: $name" >&2; exit 1;
  }
done
echo STANDALONE_DMG_BRANDING_OK
# Recheck the precise bytes that will go into the disk image.
codesign --verify --deep --verbose=2 "$TMP/dmg/SYN.app"
# Verify also every Mach-O in the exact copied payload that goes into the DMG.
while IFS= read -r -d '' binary; do
  case "$binary" in
    *.dylib|*.so|"$APP/Contents/Resources/bin/ffmpeg") ;;
    *) continue ;;
  esac
  relative="${binary#"$APP"/}"
  test "$relative" != "$binary" || { echo "ERROR: ruta fuera de SYN.app: $binary" >&2; exit 1; }
  copied="$TMP/dmg/SYN.app/$relative"
  if ! codesign --verify --strict "$copied" >/dev/null 2>&1; then
    echo "❌ Firma inválida en DMG: $copied" >&2
    codesign --verify --strict --verbose=2 "$copied" >&2 || true
    exit 1
  fi
done < "$NATIVE_MANIFEST"
echo STANDALONE_DMG_NATIVE_SIGNATURES_OK
echo STANDALONE_DMG_CONTENT_SIGNATURE_OK
ln -s /Applications "$TMP/dmg/Applications"
DMG="$ROOT/dist/SYN-1.0-macOS-arm64-autonomo-beta.dmg"
rm -f "$DMG"
hdiutil create -quiet -ov -volname 'SYN 1.0' -srcfolder "$TMP/dmg" -format UDZO "$DMG"
hdiutil verify "$DMG" >/dev/null
printf 'STANDALONE_DMG_BETA_OK %s\n' "$DMG"
echo 'ATENCION: Firma ad hoc, sin notarizar; confirmar instalacion en Mac limpio.'
