# SYN DVR 1.2.2 — Linux (x86_64 y ARM64)

Primera publicación multiplataforma del sistema DVR integrado de SYN. Esta versión incorpora la grabación mediante FFmpeg, la programación desde la guía EPG y una biblioteca de grabaciones dentro de la interfaz GTK4/libmpv.

## Novedades

- Botón REC rojo para grabar el canal actual, sin recodificar (`ffmpeg -c copy`).
- Calendario de grabaciones y selección de canal, fecha y horario.
- Clic derecho sobre un programa de la EPG para programar su grabación con el horario original.
- Biblioteca de grabaciones y reproducción dentro de SYN; acceso a la carpeta del archivo.
- Carpeta de destino configurable y validación de permisos.
- Programador independiente `syn-dvr-worker.service` para continuar grabando tras cerrar la ventana, **si está instalado y activo**.
- Reproducción con libmpv y consultas Xtream/M3U/EPG con User-Agent independiente: resuelve proveedores que exigen VLC para el vídeo pero lo rechazan en `player_api.php`.
- Correcciones al cambiar de una grabación al directo: evita usar la resolución anterior.

## Qué descargar

Se generan diez paquetes: RPM, DEB, Pacman, Flatpak y AppImage, cada uno en versión `x86_64` (AMD/Intel) y `aarch64` (ARM64). **El Flatpak también es específico de la arquitectura**, aunque funciona en distintas distribuciones Linux.

- **Fedora:** `.rpm` (preferible para instalación nativa) o `.flatpak`.
- **Ubuntu/Debian:** `.deb` o `.flatpak`.
- **Arch/EndeavourOS:** `.pkg.tar.zst` o `.flatpak`.
- **Otros Linux:** `.flatpak`; `.AppImage` experimental.

Los RPM/DEB/Pacman necesitan paquetes del sistema: GTK4, PyGObject, libadwaita, libmpv y FFmpeg. Los Flatpak instalan su propio entorno GNOME 49 desde Flathub al instalarlos. Los AppImage están pensados para Ubuntu 24.04 o sistemas compatibles; **no se garantiza compatibilidad con cualquier Linux**, especialmente en entornos OpenGL/Wayland particulares.

## Instalación y servicio DVR

Las grabaciones programadas requieren el servicio independiente. Al instalar un paquete nativo, actívalo explícitamente con:

```bash
systemctl --user enable --now syn-dvr-worker.service
systemctl --user is-active syn-dvr-worker.service
```

Para una instalación Flatpak manual, además de instalar el bundle, usa el script `instalar-servicio-dvr.sh` del repositorio:

```bash
flatpak --user install ./SYN-1.2.2-x86_64.flatpak
bash instalar-servicio-dvr.sh
```

Sustituye la arquitectura que corresponda y **no actives simultáneamente dos servicios DVR de instalaciones diferentes** si comparten la misma base de datos.

Para AppImage, copia el archivo a una ruta permanente y ejecuta una vez:

```bash
chmod +x SYN-1.2.2-x86_64.AppImage
./SYN-1.2.2-x86_64.AppImage --install-dvr-service
```

Si ya hay una grabación en curso, **no cambies de paquete ni reinicies el servicio**.

## Limitaciones y privacidad

- Los paquetes se publican solo tras completar las diez compilaciones y las pruebas de cada trabajo en GitHub Actions.
- AppImage es experimental, empaqueta bibliotecas GTK4/PyGObject y libmpv, pero no sustituye los controladores gráficos del anfitrión; exige validación en sistemas reales.
- No incluye canales, suscripciones ni listas IPTV. Solo debes usar emisiones para las que tengas autorización.
- Los datos de usuario (`profiles.json`, credenciales Xtream, `dvr.json`) y las grabaciones son **locales** y no forman parte de los paquetes.
- `SHA256SUMS.txt` permite comprobar la integridad de los archivos de Release.
- El servicio de usuario solo continúa grabando mientras esté activo y el equipo permanezca encendido y sin suspenderse.

Consulta [las notas técnicas](https://github.com/manupernas/SYN/blob/main/docs/NOTAS_DVR_1.2.2.md) y [el repositorio de SYN](https://github.com/manupernas/SYN).
