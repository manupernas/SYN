"""Dracula Classic / Alucard Classic for SYN GTK4 (2.0.9 preview).

Palettes: https://draculatheme.com/spec -- colour data only; no player changes.
"""
from __future__ import annotations
import re

COLORS = {
    'dracula': {
        'background': '#282A36', 'foreground': '#F8F8F2',
        'selection': '#44475A', 'comment': '#6272A4',
        'red': '#FF5555', 'orange': '#FFB86C', 'yellow': '#F1FA8C',
        'green': '#50FA7B', 'cyan': '#8BE9FD', 'purple': '#BD93F9',
        'pink': '#FF79C6',
        'floating': '#343746', 'lighter': '#424450',
        'light': '#343746', 'dark': '#21222C', 'darker': '#191A21',
    },
    'alucard': {
        'background': '#FFFBEB', 'foreground': '#1F1F1F',
        'selection': '#CFCFDE', 'comment': '#6C664B',
        'red': '#CB3A2A', 'orange': '#A34D14', 'yellow': '#846E15',
        'green': '#14710A', 'cyan': '#036A96', 'purple': '#644AC9',
        'pink': '#A3144D',
        'floating': '#EFEDDC', 'lighter': '#ECE9DF',
        'light': '#DEDCCF', 'dark': '#CECCC0', 'darker': '#BCBAB3',
    },
}

ACCENT_NAMES = ('red', 'orange', 'yellow', 'green', 'cyan', 'purple', 'pink')


def _luminance(color):
    rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
    return sum(a*b for a, b in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    aa, bb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (aa + .05) / (bb + .05)


def readable_ink(bg, variant):
    """Use whichever of the variant's official text/background gives more contrast."""
    scheme = COLORS[variant]
    options = (scheme['foreground'], scheme['background'], '#191A21', '#FFFFFF')
    return max(options, key=lambda fg: contrast(bg, fg))


# Strongly scoped: no changes to video surface, libmpv, DVR logic or EPG event colours.
CSS = r'''
window.iptv-tv, window.iptv-tv .iptv-surface,
window.syn-settings-window { background-color:%%BG%%; color:%%FG%%; }
window.iptv-tv .iptv-header, window.iptv-tv headerbar {
 background-color:%%BAR%%; color:%%FG%%; border-bottom:1px solid %%STROKE%%; }
window.iptv-tv .iptv-heading, window.iptv-tv .iptv-channel,
window.iptv-tv .iptv-placeholder, window.iptv-tv .syn-channel-display-name,
window.iptv-tv .syn-favorite-display-name { color:%%FG%%; }
window.iptv-tv .iptv-info, window.iptv-tv .iptv-details,
window.iptv-tv .iptv-group, window.iptv-tv .iptv-subtitle { color:%%MUTED%%; }
window.iptv-tv .iptv-sidebar { background-color:%%PANEL%%; border-right:1px solid %%STROKE%%; }
window.iptv-tv .iptv-list, window.iptv-tv listbox { background-color:transparent; color:%%FG%%; }
window.iptv-tv .iptv-row { background-color:%%CARD%%; color:%%FG%%;
 border:1px solid %%STROKE%%; border-radius:10px; margin:2px 6px; }
window.iptv-tv .iptv-row:hover { background-color:%%HOVER%%; }
window.iptv-tv .iptv-row:selected { background-color:%%SELECTED%%; border-color:%%ACCENT%%; }
window.iptv-tv .iptv-row:selected label { color:%%FG%%; }
window.iptv-tv .iptv-search, window.iptv-tv .iptv-dropdown,
window.iptv-tv .iptv-toolbar { background-color:%%PANEL%%; color:%%FG%%; border-color:%%STROKE%%; }
window.iptv-tv .iptv-video { background-color:#000000; }
window.iptv-tv button, window.iptv-tv entry, window.iptv-tv searchentry,
window.iptv-tv dropdown, window.iptv-tv spinbutton,
window.syn-settings-window button, window.syn-settings-window entry,
window.syn-settings-window dropdown, window.syn-settings-window passwordentry,
window.syn-settings-window spinbutton { background-color:%%INPUT%%; color:%%FG%%;
 border:1px solid %%STROKE%%; border-radius:10px; }
window.iptv-tv button:hover, window.syn-settings-window button:hover {
 background-color:%%HOVER%%; color:%%FG%%; }
window.iptv-tv button.iptv-accent, window.iptv-tv button:checked,
window.iptv-tv togglebutton:checked, window.syn-settings-window button.suggested-action {
 background-color:%%ACCENT%%; border-color:%%ACCENT%%; color:%%ACCENT_FG%%; }
window.iptv-tv button.iptv-accent label, window.iptv-tv button:checked label,
window.iptv-tv togglebutton:checked label { color:%%ACCENT_FG%%; }
window.iptv-tv .iptv-icon, window.iptv-tv .syn-portal-kicker,
window.iptv-tv .syn-portal-counter { color:%%ACCENT%%; }
window.iptv-tv scale highlight { background-color:%%ACCENT%%; }
window.iptv-tv separator, window.syn-settings-window separator { background-color:%%STROKE%%; }
window.iptv-tv scrollbar slider, window.syn-settings-window scrollbar slider { background-color:%%SCROLL%%; }
window.syn-settings-window label { color:%%FG%%; }
window.syn-settings-window .syn-pref-muted,
window.syn-settings-window .iptv-details { color:%%MUTED%%; }
window.syn-settings-window .syn-pref-group { background-color:%%CARD%%; border-color:%%STROKE%%; }
window.syn-settings-window .syn-pref-header, window.syn-settings-window .syn-pref-footer,
window.syn-settings-window .syn-pref-sidebar { border-color:%%STROKE%%; }
window.syn-settings-window button.syn-pref-theme:checked {
 background-color:%%SELECTED%%; border:2px solid %%ACCENT%%; color:%%FG%%; }
window.syn-settings-window button.syn-pref-swatch { border:1px solid %%STROKE%%; }
/* Portal, films and series */
window.iptv-tv .syn-portal-root { background-color:%%BG%%; color:%%FG%%; }
window.iptv-tv .syn-portal-top { background-color:%%BAR%%; border-bottom:1px solid %%STROKE%%; }
window.iptv-tv .syn-portal-title, window.iptv-tv .syn-portal-hero,
window.iptv-tv .syn-portal-tile-title, window.iptv-tv .syn-portal-poster-name { color:%%FG%%; }
window.iptv-tv .syn-portal-poster-group { color:%%MUTED%%; }
window.iptv-tv button.syn-portal-tile, window.iptv-tv button.syn-portal-poster-card {
 background-image:none; background-color:%%CARD%%; border:1px solid %%STROKE%%; color:%%FG%%; }
window.iptv-tv button.syn-portal-tile:hover, window.iptv-tv button.syn-portal-poster-card:hover {
 background-color:%%HOVER%%; border-color:%%ACCENT%%; }
window.iptv-tv .syn-portal-orb, window.iptv-tv .syn-portal-poster { background-color:%%SELECTED%%; }
window.iptv-tv .syn-portal-orb-icon { color:%%ACCENT%%; }
window.iptv-tv .syn-portal-orb-series, window.iptv-tv .syn-portal-orb-movies { background-color:%%HOVER%%; }
window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon,
window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon { color:%%ACCENT%%; }
/* EPG containers only. Ten per-programme gradients come from syn_epg_pop. */
window.iptv-tv .syn-guide-backdrop { background-color:%%BG%%; color:%%FG%%; }
window.iptv-tv .syn-guide-header, window.iptv-tv .syn-guide-axis {
 background-color:%%BAR%%; border-color:%%STROKE%%; }
window.iptv-tv .syn-guide-categories, window.iptv-tv .syn-guide-track {
 background-color:%%PANEL%%; }
window.iptv-tv .syn-guide-channel, window.iptv-tv .syn-guide-head-button {
 background-color:%%CARD%%; color:%%FG%%; }
window.iptv-tv .syn-guide-channel-playing { background-color:%%SELECTED%%; }
window.iptv-tv .syn-guide-cat, window.iptv-tv .syn-guide-channel-name,
window.iptv-tv .syn-guide-title { color:%%FG%%; }
window.iptv-tv .syn-guide-muted, window.iptv-tv .syn-guide-footer { color:%%MUTED%%; }
window.iptv-tv .syn-guide-cat.active { background-color:%%SELECTED%%;
 color:%%FG%%; border-left:3px solid %%ACCENT%%; }
window.iptv-tv .syn-guide-footer { background-color:%%BAR%%; }
window.iptv-tv .syn-guide-current { border-color:%%ACCENT%%; }
window.iptv-tv .syn-guide-now-line { background-color:%%ACCENT%%; }
window.iptv-tv .syn-guide-gap { background-color:%%CARD%%; color:%%MUTED%%; }
/* DVR background, list, scheduler and calendar (without touching its engine). */
window.iptv-tv .syn-dvr-page, window.iptv-tv .syn-dvr-page scrolledwindow {
 background-color:%%BG%%; color:%%FG%%; }
window.iptv-tv .syn-dvr-page list.boxed-list, window.iptv-tv .syn-dvr-page button,
window.iptv-tv .syn-dvr-page entry, window.iptv-tv .syn-dvr-page dropdown > button {
 background-color:%%CARD%%; color:%%FG%%; border-color:%%STROKE%%; }
window.iptv-tv .syn-dvr-page label { color:%%FG%%; }
window.iptv-tv .syn-dvr-page .dim-label { color:%%MUTED%%; }
window.iptv-tv .syn-dvr-page list.boxed-list > row:hover { background-color:%%HOVER%%; }
window.iptv-tv .syn-dvr-page calendar grid label.today:not(:selected) {
 box-shadow:inset 0 0 0 1px %%ACCENT%%; }
window.iptv-tv .syn-dvr-page calendar grid label:selected {
 background-color:%%ACCENT%%; color:%%ACCENT_FG%%; }
window.iptv-tv .syn-dvr-page button.syn-dvr-schedule-action {
 background-color:%%ACCENT%%; color:%%ACCENT_FG%%; border-color:%%ACCENT%%; }
/* Zapping list, not the playback surface. */
window.iptv-tv .syn-zap-panel { color:%%FG%%; }
window.iptv-tv .syn-zap-row { background-color:%%CARD%%; border-color:%%STROKE%%; }
window.iptv-tv .syn-zap-row:hover { background-color:%%HOVER%%; }
window.iptv-tv .syn-zap-row.syn-zap-playing {
 background-color:%%SELECTED%%; border-color:%%ACCENT%%; }
window.iptv-tv .syn-zap-title, window.iptv-tv .syn-zap-name { color:%%FG%%; }
'''


def dracula_css(theme, accent_hex=''):
    if theme not in COLORS:
        raise ValueError('Unknown classic theme: ' + str(theme))
    p = COLORS[theme]
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', accent_hex or ''):
        accent_hex = p['red']  # Classic default: red for both variants.
    accent_hex = accent_hex.upper()
    if theme == 'dracula':
        roles = dict(BG=p['background'], FG=p['foreground'], PANEL=p['dark'],
                     BAR=p['background'], CARD=p['floating'], INPUT=p['floating'],
                     HOVER=p['lighter'], SELECTED=p['selection'],
                     MUTED='#C7D1E5', STROKE=p['comment'], SCROLL=p['comment'])
    else:
        roles = dict(BG=p['background'], FG=p['foreground'], PANEL=p['floating'],
                     BAR=p['lighter'], CARD=p['background'], INPUT=p['floating'],
                     HOVER=p['light'], SELECTED=p['selection'],
                     MUTED=p['comment'], STROKE=p['dark'], SCROLL=p['comment'])
    roles['ACCENT'] = accent_hex
    roles['ACCENT_FG'] = readable_ink(accent_hex, theme)
    css = CSS
    for key, value in roles.items():
        css = css.replace('%%' + key + '%%', value)
    if re.search(r'%%[A-Z_]+%%', css):
        raise AssertionError('Unresolved Dracula/Alucard CSS tokens')
    return css
