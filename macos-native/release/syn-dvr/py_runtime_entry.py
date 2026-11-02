"""Frozen Python entrypoint, bundled only in SYN DVR distributions.

Executes exactly one bundled .py script. No host Python executable is called.
"""
import os
import runpy
import sys
from pathlib import Path


def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--self-test':
        print('SYN_PYTHON_RUNTIME_OK')
        return
    if len(sys.argv) < 2:
        sys.stderr.write('SYN DVR: falta el programa a ejecutar\n')
        raise SystemExit(2)
    script = Path(sys.argv[1]).resolve()
    if not script.is_file() or script.suffix != '.py':
        sys.stderr.write('SYN DVR: script inexistente o no válido\n')
        raise SystemExit(2)
    runtime = (Path(sys.executable).resolve().parent.parent / 'Resources' / 'SYN-DVR-Runtime').resolve()
    known_scripts = {'standalone_supervisor.py', 'syn_dvr_remote.py', 'hls_server.py'}
    support = Path.home() / 'Library' / 'Application Support'
    allowed_external = any(base in script.parents for base in (
        support / 'SYN DVR Remote', support / 'SYN DVR Engine 2.0'))
    if script.name not in known_scripts or not (runtime in script.parents or allowed_external):
        sys.stderr.write('SYN DVR: script fuera de los recursos internos\n')
        raise SystemExit(2)
    sys.argv = [str(script), *sys.argv[2:]]
    sys.path.insert(0, str(script.parent))
    os.chdir(str(script.parent))
    runpy.run_path(str(script), run_name='__main__')


if __name__ == '__main__':
    main()
