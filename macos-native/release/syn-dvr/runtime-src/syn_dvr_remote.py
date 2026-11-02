#!/usr/bin/env python3
"""SYN DVR Remote 4.1: optionally authenticated HTTPS API to the EXISTING recorder queue.

Never starts a capture process or opens a provider URL; one existing engine owns
all streams. No third-party Python packages are required.
"""
import argparse
import base64
import contextlib
import datetime
import hashlib
import hmac
import http.server
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid

ROOT = Path(os.environ.get('SYN_DVR_REMOTE_HOME', str(Path.home() / 'Library/Application Support/SYN DVR Remote'))).expanduser()
ENGINE = Path(os.environ.get('SYN_DVR_ENGINE_HOME', str(Path.home() / 'Library/Application Support/SYN DVR Engine 2.0'))).expanduser()
CONFIG = ROOT / 'server.json'
AUTH = ROOT / 'auth.json'
CERT = ROOT / 'tls.crt'
KEY = ROOT / 'tls.key'
HEARTBEAT = ROOT / 'server.heartbeat.json'
MAX_REQUEST_BYTES = 32768
ITERATIONS = 400000
TERMINAL = {'finished', 'completed', 'failed', 'cancelled', 'partial', 'expired'}
STATES = {'scheduled','recording','reconnecting','retrying','waiting_for_tuner','stopping',*TERMINAL}


def ensure_root():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)


def atomic_json(path, data, mode=0o600):
    ensure_root() if path.parent == ROOT else path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.syn-tmp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            os.fchmod(f.fileno(), mode)
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(temp)


def load_json(p, fallback=None):
    try:
        with p.open(encoding='utf-8') as f: return json.load(f)
    except (OSError, ValueError): return fallback


def fingerprint():
    if not CERT.exists(): return ''
    pem = CERT.read_text()
    match = re.search(r'-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----', pem, re.S)
    if match is None: return ''
    der = base64.b64decode(re.sub(r'\s+', '', match.group(1)))
    return hashlib.sha256(der).hexdigest().upper()


def set_password(value):
    if not value:
        raise ValueError('Activa la contraseña e introduce al menos un carácter, o desactívala')
    salt = secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac('sha256', value.encode('utf-8'), salt, ITERATIONS)
    atomic_json(AUTH, {'kind':'pbkdf2-sha256','iterations': ITERATIONS,
                       'salt':salt.hex(),'digest':digest.hex()})


def verify_password(value):
    conf = load_json(AUTH)
    if not isinstance(conf, dict) or conf.get('kind') != 'pbkdf2-sha256': return False
    try:
        iterations=int(conf['iterations'])
        if not (200000 <= iterations <= 1000000): return False
        expected = bytes.fromhex(conf['digest'])
        salt=bytes.fromhex(conf['salt'])
        actual=hashlib.pbkdf2_hmac('sha256', value.encode('utf-8'), salt, iterations)
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError,KeyError,OverflowError): return False


def validate_config(data):
    if not isinstance(data,dict): raise ValueError('Configuración inválida')
    bind = data.get('bind', '0.0.0.0')
    if bind not in ('0.0.0.0','127.0.0.1'): raise ValueError('Solo escucha LAN o localhost')
    port = int(data.get('port',8090))
    if not 1024 <= port <= 65535: raise ValueError('Puerto permitido: 1024–65535')
    folder = Path(data.get('recordingsFolder',str(Path.home()/'Movies/SYN Grabaciones'))).expanduser()
    if not folder.is_absolute() or folder == Path('/'): raise ValueError('Carpeta de grabaciones inválida')
    folder.mkdir(parents=True,exist_ok=True)
    if not folder.is_dir() or not os.access(folder, os.W_OK | os.X_OK):
        raise ValueError('La carpeta no tiene permisos de escritura')
    return {'bind':bind,'port':port,'recordingsFolder':str(folder.resolve()),
            'createdAt':data.get('createdAt',time.time()),
            'authRequired':bool(data.get('authRequired',AUTH.exists()))}


def create_cert():
    if CERT.exists() and KEY.exists(): return
    if CERT.exists() or KEY.exists(): raise RuntimeError('Falta parte del par TLS; no se sobrescriben claves')
    openssl = shutil.which('openssl')
    if not openssl: raise RuntimeError('Necesito openssl para crear el certificado HTTPS')
    ensure_root()
    cmd=[openssl,'req','-x509','-newkey','rsa:3072','-sha256','-nodes','-days','825',
         '-keyout',str(KEY),'-out',str(CERT),'-subj','/CN=SYN DVR Local',
         '-addext','subjectAltName=DNS:localhost,IP:127.0.0.1']
    r=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=30)
    if r.returncode != 0:
        # Some macOS LibreSSL releases do not support -addext; use an
        # explicit OpenSSL configuration with identical SAN extensions.
        with contextlib.suppress(FileNotFoundError): KEY.unlink()
        with contextlib.suppress(FileNotFoundError): CERT.unlink()
        config=ROOT/'openssl-tls.cfg'
        config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=SYN DVR Local\n[ext]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n')
        config.chmod(0o600)
        retry=[openssl,'req','-x509','-newkey','rsa:3072','-sha256','-nodes',
               '-days','825','-keyout',str(KEY),'-out',str(CERT),'-config',str(config)]
        r=subprocess.run(retry,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=30)
        config.unlink(missing_ok=True)
        if r.returncode != 0:
            with contextlib.suppress(FileNotFoundError): KEY.unlink()
            with contextlib.suppress(FileNotFoundError): CERT.unlink()
            raise RuntimeError('No se pudo generar TLS: '+r.stderr[:200])
    KEY.chmod(0o600); CERT.chmod(0o600)


def machine_addresses():
    found=['127.0.0.1']
    if sys.platform=='darwin':
        try:
            out=subprocess.run(['/sbin/ifconfig'],capture_output=True,text=True,timeout=5).stdout
            for m in re.finditer(r'\binet (\d+\.\d+\.\d+\.\d+)\b',out):
                ip=m.group(1)
                if ip != '127.0.0.1' and ipaddress.ip_address(ip).is_private and ip not in found:
                    found.append(ip)
        except (OSError,subprocess.TimeoutExpired): pass
    else:
        try:
            for item in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
                ip=item[4][0]
                if ipaddress.ip_address(ip).is_private and ip not in found: found.append(ip)
        except OSError: pass
    return found


def jobdir(): return ENGINE / 'jobs'


def pool_snapshot():
    d=load_json(ENGINE / 'pool.status.json',{})
    if not isinstance(d,dict) or abs(time.time()-float(d.get('timestamp',0)))>15: return {}
    return d


def worker_snapshot():
    d=load_json(ENGINE / 'worker.heartbeat.json',{})
    if not isinstance(d,dict): return {}
    try:
        if abs(time.time()-float(d.get('timestamp',0))) > 15: return {}
        os.kill(int(d['pid']),0)
        return {'running':True,'version':d.get('version','3.x')}
    except (KeyError,TypeError,ValueError,ProcessLookupError,PermissionError): return {}


def jobs_snapshot():
    result=[]
    for path in jobdir().glob('*.json'):
        if path.name.endswith('.status.json'): continue
        try: identifier=str(uuid.UUID(path.stem)).upper()
        except ValueError: continue
        j=load_json(path)
        if not isinstance(j,dict): continue
        s=load_json(jobdir()/(identifier+'.status.json'),{}) or {}
        if not isinstance(s,dict): s={}
        state=s.get('state','scheduled')
        parts=s.get('parts',[])
        result.append({'id':identifier,'channel':str(j.get('channel',''))[:160],
                       'title':str(j.get('title',''))[:300],
                       'start':j.get('start'), 'end':j.get('end'),
                       'state':state,'startedAt':s.get('startedAt'),
                       'finishedAt':s.get('finishedAt'), 'receivedBytes':s.get('receivedBytes',0),
                       'segments':len(parts) if isinstance(parts,list) else 0,
                       'retryAt':s.get('retryAt'),'retries':s.get('retries',0),
                       'updatedAt':s.get('updatedAt'),'warning':s.get('warning'),
                       'outputPath':s.get('outputPath')})
    return sorted(result,key=lambda x:x.get('start') or 0,reverse=True)


def disk_snapshot(folder):
    try:
        disk=shutil.disk_usage(folder)
        return {'freeBytes':disk.free,'totalBytes':disk.total,'usedBytes':disk.used}
    except OSError: return {'freeBytes':None,'totalBytes':None,'usedBytes':None}


def memory_snapshot():
    result={'totalBytes':None,'freeApproxBytes':None,'pressure':'unknown'}
    if sys.platform == 'darwin':
        try:
            result['totalBytes']=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'],timeout=3).strip())
        except (OSError,subprocess.SubprocessError,ValueError): pass
        try:
            p=subprocess.run(['/usr/bin/memory_pressure','-Q'],capture_output=True,text=True,timeout=4)
            m=re.search(r'System-wide free memory percentage:\s*(\d+)%',p.stdout)
            if m and result['totalBytes']:
                result['freeApproxBytes']=int(result['totalBytes']*int(m.group(1))/100)
        except (OSError,subprocess.SubprocessError): pass
        # Apple reports a discrete memory-pressure level; never manufacture a percentage.
        try:
            raw=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'],
                                        timeout=3,stderr=subprocess.DEVNULL).strip()
            result['pressure']={1:'normal',2:'warning',4:'critical'}.get(int(raw),'unknown')
        except (OSError,subprocess.SubprocessError,ValueError): pass
    else:
        try:
            result['totalBytes']=int(os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE'))
            result['freeApproxBytes']=int(os.sysconf('SC_AVPHYS_PAGES')*os.sysconf('SC_PAGE_SIZE'))
        except (ValueError,OSError): pass
    return result


def status_snapshot():
    conf=load_json(CONFIG,{}) or {}
    pool=pool_snapshot()
    entries=jobs_snapshot()
    return {'product':'SYN DVR','apiVersion':'1.0','serverVersion':'4.1.0',
            'serverTime':time.time(),'engine':worker_snapshot(),
            'connections':{'used':pool.get('occupied'),
                           'limit':pool.get('maxConnections')},
            'jobs':{'active':sum(j['state'] in ('recording','reconnecting','retrying','waiting_for_tuner','stopping') for j in entries),
                    'scheduled':sum(j['state']=='scheduled' for j in entries)},
            'storage':disk_snapshot(conf.get('recordingsFolder',str(Path.home()))),
            'memory':memory_snapshot()}


class Service(http.server.ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,addr,handler):
        super().__init__(addr,handler)
        self.failed={}
        self.failed_lock=threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version='SYN-DVR/4'
    sys_version=''
    def log_message(self, format, *args):
        # Never log URLs, passwords, query strings, or supplied headers.
        pass

    def response(self,code,obj):
        data=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        conf=load_json(CONFIG,{}) or {}
        if not conf.get('authRequired',AUTH.exists()):
            return True
        addr=self.client_address[0]
        with self.server.failed_lock:
            prev=self.server.failed.get(addr,(0,0))
            if prev[0]>=8 and time.monotonic()-prev[1]<60: return False
        encoded=self.headers.get('X-SYN-DVR-Password-B64')
        if encoded is not None:
            try:
                guess=base64.b64decode(encoded,validate=True).decode('utf-8')
            except (ValueError,UnicodeDecodeError,base64.binascii.Error):
                guess=''
        else:
            guess=self.headers.get('X-SYN-DVR-Password','')
        valid=verify_password(guess)
        if not valid:
            with self.server.failed_lock:
                n,t=self.server.failed.get(addr,(0,0))
                self.server.failed[addr]=(n+1 if time.monotonic()-t<60 else 1,time.monotonic())
        else:
            with self.server.failed_lock: self.server.failed.pop(addr,None)
        return valid

    def endpoint(self):
        parsed=urllib.parse.urlsplit(self.path)
        if parsed.query or parsed.fragment: return None
        return parsed.path

    def process(self,method):
        path=self.endpoint()
        if path is None: return self.response(400,{'error':'No se admiten parámetros en la URL'})
        if path=='/health' and method=='GET':
            return self.response(200,{'ok':True,'service':'SYN DVR'})
        if not self.authorized(): return self.response(401,{'error':'Credenciales inválidas'})
        if method=='GET':
            if path=='/api/v1/status': return self.response(200,status_snapshot())
            if path=='/api/v1/jobs': return self.response(200,{'jobs':jobs_snapshot()})
            if path=='/api/v1/server':
                c=load_json(CONFIG,{}) or {}
                return self.response(200,{'ipAddresses':machine_addresses(),
                                           'port':c.get('port'), 'bind':c.get('bind'),
                                           'recordingsFolder':c.get('recordingsFolder'),
                                           'certificateSHA256':fingerprint()})
            return self.response(404,{'error':'Ruta no encontrada'})
        if method not in ('POST','DELETE'): return self.response(405,{'error':'Método no permitido'})
        if method=='POST' and self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
            return self.response(415,{'error':'Se necesita application/json'})
        try:
            length=int(self.headers.get('Content-Length','-1'))
        except ValueError: length=-1
        if method=='DELETE' and length<0: length=0
        if length<0 or length>MAX_REQUEST_BYTES: return self.response(413,{'error':'Petición demasiado grande'})
        body=self.rfile.read(length)
        try: payload=json.loads(body) if body else {}
        except (UnicodeError,ValueError): return self.response(400,{'error':'JSON inválido'})
        if not isinstance(payload,dict): return self.response(400,{'error':'Objeto JSON requerido'})
        if method=='POST' and path=='/api/v1/jobs':
            return self.submit_job(payload)
        match=re.fullmatch(r'/api/v1/jobs/([0-9a-fA-F-]{36})(/cancel)?',path)
        if match:
            try: ident=str(uuid.UUID(match.group(1))).upper()
            except ValueError: return self.response(400,{'error':'UUID inválido'})
            task=jobdir()/(ident+'.json')
            if not task.is_file(): return self.response(404,{'error':'No existe esa tarea'})
            if method=='POST' and match.group(2)=='/cancel':
                p=jobdir()/(ident+'.cancel')
                atomic_json(p,{'cancel':True})
                return self.response(202,{'accepted':True,'id':ident})
            if method=='DELETE' and not match.group(2):
                state=(load_json(jobdir()/(ident+'.status.json'),{}) or {}).get('state','scheduled')
                if state not in TERMINAL: return self.response(409,{'error':'Cancela antes la grabación'})
                for suffix in ('.json','.status.json','.cancel'):
                    with contextlib.suppress(FileNotFoundError): (jobdir()/(ident+suffix)).unlink()
                return self.response(200,{'deleted':True,'filesPreserved':True})
        return self.response(404,{'error':'Ruta no encontrada'})

    def submit_job(self,p):
        conf=load_json(CONFIG,{}) or {}
        url=p.get('url'); start=p.get('start'); end=p.get('end')
        channel=p.get('channel'); title=p.get('title')
        if not isinstance(url,str) or len(url)>8192 or urllib.parse.urlsplit(url).scheme not in ('http','https'):
            return self.response(422,{'error':'URL IPTV HTTP(S) inválida'})
        if not isinstance(channel,str) or not channel.strip() or len(channel)>180 or not isinstance(title,str) or not title.strip() or len(title)>300:
            return self.response(422,{'error':'Canal o título inválido'})
        if isinstance(start,bool) or isinstance(end,bool) or not all(isinstance(v,(int,float)) for v in (start,end)):
            return self.response(422,{'error':'Fechas inválidas'})
        if not all(v==v and abs(v)<1e15 for v in (start,end)) or end<=start or end-start>48*3600 or end<time.time():
            return self.response(422,{'error':'Intervalo inválido'})
        ident=str(uuid.uuid4()).upper()
        job={'url':url,'channel':channel,'title':title,'start':float(start),
             'end':float(end),'folder':conf['recordingsFolder']}
        jobdir().mkdir(parents=True,exist_ok=True,mode=0o700)
        # Atomic writes mirror SYN DVR engine queue. No second engine starts.
        atomic_json(jobdir()/(ident+'.json'),job)
        return self.response(201,{'id':ident,'state':'scheduled'})

    def do_GET(self):
        try: self.process('GET')
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception: self.response(500,{'error':'Error interno'})
    def do_POST(self):
        try: self.process('POST')
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception: self.response(500,{'error':'Error interno'})
    def do_DELETE(self):
        try: self.process('DELETE')
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception: self.response(500,{'error':'Error interno'})


def serve():
    if not (CONFIG.exists() and CERT.exists() and KEY.exists()):
        raise SystemExit('Primero ejecuta la configuración inicial')
    c=validate_config(load_json(CONFIG))
    if not ENGINE.exists(): raise SystemExit('Falta SYN DVR Engine 3.x')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(CERT),str(KEY))
    server=Service((c['bind'],c['port']),Handler)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    stop=threading.Event()
    def pulse():
        while not stop.is_set():
            atomic_json(HEARTBEAT,{'pid':os.getpid(),'timestamp':time.time(),'port':c['port']})
            stop.wait(5)
    thread=threading.Thread(target=pulse,daemon=True)
    thread.start()
    print(f'SYN DVR Remote HTTPS :{c["port"]}',flush=True)
    try: server.serve_forever(poll_interval=.5)
    finally:
        stop.set();thread.join(timeout=2)
        server.server_close()
        with contextlib.suppress(OSError): HEARTBEAT.unlink()


def prepare():
    # No terminal prompts. User configures IP/port/folder/password in MenuBar.
    existing=load_json(CONFIG,{}) or {}
    if not isinstance(existing,dict): raise ValueError('Configuración existente no válida')
    if not CONFIG.exists():
        existing={'bind':'127.0.0.1','port':8090,
                  'recordingsFolder':str(Path.home()/'Movies/SYN Grabaciones'),
                  'authRequired':False,'createdAt':time.time()}
    elif 'authRequired' not in existing:
        # Preserve legacy password protection, never silently downgrade.
        existing['authRequired']=AUTH.exists()
    new=validate_config(existing)
    if new['authRequired'] and not AUTH.exists():
        raise ValueError('Servidor protegido sin verificador de contraseña')
    create_cert()
    atomic_json(CONFIG,new)
    return new


def configure(data,first=False):
    if not isinstance(data,dict): raise ValueError('Objeto de configuración requerido')
    c=load_json(CONFIG,{}) or {}
    if not isinstance(c,dict): raise ValueError('Configuración existente no válida')
    for name in ('bind','port','recordingsFolder'):
        if name in data: c[name]=data[name]
    if 'createdAt' not in c: c['createdAt']=time.time()
    enabled=data.get('authRequired', bool(data.get('password')) or c.get('authRequired',AUTH.exists()))
    if not isinstance(enabled,bool): raise ValueError('authRequired debe ser booleano')
    c['authRequired']=enabled
    password=data.get('password','')
    if not isinstance(password,str): raise ValueError('Contraseña no válida')
    new=validate_config(c)
    if enabled and not password and not AUTH.exists():
        raise ValueError('Introduce una contraseña o desactiva la protección')
    # Do not change current security or destination if validation fails.
    create_cert()
    if enabled and password: set_password(password)
    atomic_json(CONFIG,new)
    return new


def cli():
    parser=argparse.ArgumentParser(description='SYN DVR Remote 4.1')
    sub=parser.add_subparsers(dest='cmd',required=True)
    sub.add_parser('serve')
    sub.add_parser('info')
    sub.add_parser('prepare',help='Valores por defecto sin preguntas')
    sub.add_parser('configure-stdin',help='JSON por stdin; configura la interfaz gráfica')
    args=parser.parse_args()
    if args.cmd=='serve': serve(); return
    if args.cmd=='prepare':
        prepare();print('✅ Servidor preparado; ajusta todo desde SYN DVR → Servidor.');return
    if args.cmd=='info':
        c=load_json(CONFIG,{}) or {}
        if c:
            print('Direcciones: '+', '.join(machine_addresses()))
            print('Puerto:',c.get('port'))
            print('Carpeta:',c.get('recordingsFolder'))
            print('Contraseña:', 'activada' if c.get('authRequired',AUTH.exists()) else 'desactivada')
            print('Motor:', 'activo' if worker_snapshot() else 'sin latido reciente')
        else: print('Configura el servidor en la interfaz SYN DVR')
        return
    if args.cmd=='configure-stdin':
        blob=sys.stdin.buffer.read(MAX_REQUEST_BYTES+1)
        if len(blob)>MAX_REQUEST_BYTES: raise SystemExit('Entrada demasiado grande')
        try: data=json.loads(blob)
        except (ValueError,UnicodeDecodeError): raise SystemExit('Entrada JSON inválida')
        try: configure(data)
        except (ValueError,OSError,RuntimeError) as e: raise SystemExit(str(e))
        print('✅ Ajustes guardados. Reiniciando la API se aplicarán los cambios.')

if __name__=='__main__': cli()
