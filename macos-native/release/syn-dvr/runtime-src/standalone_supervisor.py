#!/usr/bin/env python3
"""SYN DVR 4.2: app-owned HTTPS + existing DVR engine, no LaunchAgent.

The GUI owns one anonymous stdin pipe. Closing the GUI closes the pipe;
this supervisor then terminates the API and the engine's complete process
session. Scheduled tasks remain on disk but cannot run without this process.
"""
import contextlib
import json
import os
from pathlib import Path
import plistlib
import select
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.request

HOME = Path.home()
ENGINE_DIR = HOME / 'Library/Application Support/SYN DVR Engine 2.0'
REMOTE_DIR = HOME / 'Library/Application Support/SYN DVR Remote'
ENGINE_PROGRAM = Path(os.environ.get('SYN_DVR_ENGINE', str(ENGINE_DIR / 'bin/syn-dvr-engine')))
API_PROGRAM = Path(os.environ.get('SYN_DVR_REMOTE_SCRIPT', str(REMOTE_DIR / 'syn_dvr_remote.py')))
API_CONFIG = REMOTE_DIR / 'server.json'
AGENT = HOME / 'Library/LaunchAgents/com.mrseivane.syn.dvr2.plist'
AGENT_SNAPSHOT = REMOTE_DIR / 'standalone.engine-agent.plist'
STATUS = REMOTE_DIR / 'standalone.status.json'
LOG = REMOTE_DIR / 'standalone.log'
PYTHON = os.environ.get('SYN_DVR_POOL_PYTHON', '/usr/bin/python3')
children = []
exit_requested = False


def log(msg):
    REMOTE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + msg + '\n')


def status(state, api=None, engine=None, detail=''):
    data = {'timestamp': time.time(), 'supervisorPID': (os.getppid() if getattr(sys, 'frozen', False) else os.getpid()),
            'apiPID': api.pid if api else None, 'enginePID': engine.pid if engine else None,
            'state': state, 'detail': detail}
    tmp = STATUS.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(data, f)
    os.replace(tmp, STATUS)


def safe_stop(p, name):
    if not p:
        return
    # First ask the engine to close its pool and terminate captures itself.
    # Never send SIGTERM to the full process group immediately: that prevents
    # the engine's Swift shutdown handler from running.
    if p.poll() is None:
        try:
            os.kill(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            log(name + ': cierre lento, escalando señal')
    # Kill remaining descendants (FFmpeg / HLS server) in this private
    # process session even if the parent has already exited.
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    time.sleep(.3)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if p.poll() is None:
        try: p.wait(timeout=2)
        except subprocess.TimeoutExpired: log(name + ': no respondió a SIGKILL')


def engine_environment():
    env = os.environ.copy()
    agent_path = AGENT if AGENT.exists() else AGENT_SNAPSHOT
    if agent_path.exists():
        with agent_path.open('rb') as f:
            p = plistlib.load(f)
        if p.get('Label') != 'com.mrseivane.syn.dvr2':
            raise RuntimeError('LaunchAgent antiguo inesperado; no arranco')
        for k, v in p.get('EnvironmentVariables', {}).items():
            if isinstance(k, str) and isinstance(v, str):
                env[k] = v
    env.setdefault('SYN_DVR_POOL_SERVER', str(ENGINE_DIR / 'bin/hls_server.py'))
    env.setdefault('SYN_DVR_POOL_PYTHON', PYTHON)
    if not Path(env['SYN_DVR_POOL_SERVER']).is_file():
        raise RuntimeError('Falta el servidor HLS local del motor')
    if not Path(env['SYN_DVR_POOL_PYTHON']).is_file():
        raise RuntimeError('Falta Python para el HLS local')
    return env


def api_port():
    data = json.loads(API_CONFIG.read_text(encoding='utf-8'))
    port = int(data['port'])
    if not 1024 <= port <= 65535:
        raise RuntimeError('Puerto HTTPS fuera de rango')
    return port


def start_api(out):
    return subprocess.Popen([PYTHON, str(API_PROGRAM), 'serve'],
                            stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                            start_new_session=True, close_fds=True)


def health(port):
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(f'https://127.0.0.1:{port}/health',
                                context=ctx, timeout=1) as response:
        return bool(json.load(response).get('ok'))


def await_api(proc, port):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('La API HTTPS terminó al arrancar')
        try:
            if health(port):
                return
        except (OSError, ValueError, ssl.SSLError, TimeoutError):
            pass
        time.sleep(.25)
    raise RuntimeError('La API HTTPS no respondió en el puerto configurado')


def await_engine(proc):
    deadline = time.monotonic() + 15
    path = ENGINE_DIR / 'worker.heartbeat.json'
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('El motor terminó al arrancar (¿bloqueado por otra instancia?)')
        try:
            obj = json.loads(path.read_text())
            if int(obj['pid']) == proc.pid and time.time() - float(obj['timestamp']) < 5:
                port = int((ENGINE_DIR / 'pool.port').read_text().strip())
                if 1 <= port <= 65535:
                    with socket.create_connection(('127.0.0.1', port), timeout=.5):
                        return
        except (OSError, ValueError, TypeError, KeyError):
            pass
        time.sleep(.25)
    raise RuntimeError('El motor DVR no respondió (sin iniciar ninguna tarea)')


def on_signal(signum, frame):
    global exit_requested
    exit_requested = True


def run():
    """Run the recorder first. HTTPS is an optional capability, not a prerequisite."""
    global children
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    REMOTE_DIR.mkdir(parents=True, exist_ok=True)
    # Only the app's own user data; no chmod of other people's folders.
    if not ENGINE_PROGRAM.is_file() or not os.access(ENGINE_PROGRAM, os.X_OK):
        raise RuntimeError('No se encuentra el motor DVR incluido en la aplicación')
    env = engine_environment()
    api = None
    engine = None
    remote_detail = ''
    with (REMOTE_DIR / 'standalone.children.log').open('ab', buffering=0) as out:
        def launch_optional_api():
            nonlocal api, remote_detail
            if api is not None:
                safe_stop(api, 'Servidor HTTPS')
                api = None
            try:
                if not API_PROGRAM.is_file():
                    raise RuntimeError('Servidor remoto no incluido')
                # Idempotent; preserves configured port, password, keys and recordings.
                subprocess.run([PYTHON, str(API_PROGRAM), 'prepare'],
                               stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                               env=env, timeout=45, check=True)
                api = start_api(out)
                children.append(api)
                await_api(api, api_port())
                remote_detail = ''
                log('Servidor HTTPS disponible')
            except Exception as exc:
                if api is not None:
                    safe_stop(api, 'Servidor HTTPS')
                api = None
                remote_detail = str(exc)[:180]
                log('Servidor HTTPS no disponible (motor sigue activo): ' + remote_detail)

        try:
            status('starting')
            # Critical: launch the only recording engine before the optional API.
            engine = subprocess.Popen([str(ENGINE_PROGRAM), 'serve'], env=env,
                                      stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=subprocess.STDOUT, start_new_session=True,
                                      close_fds=True)
            children.append(engine)
            await_engine(engine)
            status('running', None, engine, 'Motor DVR activo; configurando servidor remoto…')
            log('Motor DVR activo')
            launch_optional_api()
            while not exit_requested:
                if engine.poll() is not None:
                    raise RuntimeError('El motor de grabación se cerró: consulta standalone.children.log')
                if api is not None and api.poll() is not None:
                    api = None
                    remote_detail = 'El servidor HTTPS se ha cerrado'
                    log('Servidor HTTPS cerrado; las grabaciones continúan')
                r, _, _ = select.select([sys.stdin.buffer], [], [], 1)
                if r:
                    msg = os.read(sys.stdin.fileno(), 128)
                    if not msg:
                        log('Se ha cerrado la aplicación SYN DVR')
                        break
                    if b'reload' in msg:
                        launch_optional_api()
                detail = ('Motor DVR activo; servidor remoto no disponible: ' + remote_detail
                          if remote_detail else 'Motor DVR y servidor remoto activos')
                status('running', api, engine, detail)
        finally:
            status('stopping', api, engine)
            safe_stop(engine, 'Motor DVR')
            safe_stop(api, 'Servidor HTTPS')
            status('stopped')
            log('Motor DVR detenido')


if __name__ == '__main__':
    try:
        if len(sys.argv) == 2 and sys.argv[1] == 'check':
            engine_environment()
            required = [('motor DVR', ENGINE_PROGRAM),
                        ('servidor remoto', API_PROGRAM),
                        ('configuración de servidor', API_CONFIG)]
            missing = [f'{label}: {path}' for label, path in required if not path.is_file()]
            if missing:
                raise RuntimeError('Componentes ausentes: ' + ' | '.join(missing))
            print('OK: componentes autónomos disponibles')
        elif len(sys.argv) == 2 and sys.argv[1] == 'run':
            run()
        else:
            raise SystemExit('Uso: standalone_supervisor.py check|run')
    except Exception as e:
        status('error', detail=str(e))
        log('ERROR: ' + str(e))
        print('ERROR: ' + str(e), file=sys.stderr)
        sys.exit(1)
