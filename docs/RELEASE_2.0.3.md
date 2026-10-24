# SYN 2.0.3 — Linux

## Corrección de temas en los paquetes nativos

- Los RPM, DEB y paquetes Arch respetan primero la preferencia claro/oscuro de GNOME cuando está elegida explícitamente.
- Si no existe una preferencia explícita, se utiliza la variante GTK oscura/clara si su nombre es inequívoco, dejando los casos ambiguos a libadwaita.
- Los fondos y textos de las superficies de SYN en modo **Sistema** se dibujan con prioridad adecuada frente al `gtk.css` nativo, sin imponer una paleta fija a los temas personalizados.
- Las versiones Flatpak mantienen el mismo comportamiento que antes.

## Sin cambios

Sin modificaciones de motor libmpv, DVR, Chromecast, conexiones, perfiles, credenciales, favoritos ni EPG.

## Verificación

Las pruebas estáticas de arranque y CSS se ejecutan en GitHub Actions; el aspecto definitivo de los paquetes nativos debe validarse también en un escritorio Fedora/Arch real.
