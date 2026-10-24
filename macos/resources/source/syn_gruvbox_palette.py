"""SYN 1.3.6beta10 — Gruvbox light/dark (medium), original Morhetz palette.

GTK-only palettes; does not change video colours, GL, DVR logic or channel art.
The POP EPG gradients from beta9 deliberately retain precedence.
"""
from __future__ import annotations
import re

COLORS = {
 'dark0': '#282828', 'dark1': '#3c3836', 'dark2': '#504945',
 'dark3': '#665c54', 'dark4': '#7c6f64',
 'light0': '#fbf1c7', 'light1': '#ebdbb2', 'light2': '#d5c4a1',
 'light3': '#bdae93', 'light4': '#a89984',
 'bright_red': '#fb4934', 'bright_green': '#b8bb26',
 'bright_yellow': '#fabd2f', 'bright_blue': '#83a598',
 'bright_purple': '#d3869b', 'bright_aqua': '#8ec07c',
 'bright_orange': '#fe8019',
 'red': '#cc241d', 'green': '#98971a', 'yellow': '#d79921',
 'blue': '#458588', 'purple': '#b16286', 'aqua': '#689d6a',
 'orange': '#d65d0e',
 'faded_red': '#9d0006', 'faded_green': '#79740e',
 'faded_yellow': '#b57614', 'faded_blue': '#076678',
 'faded_purple': '#8f3f71', 'faded_aqua': '#427b58',
 'faded_orange': '#af3a03',
}
ACCENTS = (
 ('Rojo', COLORS['red']), ('Verde', COLORS['green']),
 ('Amarillo', COLORS['yellow']), ('Azul', COLORS['blue']),
 ('Morado', COLORS['purple']), ('Aqua', COLORS['aqua']),
 ('Naranja', COLORS['orange']),
)


def _luminance(color):
    values = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
    channels = [x/12.92 if x <= .04045 else ((x + .055)/1.055)**2.4 for x in values]
    return sum(v*w for v, w in zip(channels, (.2126,.7152,.0722)))


def readable_ink(color):
    """Choose gruvbox dark or light text by actual WCAG contrast."""
    l = _luminance(color)
    dark = COLORS['dark0']; light = COLORS['light0']
    ld, ll = _luminance(dark), _luminance(light)
    return dark if (l+.05)/(ld+.05) >= (ll+.05)/(l+.05) else light


# Strongly scoped to SYN; preserving shape and geometry of every widget.
# The EPGBeta9 gradient rules are appended AFTER these, never overridden here.
CSS = r'''
window.iptv-tv, window.iptv-tv .iptv-surface,
window.syn-settings-window { background-color: %%BG%%; color: %%FG%%; }
window.iptv-tv .iptv-header, window.iptv-tv headerbar {
 background-color: %%BAR%%; color: %%FG%%; border-bottom: 1px solid %%STROKE%%;
}
window.iptv-tv .iptv-heading, window.iptv-tv .iptv-channel,
window.iptv-tv .iptv-placeholder, window.iptv-tv .syn-channel-display-name,
window.iptv-tv .syn-favorite-display-name { color: %%FG%%; }
window.iptv-tv .iptv-info, window.iptv-tv .iptv-details,
window.iptv-tv .iptv-group, window.iptv-tv .iptv-subtitle {color: %%MUTED%%;}
window.iptv-tv .iptv-sidebar { background-color: %%PANEL%%; border-right:1px solid %%STROKE%%; }
window.iptv-tv .iptv-list, window.iptv-tv listbox {background-color:transparent; color:%%FG%%;}
window.iptv-tv .iptv-row {background-color:%%CARD%%; color:%%FG%%; border:1px solid %%STROKE%%; border-radius:10px; margin:2px 6px;}
window.iptv-tv .iptv-row:hover {background-color:%%HOVER%%;}
window.iptv-tv .iptv-row:selected {background-color:%%SELECTED%%; border-color:%%ACCENT%%;}
window.iptv-tv .iptv-row:selected label {color:%%FG%%;}
window.iptv-tv .iptv-search, window.iptv-tv .iptv-dropdown,
window.iptv-tv .iptv-toolbar {background-color:%%PANEL%%; color:%%FG%%; border-color:%%STROKE%%;}
window.iptv-tv .iptv-video { background-color:#000000; }
window.iptv-tv button, window.iptv-tv entry, window.iptv-tv searchentry,
window.iptv-tv dropdown, window.iptv-tv spinbutton,
window.syn-settings-window button, window.syn-settings-window entry,
window.syn-settings-window dropdown, window.syn-settings-window passwordentry,
window.syn-settings-window spinbutton {background-color:%%INPUT%%; color:%%FG%%; border:1px solid %%STROKE%%; border-radius:10px;}
window.iptv-tv button:hover, window.syn-settings-window button:hover { background-color:%%HOVER%%; color:%%FG%%; }
window.iptv-tv button.iptv-accent, window.iptv-tv button:checked,
window.iptv-tv togglebutton:checked, window.syn-settings-window button.suggested-action {
 background-color:%%ACCENT%%; border-color:%%ACCENT%%; color:%%ACCENT_FG%%;
}
window.iptv-tv button.iptv-accent label, window.iptv-tv button:checked label {color:%%ACCENT_FG%%;}
window.iptv-tv .iptv-icon, window.iptv-tv .syn-portal-kicker,
window.iptv-tv .syn-portal-counter {color:%%ACCENT%%;}
window.iptv-tv scale highlight {background-color:%%ACCENT%%;}
window.iptv-tv separator, window.syn-settings-window separator {background-color:%%STROKE%%;}
window.iptv-tv scrollbar slider, window.syn-settings-window scrollbar slider {background-color:%%SCROLL%%;}
window.syn-settings-window label {color:%%FG%%;}
window.syn-settings-window .syn-pref-muted, window.syn-settings-window .iptv-details {color:%%MUTED%%;}
window.syn-settings-window .syn-pref-group {background-color:%%CARD%%; border-color:%%STROKE%%;}
window.syn-settings-window .syn-pref-header, window.syn-settings-window .syn-pref-footer,
window.syn-settings-window .syn-pref-sidebar {border-color:%%STROKE%%;}
window.syn-settings-window button.syn-pref-theme:checked {background-color:%%SELECTED%%; border:2px solid %%ACCENT%%;}
/* Perfil, cine y series */
window.iptv-tv .syn-portal-root {background-color:%%BG%%; color:%%FG%%;}
window.iptv-tv .syn-portal-top {background-color:%%BAR%%; border-bottom:1px solid %%STROKE%%;}
window.iptv-tv .syn-portal-title, window.iptv-tv .syn-portal-hero,
window.iptv-tv .syn-portal-tile-title, window.iptv-tv .syn-portal-poster-name {color:%%FG%%;}
window.iptv-tv .syn-portal-poster-group {color:%%MUTED%%;}
window.iptv-tv button.syn-portal-tile, window.iptv-tv button.syn-portal-poster-card {
 background-image:none; background-color:%%CARD%%; border:1px solid %%STROKE%%; color:%%FG%%;
}
window.iptv-tv button.syn-portal-tile:hover, window.iptv-tv button.syn-portal-poster-card:hover {
 background-color:%%HOVER%%; border-color:%%ACCENT%%;
}
window.iptv-tv .syn-portal-orb, window.iptv-tv .syn-portal-poster {background-color:%%SELECTED%%;}
window.iptv-tv .syn-portal-orb-icon {color:%%ACCENT%%;}
window.iptv-tv .syn-portal-orb-series, window.iptv-tv .syn-portal-orb-movies {background-color:%%HOVER%%;}
window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon,
window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon {color:%%ACCENT%%;}
/* EPG containers and controls. Programme tiles keep beta9 gradients. */
window.iptv-tv .syn-guide-backdrop {background-color:%%BG%%;color:%%FG%%;}
window.iptv-tv .syn-guide-header, window.iptv-tv .syn-guide-axis {background-color:%%BAR%%;border-color:%%STROKE%%;}
window.iptv-tv .syn-guide-categories, window.iptv-tv .syn-guide-track {background-color:%%PANEL%%;}
window.iptv-tv .syn-guide-channel, window.iptv-tv .syn-guide-head-button {background-color:%%CARD%%;color:%%FG%%;}
window.iptv-tv .syn-guide-channel-playing {background-color:%%SELECTED%%;}
window.iptv-tv .syn-guide-cat, window.iptv-tv .syn-guide-channel-name,
window.iptv-tv .syn-guide-title, window.iptv-tv .syn-guide-time {color:%%FG%%;}
window.iptv-tv .syn-guide-muted, window.iptv-tv .syn-guide-footer {color:%%MUTED%%;}
window.iptv-tv .syn-guide-cat.active {background-color:%%SELECTED%%;color:%%FG%%; border-left:3px solid %%ACCENT%%;}
window.iptv-tv .syn-guide-footer {background-color:%%BAR%%;}
window.iptv-tv .syn-guide-current {border-color:%%ACCENT%%;}
window.iptv-tv .syn-guide-now-line {background-color:%%ACCENT%%;}
window.iptv-tv .syn-guide-gap {background-color:%%CARD%%; color:%%MUTED%%;}
/* DVR */
window.iptv-tv .syn-dvr-page, window.iptv-tv .syn-dvr-page scrolledwindow {background-color:%%BG%%;color:%%FG%%;}
window.iptv-tv .syn-dvr-page list.boxed-list, window.iptv-tv .syn-dvr-page button,
window.iptv-tv .syn-dvr-page entry, window.iptv-tv .syn-dvr-page dropdown > button {
 background-color:%%CARD%%;color:%%FG%%;border-color:%%STROKE%%;
}
window.iptv-tv .syn-dvr-page label {color:%%FG%%;}
window.iptv-tv .syn-dvr-page .dim-label {color:%%MUTED%%;}
window.iptv-tv .syn-dvr-page list.boxed-list > row:hover {background-color:%%HOVER%%;}
window.iptv-tv .syn-dvr-page calendar grid label.today:not(:selected) {box-shadow:inset 0 0 0 1px %%ACCENT%%;}
window.iptv-tv .syn-dvr-page calendar grid label:selected {background-color:%%ACCENT%%;color:%%ACCENT_FG%%;}
window.iptv-tv .syn-dvr-page button.syn-dvr-schedule-action {background-color:%%ACCENT%%;color:%%ACCENT_FG%%;border-color:%%ACCENT%%;}
/* Zapping: no changes to actual video */
window.iptv-tv .syn-zap-panel {color:%%FG%%;}
window.iptv-tv .syn-zap-row {background-color:%%CARD%%;border-color:%%STROKE%%;}
window.iptv-tv .syn-zap-row:hover {background-color:%%HOVER%%;}
window.iptv-tv .syn-zap-row.syn-zap-playing {background-color:%%SELECTED%%;border-color:%%ACCENT%%;}
window.iptv-tv .syn-zap-title, window.iptv-tv .syn-zap-name {color:%%FG%%;}
'''


def gruvbox_css(theme, accent_hex=''):
    if theme not in ('gruvbox-light', 'gruvbox-dark'):
        raise ValueError('Tema Gruvbox no válido: ' + str(theme))
    dark = theme == 'gruvbox-dark'
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', accent_hex or ''):
        accent_hex = COLORS['bright_orange'] if dark else COLORS['orange']
    accent_hex = accent_hex.upper()
    if dark:
        roles = dict(BG=COLORS['dark0'], PANEL=COLORS['dark1'], BAR=COLORS['dark1'],
                     CARD=COLORS['dark2'], INPUT=COLORS['dark2'], HOVER=COLORS['dark3'],
                     SELECTED=COLORS['dark3'], FG=COLORS['light1'], MUTED=COLORS['light3'],
                     STROKE=COLORS['dark4'], SCROLL=COLORS['dark4'])
    else:
        roles = dict(BG=COLORS['light0'], PANEL=COLORS['light1'], BAR=COLORS['light1'],
                     CARD=COLORS['light0'], INPUT=COLORS['light0'], HOVER=COLORS['light2'],
                     SELECTED=COLORS['light2'], FG=COLORS['dark1'], MUTED=COLORS['dark3'],
                     STROKE=COLORS['light3'], SCROLL=COLORS['dark4'])
    roles['ACCENT'] = accent_hex
    roles['ACCENT_FG'] = readable_ink(accent_hex)
    css = CSS
    for key, value in roles.items():
        css = css.replace('%%' + key + '%%', value)
    if re.search(r'%%[A-Z_0-9]+%%', css):
        raise AssertionError('Marcadores de paleta Gruvbox sin resolver')
    return css
