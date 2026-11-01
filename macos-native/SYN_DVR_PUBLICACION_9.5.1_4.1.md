# SYN 9.5.1 y SYN DVR — fuentes macOS

Esta rama reúne las fuentes locales verificadas por marcadores:

- `SYNNative`: SYN macOS, reproductor de grabaciones integrado 9.5.1.
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
