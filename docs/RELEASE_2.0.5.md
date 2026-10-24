# SYN 2.0.5 — Linux

## Apariencia y guía EPG en paquetes nativos

- **Ajustes → Apariencia** guarda los cambios de tema y realce sin validar
  las fuentes IPTV. Una lista M3U o un archivo XMLTV inaccesible en esa
  máquina ya no impide cambiar entre Sistema, Claro, Oscuro, Teal, Nord y
  Gruvbox. La validación de fuentes sigue funcionando en el apartado Perfil.
- La columna de vídeo y las superficies superior e inferior de la guía EPG
  utilizan los colores del tema seleccionado, sin dejar franjas heredadas
  del CSS GTK4 del escritorio en Debian/Ubuntu.
- La solución reproduce el parche **SYN 2.0.5 beta1**, comprobado
  visualmente en Ubuntu 26.10 con el paquete DEB.
- El CSS modificado es exclusivo de los componentes visuales de SYN.
  No cambia los temas globales GTK/GNOME del usuario.

## Sin cambios

Motor libmpv, FFmpeg DVR, Chromecast, lista de canales, EPG, perfiles,
credenciales, grabaciones, servicios de usuario y aspecto de la bienvenida.

## Distribución y pruebas

Se conservan las 6 variantes nativas (RPM/DEB/Arch para x86_64 y ARM64) y los
2 Flatpak existentes. El workflow verifica el código antes de construirlas.
