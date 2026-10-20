# SYN 1.0.2b — Realce, última vista e icono nuevo

**GTK4 · libadwaita · libmpv · Flatpak · Fedora ARM64 / Linux x86_64**

Esta versión corrige el botón de Ajustes que dejó de responder tras introducir
las traducciones en SYN 3.8.13 y consolida el modo **Oscuro**. Conserva los
idiomas `es`, `en_US` (AM/PM) y `en_GB` (24 h), elegidos automáticamente
según el idioma del escritorio.

## Error de Ajustes: causa y solución

La función de traducción se llamaba `_`, pero numerosos callbacks GTK tenían
un parámetro `*_`. Como el parámetro local tenía el mismo nombre, `_('texto')`
intentaba llamar a una tupla y producía `TypeError: 'tuple' object is not callable`.
Esto afectaba a Ajustes y potencialmente a la bienvenida, parada, información,
abrir lista M3U y otros manejadores. La traducción se llama ahora `tr(...)` en
todo `syn.py`, evitando las colisiones; los parámetros GTK permanecen intactos.

El test `test_syn10_release.py` **ejecuta el método real `open_settings`** con
controles GTK simulados y comprueba la apertura y el guardado de opciones en
inglés sin alterar los valores internos de perfiles ni de MPV. Los tests son
simulaciones: no sustituyen a la prueba real en Fedora/Wayland.

## Tema Oscuro

- Paleta grafito definida para cabeceras, canales, textos y barra inferior.
- Menús desplegables (`Gtk.DropDown`), `popover > contents`, hover, selección,
  opciones y barras de desplazamiento con contraste oscuro consistente.
- Ajustes: entradas, contraseña, botones, acciones, barras, texto, selección.
- EPG: categorías, programación, cabeceras, búsqueda, marcas horarias.
- Zapping, overlays a pantalla completa y primer arranque.
- Los cambios se aplican solo al modo `dark`: **Sistema, Claro y Teal SYN**
  siguen con su comportamiento propio.

## Sin regresiones intencionadas

- `NativeMpv` y `MpvArea` son AST idénticos a SYN 3.8.13.
- `_draw_channel_logo` y el lienzo fijo de 108×38 también son idénticos.
- `syn_sources.py` es byte por byte idéntico.
- Se mantienen las pastillas 120×46, favoritos, EPG por tandas de 24 y scroll.
- Los perfiles se conservan; el script actualizador guarda una copia de las
  fuentes anteriores en `syn-backups/`.

## Actualizar el Flatpak actual

Cierra SYN, descomprime el ZIP, abre Ghostty dentro de la carpeta y ejecuta:

```bash
bash actualizar-flatpak-existente.sh \
  "$HOME/Música/SYN_3.0_BETA_Linux_Flatpak_Fuentes"
```

Para comprobar:

```bash
flatpak run com.mrseivane.Syn --version
flatpak run com.mrseivane.Syn --locale-info
```

Debe indicar `SYN 1.0.2b` y el idioma detectado.

**Comprueba visualmente** que el botón Ajustes abre su ventana y que se pueden
guardar opciones; y después revisa en modo Oscuro los desplegables (abiertos y
cerrados) y la guía EPG. No se ha podido ejecutar GTK real dentro del entorno
de construcción de este ZIP.

## Verificaciones realizadas

- 123 pruebas automatizadas, con pruebas del método real `open_settings` usando
  objetos GTK simulados, revisión CSS y compatibilidad de perfiles.
- `python3 -m py_compile` y `bash -n` correctos.
- Verificación de los ZIP (CRC).
- Comprobación del motor de reproducción y el renderizador fijo de logos.
