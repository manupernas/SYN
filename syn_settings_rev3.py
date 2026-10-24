#!/usr/bin/env python3
"""SYN 1.3b rev3: GTK4 settings dialog, grouped without changing config schema.

This module is imported by syn.py on opening Settings only. No background
worker, stream, FFmpeg, or user configuration files are touched until Save.
"""
from __future__ import annotations
import syn_sources as sources
from syn_i18n import LANGUAGE
from syn_multistream import profile_limit

# Source strings in Spanish are intentionally separate from programmatic choices.
# No provider channel or XMLTV programme text ever flows through this dictionary.
EN = {
 'Ajustes': ('Settings','Settings'), 'Perfil': ('Profile','Profile'),
 'Capturas de pantalla': ('Screenshots','Screenshots'),
 'Carpeta de capturas': ('Screenshot folder','Screenshot folder'),
 'Elegir carpeta…': ('Choose folder…','Choose folder…'),
 'Elige dónde guardar capturas PNG del vídeo.': ('Choose where PNG video frames are saved.','Choose where PNG video frames are saved.'),
 'Timeshift automático': ('Automatic timeshift','Automatic timeshift'),
 'Activar el búfer al reproducir un canal': ('Enable timeshift when a channel starts','Enable timeshift when a channel starts'),
 'Reproducción': ('Playback','Playback'), 'Apariencia': ('Appearance','Appearance'),
 'Fuentes y credenciales': ('Sources and credentials','Sources and credentials'),
 'Configura tus listas y conexiones.': ('Configure your playlists and connections.','Configure your playlists and connections.'),
 'Seleccionar perfil': ('Select profile','Select profile'), 'Nuevo perfil': ('New profile','New profile'),
 'Nombre del perfil': ('Profile name','Profile name'), 'Tipo de fuente': ('Source type','Source type'),
 'Archivo M3U': ('M3U file','M3U file'), 'URL M3U': ('M3U URL','M3U URL'),
 'Ruta o URL M3U': ('M3U path or URL','M3U path or URL'),
 'Servidor Xtream': ('Xtream server','Xtream server'), 'Usuario': ('Username','Username'),
 'Contraseña': ('Password','Password'), 'Formato': ('Format','Format'),
 'Conexiones simultáneas del proveedor': ('Provider connections', 'Provider connections'),
 'Incluye la reproducción y el timeshift (máx. 4).':
     ('Includes live playback and timeshift (max. 4).',
      'Includes live playback and timeshift (max. 4).'),
 'EPG XMLTV': ('XMLTV EPG','XMLTV EPG'),
 'URL o archivo .xml / .xml.gz': ('URL or .xml / .xml.gz file','URL or .xml / .xml.gz file'),
 'Elegir archivo EPG…': ('Choose EPG file…','Choose EPG file…'),
 'Opciones de reproducción': ('Playback options','Playback options'),
 'Las opciones de MPV se aplicarán tras reiniciar SYN.': ('MPV changes take effect after restarting SYN.','MPV changes take effect after restarting SYN.'),
 'Guía de programas': ('Programme guide','Programme guide'),
 'Actualizar la EPG del perfil actual': ('Refresh EPG for the current profile','Refresh EPG for the current profile'),
 'Actualizar EPG ahora': ('Refresh EPG now','Refresh EPG now'),
 'Se ha solicitado la actualización de la EPG.': ('EPG refresh requested.','EPG refresh requested.'),
 'User-Agent de vídeo (MPV)': ('Video User-Agent (MPV)','Video User-Agent (MPV)'),
 'User-Agent de listas y EPG': ('Playlist and EPG User-Agent','Playlist and EPG User-Agent'),
 'Personalizado (reproducción)': ('Custom (playback)','Custom (playback)'),
 'Personalizado (fuentes)': ('Custom (sources)','Custom (sources)'),
 'Predeterminado': ('Default','Default'), 'Personalizado': ('Custom','Custom'),
 'Aceleración por hardware': ('Hardware acceleration','Hardware acceleration'),
 'Caché del reproductor': ('Player cache','Player cache'),
 'Sincronización de vídeo': ('Video synchronisation','Video synchronisation'),
 'Búfer de demultiplexación': ('Demuxer buffer','Demuxer buffer'),
 'Predeterminado · 0 MiB': ('Default · 0 MiB','Default · 0 MiB'),
 'MiB': ('MiB','MiB'),
 'Diseño y colores': ('Design and colors','Design and colours'),
 'Elige cómo quieres que se vea SYN.': ('Choose how SYN looks.','Choose how SYN looks.'),
 'Tema de la aplicación': ('Application theme','Application theme'),
 'Sistema': ('System','System'), 'Claro': ('Light','Light'),
 'Oscuro': ('Dark','Dark'), 'Teal SYN': ('SYN Teal','SYN Teal'),
 'Respetar los colores del escritorio': ('Follow desktop colors','Follow desktop colours'),
 'Aspecto pastel': ('Pastel appearance','Pastel appearance'),
 'Negro y gris': ('Black and grey','Black and grey'),
 'Verde azulado petróleo': ('Deep teal','Deep teal'),
 'Color de realce personalizado': ('Custom accent color','Custom accent colour'),
 'Utilizar color propio': ('Use a custom color','Use a custom colour'),
 'Hexadecimal (#RRGGBB)': ('Hexadecimal (#RRGGBB)','Hexadecimal (#RRGGBB)'),
 'Colores rápidos': ('Quick colors','Quick colours'),
 'Logos de canales': ('Channel logos','Channel logos'),
 'Canal seleccionado': ('Selected channel','Selected channel'),
 'Selecciona primero un canal en la ventana principal.': ('Select a channel in the main window first.','Select a channel in the main window first.'),
 'Cargar archivo…': ('Load file…','Load file…'),
 'Logo desde URL…': ('Logo from URL…','Logo from URL…'),
 'Restaurar logo': ('Restore logo','Restore logo'),
 'Tus logos personalizados se conservan por perfil.': ('Your custom logos are saved per profile.','Your custom logos are saved per profile.'),
 'Eliminar perfil': ('Delete profile','Delete profile'),
 'Cancelar': ('Cancel','Cancel'), 'Guardar cambios': ('Save changes','Save changes'),
 'Ajustes guardados. Reinicia SYN para aplicar los cambios de MPV.': (
      'Settings saved. Restart SYN to apply MPV changes.',
      'Settings saved. Restart SYN to apply MPV changes.'),
 'El nombre del perfil no puede estar vacío.': ('The profile name cannot be empty.','The profile name cannot be empty.'),
 'Debe quedar al menos un perfil.': ('At least one profile must remain.','At least one profile must remain.'),
 'Selecciona un perfil existente.': ('Select an existing profile.','Select an existing profile.'),
 'Sí': ('Yes','Yes'), 'No': ('No','No'),
}

# SYN 1.3.6beta11: Nord/Gruvbox labels in Settings (en_US, en_GB).
# The existing translator t() selects one column; these are not channel names.
EN.update({
 'Nord claro': ('Nord Light', 'Nord Light'),
 'Nord oscuro': ('Nord Dark', 'Nord Dark'),
 'Snow Storm · hielo': ('Snow Storm · ice', 'Snow Storm · ice'),
 'Polar Night · ártico': ('Polar Night · Arctic', 'Polar Night · Arctic'),
 'Nord · Frost y Aurora': ('Nord · Frost and Aurora', 'Nord · Frost and Aurora'),
 'Frost · azul hielo': ('Frost · ice blue', 'Frost · ice blue'),
 'Aurora · rojo': ('Aurora · red', 'Aurora · red'),
 'Aurora · naranja': ('Aurora · orange', 'Aurora · orange'),
 'Aurora · amarillo': ('Aurora · yellow', 'Aurora · yellow'),
 'Aurora · verde': ('Aurora · green', 'Aurora · green'),
 'Aurora · violeta': ('Aurora · purple', 'Aurora · purple'),
 'Gruvbox claro': ('Gruvbox Light', 'Gruvbox Light'),
 'Gruvbox oscuro': ('Gruvbox Dark', 'Gruvbox Dark'),
 'Crema · retro': ('Cream · retro', 'Cream · retro'),
 'Café · retro': ('Coffee · retro', 'Coffee · retro'),
 'Gruvbox · colores de realce': ('Gruvbox · accent colors', 'Gruvbox · accent colours'),
 'Rojo': ('Red', 'Red'), 'Verde': ('Green', 'Green'),
 'Amarillo': ('Yellow', 'Yellow'), 'Azul': ('Blue', 'Blue'),
 'Morado': ('Purple', 'Purple'), 'Aqua': ('Aqua', 'Aqua'),
 'Naranja': ('Orange', 'Orange'),
 'Ajustes guardados. La reproducción continúa sin interrupción.':
    ('Settings saved. Playback continues uninterrupted.',
     'Settings saved. Playback continues uninterrupted.'),
})

def t(msg):
    if LANGUAGE == 'en_US':
        return EN.get(msg, (msg,msg))[0]
    if LANGUAGE == 'en_GB':
        return EN.get(msg, (msg,msg))[1]
    return msg


def open_settings(app, Gtk, GLib, Pango, normalize_accent_hex):
    win = Gtk.Window(title=f'SYN · {t("Ajustes")}', transient_for=app, modal=True,
                     default_width=860, default_height=670)
    win.add_css_class('syn-settings-window')
    if not getattr(app, '_rev3_settings_css_installed', False):
        css = Gtk.CssProvider()
        css.load_from_data(b'''
          window.syn-settings-window .syn-pref-header { padding: 16px 22px;
            border-bottom: 1px solid alpha(@window_fg_color,.12); }
          window.syn-settings-window .syn-pref-heading { font-size: 21px; font-weight: 750; }
          window.syn-settings-window .syn-pref-sidebar { min-width: 164px;
            padding: 12px 6px; border-right: 1px solid alpha(@window_fg_color,.12); }
          window.syn-settings-window .syn-pref-page { padding: 22px 25px; }
          window.syn-settings-window .syn-pref-section-title { font-size: 16px;
            font-weight: 750; margin-bottom: 4px; }
          window.syn-settings-window .syn-pref-group { padding: 12px;
            margin-bottom: 14px; border-radius: 14px;
            background-color: alpha(@window_fg_color,.045);
            border: 1px solid alpha(@window_fg_color,.09); }
          window.syn-settings-window .syn-pref-row { padding: 8px 5px; }
          window.syn-settings-window .syn-pref-muted { opacity: .74; font-size: 12px; }
          window.syn-settings-window .syn-pref-footer { padding: 12px 20px;
            border-top: 1px solid alpha(@window_fg_color,.12); }
          window.syn-settings-window .syn-pref-theme { border-radius: 12px;
            min-height: 66px; padding: 7px 12px; }
          window.syn-settings-window .syn-pref-theme:checked {
            border: 2px solid @accent_bg_color;
            background-color: alpha(@accent_bg_color,.17); }
          window.syn-settings-window button.syn-pref-swatch { min-width: 30px;
            min-height: 30px; border-radius: 50%; padding: 0; }
          window.syn-settings-window button.syn-pref-swatch-teal { background-color: #2A9D8F; }
          window.syn-settings-window button.syn-pref-swatch-orange { background-color: #F28C28; }
          window.syn-settings-window button.syn-pref-swatch-blue { background-color: #527EB0; }
          window.syn-settings-window button.syn-pref-swatch-red { background-color: #D94B63; }
          window.syn-settings-window button.syn-pref-swatch-aurora-frost { background-color: #88C0D0; }
          window.syn-settings-window button.syn-pref-swatch-aurora-red { background-color: #BF616A; }
          window.syn-settings-window button.syn-pref-swatch-aurora-orange { background-color: #D08770; }
          window.syn-settings-window button.syn-pref-swatch-aurora-yellow { background-color: #EBCB8B; }
          window.syn-settings-window button.syn-pref-swatch-aurora-green { background-color: #A3BE8C; }
          window.syn-settings-window button.syn-pref-swatch-aurora-purple { background-color: #B48EAD; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-red { background-color: #CC241D; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-green { background-color: #98971A; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-yellow { background-color: #D79921; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-blue { background-color: #458588; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-purple { background-color: #B16286; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-aqua { background-color: #689D6A; }
          window.syn-settings-window button.syn-pref-swatch-gruvbox-orange { background-color: #D65D0E; }
        ''')
        Gtk.StyleContext.add_provider_for_display(win.get_display(), css,
                                                    Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
        app._rev3_settings_css_installed = css

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    win.set_child(root)
    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    header.add_css_class('syn-pref-header')
    header_icon = Gtk.Image.new_from_icon_name('preferences-system-symbolic')
    header.set_valign(Gtk.Align.CENTER)
    header.append(header_icon)
    headline = Gtk.Label(label=f'SYN  ·  {t("Ajustes")}', xalign=0)
    headline.add_css_class('syn-pref-heading'); headline.set_hexpand(True)
    header.append(headline)
    root.append(header)

    area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    area.set_vexpand(True)
    root.append(area)
    stack = Gtk.Stack()
    stack.set_hexpand(True); stack.set_vexpand(True)
    stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    stack.set_transition_duration(180)
    sidebar = Gtk.StackSidebar()
    sidebar.add_css_class('syn-pref-sidebar')
    sidebar.set_stack(stack)
    sidebar.set_valign(Gtk.Align.FILL)
    area.append(sidebar)
    area.append(stack)

    def page(name, heading, detail):
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.add_css_class('syn-pref-page')
        box.set_hexpand(True)
        subtitle = Gtk.Label(label=detail, xalign=0)
        subtitle.add_css_class('syn-pref-muted'); subtitle.set_wrap(True)
        section_title = Gtk.Label(label=heading, xalign=0)
        section_title.add_css_class('syn-pref-section-title')
        box.append(section_title); box.append(subtitle)
        scroll.set_child(box)
        stack.add_titled(scroll, name, t(heading))
        return box

    profile_page = page('profile', 'Perfil', t('Configura tus listas y conexiones.'))
    playback_page = page('playback', 'Reproducción', t('Las opciones de MPV se aplicarán tras reiniciar SYN.'))
    appearance_page = page('appearance', 'Apariencia', t('Elige cómo quieres que se vea SYN.'))

    def group(parent, label):
        heading = Gtk.Label(label=t(label), xalign=0)
        heading.add_css_class('syn-pref-section-title')
        parent.append(heading)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class('syn-pref-group')
        parent.append(box)
        return box

    def field(parent, title, widget, hint=None):
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        line.add_css_class('syn-pref-row')
        caption = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        caption.set_hexpand(True)
        label = Gtk.Label(label=t(title), xalign=0)
        label.set_wrap(True); caption.append(label)
        if hint:
            sub = Gtk.Label(label=t(hint), xalign=0)
            sub.add_css_class('syn-pref-muted'); sub.set_wrap(True)
            caption.append(sub)
        line.append(caption)
        widget.set_halign(Gtk.Align.END)
        widget.set_valign(Gtk.Align.CENTER)
        line.append(widget)
        parent.append(line)
        return widget

    def combo(options, active=None, width=225):
        # Each choice is (persisted-value, translated-display-label).
        codes = [code for code, label in options]
        widget = Gtk.DropDown.new_from_strings([t(label) for code,label in options])
        widget.set_selected(codes.index(active) if active in codes else 0)
        widget.set_size_request(width, -1)
        return widget, codes

    def entry(value='', password=False, width=260):
        widget = Gtk.PasswordEntry() if password else Gtk.Entry()
        widget.set_text(str(value or ''))
        widget.set_size_request(width, -1)
        return widget

    profiles = app.cfg['profiles']
    profile_names = [(p['id'],p['name']) for p in profiles] + [(None,'＋ '+t('Nuevo perfil'))]
    source = app.profile
    picker, _ = combo(profile_names, source.get('id'))
    profile_group = group(profile_page, 'Fuentes y credenciales')
    field(profile_group, 'Seleccionar perfil', picker)
    pname = field(profile_group, 'Nombre del perfil', entry(source.get('name')))
    types = [('file','Archivo M3U'),('url','URL M3U'),('xtream','Xtream Codes')]
    source_type, kinds = combo(types, source.get('type','file'))
    field(profile_group, 'Tipo de fuente', source_type)
    src = field(profile_group, 'Ruta o URL M3U', entry(source.get('source')))
    server = field(profile_group, 'Servidor Xtream', entry(source.get('server')))
    user = field(profile_group, 'Usuario', entry(source.get('username')))
    passwd = field(profile_group, 'Contraseña', entry(source.get('password'), password=True))
    fmt, fmts = combo([('m3u8','m3u8'),('ts','ts')], source.get('format','m3u8'))
    field(profile_group, 'Formato', fmt)
    connections, conn_codes = combo([(i, str(i)) for i in range(1,5)],
                                    profile_limit(source))
    field(profile_group, 'Conexiones simultáneas del proveedor', connections,
          'Incluye la reproducción y el timeshift (máx. 4).')
    epg = field(profile_group, 'EPG XMLTV', entry(source.get('epg_url')),
                'URL o archivo .xml / .xml.gz')
    browse = Gtk.Button(label=t('Elegir archivo EPG…'))
    browse.set_halign(Gtk.Align.END)
    profile_group.append(browse)
    def on_epg_file(dlg, result):
        try:
            file = dlg.open_finish(result)
            if file and file.get_path(): epg.set_text(file.get_path())
        except GLib.Error:
            pass
    browse.connect('clicked', lambda *_: Gtk.FileDialog(
        title=t('Elegir archivo EPG…')).open(win, None, on_epg_file))

    opts = app.cfg.get('player', {})
    gp = group(playback_page, 'Guía de programas')
    refresh = Gtk.Button(label=t('Actualizar EPG ahora'))
    field(gp, 'Actualizar la EPG del perfil actual', refresh)
    def refresh_guide(*_):
        app.load_guide(force=True)
        notice.set_text(t('Se ha solicitado la actualización de la EPG.'))
    refresh.connect('clicked', refresh_guide)

    gp = group(playback_page, 'Opciones de reproducción')
    agents = [('Predeterminado','Predeterminado'),('VLC','VLC'),('Firefox','Firefox'),
              ('Safari','Safari'),('Personalizado','Personalizado')]
    ua, codes = combo(agents, opts.get('user_agent','Predeterminado'))
    field(gp, 'User-Agent de vídeo (MPV)', ua)
    custom_ua = field(gp, 'Personalizado (reproducción)', entry(opts.get('custom_ua','')))
    source_ua, _ = combo(agents, opts.get('source_user_agent','Predeterminado'))
    field(gp, 'User-Agent de listas y EPG', source_ua)
    source_custom_ua = field(gp, 'Personalizado (fuentes)', entry(opts.get('source_custom_ua','')))
    def agents_changed(*_):
        custom_ua.set_sensitive(codes[ua.get_selected()] == 'Personalizado')
        source_custom_ua.set_sensitive(codes[source_ua.get_selected()] == 'Personalizado')
    ua.connect('notify::selected', agents_changed)
    source_ua.connect('notify::selected', agents_changed)
    agents_changed()

    choices = [('Predeterminado','Predeterminado'), ('no','No'),
               ('auto-safe','auto-safe'), ('auto','auto')]
    hwdec, hcodes = combo(choices, opts.get('hwdec','Predeterminado'))
    field(gp, 'Aceleración por hardware', hwdec)
    cache, ccodes = combo([('Predeterminado','Predeterminado'), ('auto','auto'),
                            ('yes','Sí'),('no','No')], opts.get('cache','Predeterminado'))
    field(gp, 'Caché del reproductor', cache)
    sync, scodes = combo([('Predeterminado','Predeterminado'),('audio','audio'),
                          ('display-resample','display-resample')],
                         opts.get('video_sync','Predeterminado'))
    field(gp, 'Sincronización de vídeo', sync)

    mb_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1024, 16)
    scale.set_size_request(170, -1)
    scale.set_draw_value(False)
    scale.set_value(min(1024, max(0,int(opts.get('demuxer_mb',0) or 0))))
    mb_value = Gtk.Label(xalign=1)
    mb_box.append(scale); mb_box.append(mb_value)
    def scale_changed(w):
        value = int(round(w.get_value() / 16) * 16)
        mb_value.set_text(t('Predeterminado · 0 MiB') if not value else f'{value} {t("MiB")}')
    scale.connect('value-changed', scale_changed)
    scale_changed(scale)
    field(gp, 'Búfer de demultiplexación', mb_box)

    # SYN_CAPTURE_DIR_BETA5: folder picker through the GTK document portal.
    auto_group = group(playback_page, 'Timeshift automático')
    ts_auto = Gtk.Switch()
    ts_auto.set_active(bool(opts.get('timeshift_auto', True)))
    ts_auto.set_valign(Gtk.Align.CENTER)
    field(auto_group, 'Activar el búfer al reproducir un canal', ts_auto)
    capture_group = group(playback_page, 'Capturas de pantalla')
    pictures_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    default_capture = str((__import__('pathlib').Path(pictures_dir) if pictures_dir else
                          __import__('pathlib').Path.home() / 'Imágenes') / 'SYN')
    capture_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    capture_entry = Gtk.Entry()
    capture_entry.set_text(str(opts.get('screenshot_dir', '') or default_capture))
    capture_entry.set_hexpand(True)
    capture_entry.set_width_chars(28)
    capture_box.append(capture_entry)
    capture_choose = Gtk.Button(label=t('Elegir carpeta…'))
    capture_box.append(capture_choose)
    def capture_folder_done(dialog, result):
        try:
            file = dialog.select_folder_finish(result)
            if file and file.get_path():
                capture_entry.set_text(file.get_path())
        except GLib.Error:
            pass
    capture_choose.connect('clicked', lambda *_: Gtk.FileDialog(
        title=t('Carpeta de capturas')).select_folder(win, None, capture_folder_done))
    field(capture_group, 'Carpeta de capturas', capture_box,
          'Elige dónde guardar capturas PNG del vídeo.')

    gp = group(appearance_page, 'Tema de la aplicación')
    theme_codes = ['system','light','dark','teal','nord-light','nord-dark','gruvbox-light','gruvbox-dark']
    theme_labels = [('Sistema','Respetar los colores del escritorio'),
                    ('Claro','Aspecto pastel'),('Oscuro','Negro y gris'),
                    ('Teal SYN','Verde azulado petróleo'),
                    ('Nord claro','Snow Storm · hielo'),
                    ('Nord oscuro','Polar Night · ártico'),
                    ('Gruvbox claro','Crema · retro'),
                    ('Gruvbox oscuro','Café · retro')]
    tile_row = Gtk.Grid(column_spacing=8, row_spacing=8)
    tile_row.set_column_homogeneous(True)
    tiles = []
    for idx,(title,hint) in enumerate(theme_labels):
        tile = Gtk.ToggleButton()
        tile.add_css_class('syn-pref-theme')
        if tiles:
            tile.set_group(tiles[0])
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label = Gtk.Label(label=t(title)); label.set_wrap(True)
        sub = Gtk.Label(label=t(hint)); sub.add_css_class('syn-pref-muted')
        sub.set_wrap(True)
        content.append(label); content.append(sub)
        tile.set_child(content)
        tile.set_active(theme_codes[idx] == app.cfg.get('theme','teal'))
        tiles.append(tile)
        tile_row.attach(tile, idx % 2, idx // 2, 1, 1)
    gp.append(tile_row)

    gp = group(appearance_page, 'Color de realce personalizado')
    current_accent = app.cfg.get('accent_hex','')
    accent_switch = Gtk.Switch()
    field(gp, 'Utilizar color propio', accent_switch)
    color_entry = field(gp, 'Hexadecimal (#RRGGBB)', entry(current_accent or '#2A9D8F', width=135))
    accent_switch.set_active(bool(current_accent))
    accent_switch.connect('notify::active', lambda w,_: color_entry.set_sensitive(w.get_active()))
    color_entry.set_sensitive(accent_switch.get_active())
    swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    for name,hex_value in [('teal','#2A9D8F'),('orange','#F28C28'),
                           ('blue','#527EB0'),('red','#D94B63')]:
        swatch = Gtk.Button()
        swatch.add_css_class('syn-pref-swatch')
        swatch.add_css_class('syn-pref-swatch-'+name)
        swatch.set_tooltip_text(hex_value)
        swatch.connect('clicked', lambda _btn, c=hex_value: (
            accent_switch.set_active(True), color_entry.set_text(c)))
        swatches.append(swatch)
    field(gp, 'Colores rápidos', swatches)

    # NORDBETA: Frost plus Nord11..15 Aurora, saved using existing accent_hex.
    aurora_title = Gtk.Label(label=t('Nord · Frost y Aurora'), xalign=0)
    aurora_title.add_css_class('syn-pref-section-title')
    gp.append(aurora_title)
    aurora_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
    for slug, title, hex_value in (
        ('frost', 'Frost · azul hielo', '#88C0D0'),
        ('red', 'Aurora · rojo', '#BF616A'),
        ('orange', 'Aurora · naranja', '#D08770'),
        ('yellow', 'Aurora · amarillo', '#EBCB8B'),
        ('green', 'Aurora · verde', '#A3BE8C'),
        ('purple', 'Aurora · violeta', '#B48EAD'),
    ):
        button = Gtk.Button()
        button.add_css_class('syn-pref-swatch')
        button.add_css_class('syn-pref-swatch-aurora-' + slug)
        button.set_tooltip_text(t(title) + '  ' + hex_value)
        button.connect('clicked', lambda _btn, color=hex_value: (
            accent_switch.set_active(True), color_entry.set_text(color)))
        aurora_row.append(button)
    gp.append(aurora_row)

    gruvbox_title = Gtk.Label(label=t('Gruvbox · colores de realce'), xalign=0)
    gruvbox_title.add_css_class('syn-pref-section-title')
    gp.append(gruvbox_title)
    gruvbox_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    for slug, title, hex_value in (
        ('red', 'Rojo', '#CC241D'),
        ('green', 'Verde', '#98971A'),
        ('yellow', 'Amarillo', '#D79921'),
        ('blue', 'Azul', '#458588'),
        ('purple', 'Morado', '#B16286'),
        ('aqua', 'Aqua', '#689D6A'),
        ('orange', 'Naranja', '#D65D0E'),
    ):
        button = Gtk.Button()
        button.add_css_class('syn-pref-swatch')
        button.add_css_class('syn-pref-swatch-gruvbox-' + slug)
        button.set_tooltip_text('Gruvbox · ' + t(title) + ' · ' + hex_value)
        button.connect('clicked', lambda _btn, color=hex_value: (
            accent_switch.set_active(True), color_entry.set_text(color)))
        gruvbox_row.append(button)
    gp.append(gruvbox_row)

    gp = group(appearance_page, 'Logos de canales')
    ch = app._logo_selected_channel()
    if ch:
        name = Gtk.Label(label=f'{t("Canal seleccionado")}: {ch.name}', xalign=0)
        name.set_wrap(True); gp.append(name)
        preview = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        preview.append(app.channel_pill(ch,148,58))
        app._logo_settings_preview = (ch,preview)
        gp.append(preview)
    else:
        name = Gtk.Label(label=t('Selecciona primero un canal en la ventana principal.'),xalign=0)
        name.add_css_class('syn-pref-muted'); name.set_wrap(True); gp.append(name)
        app._logo_settings_preview = (None,Gtk.Box())
    buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    for title, cb in [('Cargar archivo…', lambda: app.choose_custom_logo(channel=ch)),
                      ('Logo desde URL…', lambda: app.choose_custom_logo_url(channel=ch)),
                      ('Restaurar logo', lambda: app.reset_selected_logo())]:
        btn = Gtk.Button(label=t(title))
        btn.set_sensitive(bool(ch))
        btn.connect('clicked', lambda _button, action=cb: action())
        buttons.append(btn)
    gp.append(buttons)
    tip = Gtk.Label(label=t('Tus logos personalizados se conservan por perfil.'), xalign=0)
    tip.add_css_class('syn-pref-muted'); gp.append(tip)

    footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    footer.add_css_class('syn-pref-footer')
    root.append(footer)
    delete = Gtk.Button(label=t('Eliminar perfil'))
    delete.add_css_class('destructive-action')
    footer.append(delete)
    notice = Gtk.Label(label='', xalign=0)
    notice.add_css_class('syn-pref-muted')
    notice.set_hexpand(True); notice.set_ellipsize(Pango.EllipsizeMode.END)
    notice.set_tooltip_text('')
    footer.append(notice)
    cancel = Gtk.Button(label=t('Cancelar'))
    footer.append(cancel)
    save = Gtk.Button(label=t('Guardar cambios'))
    save.add_css_class('suggested-action')
    footer.append(save)

    state = {'id': app.profile['id']}
    def source_changed(*_):
        is_xtream = kinds[source_type.get_selected()] == 'xtream'
        src.set_sensitive(not is_xtream)
        for widget in (server,user,passwd,fmt): widget.set_sensitive(is_xtream)
    source_type.connect('notify::selected', source_changed)

    def picker_changed(*_):
        index = picker.get_selected()
        p = (profiles[index] if index < len(profiles) else None)
        state['id'] = p.get('id') if p else None
        if p is None:
            p = {'type':'file','format':'m3u8','name':t('Nuevo perfil')}
        for widget,key in ((pname,'name'), (src,'source'), (server,'server'),
                           (user,'username'), (passwd,'password'), (epg,'epg_url')):
            widget.set_text(str(p.get(key,'') or ''))
        kind = p.get('type','file')
        source_type.set_selected(kinds.index(kind) if kind in kinds else 0)
        fmt.set_selected(1 if p.get('format') == 'ts' else 0)
        connections.set_selected(conn_codes.index(profile_limit(p)))
        source_changed()
    picker.connect('notify::selected', picker_changed)
    source_changed()

    def delete_click(*_):
        if len(app.cfg['profiles']) <= 1:
            notice.set_text(t('Debe quedar al menos un perfil.')); return
        victim = next((p for p in app.cfg['profiles'] if p.get('id') == state['id']),None)
        if victim is None:
            notice.set_text(t('Selecciona un perfil existente.')); return
        app.cfg['profiles'].remove(victim)
        app.profile = app.cfg['profiles'][0]
        app.cfg['selected'] = app.profile['id']
        app.favorites = set(app.profile.get('favorites',[]))
        sources.save_config(app.cfg)
        app.profile_picker.set_model(Gtk.StringList.new([p['name'] for p in app.cfg['profiles']]))
        app.profile_picker.set_selected(0)
        app.load_channels()
        win.close()

    def save_click(*_):
        # SYN 2.0.5: Appearance is independent from source validation.
        # A missing local M3U / EPG path must never block selecting a theme.
        if stack.get_visible_child_name() == 'appearance':
            try:
                chosen_accent = (normalize_accent_hex(color_entry.get_text().strip())
                                 if accent_switch.get_active() else '')
            except ValueError as exc:
                notice.set_text(str(exc))
                notice.set_tooltip_text(str(exc))
                return
            chosen_theme = next((name for name, button in zip(theme_codes, tiles)
                                 if button.get_active()), app.cfg.get('theme', 'system'))
            # Update in memory and on disk without touching source credentials,
            # DVR jobs, playback settings, or the currently tuned channel.
            app.cfg['accent_hex'] = chosen_accent
            app.cfg['theme'] = chosen_theme
            sources.save_config(app.cfg)
            app.get_application().apply_theme(chosen_theme, chosen_accent)
            app.status.set_text(t('Ajustes guardados. La reproducción continúa sin interrupción.'))
            win.close()
            return
        is_new = state['id'] is None
        new_id = state['id'] or sources.next_profile_id()
        obj = dict(next((p for p in app.cfg['profiles'] if p.get('id') == new_id), {}))
        obj.update(id=new_id, name=pname.get_text().strip(),
                   type=kinds[source_type.get_selected()], source=src.get_text().strip(),
                   server=server.get_text().strip(), username=user.get_text().strip(),
                   password=passwd.get_text(), format=fmts[fmt.get_selected()],
                   epg_url=epg.get_text().strip(),
                   max_connections=conn_codes[connections.get_selected()])
        # Validate everything before changing persistent config, including theme.
        try:
            if not obj['name']:
                raise ValueError(t('El nombre del perfil no puede estar vacío.'))
            sources.validate_profile(obj)
            accent = (normalize_accent_hex(color_entry.get_text().strip())
                      if accent_switch.get_active() else '')
        except ValueError as exc:
            notice.set_text(str(exc)); notice.set_tooltip_text(str(exc)); return
        previous_profile = next((p for p in app.cfg['profiles']
                                 if p.get('id') == new_id), None)
        profile_changed = (is_new or previous_profile != obj
                           or app.cfg.get('selected') != obj['id'])
        if is_new:
            app.cfg['profiles'].append(obj)
        else:
            old = next(p for p in app.cfg['profiles'] if p['id'] == obj['id'])
            app.cfg['profiles'][app.cfg['profiles'].index(old)] = obj
        app.cfg['selected'] = obj['id']
        app.cfg['accent_hex'] = accent
        app.cfg['theme'] = next((name for name, button in zip(theme_codes,tiles)
                                if button.get_active()),app.cfg.get('theme','teal'))
        app.cfg['player'] = {
            'user_agent': codes[ua.get_selected()],
            'custom_ua': custom_ua.get_text().strip(),
            'source_user_agent': codes[source_ua.get_selected()],
            'source_custom_ua': source_custom_ua.get_text().strip(),
            'hwdec': hcodes[hwdec.get_selected()],
            'cache': ccodes[cache.get_selected()],
            'video_sync': scodes[sync.get_selected()],
            'demuxer_mb': int(round(scale.get_value() / 16) * 16),
            'screenshot_dir': capture_entry.get_text().strip(),
            'timeshift_auto': bool(ts_auto.get_active()),
        }
        sources.save_config(app.cfg)
        app.get_application().apply_theme(app.cfg['theme'],app.cfg['accent_hex'])
        app.player_options = dict(app.cfg['player'])
        # Reconstruct the UI only for a genuinely changed source/profile.
        # Theme-only Save must NOT reset the currently playing mpv stream,
        # its EPG, selected channel or scrolled list.
        app.profile = obj
        if profile_changed:
            app.favorites = set(obj.get('favorites', []))
            app.profile_picker.set_model(Gtk.StringList.new(
                [p['name'] for p in app.cfg['profiles']]))
            app.profile_picker.set_selected(app.cfg['profiles'].index(obj))
            app.load_channels()
        app.status.set_text(t('Ajustes guardados. La reproducción continúa sin interrupción.'))
        win.close()

    def tab_changed(stack,_pspec):
        delete.set_visible(stack.get_visible_child_name() == 'profile')
    stack.connect('notify::visible-child-name', tab_changed)
    stack.set_visible_child_name('profile')
    tab_changed(stack,None)
    save.connect('clicked',save_click)
    cancel.connect('clicked',lambda *_: win.close())
    delete.connect('clicked',delete_click)
    win.present()
    return win
