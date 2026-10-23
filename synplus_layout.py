"""SYN Plus 2.0 alpha2.3 — refined overlay and near-borderless video frame.

Preserves the existing Gtk.GLArea, libmpv, DVR, Cast, profile, EPG, and
channel handlers. This file changes placement and presentation, not backends.
"""
from __future__ import annotations
import hashlib
import time
import unicodedata


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
        # Deep enough for white lettering even in the palest GTK palettes.
        epg_colors = ('#437e78', '#755b99', '#466f9e', '#9b7042', '#3b826f', '#936171')
        epg_text = '#ffffff'
    else:
        epg_colors = ('#245d48', '#59317e', '#194c86', '#6a5231', '#266064', '#724653')
        epg_text = '#f9fcfd'
    palette += ''.join(
        f'window.iptv-tv .synplus-guide .syn-guide-program-{n} '
        f'{{ background-color:{tone}; }}\n'
        for n, tone in enumerate(epg_colors)
    )
    palette += ("window.iptv-tv.synplus-window .synplus-guide .syn-guide-program label, "
                "window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-name, "
                "window.iptv-tv.synplus-window .synplus-guide .syn-guide-time "
                "{ color:#ffffff; text-shadow:0 1px 2px rgba(0,0,0,.2); }")
    return '''
    /* SYN-Plus 2.0: visual workbench of the approved 2026-10-23 mockups. */
    window.iptv-tv .synplus-workbench { border-spacing:0; }
    window.iptv-tv .synplus-nav {
      padding:10px 9px 13px 9px; border-right:1px solid;
    }
    window.iptv-tv .synplus-nav-brand { margin:6px 0 18px 0; }
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
    /* A longer, continuous tonal ramp; no sudden black foot at the bottom. */
    window.iptv-tv .synplus-video-chrome {
      background-image:linear-gradient(to bottom,
          rgba(5,11,17,.015) 0%,
          rgba(5,11,17,.045) 20%,
          rgba(5,11,17,.105) 40%,
          rgba(5,11,17,.19) 60%,
          rgba(5,11,17,.30) 80%,
          rgba(5,11,17,.42) 100%);
      color:#f6f8fa; padding:76px 11px 7px 11px;
    }
    /* Small player: keep the same steady ramp without covering all the image. */
    window.iptv-tv.synplus-window.synplus-compact-player .synplus-video-chrome {
      padding-top:53px;
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
    ''' + palette + avatar_css() + '''
    window.iptv-tv.synplus-window .synplus-nav { min-width:138px; }
    window.iptv-tv.synplus-window .synplus-guide-full {
      margin:0; border:0; border-radius:0; background-color:@window_bg_color;
    }
    window.iptv-tv.synplus-window .synplus-visual-player {
      border-radius:6px; margin:2px 4px 0 4px;
      border:0; box-shadow:none; }
    window.iptv-tv.synplus-window .synplus-visual-player .iptv-video {
      border:0; box-shadow:none; }
    window.iptv-tv.synplus-window.synplus-pure-fullscreen .synplus-visual-player {
      border-radius:0; margin:0; padding:0; }
    window.iptv-tv.synplus-window.synplus-pure-fullscreen .synplus-video-chrome {
      background-image:none; padding:0; }
    window.iptv-tv.synplus-window .synplus-video-chrome { border-radius:0 0 5px 5px; }
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-program { border-radius:10px; }
    window.iptv-tv.synplus-window .synplus-avatar {
      min-height:38px; min-width:38px; border-radius:14px; padding:4px;
      background-image:none; border:1px solid alpha(@window_fg_color,.12);
    }
    window.iptv-tv.synplus-window .synplus-avatar image { -gtk-icon-size:22px; }
    window.synplus-welcome .syn-welcome-bg { background-image:none;
      background-color:@window_bg_color; color:@window_fg_color; }
    window.synplus-welcome .syn-welcome-title {
      color:@window_fg_color; font-size:29px; font-weight:780; }
    window.synplus-welcome .syn-welcome-subtitle,
    window.synplus-welcome .syn-welcome-muted { color:@window_fg_color; opacity:.72; }
    window.synplus-welcome .syn-welcome-card {
      background-image:none; background-color:alpha(@window_fg_color,.045);
      border:1px solid alpha(@window_fg_color,.11); border-radius:18px;
      box-shadow:none; padding:14px; }
    window.synplus-welcome .syn-welcome-card:hover {
      background-color:alpha(@accent_color,.12); border-color:alpha(@accent_color,.4); }
    window.synplus-welcome .syn-welcome-card-title { font-size:16px; }
    window.synplus-welcome .syn-welcome-body { background-color:transparent; }
    window.synplus-welcome .syn-welcome-cta { border-radius:14px; min-height:40px; }
    '''


def install_synplus_layout(window, Gtk, GLib, video_column, base, brand, hidden_header_controls):
    """Recompose EXISTING GTK widgets before GTK/GLArea is realized.

    The player overlay is never recreated. EPG keeps its original scrolling,
    XMLTV paint, program gestures, recording context menus and programme data.
    """
    if getattr(window, '_synplus_ui', False):
        return
    window._synplus_ui = True
    window._synplus_gtk = Gtk
    window.set_title("SYN Plus · Alfa 2.3")
    window.set_default_size(1370, 920)
    window.add_css_class('synplus-window')
    window.header.add_css_class('synplus-header')

    # 3 zones: fixed 138px nav, existing 315px channel browser, player + EPG.
    workbench = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    workbench.add_css_class('synplus-workbench')
    workbench.set_hexpand(True)
    workbench.set_vexpand(True)
    nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    nav.set_size_request(138, -1)
    nav.set_hexpand(False)
    nav.set_halign(Gtk.Align.START)
    nav.add_css_class('synplus-nav')
    window._synplus_nav = nav
    base.remove(window.main_stack)
    workbench.append(nav)
    workbench.append(window.main_stack)
    base.append(workbench)

    # Move existing, theme-switching SYN wordmark out of channel list.
    window.sidebar.remove(window._syn_brand_band)
    window._syn_brand_band_spacer.set_size_request(-1, 65)
    window.syn_wordmark.set_size_request(103, 50)
    window.syn_wordmark.set_margin_start(2)
    window.syn_wordmark.set_margin_top(4)
    window._syn_brand_band.add_css_class('synplus-nav-brand')
    nav.append(window._syn_brand_band)
    # The original SYN wordmark is the sole brand: no extra subtitle.
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
    # No duplicates: the rail already contains Guide, Library and Settings.
    more_items = (
        ('Actualizar canales', window.load_channels),
        ('Abrir archivo M3U', window.open_playlist),
        ('Personalizar logo del canal', window.choose_custom_logo),
        ('Capturar PNG', window._syn_capture_take),
        ('Información de reproducción', window.show_info),
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
        set_guide_mode(window, GLib, False)
        window._syn_portal_hide()
        if window.dvr_view.get_visible():
            window.toggle_dvr_view()
        window.favs.set_active(bool(favorites))
        if not window.fullscreen_mode and not window.guide_open:
            window.set_guide_open(True)
        _select('favoritos' if favorites else 'tv')

    def _guide(*_):
        window._syn_portal_hide()
        if window.dvr_view.get_visible():
            window.toggle_dvr_view()
        if not window.guide_open:
            window.set_guide_open(True)
        set_guide_mode(window, GLib, True)
        _select('guia')

    def _portal(mode, section):
        set_guide_mode(window, GLib, False)
        window._syn_portal_show(mode)
        _select(section)

    def _dvr(*_):
        set_guide_mode(window, GLib, False)
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
    # Existing fallback art uses a Cairo drawing callback. Override only this
    # instance, so a genuine provider logo still renders through the stable path.
    window._draw_channel_logo_or_art = lambda area,cr,w,h: draw_classic_refined_pill(window,area,cr,w,h)
    nav_spacer = Gtk.Box()
    nav_spacer.set_vexpand(True)
    nav.append(nav_spacer)
    # Profile avatars are deterministic: same ID, same icon, same colours.
    profile_button = Gtk.MenuButton()
    profile_button.add_css_class('synplus-avatar')
    profile_button.set_tooltip_text('Perfiles · cambiar o añadir')
    avatar_image = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
    avatar_image.set_pixel_size(22)
    profile_button.set_child(avatar_image)
    profile_menu = Gtk.Popover()
    profile_button.set_popover(profile_menu)
    nav.append(profile_button)
    window._synplus_avatar_button = profile_button
    window._synplus_avatar_picture = avatar_image
    window._synplus_avatar_menu = profile_menu
    rebuild_profile_menu(window, Gtk)
    profile_button.connect('notify::active', lambda btn, *_:
        rebuild_profile_menu(window, Gtk) if btn.get_active() else None)
    window.profile_picker.connect('notify::selected', lambda *_: refresh_avatar(window))
    refresh_avatar(window)
    add_profile = Gtk.Button(label='+  Añadir')
    add_profile.set_tooltip_text('Añadir perfil IPTV')
    add_profile.add_css_class('synplus-nav-button')
    add_profile.connect('clicked', lambda *_: window.show_welcome())
    nav.append(add_profile)
    info = Gtk.Label(label='ALFA 2.3', xalign=0)
    info.add_css_class('synplus-nav-note')
    nav.append(info)

    # Existing video stays inside the Gtk.Overlay. We only move the overlay
    # before the first realization and overlay an unobtrusive playback chrome.
    video_column.remove(window.overlay)
    frame = Gtk.AspectFrame.new(0.5, 0.5, 16 / 9, False)
    # GTK AspectFrame constrains the CHILD, not the frame. Normal-window
    # geometry can be wider than 16:9; the ratio follows each allocation.
    # On fullscreen the frame expands to fill the display without reparenting
    # Gtk.GLArea or recreating the libmpv OpenGL context.
    frame.set_hexpand(False)
    frame.set_vexpand(False)
    frame.set_halign(Gtk.Align.CENTER)
    frame.set_valign(Gtk.Align.START)
    frame.set_size_request(-1, -1)
    frame.add_css_class('synplus-visual-player')
    frame.set_child(window.overlay)
    # The frame is an UNMEASURED OVERLAY. Its calculated (w,h) request will
    # not become the MINIMUM WINDOW SIZE, so the GTK window is freely resizable.
    # The base child provides the flexible space remaining above the EPG.
    video_host = Gtk.Overlay()
    video_host.add_css_class('synplus-player-host')
    video_host.set_hexpand(True)
    video_host.set_vexpand(True)
    blank_host = Gtk.Box()
    blank_host.set_hexpand(True)
    blank_host.set_vexpand(True)
    video_host.set_child(blank_host)
    video_host.add_overlay(frame)
    video_host.set_measure_overlay(frame, False)
    video_column.prepend(video_host)
    window._synplus_player_frame = frame
    window._synplus_player_host = video_host
    window._synplus_video_column = video_column
    window._synplus_requested_video = None
    # SYN 1.3.7's one-shot startup 16:9 WINDOW resize is not wanted here:
    # user dimensions must remain free from the very first launch.
    window._syn_startup_ratio_pending = False

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
    # Crossfade of all playback text and controls without modifying video GLArea.
    window.overlay.remove_overlay(chrome)
    reveal = Gtk.Revealer()
    reveal.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
    reveal.set_transition_duration(210)
    # Windowed chrome starts hidden; pointer hover/click is the ONLY reveal.
    reveal.set_reveal_child(False)
    reveal.set_halign(Gtk.Align.FILL)
    reveal.set_valign(Gtk.Align.END)
    reveal.set_child(chrome)
    window.overlay.add_overlay(reveal)
    window._synplus_chrome_reveal = reveal
    motion = Gtk.EventControllerMotion.new()
    motion.connect('enter', lambda *_: reveal_controls(window, True))
    motion.connect('motion', lambda *_: reveal_controls(window, True))
    motion.connect('leave', lambda *_: reveal_controls(window, False))
    window.overlay.add_controller(motion)
    window._synplus_mouse_over_video = False
    window._synplus_reveal_until = 0.0
    GLib.timeout_add(300, lambda: poll_chrome(window))
    window.footer.set_visible(False)
    window.status.set_visible(False)
    # The channel list starts playback directly. Keep the underlying handler
    # for compatibility but remove the redundant Play button from the toolbar.
    if window.play_button.get_parent() == window.strip:
        window.strip.remove(window.play_button)
    window.play_button.set_visible(False)
    window.pause_button.set_label('⏸')

    # Embedded real EPG, using the exact 1.3.7 XMLTV and recording handlers.
    # A single reparent BEFORE GTK is realized keeps the GLArea stable.
    window.overlay.remove_overlay(window.guide_surface)
    video_column.append(window.guide_surface)
    window.guide_surface.add_css_class('synplus-guide')
    window.guide_surface.set_vexpand(False)
    window.guide_surface.set_size_request(-1, 340)
    window._synplus_guide_home = video_column
    window._synplus_full_guide = False
    window.guide_categories_scroll.set_visible(False)
    window.guide_search.set_visible(False)
    window._guide_header_subtitle.set_visible(False)
    window._synplus_embedded_guide = True
    window._synplus_guide_requested = True
    window._synplus_in_fullscreen = False
    # Main content navigates between an embedded 3–5-row EPG and full guide.
    window._synplus_open_full_guide = _guide
    # Height-only resizes and dragging the channel divider must also resize
    # the player; SYN's pre-existing responsive timer tracks window width.
    def _poll_geometry():
        if window.get_root() is None:
            return True  # not mapped yet; wait for the normal GTK allocation
        if not getattr(window,'_synplus_in_fullscreen',False):
            adapt(window, window.get_width())
        return True
    window._synplus_geometry_timer = GLib.timeout_add(220, _poll_geometry)
    GLib.idle_add(lambda: (window.set_guide_open(True), False)[1])


def player_geometry(region_width, region_height, guide_height, horizontal_margin=24,
                    vertical_margin=28):
    """Fill available horizontal space, without ever becoming taller than 16:9.

    16 is the baseline width and 9 is the MAXIMUM proportional height. Resizing
    a shallow window can produce a wide cinematic frame (21:9, 32:9, etc.).
    The underlying MPV render preserves the source's own pixel aspect ratio;
    video content is never stretched just to fill the frame.
    """
    usable_w = max(0, int(region_width) - int(horizontal_margin))
    usable_h = max(0, int(region_height) - int(guide_height) - int(vertical_margin))
    if usable_w < 16 or usable_h < 16:
        return None
    return (usable_w, min(usable_h, (usable_w * 9) // 16))


def adapt(window, width):
    """Fixed 138px navigation, flexible panoramic player, 3–5 EPG rows."""
    if not getattr(window, '_synplus_ui', False) or getattr(window, '_synplus_in_fullscreen', False):
        return
    window._synplus_nav.set_visible(True)
    window._synplus_nav.set_size_request(138, -1)
    window.channel_menu.set_visible(width < 1140)
    window._synplus_more.set_visible(True)
    full_guide = getattr(window, '_synplus_full_guide', False)
    if not full_guide:
        rows = 3 if window.get_height() < 850 else (4 if window.get_height() < 1080 else 5)
        window._synplus_rows = rows
        # Existing EPG renderer (programmes, click-to-record, scroll) remains.
        guide_h = 70 * rows + 119
        if getattr(window, '_synplus_guide_height',None) != guide_h:
            window._synplus_guide_height=guide_h
            window.guide_surface.set_size_request(-1, guide_h)
            window.guide_tracks_scroll.set_min_content_height(70 * rows)
    else:
        guide_h = 0

    host = getattr(window, '_synplus_player_host', None)
    frame = getattr(window, '_synplus_player_frame', None)
    if host is not None and frame is not None:
        # The host is sized by Gtk.Box AFTER reserving EPG space. Its own
        # measurement EXCLUDES the frame, so its dimensions remain flexible.
        cw, ch = host.get_width(), host.get_height()
        if cw > 0 and ch > 0 and not full_guide:
            # Just four pixels of visual breathing room around the video,
            # instead of the thick insets introduced in the previous alpha.
            wanted = player_geometry(cw, ch, 0, horizontal_margin=8, vertical_margin=4)
            if wanted and wanted != getattr(window,'_synplus_requested_video',None):
                # AspectFrame must follow the actual requested frame ratio.
                # Leaving this fixed at 16:9 would introduce a dead letterbox
                # inside the widget when the user made the window panoramic.
                frame.set_ratio(wanted[0] / wanted[1])
                frame.set_size_request(*wanted)
                window._synplus_requested_video=wanted
    player_w = getattr(window,'_synplus_requested_video',(0,0))
    displayed_w = player_w[0] if player_w else 0
    window._synplus_compact = width < 1260 or (0 < displayed_w < 690)
    # A slightly shorter ramp for compact windows: gradient shape stays smooth.
    if window._synplus_compact:
        window.add_css_class('synplus-compact-player')
    else:
        window.remove_css_class('synplus-compact-player')
    poll_chrome(window)


def fullscreen_changed(window, enabled, GLib):
    """Pure transmission fullscreen, without touching the realized GLArea.

    The original SYN fullscreen handler already hides the GNOME header and
    channel sidebar. SYN Plus must ALSO make its own frame fill the view,
    hide its independent navigation and EPG, and remove the windowed margins.
    """
    if not getattr(window, '_synplus_ui', False):
        return
    enabled = bool(enabled)
    if getattr(window, '_synplus_in_fullscreen', False) == enabled:
        return
    frame = window._synplus_player_frame
    align = window._synplus_gtk.Align
    if enabled:
        window._synplus_pre_full_guide = bool(window._synplus_full_guide)
        # A full-page EPG is an overlay of main_stack; remove it BEFORE the
        # fullscreen player is shown or it may cover the transmission.
        if window._synplus_full_guide:
            set_guide_mode(window, GLib, False)
        window._synplus_in_fullscreen = True
        window._synplus_nav.set_visible(False)
        window._synplus_more.set_visible(False)
        window.guide_surface.set_visible(False)
        # The stable fullscreen handler handles its own channel sidebar,
        # but SYN Plus has an independent host and guide outside the video.
        # Keep them hidden while the window itself is fullscreen.
        window._synplus_chrome_reveal.set_reveal_child(False)
        window._synplus_chrome_reveal.set_visible(False)
        window._synplus_chrome.set_visible(False)
        window.footer.set_visible(False)
        window.status.set_visible(False)
        window.add_css_class('synplus-pure-fullscreen')
        # Gtk.AspectFrame spans the screen, its CHILD is video-shaped and
        # GTK/libmpv letterbox the source if the physical screen isn't 16:9.
        # No toolbar/rail/channel-list/EPG occupies space.
        frame.set_size_request(-1, -1)
        frame.set_ratio(16 / 9)
        frame.set_halign(align.FILL)
        frame.set_valign(align.FILL)
        frame.set_hexpand(True)
        frame.set_vexpand(True)
        window._synplus_requested_video = None
        GLib.idle_add(window._queue_video_frame)
        return

    # Exit fullscreen: return the frame to a naturally sized normal-window
    # workbench; recompute from the current window dimensions on next GTK pass.
    window._synplus_in_fullscreen = False
    window.remove_css_class('synplus-pure-fullscreen')
    frame.set_size_request(-1, -1)
    frame.set_hexpand(False)
    frame.set_vexpand(False)
    frame.set_halign(align.CENTER)
    frame.set_valign(align.START)
    window._synplus_requested_video = None
    window._synplus_nav.set_visible(True)
    window._synplus_more.set_visible(True)
    window._synplus_chrome.set_visible(True)
    window._synplus_chrome_reveal.set_visible(True)
    if not window.guide_open and window._synplus_guide_requested:
        GLib.idle_add(lambda: (window.set_guide_open(True), False)[1])
    elif window.guide_open:
        window.guide_surface.set_visible(True)
    if getattr(window, '_synplus_pre_full_guide', False):
        GLib.idle_add(lambda: (set_guide_mode(window, GLib, True), False)[1])
    window._synplus_pre_full_guide = False
    # Layout is reported only after the compositor has sent its allocation.
    GLib.timeout_add(80, lambda: (adapt(window, window.get_width()), False)[1])
    GLib.idle_add(window._queue_video_frame)


# Icons from the desktop's existing symbolic icon theme: no downloads or
# external fonts, and the icon remains monochrome over its assigned colour.
PROFILE_ICONS = (
    'starred-symbolic', 'weather-clear-symbolic', 'media-playback-start-symbolic',
    'network-wireless-symbolic', 'camera-photo-symbolic', 'audio-x-generic-symbolic',
    'folder-videos-symbolic', 'applications-games-symbolic', 'emblem-favorite-symbolic',
    'view-grid-symbolic', 'mail-unread-symbolic', 'weather-overcast-symbolic',
    'media-optical-symbolic', 'face-smile-symbolic', 'preferences-desktop-theme-symbolic',
)
PROFILE_COLORS = (
    '#d9bfaa', '#357b75', '#becdd3', '#dcaa73', '#505d84',
    '#b5cba9', '#80677b', '#e6cc8b', '#60799a', '#a9c6c1',
    '#967e66', '#d8ada7', '#566f67', '#d4c5da', '#c1b99c',
)


def _rgb(hexval):
    c=hexval.lstrip('#')
    return tuple(int(c[i:i+2],16) / 255.0 for i in (0,2,4))


def _contrast(hexval):
    r,g,b = _rgb(hexval)
    def lin(v): return v/12.92 if v < .04045 else ((v+.055)/1.055)**2.4
    luminance = .2126*lin(r)+.7152*lin(g)+.0722*lin(b)
    return '#121619' if luminance >= .36 else '#ffffff'


def avatar_style(profile_id):
    digest=hashlib.sha256(str(profile_id).encode('utf-8')).digest()
    # Independent positions, stable across machines and launches.
    idx=digest[0] % len(PROFILE_ICONS)
    color=PROFILE_COLORS[digest[1] % len(PROFILE_COLORS)]
    return idx, color, _contrast(color)


def avatar_css():
    return ''.join(
        'window.iptv-tv.synplus-window .synplus-avatar-c%d { '
        'background-color:%s; color:%s; } '
        'window.iptv-tv.synplus-window .synplus-avatar-c%d image { color:%s; }\n' %
        (i,color,_contrast(color),i,_contrast(color))
        for i,color in enumerate(PROFILE_COLORS)
    )


def refresh_avatar(window):
    btn=getattr(window,'_synplus_avatar_button',None)
    if btn is None: return
    for i in range(len(PROFILE_COLORS)):
        btn.remove_css_class('synplus-avatar-c%d' % i)
    p=getattr(window, 'profile', {}) or {}
    i,color,ink=avatar_style(p.get('id','synplus'))
    digest=hashlib.sha256(str(p.get('id','synplus')).encode('utf-8')).digest()
    btn.add_css_class('synplus-avatar-c%d' % (digest[1] % len(PROFILE_COLORS)))
    window._synplus_avatar_picture.set_from_icon_name(PROFILE_ICONS[i])
    btn.set_tooltip_text('Perfiles · %s' % p.get('name','Mi televisión'))


def rebuild_profile_menu(window, Gtk):
    pop=window._synplus_avatar_menu
    old=pop.get_child()
    if old is not None: pop.set_child(None)
    root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
    for margin in ('top','bottom','start','end'):
        getattr(root,'set_margin_'+margin)(10)
    title=Gtk.Label(label='Perfiles',xalign=0)
    title.add_css_class('heading')
    root.append(title)
    for i,p in enumerate(window.cfg.get('profiles',[])):
        name=p.get('name','Sin nombre')
        btn=Gtk.Button(label=('✓  ' if p.get('id')==window.profile.get('id') else '    ')+name)
        btn.add_css_class('flat')
        btn.connect('clicked',lambda _b,index=i:(pop.popdown(),window.profile_picker.set_selected(index)))
        root.append(btn)
    root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
    add=Gtk.Button(label='+  Añadir perfil')
    add.add_css_class('suggested-action')
    add.connect('clicked',lambda *_:(pop.popdown(),window.show_welcome()))
    root.append(add)
    pop.set_child(root)


def set_guide_mode(window, GLib, full):
    """Move the existing EPG widget, never GLArea, to fill all but nav rail."""
    if not getattr(window,'_synplus_embedded_guide',False): return
    full=bool(full)
    if full == getattr(window,'_synplus_full_guide',False): return
    epg=window.guide_surface
    home=window._synplus_guide_home
    if full:
        if epg.get_parent() == home:
            home.remove(epg)
        window.main_stack.add_overlay(epg)
        window.main_stack.set_clip_overlay(epg, True)
        epg.set_vexpand(True)
        epg.set_valign(window._synplus_gtk.Align.FILL)
        epg.set_halign(window._synplus_gtk.Align.FILL)
        epg.set_size_request(-1,-1)
        epg.add_css_class('synplus-guide-full')
        window.guide_categories_scroll.set_visible(True)
        window.guide_search.set_visible(True)
    else:
        if epg.get_parent() == window.main_stack:
            window.main_stack.remove_overlay(epg)
        home.append(epg)
        epg.set_vexpand(False)
        epg.set_size_request(-1,70*getattr(window,'_synplus_rows',3)+119)
        epg.remove_css_class('synplus-guide-full')
        window.guide_categories_scroll.set_visible(False)
        window.guide_search.set_visible(False)
    window._synplus_full_guide=full
    epg.set_visible(True)
    def _redraw():
        if window.guide_open:
            window._guide_adapt_width()
            window.guide_render_rows()
        return False
    GLib.timeout_add(90,_redraw)


def reveal_controls(window, entering=True):
    """Hover reveals immediately. Leaving hides immediately, at any size."""
    if getattr(window,'_synplus_in_fullscreen',False): return
    window._synplus_mouse_over_video=bool(entering)
    if not entering:
        # Clear the click hold as well: once the pointer leaves, the video
        # must not retain a dark control strip for several more seconds.
        window._synplus_reveal_until=0.0
    poll_chrome(window)


def click_controls(window):
    """Show on a direct video click without faking a lasting mouse-enter."""
    if getattr(window,'_synplus_in_fullscreen',False): return
    window._synplus_reveal_until=time.monotonic()+2.0
    poll_chrome(window)


def controls_visible(full, hovering, held_until, now):
    """Pure decision shared by GTK hover/click and offline unit tests."""
    return bool(not full and (hovering or now < held_until))


def poll_chrome(window):
    if not getattr(window,'_synplus_ui',False): return False
    reveal=getattr(window,'_synplus_chrome_reveal',None)
    if reveal is None: return True
    visible=controls_visible(
        getattr(window,'_synplus_in_fullscreen',False),
        getattr(window,'_synplus_mouse_over_video',False),
        getattr(window,'_synplus_reveal_until',0.0),
        time.monotonic())
    reveal.set_reveal_child(visible)
    return True


def show_guide_page(window, GLib):
    cb=getattr(window,'_synplus_open_full_guide',None)
    if cb and not getattr(window,'_synplus_in_fullscreen',False): cb()


# SYN classic refined: exactly the original two-line composition and graphic
# motifs, only the inks are less saturated and the accents less aggressive.
# No visual rebranding; real provider logos still take precedence.
CLASSIC_REFINED_PALETTES = (
    ((.10,.20,.35),(.58,.38,.49),(.79,.66,.44)),
    ((.09,.28,.30),(.64,.42,.35),(.78,.65,.47)),
    ((.29,.19,.39),(.33,.63,.59),(.78,.47,.58)),
    ((.09,.27,.43),(.60,.42,.60),(.78,.66,.46)),
    ((.32,.19,.28),(.66,.45,.35),(.78,.63,.58)),
    ((.16,.28,.24),(.62,.44,.37),(.73,.70,.45)),
    ((.19,.21,.38),(.53,.46,.67),(.50,.70,.77)),
    ((.13,.29,.33),(.66,.44,.51),(.76,.67,.46)),
)


def draw_classic_refined_pill(window, area, cr, width, height):
    """Original SYN fallback collage, with gentle editorial colour grading."""
    if getattr(area, '_syn_pixbuf', None) is not None:
        return window._draw_channel_logo(area, cr, width, height)
    if width <= 0 or height <= 0:
        return
    import math
    from syn_fallback_art import artwork_identity, artwork_lines
    name,group=getattr(area, '_syn_art_id', ('SYN','TV'))
    idx,motif=artwork_identity(name,group)
    bg,shape,sparkle=CLASSIC_REFINED_PALETTES[idx]
    title,subtitle=artwork_lines(name)
    cr.save()
    try:
        cr.scale(width/108.0,height/38.0)
        cr.set_source_rgb(*bg)
        cr.rectangle(0,0,108,38);cr.fill()
        # Keep SYN's recognizable original shapes, softened slightly.
        cr.set_source_rgba(*shape,.82)
        if motif==0:
            cr.arc(100,6,29,0,math.tau);cr.fill()
            cr.set_source_rgba(*sparkle,.75)
            cr.rectangle(87,23,24,7);cr.fill()
        elif motif==1:
            cr.move_to(78,38);cr.line_to(94,0);cr.line_to(108,0)
            cr.line_to(108,38);cr.close_path();cr.fill()
            cr.set_source_rgba(*sparkle,.75)
            cr.arc(104,31,9,0,math.tau);cr.fill()
        elif motif==2:
            cr.rectangle(89,0,8,38);cr.fill()
            cr.set_source_rgba(*sparkle,.75)
            cr.rectangle(99,0,9,38);cr.fill()
        else:
            cr.arc(98,20,22,0,math.tau);cr.fill()
            cr.set_source_rgba(*sparkle,.75)
            cr.arc(98,20,10,0,math.tau);cr.fill()
        cr.set_source_rgba(1,1,1,.25)
        cr.rectangle(6,5,2,28);cr.fill()
        cr.set_source_rgb(1,1,1)
        cr.select_font_face('Sans',0,1)
        cr.set_font_size(9.6 if len(title)<=9 else 7.8)
        cr.move_to(13,17);cr.show_text(title)
        cr.set_source_rgba(1,1,1,.82)
        cr.select_font_face('Sans',0,0)
        cr.set_font_size(6.8 if len(subtitle)<=13 else 5.9)
        cr.move_to(13,29);cr.show_text(subtitle)
    finally:
        cr.restore()
