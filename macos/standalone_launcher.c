/* SYN Mac native host — initialise CPython with an explicit interpreter
 * identity, so Python.framework and PyGObject share the same runtime.
 * Uses PyConfig and explicitly preloads Homebrew GLib / GIRepository.
 * GI typelibs may reference leaf library names (libglib-2.0.0.dylib) and
 * cannot always find those when libpython is embedded in a new binary.
 */
#include <Python.h>
#include <mach-o/dyld.h>
#include <unistd.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>

#ifndef SYN_PYTHON_HOME
#error SYN_PYTHON_HOME is not defined
#endif
#ifndef SYN_PYTHON_EXE
#error SYN_PYTHON_EXE is not defined
#endif
#ifndef SYN_SET_HOME
#define SYN_SET_HOME 0
#endif
#ifndef SYN_GLIB_DIR
#define SYN_GLIB_DIR "/opt/homebrew/lib"
#endif

/* Avoid mixed copies of GLib/GObject: the same Homebrew libraries must be
 * shared by PyGObject and GIRepository. Run this BEFORE Py_Initialize. */
static int setup_homebrew_gi(const char *lib_dir) {
    static const char *libs[] = {
        "libglib-2.0.0.dylib",
        "libgobject-2.0.0.dylib",
        "libgmodule-2.0.0.dylib",
        "libgio-2.0.0.dylib",
        /* GTK typelibs refer to bare dylib names. Preload bundled dylibs
         * so GIRepository does not fall back to external Homebrew paths. */
        "libpango-1.0.0.dylib",
        "libpangocairo-1.0.0.dylib",
        "libgdk_pixbuf-2.0.0.dylib",
        "libgraphene-1.0.0.dylib",
        "libgtk-4.1.dylib",
        "libadwaita-1.0.dylib",
        NULL
    };
    int loaded = 0;
    char path[PATH_MAX];
    for (int i=0; libs[i] != NULL; i++) {
        if (snprintf(path, sizeof(path), "%s/%s", lib_dir, libs[i]) >= (int)sizeof(path))
            return -1;
        void *handle = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
        if (handle) loaded++;
        else fprintf(stderr, "SYN GLib preload %s: %s\n", path, dlerror());
    }
    if (loaded < 2) {
        fprintf(stderr, "SYN: cannot preload Homebrew GLib/GObject from %s\n", lib_dir);
        return -1;
    }
    /* gobject-introspection 1.x and 2.x expose different ABI symbols.
       Load only ONE installed GIRepository ABI where available. */
    const char *gi_libs[] = {
        "libgirepository-2.0.0.dylib",
        "libgirepository-1.0.1.dylib",
        "libgirepository-1.0.dylib",
        NULL
    };
    void *repo_lib = NULL;
    for (int i=0; gi_libs[i] != NULL; i++) {
        if (snprintf(path, sizeof(path), "%s/%s", lib_dir, gi_libs[i]) >= (int)sizeof(path))
            continue;
        if (access(path, R_OK) != 0) continue;
        repo_lib = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
        if (repo_lib) break;
        fprintf(stderr, "SYN GIRepository preload %s: %s\n", path, dlerror());
    }
    if (repo_lib) {
        typedef void (*legacy_prepend)(const char *);
        typedef void *(*get_repository)(void);
        typedef void (*modern_prepend)(void *,const char *);
        legacy_prepend legacy = (legacy_prepend)dlsym(repo_lib, "g_irepository_prepend_library_path");
        if (legacy) {
            legacy(lib_dir);
        } else {
            get_repository get_default = (get_repository)dlsym(repo_lib, "gi_repository_get_default");
            modern_prepend prepend = (modern_prepend)dlsym(repo_lib, "gi_repository_prepend_library_path");
            if (get_default && prepend) {
                void *repo = get_default();
                if (repo) prepend(repo, lib_dir);
            }
        }
    }
    return 0;
}

static int check_status(PyStatus status) {
    if (PyStatus_Exception(status)) {
        fprintf(stderr, "SYN/Python init: %s\n", status.err_msg ? status.err_msg : "unknown");
        return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    char current[PATH_MAX] = {0};
    uint32_t capacity = sizeof(current);
    if (_NSGetExecutablePath(current, &capacity) != 0) {
        fprintf(stderr, "SYN: executable path not available\n");
        return 90;
    }
    char *slash = strrchr(current, '/');
    if (!slash) return 91;
    *slash = '\0';
    char script[PATH_MAX];
    if (snprintf(script, sizeof(script), "%s/../Resources/macos_alpha.py", current) >= (int)sizeof(script)) {
        return 92;
    }

    const int probe = (argc >= 2 && strcmp(argv[1], "--syn-bootstrap-check") == 0);
    const int worker = (argc >= 2 && strcmp(argv[1], "--syn-dvr-worker") == 0);
    const int cast = (argc >= 2 && strcmp(argv[1], "--syn-cast-host") == 0);
    char frameworks[PATH_MAX], python_home[PATH_MAX], python_bin[PATH_MAX];
    char libmpv[PATH_MAX], ffmpeg[PATH_MAX], helper[PATH_MAX];
    char py_site[PATH_MAX], py_src[PATH_MAX], py_resources[PATH_MAX], py_stdlib[PATH_MAX], py_dynload[PATH_MAX];
    char gtk_share[PATH_MAX], typelib[PATH_MAX], schemas[PATH_MAX], gio_mods[PATH_MAX], binpath[PATH_MAX], origpath[PATH_MAX * 2];
    snprintf(frameworks, sizeof(frameworks), "%s/../Frameworks", current);
    snprintf(python_home, sizeof(python_home), "%s/Python.framework/Versions/3.15", frameworks);
    snprintf(python_bin, sizeof(python_bin), "%s/bin/python3.15", python_home);
    snprintf(py_site, sizeof(py_site), "%s/../Resources/python-site", current);
    snprintf(py_src, sizeof(py_src), "%s/../Resources/source", current);
    snprintf(py_resources, sizeof(py_resources), "%s/../Resources", current);
    snprintf(py_stdlib, sizeof(py_stdlib), "%s/lib/python3.15", python_home);
    snprintf(py_dynload, sizeof(py_dynload), "%s/lib/python3.15/lib-dynload", python_home);
    snprintf(libmpv, sizeof(libmpv), "%s/libmpv.dylib", frameworks);
    snprintf(ffmpeg, sizeof(ffmpeg), "%s/../Resources/bin/ffmpeg", current);
    snprintf(helper, sizeof(helper), "%s/../Helpers", current);
    snprintf(gtk_share, sizeof(gtk_share), "%s/../Resources/share", current);
    snprintf(typelib, sizeof(typelib), "%s/../Resources/girepository-1.0", current);
    snprintf(schemas, sizeof(schemas), "%s/glib-2.0/schemas", gtk_share);
    snprintf(gio_mods, sizeof(gio_mods), "%s/../Resources/lib/gio/modules", current);
    snprintf(binpath, sizeof(binpath), "%s/../Resources/bin", current);
    const char *oldpath = getenv("PATH");
    snprintf(origpath, sizeof(origpath), "%s:%s", binpath,
             oldpath && *oldpath ? oldpath : "/usr/bin:/bin:/usr/sbin:/sbin");
    setenv("PATH", origpath, 1);
    setenv("SYN_STANDALONE", "1", 1);
    setenv("SYN_BUNDLED_LIBMPV", libmpv, 1);
    setenv("SYN_FFMPEG_BIN", ffmpeg, 1);
    setenv("SYN_BUNDLED_PYTHON", current, 1);
    setenv("SYN_BUNDLED_HELPERS", helper, 1);
    setenv("GI_TYPELIB_PATH", typelib, 1);
    setenv("GSETTINGS_SCHEMA_DIR", schemas, 1);
    setenv("GIO_EXTRA_MODULES", gio_mods, 1);
    setenv("XDG_DATA_DIRS", gtk_share, 1);
    setenv("PYTHONNOUSERSITE", "1", 1);
    if (worker) snprintf(script, sizeof(script), "%s/../Resources/mac_dvr_worker.py", current);
    if (cast) snprintf(script, sizeof(script), "%s/../Resources/source/syn_cast_host.py", current);
    if (setup_homebrew_gi(frameworks) != 0) {
        fprintf(stderr, "SYN: preload failed; nothing was installed by the check.\n");
        return 94;
    }
    if (!probe && access(script, R_OK) != 0) {
        fprintf(stderr, "SYN: macos_alpha.py missing: %s\n", script);
        return 93;
    }
    /* Isolate bundled Python from the user's Homebrew or virtualenv. */
    unsetenv("PYTHONHOME");
    unsetenv("PYTHONPATH");
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.parse_argv = 0;
    config.use_environment = 0;
    /* The signed Python.framework is sealed: runtime .pyc files would
     * invalidate its ad-hoc signature after --syn-bootstrap-check. */
    config.write_bytecode = 0;
    config.site_import = 0;
    config.module_search_paths_set = 1;
    const char *py_paths[] = {py_site, py_resources, py_src, py_stdlib, py_dynload, NULL};
    for (int i = 0; py_paths[i] != NULL; ++i) {
        wchar_t *w = Py_DecodeLocale(py_paths[i], NULL);
        if (!w) goto failure;
        PyStatus ps = PyWideStringList_Append(&config.module_search_paths, w);
        PyMem_RawFree(w);
        if (check_status(ps)) goto failure;
    }

    PyStatus status = PyConfig_SetBytesString(&config, &config.program_name, python_bin);
    if (check_status(status)) goto failure;
    status = PyConfig_SetBytesString(&config, &config.executable, python_bin);
    if (check_status(status)) goto failure;
    status = PyConfig_SetBytesString(&config, &config.home, python_home);
    if (check_status(status)) goto failure;
    if (probe) {
        /* Import GLib first to catch the g_type != TYPE_NONE failure reported
         * under Python 3.15, not just a superficial import of gi. */
        const char *code =
            "import os, sys, gi, cairo, ctypes, subprocess\n"
            "from pathlib import Path\n"
            "gi.require_version('Gtk','4.0')\n"
            "gi.require_version('GLib','2.0')\n"
            "gi.require_version('Adw','1')\n"
            "gi.require_version('GdkPixbuf','2.0')\n"
            "from gi.repository import GLib, Gtk, Adw, GdkPixbuf\n"
            "assert Gtk.get_major_version() == 4\n"
            "contents = Path(os.environ['SYN_BUNDLED_PYTHON']).resolve().parent\n"
            "fw = (contents / 'Frameworks/Python.framework/Versions/3.15').resolve()\n"
            "site = (contents / 'Resources/python-site').resolve()\n"
            "print('SYN_PREFIX', repr(sys.prefix), 'GI', repr(gi.__file__), flush=True)\n"
            "assert Path(sys.prefix).resolve() == fw, (sys.prefix, str(fw))\n"
            "assert Path(gi.__file__).resolve().is_relative_to(site), (gi.__file__, str(site))\n"
            "print('SYN_GTK_IMPORT_OK', flush=True)\n"
            "ctypes.CDLL(os.environ['SYN_BUNDLED_LIBMPV'])\n"
            "print('SYN_LIBMPV_LOAD_OK', flush=True)\n"
            "f = subprocess.run([os.environ['SYN_FFMPEG_BIN'], '-version'],\n"
            "                  capture_output=True, text=True, timeout=20)\n"
            "assert f.returncode == 0, (f.returncode, f.stderr[:2000])\n"
            "print('SYN_FFMPEG_EXEC_OK', flush=True)\n"
            "print('SYN_NATIVE_GTK_OK', sys.version.split()[0], GLib.MAJOR_VERSION)\n";
        status = PyConfig_SetBytesString(&config, &config.run_command, code);
    } else {
        status = PyConfig_SetBytesString(&config, &config.run_filename, script);
    }
    if (check_status(status)) goto failure;

    int count = probe ? 1 : (worker || cast ? (argc - 1) : argc);
    char **py_argv = (char **)calloc((size_t)count, sizeof(char *));
    if (!py_argv) {
        fprintf(stderr, "SYN: memory allocation failed\n");
        goto failure;
    }
    py_argv[0] = probe ? "-c" : script;
    if (!probe) {
        for (int i = (worker || cast ? 2 : 1); i < argc; ++i)
            py_argv[i - (worker || cast ? 1 : 0)] = argv[i];
    }
    status = PyConfig_SetBytesArgv(&config, count, py_argv);
    free(py_argv);
    if (check_status(status)) goto failure;
    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        fprintf(stderr, "SYN: failed to initialize CPython: %s\n", status.err_msg ? status.err_msg : "unknown");
        return 96;
    }
    return Py_RunMain();

failure:
    PyConfig_Clear(&config);
    return 95;
}
