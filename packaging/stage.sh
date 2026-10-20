#!/usr/bin/env bash
# Prepara únicamente los archivos públicos de SYN: nunca perfiles ni credenciales.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT=packaging/stage
rm -rf "$ROOT"
install -d "$ROOT/usr/bin" "$ROOT/usr/share/syn" \
  "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor" \
  "$ROOT/usr/share/locale"

install -m 644 syn.py syn_sources.py syn_i18n.py "$ROOT/usr/share/syn/"
install -m 644 io.github.manupernas.SYN.desktop \
  "$ROOT/usr/share/applications/io.github.manupernas.SYN.desktop"
cp -R icons/. "$ROOT/usr/share/icons/hicolor/"

for locale in en_US en_GB; do
  install -Dm644 "locale/$locale/LC_MESSAGES/syn.mo" \
    "$ROOT/usr/share/locale/$locale/LC_MESSAGES/syn.mo"
done

cat > "$ROOT/usr/bin/syn" <<'SH'
#!/bin/sh
# Mantener el separador decimal en punto para el motor libmpv.
export LC_NUMERIC=C
exec /usr/bin/python3 /usr/share/syn/syn.py "$@"
SH
chmod 755 "$ROOT/usr/bin/syn"

echo "Preparado: SYN nativo con iconos, traducciones y acceso al libmpv del sistema."
