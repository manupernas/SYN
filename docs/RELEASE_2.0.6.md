# SYN 2.0.6 — Linux

## Rendimiento y logotipos

- Validada en Ubuntu 26.10 ARM64 con 6.720 canales y 4.766 URLs de logos.
- Construcción gradual de las filas (18 por tanda) en las listas principal y rápida.
- El selector rápido no crea filas ocultas al arrancar.
- Carga/recorte/escalado de los logos de proveedor en los hilos existentes;
  GTK4 solo recibe las texturas listas para pintar, sin recortar en su hilo.
- Pastillas de 120 × 46 con `Gtk.Overlay`: el logo real centrado encima de
  la ilustración alternativa, sin desplazar la disposición de Favoritos.
- Los canales sin logo siguen usando los diseños originales de SYN/Cairo.
- Los paquetes DEB declaran `python3-gi-cairo` para las ilustraciones.

## Mantenido sin cambios

Ajustes de tema y EPG 2.0.5, reproducción libmpv, DVR, Chromecast, XMLTV,
perfiles, credenciales, archivos personales, logos personalizados, grabaciones,
servicios de usuario y sus configuraciones.

## Paquetes

6 paquetes nativos (DEB/RPM/Arch, aarch64/x86_64) y 2 Flatpaks.
El workflow valida todos los tests antes de publicar cada release.
