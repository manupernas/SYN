"""SYN-Plus 2.0 alpha1 — three-zone GTK4 workbench built on SYN 1.3.7.

Preserves the existing Gtk.GLArea, libmpv, DVR, Cast, profile, EPG, and
channel handlers. This file changes placement and presentation, not backends.
"""
from __future__ import annotations


def css(theme='system'):
    """Theme-neutral GTK CSS, with small scoped overrides for bundled palettes."""
    values = {
        'teal': ('#091b20', '#0f252a', '#10272c', '#e9f7f4', '#162f34', '#f1a46a'),
        'dark': ('#11161e', '#18212b', '#1b2631', '#f2f5f8', '#283440', '#76c2c2'),
        'light': ('#f1f5f8', '#f9fbfd', '#ffffff', '#18242e', '#e7eef2', '#177e79'),
        'nord-dark': ('#222b37', '#293644', '#303f50', '#e9f0f6', '#39485a', '#88c0d0'),
        'nord-light': ('#eceff4', '#f5f7fa', '#ffffff', '#293b4c', '#e4e9f0', '#5e81ac'),
        'gruvbox-dark': ('#242321', '#302d28', '#37332c', '#f6ead6', '#484239', '#d79921'),
        'gruvbox-light': ('#fbf1c7', '#f8f2da', '#fffae6', '#3c3836', '#eee5c6', '#458588'),
    }
    if theme in values:
        bg, nav, surface, fg, hover, accent = values[theme]
        palette = f'''
        window.iptv-tv.synplus-window {{ background-color:{bg}; color:{fg}; }}
        window.iptv-tv .synplus-nav {{ background-color:{nav}; color:{fg}; border-color:alpha({fg},.11); }}
        window.iptv-tv .synplus-workbench {{ background-color:{bg}; }}
        window.iptv-tv .synplus-sidebar {{ background-color:{nav}; color:{fg}; border-color:alpha({fg},.09); }}
        window.iptv-tv .synplus-guide {{ background-color:{surface}; color:{fg}; border-color:alpha({fg},.12); }}
        window.iptv-tv .synplus-nav-button {{ color:{fg}; }}
        window.iptv-tv button.synplus-nav-button:hover {{ background-color:{hover}; }}
        window.iptv-tv button.synplus-nav-button.synplus-current {{ background-color:alpha({accent},.22); color:{fg}; }}
        window.iptv-tv .synplus-sidebar .iptv-row {{ background-color:transparent; color:{fg}; }}
        window.iptv-tv .synplus-sidebar .iptv-row:hover {{ background-color:{hover}; }}
        window.iptv-tv .synplus-sidebar .iptv-row:selected {{ background-color:alpha({accent},.18); border-color:alpha({accent},.50); }}
        window.iptv-tv .synplus-sidebar .iptv-row label {{ color:{fg}; }}
        window.iptv-tv .synplus-sidebar .iptv-search {{ background-color:{hover}; color:{fg}; }}
        '''
    else:
        palette = '''
        window.iptv-tv .synplus-nav { background-color: alpha(@window_fg_color,.035);
           border-color:alpha(@window_fg_color,.13); }
        window.iptv-tv .synplus-sidebar { background-color:alpha(@window_fg_color,.018);
           border-color:alpha(@window_fg_color,.11); }
        window.iptv-tv .synplus-guide { background-color:@window_bg_color;
           border-color:alpha(@window_fg_color,.12); }
        window.iptv-tv button.synplus-nav-button.synplus-current {
           background-color:alpha(@accent_color,.16); }
        window.iptv-tv .synplus-sidebar .iptv-row { background-color:transparent; }
        window.iptv-tv .synplus-sidebar .iptv-row:hover { background-color:alpha(@window_fg_color,.07); }
        window.iptv-tv .synplus-sidebar .iptv-row:selected {
           background-color:alpha(@accent_color,.13); border-color:alpha(@accent_color,.4); }
        '''
    # Pastillas cromáticas inspiradas por el boceto: estilo, no datos falsos.
    if theme in ('light', 'nord-light', 'gruvbox-light'):
        epg_colors = ('#b8dfd4', '#d8c4ef', '#c0ddf6', '#f7dbb8', '#c0e9dc', '#e4d5ee')
        epg_text = '#24333e'
    else:
        epg_colors = ('#245d48', '#59317e', '#194c86', '#6a5231', '#266064', '#724653')
        epg_text = '#f9fcfd'
    palette += ''.join(
        f'window.iptv-tv .synplus-guide .syn-guide-program-{n} '
        f'{{ background-color:{tone}; }}\n'
        for n, tone in enumerate(epg_colors)
    )
    palette += ('window.iptv-tv .synplus-guide .syn-guide-program-name, '
                'window.iptv-tv .synplus-guide .syn-guide-time '
                '{ color:' + epg_text + '; }')
    return '''
    /* SYN-Plus 2.0: visual workbench of the approved 2026-10-23 mockups. */
    window.iptv-tv .synplus-plus-mark {
      font-size:10px; font-weight:750; letter-spacing:2px;
      opacity:.66; margin-bottom:7px;
    }
    window.iptv-tv .synplus-workbench { border-spacing:0; }
    window.iptv-tv .synplus-nav {
      padding:10px 9px 13px 9px; border-right:1px solid;
    }
    window.iptv-tv .synplus-nav-brand { margin:6px 0 12px 0; }
    window.iptv-tv button.synplus-nav-button {
      min-height:34px; margin:2px 0; padding:6px 10px;
      border:0; border-radius:11px; background-image:none;
      background-color:transparent; box-shadow:none;
      font-size:13px; font-weight:560; text-shadow:none;
    }
    window.iptv-tv button.synplus-nav-button.synplus-current { font-weight:740; }
    window.iptv-tv .synplus-nav-note { font-size:10px; opacity:.63; margin:4px 10px; }
    window.iptv-tv .synplus-nav-spacer { min-height:12px; }
    window.iptv-tv .synplus-sidebar { border-right:1px solid; padding:4px 0 0 0; }
    window.iptv-tv .synplus-sidebar searchentry,
    window.iptv-tv .synplus-sidebar .iptv-search { min-height:34px; border-radius:13px; }
    window.iptv-tv .synplus-sidebar .iptv-row {
      border:1px solid transparent; border-radius:11px; margin:1px 5px;
      min-height:45px; box-shadow:none;
    }
    window.iptv-tv .synplus-sidebar .iptv-row:selected { border-width:1px; }
    window.iptv-tv .synplus-sidebar .syn-channel-display-name { font-size:12px; font-weight:580; }
    window.iptv-tv .synplus-sidebar .syn-heart-filter { min-width:34px; min-height:31px; }
    window.iptv-tv .synplus-visual-player { background-color:#03080b; }
    window.iptv-tv .synplus-video-chrome {
      background-image:linear-gradient(to bottom,
          rgba(4,10,16,0),rgba(4,10,16,.72) 24%,rgba(4,10,16,.94) 100%);
      color:#f6f8fa; padding:24px 13px 10px 13px;
    }
    window.iptv-tv .synplus-video-chrome label { color:#f6f8fa; }
    window.iptv-tv .synplus-video-chrome .iptv-details { color:#d8e0e8; }
    window.iptv-tv .synplus-video-chrome .iptv-toolbar {
      background-color:transparent; background-image:none;
      border:0; box-shadow:none; padding:0;
    }
    window.iptv-tv .synplus-video-chrome .iptv-toolbar button {
      min-width:27px; min-height:28px; padding:3px 7px; margin:0;
      border-radius:16px; border-color:rgba(255,255,255,.10);
      background-color:rgba(33,45,53,.48); color:#f9fafb;
      box-shadow:none; font-size:12px;
    }
    window.iptv-tv .synplus-sidebar .syn-logo-pill { border-radius:10px; }
    window.iptv-tv .synplus-video-chrome .iptv-toolbar button:hover {
      background-color:rgba(68,90,101,.75);
    }
    window.iptv-tv .synplus-video-chrome .iptv-toolbar button.syn-dvr-rec {
      color:#ff4c54; font-size:18px; font-weight:900;
    }
    window.iptv-tv .synplus-guide {
      margin:5px 10px 10px 10px; border:1px solid; border-radius:15px;
    }
    window.iptv-tv .synplus-guide .syn-guide-header {
      padding:9px 11px; min-height:31px; border:none;
    }
    window.iptv-tv .synplus-guide .syn-guide-title { font-size:14px; font-weight:760; }
    window.iptv-tv .synplus-guide .syn-guide-muted { font-size:10px; }
    window.iptv-tv .synplus-guide .syn-guide-channel,
    window.iptv-tv .synplus-guide .syn-guide-track { border-radius:6px; }
    window.iptv-tv .synplus-guide .syn-guide-program {
      border-radius:9px; margin:2px 1px; border-width:1px;
    }
    window.iptv-tv .synplus-guide .syn-guide-footer { padding:3px 9px; }
    window.iptv-tv .synplus-guide .syn-guide-axis { min-height:31px; }
    window.iptv-tv .synplus-header { box-shadow:none; border-bottom:0; min-height:37px; }
    window.iptv-tv .synplus-header button, window.iptv-tv .synplus-header dropdown > button {
      min-height:28px; border-radius:13px; padding:3px 8px;
    }
    ''' + palette


def install_synplus_layout(window, Gtk, GLib, video_column, base, brand, hidden_header_controls):
    """Recompose EXISTING GTK widgets before GTK/GLArea is realized.

    The player overlay is never recreated. EPG keeps its original scrolling,
    XMLTV paint, program gestures, recording context menus and programme data.
    """
    if getattr(window, '_synplus_ui', False):
        return
    window._synplus_ui = True
    window.set_title("SYN-Plus · Alfa 1")
    window.set_default_size(1440, 960)
    window.add_css_class('synplus-window')
    window.header.add_css_class('synplus-header')

    # 3 zones: 138px navigation, existing 315px channel browser, player + EPG.
    workbench = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    workbench.add_css_class('synplus-workbench')
    workbench.set_hexpand(True)
    workbench.set_vexpand(True)
    nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    nav.set_size_request(146, -1)
    nav.add_css_class('synplus-nav')
    window._synplus_nav = nav
    base.remove(window.main_stack)
    workbench.append(nav)
    workbench.append(window.main_stack)
    base.append(workbench)

    # Move existing, theme-switching SYN wordmark out of channel list.
    window.sidebar.remove(window._syn_brand_band)
    window._syn_brand_band_spacer.set_size_request(-1, 77)
    window.syn_wordmark.set_size_request(126, 60)
    window.syn_wordmark.set_margin_start(6)
    window.syn_wordmark.set_margin_top(4)
    window._syn_brand_band.add_css_class('synplus-nav-brand')
    nav.append(window._syn_brand_band)
    plus_mark = Gtk.Label(label='P L U S', xalign=0)
    plus_mark.add_css_class('synplus-plus-mark')
    plus_mark.set_margin_start(17)
    plus_mark.set_margin_bottom(12)
    nav.append(plus_mark)
    window.sidebar.add_css_class('synplus-sidebar')
    window.paned.set_position(315)
    window._saved_paned_position = 315
    window.sidebar.set_size_request(280, -1)

    # The HeaderBar still owns GNOME/Wayland window controls and can drag.
    # Only profile selection, a genuine overflow menu and compact channels remain.
    brand.set_visible(False)
    for widget in hidden_header_controls:
        widget.set_visible(False)
    window.profile_picker.set_visible(True)

    more = Gtk.MenuButton()
    more.set_icon_name('view-more-symbolic')
    more.set_tooltip_text('Más acciones de SYN')
    menu = Gtk.Popover()
    menu_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    menu_content.set_margin_top(7)
    menu_content.set_margin_bottom(7)
    menu_content.set_margin_start(7)
    menu_content.set_margin_end(7)
    more_items = (
        ('Añadir fuente IPTV', window.show_welcome),
        ('Abrir lista M3U', window.open_playlist),
        ('Actualizar canales', window.load_channels),
        ('Mostrar / ocultar guía EPG', window.show_guide),
        ('Abrir biblioteca', lambda: window._syn_portal_show('home')),
        ('Cambiar logo del canal', window.choose_custom_logo),
        ('Capturar imagen PNG', window._syn_capture_take),
        ('Información de reproducción', window.show_info),
        ('Ajustes', window.open_settings),
    )
    for label, handler in more_items:
        action = Gtk.Button(label=label)
        action.set_halign(Gtk.Align.FILL)
        action.add_css_class('flat')
        action.connect('clicked', lambda _btn, h=handler: (menu.popdown(), h()))
        menu_content.append(action)
    menu.set_child(menu_content)
    more.set_popover(menu)
    window.header.pack_end(more)
    window._synplus_more = more

    buttons = {}

    def _select(name):
        for key, btn in buttons.items():
            if key == name:
                btn.add_css_class('synplus-current')
            else:
                btn.remove_css_class('synplus-current')

    def _tv(*_, favorites=False):
        window._syn_portal_hide()
        if window.dvr_view.get_visible():
            window.toggle_dvr_view()
        window.favs.set_active(bool(favorites))
        if not window.fullscreen_mode:
            if window.guide_open:
                window.set_guide_open(False)
            window.set_guide_open(True)
        _select('favoritos' if favorites else 'tv')

    def _guide(*_):
        _tv()
        if not window.guide_open:
            window.set_guide_open(True)
        window.guide_surface.grab_focus()
        _select('guia')

    def _portal(mode, section):
        window._syn_portal_show(mode)
        _select(section)

    def _dvr(*_):
        window._syn_portal_hide()
        if not window.dvr_view.get_visible():
            window.toggle_dvr_view()
        _select('dvr')

    entries = [
        ('tv', 'TV', 'video-display-symbolic', lambda: _tv()),
        ('guia', 'Guía', 'view-list-symbolic', lambda: _guide()),
        ('series', 'Series', 'folder-videos-symbolic', lambda: _portal('series','series')),
        ('cine', 'Cine', 'video-x-generic-symbolic', lambda: _portal('movies','cine')),
        ('dvr', 'DVR', 'media-record-symbolic', lambda: _dvr()),
        ('favoritos', 'Favoritos', 'emblem-favorite-symbolic', lambda: _tv(favorites=True)),
        ('ajustes', 'Ajustes', 'emblem-system-symbolic', window.open_settings),
    ]
    for idx, (key, label, icon_name, callback) in enumerate(entries):
        if idx == 5:
            nav.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        button = Gtk.Button()
        button.set_halign(Gtk.Align.FILL)
        button.set_hexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pictogram = Gtk.Image.new_from_icon_name(icon_name)
        pictogram.set_pixel_size(16)
        content.append(pictogram)
        caption = Gtk.Label(label=label, xalign=0)
        caption.set_hexpand(True)
        content.append(caption)
        button.set_child(content)
        button.add_css_class('synplus-nav-button')
        button.connect('clicked', lambda _button, cb=callback: cb())
        nav.append(button)
        buttons[key] = button
    _select('tv')
    window._synplus_nav_buttons = buttons
    nav_spacer = Gtk.Box()
    nav_spacer.set_vexpand(True)
    nav.append(nav_spacer)
    info = Gtk.Label(label='SYN-Plus · alfa 1', xalign=0)
    info.add_css_class('synplus-nav-note')
    nav.append(info)

    # Existing video stays inside the Gtk.Overlay. We only move the overlay
    # before the first realization and overlay an unobtrusive playback chrome.
    video_column.remove(window.overlay)
    frame = Gtk.AspectFrame.new(0.5, 0.5, 16 / 9, False)
    frame.set_hexpand(True)
    frame.set_vexpand(True)
    frame.set_size_request(-1, 220)
    frame.add_css_class('synplus-visual-player')
    frame.set_child(window.overlay)
    video_column.prepend(frame)
    window._synplus_player_frame = frame

    chrome = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    chrome.add_css_class('synplus-video-chrome')
    chrome.set_valign(Gtk.Align.END)
    chrome.set_halign(Gtk.Align.FILL)
    chrome.set_hexpand(True)
    chrome.set_vexpand(False)
    for child in (window.details, window.program_label, window.toolbar):
        video_column.remove(child)
        chrome.append(child)
    window.overlay.add_overlay(chrome)
    window._synplus_chrome = chrome
    window.footer.set_visible(False)
    window.status.set_visible(False)
    window.play_button.set_label('▶')
    window.play_button.set_tooltip_text('Reproducir canal seleccionado')
    window.pause_button.set_label('⏸')

    # Embedded real EPG, using the exact 1.3.7 XMLTV and recording handlers.
    # A single reparent BEFORE GTK is realized keeps the GLArea stable.
    window.overlay.remove_overlay(window.guide_surface)
    video_column.append(window.guide_surface)
    window.guide_surface.add_css_class('synplus-guide')
    window.guide_surface.set_vexpand(False)
    window.guide_surface.set_size_request(-1, 360)
    window.guide_categories_scroll.set_visible(False)
    window.guide_search.set_visible(False)
    window._guide_header_subtitle.set_visible(False)
    window._synplus_embedded_guide = True
    window._synplus_guide_requested = True
    window._synplus_in_fullscreen = False
    GLib.idle_add(lambda: (window.set_guide_open(True), False)[1])


def adapt(window, width):
    """Responsive version: no features are discarded in small windows."""
    if not getattr(window, '_synplus_ui', False):
        return
    if getattr(window, '_synplus_in_fullscreen', False):
        return
    nav_visible = width >= 850
    window._synplus_nav.set_visible(nav_visible)
    # The legacy HeaderBar supplies full-featured compact channel menu.
    # Keep the menu button accessible even when 3-column layout collapses.
    window.channel_menu.set_visible(width < 1140)
    if window.paned.get_position() and width < 1140 and not window.compact_sidebar:
        window.paned.set_position(0)
    window._synplus_more.set_visible(True)
    # The EPG is user-hideable, and still has a nav affordance at large sizes.
    # At smaller sizes, allow the full-height player to take priority.
    height = window.get_height()
    guide_height = 205 if height < 720 or width < 830 else (275 if height < 900 else 360)
    window.guide_surface.set_size_request(-1, guide_height)


def fullscreen_changed(window, enabled, GLib):
    """Fullscreen is true video fullscreen, not a full-screen 3-zone window."""
    if not getattr(window, '_synplus_ui', False):
        return
    window._synplus_in_fullscreen = bool(enabled)
    window._synplus_nav.set_visible(False if enabled else window.get_width() >= 850)
    window._synplus_chrome.set_visible(not enabled)
    window.guide_surface.set_visible(False)
    window.footer.set_visible(False)
    window.status.set_visible(False)
    if not enabled:
        window._synplus_nav.set_visible(window.get_width() >= 850)
        if not window.guide_open and window._synplus_guide_requested:
            GLib.idle_add(lambda: (window.set_guide_open(True), False)[1])
        elif window.guide_open:
            window.guide_surface.set_visible(True)
