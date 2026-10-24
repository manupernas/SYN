"""Automatic Apple appearance for SYN-Mac (no user theme or accent choices)."""
from __future__ import annotations
import subprocess
import sys

# macOS system colour palette from its built-in Accent Color setting.
APPLE = {
    -1: ('#8E8E93','#98989D'),
     0: ('#FF3B30','#FF453A'),
     1: ('#FF9500','#FF9F0A'),
     2: ('#FFCC00','#FFD60A'),
     3: ('#34C759','#30D158'),
     4: ('#007AFF','#0A84FF'),
     5: ('#AF52DE','#BF5AF2'),
     6: ('#FF2D55','#FF375F'),
}

def _default(key):
    if sys.platform != 'darwin':return ''
    try:
        done = subprocess.run(['/usr/bin/defaults','read','-g',key],
                              stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                              text=True,timeout=1.6)
        return done.stdout.strip() if done.returncode==0 else ''
    except (OSError,subprocess.TimeoutExpired):
        return ''

def is_dark():
    return _default('AppleInterfaceStyle').casefold()=='dark'

def accent_id():
    try:return int(_default('AppleAccentColor'))
    except (TypeError, ValueError):return 4  # macOS default in the absence of an explicit accent

def accent_color(dark=None):
    if dark is None:dark=is_dark()
    pair=APPLE.get(accent_id(),APPLE[4])
    return pair[1 if dark else 0]

def signature():
    return (is_dark(), accent_id())
