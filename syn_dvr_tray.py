#!/usr/bin/env python3
"""SYN DVR tray: real StatusNotifierItem + DBusMenu for GNOME Status Tray.

Runs WITHIN the SYN Flatpak, as a separate user systemd service that
invokes Flatpak. Playback and recordings never depend on this process.
Never puts stream URLs or credentials on D-Bus.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

APP_ID = 'com.mrseivane.Syn'
SERVICE = 'com.mrseivane.Syn.Tray'
SNI_PATH = '/StatusNotifierItem'
MENU_PATH = '/MenuBar'
SNI = 'org.kde.StatusNotifierItem'
DBMENU = 'com.canonical.dbusmenu'
IS_NATIVE = os.environ.get('SYN_NATIVE_PACKAGE') == '1'
DB_PATH = ((Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'syn/dvr.json')
           if IS_NATIVE else (Path.home() / '.var/app' / APP_ID / 'data/syn/dvr.json'))
ICON_PATH = Path('/usr/share/icons/hicolor/48x48/apps/com.mrseivane.Syn.png' if IS_NATIVE
                 else '/app/share/icons/hicolor/48x48/apps/com.mrseivane.Syn.png')

SNI_XML = '''<node>
<interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="WindowId" type="u" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="OverlayIconName" type="s" access="read"/>
  <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
  <property name="AttentionIconName" type="s" access="read"/>
  <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <signal name="NewIcon"/>
  <signal name="NewTitle"/>
  <signal name="NewStatus"><arg type="s"/></signal>
  <signal name="NewMenu"/>
</interface>
</node>'''
MENU_XML = '''<node>
<interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout">
    <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
    <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
  </method>
  <method name="GetGroupProperties">
    <arg type="ai" direction="in"/><arg type="as" direction="in"/>
    <arg type="a(ia{sv})" direction="out"/>
  </method>
  <method name="GetProperty">
    <arg type="i" direction="in"/><arg type="s" direction="in"/>
    <arg type="v" direction="out"/>
  </method>
  <method name="Event">
    <arg type="i" direction="in"/><arg type="s" direction="in"/>
    <arg type="v" direction="in"/><arg type="u" direction="in"/>
  </method>
  <method name="EventGroup">
    <arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/>
  </method>
  <method name="AboutToShow">
    <arg type="i" direction="in"/><arg type="b" direction="out"/>
  </method>
  <method name="AboutToShowGroup">
    <arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
  </method>
  <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
  <signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
  <signal name="ItemActivationRequested"><arg type="i"/><arg type="u"/></signal>
</interface>
</node>'''


def read_state(path=DB_PATH, now=None):
    """Return (worker_alive, active_channels, folder). Never expose stream URLs."""
    if now is None:
        now = time.time()
    try:
        db = json.loads(Path(path).read_text(encoding='utf-8'))
        worker_age = now - float(db.get('heartbeat', 0))
        alive = (db.get('worker_mode') == 'background'
                 and int(db.get('worker_pid', 0)) > 0 and 0 <= worker_age < 12)
        if not alive:
            return False, [], None
        jobs = db.get('jobs', [])
        if not isinstance(jobs, list):
            return False, [], None
        channels = []
        for job in jobs:
            if isinstance(job, dict) and job.get('status') in ('running', 'reconnecting'):
                channel = str(job.get('channel', 'Canal') or 'Canal')
                # One line, short; no URL/credentials ever sent on D-Bus.
                channels.append(' '.join(channel.split())[:72])
        folder = db.get('folder')
        return True, channels, folder if isinstance(folder, str) else None
    except (OSError, ValueError, TypeError, OverflowError, AttributeError):
        return False, [], None


def menu_rows(channels, worker_alive):
    """Stable IDs; disabled informational entries are non-interactive."""
    count = len(channels)
    rows = [(1, f'● Grabando: {count} canal' + ('' if count == 1 else 'es'), False, False)]
    for idx, ch in enumerate(channels[:4]):
        rows.append((10 + idx, '  ' + ch, False, False))
    if count > 4:
        rows.append((14, f'  Y {count - 4} grabación(es) más', False, False))
    rows += [(20, 'Servicio DVR: activo' if worker_alive else 'Servicio DVR: no disponible', False, False),
             (30, '', False, True),
             (40, 'Abrir SYN', True, False),
             (41, 'Abrir carpeta de grabaciones', True, False)]
    return rows


def spawn(args):
    try:
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError as exc:
        print('SYN tray: no se pudo abrir: ' + str(exc), file=sys.stderr)
        return False


class RecordingIndicator:
    def __init__(self):
        from gi.repository import Gio, GLib, GdkPixbuf
        self.Gio, self.GLib, self.GdkPixbuf = Gio, GLib, GdkPixbuf
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.name_owned = False
        self.registered_watchers = set()
        self.alive, self.channels, self.folder = False, [], None
        self.revision = 1
        self.rows = menu_rows([], False)
        self.pixmaps = self.build_pixmaps()
        self.node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        self.menu_node = Gio.DBusNodeInfo.new_for_xml(MENU_XML)
        self.reg_sni = self.bus.register_object(
            SNI_PATH, self.node.interfaces[0], self.on_method, self.get_property, None)
        self.reg_menu = self.bus.register_object(
            MENU_PATH, self.menu_node.interfaces[0], self.on_method, self.get_property, None)
        self.mainloop = GLib.MainLoop()

    def build_pixmaps(self):
        if not ICON_PATH.is_file():
            return []
        result = []
        for size in (32, 48):
            try:
                pix = self.GdkPixbuf.Pixbuf.new_from_file_at_scale(str(ICON_PATH), size, size, True)
                data = bytes(pix.get_pixels())
                stride, chans = pix.get_rowstride(), pix.get_n_channels()
                rgba = []
                for y in range(size):
                    for x in range(size):
                        p = y * stride + x * chans
                        r, g, b = data[p:p+3]
                        a = data[p+3] if chans == 4 else 255
                        dx = x - (size - size // 5)
                        dy = y - size // 5
                        if dx*dx+dy*dy <= (size//7)**2:
                            r, g, b, a = 237, 55, 67, 255
                        rgba.extend((a, r, g, b))
                result.append((size, size, bytes(rgba)))
            except (self.GLib.Error, OSError, ValueError):
                return []
        return result

    def get_property(self, _connection, _sender, _path, iface, name):
        v = self.GLib.Variant
        n = len(self.channels)
        if iface == SNI:
            props = {
                'Category': v('s', 'ApplicationStatus'),
                'Id': v('s', 'syn-dvr-recording'),
                'Title': v('s', f'SYN DVR · {n} grabación(es)'),
                'Status': v('s', 'Active'),
                'WindowId': v('u', 0),
                'IconName': v('s', '' if self.pixmaps else APP_ID),
                'IconPixmap': v('a(iiay)', self.pixmaps),
                'OverlayIconName': v('s', ''),
                'OverlayIconPixmap': v('a(iiay)', []),
                'AttentionIconName': v('s', ''),
                'AttentionIconPixmap': v('a(iiay)', []),
                'ToolTip': v('(sa(iiay)ss)', ('', self.pixmaps, 'SYN · DVR',
                           f'{n} grabación(es) en segundo plano')),
                'ItemIsMenu': v('b', True),
                'Menu': v('o', MENU_PATH),
            }
        elif iface == DBMENU:
            props = {
                'Version': v('u', 3),
                'TextDirection': v('s', 'ltr'),
                'Status': v('s', 'normal'),
                'IconThemePath': v('as', []),
            }
        else:
            return None
        return props.get(name)

    def row_properties(self, row, filters=()):
        _id, label, enabled, separator = row
        v = self.GLib.Variant
        props = {'label': v('s', label), 'enabled': v('b', enabled),
                 'visible': v('b', True)}
        if separator:
            props['type'] = v('s', 'separator')
        return {k: p for k, p in props.items() if not filters or k in filters}

    def layout(self, node_id=0, depth=-1, filters=()):
        v = self.GLib.Variant
        if node_id != 0:
            row = next((r for r in self.rows if r[0] == node_id), None)
            return (node_id, self.row_properties(row, filters) if row else {}, [])
        children = []
        if depth != 0:
            for row in self.rows:
                child = v('(ia{sv}av)', (row[0], self.row_properties(row, filters), []))
                children.append(child)
        return 0, {}, children

    def refresh(self):
        alive, channels, folder = read_state()
        changed = (self.alive, self.channels, self.folder) != (alive, channels, folder)
        self.alive, self.channels, self.folder = alive, channels, folder
        self.rows = menu_rows(channels, alive)
        if changed:
            self.revision = (self.revision + 1) % (2**32)
            if self.name_owned:
                self.bus.emit_signal(None, MENU_PATH, DBMENU, 'LayoutUpdated',
                                     self.GLib.Variant('(ui)', (self.revision, 0)))
                self.bus.emit_signal(None, SNI_PATH, SNI, 'NewTitle', None)
        return changed

    def on_method(self, connection, sender, obj, iface, method, parameters, invocation):
        v = self.GLib.Variant
        if iface == SNI:
            if method in ('Activate', 'SecondaryActivate'):
                spawn(['syn'] if IS_NATIVE else ['flatpak-spawn', '--host', 'flatpak', 'run', '--user', APP_ID])
            # ContextMenu supplied by DBusMenu via the Menu property.
            invocation.return_value(None)
            return
        if iface != DBMENU:
            invocation.return_dbus_error('com.mrseivane.Syn.UnknownInterface', iface)
            return
        if method == 'AboutToShow':
            self.refresh()
            invocation.return_value(v('(b)', (False,)))
        elif method == 'GetLayout':
            parent, depth, names = parameters.unpack()
            self.refresh()
            invocation.return_value(v('(u(ia{sv}av))',
                                      (self.revision, self.layout(parent, depth, names))))
        elif method == 'GetGroupProperties':
            ids, names = parameters.unpack()
            rows = [(r[0], self.row_properties(r, names)) for r in self.rows if r[0] in ids]
            invocation.return_value(v('(a(ia{sv}))', (rows,)))
        elif method == 'GetProperty':
            ident, name = parameters.unpack()
            row = next((r for r in self.rows if r[0] == ident), None)
            prop = self.row_properties(row).get(name) if row else None
            if prop is None:
                invocation.return_dbus_error('com.canonical.dbusmenu.Error', 'Propiedad no disponible')
            else:
                invocation.return_value(v('(v)', (prop,)))
        elif method in ('Event', 'EventGroup'):
            events = ([parameters.unpack()] if method == 'Event'
                      else parameters.unpack()[0])
            unknown = []
            for ident, ev, _data, _timestamp in events:
                if ev != 'clicked':
                    continue
                if ident == 40:
                    spawn(['syn'] if IS_NATIVE else ['flatpak-spawn', '--host', 'flatpak', 'run', '--user', APP_ID])
                elif ident == 41:
                    folder = Path(self.folder or (Path.home() / 'Vídeos/SYN')).expanduser()
                    if folder.is_dir():
                        spawn(['xdg-open', str(folder)] if IS_NATIVE else ['flatpak-spawn', '--host', 'xdg-open', str(folder)])
                else:
                    unknown.append(ident)
            if method == 'Event':
                invocation.return_value(None)
            else:
                invocation.return_value(v('(ai)', (unknown,)))
        elif method == 'AboutToShowGroup':
            ids, = parameters.unpack()
            self.refresh()
            invocation.return_value(v('(aiai)', ([], [])))
        else:
            invocation.return_dbus_error('com.mrseivane.Syn.UnknownMethod', method)

    def name_has_owner(self, name):
        try:
            response = self.bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'NameHasOwner', self.GLib.Variant('(s)', (name,)),
                self.GLib.VariantType.new('(b)'), self.Gio.DBusCallFlags.NONE, 900, None)
            return response.unpack()[0]
        except self.GLib.Error:
            return False

    def set_visible(self, visible):
        if self.name_owned == visible:
            return
        action, signature = ('RequestName', '(su)') if visible else ('ReleaseName', '(s)')
        args = (SERVICE, 0) if visible else (SERVICE,)
        try:
            reply = self.bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', action, self.GLib.Variant(signature, args),
                self.GLib.VariantType.new('(u)'), self.Gio.DBusCallFlags.NONE, 1200, None)
            code, = reply.unpack()
            self.name_owned = (code in (1, 4)) if visible else False
        except self.GLib.Error as exc:
            self.name_owned = False
            print('SYN tray: error D-Bus: ' + str(exc), file=sys.stderr)
        if self.name_owned:
            self.registered_watchers.clear()
            self.register_watchers()

    def register_watchers(self):
        for watcher in ('org.kde.StatusNotifierWatcher', 'org.freedesktop.StatusNotifierWatcher'):
            if not self.name_has_owner(watcher):
                self.registered_watchers.discard(watcher)
                continue
            if watcher in self.registered_watchers:
                continue
            try:
                self.bus.call_sync(watcher, '/StatusNotifierWatcher', watcher,
                    'RegisterStatusNotifierItem', self.GLib.Variant('(s)', (SERVICE,)),
                    None, self.Gio.DBusCallFlags.NONE, 1200, None)
                self.registered_watchers.add(watcher)
            except self.GLib.Error:
                pass

    def tick(self):
        self.refresh()
        # Icono visible mientras el DVR independiente graba, esté o no abierta la ventana.
        self.set_visible(self.alive and len(self.channels) > 0)
        if self.name_owned:
            self.register_watchers()
        return True

    def run(self):
        self.tick()
        self.GLib.timeout_add_seconds(2, self.tick)
        self.mainloop.run()


def self_test():
    """Static and GI signature smoke test, without joining the D-Bus session."""
    assert read_state('/nonexistent/dvr.json') == (False, [], None)
    rows = menu_rows(['LA 1 UHD'], True)
    assert any(r[0] == 40 and r[2] for r in rows)
    assert any('LA 1 UHD' in r[1] and not r[2] for r in rows)
    from gi.repository import Gio, GLib
    Gio.DBusNodeInfo.new_for_xml(SNI_XML)
    Gio.DBusNodeInfo.new_for_xml(MENU_XML)
    fake = object.__new__(RecordingIndicator)
    fake.GLib = GLib
    fake.rows = rows
    fake.revision = 1
    layout = fake.layout()
    result = GLib.Variant('(u(ia{sv}av))', (fake.revision, layout))
    assert result.get_type_string() == '(u(ia{sv}av))'
    assert len(result.unpack()[1][2]) == len(rows)
    print('OK: menú D-Bus con', len(rows), 'elementos; GetLayout válido.')


def main():
    if '--self-test' in sys.argv:
        self_test()
        return 0
    try:
        RecordingIndicator().run()
    except Exception as exc:
        print('ERROR SYN DVR indicator: ' + repr(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
