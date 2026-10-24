"""Cross-platform regression for universal2 otool slice parsing and relinking."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import tempfile
import types

SCRIPT = Path(__file__).resolve().parents[1] / 'macho_relocate.py'
spec = importlib.util.spec_from_file_location('syn_macho', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def check_universal_parser():
    name = '/app/Contents/Resources/python-site/google/_upb/_message.abi3.so'
    output_d = (f'{name} (architecture x86_64):\n'
                'bazel-out/k8-opt-ST-9e73343f3d22/bin/python/lib_message_binary.so\n'
                f'{name} (architecture arm64):\n'
                'bazel-out/k8-opt-ST-d581c5370a66/bin/python/lib_message_binary.so\n')
    output_l = (f'{name} (architecture x86_64):\n'
                '  bazel-out/k8-opt-ST-9e73343f3d22/bin/python/lib_message_binary.so '
                '(compatibility version 0.0.0, current version 0.0.0)\n'
                '  /usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n'
                f'{name} (architecture arm64):\n'
                '  bazel-out/k8-opt-ST-d581c5370a66/bin/python/lib_message_binary.so '
                '(compatibility version 0.0.0, current version 0.0.0)\n'
                '  /usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n')

    def fake_subproc(cmd, **kwargs):
        assert cmd[-1] == name, cmd
        return types.SimpleNamespace(returncode=0, stdout=output_d if cmd[1] == '-D' else output_l)

    with patch.object(m.subprocess, 'run', fake_subproc):
        ids=m.macho_ids(Path(name))
        assert ids == {
            'bazel-out/k8-opt-ST-9e73343f3d22/bin/python/lib_message_binary.so',
            'bazel-out/k8-opt-ST-d581c5370a66/bin/python/lib_message_binary.so'
        }, ids
        with patch.object(m, 'run', lambda *args: output_l):
            ds=m.deps(Path(name))
        assert len(ds)==3 and '/usr/lib/libSystem.B.dylib' in ds, ds
        assert all('(architecture' not in d for d in ds), ds


def check_end_to_end_relink():
    with tempfile.TemporaryDirectory() as tmp:
        app=Path(tmp)/'SYN.app'
        fat=app/'Contents/Resources/python-site/google/_upb/_message.abi3.so'
        py=app/'Contents/Frameworks/Python.framework/Versions/3.15/Python'
        svg=app/'Contents/Resources/lib/loaders/libpixbufloader_svg.so'
        for p in (fat,py,svg):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'\xcf\xfa\xed\xfe'+b'0'*256)
        original={
            str(fat):{'bazel-out/k8-opt-ST-9e73343f3d22/bin/python/lib_message_binary.so',
                     'bazel-out/k8-opt-ST-d581c5370a66/bin/python/lib_message_binary.so'},
            str(py):{'/opt/homebrew/opt/python@3.15/Frameworks/Python.framework/Versions/3.15/Python'},
            str(svg):{'/opt/homebrew/opt/librsvg/lib/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader_svg.dylib'},
        }
        deps={str(p):set(original[str(p)])|{'/usr/lib/libSystem.B.dylib'} for p in (fat,py,svg)}
        operations=[]
        def fake_run(*cmd):
            operations.append(cmd)
            if cmd[1]=='-id':
                key=cmd[-1]
                original[key]={cmd[2]}
                deps[key]={cmd[2]} | {'/usr/lib/libSystem.B.dylib'}
            return ''
        with patch.object(m.Bundler,'seed',lambda self:None),\
             patch.object(m.Bundler,'all_binaries',lambda self:[fat,py,svg]),\
             patch.object(m,'macho_ids',lambda path: original[str(path)]),\
             patch.object(m,'deps',lambda path: sorted(deps[str(path)])),\
             patch.object(m,'run',fake_run),\
             patch.object(m.Bundler,'find_homebrew',lambda self, dep, o: None):
            m.Bundler(app).bundle()
        assert all(len(v)==1 and next(iter(v)).startswith('@rpath/') for v in original.values())
        assert len(operations)==3 and all(cmd[1]=='-id' for cmd in operations), operations


if __name__=='__main__':
    check_universal_parser()
    check_end_to_end_relink()
    print('PASS: multiarch Mach-O ids, headers and in-place install names')
