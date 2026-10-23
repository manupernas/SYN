"""Official Nord (nord0..nord15) palettes for SYN GTK4.

This module deliberately contains only theme data & CSS. It never touches mpv,
DVR, source credentials, profiles or GNOME launchers.
"""
from __future__ import annotations
import re

NORD = (
    '#2E3440', '#3B4252', '#434C5E', '#4C566A',
    '#D8DEE9', '#E5E9F0', '#ECEFF4',
    '#8FBCBB', '#88C0D0', '#81A1C1', '#5E81AC',
    '#BF616A', '#D08770', '#EBCB8B', '#A3BE8C', '#B48EAD',
)
AURORA = {'rojo': NORD[11], 'naranja': NORD[12], 'amarillo': NORD[13],
          'verde': NORD[14], 'violeta': NORD[15]}
FROST = NORD[8]


def contrast_ink(color):
    """WCAG luminance, dark or white readable text against the chosen accent."""
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', color or ''):
        raise ValueError('Se esperaba un color hexadecimal RGB.')
    rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    lin = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    luminance = .2126*lin[0] + .7152*lin[1] + .0722*lin[2]
    # Choose the option with superior contrast ratio.
    return '#2E3440' if (luminance + .05) / .05 >= 1.05 / (luminance + .05) else '#ECEFF4'


CSS = r'''
/* SYN Nord: Snow Storm / Polar Night, official Nord palette.
   Accent defaults to nord8 Frost; Aurora options choose nord11..15. */
window.iptv-tv, window.iptv-tv .iptv-surface,
window.syn-settings-window {
    background-color: %%BG%%; color: %%FG%%;
}
window.iptv-tv .iptv-header, window.iptv-tv headerbar {
    background-color: %%BAR%%; color: %%FG%%;
    border-bottom: 1px solid %%STROKE%%;
}
window.iptv-tv .iptv-heading,
window.iptv-tv .iptv-channel, window.iptv-tv .iptv-placeholder,
window.iptv-tv .syn-channel-display-name,
window.iptv-tv .syn-favorite-display-name { color: %%FG%%; }
window.iptv-tv .iptv-group, window.iptv-tv .iptv-details,
window.iptv-tv .iptv-subtitle, window.iptv-tv .iptv-info {
    color: %%MUTED%%;
}
window.iptv-tv .iptv-sidebar {
    background-color: %%PANEL%%;
    border-right: 1px solid %%STROKE%%;
}
window.iptv-tv .iptv-list, window.iptv-tv listbox {
    background-color: transparent; color: %%FG%%;
}
window.iptv-tv .iptv-row {
    background-color: %%CARD%%; color: %%FG%%;
    border: 1px solid %%STROKE%%;
    border-radius: 10px; margin: 2px 6px;
}
window.iptv-tv .iptv-row:hover { background-color: %%HOVER%%; }
window.iptv-tv .iptv-row:selected {
    background-color: %%SELECTED%%;
    border-color: %%ACCENT%%;
}
window.iptv-tv .iptv-row:selected label { color: %%FG%%; }
window.iptv-tv .iptv-search, window.iptv-tv .iptv-dropdown {
    background-color: %%INPUT%%; color: %%FG%%;
    border-color: %%STROKE%%;
}
window.iptv-tv .iptv-toolbar {
    background-color: %%BAR%%; color: %%FG%%;
    border-top: 1px solid %%STROKE%%;
}
window.iptv-tv .iptv-video { background-color: #000000; }
window.iptv-tv .iptv-icon, window.iptv-tv .syn-portal-kicker,
window.iptv-tv .syn-portal-counter { color: %%ACCENT%%; }
window.iptv-tv button, window.iptv-tv entry,
window.iptv-tv searchentry, window.iptv-tv dropdown,
window.iptv-tv spinbutton, window.syn-settings-window button,
window.syn-settings-window entry, window.syn-settings-window dropdown,
window.syn-settings-window passwordentry, window.syn-settings-window spinbutton {
    background-color: %%INPUT%%; color: %%FG%%;
    border: 1px solid %%STROKE%%;
    border-radius: 10px;
}
window.iptv-tv button:hover, window.syn-settings-window button:hover {
    background-color: %%HOVER%%; color: %%FG%%;
}
window.iptv-tv button.iptv-accent,
window.syn-settings-window button.suggested-action,
window.iptv-tv button:checked,
window.iptv-tv togglebutton:checked {
    background-color: %%ACCENT%%; color: %%ACCENT_FG%%;
    border-color: %%ACCENT%%;
}
window.iptv-tv button.iptv-accent label,
window.iptv-tv button:checked label { color: %%ACCENT_FG%%; }
window.iptv-tv scale highlight { background-color: %%ACCENT%%; }
window.iptv-tv separator, window.syn-settings-window separator {
    background-color: %%STROKE%%;
}
window.iptv-tv scrollbar slider, window.syn-settings-window scrollbar slider {
    background-color: %%SCROLL%%;
}
window.syn-settings-window label { color: %%FG%%; }
window.syn-settings-window .syn-pref-muted,
window.syn-settings-window .iptv-details { color: %%MUTED%%; }
window.syn-settings-window .syn-pref-group {
    background-color: %%CARD%%; border-color: %%STROKE%%;
}
window.syn-settings-window .syn-pref-header,
window.syn-settings-window .syn-pref-footer,
window.syn-settings-window .syn-pref-sidebar { border-color: %%STROKE%%; }
window.syn-settings-window button.syn-pref-theme:checked {
    border: 2px solid %%ACCENT%%;
    background-color: %%SELECTED%%;
}
/* Profiles / movies / series */
window.iptv-tv .syn-portal-root { background-color: %%BG%%; color: %%FG%%; }
window.iptv-tv .syn-portal-top {
    background-color: %%BAR%%; border-bottom: 1px solid %%STROKE%%;
}
window.iptv-tv .syn-portal-title,
window.iptv-tv .syn-portal-hero,
window.iptv-tv .syn-portal-tile-title,
window.iptv-tv .syn-portal-poster-name { color: %%FG%%; }
window.iptv-tv .syn-portal-poster-group { color: %%MUTED%%; }
window.iptv-tv button.syn-portal-tile,
window.iptv-tv button.syn-portal-poster-card {
    background-image: none; background-color: %%CARD%%;
    border: 1px solid %%STROKE%%; color: %%FG%%;
}
window.iptv-tv button.syn-portal-tile:hover,
window.iptv-tv button.syn-portal-poster-card:hover {
    background-color: %%HOVER%%; border-color: %%ACCENT%%;
}
window.iptv-tv .syn-portal-orb,
window.iptv-tv .syn-portal-poster { background-color: %%SELECTED%%; }
window.iptv-tv .syn-portal-orb-icon { color: %%FROST%%; }
window.iptv-tv .syn-portal-orb-series { background-color: %%SERIES%%; }
window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon { color: %%SERIES_FG%%; }
window.iptv-tv .syn-portal-orb-movies { background-color: %%MOVIES%%; }
window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon { color: %%MOVIES_FG%%; }
/* EPG · Aurora programme bars */
window.iptv-tv .syn-guide-backdrop {
    background-color: %%GUIDE%%; color: %%FG%%;
}
window.iptv-tv .syn-guide-header,
window.iptv-tv .syn-guide-axis { background-color: %%BAR%%; border-color: %%STROKE%%; }
window.iptv-tv .syn-guide-categories,
window.iptv-tv .syn-guide-track { background-color: %%PANEL%%; }
window.iptv-tv .syn-guide-channel,
window.iptv-tv .syn-guide-head-button { background-color: %%CARD%%; color: %%FG%%; }
window.iptv-tv .syn-guide-channel-playing { background-color: %%SELECTED%%; }
window.iptv-tv .syn-guide-cat,
window.iptv-tv .syn-guide-channel-name,
window.iptv-tv .syn-guide-title,
window.iptv-tv .syn-guide-time,
window.iptv-tv .syn-guide-program-name { color: %%FG%%; }
window.iptv-tv .syn-guide-muted,
window.iptv-tv .syn-guide-footer { color: %%MUTED%%; }
window.iptv-tv .syn-guide-cat.active {
    background-color: %%SELECTED%%;
    color: %%FG%%; border-left: 3px solid %%ACCENT%%;
}
window.iptv-tv .syn-guide-cat.active label { color: %%FG%%; }
window.iptv-tv .syn-guide-footer { background-color: %%BAR%%; }
window.iptv-tv .syn-guide-program { border: 1px solid %%STROKE%%; color: %%FG%%; }
window.iptv-tv .syn-guide-program-0 { background-color: %%PROGRAM_0%%; }
window.iptv-tv .syn-guide-program-1 { background-color: %%PROGRAM_1%%; }
window.iptv-tv .syn-guide-program-2 { background-color: %%PROGRAM_2%%; }
window.iptv-tv .syn-guide-program-3 { background-color: %%PROGRAM_3%%; }
window.iptv-tv .syn-guide-program-4 { background-color: %%PROGRAM_4%%; }
window.iptv-tv .syn-guide-program-5 { background-color: %%PROGRAM_5%%; }
window.iptv-tv .syn-guide-current { border-color: %%ACCENT%%; }
window.iptv-tv .syn-guide-now-line { background-color: %%ACCENT%%; }
window.iptv-tv .syn-guide-gap { background-color: %%CARD%%; color: %%MUTED%%; }
/* DVR */
window.iptv-tv .syn-dvr-page,
window.iptv-tv .syn-dvr-page scrolledwindow {
    background-color: %%BG%%; color: %%FG%%;
}
window.iptv-tv .syn-dvr-page list.boxed-list,
window.iptv-tv .syn-dvr-page button,
window.iptv-tv .syn-dvr-page entry,
window.iptv-tv .syn-dvr-page dropdown > button {
    background-color: %%CARD%%; color: %%FG%%; border-color: %%STROKE%%;
}
window.iptv-tv .syn-dvr-page label { color: %%FG%%; }
window.iptv-tv .syn-dvr-page .dim-label { color: %%MUTED%%; }
window.iptv-tv .syn-dvr-page list.boxed-list > row:hover { background-color: %%HOVER%%; }
window.iptv-tv .syn-dvr-page calendar grid label.today:not(:selected) {
    box-shadow: inset 0 0 0 1px %%ACCENT%%;
}
window.iptv-tv .syn-dvr-page calendar grid label:selected {
    background-color: %%ACCENT%%; color: %%ACCENT_FG%%;
}
window.iptv-tv .syn-dvr-page button.syn-dvr-schedule-action {
    background-color: %%ACCENT%%; color: %%ACCENT_FG%%; border-color: %%ACCENT%%;
}
/* Zapping. Video itself is never tinted. */
window.iptv-tv .syn-zap-panel { color: %%FG%%; }
window.iptv-tv .syn-zap-row { background-color: %%CARD%%; border-color: %%STROKE%%; }
window.iptv-tv .syn-zap-row:hover { background-color: %%HOVER%%; }
window.iptv-tv .syn-zap-row.syn-zap-playing {
    background-color: %%SELECTED%%; border-color: %%ACCENT%%;
}
window.iptv-tv .syn-zap-title,
window.iptv-tv .syn-zap-name { color: %%FG%%; }
'''


def nord_css(theme: str, accent_hex: str = '') -> str:
    """Return Nord GTK4 CSS, safe to load as a CssProvider data string."""
    if theme not in ('nord-light', 'nord-dark'):
        raise ValueError(f'Tema Nord desconocido: {theme}')
    accent = accent_hex.upper() if accent_hex else FROST
    if not re.fullmatch(r'#[0-9A-F]{6}', accent):
        accent = FROST
    dark = theme == 'nord-dark'
    if dark:
        roles = dict(BG=NORD[0], PANEL=NORD[1], BAR=NORD[1], CARD=NORD[2],
                     INPUT=NORD[2], HOVER=NORD[3], SELECTED=NORD[3],
                     FG=NORD[6], MUTED=NORD[4], STROKE=NORD[3], SCROLL=NORD[3],
                     GUIDE=NORD[0], FROST=NORD[8], SERIES=NORD[3],
                     SERIES_FG=NORD[6], MOVIES=NORD[3], MOVIES_FG=NORD[6])
        opacities = ('.35', '.32', '.30', '.32', '.33', '.31')
    else:
        roles = dict(BG=NORD[6], PANEL=NORD[5], BAR=NORD[5], CARD=NORD[6],
                     INPUT=NORD[6], HOVER=NORD[4], SELECTED=NORD[4],
                     FG=NORD[0], MUTED=NORD[3], STROKE=NORD[4], SCROLL=NORD[3],
                     GUIDE=NORD[6], FROST=NORD[10], SERIES=NORD[4],
                     SERIES_FG=NORD[0], MOVIES=NORD[4], MOVIES_FG=NORD[0])
        opacities = ('.18', '.22', '.24', '.21', '.20', '.25')
    roles['ACCENT'] = accent
    roles['ACCENT_FG'] = contrast_ink(accent)
    for i, index in enumerate((11, 12, 13, 14, 15, 9)):
        # GTK's alpha(color, value) function allows Nord Aurora tinting without
        # arbitrary off-palette colours. Programme tiles retain legible text.
        roles[f'PROGRAM_{i}'] = f'alpha({NORD[index]}, {opacities[i]})'
    css = CSS
    for key, value in roles.items():
        css = css.replace('%%' + key + '%%', value)
    if re.search(r'%%[A-Z_0-9]+%%', css):
        raise AssertionError('Nord CSS contiene marcadores sin resolver')
    return css
