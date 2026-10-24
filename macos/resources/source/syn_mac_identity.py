"""Set SYN as the native process name before creating GTK's NSApplication.

Native AppKit normally derives its menu title from the application bundle.
The older Python-based launcher exposed the interpreter instead. This sets
NSProcessInfo.processName, with Info.plist as another source of the app name.
"""
from __future__ import annotations
import ctypes
import sys


def set_process_name(name='SYN'):
    if sys.platform != 'darwin': return False
    try:
        ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
        objc=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        get_class=objc.objc_getClass
        get_class.argtypes=[ctypes.c_char_p]
        get_class.restype=ctypes.c_void_p
        sel=objc.sel_registerName
        sel.argtypes=[ctypes.c_char_p]
        sel.restype=ctypes.c_void_p
        call0=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
        call1=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
        nsstring=get_class(b'NSString')
        process_info=get_class(b'NSProcessInfo')
        if not nsstring or not process_info: return False
        title=ctypes.create_string_buffer(name.encode('utf-8'))
        ns_title=call1(nsstring,sel(b'stringWithUTF8String:'),ctypes.cast(title,ctypes.c_void_p))
        instance=call0(process_info,sel(b'processInfo'))
        if not ns_title or not instance: return False
        call1(instance,sel(b'setProcessName:'),ns_title)
        return True
    except Exception:
        return False


def fix_menu_bar_name(name='SYN'):
    """Rename only the application's native macOS *displayed* menu title.

    This is called on the GTK/AppKit main thread *after* GTK has created its
    NSMenu. Earlier setProcessName() alone was insufficient for GTK4.
    """
    if sys.platform != 'darwin':
        return False
    import ctypes as C
    objc = C.CDLL('/usr/lib/libobjc.A.dylib')
    C.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
    objc.objc_getClass.argtypes=[C.c_char_p]
    objc.objc_getClass.restype=C.c_void_p
    objc.sel_registerName.argtypes=[C.c_char_p]
    objc.sel_registerName.restype=C.c_void_p
    def sel(n): return objc.sel_registerName(n.encode('utf-8'))
    send0=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p)(('objc_msgSend',objc))
    send_obj=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)(('objc_msgSend',objc))
    send_idx=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p,C.c_long)(('objc_msgSend',objc))
    send_set=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_void_p)(('objc_msgSend',objc))
    send_chars=C.CFUNCTYPE(C.c_char_p,C.c_void_p,C.c_void_p)(('objc_msgSend',objc))
    app_class=objc.objc_getClass(b'NSApplication')
    ns_class=objc.objc_getClass(b'NSString')
    if not app_class or not ns_class: return False
    app=send0(app_class,sel('sharedApplication'))
    if not app: return False
    menu=send0(app,sel('mainMenu'))
    if not menu: return False
    first=send_idx(menu,sel('itemAtIndex:'),0)
    if not first: return False
    obj=send0(first,sel('title'))
    previous=(send_chars(obj,sel('UTF8String')) or b'').decode('utf-8','replace') if obj else ''
    if previous == name: return True
    # AppKit's first item must be the existing application menu. Do not touch
    # File/Edit/Window menus if it is not an app menu.
    if 'python' not in previous.casefold() and not previous.casefold().startswith('syn'):
        return False
    buffer=C.create_string_buffer(name.encode('utf-8'))
    title=send_obj(ns_class,sel('stringWithUTF8String:'),C.cast(buffer,C.c_void_p))
    if not title: return False
    send_set(first,sel('setTitle:'),title)
    # The first submenu may still read 'Python'. Update only that title.
    submenu=send0(first,sel('submenu'))
    if submenu: send_set(submenu,sel('setTitle:'),title)
    return True
