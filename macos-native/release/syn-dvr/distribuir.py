#!/usr/bin/env python3
"""SYN DVR production distribution builder. Run on macOS, not on users' Macs.

Explicitly imports dependency closure logic from syn_dvr_bundling.py and builds a
self-contained ZIP of SYN DVR.app. Default web build is ad-hoc signed, unnotarized; NOT published automatically.
The installed original app and the user's DVR engine are never modified.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import datetime
import hashlib
import platform
import syn_dvr_bundling as deps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
APP_DEFAULT = None  # Compilar SIEMPRE desde el proyecto integrado; no usar la app instalada.
ICON = ROOT/'SYNDVRMenu/Resources/SYNDVR.icns'
REQUIRED = ('comskip','ffmpeg','ffprobe')
APP_ID = 'com.mrseivane.SYNDVRMenu'


def run(cmd, **kwargs):
    return subprocess.run([str(a) for a in cmd], check=True, **kwargs)


def inspect_binary(bin_path: Path):
    p = subprocess.run(['/usr/bin/lipo','-archs',str(bin_path)],capture_output=True,text=True)
    if p.returncode != 0:
        raise RuntimeError(f'No se puede determinar la arquitectura de {bin_path.name}: {p.stderr.strip()}')
    return set(p.stdout.split())


def get_developer_id(identity: str) -> None:
    p = subprocess.run(['/usr/bin/security','find-identity','-v','-p','codesigning'],capture_output=True,text=True)
    if p.returncode != 0 or not any('Developer ID Application:' in line and identity in line for line in p.stdout.splitlines()):
        raise RuntimeError('No se encontró una identidad Developer ID Application que coincida con --identity. ' +
                           'Apple Development NO sirve para una descarga pública sin avisos.')


def check_external_paths(stage: Path, bundled: list[Path]):
    root = stage/'Contents/MacOS'
    for path in bundled:
        refs = deps.mac_deps(path)
        if path.suffix == '.dylib' and refs: refs = refs[1:]
        for ref in refs:
            if deps.system_dep(ref): continue
            if ref.startswith('@loader_path/') and (root / ref.removeprefix('@loader_path/')).is_file():
                continue
            raise RuntimeError('Biblioteca de fuera de la app: ' + path.name + ' -> ' + ref)
    # Reject absolute build-machine paths, for dynamically linked tools.
    # This validation is not a substitute for a real clean-Mac test.


def sign(stage: Path, binaries: list[Path], identity: str, test: bool):
    for path in sorted(binaries,key=lambda p: (p.suffix!='.dylib', p.name)):
        args=['/usr/bin/codesign','--force','--sign', '-' if test else identity]
        if not test: args += ['--options','runtime','--timestamp']
        run(args+[str(path)])
    args=['/usr/bin/codesign','--force','--deep','--sign','-' if test else identity]
    if not test: args+=['--options','runtime','--timestamp']
    run(args+[str(stage)])
    run(['/usr/bin/codesign','--verify','--deep','--strict','--verbose=2',str(stage)])


def selftest(stage: Path):
    bindir = stage/'Contents/MacOS'
    for name in ('ffmpeg','ffprobe'):
        proc = subprocess.run([str(bindir/name),'-version'],capture_output=True,text=True,timeout=30)
        if proc.returncode or not proc.stdout.lower().startswith(name+' version'):
            raise RuntimeError(f'{name} no funciona desde el paquete: {proc.stderr[-600:]}')
    p = subprocess.run([str(bindir/'comskip'),'--help'],capture_output=True,text=True,timeout=25)
    if p.returncode < 0 or 'library not loaded' in p.stderr.lower() or 'dyld:' in p.stderr.lower():
        raise RuntimeError('Comskip sigue dependiendo de una biblioteca externa: '+p.stderr[-600:])
    p=subprocess.run([str(bindir/'syn-dvr-ads')],capture_output=True,text=True,timeout=20)
    if p.returncode != 2 or 'Argumentos incorrectos' not in p.stdout:
        raise RuntimeError('El ejecutable nativo de anuncios no arranca: '+p.stderr[-500:])


def main():
    parser=argparse.ArgumentParser(description='Genera SYN DVR auto-contenido, sin instaladores para el usuario final')
    parser.add_argument('--app',type=Path,default=APP_DEFAULT,help='Solo para diagnóstico; debe estar compilada con SYNBundledRuntime446')
    parser.add_argument('--output',type=Path,default=Path.home()/'Downloads',help='Directorio destino')
    parser.add_argument('--identity',default=os.environ.get('SYN_DEVELOPER_ID',''),help='Developer ID Application: ...')
    parser.add_argument('--notary-profile',default=os.environ.get('SYN_NOTARY_PROFILE',''),help='Perfil de notarytool creado en el llavero')
    parser.add_argument('--development',action='store_true',help='Generar ZIP interno de pruebas (ad hoc, no notarizado)')
    args=parser.parse_args()
    if sys.platform != 'darwin': raise RuntimeError('Este proceso debe ejecutarse en macOS.')
    if args.app is not None:
        raise RuntimeError('Por seguridad, esta versión construye SYN DVR desde el código fuente integrado. No acepta --app de una versión antigua.')
    if not ICON.is_file() or ICON.stat().st_size < 1024:
        raise RuntimeError('Falta el icono oficial en SYNDVRMenu/Resources/SYNDVR.icns')
    if not (HERE/'syn-dvr-ads.swift').is_file():
        raise RuntimeError('Falta el procesador nativo syn-dvr-ads.swift')
    # Publicación web sin Developer ID: admisible como descarga, pero macOS
    # bloqueará la primera apertura hasta que la persona la autorice manualmente.
    # El modo Developer ID/notarización sigue disponible si se obtiene en el futuro.
    if args.development and (args.identity or args.notary_profile):
        raise RuntimeError('--development no puede combinarse con --identity o --notary-profile.')
    if bool(args.identity) != bool(args.notary_profile):
        raise RuntimeError('Para notarizar debes indicar tanto --identity como --notary-profile; ' +
                           'sin ambos se genera una descarga web firmada ad hoc.')
    developer_signed = bool(args.identity and args.notary_profile)
    if developer_signed:
        get_developer_id(args.identity)
    else:
        print('ℹ️ Modo web sin Developer ID: firma ad hoc, NO notarizada; ' +
              'el usuario deberá autorizar manualmente la primera apertura en macOS.')
    if 'DEVELOPER_DIR' not in os.environ and Path('/Volumes/T7/Xcode.app/Contents/Developer').is_dir():
        os.environ['DEVELOPER_DIR']='/Volumes/T7/Xcode.app/Contents/Developer'
    if not shutil.which('xcrun'): raise RuntimeError('Falta Xcode completo en el Mac de compilación.')
    if not shutil.which('xcodegen'):
        raise RuntimeError('Falta XcodeGen en el Mac CONSTRUCTOR. No será necesario para quien descargue SYN DVR.')
    source_root = ROOT / 'release/syn-dvr/runtime-src'
    runtime_sources = [source_root/name for name in ('standalone_supervisor.py','syn_dvr_remote.py')]
    runtime_sources += [ROOT/'.syn-pool31-engine/hls_server.py']
    for script in runtime_sources:
        if not script.is_file():
            raise RuntimeError('Falta el componente del motor: ' + str(script) + '. No se puede generar una distribución plug and play.')
    if not (ROOT/'SYNDVRMenu/SYNBundledRuntime446.swift').is_file():
        raise RuntimeError('Falta el runtime Swift integrado. No se puede compilar la edición autónoma.')
    py = Path(shutil.which('python3') or '')
    if not py.is_file():
        raise RuntimeError('Se requiere Python en el Mac de CONSTRUCCIÓN para empaquetar el runtime. El usuario NO lo necesita.')
    test_pyinstaller = subprocess.run([str(py),'-c','import PyInstaller'],capture_output=True,text=True)
    if test_pyinstaller.returncode:
        raise RuntimeError('El Mac CONSTRUCTOR necesita PyInstaller para incrustar Python. ' +
                           'Instálalo en un entorno virtual de compilación; no es un requisito del usuario.')
    src={}
    for name in REQUIRED:
        p=shutil.which(name)
        if not p: raise RuntimeError('Al equipo de CONSTRUCCIÓN le falta '+name+' (el usuario final nunca lo necesitará).')
        src[name]=Path(p).resolve()
        if not str(src[name]).startswith(('/opt/homebrew/','/usr/local/')):
            raise RuntimeError('Origen de binario no reconocido: '+str(src[name]))
    app_arch={platform.machine()}
    for name,p in src.items():
        arch=inspect_binary(p)
        if not app_arch.issubset(arch):
            raise RuntimeError(name+' no contiene todas las arquitecturas de SYN DVR: '+str(app_arch)+' vs '+str(arch)+
                               '. Para publicar Intel y Apple Silicon, genera y prueba dos paquetes o usa binarios universales reales.')
    args.output.mkdir(parents=True,exist_ok=True)
    label=('PRUEBAS-NO-PUBLICAR' if args.development else
           ('WEB-SIN-NOTARIZAR' if not developer_signed else 'PUBLICACION-FIRMADA'))
    arches='-'.join(sorted(app_arch))
    output=args.output/f'SYN-DVR-4.4.6-{arches}-{label}.zip'
    if output.exists(): raise RuntimeError('Ya existe un archivo de salida: '+str(output)+'; no lo sobreescribo.')
    with tempfile.TemporaryDirectory(prefix='syn-dvr-release-') as temp:
        temp=Path(temp)
        # Compilar siempre el producto actual, que incluye SYNBundledRuntime446.
        # NO se modifica /Applications ni se reutiliza una app anterior al parche.
        run(['xcodegen','generate','--spec',str(ROOT/'project.yml'),'--project',str(ROOT)])
        derived=temp/'DerivedData'
        run(['xcodebuild','-project',str(ROOT/'SYNNative.xcodeproj'),'-scheme','SYNDVRMenu',
             '-configuration','Release','-derivedDataPath',str(derived),
             'CODE_SIGNING_ALLOWED=NO','build'])
        built=derived/'Build/Products/Release/SYN DVR.app'
        if deps.app_id(built)!=APP_ID:
            raise RuntimeError('Xcode no ha producido una SYN DVR.app con el identificador esperado.')
        real_app_arch=inspect_binary(deps.app_executable(built))
        if real_app_arch != app_arch:
            raise RuntimeError('Arquitecturas inesperadas al compilar SYN DVR: '+str(real_app_arch)+' vs '+str(app_arch))
        stage=temp/'SYN DVR.app'
        run(['/usr/bin/ditto',str(built),str(stage)])
        shutil.copy2(ICON,stage/'Contents/Resources/SYNDVR.icns')
        bundled=deps.bundle_libraries(stage,src)
        helper=stage/'Contents/MacOS/syn-dvr-ads'
        run(['xcrun','swiftc','-O',str(HERE/'syn-dvr-ads.swift'),'-o',str(helper)])
        bundled.append(helper)
        # Incorporar la versión de código fuente del motor del mismo repositorio.
        engine=ROOT/'.syn-pool31-engine'
        run(['xcrun','swift','build','--package-path',str(engine),'-c','release'])
        engine_bin=Path(subprocess.check_output(
            ['xcrun','swift','build','--package-path',str(engine),'-c','release','--show-bin-path'],
            text=True).strip())/'syn-dvr-engine'
        worker=stage/'Contents/MacOS/syn-dvr-worker'
        shutil.copy2(engine_bin,worker)
        worker.chmod(worker.stat().st_mode | 0o111)
        bundled.append(worker)
        # Scripts del supervisor y servidor remoto: fuentes INCLUIDAS en GitHub.
        runtime=stage/'Contents/Resources/SYN-DVR-Runtime'
        runtime.mkdir(parents=True,exist_ok=False)
        for original in runtime_sources:
            shutil.copy2(original,runtime/original.name)
        # PyInstaller incluye Python y dependencias; nunca se invoca Python del usuario.
        # Sus imports dinámicos se declaran explícitamente usando AST de los scripts.
        import ast
        imports=set()
        for original in runtime_sources:
            try:
                tree=ast.parse(original.read_text(encoding='utf-8'))
            except (SyntaxError,UnicodeDecodeError) as error:
                raise RuntimeError(f'No puedo empaquetar {original.name}: {error}') from error
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    imports.update(n.name for n in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module and node.level==0:
                    imports.add(node.module)
        dist=temp/'Frozen';work=temp/'PyInstallerWork';spec=temp/'PyInstallerSpec'
        command=[str(py),'-m','PyInstaller','--onefile','--clean','--noconfirm',
                 '--name','syn-dvr-python','--distpath',str(dist),
                 '--workpath',str(work),'--specpath',str(spec)]
        for name in sorted(imports):
            if not name.startswith('_'):
                command.extend(['--hidden-import',name])
        command.append(str(HERE/'py_runtime_entry.py'))
        run(command)
        frozen=stage/'Contents/MacOS/syn-dvr-python'
        shutil.copy2(dist/'syn-dvr-python',frozen)
        frozen.chmod(frozen.stat().st_mode | 0o111)
        bundled.append(frozen)
        # El motor y el supervisor no pueden depender de la instalación Homebrew del usuario.
        for item in ('syn-dvr-python','syn-dvr-worker'):
            if not (stage/'Contents/MacOS'/item).is_file():
                raise RuntimeError('Falta componente obligatorio: '+item)
        probe=subprocess.run([str(frozen),'--self-test'],capture_output=True,text=True,timeout=40)
        if probe.returncode or 'SYN_PYTHON_RUNTIME_OK' not in probe.stdout:
            raise RuntimeError('El Python incrustado no supera la prueba de ejecución: '+probe.stderr[-400:])
        print('✅ Motor Swift, Python incrustado, supervisor, HLS y servidor remoto incorporados.')
        for binary in bundled:
            if not app_arch.issubset(inspect_binary(binary)):
                raise RuntimeError('Arquitectura faltante en '+binary.name+'; no publicaré un paquete incompleto.')
        check_external_paths(stage,bundled)
        selftest(stage)
        # Verificación de motor y scripts antes de firmar el paquete.
        probe=subprocess.run([str(stage/'Contents/MacOS/syn-dvr-python'),'--self-test'],
                             capture_output=True,text=True,timeout=40)
        if probe.returncode or 'SYN_PYTHON_RUNTIME_OK' not in probe.stdout:
            raise RuntimeError('Python incrustado no arranca desde el paquete.')
        version=''
        with (stage/'Contents/Info.plist').open('rb') as f:
            version=str(plistlib.load(f).get('CFBundleShortVersionString',''))
        manifest={
            'package':'SYN DVR', 'version':version, 'architectures':sorted(app_arch),
            'tools':{'comskip':str(src['comskip']),'ffmpeg':str(src['ffmpeg']),'ffprobe':str(src['ffprobe'])},
            'runtime':['syn-dvr-worker','syn-dvr-python','standalone_supervisor.py',
                       'syn_dvr_remote.py','hls_server.py'],
            'icon_sha256':hashlib.sha256(ICON.read_bytes()).hexdigest(),
            'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'distribution': ('developer_id_notarized' if developer_signed else 'ad_hoc_unnotarized'),
            'notes':'Las rutas de origen de Homebrew son información del equipo creador; no son dependencias de ejecución.'
        }
        support=stage/'Contents/Resources/SYN-DVR-ThirdParty'
        support.mkdir(parents=True,exist_ok=True)
        (support/'BINARIES-AND-SOURCES.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
        (support/'THIRD-PARTY-NOTICE.txt').write_text(
            'Comskip (GPL-2.0): https://github.com/erikkaashoek/Comskip\n'
            'FFmpeg (LGPL/GPL según configuración): https://ffmpeg.org/legal.html\n'
            'Antes de publicar: revisa licencias de TODAS las librerías empaquetadas y facilita las fuentes correspondientes.\n')
        sign(stage,bundled,args.identity,not developer_signed)
        selftest(stage)
        run(['/usr/bin/ditto','-c','-k','--keepParent',str(stage),str(output)])
        if developer_signed:
            run(['xcrun','notarytool','submit',str(output),'--keychain-profile',args.notary_profile,'--wait'])
            run(['xcrun','stapler','staple',str(stage)])
            # rebuild notarized + stapled app zip
            output.unlink()
            run(['/usr/bin/ditto','-c','-k','--keepParent',str(stage),str(output)])
            run(['xcrun','stapler','validate',str(stage)])
            run(['/usr/sbin/spctl','-a','-vv','-t','exec',str(stage)])
        # Instruciones también DENTRO de la descarga, sin ejecutables extra.
        # No suprimir Gatekeeper ni pedir desactivar la protección global del Mac.
        import zipfile
        with zipfile.ZipFile(output, 'a', compression=zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr('LEEME-PRIMERA-APERTURA.txt',
                'SYN DVR para macOS — descarga oficial desde la web\n\n'
                'Esta aplicación incluye Comskip, FFmpeg, FFprobe y el procesador de anuncios.\n'
                'No hace falta instalar Homebrew, Python ni herramientas externas.\n\n'
                + ('Aplicación firmada con Developer ID y notarizada por Apple.\n' if developer_signed else
                   'IMPORTANTE: aplicación firmada ad hoc, SIN notarización de Apple.\n'
                   'macOS mostrará una advertencia al abrirla por primera vez.\n'
                   'Tras intentar abrirla, entra en Ajustes del Sistema > Privacidad y seguridad >\n'
                   'Abrir igualmente y confirma. Hazlo solo si la has descargado de una fuente\n'
                   'en la que confías y has verificado su origen. Este permiso es por app.\n'
                   'No es necesario desactivar Gatekeeper.\n')
                + '\nConsulta https://support.apple.com/es-es/102445 para más información.\n')
        # Validate contents of actual ZIP (not only staged build)
        with zipfile.ZipFile(output) as zipped:
            names=set(zipped.namelist())
            expected={f'SYN DVR.app/Contents/MacOS/{name}' for name in (*REQUIRED,'syn-dvr-ads','syn-dvr-worker','syn-dvr-python')}
            expected.update(f'SYN DVR.app/Contents/Resources/SYN-DVR-Runtime/{name}' for name in
                            ('standalone_supervisor.py','syn_dvr_remote.py','hls_server.py'))
            expected.add('SYN DVR.app/Contents/Resources/SYNDVR.icns')
            missing=expected - names
            if missing: raise RuntimeError('Archivo incompleto: '+', '.join(sorted(missing)))
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        checksum=Path(str(output)+'.sha256')
        checksum.write_text(f'{digest}  {output.name}\n', encoding='utf-8')
        print('\n✅ ZIP COMPLETO generado: '+str(output))
        print('✅ SHA-256: '+digest)
        print('✅ Archivo de comprobación: '+str(checksum))
        if args.development:
            print('⚠️ Paquete de pruebas internas, no usar para la publicación.')
        elif developer_signed:
            print('✅ Firma Developer ID y notarización realizadas.')
        else:
            print('⚠️ Descarga web SIN notarización: el usuario deberá usar Abrir igualmente en Privacidad y seguridad.')
            print('⚠️ Una firma ad hoc NO equivale a una firma Developer ID.')
        print('✅ El ZIP incluye motor, supervisor, servidor HLS/remoto, Python incrustado y Comskip/FFmpeg.')
        print('⚠️ Pendiente: prueba funcional de grabación y servidor remoto en macOS limpio antes de publicar.')
        print('⚠️ Antes de publicar, revisa licencias, fuentes GPL/LGPL y compatibilidad en un Mac limpio.')


if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,subprocess.SubprocessError,TimeoutError) as exc:
        print('\n❌ '+str(exc),file=sys.stderr)
        sys.exit(1)
