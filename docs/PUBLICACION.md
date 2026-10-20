# Hoja de ruta de publicación

Esta carpeta contiene el código fuente de **SYN 1.0.2b**, preparado para publicar en el repositorio propio de GitHub.

## Antes de publicar el proyecto

1. Revisa el contenido completo, especialmente la configuración de IPTV. No incluyas ninguna lista real ni credenciales.
2. Comprueba que `README.md` describe correctamente la aplicación.
3. Prueba el Flatpak en Fedora y, antes de llegar a Flathub, también en x86_64.
4. Conserva esta copia de las fuentes como referencia para crear futuras versiones y etiquetas de Git.

## Antes de solicitar inclusión en Flathub

- El manifiesto de desarrollo actual usa `type: dir`, por lo que no es apto directamente para construir desde una fuente remota.
- El identificador `com.mrseivane.Syn` debe ser coherente con una web/dominio que controle el desarrollador, o debe estudiarse cambiarlo por un identificador `io.github.manupernas.*` antes de distribuir públicamente por Flathub.
- Se necesitan capturas reales, ficha AppStream revisada, verificación de permisos, dependencias, licencias y prueba de arquitecturas.
- Flathub tiene requisitos específicos sobre materiales generados con IA: revelar su uso, y el manifiesto destinado a Flathub debe ser redactado por una persona, no generado con IA. No usar agentes de IA para abrir ni automatizar la solicitud a Flathub.

Documentación de referencia: https://docs.flathub.org/docs/for-app-authors/requirements
