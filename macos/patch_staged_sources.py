#!/usr/bin/env python3
"""Patch only temporary staged application sources for relocatable runtime.

Never writes in /Applications or the existing checkout source snapshot.
Use exact anchors: unexpected source revisions must fail rather than silently
produce a misleading or incomplete standalone DMG.
"""
from __future__ import annotations
from pathlib import Path
import sys


def replace_once(p: Path, old: str, new: str):
    s = p.read_text('utf-8')
    if s.count(old) != 1:
        raise RuntimeError(f'{p}: expected exactly one occurrence, got {s.count(old)}: {old[:70]!r}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')


def main():
    root = Path(sys.argv[1])
    res = root / 'Contents/Resources'
    alpha = res / 'macos_alpha.py'
    cast = res / 'source/syn_mac_cast_launcher.py'
    syn = res / 'source/syn.py'
    worker = res / 'mac_dvr_worker.py'
    support = res / 'syn_macos_dvr_support.py'

    replace_once(alpha,
        '    import gi, cairo\n',
        "    if os.environ.get('SYN_STANDALONE') == '1':\n"
        '        from syn_macos_bootstrap import prepare_runtime\n'
        '        prepare_runtime()\n'
        '    import gi, cairo\n')
    replace_once(alpha,
        "    os.environ['PATH'] = '/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin'",
        "    os.environ['PATH'] = os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')")
    replace_once(alpha,
        '    candidates = (\n',
        "    candidates = (\n        os.environ.get('SYN_BUNDLED_LIBMPV', ''),\n")
    replace_once(alpha,
        '    syn_mac_cast_launcher.ensure_running(source)\n',
        "    syn_mac_cast_launcher.ensure_running(source)\n"
        "    if os.environ.get('SYN_STANDALONE') == '1':\n"
        '        import threading\n'
        '        from syn_macos_bootstrap import ensure_dvr_agent\n'
        '        threading.Thread(target=ensure_dvr_agent, daemon=True).start()\n')

    replace_once(worker,
        "    os.environ['PATH'] = '/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin'",
        "    os.environ['PATH'] = os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')")
    replace_once(worker,
        "    ffmpeg = Path('/opt/homebrew/bin/ffmpeg')",
        "    ffmpeg = Path(os.environ.get('SYN_FFMPEG_BIN', '/opt/homebrew/bin/ffmpeg'))")

    replace_once(cast,
        "    interpreter=PRIVATE / 'cast-venv' / 'bin' / 'python'\n"
        "    host=source / 'syn_cast_host.py'\n"
        "    if not interpreter.is_file() or not host.is_file():",
        "    packaged = os.environ.get('SYN_STANDALONE') == '1'\n"
        "    interpreter = (Path(os.environ.get('SYN_BUNDLED_PYTHON', '')) / 'SYN'\n"
        "                   if packaged else PRIVATE / 'cast-venv' / 'bin' / 'python')\n"
        "    host=source / 'syn_cast_host.py'\n"
        "    if not interpreter.is_file() or not host.is_file():")
    replace_once(cast,
        "    env['PATH']='/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'",
        "    env['PATH']=os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')")
    replace_once(cast,
        "    subprocess.Popen([str(interpreter),str(host)],stdin=subprocess.DEVNULL,",
        "    command = ([str(interpreter), '--syn-cast-host'] if packaged\n"
        "               else [str(interpreter),str(host)])\n"
        "    subprocess.Popen(command,stdin=subprocess.DEVNULL,")

    replace_once(syn,
        "            native = (Path.home() / 'Library' / 'Application Support' /\n"
        "                      'SYN-Mac' / 'Notifications' / 'SYN Notifications.app')",
        "            native = (Path(__file__).resolve().parents[2] / 'Helpers' /\n"
        "                      'SYN Notifications.app' if os.environ.get('SYN_STANDALONE') == '1'\n"
        "                      else Path.home() / 'Library' / 'Application Support' /\n"
        "                      'SYN-Mac' / 'Notifications' / 'SYN Notifications.app')")
    replace_once(syn,
        "            binary=(Path.home()/'Library'/'Application Support'/'SYN-Mac'/'AirPlay'/\n"
        "                    'SYN AirPlay.app'/'Contents'/'MacOS'/'SYNAirPlay')",
        "            binary=((Path(__file__).resolve().parents[2] / 'Helpers' /\n"
        "                     'SYN AirPlay.app' / 'Contents' / 'MacOS' / 'SYNAirPlay')\n"
        "                    if os.environ.get('SYN_STANDALONE') == '1'\n"
        "                    else Path.home()/'Library'/'Application Support'/'SYN-Mac'/'AirPlay'/\n"
        "                    'SYN AirPlay.app'/'Contents'/'MacOS'/'SYNAirPlay')")

    # GUI and DVR worker both use this, so update centrally.
    replace_once(support,
        "    binary = shutil.which('osascript')",
        "    native = (Path(__file__).resolve().parent.parent / 'Helpers' /\n"
        "              'SYN Notifications.app')\n"
        "    if native.is_dir():\n"
        "        try:\n"
        "            done = subprocess.run(['/usr/bin/open', '-g', '-n', '-a', str(native),\n"
        "                                  '--args', 'SYN DVR', str(message)[:550]],\n"
        "                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n"
        "                                  stderr=subprocess.DEVNULL, timeout=4)\n"
        "            if done.returncode == 0: return True\n"
        "        except (OSError, subprocess.TimeoutExpired):\n"
        "            pass\n"
        "    binary = shutil.which('osascript')")
    print('STANDALONE_SOURCE_PATCH_OK')


if __name__ == '__main__':
    main()
