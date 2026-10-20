# SYN DVR 1.2.2 — versión de desarrollo

Esta revisión incorpora el sistema DVR al proyecto GTK4/libmpv. No incluye emisiones, listas IPTV, claves ni datos privados.

## Funcionalidad

- Grabación inmediata con botón REC rojo compacto y FFmpeg `-c copy` (sin recodificación).
- Programación de grabaciones por fecha, hora y canal; clic derecho sobre un programa EPG para programar su horario original.
- Pantalla DVR y biblioteca de grabaciones integradas, con reproducción en SYN y acceso a la carpeta real del archivo.
- Directorio de grabaciones configurable y comprobado antes de utilizarlo.
- Servicio `syn-dvr-worker.service` en systemd de usuario, con confirmación de latido de grabador independiente.
- Separa los User-Agent de *reproducción MPV* y *consultas M3U/Xtream/EPG/logos* para proveedores que rechazan VLC al consultar `player_api.php`.
- El grabador utiliza User-Agent VLC/3.0.21 de forma independiente.

## Compilar e instalar

En Fedora, con `flatpak-builder`, `flatpak` y `git` instalados:

```bash
bash construir-flatpak.sh
bash instalar-servicio-dvr.sh
flatpak run com.mrseivane.Syn
systemctl --user is-active syn-dvr-worker.service
```

El manifiesto de desarrollo obtiene FFmpeg y mpv desde sus repositorios. Compilar en cada arquitectura: la versión de desarrollo tiene pruebas reales en Fedora ARM64; otras arquitecturas necesitan comprobación.

Las grabaciones continúan después de cerrar la ventana **solo mientras el servicio systemd esté activo, la sesión de usuario admita ejecutarlo y el ordenador no esté suspendido**.

## Privacidad y archivos

Los perfiles Xtream, contraseñas, bases `dvr.json`, URLs privadas, cachés, ficheros `.mkv` y registros de grabación son datos locales del usuario: **no se deben incorporar al repositorio ni a los issues**. No subir salidas completas de FFmpeg sin ocultar las URLs del proveedor.

## Alcance

Publicación del código fuente de la versión de desarrollo 1.2.2; **no supone aceptación en Flathub ni certifica funcionamiento en cualquier proveedor IPTV**.
