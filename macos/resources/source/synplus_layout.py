"""SYN 2.0 release — fullscreen EPG fix; startup 16:9, free resize, linked chrome and retro monochrome standby.

Preserves the existing Gtk.GLArea, libmpv, DVR, Cast, profile, EPG, and
channel handlers. This file changes placement and presentation, not backends.
"""
from __future__ import annotations
import hashlib
import os
import sys
import time
import unicodedata
import re
from syn_i18n import translate as tr


def choose_system_scheme(gtk_theme_name='', prefer_dark=False, desktop_preference=''):
    """Pure GNOME/GTK fallback used by native and sandboxed builds.

    A real GNOME selection wins; when unset, respect explicit GTK variants.
    In an ambiguous case let libadwaita follow the portal. Never infer
    the desktop theme from GTK3 palette files.
    """
    if desktop_preference in ('prefer-dark', 'prefer-light'):
        return 'follow-system'
    if prefer_dark or re.search(r'(?:^|[-_:])dark(?:$|[-_:])', str(gtk_theme_name).lower()):
        return 'dark'
    if re.search(r'(?:^|[-_:])light(?:$|[-_:])', str(gtk_theme_name).lower()):
        return 'light'
    return 'follow-system'


def native_system_css():
    """Scoped native-only bridge against GTK USER stylesheets.

    Keeps the host's semantic @window colors and limits priority to SYN's
    workbench/navigation, without changing Flatpak's System appearance.
    """
    if sys.platform == "darwin":
        return ""
    return """
    window.iptv-tv.synplus-window .synplus-workbench {
        background-color:@window_bg_color; color:@window_fg_color;
    }
    window.iptv-tv.synplus-window .synplus-nav {
        background-color:@window_bg_color; color:@window_fg_color;
        border-color:alpha(@window_fg_color,.13);
    }
    """


def cast_popover_css(theme='system', system_dark=False):
    """Strong scoped styling: readable Cast popup even with host GTK USER CSS.

    This CSS is installed separately at USER+4. GTK's popover remains a
    native Wayland popup; its parent is still the original Cast button.
    """
    schemes = {
        'teal': ('#10272c', '#e9f7f4', '#f1a46a'),
        'dark': ('#1b2631', '#f2f5f8', '#76c2c2'),
        'light': ('#ffffff', '#18242e', '#177e79'),
        'nord-dark': ('#303f50', '#e9f0f6', '#88c0d0'),
        'nord-light': ('#ffffff', '#293b4c', '#5e81ac'),
        'gruvbox-dark': ('#37332c', '#f6ead6', '#d79921'),
        'gruvbox-light': ('#fffae6', '#3c3836', '#458588'),
    }
    if theme == 'system':
        # macOS GTK USER themes may give an unexpected foreground for symbolic
        # @window colors in detached popovers. Use actual Adwaita color scheme.
        cast_bg, cast_fg, cast_accent = (
            ('#1b2631', '#f2f5f8', '#76c2c2') if system_dark
            else ('#ffffff', '#172b36', '#166c70'))
    else:
        cast_bg, cast_fg, cast_accent = schemes.get(
            theme, ('#ffffff', '#172b36', '#166c70'))
    if sys.platform == 'darwin':
        from syn_macos_theme import accent_color
        cast_bg = '#1C1C1E' if system_dark else '#FFFFFF'
        cast_fg = '#F5F5F7' if system_dark else '#1C1C1E'
        cast_accent = accent_color(system_dark)
    return f"""
    popover.syn-cast-popover > contents {{
        background-image:none; background-color:{cast_bg}; color:{cast_fg};
        border:1px solid alpha({cast_fg},.18); border-radius:14px;
        box-shadow:0 10px 28px rgba(0,0,0,.24);
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel,
    popover.syn-cast-popover > contents box.syn-cast-panel label,
    popover.syn-cast-popover > contents box.syn-cast-panel label.heading {{
        color:{cast_fg}; background-color:transparent;
        opacity:1; text-shadow:none;
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel button.syn-cast-action {{
        background-image:none; background-color:alpha({cast_fg},.085);
        color:{cast_fg}; border:1px solid alpha({cast_fg},.16);
        border-radius:10px; box-shadow:none; min-height:30px;
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel button.syn-cast-action:hover {{
        background-color:alpha({cast_accent},.20);
        border-color:alpha({cast_accent},.44);
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel button.syn-cast-action label {{
        color:{cast_fg}; opacity:1;
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel spinbutton.syn-cast-numeric,
    popover.syn-cast-popover > contents box.syn-cast-panel spinbutton.syn-cast-numeric text {{
        color:{cast_fg}; background-color:alpha({cast_fg},.045);
        border-color:alpha({cast_fg},.16);
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel spinbutton.syn-cast-numeric button {{
        color:{cast_fg}; background-image:none;
        background-color:alpha({cast_fg},.075);
        border-color:alpha({cast_fg},.14);
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel scale highlight {{
        background-color:{cast_accent};
    }}
    /* SYN_MAC_ALPHA53_CAST_CONTRASTE: etiquetas y escalas legibles en claros. */
    popover.syn-cast-popover > contents box.syn-cast-panel scale,
    popover.syn-cast-popover > contents box.syn-cast-panel scale marks mark label,
    popover.syn-cast-popover > contents box.syn-cast-panel spinbutton text,
    popover.syn-cast-popover > contents box.syn-cast-panel spinbutton button,
    popover.syn-cast-popover > contents box.syn-cast-panel button.syn-cast-action label {{
        color:{cast_fg}; opacity:1; text-shadow:none;
    }}
    popover.syn-cast-popover > contents box.syn-cast-panel scale trough {{
        background-color:alpha({cast_fg},.14);
        border-color:alpha({cast_fg},.20);
    }}
    """


def welcome_light_css(theme='system', system_dark=False):
    """Isolated readable first-run palette for GTK4 welcome dialog on LIGHT desktops.

    Covers every welcome subwidget, including buttons/icons and form fields.
    The provider using this CSS is scoped to ``window.synplus-welcome`` and
    installed at USER+5 so host GTK/Yaru CSS cannot undo the dialog contrast.
    Dark schemes deliberately return empty CSS and remain unchanged.
    """
    light_schemes = {
        #               background  foreground  muted       card        stroke      hover       accent      button_fg
        'system':       ('#f6f9f8', '#183b39', '#405f5c', '#ffffff', '#c3d9d3', '#e3f2ed', '#236961', '#ffffff'),
        'light':        ('#f1f8f6', '#17413b', '#43645e', '#ffffff', '#bfdcd1', '#ddf1eb', '#177e79', '#ffffff'),
        'nord-light':   ('#eceff4', '#293b4c', '#455c70', '#ffffff', '#c7d1dc', '#dae6f0', '#416a93', '#ffffff'),
        'gruvbox-light':('#fbf1c7', '#3c3836', '#625a4b', '#fff9e9', '#d5c8aa', '#f0e5cb', '#346a68', '#ffffff'),
    }
    if theme == 'system' and system_dark:
        return ''
    if theme not in light_schemes:
        return ''
    bg, fg, muted, card, stroke, hover, accent, accent_fg = light_schemes[theme]
    return f"""
    /* SYN 2.0.4: welcome is a separate Gtk.Window, not the player window.
       Never allow dark legacy .syn-welcome-* styles to wash out light text. */
    window.synplus-welcome,
    window.synplus-welcome .syn-welcome-bg,
    window.synplus-welcome .syn-welcome-hero,
    window.synplus-welcome .syn-welcome-body,
    window.synplus-welcome scrolledwindow,
    window.synplus-welcome viewport {{
        background-image:none; background-color:{bg}; color:{fg};
    }}
    window.synplus-welcome label,
    window.synplus-welcome .syn-welcome-bg label,
    window.synplus-welcome .syn-welcome-bg image,
    window.synplus-welcome .syn-welcome-body label,
    window.synplus-welcome .syn-welcome-kicker,
    window.synplus-welcome .syn-welcome-title,
    window.synplus-welcome .syn-welcome-card-title,
    window.synplus-welcome .syn-welcome-card image {{
        color:{fg}; opacity:1; text-shadow:none;
    }}
    window.synplus-welcome .syn-welcome-subtitle,
    window.synplus-welcome .syn-welcome-card-subtitle,
    window.synplus-welcome .syn-welcome-muted {{
        color:{muted}; opacity:1; text-shadow:none;
    }}
    window.synplus-welcome button.syn-welcome-card {{
        background-image:none; background-color:{card}; color:{fg};
        border:1px solid {stroke}; border-radius:17px;
        box-shadow:none;
    }}
    window.synplus-welcome button.syn-welcome-card:hover,
    window.synplus-welcome button.syn-welcome-card:focus {{
        background-image:none; background-color:{hover};
        border-color:{accent}; color:{fg};
    }}
    window.synplus-welcome .syn-welcome-symbol,
    window.synplus-welcome button.syn-welcome-card image.syn-welcome-symbol {{
        color:{accent}; opacity:1;
    }}
    window.synplus-welcome .syn-welcome-body entry,
    window.synplus-welcome .syn-welcome-body passwordentry,
    window.synplus-welcome .syn-welcome-body entry text,
    window.synplus-welcome .syn-welcome-body passwordentry text {{
        background-image:none; background-color:{card}; color:{fg};
        border-color:{stroke};
    }}
    window.synplus-welcome .syn-welcome-body button:not(.syn-welcome-cta) {{
        background-image:none; background-color:{card}; color:{fg};
        border:1px solid {stroke};
    }}
    window.synplus-welcome .syn-welcome-body button:not(.syn-welcome-cta) image,
    window.synplus-welcome .syn-welcome-body button:not(.syn-welcome-cta) label {{
        color:{fg};
    }}
    window.synplus-welcome button.syn-welcome-cta {{
        background-image:none; background-color:{accent}; color:{accent_fg};
        border:1px solid {accent}; font-weight:800;
    }}
    window.synplus-welcome button.syn-welcome-cta label {{
        color:{accent_fg}; opacity:1;
    }}
    window.synplus-welcome button.syn-welcome-cta:hover {{
        background-image:none; background-color:{accent};
        border-color:{fg};
    }}
    window.synplus-welcome .syn-welcome-body expander,
    window.synplus-welcome .syn-welcome-body expander label {{
        color:{fg};
    }}
    """


def css(theme='system', accent_hex='', system_dark=False):
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
        # Dark rail: blend its surface toward the surrounding background.
        # Keep the channel sidebar untouched (it uses the original nav tone).
        rail_nav = nav
        if theme in ('teal', 'dark', 'nord-dark', 'gruvbox-dark'):
            def mix(a, b, fraction=.43):
                aa = (int(a[i:i+2], 16) for i in (1, 3, 5))
                bb = (int(b[i:i+2], 16) for i in (1, 3, 5))
                return '#' + ''.join(f'{round(x*(1-fraction) + y*fraction):02x}'
                                   for x, y in zip(aa, bb))
            rail_nav = mix(bg, nav)
        palette = f'''
        window.iptv-tv.synplus-window .synplus-video-column {{
            background-color:{bg}; color:{fg}; }}
        window.iptv-tv.synplus-window .synplus-guide .syn-guide-header,
        window.iptv-tv.synplus-window .synplus-guide .syn-guide-axis,
        window.iptv-tv.synplus-window .synplus-guide .syn-guide-footer {{
            background-color:{surface}; color:{fg}; }}
        window.iptv-tv.synplus-window {{ background-color:{bg}; color:{fg}; }}
        window.iptv-tv .synplus-nav {{ background-color:{rail_nav}; color:{fg}; border-color:alpha({fg},.11); }}
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
        window.iptv-tv.synplus-window .synplus-video-column {
            background-color:@window_bg_color; color:@window_fg_color; }
        window.iptv-tv.synplus-window .synplus-guide .syn-guide-header,
        window.iptv-tv.synplus-window .synplus-guide .syn-guide-axis,
        window.iptv-tv.synplus-window .synplus-guide .syn-guide-footer {
            background-color:@window_bg_color; color:@window_fg_color; }
        window.iptv-tv .synplus-nav { background-color: alpha(@window_fg_color,.022);
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
    # Dedicated high-priority Cast styling, unaffected by the video.
    palette += cast_popover_css(theme)
    # Pastillas cromáticas inspiradas por el boceto: estilo, no datos falsos.
    if theme in ('light', 'nord-light', 'gruvbox-light'):
        # Deep enough for white lettering even in the palest GTK palettes.
        epg_colors = ('#437e78', '#755b99', '#466f9e', '#9b7042', '#3b826f', '#936171')
        epg_text = '#ffffff'
    else:
        epg_colors = ('#245d48', '#59317e', '#194c86', '#6a5231', '#266064', '#724653')
        epg_text = '#f9fcfd'
    # Always keep the left rail distinct: a soft accent wash in light themes,
    # and a much quieter one in dark themes. Follow both custom accent and
    # the selected theme; System mode follows Adwaita/GNOME's dark flag.
    rail_is_light = theme in ('light', 'nord-light', 'gruvbox-light') or (theme == 'system' and not system_dark)
    if isinstance(accent_hex, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', accent_hex):
        tint_color = accent_hex
    elif theme in values:
        tint_color = values[theme][5]
    else:
        tint_color = '@accent_color'
    wash = '.08' if rail_is_light else '.035'
    palette += ("window.iptv-tv.synplus-window .synplus-nav { "
                "background-image:linear-gradient(to bottom, "
                f"alpha({tint_color},{wash}), alpha({tint_color},{wash})); "
                "}")
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
    /* Video-shadow is a separate unclickable revealer, but uses the same
       state and duration as the text/buttons. Long, dark, uniform tail:
       high contrast at the bottom without an abrupt black stripe. */
    window.iptv-tv.synplus-window .synplus-video-gradient {
      background-color:transparent;
      background-image:linear-gradient(to bottom,
          rgba(5,8,11,0) 0%,
          rgba(5,8,11,.035) 13%,
          rgba(5,8,11,.10) 29%,
          rgba(5,8,11,.22) 44%,
          rgba(5,8,11,.39) 62%,
          rgba(5,8,11,.58) 80%,
          rgba(5,8,11,.77) 100%);
      box-shadow:none; border:0; border-radius:0;
    }
    window.iptv-tv.synplus-window .synplus-video-chrome {
      background-color:transparent; background-image:none;
      color:#f6f8fa; padding:24px 11px 7px 11px;
    }
    window.iptv-tv.synplus-window.synplus-compact-player .synplus-video-chrome {
      padding-top:14px;
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
    window.iptv-tv.synplus-window .synplus-nav { min-width:195px; }
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
    window.iptv-tv.synplus-window.synplus-pure-fullscreen .synplus-video-gradient {
      background-image:none; }
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
''' + mac_visual_cleanup_css(rail_is_light) + mac_native_css(accent_hex, system_dark)


def mac_popover_css(dark=False):
    """Native Mac whites/blacks for ALL non-Cast detached Gtk.Popovers.

    Scope specifically to popovers instead of the main GTK workbench. Cast
    keeps its independently validated styling provider untouched.
    """
    if sys.platform != 'darwin': return ''
    from syn_macos_theme import accent_color
    accent = accent_color(bool(dark))
    bg = '#1C1C1E' if dark else '#FFFFFF'
    panel = '#2C2C2E' if dark else '#F2F2F7'
    fg = '#F5F5F7' if dark else '#1C1C1E'
    line = 'rgba(255,255,255,.17)' if dark else 'rgba(0,0,0,.12)'
    return f"""
    /* SYN_MAC_574_POPUPS: settings gear + channel dropdown + context menus.
       Exclude Chromecast's popup deliberately. */
    popover:not(.syn-cast-popover),
    popover:not(.syn-cast-popover) > contents,
    popover:not(.syn-cast-popover) > contents box,
    popover:not(.syn-cast-popover) scrolledwindow,
    popover:not(.syn-cast-popover) viewport,
    popover:not(.syn-cast-popover) listview,
    popover:not(.syn-cast-popover) listbox {{
       background-image:none; background-color:{bg}; color:{fg};
    }}
    popover:not(.syn-cast-popover) > contents {{
       border:1px solid {line}; border-radius:12px;
       box-shadow:0 8px 24px rgba(0,0,0,.18);
    }}
    popover:not(.syn-cast-popover) button,
    popover:not(.syn-cast-popover) modelbutton,
    popover:not(.syn-cast-popover) row,
    popover:not(.syn-cast-popover) listview row {{
       background-image:none; background-color:transparent; color:{fg};
       border-color:transparent;
    }}
    popover:not(.syn-cast-popover) row:hover,
    popover:not(.syn-cast-popover) row:selected,
    popover:not(.syn-cast-popover) modelbutton:hover,
    popover:not(.syn-cast-popover) button:hover {{
       background-image:none; background-color:alpha({accent},.15);
       color:{fg};
    }}
    popover:not(.syn-cast-popover) label,
    popover:not(.syn-cast-popover) image,
    popover:not(.syn-cast-popover) button label,
    popover:not(.syn-cast-popover) row label,
    popover:not(.syn-cast-popover) modelbutton label {{
       color:{fg}; text-shadow:none;
    }}
    popover:not(.syn-cast-popover) entry,
    popover:not(.syn-cast-popover) searchentry,
    popover:not(.syn-cast-popover) text {{
       background-image:none; background-color:{panel}; color:{fg};
       border-color:{line};
    }}
    window.syn-settings-window popover:not(.syn-cast-popover) {{
       color:{fg};
    }}
    """


def mac_settings_css(dark=False):
    """SYN_MAC_575_SETTINGS: neutral AppKit-inspired settings, system accent only.

    Installed separately above GTK USER styles from Linux and the dialog CSS.
    Does not touch data, values, actions or existing widgets.
    """
    if sys.platform != 'darwin':
        return ''
    from syn_macos_theme import accent_color
    accent = accent_color(bool(dark))
    bg = '#1C1C1E' if dark else '#FFFFFF'
    surface = '#2C2C2E' if dark else '#F2F2F7'
    control = '#3A3A3C' if dark else '#FFFFFF'
    fg = '#F5F5F7' if dark else '#1C1C1E'
    muted = '#AEAEB2' if dark else '#636366'
    border = 'rgba(255,255,255,.15)' if dark else 'rgba(0,0,0,.12)'
    accent_button_fg = '#1C1C1E' if accent.lower() in (
        '#ff9500','#ff9f0a','#ffcc00','#ffd60a','#34c759','#30d158') else '#FFFFFF'
    return f"""
    /* SYN_MAC_575_SETTINGS: no Linux palette, including detached settings UI */
    window.syn-settings-window,
    window.syn-settings-window box,
    window.syn-settings-window scrolledwindow,
    window.syn-settings-window viewport,
    window.syn-settings-window stack,
    window.syn-settings-window .syn-pref-page {{
       background-image:none; background-color:{bg}; color:{fg};
    }}
    window.syn-settings-window .syn-pref-header,
    window.syn-settings-window .syn-pref-footer,
    window.syn-settings-window headerbar,
    window.syn-settings-window .titlebar {{
       background-image:none; background-color:{bg}; color:{fg};
       border-color:{border};
    }}
    window.syn-settings-window .syn-pref-sidebar,
    window.syn-settings-window .syn-pref-sidebar list,
    window.syn-settings-window .syn-pref-sidebar listbox {{
       background-image:none; background-color:{surface}; color:{fg};
       border-color:{border};
    }}
    window.syn-settings-window .syn-pref-sidebar row {{
       background-image:none; background-color:transparent; color:{fg};
       border-radius:10px;
    }}
    window.syn-settings-window .syn-pref-sidebar row:hover {{
       background-color:alpha({accent},.10); color:{fg};
    }}
    window.syn-settings-window .syn-pref-sidebar row:selected {{
       background-color:alpha({accent},.18); color:{fg};
    }}
    window.syn-settings-window .syn-pref-group {{
       background-image:none; background-color:{surface}; color:{fg};
       border:1px solid {border}; border-radius:14px;
    }}
    window.syn-settings-window label,
    window.syn-settings-window .syn-pref-heading,
    window.syn-settings-window .syn-pref-section-title,
    window.syn-settings-window image {{color:{fg}; text-shadow:none;}}
    window.syn-settings-window .syn-pref-muted {{color:{muted}; opacity:1;}}
    window.syn-settings-window button:not(.suggested-action):not(.destructive-action):not(.syn-pref-swatch),
    window.syn-settings-window dropdown > button,
    window.syn-settings-window entry,
    window.syn-settings-window passwordentry,
    window.syn-settings-window spinbutton,
    window.syn-settings-window searchentry {{
       background-image:none; background-color:{control}; color:{fg};
       border:1px solid {border}; box-shadow:none;
    }}
    window.syn-settings-window button:not(.suggested-action):not(.destructive-action):not(.syn-pref-swatch):hover,
    window.syn-settings-window dropdown > button:hover {{
       background-image:none; background-color:alpha({accent},.13);
       border-color:alpha({accent},.45); color:{fg};
    }}
    window.syn-settings-window button.syn-pref-theme:checked,
    window.syn-settings-window .syn-pref-sidebar row:selected {{
       border-color:alpha({accent},.55); background-color:alpha({accent},.17);
    }}
    window.syn-settings-window button.suggested-action {{
       background-image:none; background-color:{accent}; color:{accent_button_fg};
       border:1px solid {accent}; box-shadow:none;
    }}
    window.syn-settings-window button.suggested-action label {{color:{accent_button_fg};}}
    window.syn-settings-window button.destructive-action {{
       background-image:none; background-color:transparent;
       color:{'#FF453A' if dark else '#FF3B30'}; border-color:{border};
    }}
    window.syn-settings-window button.destructive-action label {{
       color:{'#FF453A' if dark else '#FF3B30'};
    }}
    window.syn-settings-window switch:checked {{background-color:{accent};}}
    window.syn-settings-window checkbutton:checked check,
    window.syn-settings-window radiobutton:checked radio,
    window.syn-settings-window scale highlight,
    window.syn-settings-window scrollbar slider:hover {{background-color:{accent};}}
    window.syn-settings-window entry text,
    window.syn-settings-window passwordentry text,
    window.syn-settings-window searchentry text,
    window.syn-settings-window dropdown label,
    window.syn-settings-window dropdown arrow {{color:{fg};}}
    window.syn-settings-window selection {{background-color:alpha({accent},.33);}}
    """


def mac_native_css(accent_hex='', system_dark=False):
    """macOS-only Apple semantic palette, with system-controlled accent.

    Gtk CSS can approximate translucent frosted glass. It cannot apply native
    NSVisualEffectView blur; we deliberately avoid claiming a native blur.
    """
    if sys.platform != 'darwin':return ''
    from syn_macos_theme import accent_color, is_dark
    dark = bool(system_dark)
    accent = accent_color(dark)
    # Official macOS light/dark neutral color families, not a SYN colour theme.
    bg = '#000000' if dark else '#FFFFFF'
    panel = '#1C1C1E' if dark else '#F2F2F7'
    white = '#2C2C2E' if dark else '#FFFFFF'
    fg = '#F5F5F7' if dark else '#1C1C1E'
    muted = '#98989D' if dark else '#6C6C70'
    border = 'rgba(255,255,255,.16)' if dark else 'rgba(0,0,0,.10)'
    glass = 'rgba(44,44,46,.82)' if dark else 'rgba(242,242,247,.78)'
    chrome = 'rgba(50,50,54,.86)' if dark else 'rgba(250,250,252,.92)'
    return f"""
    /* SYN-Mac 5.7 : AUTO LIGHT/DARK + true macOS system accent. */
    window.iptv-tv.synplus-window,
    window.iptv-tv.synplus-window .synplus-workbench,
    window.iptv-tv.synplus-window .synplus-video-column {{
        background-image:none; background-color:{bg}; color:{fg};
    }}
    window.iptv-tv.synplus-window .synplus-nav {{
        background-image:none; background-color:{glass}; color:{fg};
        border-right:1px solid {border}; min-width:195px;
    }}
    window.iptv-tv.synplus-window .synplus-nav label,
    window.iptv-tv.synplus-window .synplus-nav image {{ color:{fg}; }}
    window.iptv-tv.synplus-window .synplus-nav button.synplus-nav-button {{
        background-image:none; background-color:transparent; color:{fg};
        border:0; box-shadow:none;
    }}
    window.iptv-tv.synplus-window .synplus-nav button.synplus-nav-button:hover {{
        background-image:none; background-color:alpha({accent},.15);
        color:{fg};
    }}
    window.iptv-tv.synplus-window .synplus-nav button.synplus-nav-button.synplus-current {{
        background-image:none; background-color:alpha({accent},.22);
        color:{fg};
    }}
    window.iptv-tv.synplus-window .synplus-nav button.synplus-add-profile {{
        background-image:none; background-color:{accent}; color:{'#1C1C1E' if dark else '#FFFFFF'};
        border:0; border-radius:11px; font-weight:700;
    }}
    window.iptv-tv.synplus-window .synplus-nav button.synplus-add-profile:hover {{
        background-color:alpha({accent},.77);
    }}
    window.iptv-tv.synplus-window .synplus-nav dropdown.synplus-profile-picker,
    window.iptv-tv.synplus-window .synplus-nav dropdown.synplus-profile-picker > button {{
        background-image:none; background-color:alpha({fg},.065);
        color:{fg}; border:1px solid {border}; border-radius:11px;
        min-height:34px; box-shadow:none;
    }}
    window.iptv-tv.synplus-window .synplus-nav dropdown.synplus-profile-picker:hover,
    window.iptv-tv.synplus-window .synplus-nav dropdown.synplus-profile-picker > button:hover {{
        background-color:alpha({accent},.13); border-color:alpha({accent},.4);
    }}
    window.iptv-tv.synplus-window .synplus-sidebar {{
        background-image:none; background-color:{chrome}; color:{fg}; border-right:1px solid {border};
    }}
    window.iptv-tv.synplus-window .synplus-sidebar .iptv-row:hover {{
        background-color:alpha({accent},.07);
    }}
    window.iptv-tv.synplus-window .synplus-sidebar .iptv-row:selected {{
        background-color:alpha({accent},.24); border-color:alpha({accent},.62);
    }}
    window.iptv-tv.synplus-window .synplus-sidebar .iptv-row label,
    window.iptv-tv.synplus-window .synplus-sidebar .syn-channel-display-name {{
        color:{fg};
    }}
    window.iptv-tv.synplus-window .synplus-sidebar searchentry,
    window.iptv-tv.synplus-window .synplus-sidebar .iptv-search,
    window.iptv-tv.synplus-window .synplus-sidebar dropdown > button {{
        background-image:none; background-color:{white}; color:{fg}; border-color:{border};
    }}
    window.iptv-tv.synplus-window .synplus-sidebar button.syn-favorite-heart {{
        background:transparent; color:{muted};
    }}
    window.iptv-tv.synplus-window .synplus-sidebar button.syn-favorite-heart:hover {{
        background-color:alpha({accent},.13); color:{accent};
    }}
    window.iptv-tv.synplus-window .synplus-guide {{
        background-color:{panel}; color:{fg}; border-color:{border};
    }}
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-header,
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-axis,
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-footer {{
        background-color:{panel}; color:{fg};
    }}
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-title,
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-muted {{color:{fg};}}
    window.iptv-tv.synplus-window .synplus-guide .syn-guide-head-button:hover {{
        background-color:alpha({accent},.18); color:{fg};
    }}
    window.iptv-tv.synplus-window .synplus-header {{
        background-image:none; background-color:{glass}; color:{fg};
        border-bottom:1px solid {border};
    }}
    window.iptv-tv.synplus-window .synplus-header button:hover {{
        background-color:alpha({accent},.16); color:{fg};
    }}
    /* Fullscreen always uses neutral dark translucent controls, regardless
       of whether the desktop's appearance is white or black. */
    window.iptv-tv.synplus-window .syn-fs-top button:not(.syn-cast-button),
    window.iptv-tv.synplus-window .syn-fs-bottom button:not(.syn-cast-button) {{
        background-image:none; background-color:rgba(28,28,30,.65);
        color:#FFFFFF; border:1px solid rgba(255,255,255,.14); box-shadow:none;
        border-radius:9px;
    }}
    window.iptv-tv.synplus-window .syn-fs-top button:not(.syn-cast-button):hover,
    window.iptv-tv.synplus-window .syn-fs-bottom button:not(.syn-cast-button):hover {{
        background-color:alpha({accent},.72); color:#FFFFFF;
    }}
    window.iptv-tv.synplus-window .syn-fs-top button image {{color:#FFFFFF;}}
    window.iptv-tv.synplus-window .syn-fs-bottom scale highlight {{
        background-color:{accent};
    }}
    window.iptv-tv.synplus-window button.syn-cast-button {{
        background-color:{accent}; border-color:{accent};
    }}
     /* SYN_MAC_572_NEUTRAL — Mac UI uses only neutral surfaces + system accent. */
     window.iptv-tv.synplus-window .synplus-sidebar,
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-list,
     window.iptv-tv.synplus-window .synplus-sidebar scrolledwindow,
     window.iptv-tv.synplus-window .synplus-sidebar listbox {{
        background-image:none; background-color:{chrome}; color:{fg};
     }}
     window.iptv-tv.synplus-window .synplus-nav {{
        background-image:none; background-color:{'rgba(44,44,46,.56)' if dark else 'rgba(242,242,247,.56)'};
        border-right:1px solid {border};
     }}
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-dropdown,
     window.iptv-tv.synplus-window .synplus-sidebar dropdown,
     window.iptv-tv.synplus-window .synplus-sidebar dropdown > button,
     window.iptv-tv.synplus-window .synplus-sidebar searchentry,
     window.iptv-tv.synplus-window .synplus-sidebar searchentry text {{
        background-image:none; background-color:{white}; color:{fg};
        border-color:{border};
     }}
     window.iptv-tv.synplus-window .synplus-sidebar dropdown:hover,
     window.iptv-tv.synplus-window .synplus-sidebar dropdown > button:hover {{
        background-color:alpha({accent},.11); border-color:alpha({accent},.45);
     }}
     popover.menu > contents, popover > contents {{
        background-color:{white}; color:{fg};
     }}
     popover modelbutton:hover, popover row:hover,
     popover modelbutton:selected, popover row:selected {{
        background-color:alpha({accent},.18); color:{fg};
     }}
     window.iptv-tv.synplus-window .synplus-guide,
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-footer,
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-header,
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-axis {{
        background-image:none; background-color:{panel}; color:{fg};
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-track {{
        background-image:none; background-color:{panel}; color:{fg};
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-channel {{
        background-image:none; background-color:{white}; color:{fg};
        border-color:alpha({accent},.18);
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-channel-playing {{
        background-image:none; background-color:alpha({accent},.16);
        border-color:alpha({accent},.38); color:{fg};
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-cat,
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-channel-name {{
        color:{fg};
     }}
     /* SYN_MAC_572_EPG_NEUTRAL: embedded and full EPG are Apple-neutral.
        The pop/fluorescent programme gradients are intentionally untouched. */
     window.iptv-tv.synplus-window .syn-guide-backdrop,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-header,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-axis,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-footer,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-categories {{
         background-image:none; background-color:{panel}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-track,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-gap {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-channel {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-channel-playing {{
         background-image:none; background-color:alpha({accent},.16);
         border-color:alpha({accent},.48); color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-channel-name,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-title,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-time,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-muted {{
         color:{fg}; text-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-cat {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-cat:hover {{
         background-color:alpha({accent},.09);
         border-color:alpha({accent},.28);
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-cat.active {{
         background-image:none; background-color:alpha({accent},.21);
         border-color:alpha({accent},.65); color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-head-button,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-search {{
         background-image:none; background-color:{white};
         color:{fg}; border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-head-button:hover,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-search:focus {{
         background-color:alpha({accent},.12);
         border-color:alpha({accent},.5); color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-search text {{
         background-color:transparent; color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-now-line {{
         background-color:{accent};
     }}
     /* Neutral channel list. Accent only on hover and selected channel. */
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-list,
     window.iptv-tv.synplus-window .synplus-sidebar listbox,
     window.iptv-tv.synplus-window .synplus-sidebar scrolledwindow {{
         background-image:none; background-color:{chrome};
     }}
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-row:selected {{
         background-image:none; background-color:alpha({accent},.22);
         border-color:alpha({accent},.72);
     }}
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-row:hover:not(:selected) {{
         background-image:none; background-color:alpha({accent},.065);
     }}
     /* SYN_MAC_572_EPG_NEUTRAL: embedded and full EPG are Apple-neutral.
        The pop/fluorescent programme gradients are intentionally untouched. */
     window.iptv-tv.synplus-window .syn-guide-backdrop,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-header,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-axis,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-footer,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-categories {{
         background-image:none; background-color:{panel}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-track,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-gap {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-channel {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-channel-playing {{
         background-image:none; background-color:alpha({accent},.16);
         border-color:alpha({accent},.48); color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-channel-name,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-title,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-time,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-muted {{
         color:{fg}; text-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-cat {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-cat:hover {{
         background-color:alpha({accent},.09);
         border-color:alpha({accent},.28);
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-cat.active {{
         background-image:none; background-color:alpha({accent},.21);
         border-color:alpha({accent},.65); color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-head-button,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-search {{
         background-image:none; background-color:{white};
         color:{fg}; border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-head-button:hover,
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-search:focus {{
         background-color:alpha({accent},.12);
         border-color:alpha({accent},.5); color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-search text {{
         background-color:transparent; color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-guide-backdrop .syn-guide-now-line {{
         background-color:{accent};
     }}
     /* Neutral channel list. Accent only on hover and selected channel. */
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-list,
     window.iptv-tv.synplus-window .synplus-sidebar listbox,
     window.iptv-tv.synplus-window .synplus-sidebar scrolledwindow {{
         background-image:none; background-color:{chrome};
     }}
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-row:selected {{
         background-image:none; background-color:alpha({accent},.22);
         border-color:alpha({accent},.72);
     }}
     window.iptv-tv.synplus-window .synplus-sidebar .iptv-row:hover:not(:selected) {{
         background-image:none; background-color:alpha({accent},.065);
     }}
     /* Bottom fullscreen controls: no pillboxes, white divider lines or teal. */
     window.iptv-tv.synplus-window .syn-fs-bottom,
     window.iptv-tv.synplus-window .syn-fs-volume,
     window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume {{
        background-image:none; background-color:transparent;
        color:#FFFFFF; border:0; box-shadow:none; padding:0;
     }}
     window.iptv-tv.synplus-window .syn-fs-bottom button,
     window.iptv-tv.synplus-window .syn-fs-bottom button.flat {{
        background-image:none; background-color:transparent; color:#FFFFFF;
        border:0; box-shadow:none; border-radius:7px;
        min-height:28px; min-width:28px; padding:0 5px;
     }}
     window.iptv-tv.synplus-window .syn-fs-bottom button:hover {{
        background-color:alpha({accent},.22); color:#FFFFFF;
     }}
     window.iptv-tv.synplus-window .syn-fs-bottom scale trough {{
        background-color:rgba(255,255,255,.27); border:0; box-shadow:none;
        min-height:3px; border-radius:2px;
     }}
     window.iptv-tv.synplus-window .syn-fs-bottom scale highlight {{
        background-color:{accent}; border-radius:2px;
     }}
     window.iptv-tv.synplus-window .syn-fs-bottom scale slider {{
        background-color:#FFFFFF; border:0; min-width:11px; min-height:11px;
        box-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-fs-scrim-bottom {{
        background-image:linear-gradient(to top,
            rgba(0,0,0,.85),rgba(0,0,0,.50) 40%,transparent 100%);
        background-color:transparent;
     }}
     window.iptv-tv.synplus-window .syn-fs-scrim-top {{
        background-image:linear-gradient(to bottom,
            rgba(0,0,0,.65),rgba(0,0,0,.28) 52%,transparent 100%);
        background-color:transparent;
     }}
     /* Zapping: charcoal-to-black veil, independent of light/dark appearance. */
     window.iptv-tv.synplus-window .syn-zap-backdrop {{
        background-image:linear-gradient(to left,
            rgba(0,0,0,.96) 0%,rgba(0,0,0,.92) 39%,
            rgba(0,0,0,.70) 65%,rgba(0,0,0,.22) 89%,transparent 100%);
        background-color:transparent; border:0; box-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel,
     window.iptv-tv.synplus-window .syn-zap-panel label,
     window.iptv-tv.synplus-window .syn-zap-panel image,
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-title,
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-name {{
        color:#FFFFFF; text-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-subtitle,
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-group {{
        color:#D1D1D6;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel button,
     window.iptv-tv.synplus-window .syn-zap-panel checkbutton,
     window.iptv-tv.synplus-window .syn-zap-panel dropdown {{
        background-image:none; background-color:transparent; color:#FFFFFF;
        border:0; box-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel button:hover,
     window.iptv-tv.synplus-window .syn-zap-panel row:hover {{
        background-color:alpha({accent},.20); color:#FFFFFF;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-row.syn-zap-playing {{
        background-color:alpha({accent},.24); border-color:alpha({accent},.70);
     }}
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-row {{
        background-color:rgba(255,255,255,.055); border:1px solid transparent;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-search,
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-category {{
        background-image:none; background-color:rgba(255,255,255,.13);
        color:#FFFFFF; border:1px solid rgba(255,255,255,.15);
     }}
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-search text {{
        background-color:transparent; color:#FFFFFF;
     }}
     window.iptv-tv.synplus-window .syn-zap-panel .syn-zap-eyebrow {{color:{accent};}}
     /* 5.7.1 — Pastillas EPG pop fluor con gradientes y bordes redondeados.
        Se colorean SOLO los programas, nunca las celdas de canal/logos. */
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program {{
         border-radius:11px; background-clip:padding-box;
         border:1px solid rgba(0,0,0,.13); box-shadow:none;
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-0 {{
         background-image:linear-gradient(145deg,#00CDA7 0%,#047861 100%);
         background-color:#047861;
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-1 {{
         background-image:linear-gradient(145deg,#D155FA 0%,#6B31C6 100%);
         background-color:#6B31C6;
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-2 {{
         background-image:linear-gradient(145deg,#1AAEFF 0%,#235BDB 100%);
         background-color:#235BDB;
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-3 {{
         background-image:linear-gradient(145deg,#FF9E25 0%,#D6531B 100%);
         background-color:#D6531B;
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-4 {{
         background-image:linear-gradient(145deg,#FF4AA6 0%,#BA2580 100%);
         background-color:#BA2580;
     }}
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program-5 {{
         background-image:linear-gradient(145deg,#A4E82F 0%,#2E9060 100%);
         background-color:#2E9060;
     }}
     /* SYN_MAC_573_EPG_UNIFORM: all program titles/times remain white.
        Strong neutral shadow maintains legibility on lime/orange/neon bars. */
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program label,
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program .syn-guide-program-name,
     window.iptv-tv.synplus-window .synplus-guide .syn-guide-program .syn-guide-time {{
         color:#FFFFFF;
         text-shadow:0 1px 2px rgba(0,0,0,.88), 0 0 5px rgba(0,0,0,.58);
     }}
     /* SYN_MAC_573_GLOBAL_APPLE: macOS neutrality extends to DVR, Cine, Series,
        calendar, recording library and detached controls. No Linux teal. */
     window.iptv-tv.synplus-window .syn-dvr-page,
     window.iptv-tv.synplus-window .syn-dvr-page scrolledwindow,
     window.iptv-tv.synplus-window .syn-dvr-page viewport {{
         background-image:none; background-color:{bg}; color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-dvr-page label,
     window.iptv-tv.synplus-window .syn-dvr-page .heading,
     window.iptv-tv.synplus-window .syn-dvr-page .title-2,
     window.iptv-tv.synplus-window .syn-dvr-page .title-3 {{
         color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-dvr-page .dim-label {{ color:{muted}; }}
     window.iptv-tv.synplus-window .syn-dvr-page list.boxed-list,
     window.iptv-tv.synplus-window .syn-dvr-page list.boxed-list > row,
     window.iptv-tv.synplus-window .syn-dvr-page calendar.view {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-dvr-page list.boxed-list > row:hover {{
         background-image:none; background-color:alpha({accent},.085);
     }}
     window.iptv-tv.synplus-window .syn-dvr-page button:not(.syn-dvr-action-record):not(.syn-dvr-schedule-action),
     window.iptv-tv.synplus-window .syn-dvr-page entry,
     window.iptv-tv.synplus-window .syn-dvr-page dropdown > button {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-dvr-page button:not(.syn-dvr-action-record):not(.syn-dvr-schedule-action):hover,
     window.iptv-tv.synplus-window .syn-dvr-page dropdown > button:hover {{
         background-image:none; background-color:alpha({accent},.11);
         border-color:alpha({accent},.40);
     }}
     window.iptv-tv.synplus-window .syn-dvr-page calendar header,
     window.iptv-tv.synplus-window .syn-dvr-page calendar grid {{
         background-image:none; background-color:{white}; color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-dvr-page calendar grid label:selected,
     window.iptv-tv.synplus-window .syn-dvr-page button.syn-dvr-schedule-action {{
         background-image:none; background-color:{accent};
         color:{'#FFFFFF' if not dark else '#1C1C1E'}; border-color:{accent};
     }}
     window.iptv-tv.synplus-window .syn-dvr-page button.syn-dvr-schedule-action label {{
         color:{'#FFFFFF' if not dark else '#1C1C1E'};
     }}
     window.iptv-tv.synplus-window button.syn-dvr-action-record,
     window.iptv-tv.synplus-window button.syn-dvr-action-record:hover {{
         background-image:none; background-color:#FF2D55;
         color:#FFFFFF; border-color:#FF2D55;
     }}
     window.iptv-tv.synplus-window button.syn-dvr-action-record label,
     window.iptv-tv.synplus-window button.syn-dvr-action-record:hover label {{
         color:#FFFFFF; text-shadow:none;
     }}
     dropdown.syn-dvr-channel-picker popover > contents,
     dropdown.syn-dvr-channel-picker popover listview,
     dropdown.syn-dvr-channel-picker popover scrolledwindow,
     dropdown.syn-dvr-channel-picker popover listview row {{
         background-image:none; background-color:{white}; color:{fg};
     }}
     dropdown.syn-dvr-channel-picker popover listview row:hover {{
         background-color:alpha({accent},.10);
     }}
     dropdown.syn-dvr-channel-picker popover listview row:selected {{
         background-color:alpha({accent},.22);
     }}
     /* Series and Cine: editorial content stays grayscale; posters and
        artwork retain their source colors, as do the separate EPG pills. */
     window.iptv-tv.synplus-window .syn-portal-root {{
         background-image:none; background-color:{bg}; color:{fg};
     }}
     window.iptv-tv.synplus-window .syn-portal-top {{
         background-image:none; background-color:{panel}; color:{fg};
         border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-portal-title,
     window.iptv-tv.synplus-window .syn-portal-hero,
     window.iptv-tv.synplus-window .syn-portal-tile-title,
     window.iptv-tv.synplus-window .syn-portal-poster-name,
     window.iptv-tv.synplus-window .syn-portal-art-name {{
         color:{fg}; text-shadow:none;
     }}
     window.iptv-tv.synplus-window .syn-portal-subtitle,
     window.iptv-tv.synplus-window .syn-portal-muted,
     window.iptv-tv.synplus-window .syn-portal-poster-group {{ color:{muted}; }}
     window.iptv-tv.synplus-window .syn-portal-kicker,
     window.iptv-tv.synplus-window .syn-portal-counter {{ color:{accent}; }}
     window.iptv-tv.synplus-window button.syn-portal-tile,
     window.iptv-tv.synplus-window button.syn-portal-poster-card {{
         background-image:none; background-color:{white}; color:{fg};
         border-color:{border}; box-shadow:none;
     }}
     window.iptv-tv.synplus-window button.syn-portal-tile:hover,
     window.iptv-tv.synplus-window button.syn-portal-poster-card:hover {{
         background-image:none; background-color:alpha({accent},.10);
         border-color:alpha({accent},.48);
     }}
     window.iptv-tv.synplus-window .syn-portal-orb,
     window.iptv-tv.synplus-window .syn-portal-orb-movies,
     window.iptv-tv.synplus-window .syn-portal-orb-series {{
         background-image:none; background-color:alpha({accent},.10);
         border-color:alpha({accent},.30);
     }}
     window.iptv-tv.synplus-window .syn-portal-orb-icon,
     window.iptv-tv.synplus-window .syn-portal-orb-movies .syn-portal-orb-icon,
     window.iptv-tv.synplus-window .syn-portal-orb-series .syn-portal-orb-icon {{
         color:{accent};
     }}
     window.iptv-tv.synplus-window .syn-portal-poster {{
         background-color:{panel}; border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-portal-root button:not(.syn-portal-tile):not(.syn-portal-poster-card) {{
         color:{fg}; border-color:{border};
     }}
     window.iptv-tv.synplus-window .syn-portal-root button:not(.syn-portal-tile):not(.syn-portal-poster-card):hover {{
         background-color:alpha({accent},.13);
     }}
     window.syn-settings-window {{background-color:{bg}; color:{fg};}}
     """


def mac_visual_cleanup_css(light_theme):
    """SYN_MAC_56B1_UI_POLISH: UI, nunca reproductor/EPG/servicios."""
    common = """
    /* SYN_MAC_56B1_UI_POLISH: navegación y botón Añadir; todas las paletas. */
    window.iptv-tv.synplus-window .synplus-nav .synplus-fav-heart-icon {
        font-size:20px; font-weight:700; min-width:17px;
        color:inherit; padding:0; margin:0;
    }
    window.iptv-tv.synplus-window button.synplus-add-profile {
        background-image:none; background-color:#126c63;
        color:#ffffff; border:1px solid #0d544c;
        border-radius:12px; min-height:38px;
        padding:6px 12px; margin:5px 5px 8px;
        font-weight:700; box-shadow:none;
    }
    window.iptv-tv.synplus-window button.synplus-add-profile:hover {
        background-color:#178879; color:#ffffff; border-color:#11695f;
    }
    """
    if not light_theme:
        return common
    return common + """
    /* Pantalla completa CLARA: fondo oscuro translúcido en lugar de
       pastillas opacas blanco/azul celeste sobre la imagen. */
    window.iptv-tv.synplus-window .syn-fs-top { margin:16px 18px; }
    window.iptv-tv.synplus-window .syn-fs-top button:not(.syn-cast-button) {
        background-image:none; background-color:rgba(9,30,35,.62);
        color:#f5fffd; border:1px solid rgba(241,255,252,.18);
        border-radius:9px; min-height:32px; min-width:34px;
        padding:3px 7px; box-shadow:none; text-shadow:none;
    }
    window.iptv-tv.synplus-window .syn-fs-top button:not(.syn-cast-button) image {
        color:#f5fffd;
    }
    window.iptv-tv.synplus-window .syn-fs-top button:not(.syn-cast-button):hover {
        background-color:rgba(28,28,30,.84);
        border-color:rgba(248,255,254,.40); color:#ffffff;
    }
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume {
        background-image:none; background-color:rgba(9,30,35,.60);
        color:#f6fffd; border:1px solid rgba(244,255,252,.10);
        border-radius:11px; padding:4px 7px; box-shadow:none;
    }
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume label,
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume image {
        color:#f6fffd;
    }
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume button {
        background-image:none; background-color:rgba(255,255,255,.09);
        border:0; border-radius:7px; padding:2px 5px;
        color:#f5fffd; min-height:25px; box-shadow:none;
    }
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume button:hover {
        background-color:rgba(28,28,30,.78); color:#ffffff;
    }
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume scale trough {
        background-color:rgba(250,255,254,.20);
        border:0; border-radius:7px;
    }
    window.iptv-tv.synplus-window .syn-fs-bottom .syn-fs-volume scale highlight {
        background-color:#FFFFFF; border-radius:7px;
    }
    """


def draw_monochrome_testcard(area, cr, width, height):
    """Scale-independent B/W vintage TV test pattern used before playback.

    Pure Cairo drawing: no external images, no downloads, no stored assets,
    and never a black blank player surface. Drawn only while the original
    SYN idle layer is visible; leaves GLArea/libmpv completely untouched.
    """
    if width <= 0 or height <= 0:
        return
    import math
    cr.save()
    try:
        # Retro SMPTE/monoscope-inspired geometry, deliberately GRAYSCALE only.
        cr.scale(width/960.0, height/540.0)
        def ink(y): cr.set_source_rgb(y,y,y)
        def rect(x,y,w,h,tone):
            ink(tone); cr.rectangle(x,y,w,h); cr.fill()
        def line(x1,y1,x2,y2,tone=.14,thickness=2):
            ink(tone); cr.set_line_width(thickness)
            cr.move_to(x1,y1); cr.line_to(x2,y2); cr.stroke()
        rect(0,0,960,540,.78)
        rect(10,10,940,520,.12)
        rect(18,18,924,504,.87)
        # Repeated vertical gray bars, like a monochrome broadcast chart.
        for i,shade in enumerate((.98,.84,.70,.57,.44,.31,.18,.08)):
            rect(28+i*113,28,113,117,shade)
        rect(28,151,904,22,.15)
        for i in range(16):
            rect(28+i*56.5,152,56.5,20,.94 if i%2==0 else .24)
        # Lower calibration ramp and alternate-frequency blocks.
        for i in range(20):
            rect(28+i*45.2,425,45.2,43,.10+i*(.84/19.0))
        for i in range(36):
            rect(28+i*25.12,474,25.12,32,.97 if i%2 else .11)
        # Border crosses give the technical, slightly imperfect retro feel.
        for x in (50,910):
            for y in (198,400):
                line(x-13,y,x+13,y,.17,2)
                line(x,y-13,x,y+13,.17,2)
        # Central calibration target with circular rulers.
        ink(.94); cr.arc(480,298,128,0,math.tau);cr.fill()
        ink(.16);cr.set_line_width(5);cr.arc(480,298,124,0,math.tau);cr.stroke()
        ink(.52);cr.set_line_width(15);cr.arc(480,298,103,0,math.tau);cr.stroke()
        ink(.11);cr.set_line_width(2);cr.arc(480,298,76,0,math.tau);cr.stroke()
        ink(.12);cr.set_line_width(1.4);cr.arc(480,298,43,0,math.tau);cr.stroke()
        for t in range(0,360,15):
            a=math.radians(t)
            outer=120
            inner=108 if t%45 else 98
            line(480+inner*math.cos(a),298+inner*math.sin(a),
                 480+outer*math.cos(a),298+outer*math.sin(a),.14,2)
        line(480,178,480,418,.14,1.5)
        line(356,298,604,298,.14,1.5)
        # High contrast signature strip and central SYN wordmark.
        rect(401,263,158,63,.12)
        ink(.97)
        cr.select_font_face('Sans', 0, 1)
        cr.set_font_size(43)
        cr.move_to(431,310)
        cr.show_text('SYN')
        # Useful engineering captions, with simple ASCII toy text.
        ink(.19);cr.select_font_face('Monospace',0,1)
        cr.set_font_size(15)
        cr.move_to(41,194);cr.show_text('MONOCHROME / TEST SIGNAL')
        cr.move_to(680,194);cr.show_text('625 LINES')
        cr.move_to(45,414);cr.show_text('VIDEO CALIBRATION')
        cr.move_to(731,414);cr.show_text('STANDBY')
        # Thin edge rules to anchor all elements at any ratio.
        ink(.13);cr.set_line_width(2)
        cr.rectangle(22,22,916,494);cr.stroke()
    finally:
        cr.restore()


def preferred_window_size(monitor_width, monitor_height):
    """Use the user's screenshot proportions on *any* monitor size, not pixels."""
    w = max(1, int(monitor_width))
    h = max(1, int(monitor_height))
    # 71% of display width, with safe space around the window vertically.
    # Very small displays may still be constrained by GTK widget minimums.
    chosen_w = max(1, round(min(w * .71, (h * .73) * 5 / 3)))
    return chosen_w, round(chosen_w * 3 / 5)


def opening_window_geometry(window):
    try:
        monitors = window.get_display().get_monitors()
        if monitors.get_n_items():
            geometry = monitors.get_item(0).get_geometry()
            if geometry.width > 0 and geometry.height > 0:
                return preferred_window_size(geometry.width, geometry.height)
    except (AttributeError, TypeError, ValueError):
        pass
    return preferred_window_size(1920, 1200)


def install_synplus_layout(window, Gtk, GLib, video_column, base, brand, hidden_header_controls):
    """Recompose EXISTING GTK widgets before GTK/GLArea is realized.

    The player overlay is never recreated. EPG keeps its original scrolling,
    XMLTV paint, program gestures, recording context menus and programme data.
    """
    if getattr(window, '_synplus_ui', False):
        return
    window._synplus_ui = True
    video_column.add_css_class('synplus-video-column')
    window._synplus_gtk = Gtk
    window.set_title("SYN")
    window.set_resizable(True)
    # SYN_MAC_573_WINDOW: initial size tracks available monitor geometry.
    # The reference screenshot is ~5:3, about 71% of monitor width. This is
    # ONLY the startup size; GTK never imposes ongoing aspect-ratio constraints.
    opening_width, opening_height = opening_window_geometry(window)
    window.set_default_size(opening_width, opening_height)
    window.add_css_class('synplus-window')
    window.header.add_css_class('synplus-header')

    # 3 zones: fixed 150px nav, existing 315px channel browser, player + EPG.
    workbench = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    workbench.add_css_class('synplus-workbench')
    workbench.set_hexpand(True)
    workbench.set_vexpand(True)
    nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    nav.set_size_request(195, -1)
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
    window._syn_brand_band_spacer.set_size_request(-1, 83)
    window.syn_wordmark.set_size_request(142, 65)
    window.syn_wordmark.set_margin_start(9)
    window.syn_wordmark.set_margin_top(5)
    window._syn_brand_band.add_css_class('synplus-nav-brand')
    nav.append(window._syn_brand_band)
    # The original SYN wordmark is the sole brand: no extra subtitle.
    window.sidebar.add_css_class('synplus-sidebar')
    window.paned.set_position(330)
    window._saved_paned_position = 330
    window.sidebar.set_size_request(300, -1)

    # The HeaderBar still owns GNOME/Wayland window controls and can drag.
    # Only profile selection, a genuine overflow menu and compact channels remain.
    brand.set_visible(False)
    for widget in hidden_header_controls:
        widget.set_visible(False)
    # macOS: native profile picker lives at the bottom of the fixed rail,
    # not among traffic-light controls in the titlebar. Reuse the live widget
    # so change_profile, profile updates and persisted selections remain intact.
    if sys.platform == 'darwin':
        window.header.remove(window.profile_picker)
        window.profile_picker.add_css_class('synplus-profile-picker')
        window.profile_picker.set_hexpand(True)
        window.profile_picker.set_halign(Gtk.Align.FILL)
    window.profile_picker.set_visible(True)

    # SYN_MAC_578_NO_OVERFLOW: the redundant ⋯ menu is removed entirely.

    buttons = {}

    def _select(name):
        window._synplus_current_section = name
        for key, btn in buttons.items():
            if key == name:
                btn.add_css_class('synplus-current')
            else:
                btn.remove_css_class('synplus-current')
        fav = buttons.get('favoritos')
        if fav is not None:
            glyph = fav.get_child().get_first_child()
            glyph.set_text('♥' if name == 'favoritos' else '♡')

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
        # Remember the active destination BEFORE Guide hides the portal
        # or DVR. Do not overwrite when Guide is already active.
        previous = getattr(window, '_synplus_current_section', 'tv')
        if previous != 'guia':
            state = {'section': previous}
            if previous in ('cine', 'series'):
                state['portal_mode'] = getattr(window, '_syn_portal_mode',
                                               'movies' if previous == 'cine' else 'series')
                state['query'] = window._syn_portal_search.get_text()
            window._synplus_guide_return = state
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

    def _restore_guide(*_):
        # Reparent the EPG first, then close it. Closing alone leaves
        # the full-guide navigation selection over a black main panel.
        state = getattr(window, '_synplus_guide_return', None) or {}
        previous = state.get('section', 'tv')
        set_guide_mode(window, GLib, False)
        if window.guide_open:
            window.set_guide_open(False)
        if previous == 'dvr':
            _dvr()
        elif previous in ('cine', 'series'):
            mode = state.get('portal_mode') or (
                'movies' if previous == 'cine' else 'series')
            if previous == 'cine':
                mode = 'movies'
            elif mode not in ('series', 'episodes'):
                mode = 'series'
            _portal(mode, previous)
            query = state.get('query', '')
            if query:
                window._syn_portal_search.set_text(query)
        elif previous == 'favoritos':
            _tv(favorites=True)
        else:
            _tv()
        window._synplus_guide_return = None

    window._synplus_restore_guide = _restore_guide

    entries = [
        ('tv', 'TV', 'video-display-symbolic', lambda: _tv()),
        ('guia', 'Guía', 'view-list-symbolic', lambda: _guide()),
        ('series', 'Series', 'folder-videos-symbolic', lambda: _portal('series','series')),
        ('cine', 'Cine', 'video-x-generic-symbolic', lambda: _portal('movies','cine')),
        ('dvr', 'DVR', 'media-record-symbolic', lambda: _dvr()),
        ('favoritos', 'Favoritos', None, lambda: _tv(favorites=True)),
        ('ajustes', 'Ajustes', 'emblem-system-symbolic', window.open_settings),
    ]
    for idx, (key, label, icon_name, callback) in enumerate(entries):
        if idx == 5:
            nav.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        button = Gtk.Button()
        button.set_halign(Gtk.Align.FILL)
        button.set_hexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        if key == 'favoritos':
            pictogram = Gtk.Label(label='♡')
            pictogram.add_css_class('synplus-fav-heart-icon')
        elif key == 'tv':
            # Pictograma nativo, evita un icono de tema inexistente o distinto.
            pictogram = Gtk.DrawingArea()
            pictogram.set_content_width(19)
            pictogram.set_content_height(19)
            pictogram.set_size_request(19, 19)
            pictogram.set_can_target(False)
            pictogram.set_draw_func(draw_tv_sidebar_icon)
            window._synplus_tv_icon = pictogram
        elif key == 'cine':
            pictogram = Gtk.DrawingArea()
            pictogram.set_content_width(19)
            pictogram.set_content_height(19)
            pictogram.set_size_request(19,19)
            pictogram.set_can_target(False)
            pictogram.set_draw_func(draw_vintage_movie_reel)
            window._synplus_cine_reel = pictogram
        else:
            pictogram = Gtk.Image.new_from_icon_name(icon_name)
            pictogram.set_pixel_size(16)
        content.append(pictogram)
        caption = Gtk.Label(label=tr(label), xalign=0)
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
    profile_button.set_tooltip_text(tr('Perfiles · cambiar o añadir'))
    avatar_image = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
    avatar_image.set_pixel_size(22)
    profile_button.set_child(avatar_image)
    profile_menu = Gtk.Popover()
    profile_menu.set_autohide(True)
    profile_button.set_popover(profile_menu)
    profile_button.set_visible(False)
    nav.append(profile_button)
    window._synplus_avatar_button = profile_button
    window._synplus_avatar_picture = avatar_image
    window._synplus_avatar_menu = profile_menu
    rebuild_profile_menu(window, Gtk)
    profile_button.connect('notify::active', lambda btn, *_:
        rebuild_profile_menu(window, Gtk) if btn.get_active() else None)
    window.profile_picker.connect('notify::selected', lambda *_: refresh_avatar(window))
    refresh_avatar(window)
    if sys.platform == 'darwin':
        window.profile_picker.set_margin_start(6)
        window.profile_picker.set_margin_end(6)
        window.profile_picker.set_margin_bottom(8)
        window.profile_picker.set_tooltip_text(tr('Cambiar de perfil IPTV'))
        nav.append(window.profile_picker)
    add_profile = Gtk.Button(label=tr('+  Añadir'))
    add_profile.set_tooltip_text(tr('Añadir perfil IPTV'))
    add_profile.add_css_class('synplus-nav-button')
    add_profile.add_css_class('synplus-add-profile')
    add_profile.connect('clicked', lambda *_: window.show_welcome())
    nav.append(add_profile)

    # Replace SYN's old coloured idle PNG with a purely grayscale, responsive
    # Cairo test pattern, before GTK realizes the GLArea. Existing idle logic
    # still controls visibility; actual playback is unaffected.
    card = Gtk.DrawingArea()
    card.set_hexpand(True)
    card.set_vexpand(True)
    card.set_halign(Gtk.Align.FILL)
    card.set_valign(Gtk.Align.FILL)
    card.set_can_target(False)
    card.set_draw_func(draw_monochrome_testcard)
    window._syn_idle_layer.set_child(card)
    window._syn_idle_hint.set_visible(False)
    window._synplus_idle_testcard = card

    # Existing video stays inside the Gtk.Overlay. We only move the overlay
    # before the first realization and overlay an unobtrusive playback chrome.
    video_column.remove(window.overlay)
    # Gtk.Frame does NOT impose any aspect ratio. The player canvas follows
    # the window's dimensions freely; MPV letterboxes the source as needed.
    # Gtk.GLArea stays attached to its original Gtk.Overlay throughout.
    frame = Gtk.Frame.new(None)
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
    # Starts exactly 16:9. Once the user resizes, the player canvas becomes
    # fully free (portrait, square, ultrawide); this is NOT a size constraint.
    window._synplus_opening_ratio = True
    window._synplus_opening_window_size = None
    # No Gtk.AspectFrame or Gdk surface geometry hints. The window, video
    # canvas, and EPG can be portrait, square or ultrawide as space allows.
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
    # The gradient and the controls now have independent, perfectly matched
    # 210ms CROSSFADE animations. Both follow one visibility state.
    # Drawing the gradient on a full-height surface makes it smooth, not a
    # black stripe cut off just below the buttons.
    persistent_gradient = Gtk.Box()
    persistent_gradient.add_css_class('synplus-video-gradient')
    persistent_gradient.set_halign(Gtk.Align.FILL)
    persistent_gradient.set_valign(Gtk.Align.FILL)
    persistent_gradient.set_hexpand(True)
    persistent_gradient.set_vexpand(True)
    persistent_gradient.set_can_target(False)
    gradient_reveal = Gtk.Revealer()
    gradient_reveal.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
    gradient_reveal.set_transition_duration(270)
    gradient_reveal.set_halign(Gtk.Align.FILL)
    gradient_reveal.set_valign(Gtk.Align.FILL)
    gradient_reveal.set_hexpand(True)
    gradient_reveal.set_vexpand(True)
    gradient_reveal.set_can_target(False)  # Do not block mouse or controls.
    gradient_reveal.set_child(persistent_gradient)
    gradient_reveal.set_reveal_child(False)
    window.overlay.add_overlay(gradient_reveal)
    window.overlay.set_measure_overlay(gradient_reveal, False)
    window._synplus_video_gradient = persistent_gradient
    window._synplus_gradient_reveal = gradient_reveal

    # Crossfade of the original toolbar and text on top of the shadow.
    window.overlay.remove_overlay(chrome)
    reveal = Gtk.Revealer()
    reveal.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
    reveal.set_transition_duration(270)
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
    window._synplus_cast_popover_open = False
    window._synplus_cast_popover = None
    GLib.timeout_add(300, lambda: poll_chrome(window))
    # These two legacy labels were outside the player and EPG. Keeping
    # them in the vertical box created a redundant black band, and fullscreen
    # transitions could make them visible again. Preserve self.status for
    # internal notifications, but never allocate visible height to either.
    for redundant in (window.footer, window.status):
        if redundant.get_parent() == video_column:
            video_column.remove(redundant)
        redundant.set_visible(False)
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
    if sys.platform == 'darwin':
        # The layout is now fully assembled. Set desired size again so the
        # later EPG/GLArea measurement cannot replace its initial hint.
        window.set_default_size(*opening_window_geometry(window))
        # No secondary startup resize when the player learns its dimensions.
        window._syn_startup_ratio_pending = False
    GLib.idle_add(lambda: (window.set_guide_open(True), False)[1])


def player_geometry(region_width, region_height, guide_height, horizontal_margin=8,
                    vertical_margin=4):
    """Use every available pixel: no 16:9 minimum, maximum, or other ratio.

    The Gtk.Overlay and Gtk.GLArea inherit this available area, while MPV
    retains the source material's original aspect ratio inside it.
    """
    usable_w = max(0, int(region_width) - int(horizontal_margin))
    usable_h = max(0, int(region_height) - int(guide_height) - int(vertical_margin))
    if usable_w < 16 or usable_h < 16:
        return None
    return usable_w, usable_h


def opening_player_geometry(region_width, region_height,
                            horizontal_margin=8, vertical_margin=4):
    """Exactly 16:9, fitted INSIDE the available player area at startup only.

    Uses integer blocks of 16x9, so never distorts or requests outside its host.
    After a window resize `player_geometry` takes over (arbitrary proportions).
    """
    available_w=max(0,int(region_width)-int(horizontal_margin))
    available_h=max(0,int(region_height)-int(vertical_margin))
    blocks=min(available_w//16,available_h//9)
    if blocks < 1:
        return None
    return 16*blocks,9*blocks


def adapt(window, width):
    """Fixed 150px navigation, freely sized video, 3–5 EPG rows."""
    if not getattr(window, '_synplus_ui', False) or getattr(window, '_synplus_in_fullscreen', False):
        return
    window._synplus_nav.set_visible(True)
    window._synplus_nav.set_size_request(195, -1)
    window.channel_menu.set_visible(width < 1140)
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
            if getattr(window,'_synplus_opening_ratio',False):
                # Remember the first allocated window size, not GTK's
                # preliminary zero-sized measurement. Only an actual change
                # in outer dimensions releases the 16:9 startup condition.
                outer=(window.get_width(),window.get_height())
                original=getattr(window,'_synplus_opening_window_size',None)
                if original is None and min(outer)>100:
                    window._synplus_opening_window_size=outer
                elif original is not None and (abs(outer[0]-original[0])>7 or
                                               abs(outer[1]-original[1])>7):
                    window._synplus_opening_ratio=False
            if getattr(window,'_synplus_opening_ratio',False):
                wanted=opening_player_geometry(cw,ch,8,4)
            else:
                wanted=player_geometry(cw, ch, 0, horizontal_margin=8, vertical_margin=4)
            if wanted and wanted != getattr(window,'_synplus_requested_video',None):
                # Initial frame is 16:9; after manual resize any ratio works.
                # The broadcast image itself keeps its native aspect ratio.
                frame.set_size_request(*wanted)
                window._synplus_requested_video=wanted
        elif (full_guide or cw < 16 or ch < 16) and getattr(window,'_synplus_requested_video',None):
            # Avoid keeping stale dimensions after a very small resize.
            frame.set_size_request(-1, -1)
            window._synplus_requested_video=None
    player_w = getattr(window,'_synplus_requested_video',(0,0))
    displayed_w = player_w[0] if player_w else 0
    window._synplus_compact = width < 1260 or (0 < displayed_w < 690)
    # The gradient is the same soft full-canvas ramp at any window size.
    if window._synplus_compact:
        window.add_css_class('synplus-compact-player')
    else:
        window.remove_css_class('synplus-compact-player')
    poll_chrome(window)


def fade_fullscreen_panels(window, GLib, showing, finished=None):
    """macOS-only 120/230ms alpha ramp for nav/list/EPG around native fullscreen.

    No video processing, no changes to Gdk.GLArea, mpv, or DVR. OS/GTK remains
    responsible for actual window-space animation. Other platforms untouched.
    """
    previous = getattr(window, '_synplus_panel_fade_id', 0)
    if previous:
        GLib.source_remove(previous)
        window._synplus_panel_fade_id = 0
    panels = [window._synplus_nav, window.sidebar, window.guide_surface]
    if showing:
        # Native compositor has already restored windowed geometry.
        for panel in panels:
            panel.set_opacity(0.0)
    else:
        # Before asking for fullscreen, fade the panels only, not the video.
        for panel in panels:
            panel.set_opacity(1.0)
    started = time.monotonic()
    duration = .23 if showing else .12

    def step():
        progress = min(1.0, (time.monotonic() - started) / duration)
        # Smoothstep: starts and stops without a hard jump.
        eased = progress * progress * (3.0 - 2.0 * progress)
        alpha = eased if showing else 1.0 - eased
        for panel in panels:
            panel.set_opacity(alpha)
        if progress >= 1.0:
            # Entry stays faded out until GTK hides the panels. Reset their
            # opacity only once hidden; otherwise one frame may flash.
            if showing:
                for panel in panels:
                    panel.set_opacity(1.0)
            window._synplus_panel_fade_id = 0
            if finished is not None:
                finished()
            return False
        return True

    window._synplus_panel_fade_id = GLib.timeout_add(16, step)


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
        cast_pop = getattr(window, '_synplus_cast_popover', None)
        if cast_pop is not None:
            cast_pop.popdown()
        window._synplus_cast_popover_open = False
        window._synplus_nav.set_visible(False)
        window.guide_surface.set_visible(False)
        for panel in (window._synplus_nav, window.sidebar, window.guide_surface):
            panel.set_opacity(1.0)
        # The stable fullscreen handler handles its own channel sidebar,
        # but SYN Plus has an independent host and guide outside the video.
        # Keep them hidden while the window itself is fullscreen.
        window._synplus_chrome_reveal.set_reveal_child(False)
        window._synplus_chrome_reveal.set_visible(False)
        window._synplus_chrome.set_visible(False)
        window.footer.set_visible(False)
        window.status.set_visible(False)
        window.add_css_class('synplus-pure-fullscreen')
        # The player frame stretches to the physical fullscreen surface.
        # libmpv, not GTK, letterboxes nonmatching broadcast aspect ratios.
        # No toolbar/rail/channel-list/EPG occupies space.
        window._synplus_gradient_reveal.set_reveal_child(False)
        window._synplus_gradient_reveal.set_visible(False)
        frame.set_size_request(-1, -1)
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
    window._synplus_mouse_over_video = False
    window._synplus_reveal_until = 0.0
    window._synplus_nav.set_visible(True)
    window._synplus_chrome.set_visible(True)
    window._synplus_chrome_reveal.set_visible(True)
    window._synplus_gradient_reveal.set_visible(True)
    if not window.guide_open and window._synplus_guide_requested:
        GLib.idle_add(lambda: (window.set_guide_open(True), False)[1])
    elif window.guide_open:
        window.guide_surface.set_visible(True)
    if getattr(window, '_synplus_pre_full_guide', False):
        GLib.idle_add(lambda: (set_guide_mode(window, GLib, True), False)[1])
    window._synplus_pre_full_guide = False
    # macOS: restore the side panels with a brief opacity transition.
    if sys.platform == 'darwin':
        fade_fullscreen_panels(window, GLib, True)
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
    btn.set_tooltip_text(tr('Perfiles')+' · %s' % p.get('name',tr('Mi televisión')))


def rebuild_profile_menu(window, Gtk):
    pop=window._synplus_avatar_menu
    old=pop.get_child()
    if old is not None: pop.set_child(None)
    root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
    for margin in ('top','bottom','start','end'):
        getattr(root,'set_margin_'+margin)(10)
    title=Gtk.Label(label=tr('Perfiles'),xalign=0)
    title.add_css_class('heading')
    root.append(title)
    for i,p in enumerate(window.cfg.get('profiles',[])):
        name=p.get('name',tr('Sin nombre'))
        btn=Gtk.Button(label=('✓  ' if p.get('id')==window.profile.get('id') else '    ')+name)
        btn.add_css_class('flat')
        btn.connect('clicked',lambda _b,index=i:(pop.popdown(),window.profile_picker.set_selected(index)))
        root.append(btn)
    root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
    add=Gtk.Button(label=tr('+  Añadir perfil'))
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




def mount_fullscreen_guide(window):
    """Expose the EXISTING EPG above libmpv, only in broadcast fullscreen.

    SYN Plus normally keeps guide_surface below its windowed video; the
    original fullscreen EPG button calls set_guide_open(True). Without this
    reparent, GTK makes the hidden, offscreen guide 'visible' but shows nothing.

    Only the guide widget is moved. Never unparent Gtk.GLArea, video overlay,
    mpv GL context, DVR worker, or any stream.
    """
    if not (getattr(window, '_synplus_ui', False)
            and getattr(window, '_synplus_in_fullscreen', False)):
        return False
    epg = window.guide_surface
    if getattr(window, '_synplus_fullscreen_guide', False):
        return True
    home = window._synplus_guide_home
    parent = epg.get_parent()
    if parent == home:
        home.remove(epg)
    elif parent == window.main_stack:
        window.main_stack.remove_overlay(epg)
    elif parent != window.overlay:
        # Unknown parent: do not destroy somebody else's layout.
        raise RuntimeError('SYN Plus: parent de la guía inesperado en fullscreen')
    if epg.get_parent() != window.overlay:
        window.overlay.add_overlay(epg)
        window.overlay.set_clip_overlay(epg, True)
        window.overlay.set_measure_overlay(epg, False)
    align = window._synplus_gtk.Align
    epg.set_vexpand(True)
    epg.set_hexpand(True)
    epg.set_halign(align.FILL)
    epg.set_valign(align.FILL)
    epg.set_size_request(-1, -1)
    epg.add_css_class('synplus-guide-full')
    window.guide_categories_scroll.set_visible(True)
    window.guide_search.set_visible(True)
    window._synplus_fullscreen_guide = True
    return True


def unmount_fullscreen_guide(window):
    """Return the EPG to its exact ordinary windowed home after Close/Escape.

    Hooked from set_guide_open(False), so *all* close routes restore it,
    including the header close button, Escape and leaving fullscreen.
    """
    if not getattr(window, '_synplus_fullscreen_guide', False):
        return False
    epg = window.guide_surface
    if epg.get_parent() == window.overlay:
        window.overlay.remove_overlay(epg)
    elif epg.get_parent() == window.main_stack:
        window.main_stack.remove_overlay(epg)
    home = window._synplus_guide_home
    if epg.get_parent() is None:
        home.append(epg)
    align = window._synplus_gtk.Align
    epg.set_vexpand(False)
    epg.set_hexpand(True)
    epg.set_halign(align.FILL)
    epg.set_valign(align.FILL)
    rows = getattr(window, '_synplus_rows', 3)
    epg.set_size_request(-1, 70 * rows + 119)
    epg.remove_css_class('synplus-guide-full')
    window.guide_categories_scroll.set_visible(False)
    window.guide_search.set_visible(False)
    window._guide_header_subtitle.set_visible(False)
    window._synplus_fullscreen_guide = False
    return True


def hold_chrome_for_cast(window, pop, Gtk):
    """Keep the mini-player toolbar mapped until the Cast popup closes.

    The GDK popover can extend outside the video rectangle. Pointer leave is
    *not* permission to unmap the Gtk.Revealer holding its anchor button.
    Set the preferred popup direction upward so the controls remain usable in
    compact windows; GTK may flip it if screen geometry requires.
    """
    if not getattr(window, '_synplus_ui', False):
        return
    previous = getattr(window, '_synplus_cast_popover', None)
    if previous is not None and previous is not pop:
        previous.popdown()
    window._synplus_cast_popover = pop
    window._synplus_cast_popover_open = True
    pop.set_position(Gtk.PositionType.TOP)
    def _closed(closed_pop):
        if getattr(window, '_synplus_cast_popover', None) is closed_pop:
            window._synplus_cast_popover = None
            window._synplus_cast_popover_open = False
            poll_chrome(window)
    pop.connect('closed', _closed)
    poll_chrome(window)


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
    fullscreen = getattr(window, '_synplus_in_fullscreen', False)
    visible = controls_visible(
        fullscreen,
        getattr(window, '_synplus_mouse_over_video', False),
        getattr(window, '_synplus_reveal_until', 0.0),
        time.monotonic())
    # A Cast popover outside the video must not collapse its parent toolbar.
    if not fullscreen and getattr(window, '_synplus_cast_popover_open', False):
        visible = True
    reveal.set_reveal_child(visible)
    # SAME state and CROSSFADE duration for shadow + text/buttons.
    gradient=getattr(window,'_synplus_gradient_reveal',None)
    if gradient is not None:
        gradient.set_reveal_child(visible)
    return True


def show_guide_page(window, GLib):
    """Route the SAME Guide action to windowed or broadcast fullscreen EPG.

    Alfa 2.6 fixed mounting the EPG, but this helper still silently refused
    to do anything when _synplus_in_fullscreen=True. The OSD button and G key
    both call here; use set_guide_open to keep original XMLTV/EPG state,
    channel filters, Escape, and context actions working.
    """
    fullscreen = (getattr(window, '_synplus_in_fullscreen', False)
                  or bool(window.fullscreen_mode) or bool(window.is_fullscreen()))
    if fullscreen:
        # Rare compositor timing case: GTK entered fullscreen before the
        # SYN Plus layout hook. Synchronize only the visual fullscreen state.
        if not getattr(window, '_synplus_in_fullscreen', False):
            fullscreen_changed(window, True, GLib)
        if getattr(window, '_synplus_fullscreen_guide', False):
            window.set_guide_open(False)
            return
        # An embedded EPG may have remained logically open but is invisible
        # beneath the hidden player column. Reset before opening over video.
        if window.guide_open:
            window.set_guide_open(False)
        window.set_guide_open(True)
        # Defensive for already-open state/early theme allocation.
        if not getattr(window, '_synplus_fullscreen_guide', False):
            mount_fullscreen_guide(window)
        window.guide_surface.set_visible(True)
        return
    cb=getattr(window, '_synplus_open_full_guide', None)
    if cb:
        cb()


# SYN classic refined: exactly the original two-line composition and graphic
# motifs, only the inks are less saturated and the accents less aggressive.
# No visual rebranding; real provider logos still take precedence.
# macOS system-palette-inspired pop colours. These are fallback graphics ONLY.
# Actual provider/custom logos remain fully untouched and take absolute priority.
CLASSIC_REFINED_PALETTES = (
    ((1.00,.69,.19),(.98,.40,.10),(.19,.12,.22)), # orange / papaya
    ((.34,.78,.95),(.02,.53,.89),(.06,.17,.31)), # cyan / blue
    ((1.00,.55,.67),(.97,.20,.43),(.28,.10,.22)), # pink
    ((.66,.87,.50),(.20,.68,.34),(.10,.24,.18)), # green
    ((.78,.67,.99),(.58,.36,.91),(.23,.13,.35)), # purple
    ((1.00,.79,.47),(.94,.58,.16),(.25,.17,.10)), # yellow
    ((.55,.83,.81),(.09,.54,.54),(.10,.20,.23)), # teal
    ((.97,.64,.59),(.91,.36,.28),(.27,.12,.12)), # coral
)


def draw_tv_sidebar_icon(area, cr, width, height):
    """Small TV outline, drawn locally; same dimensions as the Cine symbol."""
    if width <= 0 or height <= 0:
        return
    s = min(width, height) / 19.0
    cr.save()
    try:
        cr.translate((width - 19*s)/2, (height - 19*s)/2)
        cr.scale(s, s)
        dark = False
        if sys.platform == 'darwin':
            root = area.get_root()
            app = root.get_application() if root is not None else None
            manager = getattr(app, '_adw_manager', None)
            if manager is not None:
                dark = bool(manager.get_dark())
            else:
                from syn_macos_theme import is_dark
                dark = is_dark()
        cr.set_source_rgb(*((.98, .98, .99) if dark else (.10, .10, .12)))
        cr.set_line_width(1.65)
        # Rounded 16:10 screen: recognizable at 19px, no theme dependency.
        cr.move_to(4.4, 3.5)
        cr.line_to(14.6, 3.5)
        cr.curve_to(15.6, 3.5, 16.1, 4.0, 16.1, 5.0)
        cr.line_to(16.1, 12.2)
        cr.curve_to(16.1, 13.2, 15.6, 13.7, 14.6, 13.7)
        cr.line_to(4.4, 13.7)
        cr.curve_to(3.4, 13.7, 2.9, 13.2, 2.9, 12.2)
        cr.line_to(2.9, 5.0)
        cr.curve_to(2.9, 4.0, 3.4, 3.5, 4.4, 3.5)
        cr.close_path()
        cr.stroke()
        cr.move_to(9.5, 13.8)
        cr.line_to(9.5, 16.0)
        cr.move_to(6.4, 16.0)
        cr.line_to(12.6, 16.0)
        cr.stroke()
    finally:
        cr.restore()


def draw_vintage_movie_reel(area, cr, width, height):
    """Cine: classic five-spoke 35mm reel, thin engraved-style strokes."""
    import math
    s = min(width or 19,height or 19)/19.0
    if s <= 0:return
    cr.save()
    try:
        cr.translate((width-19*s)/2,(height-19*s)/2)
        cr.scale(s,s)
        # SYN_MAC_577_CINE_ICON: reflect the selected SYN theme, not just
        # the desktop theme. Otherwise it can disappear on dark surfaces.
        dark = False
        if sys.platform == 'darwin':
            root = area.get_root()
            app = root.get_application() if root is not None else None
            manager = getattr(app, '_adw_manager', None)
            if manager is not None:
                dark = bool(manager.get_dark())
            else:
                from syn_macos_theme import is_dark
                dark = is_dark()
        cr.set_source_rgb(*((.98,.98,.99) if dark else (.10,.10,.12)))
        cr.set_line_width(1.65)
        cr.arc(9.5,9.0,7.4,0,math.tau);cr.stroke()
        cr.arc(9.5,9.0,1.5,0,math.tau);cr.fill()
        for n in range(5):
            theta=n*math.tau/5-math.pi/2
            cr.arc(9.5+4.7*math.cos(theta),9.0+4.7*math.sin(theta),1.8,0,math.tau)
            cr.fill()
        cr.move_to(13.7,16.0);cr.line_to(17.9,17.9);cr.stroke()
    finally:cr.restore()

def draw_classic_refined_pill(window, area, cr, width, height):
    """Pop fallback generated live in Cairo; never replaces a genuine channel logo."""
    if getattr(area,'_syn_pixbuf',None) is not None:
        return window._draw_channel_logo(area, cr, width, height)
    if width <= 0 or height <= 0:return
    import math
    from syn_fallback_art import artwork_identity, artwork_lines
    name, group = getattr(area,'_syn_art_id',('SYN','TV'))
    idx, motif = artwork_identity(name,group)
    bg, shape, ink = CLASSIC_REFINED_PALETTES[idx % len(CLASSIC_REFINED_PALETTES)]
    title, subtitle = artwork_lines(name)
    cr.save()
    try:
        cr.scale(width/108.0,height/38.0)
        cr.set_source_rgb(*bg);cr.rectangle(0,0,108,38);cr.fill()
        cr.set_source_rgb(*shape)
        if motif == 0:
            cr.arc(96,7,32,0,math.tau);cr.fill()
            cr.set_source_rgb(1,1,1)
            for a in range(5):
                theta=a*math.tau/5
                cr.arc(92+15*math.cos(theta),10+15*math.sin(theta),4,0,math.tau);cr.fill()
        elif motif==1:
            cr.move_to(72,38);cr.line_to(98,-7);cr.line_to(112,-7)
            cr.line_to(112,38);cr.close_path();cr.fill()
            cr.set_source_rgb(1,1,1);cr.arc(98,27,7,0,math.tau);cr.fill()
        elif motif==2:
            for j in range(3):
                cr.rectangle(85+j*10,-3,5,47);cr.fill()
        elif motif==3:
            cr.arc(98,20,22,0,math.tau);cr.fill()
            cr.set_source_rgb(1,1,1);cr.arc(98,20,10,0,math.tau);cr.fill()
        else:
            cr.set_line_width(9)
            cr.move_to(79,35);cr.curve_to(94,-12,101,40,114,6);cr.stroke()
        # Editorial pop typography with true high-contrast, readable labels.
        cr.set_source_rgb(*ink)
        cr.select_font_face('Sans',0,1)
        cr.set_font_size(10.2 if len(title)<=9 else 7.7)
        cr.move_to(7,16);cr.show_text(title)
        cr.select_font_face('Sans',0,0)
        cr.set_font_size(6.8 if len(subtitle)<=13 else 5.7)
        cr.move_to(7,29);cr.show_text(subtitle)
    finally:cr.restore()
