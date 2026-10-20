# SYN 1.0.1 — Realce y restauración de vista

- Color HEX personalizado: proveedor CSS independiente a prioridad superior al tema, con selectores reales para controles seleccionados, botones de acento y barras. Se aplica al guardar Ajustes, en los modos Sistema, Claro, Oscuro y Teal.
- Al cerrar normalmente se guarda la vista actual: filtro ★ Favoritos, categoría y guía EPG. La misma vista se restaura al volver a abrir SYN. Si la categoría ha desaparecido, se utiliza «Todas las categorías».
- Las preferencias se almacenan en el JSON existente sin modificar perfiles, listas ni favoritos.
- No se ha podido probar un entorno GTK/Flatpak real en Fedora desde este contenedor; se incluyen tests unitarios.

## Instalar

Cierra SYN, descomprime el ZIP y, desde la carpeta descomprimida, ejecuta:

```bash
bash actualizar-flatpak-existente.sh "$HOME/Música/SYN_3.0_BETA_Linux_Flatpak_Fuentes"
```

Comprueba que la ruta corresponde a tu carpeta de fuentes actual. El script crea copia del código anterior antes de actualizar.

```bash
flatpak run com.mrseivane.Syn --version
```
