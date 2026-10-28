# SYN Native — macOS (7.10.6)

Código fuente de la aplicación IPTV **SYN**, implementada en SwiftUI/AppKit con VLCKit 3.7.3.

Esta versión incluye perfiles Xtream y M3U, favoritos, EPG multicanal adaptable a filas completas, reproductor 16:9, gestión de fuentes y ajustes, y funciones nativas de macOS. Es una instantánea del código del 28 de octubre de 2026, reconstruida a partir del proyecto fuente aportado y los parches 7.9.7–7.10.6.

**Este directorio contiene código y recursos, no una distribución compilada ni una release.** No se incluyen Pods, aplicaciones, bases de datos, perfiles privados ni contraseñas. Revisa requisitos y funcionamiento antes de distribuir.

## Desarrollo

En macOS 15 o posterior, con Xcode, XcodeGen y CocoaPods instalados:

```sh
xcodegen generate --spec project.yml
pod install
open SYNNative.xcworkspace
```

Elige el esquema `SYNNative` y compila desde Xcode, con la identidad de firma de tu equipo. `project.yml` preserva los permisos HTTP para proveedores que los requieren; usa fuentes autorizadas y, cuando sea posible, HTTPS.

No se ha ejecutado una compilación Xcode en el entorno donde se preparó este código. No sustituye automáticamente `/Applications/SYN.app`.
