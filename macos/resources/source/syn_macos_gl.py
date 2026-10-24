"""Resolve OpenGL symbols for GTK4 Quartz + libmpv on macOS.

CFBundleGetFunctionPointerForName is the approach used by the upstream
mpv cocoa-rendergl example.  No EGL, GLX or Linux-only libraries needed.
"""
from __future__ import annotations
import ctypes as C
import threading

_cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
_cf.CFStringCreateWithCString.argtypes = [C.c_void_p, C.c_char_p, C.c_uint32]
_cf.CFStringCreateWithCString.restype = C.c_void_p
_cf.CFBundleGetBundleWithIdentifier.argtypes = [C.c_void_p]
_cf.CFBundleGetBundleWithIdentifier.restype = C.c_void_p
_cf.CFBundleGetFunctionPointerForName.argtypes = [C.c_void_p, C.c_void_p]
_cf.CFBundleGetFunctionPointerForName.restype = C.c_void_p
_cf.CFRelease.argtypes = [C.c_void_p]
_cf.CFRelease.restype = None
_encoding = 0x08000100 # kCFStringEncodingUTF8
_lock = threading.RLock()
_bundle = None

def _make_cf_string(raw: bytes):
    return _cf.CFStringCreateWithCString(None, raw, _encoding)

def gl_proc_address(open_gl_library, name: bytes):
    """Return an integer function pointer or None (as mpv expects)."""
    global _bundle
    if not name:
        return None
    try:
        symbol = getattr(open_gl_library, name.decode('ascii'))
        address = C.cast(symbol, C.c_void_p).value
        if address:
            return address
    except (AttributeError, UnicodeDecodeError):
        pass
    # Match Apple's OpenGL bundle, avoiding symbols from unrelated libs.
    with _lock:
        if _bundle is None:
            ident = _make_cf_string(b'com.apple.opengl')
            if not ident:
                return None
            try:
                _bundle = _cf.CFBundleGetBundleWithIdentifier(ident)
            finally:
                _cf.CFRelease(ident)
        if not _bundle:
            return None
        symbol_name = _make_cf_string(name)
        if not symbol_name:
            return None
        try:
            return _cf.CFBundleGetFunctionPointerForName(_bundle, symbol_name) or None
        finally:
            _cf.CFRelease(symbol_name)
