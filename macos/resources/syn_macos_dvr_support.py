"""Shared macOS DVR helpers, deliberately independent of GTK and Python GI."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path


def video_directory():
    """Default recording folder. User-selected paths persist in dvr.json."""
    return Path.home() / 'Movies' / 'SYN'


def notify_transient(message):
    # AppleScript receives the text as a literal, never as executable code.
    # Notification permission is optional and must not affect a recording.
    binary = shutil.which('osascript')
    if not binary:
        return False
    script = 'on run argv\n display notification (item 1 of argv) with title "SYN DVR"\nend run'
    try:
        subprocess.Popen([binary, '-e', script, str(message)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False
