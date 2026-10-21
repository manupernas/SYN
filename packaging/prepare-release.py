#!/usr/bin/env python3
"""Publish only complete SYN 1.3 releases (4 package formats x 2 architectures)."""
import hashlib
import os
from pathlib import Path
import re
import sys


def required_assets(version):
    return [
        f'syn-iptv-{version}-1.x86_64.rpm',
        f'syn-iptv-{version}-1.aarch64.rpm',
        f'syn-iptv_{version}-1_amd64.deb',
        f'syn-iptv_{version}-1_arm64.deb',
        f'syn-iptv-{version}-1-x86_64.pkg.tar.zst',
        f'syn-iptv-{version}-1-aarch64.pkg.tar.zst',
        f'SYN-{version}-x86_64.flatpak',
        f'SYN-{version}-aarch64.flatpak',
    ]


def prepare(directory: Path, notes_source: Path, notes_destination: Path, tag: str):
    version = tag.removeprefix('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError(f'Invalid release tag: {tag}')
    if not directory.is_dir():
        raise ValueError('Artifact directory does not exist')
    expected = set(required_assets(version))
    found = {p.name for p in directory.iterdir()}
    missing = sorted(expected - found)
    extras = sorted(found - expected)
    if missing or extras:
        raise ValueError(f'Expected exactly 8 assets. Missing: {missing}; unexpected: {extras}')
    files = sorted(directory / name for name in expected)
    for p in files:
        if not p.is_file() or p.stat().st_size <= 1024:
            raise ValueError(f'Empty or invalid asset: {p.name}')
    checksums = []
    for p in files:
        with p.open('rb') as fp:
            digest = hashlib.file_digest(fp, 'sha256').hexdigest()
        checksums.append(f'{digest}  {p.name}')
    (directory / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    source = notes_source.read_text(encoding='utf-8').rstrip()
    english_summary = (
        '\n\n## Build artifacts\n\n'
        'All **eight required packages** passed the GitHub Actions build pipeline: '
        'RPM, DEB, Arch Linux/pacman and Flatpak for both x86_64 and ARM64. '
        'The `SHA256SUMS.txt` file contains SHA-256 hashes for every downloadable package.\n'
    )
    notes_destination.write_text(source + english_summary, encoding='utf-8')
    for p in sorted(directory.iterdir()):
        print(f'{p.name}: {p.stat().st_size} bytes')
    return [p.name for p in files]


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        assets = base / 'assets'
        assets.mkdir()
        names = required_assets('1.3.1')
        for name in names:
            (assets / name).write_bytes(b'package-content' * 80)
        notes = base / 'notes.md'
        notes.write_text('# SYN 1.3\n', encoding='utf-8')
        output = base / 'release.md'
        result = prepare(assets, notes, output, 'v1.3.1')
        assert len(result) == 8
        assert len((assets / 'SHA256SUMS.txt').read_text().splitlines()) == 8
        assert 'SYN 1.3' in output.read_text()
        (assets / names[-1]).unlink()
        try:
            prepare(assets, notes, output, 'v1.3.1')
        except ValueError:
            pass
        else:
            raise AssertionError('A missing Flatpak must block publication')
    print('OK: exactly eight packages, hashes and missing-build guard')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--self-test':
        self_test()
        raise SystemExit(0)
    if len(sys.argv) != 4:
        raise SystemExit('Usage: prepare-release.py ASSETS_DIR ENGLISH_NOTES OUTPUT_BODY')
    try:
        prepare(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), os.environ['SYN_RELEASE_VERSION'])
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
