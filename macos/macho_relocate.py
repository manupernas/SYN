#!/usr/bin/env python3
"""Bundle and rewrite Homebrew Mach-O references within a macOS .app.

Runs only on macOS via otool/install_name_tool. Never mutates installed Homebrew
files; changes are made exclusively inside the temporary app staging folder.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

MAGIC = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
         b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
         b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}
BREW = Path('/opt/homebrew')


def run(*cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=True).stdout


def macho(path):
    if path.is_symlink() or not path.is_file():
        return False
    try:
        with path.open('rb') as f:
            return f.read(4) in MAGIC
    except OSError:
        return False


def deps(path):
    out = run('/usr/bin/otool', '-L', str(path)).splitlines()
    return [line.strip().split(' (compatibility version', 1)[0]
            .split(' (current version', 1)[0]
            for line in out[1:] if line.strip()]


def reloc_name(target, source):
    relative = os.path.relpath(target, source.parent)
    return '@loader_path/' + relative.replace(os.sep, '/')


class Bundler:
    def __init__(self, app: Path):
        self.app = app.resolve()
        self.fw = self.app / 'Contents/Frameworks'
        self.fw.mkdir(parents=True, exist_ok=True)
        self.orig = {}
        self.count = 0
        self.rewrites = 0

    def find_homebrew(self, dep, original):
        if dep.startswith('/opt/homebrew/'):
            candidate = Path(dep)
            if candidate.is_file():
                return candidate
            # A Homebrew formula might embed a versioned Cellar path removed in runner.
            candidate = BREW / 'lib' / Path(dep).name
            return candidate if candidate.is_file() else None
        if dep.startswith('@loader_path/') and original is not None:
            candidate = (original.parent / dep.split('/', 1)[1]).resolve()
            if candidate.is_file() and str(candidate).startswith(str(BREW) + '/'):
                return candidate
        if dep.startswith('@rpath/') or dep.startswith('@executable_path/'):
            name = Path(dep).name
            candidate = BREW / 'lib' / name
            if candidate.is_file():
                return candidate
        return None

    def import_lib(self, src):
        dst = self.fw / src.name
        if dst.exists():
            if dst not in self.orig:
                # A staged file of the same name is never silently overwritten.
                raise RuntimeError('Biblioteca duplicada en Frameworks: ' + str(dst))
            if src.resolve() != self.orig[dst].resolve():
                raise RuntimeError('Colisión de bibliotecas con mismo nombre: ' + str(src))
            return dst
        shutil.copy2(src, dst, follow_symlinks=True)
        dst.chmod(dst.stat().st_mode | 0o200)
        self.orig[dst] = src.resolve()
        self.count += 1
        return dst

    def seed(self):
        patterns = ('libglib-2.0.0.dylib', 'libgobject-2.0.0.dylib',
                    'libgio-2.0.0.dylib', 'libgmodule-2.0.0.dylib',
                    'libgirepository-*.dylib', 'libgtk-4*.dylib',
                    'libadwaita-1*.dylib', 'libmpv.dylib',
                    'libgdk_pixbuf-2.0*.dylib', 'libpango-1.0*.dylib')
        for pattern in patterns:
            files = sorted((BREW / 'lib').glob(pattern))
            if not files and pattern in ('libglib-2.0.0.dylib', 'libgobject-2.0.0.dylib',
                                         'libgio-2.0.0.dylib', 'libmpv.dylib'):
                raise RuntimeError('Biblioteca esencial no disponible: ' + pattern)
            for src in files:
                if src.is_file():
                    self.import_lib(src)

    def all_binaries(self):
        return [p for p in self.app.rglob('*') if macho(p)]

    def bundle(self):
        self.seed()
        # Closure over all compile-time dependencies, including .so extensions,
        # Python.framework, libmpv, FFmpeg, Swift helpers and GdkPixbuf loaders.
        for _ in range(30):
            before = self.count
            for dest in self.all_binaries():
                original = self.orig.get(dest)
                for dep in deps(dest):
                    if 'Python.framework/' in dep and ('/opt/homebrew/' in dep or dep.startswith('@rpath/')):
                        continue  # Copied as a full framework; handled below.
                    resolved = self.find_homebrew(dep, original)
                    if resolved is not None:
                        self.import_lib(resolved)
            if self.count == before:
                break
        else:
            raise RuntimeError('Mach-O graph did not converge in 30 rounds')

        python_fw = self.fw / 'Python.framework/Versions/3.15/Python'
        if not python_fw.is_file():
            raise RuntimeError('Framework Python 3.15 no incluido')

        for dest in self.all_binaries():
            original = self.orig.get(dest)
            for dep in deps(dest):
                target = None
                if 'Python.framework/' in dep and (dep.startswith('/opt/homebrew/') or dep.startswith('@rpath/')):
                    target = python_fw
                else:
                    resolved = self.find_homebrew(dep, original)
                    if resolved is not None:
                        target = self.fw / resolved.name
                if target is None:
                    if dep.startswith('/opt/homebrew/'):
                        raise RuntimeError(f'Unbundled Homebrew dylib in {dest}: {dep}')
                    continue
                if not target.is_file():
                    raise RuntimeError(f'Library missing from bundle: {target}')
                new = reloc_name(target, dest)
                if dep != new:
                    dest.chmod(dest.stat().st_mode | 0o200)
                    run('/usr/bin/install_name_tool', '-change', dep, new, str(dest))
                    self.rewrites += 1
            if dest.parent == self.fw and dest.suffix == '.dylib':
                run('/usr/bin/install_name_tool', '-id', '@rpath/' + dest.name, str(dest))
        # Python.framework has an LC_ID_DYLIB of its own. Unlike a linked
        # dependency (LC_LOAD_DYLIB), this ID cannot be changed with -change.
        # Homebrew sets it to /opt/homebrew/... and the final scan correctly
        # rejects it unless we rewrite it explicitly with -id.
        python_ids = deps(python_fw)
        if not python_ids:
            raise RuntimeError('Missing Python.framework install name')
        portable_id = '@rpath/Python.framework/Versions/3.15/Python'
        if python_ids[0].startswith('/opt/homebrew/'):
            python_fw.chmod(python_fw.stat().st_mode | 0o200)
            run('/usr/bin/install_name_tool', '-id', portable_id, str(python_fw))
            self.rewrites += 1
        elif python_ids[0] != portable_id:
            raise RuntimeError('Unexpected Python.framework install name: ' + python_ids[0])

        for dest in self.all_binaries():
            for dep in deps(dest):
                if dep.startswith('/opt/homebrew/'):
                    raise RuntimeError(f'Homebrew reference remains in {dest}: {dep}')
        print(f'BUNDLED_MACHO_OK libraries={self.count} rewrites={self.rewrites}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('app', type=Path)
    args = ap.parse_args()
    if sys.platform != 'darwin' or not (args.app / 'Contents/Info.plist').is_file():
        raise SystemExit('Requires a staged macOS .app')
    Bundler(args.app).bundle()


if __name__ == '__main__':
    main()
