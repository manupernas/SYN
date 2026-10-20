# Publicación automática de SYN DVR: 10 paquetes

El flujo `.github/workflows/release-10-packages.yml` tiene una matriz de **5 formatos × 2 arquitecturas** (10 jobs) y dos jobs adicionales: `test` y `release`.

| Formato | Intel/AMD | ARM64 | Dependencias |
|---|---|---|---|
| RPM | x86_64 | aarch64 | GTK4, PyGObject, libadwaita, mpv-libs, FFmpeg |
| DEB | amd64 | arm64 | GTK4, Python GI, libadwaita, libmpv2, FFmpeg |
| Pacman | x86_64 | aarch64 | GTK4, Python GObject, libadwaita, mpv, FFmpeg |
| Flatpak | x86_64 | aarch64 | Runtime GNOME 49, bibliotecas multimedia locales |
| AppImage (experimental) | x86_64 | aarch64 | GTK4/Python/FFmpeg empaquetados; gráficos del host |

La arquitectura se compila **en runners nativos** `ubuntu-24.04` y `ubuntu-24.04-arm`. Los paquetes RPM/DEB/Pacman son empaquetados por `fpm` desde los mismos archivos de SYN, con dependencias adaptadas a su gestor de paquetes. Flatpak se construye por arquitectura desde el manifiesto existente. AppImage incorpora Python/GI/libmpv y realiza un smoke test en CI, aunque **debe probarse además gráficamente**.

## Publicación

1. Incorporar `.github/workflows`, `packaging/` y `docs/RELEASE_1.2.2.md` a `main` mediante Pull Request.
2. Revisar GitHub → Actions → `SYN · 10 paquetes`, y ejecutar manualmente el flujo (`Run workflow`) para construir y comprobar los artefactos **sin publicar ninguna Release**.
3. Si las diez compilaciones pasan, desde la carpeta del paquete ejecuta `bash publicar-release.sh`. Alternativamente, crear la etiqueta **en main**:
   ```bash
   git checkout main
   git pull --ff-only
   git tag -a v1.2.2 -m 'SYN DVR 1.2.2 · 10 paquetes Linux'
   git push origin v1.2.2
   ```
4. El push del tag dispara de nuevo las diez compilaciones. **Solo si todas terminan satisfactoriamente**, el job `release` genera `SHA256SUMS.txt` y publica la versión en GitHub Releases con `docs/RELEASE_1.2.2.md`.

## Fallos y depuración

- Las Actions no se ejecutan hasta que el workflow esté incorporado a `main`.
- Si falla cualquier compilación, la Release **no se publica**. Revisa el log del job específico: `rpm/deb/pacman/flatpak/appimage · <arquitectura>`.
- No se asegura que AppImage sea compatible con todas las distribuciones; validación especialmente importante con GTK4, OpenGL y libmpv.
- No publicar versiones parciales etiquetadas como completas; resolver los fallos y preparar una nueva etiqueta si la versión anterior ya tiene una Release pública.
- No incluir configuraciones personales, URLs, M3U ni grabaciones en el repositorio.
- Para Native RPM/DEB/Pacman, el servicio systemd de usuario se instala pero **no se activa automáticamente**.
- Para Flatpak, el servicio DVR se instala manualmente con `instalar-servicio-dvr.sh` del repo; ese script requiere que el Flatpak esté instalado como usuario.
