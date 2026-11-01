# SYN 9.7.2 Flat Pop Art y SYN DVR — fuentes macOS

Esta rama reúne las fuentes locales verificadas por marcadores:

- `SYNNative`: SYN macOS 9.7.2, reproductor de grabaciones integrado y placeholders Flat Pop Art (20 paletas, 12 diseños).
- `SYNDVRMenu`: SYN DVR en barra de menús, botón «Ver en SYN», configuración Remote 4.1.
- `.syn-pool31-engine`: motor de recepción/grabación compartida 3.1.1 (fuentes, no archivos de ejecución).
- `SYNDVRRemote/syn_dvr_remote.py`: servidor API HTTPS 4.1 **sin** su configuración privada.
- `project.yml` y `Podfile`: configuración de compilación.

La rama contiene **código fuente**. No incluye aplicaciones firmadas, el SDK VLCKit
comercializado, listas IPTV, contraseñas, archivos de vídeo, configuración personal,
certificados privados, datos de usuario ni servicios instalados. Para compilar se
necesitan Xcode y las dependencias de proyecto correspondientes.

El número de versión en el nombre de la rama identifica la combinación de código.
No implica que existan pruebas de integración de cada función en todos los equipos.
