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
static int setup_homebrew_gi(void) {
    static const char *libs[] = {
        "libglib-2.0.0.dylib",
        "libgobject-2.0.0.dylib",
        "libgmodule-2.0.0.dylib",
        "libgio-2.0.0.dylib",
        NULL
    };
    int loaded = 0;
    char path[PATH_MAX];
    for (int i=0; libs[i] != NULL; i++) {
        if (snprintf(path, sizeof(path), "%s/%s", SYN_GLIB_DIR, libs[i]) >= (int)sizeof(path))
            return -1;
        void *handle = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
        if (handle) loaded++;
        else fprintf(stderr, "SYN GLib preload %s: %s\n", path, dlerror());
    }
    if (loaded < 2) {
        fprintf(stderr, "SYN: cannot preload Homebrew GLib/GObject from %s\n", SYN_GLIB_DIR);
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
        if (snprintf(path, sizeof(path), "%s/%s", SYN_GLIB_DIR, gi_libs[i]) >= (int)sizeof(path))
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
            legacy(SYN_GLIB_DIR);
        } else {
            get_repository get_default = (get_repository)dlsym(repo_lib, "gi_repository_get_default");
            modern_prepend prepend = (modern_prepend)dlsym(repo_lib, "gi_repository_prepend_library_path");
            if (get_default && prepend) {
                void *repo = get_default();
                if (repo) prepend(repo, SYN_GLIB_DIR);
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
    if (setup_homebrew_gi() != 0) {
        fprintf(stderr, "SYN: preload failed; nothing was installed by the check.\n");
        return 94;
    }
    if (!probe && access(script, R_OK) != 0) {
        fprintf(stderr, "SYN: macos_alpha.py missing: %s\n", script);
        return 93;
    }
    /* Do not force PYTHONHOME globally. For Homebrew Python.framework this
     * can break GLib introspection in an embedded interpreter. */
    unsetenv("PYTHONHOME");
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.parse_argv = 0;

    PyStatus status = PyConfig_SetBytesString(&config, &config.program_name, SYN_PYTHON_EXE);
    if (check_status(status)) goto failure;
    status = PyConfig_SetBytesString(&config, &config.executable, SYN_PYTHON_EXE);
    if (check_status(status)) goto failure;
#if SYN_SET_HOME
    status = PyConfig_SetBytesString(&config, &config.home, SYN_PYTHON_HOME);
    if (check_status(status)) goto failure;
#endif
    if (probe) {
        /* Import GLib first to catch the g_type != TYPE_NONE failure reported
         * under Python 3.15, not just a superficial import of gi. */
        const char *code =
            "import sys, gi, cairo\n"
            "gi.require_version('Gtk','4.0')\n"
            "gi.require_version('GLib','2.0')\n"
            "from gi.repository import GLib, Gtk\n"
            "assert Gtk.get_major_version() == 4\n"
            "print('SYN_NATIVE_GTK_OK', sys.version.split()[0], GLib.MAJOR_VERSION)\n";
        status = PyConfig_SetBytesString(&config, &config.run_command, code);
    } else {
        status = PyConfig_SetBytesString(&config, &config.run_filename, script);
    }
    if (check_status(status)) goto failure;

    int count = probe ? 1 : argc;
    char **py_argv = (char **)calloc((size_t)count, sizeof(char *));
    if (!py_argv) {
        fprintf(stderr, "SYN: memory allocation failed\n");
        goto failure;
    }
    py_argv[0] = probe ? "-c" : script;
    if (!probe) {
        for (int i = 1; i < argc; ++i) py_argv[i] = argv[i];
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
