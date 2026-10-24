"""SYN 1.3.6 beta9 · horizontal EPG gradients.

A high-contrast spectrum of vibrant left-hand hues fading toward a deeper
shade on the right. The first endpoint exceeds WCAG 4.5:1 vs white in every
palette, the second is darker. Applied only to programme blocks (not axis).
"""

COLORS = (
    ('#B14768', '#592C55'),  # pop coral / plum
    ('#9B571B', '#49344E'),  # amber / twilight
    ('#336CAA', '#2D376B'),  # vivid blue / indigo
    ('#7754AF', '#3F356C'),  # violet / night
    ('#08796E', '#164A57'),  # teal / deep sea
    ('#47794C', '#24463D'),  # leaf / forest
)


def contrast_against_white(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    luminance = sum(w * v for w, v in zip((.2126, .7152, .0722), linear))
    return 1.05 / (luminance + .05)


def epg_gradient_css():
    # Style programme blocks only. The guide axis and names remain styled by
    # the user's selected theme, and the video/fullscreen canvas is untouched.
    rules = [
        '/* SYN beta9: legible POP gradients in every light/dark/Nord mode. */',
        'window.iptv-tv .syn-guide-program { '
        'color: #FFFFFF; border-color: rgba(10,20,37,.42); '
        'background-clip: padding-box; }',
        'window.iptv-tv .syn-guide-program .syn-guide-program-name, '
        'window.iptv-tv .syn-guide-program .syn-guide-time, '
        'window.iptv-tv .syn-guide-program label { '
        'color: #FFFFFF; text-shadow: 0 1px 2px rgba(0,0,0,.45); }',
        'window.iptv-tv .syn-guide-program:hover { '
        'border-color: rgba(240,248,255,.78); }',
    ]
    for i, (left, right) in enumerate(COLORS):
        rules.append(
            'window.iptv-tv .syn-guide-program-%d { '
            'background-color: %s; '
            'background-image: linear-gradient(to right, %s 0%%, %s 100%%); }'
            % (i, right, left, right)
        )
    return '\n'.join(rules)
