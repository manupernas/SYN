# SYN DVR 4.5.6 — primera instalación limpia y corrección de supervisor

Rama experimental; **no publicar** hasta generar y validar el DMG integrado.

- FFmpeg, FFprobe, Comskip, motor Swift y Python empaquetados dentro de la app.
- Firmar binarios después de ajustar dylibs y antes de ejecutar comprobaciones.
- Guardar datos y ajustes en Application Support del usuario, sin copiar ejecutables.
- Inicializar automáticamente carpeta de grabaciones, configuración y TLS.
- Motor independiente del HTTPS remoto opcional; conservar grabaciones si falla HTTPS.
- Permitir configurar puerto, carpeta y contraseña en cuenta nueva.
- Registrar fallos de arranque en vez de descartar la salida.
- Resolver el script remoto directamente dentro de SYN DVR.app.
- **PyInstaller onefile:** informar el PID del lanzador para que Swift reconozca el latido.
- Prueba automática de configuración con HOME temporal en el constructor.
- Generar DMG local con `release/syn-dvr/CREAR_DMG_PRUEBA.command`.

Pruebas manuales previas en cuenta macOS nueva: reproducción SYN, grabación directa,
grabación EPG, grabación con SYN cerrado, programación manual, ajustes HTTPS.
La configuración de conexiones IPTV debe permitir los flujos simultáneos necesarios.
La firma actual es ad hoc, **sin notarización**.
La app no puede corregir por sí sola un `~/Library/Application Support` propiedad de root;
ese fallo de permisos del entorno de pruebas se corrigió por separado.
