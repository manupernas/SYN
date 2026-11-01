# SYN macOS + SYN DVR 3.1.1 — código fuente

Esta rama conserva la versión macOS local con el motor DVR de recepción
compartida. Contiene `SYNNative` (reproductor), `SYNDVRMenu` (barra de
menús) y `.syn-pool31-engine` (servicio autónomo Swift y servidor HLS).

- REC, EPG y grabaciones programadas usan el motor autónomo.
- El límite configurable de conexiones es compartido por VLC y el DVR.
- La recepción continúa aunque se cierre la interfaz de SYN.
- El motor 3.1.1 limpia los segmentos tras verificar el MKV.

No se incluyen los datos privados, listas IPTV, contraseñas, grabaciones,
frameworks binarios, compilaciones ni LaunchAgents personales.
Para compilar en otro Mac se necesita Xcode, la dependencia VLCKit y
reconstruir/configurar el proyecto según `project.yml` y `Podfile`.
Esta rama contiene **fuentes**, no una aplicación ya firmada.
