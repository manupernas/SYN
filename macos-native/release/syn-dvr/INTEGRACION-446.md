# SYN DVR 4.4.6 · Preparación Plug & Play (SIN RELEASE)

Rama de desarrollo: no incluye binarios publicados.

La aplicación se compila desde fuentes mediante `GENERAR_DISTRIBUCION.command`
en un Mac constructor con Xcode, XcodeGen, Comskip, FFmpeg, FFprobe y PyInstaller.
Todo queda integrado en el ZIP final; el usuario no necesita Homebrew ni Python.

El motor Swift procede de `.syn-pool31-engine`; los scripts de supervisor y
servidor remoto se han incorporado como código fuente. El servidor HLS se toma del motor.

NO se publica automáticamente ni se sube ZIP de usuarios.

**Pendiente de validación antes de lanzar:** compilación Xcode/Swift, arranque desde
cuenta limpia sin Homebrew/Python, programación diferida, HTTPS remoto, recepción HLS,
Comskip y cierre/reinicio del motor. Revisar licencias GPL/LGPL de herramientas.
Sin Developer ID: ZIP ad hoc sin notarizar, Gatekeeper pedirá autorización inicial.
