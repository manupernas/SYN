#!/usr/bin/env python3
"""SYN Cast Beta6: loopback-authenticated Cast control; provider URLs never logged."""
import json
import re
import mimetypes
import os
import secrets
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PORT = 18976
QUALITY_FILE = Path.home() / 'Library/Application Support/SYN Alpha/cast-quality'
QUALITY_PROFILES = {
    # SYN_CAST_SHARED_RELAY_BETA6_4: H264/AAC settings unchanged.
    # SYN_CAST_FHD1080_OPTIONAL_BETA6_5: opt-in 1080p at up to 7 Mbps.
    'alta': {'height': 1080, 'bitrate': '6300k', 'maxrate': '7500k', 'bufsize': '14000k'},
    'compatible': {'height': 720, 'bitrate': '2500k', 'maxrate': '3000k', 'bufsize': '4000k'},
    'ligero': {'height': 480, 'bitrate': '1200k', 'maxrate': '1600k', 'bufsize': '2000k'},
    'solo-audio': {'height': 0, 'bitrate': '', 'maxrate': '', 'bufsize': ''},
}

def selected_quality():
    try:
        value=QUALITY_FILE.read_text('utf-8').strip()
    except OSError:
        value='compatible'
    return value if value in QUALITY_PROFILES else 'compatible'

def _ffmpeg_has_encoder(ffmpeg, encoder):
    try:
        out=subprocess.run([ffmpeg,'-hide_banner','-encoders'],
                           capture_output=True, text=True, timeout=8, check=True)
        return re.search(r'^\s*[VAS]\S*\s+'+re.escape(encoder)+r'\s',
                         out.stdout,re.MULTILINE) is not None
    except (subprocess.SubprocessError, OSError):
        return False

def cast_hls_command(ffmpeg, url, ua, folder, playlist, quality):
    """Turn IPTV into Chromecast-compatible H.264/AAC HLS with fixed GOP.

    Input URL stays in a process argument as before; never emit command/log.
    """
    preset=QUALITY_PROFILES[quality]
    cmd=[ffmpeg,'-nostdin','-hide_banner','-loglevel','error',
         '-stats_period','2','-progress','pipe:1',
         '-fflags','+genpts+discardcorrupt',
         '-user_agent',ua or 'VLC/3.0.21 LibVLC/3.0.21',
         '-i',url,'-map','0:v:0?','-map','0:a:0?',
         '-max_muxing_queue_size','1024']
    if quality=='solo-audio':
        # Emergency low-CPU mode: video stream-copy can still have bad keyframes.
        cmd+=['-c:v','copy']
    else:
        h=preset['height']
        # Preserve aspect ratio; never upscale; frame-rate and keyframes predictable.
        if quality=='alta':
            # Limit to Full HD. Do not upscale 720p/SD sources to 1080p.
            scale=("fps=25,scale=w='min(iw,1920)':h='min(ih,1080)':"
                   'force_original_aspect_ratio=decrease:force_divisible_by=2,'
                   'setsar=1,format=yuv420p')
        else:
            scale=(f'scale=w={1280 if h==720 else 854}:h={h}:'
                   'force_original_aspect_ratio=decrease:force_divisible_by=2,'
                   'setsar=1,fps=25,format=yuv420p')
        # SYN_CAST_1080_BALANCE_V1: CABAC + deblock improve compression at
        # low CPU cost. Preserve ultrafast and the proven Mi Box handshake.
        if quality=='alta':
            cmd+=['-coder','ac','-deblock','0:0']
        cmd+=['-vf',scale,'-c:v','libx264','-preset','ultrafast',
              '-tune','zerolatency','-profile:v',('main' if quality=='alta' else 'baseline'),
              '-level',('4.0' if quality=='alta' else '3.1'),
              '-r','25','-g',('25' if quality=='alta' else '50'),
              '-keyint_min',('25' if quality=='alta' else '50'),'-sc_threshold','0',
              '-force_key_frames',('expr:gte(t,n_forced*1)' if quality=='alta'
                                   else 'expr:gte(t,n_forced*2)'),
              '-b:v',preset['bitrate'],'-maxrate',preset['maxrate'],
              '-bufsize',preset['bufsize'],'-pix_fmt','yuv420p']
    cmd+=['-c:a','aac','-b:a','128k','-ac','2','-ar','48000',
          '-af','aresample=async=1:first_pts=0',
          '-f','hls']
    # Full HD: segmentos iniciales cortos; luego conservar objetivo de 2 s.
    if quality=='alta':
        cmd+=['-hls_init_time','1']
    cmd+=['-hls_time','2', '-hls_list_size','10',
          '-hls_delete_threshold','5',
          '-hls_flags', ('delete_segments+omit_endlist+independent_segments' if quality!='solo-audio'
                         else 'delete_segments+omit_endlist'),
          '-hls_segment_filename',str(folder/'chunk_%05d.ts'),str(playlist)]
    return cmd

def read_progress(stdout, metrics):
    """Progress metadata only, no stream URL is logged or printed."""
    try:
        for raw in iter(stdout.readline,b''):
            line=raw.decode('utf-8','replace').strip()
            if line.startswith('speed='):
                v=line.partition('=')[2].strip().removesuffix('x')
                try:
                    speed=float(v)
                    if 0 <= speed < 100:
                        metrics['speed']=round(speed,2)
                except ValueError:pass
            if line.startswith('out_time_ms='):
                try:metrics['output_seconds']=max(0,int(line.partition('=')[2])/1e6)
                except ValueError:pass
    except (OSError, ValueError):
        pass
TOKEN_FILE = Path.home() / 'Library/Application Support/SYN Alpha/cast-token'
LOCK = threading.RLock()
CURRENT = {'device': None, 'name': None, 'cast': None, 'browser': None,
           'ffmpeg': None, 'media_server': None, 'media_thread': None,
           'tempdir': None, 'title': None, 'mode': None,
           'capacity': 1, 'exclusive': False, 'parallel': False,
           'shared_local': False, 'local_url': '',
           'errfile': None, 'media_ip': '', 'media_hits': {'m3u8':0, 'ts':0},
           'encoding': 'compatible', 'encoder_metrics': {}}
LAST_DIAG = {'status':'Aún no se ha probado Cast', 'media_ip':'',
             'manifest_requests':0,'segment_requests':0, 'cast_state':'IDLE',
             'detail':'', 'http_errors':0, 'encoding':'compatible',
             'encoder_speed':None,'quality_patch':'SYN_CAST_1080_BALANCE_V1'}


# On some macOS sessions multicast discovery is intermittent even though
# direct unicast discovery (known_hosts) works with the Mi Box 4.
# This private file is editable by the user; no IPTV URLs are stored here.
KNOWN_CAST_HOSTS_FILE = TOKEN_FILE.parent / 'cast-known-hosts.txt'


def known_cast_hosts():
    import ipaddress
    try:
        lines = KNOWN_CAST_HOSTS_FILE.read_text('utf-8').splitlines()
    except FileNotFoundError:
        return []
    hosts = []
    for line in lines:
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        try:
            ip = ipaddress.ip_address(line)
        except ValueError:
            continue
        if (ip.is_private or ip.is_link_local) and line not in hosts:
            hosts.append(line)
    return hosts[:8]


def _discover_devices(wanted_id=None):
    """Return (infos, browser), preserving Zeroconf until the caller finishes.

    First use the same LAN discovery as Beta 3. If there are no video receivers
    or the selected UUID vanished, retry unicast with remembered LAN IPs.
    """
    import pychromecast
    infos, browser = pychromecast.discovery.discover_chromecasts(timeout=8)
    usable = [d for d in infos if d.cast_type not in ('audio', 'group')]
    if wanted_id is None:
        enough = bool(usable)
    else:
        enough = any(str(d.uuid) == str(wanted_id) for d in usable)
    hosts = known_cast_hosts()
    if enough or not hosts:
        return usable, browser
    browser.stop_discovery()
    # Same PyChromecast known_hosts API as the successfully tested Beta 3.
    infos, browser = pychromecast.discovery.discover_chromecasts(
        timeout=10, known_hosts=hosts)
    usable = [d for d in infos if d.cast_type not in ('audio', 'group')]
    return usable, browser


def scan():
    infos, browser = _discover_devices()
    try:
        return sorted([{'id': str(info.uuid),
                        'name': info.friendly_name or info.host,
                        'model': str(info.model_name or '')}
                       for info in infos],
                      key=lambda c: c['name'].casefold())
    finally:
        browser.stop_discovery()


def stop_cast(stop_remote=True):
    with LOCK:
        cast = CURRENT['cast']
        if cast and stop_remote:
            try: cast.media_controller.stop()
            except Exception: pass
        p = CURRENT['ffmpeg']
        if p:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try: p.kill()
                except Exception: pass
        srv = CURRENT['media_server']
        if srv:
            srv.shutdown()
            srv.server_close()
        b = CURRENT['browser']
        if b:
            try: b.stop_discovery()
            except Exception: pass
        if cast:
            try: cast.disconnect()
            except Exception: pass
        if CURRENT.get('media_ip'):
            LAST_DIAG.update(media_ip=CURRENT['media_ip'],
                             encoding=CURRENT.get('encoding'),
                             encoder_speed=CURRENT.get('encoder_metrics',{}).get('speed'),
                             manifest_requests=CURRENT['media_hits']['m3u8'],
                             segment_requests=CURRENT['media_hits']['ts'])
        errfile=CURRENT.get('errfile')
        if errfile:
            try:errfile.close()
            except Exception:pass
        td = CURRENT['tempdir']
        if td: td.cleanup()
        CURRENT.update(device=None, name=None, cast=None, browser=None,
                       ffmpeg=None, media_server=None, media_thread=None,
                       tempdir=None, title=None, mode=None,
                       capacity=1, exclusive=False, parallel=False,
                       shared_local=False, local_url='',
                       errfile=None,media_ip='',media_hits={'m3u8':0,'ts':0},
                       encoding='compatible',encoder_metrics={})



def _ffmpeg_hint(errfile):
    """Only return known error categories: never expose provider URLs/tokens."""
    try:
        errfile.flush()
        errfile.seek(0)
        msg=errfile.read(200000).decode('utf-8','replace').lower()
    except Exception:
        return 'FFmpeg no ha conseguido preparar el vídeo.'
    import re
    match=re.search(r'(?:server returned |http error |http/1\.\d[\s]+)(400|401|403|404|429|500|502|503)',msg)
    if match:
        return 'El servidor IPTV ha respondido HTTP '+match.group(1)+' al puente FFmpeg.'
    if 'invalid data found' in msg: return 'El stream IPTV contiene datos incompatibles o no válidos.'
    if '403 forbidden' in msg: return 'El servidor IPTV rechaza el acceso al stream (403).'
    if 'timed out' in msg: return 'El servidor IPTV agotó el tiempo de conexión.'
    if 'error while decoding' in msg: return 'FFmpeg ha encontrado errores al decodificar el canal.'
    if 'unknown encoder' in msg: return 'La instalación de FFmpeg no dispone del codificador necesario (H.264/AAC).'
    if 'unknown decoder' in msg or 'unsupported codec' in msg:
        return 'FFmpeg no reconoce un códec del stream.'
    return 'FFmpeg no ha podido abrir o segmentar el canal.'


def start_hls_relay(url, ua, cast_host):
    """HLS segmentado con CORS, MIME explícito y sin exponer la URL IPTV."""
    from http.server import SimpleHTTPRequestHandler
    from functools import partial
    import shutil
    import urllib.request
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('Falta FFmpeg en macOS: brew install ffmpeg')
    quality=selected_quality()
    if quality!='solo-audio' and not _ffmpeg_has_encoder(ffmpeg,'libx264'):
        raise RuntimeError('FFmpeg no tiene libx264; comprueba brew install ffmpeg.')
    if not _ffmpeg_has_encoder(ffmpeg,'aac'):
        raise RuntimeError('FFmpeg no tiene codificador AAC.')
    td=tempfile.TemporaryDirectory(prefix='syn-cast-')
    random_key=secrets.token_urlsafe(24)
    root=Path(td.name)
    folder=root/random_key
    folder.mkdir(mode=0o700)
    counters={'m3u8':0,'ts':0,'errors':0}
    metrics_lock=threading.Lock()
    class MediaHandler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def _count(self):
            # Strict matching avoids counting probes or requests outside the secret path.
            path=urlsplit(self.path).path
            if not path.startswith('/'+random_key+'/'):return
            with metrics_lock:
                if path.endswith('.m3u8'): counters['m3u8']+=1
                elif path.endswith('.ts'): counters['ts']+=1
        def do_GET(self):
            self._count();super().do_GET()
        def do_HEAD(self):
            self._count();super().do_HEAD()
        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header('Content-Length','0')
            self.end_headers()
        def end_headers(self):
            # Cast's HLS receiver performs cross-origin requests.
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Allow-Methods','GET, HEAD, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Range, Accept, Content-Type')
            self.send_header('Access-Control-Expose-Headers','Content-Length, Content-Range, Accept-Ranges')
            self.send_header('Cache-Control','no-cache, no-store')
            super().end_headers()
    mimetypes.add_type('application/vnd.apple.mpegurl','.m3u8',strict=True)
    mimetypes.add_type('video/mp2t','.ts',strict=True)
    try:
        server=ThreadingHTTPServer(('0.0.0.0',18977),partial(MediaHandler,directory=str(root)))
    except Exception:
        td.cleanup();raise
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    playlist=folder/'live.m3u8'
    errfile=tempfile.TemporaryFile(mode='w+b')
    cmd=cast_hls_command(ffmpeg,url,ua,folder,playlist,quality)
    proc=None
    metrics={'speed':None, 'output_seconds':0.0}
    try:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=errfile,start_new_session=True)
        threading.Thread(target=read_progress,args=(proc.stdout,metrics),daemon=True).start()
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            if proc.poll() is not None:raise RuntimeError(_ffmpeg_hint(errfile))
            if playlist.exists() and playlist.stat().st_size>40:
                manifest=playlist.read_text('utf-8',errors='replace')
                chunks=list(folder.glob('chunk_*.ts'))
                if '#EXTINF:' in manifest and chunks and max(c.stat().st_size for c in chunks)>188:
                    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                        sock.connect((cast_host,8009))
                        local_ip=sock.getsockname()[0]
                    link=f'http://{local_ip}:{server.server_port}/{random_key}/live.m3u8'
                    # Self-test on the LAN IP, not localhost: verifies bind/MIME/CORS.
                    with urllib.request.urlopen(link,timeout=3) as response:
                        if response.headers.get('Access-Control-Allow-Origin')!='*':
                            raise RuntimeError('Relay sin cabeceras CORS.')
                        if '#EXTM3U' not in response.read(256).decode('ascii','ignore'):
                            raise RuntimeError('El relay no ha generado una lista HLS válida.')
                    # Reset local probe hits before the receiver begins its requests.
                    with metrics_lock:
                        counters['m3u8']=0
                        counters['ts']=0
                    with LOCK:
                        CURRENT['encoder_metrics']=metrics
                        CURRENT['encoding']=quality
                        CURRENT['media_ip']=local_ip
                        CURRENT['media_hits']=counters
                        LAST_DIAG.update(status='Relay listo',media_ip=local_ip,
                                         manifest_requests=0,segment_requests=0,detail='',
                                         encoding=quality,encoder_speed=metrics.get('speed'))
                    return link,td,server,thread,proc,errfile
            time.sleep(.25)
        raise RuntimeError('FFmpeg no ha generado segmentos HLS: '+_ffmpeg_hint(errfile))
    except Exception:
        if proc:
            proc.terminate()
            try:proc.wait(timeout=2)
            except Exception:proc.kill()
        server.shutdown();server.server_close();errfile.close();td.cleanup()
        raise


def _failure_hint(cast_state,reason,proc,counters,errfile):
    """Classify failures without retaining the provider's private URL."""
    if proc and proc.poll() is not None:return _ffmpeg_hint(errfile)
    manifest=counters.get('m3u8',0)
    segment=counters.get('ts',0)
    if not manifest:
        return ('Chromecast no ha solicitado la lista HLS del Mac. '
                'Revisa que Mac y Mi Box estén en la misma red '
                'y el cortafuegos TCP 18977.')
    if not segment:
        return ('Chromecast solicita la lista HLS pero no los segmentos. '
                'Revisar formato HLS/CORS y la conexión al puerto 18977.')
    if reason=='ERROR':
        return 'Chromecast descarga los segmentos pero rechaza la reproducción; probable códec o formato no compatible.'
    return 'Chromecast descarga HLS pero no llega a reproducir (códec, buffering o red inestable).'


def start_cast(device_id,url,title,ua,relay=True,capacity=1,exclusive=True):
    if urlsplit(url).scheme not in ('http','https'):
        raise ValueError('Cast requiere canales HTTP(S), no archivos locales o UDP.')
    if len(url)>12000:raise ValueError('URL de canal demasiado larga.')
    capacity=max(1,min(8,int(capacity)))
    import pychromecast
    with LOCK:
        stop_cast()
        LAST_DIAG.update(status='Conectando',detail='',media_ip='',
                         manifest_requests=0,segment_requests=0,cast_state='UNKNOWN')
        infos,browser=_discover_devices(wanted_id=device_id)
        selected=next((info for info in infos if str(info.uuid)==str(device_id)),None)
        if selected is None:
            browser.stop_discovery()
            raise RuntimeError('No se encuentra el Chromecast seleccionado en la red.')
        cast=None
        try:
            # Same connection method that worked on the Mi Box 4 (Mac Beta 3).
            cast=pychromecast.get_chromecast_from_cast_info(
                selected,browser.zc,tries=2,retry_wait=1.0,timeout=6.0)
            cast.wait(timeout=15)
            play_url=url
            relay_resources=None
            if relay:
                play_url,*res=start_hls_relay(url,ua,cast.cast_info.host)
                relay_resources=res
            elif not urlsplit(url).path.lower().endswith('.m3u8'):
                raise RuntimeError('Sin FFmpeg solo es posible enviar HLS directo.')
            # The local MPV uses the SAME HLS relay as the TV, so a non-exclusive
            # session still occupies only one provider slot.
            shared_local=bool(relay and not exclusive)
            local_url=''
            if shared_local:
                remote_path=urlsplit(play_url).path
                local_url='http://127.0.0.1:18977'+remote_path
            CURRENT.update(device=device_id,name=cast.name,cast=cast,browser=browser,
                           title=title,mode='relay' if relay else 'direct',
                           capacity=capacity,exclusive=bool(exclusive),parallel=not bool(exclusive),
                           shared_local=shared_local,local_url=local_url)
            if relay_resources:
                (CURRENT['tempdir'],CURRENT['media_server'],CURRENT['media_thread'],
                 CURRENT['ffmpeg'],CURRENT['errfile'])=relay_resources
            # SYN_CAST_MIBOX_RECOVERY_1: if Android TV refuses the media LOAD
            # before fetching the manifest, reset the receiver and retry
            # without reopening the upstream IPTV connection or FFmpeg.
            class _CastLoadObserver:
                failed_code = None
                def new_media_status(self, status):
                    pass
                def load_media_failed(self, queue_item_id, error_code):
                    self.failed_code = error_code
            cast_probe = _CastLoadObserver()
            cast.media_controller.register_status_listener(cast_probe)
            cast.media_controller.play_media(play_url,'application/vnd.apple.mpegurl',
                                             stream_type='LIVE',title=title)
            retry_index = 0
            retry_time = time.monotonic()+8
            deadline=time.monotonic()+36
            start_wait=time.monotonic()
            state='UNKNOWN'
            reason=''
            while time.monotonic()<deadline:
                info=cast.media_controller.status
                state=info.player_state or 'UNKNOWN'
                reason=str(getattr(info,'idle_reason',None) or '')
                LAST_DIAG['cast_state']=state
                if state=='PLAYING':
                    LAST_DIAG.update(status='Chromecast informa PLAYING (verificar fluidez y sonido)',detail='',
                                     encoding=CURRENT.get('encoding','compatible'),
                                     encoder_speed=CURRENT.get('encoder_metrics',{}).get('speed'))
                    return {'name':cast.name,'mode':CURRENT['mode'],
                            'local_url':CURRENT['local_url'],
                            'local_shared':CURRENT['shared_local']}
                if CURRENT['ffmpeg'] and CURRENT['ffmpeg'].poll() is not None:
                    raise RuntimeError(_ffmpeg_hint(CURRENT['errfile']))
                # La rueda de carga no debe esconder una codificación < tiempo real.
                metrics=CURRENT.get('encoder_metrics',{})
                speed=metrics.get('speed')
                if (CURRENT.get('encoding')=='alta' and
                    time.monotonic()-start_wait>16 and
                    metrics.get('output_seconds',0)>=3 and
                    speed is not None and speed<0.80):
                    raise RuntimeError(
                        'La codificación 1080p no alcanza tiempo real ('+str(speed)+'x). '
                        'No se puede sostener el búfer Chromecast: prueba 720p '
                        'o revisa aceleración y consumo CPU.')
                # If the Mi Box didn't GET the manifest, the LOAD may be stuck.
                # Keep existing FFmpeg, HTTP relay, and IPTV connection running.
                if (CURRENT['media_hits']['m3u8']==0 and
                    retry_index < 2 and time.monotonic()>=retry_time):
                    retry_index += 1
                    if retry_index == 1:
                        try:
                            cast.quit_app()  # reset stale Default Media Receiver
                        except Exception:
                            pass
                        cast.media_controller.play_media(
                            play_url,'application/vnd.apple.mpegurl',
                            stream_type='BUFFERED',title=title)
                    else:
                        cast.media_controller.play_media(
                            play_url,'application/x-mpegURL',
                            stream_type='LIVE',title=title)
                    retry_time = time.monotonic()+8
                # Ignore an old IDLE from previous session during initial handshake.
                if (state=='IDLE' and reason in ('ERROR','CANCELLED') and
                    CURRENT['media_hits']['m3u8']>0 and
                    time.monotonic()<deadline-3):
                    # Receiver tried to fetch HLS and actually reported error.
                    # Without any manifest GET, wait for media LOAD recovery.
                    break
                time.sleep(.3)
            if CURRENT['ffmpeg']:
                hint=_failure_hint(state,reason,CURRENT['ffmpeg'],CURRENT['media_hits'],CURRENT['errfile'])
            else:hint='El Chromecast no confirmó reproducción.'
            if CURRENT['media_hits']['m3u8']==0:
                code = cast_probe.failed_code
                app_id = str(getattr(cast.status,'app_id',None) or 'desconocida')
                extra = ('LOAD_FAILED='+str(code) if code is not None
                         else 'sin código LOAD_FAILED')
                hint = ('La Mi Box rechazó/no cargó el HLS antes de pedirlo. '
                        'Estado='+str(state)+'; motivo='+str(reason or 'ninguno')+
                        '; '+extra+'; app='+app_id+'.')
            LAST_DIAG.update(status='Error de reproducción',detail=hint)
            raise RuntimeError(hint)
        except Exception:
            try:browser.stop_discovery()
            except Exception:pass
            try:cast.disconnect()
            except Exception:pass
            stop_cast()
            raise


def cast_dvr_guard():
    """Give DVR jobs priority before they start; Cast is the disposable session.

    The job database contains URLs and secrets: never log or transmit it.
    Active workers can be running while GUI is closed.
    """
    # The native Mac DVR uses its private data directory; never inspect Linux stores.
    paths=[Path.home()/'Library/Application Support/SYN Alpha/data/syn/dvr.json']
    while True:
        time.sleep(2)
        try:
            with LOCK:
                if not CURRENT['cast']:
                    continue
                capacity=CURRENT['capacity']
                local=1 if CURRENT['parallel'] and not CURRENT['shared_local'] else 0
                # Count planned jobs about to start, avoiding a new collision.
                jobs_by_id={}
                for path in paths:
                    try:
                        jobs=json.loads(path.read_text('utf-8')).get('jobs',[])
                    except FileNotFoundError:
                        continue
                    for job in jobs:
                        if isinstance(job,dict):
                            key=str(job.get('id') or (str(path),len(jobs_by_id)))
                            old=jobs_by_id.get(key)
                            # Conservatively prefer active states if stores disagree.
                            if old is None or job.get('status')=='running':
                                jobs_by_id[key]=job
                now=time.time()
                used=sum(1 for job in jobs_by_id.values() if
                    (job.get('status')=='running' or
                     (job.get('status')=='scheduled' and
                      float(job.get('start',0)) <= now+8)))
                if used+local+1>capacity:
                    stop_cast()  # Never terminate, reload or reconfigure any DVR job.
        except (ValueError,OSError,TypeError):
            # Unknown DVR state => conservative: stop casting.
            with LOCK:
                if CURRENT['cast']:
                    stop_cast()
        except Exception:
            with LOCK:
                if CURRENT['cast']:
                    stop_cast()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, code, body):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
    def do_POST(self):
        try:
            if not secrets.compare_digest(self.headers.get('X-Syn-Token',''),TOKEN):
                self.reply(403,{'error':'Sin autorización'});return
            size=int(self.headers.get('Content-Length','0'))
            if size<0 or size>25000:
                self.reply(413,{'error':'Solicitud demasiado grande'});return
            inp=json.loads(self.rfile.read(size))
            action=inp.get('action')
            if action=='devices':
                self.reply(200,{'devices':scan()})
            elif action=='play':
                d=start_cast(inp['device'],inp['url'],inp.get('title','SYN'),inp.get('ua',''),
                             bool(inp.get('relay',True)),
                             inp.get('capacity',1),inp.get('exclusive',True))
                self.reply(200,{'ok':True,**d})
            elif action=='local_usage':
                with LOCK:
                    if not CURRENT['cast'] or CURRENT['exclusive']:
                        self.reply(200,{'error':'No hay Cast paralelo activo.'})
                    elif not isinstance(inp.get('shared'),bool):
                        self.reply(200,{'error':'Estado local no válido.'})
                    else:
                        # Recheck reservations at the bridge. The GTK-side DVR
                        # snapshot may be stale during a scheduled job start.
                        def occupied_slots():
                            found={}
                            for db in (Path.home()/'Library/Application Support/SYN Alpha/data/syn/dvr.json',):
                                try: records=json.loads(db.read_text('utf-8')).get('jobs',[])
                                except FileNotFoundError: continue
                                for job in records:
                                    if not isinstance(job,dict): continue
                                    key=str(job.get('id') or (str(db),len(found)))
                                    if key not in found or job.get('status')=='running': found[key]=job
                            now=time.time()
                            return sum(1 for job in found.values() if
                                job.get('status')=='running' or
                                (job.get('status')=='scheduled' and
                                 float(job.get('start',0))<=now+8))
                        try: slots=occupied_slots()
                        except (OSError,ValueError,TypeError):
                            self.reply(200,{'error':'Estado DVR no verificable; cambio local cancelado.'})
                        else:
                            required=slots+1+(0 if inp['shared'] else 1)
                            if required>CURRENT['capacity']:
                                self.reply(200,{'error':'No quedan conexiones libres para cambiar el canal local.'})
                            else:
                                CURRENT['shared_local']=inp['shared']
                                self.reply(200,{'ok':True})
            elif action=='stop':
                stop_cast();self.reply(200,{'ok':True})
            elif action=='status':
                with LOCK:
                    cast=CURRENT['cast']
                    state=(cast.media_controller.status.player_state if cast else 'IDLE')
                    self.reply(200,{'active':cast is not None,'state':state or 'UNKNOWN',
                                    'name':CURRENT['name'] or '',
                                    'device':CURRENT['device'],
                                    'exclusive':CURRENT['exclusive'],
                                    'local_shared':CURRENT['shared_local'],
                                    'local_url':CURRENT['local_url'],
                                    'diagnostic':{**LAST_DIAG,
                                      'encoding':CURRENT['encoding'] if cast else LAST_DIAG.get('encoding'),
                                      'encoder_speed':CURRENT['encoder_metrics'].get('speed') if cast else LAST_DIAG.get('encoder_speed'),
                                      'manifest_requests':CURRENT['media_hits']['m3u8'] if cast else LAST_DIAG['manifest_requests'],
                                      'segment_requests':CURRENT['media_hits']['ts'] if cast else LAST_DIAG['segment_requests']}})
            else:
                self.reply(400,{'error':'Acción desconocida'})
        except (ValueError,KeyError,RuntimeError,OSError) as exc:
            # Avoid accidental disclosure of provider URL in exception messages.
            msg=str(exc)
            if 'inp' in locals() and inp.get('url'):
                msg=msg.replace(str(inp['url']), '[URL]')
            # Return a readable JSON error to Beta6 UI: urllib drops HTTP 400 response bodies.
            LAST_DIAG.update(status='Error de inicio',detail=msg[:230])
            self.reply(200,{'error':msg[:230]})
        except Exception as exc:
            self.reply(500,{'error':'Cast: '+type(exc).__name__})

if __name__=='__main__':
    import pychromecast  # fail fast when dependency is missing
    TOKEN_FILE.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        fd=os.open(str(TOKEN_FILE),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd,'w',encoding='utf-8') as fh:
            fh.write(secrets.token_urlsafe(40)+'\n')
    TOKEN=TOKEN_FILE.read_text('utf-8').strip()
    if len(TOKEN)<32: raise SystemExit('Falta token seguro de SYN Cast')
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    threading.Thread(target=cast_dvr_guard,daemon=True).start()
    try:server.serve_forever(poll_interval=.3)
    finally:stop_cast();server.server_close()
