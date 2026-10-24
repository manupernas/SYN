# SYN 2.0.4 — Linux

## Bienvenida legible en temas claros

- La ventana de bienvenida y el formulario de añadir fuentes ahora utilizan una paleta clara completa y consistente en **Sistema claro**, **Claro**, **Nord claro** y **Gruvbox claro**, incluida la apariencia clara de Ubuntu Yaru.
- Los títulos, descripciones, botones, iconos, campos M3U/Xtream y botón de conexión mantienen un contraste legible con el fondo.
- Las reglas se limitan a `window.synplus-welcome` y tienen prioridad sobre CSS GTK personalizado; no afectan a la ventana principal de SYN.
- Si el escritorio cambia a modo oscuro, se eliminan las reglas claras y se conserva la apariencia oscura original.

## Sin cambios

No se modifican el reproductor, EPG, DVR, Chromecast, listas IPTV, perfiles guardados, temas oscuros ni el ID de la aplicación.

## Verificación

GitHub Actions ejecuta toda la batería de pruebas, incluido `tests/test_syn_204.py`. El aspecto final debe comprobarse en Ubuntu 26.10 en modo claro con los paquetes nativos.
