# SYN 2.0.7 — Tema claro y ventanas emergentes

Probado en Fedora ARM64 con el Flatpak SYN 2.0.6 y aprobado visualmente.

- Ajustes: ventana, barra de título, botón de cerrar y cabeceras con la paleta clara seleccionada.
- Menús emergentes, Gtk.DropDown, selecciones, buscadores y etiquetas con fondo y texto coherentes.
- Los estilos claros incluyen Claro, Nord claro, Gruvbox claro y Sistema claro.
- No se fuerza apariencia en Oscuro, Nord oscuro, Gruvbox oscuro, Teal ni Sistema oscuro.
- Se conserva el CSS separado del popover Chromecast de la versión estable.
- Se integra literalmente el helper CSS probado de la Beta Fedora Flatpak.

## Sin cambios

Carga progresiva de 6.720 canales, logos reales/ilustraciones, Favoritos, EPG,
reproducción libmpv, DVR, Chromecast, perfiles, credenciales y grabaciones.

## Distribución

6 paquetes nativos (DEB/RPM/Arch x86_64 y ARM64) y 2 Flatpak.
GitHub Actions verifica las pruebas antes de generar los paquetes.
