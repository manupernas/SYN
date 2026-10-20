#!/usr/bin/env bash
# AppImage experimental GTK4/PyGObject/libmpv: empaquetado nativo en Ubuntu 24.04.
set -euo pipefail
VERSION="${1:?versión}"
ARCH="${2:?x86_64 o aarch64}"
ROOT="$(cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ "$ARCH" == x86_64 || "$ARCH" == aarch64 ]] || exit 2
case "$(uname -m)" in "$ARCH") ;; *) echo 'Es necesario un runner nativo' >&2; exit 2;; esac
multiarch="$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
pyver="$(/usr/bin/python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
DIR="$ROOT/.AppDir"
rm -rf "$DIR"
mkdir -p "$DIR/usr/bin" "$DIR/usr/lib/$multiarch" "$DIR/usr/share" "$DIR/usr/lib/python3/dist-packages" "$DIR/usr/lib/$pyver" "$ROOT/dist"
# El contenido de usuario no se toca ni se empaqueta.
bash packaging/stage-native.sh "$DIR" >/dev/null
cp -L /usr/bin/python3 "$DIR/usr/bin/python3"
cp -L "$(command -v ffmpeg)" "$DIR/usr/bin/ffmpeg"
cp -a "/usr/lib/$pyver/." "$DIR/usr/lib/$pyver/"
rm -rf "$DIR/usr/lib/$pyver/test" "$DIR/usr/lib/$pyver/ensurepip" "$DIR/usr/lib/$pyver/idlelib"
cp -a /usr/lib/python3/dist-packages/gi "$DIR/usr/lib/python3/dist-packages/"
if [[ -d /usr/lib/python3/dist-packages/cairo ]]; then
  cp -a /usr/lib/python3/dist-packages/cairo "$DIR/usr/lib/python3/dist-packages/"
fi
if [[ -d /usr/lib/python3/dist-packages/gi/overrides ]]; then
  : # GTK4/PyGObject overrides ya incluidos
fi
mkdir -p "$DIR/usr/lib/$multiarch/girepository-1.0"
cp -a "/usr/lib/$multiarch/girepository-1.0/." "$DIR/usr/lib/$multiarch/girepository-1.0/"
# Se distribuyen recursos GLib y pixbuf necesarios para GTK4 (no GTK2/3).
mkdir -p "$DIR/usr/share/glib-2.0/schemas"
cp -a /usr/share/glib-2.0/schemas/*.xml "$DIR/usr/share/glib-2.0/schemas/"
glib-compile-schemas "$DIR/usr/share/glib-2.0/schemas"
if [[ -d "/usr/lib/$multiarch/gdk-pixbuf-2.0" ]]; then
  cp -a "/usr/lib/$multiarch/gdk-pixbuf-2.0" "$DIR/usr/lib/$multiarch/"
fi
for res in /usr/share/icons/Adwaita /usr/share/icons/hicolor; do
  if [[ -d "$res" ]]; then
    mkdir -p "$DIR/usr/share/icons/$(basename "$res")"
    cp -an "$res/." "$DIR/usr/share/icons/$(basename "$res")/" || true
  fi
done
# La distribución determina la ruta de la librería; ctypes.find_library()
# no busca en el AppDir si la máquina huésped no tiene libmpv instalada.
libmpv="$(ldconfig -p | awk '/libmpv.so.[0-9]+ \(/ {print $NF; exit}')"
[[ -f "$libmpv" ]] || { echo 'Falta libmpv para AppImage' >&2; exit 2; }
# Resolución de dependencias ELF de modo recursivo. No empaquetar libc ni GL
# del host: los controladores OpenGL/VirGL necesitan la pila gráfica instalada.
export APPDIR="$DIR" MULTIARCH="$multiarch" LIBMPV="$libmpv"
python3 - <<'PY'
import os, pathlib, subprocess, shutil, re
D=pathlib.Path(os.environ['APPDIR']); arch=os.environ['MULTIARCH']
libdir=D/'usr/lib'/arch
origlib=pathlib.Path(os.environ['LIBMPV'])
shutil.copy2(origlib.resolve(),libdir/origlib.name)
# El nombre libmpv.so.2 debe existir para dependencias dinámicas.
if not (libdir/'libmpv.so.2').exists():
    (libdir/'libmpv.so.2').symlink_to(origlib.name)
roots=[D/'usr/bin/python3',D/'usr/bin/ffmpeg',libdir/origlib.name]
roots += list((D/'usr/lib/python3/dist-packages').rglob('*.so'))
roots += list((D/'usr/lib'/arch/'gdk-pixbuf-2.0').rglob('*.so'))
roots += list((D/'usr/lib'/arch).glob('*.so*'))
# Los typelibs cargan estas bibliotecas dinámicamente; ldd no las detecta.
for soname in ['libgtk-4.so.1','libadwaita-1.so.0','libgirepository-1.0.so.1',
               'libgdk_pixbuf-2.0.so.0','libgio-2.0.so.0','libpango-1.0.so.0',
               'libglib-2.0.so.0','libgobject-2.0.so.0','libcairo.so.2']:
    out=subprocess.check_output(['ldconfig','-p'],text=True)
    cand=next((l.rsplit('=>',1)[1].strip() for l in out.splitlines() if l.strip().startswith(soname+' ')),None)
    if not cand: raise SystemExit('Falta biblioteca requerida: '+soname)
    p=pathlib.Path(cand)
    if not (libdir/p.name).exists(): shutil.copy2(p.resolve(),libdir/p.name)
    roots.append(libdir/p.name)
seen=set()
exclude=re.compile(r'^(?:libc\.so\.|libm\.so\.|libpthread\.so\.|libdl\.so\.|librt\.so\.|libresolv\.so\.|ld-linux|libGL(?:X|dispatch)?\.so\.|libEGL\.so\.|libnss_)')
queue=list(roots)
while queue:
    p=queue.pop()
    if not p.is_file() or p in seen: continue
    seen.add(p)
    try:
        out=subprocess.check_output(['ldd',str(p)],stderr=subprocess.STDOUT,text=True)
    except subprocess.CalledProcessError:
        continue
    for line in out.splitlines():
        if '=> not found' in line: raise SystemExit('Dependencia ELF ausente: '+line)
        m=re.search(r'=>\s+(/\S+)',line)
        if not m: continue
        origin=pathlib.Path(m.group(1))
        if exclude.match(origin.name): continue
        dst=libdir/origin.name
        if not dst.exists(): shutil.copy2(origin.resolve(),dst)
        queue.append(dst)
print('Dependencias ELF empaquetadas:',len(seen))
PY
# Corregir solo la copia de AppImage. No modificar SYN instalado ni el repo.
python3 - <<'PY'
from pathlib import Path
p=Path('.AppDir/usr/share/syn/syn.py')
s=p.read_text()
old='library = ctypes.util.find_library("mpv")'
assert s.count(old)==1,'Cambió NativeMpv: revisar la biblioteca de AppImage'
p.write_text(s.replace(old,'library = os.environ.get("SYN_LIBMPV") or ctypes.util.find_library("mpv")'))
PY
rm -rf "$DIR/usr/lib/systemd" # service native only: AppImage uses installer below
cp "com.mrseivane.Syn.desktop" "$DIR/com.mrseivane.Syn.desktop"
sed -i 's@^Exec=.*@Exec=AppRun@' "$DIR/com.mrseivane.Syn.desktop"
cp "icons/256x256/apps/com.mrseivane.Syn.png" "$DIR/com.mrseivane.Syn.png"
cat > "$DIR/AppRun" <<'EOS'
#!/bin/sh
set -eu
HERE="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
export LC_NUMERIC=C
export PYTHONHOME="$HERE/usr"
export PYTHONPATH="$HERE/usr/share/syn:$HERE/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$HERE/usr/lib/DEB_MULTIARCH:$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="$HERE/usr/lib/DEB_MULTIARCH/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export GSETTINGS_SCHEMA_DIR="$HERE/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$HERE/usr/share${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
export PATH="$HERE/usr/bin:$PATH"
export SYN_LIBMPV="$HERE/usr/lib/DEB_MULTIARCH/libmpv.so.2"
if [ "${1:-}" = "--install-dvr-service" ]; then
  if [ -z "${APPIMAGE:-}" ]; then
    echo 'Abre este comando desde el AppImage, no desde AppDir.' >&2
    exit 2
  fi
  # Write launcher for the original AppImage path, not the transient /tmp/.mount path.
  # Python shlex.quote safely quotes spaces, apostrophes and metacharacters.
  unitdir="$HOME/.config/systemd/user"
  bindir="$HOME/.local/bin"
  unit="$unitdir/syn-dvr-worker.service"
  if systemctl --user is-active --quiet syn-dvr-worker.service; then
    echo 'Ya hay un servicio DVR activo; no se modifica ni se reinicia.'
    exit 0
  fi
  if [ -e "$unit" ]; then
    echo 'Ya existe otro servicio SYN DVR (inactivo). Revísalo antes de cambiar de Flatpak o AppImage:' >&2
    echo "$unit" >&2
    exit 3
  fi
  mkdir -p "$unitdir" "$bindir"
  APPIMAGE_PATH="$APPIMAGE" LAUNCHER="$bindir/syn-appimage-dvr-worker" "$HERE/usr/bin/python3" - <<'PYWORKER'
import os, pathlib, shlex
p=pathlib.Path(os.environ['LAUNCHER'])
app=os.path.realpath(os.environ['APPIMAGE_PATH'])
p.write_text('#!/bin/sh\nexec ' + shlex.quote(app) + ' --dvr-worker\n')
p.chmod(0o755)
PYWORKER
  cat > "$unit" <<UNIT
[Unit]
Description=SYN DVR AppImage - grabaciones programadas
[Service]
Type=exec
ExecStart=%h/.local/bin/syn-appimage-dvr-worker
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload
  systemctl --user enable --now syn-dvr-worker.service
  systemctl --user show syn-dvr-worker.service -p ActiveState -p SubState --no-pager
  exit 0
fi
if [ "${1:-}" = "--dvr-worker" ]; then
  shift
  exec "$HERE/usr/bin/python3" "$HERE/usr/share/syn/syn_dvr.py" "$@"
fi
if [ "${1:-}" = "--self-test" ]; then
  exec "$HERE/usr/bin/python3" -c 'import gi,ctypes,os;gi.require_version("Gtk","4.0");gi.require_version("Adw","1");from gi.repository import Gtk,Adw;ctypes.CDLL(os.environ["SYN_LIBMPV"]);print("SYN: Gtk4/Adw/libmpv OK")'
fi
exec "$HERE/usr/bin/python3" "$HERE/usr/share/syn/syn.py" "$@"
EOS
sed -i "s@DEB_MULTIARCH@$multiarch@g" "$DIR/AppRun"
chmod +x "$DIR/AppRun"
# Smoke test explícito de GI + libmpv empaquetadas, sin pantalla X/Wayland.
"$DIR/AppRun" --self-test
"$DIR/AppRun" --version
# appimagetool conservado en versión concreta para evitar cambios de continuous.
TOOL="$ROOT/.appimagetool-${ARCH}.AppImage"
curl -fL --retry 3 \
  "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-${ARCH}.AppImage" -o "$TOOL"
chmod +x "$TOOL"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$DIR" "dist/SYN-${VERSION}-${ARCH}.AppImage"
test -s "dist/SYN-${VERSION}-${ARCH}.AppImage"
chmod +x "dist/SYN-${VERSION}-${ARCH}.AppImage"
# La extracción evita depender de FUSE dentro de GitHub Actions.
APPIMAGE_EXTRACT_AND_RUN=1 "dist/SYN-${VERSION}-${ARCH}.AppImage" --self-test
