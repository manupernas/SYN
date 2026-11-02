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
ENGINE_PROGRAM = ENGINE_DIR / 'bin/syn-dvr-engine'
API_PROGRAM = REMOTE_DIR / 'syn_dvr_remote.py'
API_CONFIG = REMOTE_DIR / 'server.json'
AGENT = HOME / 'Library/LaunchAgents/com.mrseivane.syn.dvr2.plist'
AGENT_SNAPSHOT = REMOTE_DIR / 'standalone.engine-agent.plist'
STATUS = REMOTE_DIR / 'standalone.status.json'
LOG = REMOTE_DIR / 'standalone.log'
PYTHON = '/usr/bin/python3'
children = []
exit_requested = False


def log(msg):
    REMOTE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + msg + '\n')


def status(state, api=None, engine=None, detail=''):
    data = {'timestamp': time.time(), 'supervisorPID': os.getpid(),
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
    global children
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    REMOTE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(REMOTE_DIR, 0o700)
    if not ENGINE_PROGRAM.is_file() or not os.access(ENGINE_PROGRAM, os.X_OK):
        raise RuntimeError('No encuentro el motor DVR instalado')
    if not API_PROGRAM.is_file() or not API_CONFIG.is_file():
        raise RuntimeError('No está instalado o configurado SYN DVR Remote')
    env = engine_environment()
    port = api_port()
    api = None
    engine = None
    with (REMOTE_DIR / 'standalone.children.log').open('ab', buffering=0) as out:
        try:
            status('starting')
            api = start_api(out)
            children.append(api)
            await_api(api, port)
            engine = subprocess.Popen([str(ENGINE_PROGRAM), 'serve'], env=env,
                                      stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=subprocess.STDOUT, start_new_session=True,
                                      close_fds=True)
            children.append(engine)
            await_engine(engine)
            status('running', api, engine)
            log('Servidor autónomo iniciado y verificado')
            # stdin is a dedicated PIPE from the GUI. EOF means GUI closed,
            # including crashes and Force Quit. No detach / daemonize.
            while not exit_requested:
                if api.poll() is not None:
                    raise RuntimeError('La API HTTPS se ha cerrado: detengo también el motor')
                if engine.poll() is not None:
                    raise RuntimeError('El motor DVR se ha cerrado: detengo también la API')
                r, _, _ = select.select([sys.stdin.buffer], [], [], 1)
                if r:
                    msg = os.read(sys.stdin.fileno(), 128)
                    if not msg:
                        log('La aplicación SYN DVR se ha cerrado')
                        break
                    if b'reload' in msg:
                        # Only an API restart. Keep existing recording processes.
                        safe_stop(api, 'API HTTPS')
                        api = start_api(out)
                        children[0] = api
                        await_api(api, api_port())
                        log('API HTTPS reiniciada después de cambiar la configuración')
                # Authoritative liveness check: a dead/misconfigured API
                # must not leave the engine recording on its own.
                try:
                    ok = health(api_port())
                except (OSError, ValueError, ssl.SSLError, TimeoutError):
                    ok = False
                if not ok:
                    raise RuntimeError('La API HTTPS dejó de responder: detengo también el motor')
                status('running', api, engine)
        finally:
            status('stopping', api, engine)
            # Engine first so recordings and provider connections get SIGTERM.
            safe_stop(engine, 'Motor DVR')
            safe_stop(api, 'API HTTPS')
            status('stopped')
            log('Servidor autónomo detenido')


if __name__ == '__main__':
    try:
        if len(sys.argv) == 2 and sys.argv[1] == 'check':
            engine_environment()
            assert ENGINE_PROGRAM.is_file() and API_PROGRAM.is_file() and API_CONFIG.is_file()
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
