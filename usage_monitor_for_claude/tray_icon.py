"""
Tray Icon
==========

Creates monochrome system tray icons and detects the Windows taskbar theme.

Two layouts are supported:

* ``'classic'`` - two progress bars (top + bottom field), bold Arial
  percentage text at the top.  Matches upstream behavior exactly.
* ``'compact'`` - a single bottom progress bar (the top field) and a
  large thin Arial Regular percentage text positioned slightly above
  vertical center, designed for legibility after Windows downscales the
  64 x 64 icon to ~16-24 px in the tray.
"""
from __future__ import annotations

import ctypes
import functools
import os
import winreg
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from .settings import ICON_DARK, ICON_LIGHT

__all__ = ['load_font', 'taskbar_uses_light_theme', 'watch_theme_change', 'create_icon_image', 'create_status_image']

# Theme registry
THEME_REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
THEME_REG_VALUE = 'SystemUsesLightTheme'
REG_NOTIFY_CHANGE_LAST_SET = 0x00000004

TRANSPARENT = (0, 0, 0, 0)

LAYOUT_CLASSIC = 'classic'
LAYOUT_COMPACT = 'compact'


@functools.lru_cache(maxsize=None)
def load_font(size: int, symbol: bool = False, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load an Arial (or symbol) font at the requested pixel size.

    Parameters
    ----------
    size : int
        Pixel size.
    symbol : bool
        When ``True``, prefer Segoe UI Symbol so Unicode glyphs that
        Arial lacks (e.g. ``✕``) still render.
    bold : bool
        When ``True`` (default), prefer Arial Bold and fall back to
        regular Arial.  When ``False``, prefer regular Arial and fall
        back to Arial Bold; useful for large text where the bold weight
        becomes a thick blob after the tray downscales the icon.
    """
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    if symbol:
        names = (f'{windir}\\Fonts\\seguisym.ttf', 'seguisym.ttf')
    elif bold:
        names = (f'{windir}\\Fonts\\arialbd.ttf', 'arialbd.ttf', f'{windir}\\Fonts\\arial.ttf', 'arial.ttf')
    else:
        names = (f'{windir}\\Fonts\\arial.ttf', 'arial.ttf', f'{windir}\\Fonts\\arialbd.ttf', 'arialbd.ttf')
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue

    return ImageFont.load_default()


def taskbar_uses_light_theme() -> bool:
    """Return True if the Windows taskbar uses the light theme.

    Reads ``SystemUsesLightTheme`` from the Personalize registry key.
    Returns False (dark) if the value cannot be read.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_REG_KEY) as key:
            value, _ = winreg.QueryValueEx(key, THEME_REG_VALUE)
            return bool(value)
    except OSError:
        return False


def watch_theme_change(callback: Callable[[], None]) -> None:
    """Block the current thread and call *callback* whenever the taskbar theme changes.

    Uses ``RegNotifyChangeKeyValue`` to sleep until the registry key
    is modified, avoiding any polling.  Designed to run in a daemon thread.
    """
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_REG_KEY, 0, winreg.KEY_READ) as key:
        while True:
            if ctypes.windll.advapi32.RegNotifyChangeKeyValue(int(key), False, REG_NOTIFY_CHANGE_LAST_SET, None, False) != 0:
                return
            callback()


def create_icon_image(
    pct_top: float, pct_bottom: float, light_taskbar: bool = False,
    *, mode_top: str = 'utilization', mode_bottom: str = 'utilization',
    time_pct_top: float | None = None, time_pct_bottom: float | None = None,
    extra_usage_available: bool = False,
    layout: str = LAYOUT_CLASSIC,
) -> Image.Image:
    """Create the tray icon image for the current usage state.

    Parameters
    ----------
    pct_top : float
        Utilization percentage (0-100) for the upper field.  In the
        ``'compact'`` layout this is the only field shown as a bar.
    pct_bottom : float
        Utilization percentage (0-100) for the lower field.  Drawn as a
        second bar in ``'classic'``; not drawn in ``'compact'`` but still
        used by the exhausted-quota glyph logic.
    light_taskbar : bool
        Use dark-on-light colors for a light taskbar.
    mode_top : str
        Display mode for the upper bar: ``'utilization'`` (linear fill)
        or ``'overage'`` (fills as usage exceeds the time marker).
    mode_bottom : str
        Display mode for the lower bar (``'classic'`` only).
    time_pct_top : float or None
        Elapsed-time percentage for the upper bar.  Required for
        ``'overage'`` mode; ignored otherwise.
    time_pct_bottom : float or None
        Elapsed-time percentage for the lower bar (``'classic'`` only).
    extra_usage_available : bool
        True if the account has paid extra-usage credits still available.
        When a quota is fully exhausted, this decides whether to show
        ``$`` (continuing costs money) or ``✕`` (fully blocked).
    layout : str
        Either ``'classic'`` (default, matches upstream) or ``'compact'``
        (single bar with a larger percentage text).
    """
    if layout == LAYOUT_COMPACT:
        return _create_compact_image(
            pct_top, pct_bottom, light_taskbar,
            mode_top=mode_top, time_pct_top=time_pct_top,
            extra_usage_available=extra_usage_available,
        )
    return _create_classic_image(
        pct_top, pct_bottom, light_taskbar,
        mode_top=mode_top, mode_bottom=mode_bottom,
        time_pct_top=time_pct_top, time_pct_bottom=time_pct_bottom,
        extra_usage_available=extra_usage_available,
    )


def _create_classic_image(
    pct_top: float, pct_bottom: float, light_taskbar: bool,
    *, mode_top: str, mode_bottom: str,
    time_pct_top: float | None, time_pct_bottom: float | None,
    extra_usage_available: bool,
) -> Image.Image:
    colors = ICON_DARK if light_taskbar else ICON_LIGHT
    fg, fg_half = colors['fg'], colors['fg_half']

    S = 64
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    text, font, stroke_width = _choose_glyph(pct_top, pct_bottom, extra_usage_available, bold_percent=True, percent_size=40)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    draw.text(((S - tw) / 2 - bbox[0], -bbox[1]), text, fill=fg, font=font, stroke_width=stroke_width, stroke_fill=fg)

    # Progress bars - full width, flush to bottom
    bar_h = 9
    gap = 3
    bar2_y = S - bar_h
    bar1_y = bar2_y - gap - bar_h

    for y, pct, mode, time_pct in (
        (bar1_y, pct_top, mode_top, time_pct_top),
        (bar2_y, pct_bottom, mode_bottom, time_pct_bottom),
    ):
        _draw_bar(draw, y, bar_h, S, pct, mode, time_pct, fg, fg_half)

    return img


def _create_compact_image(
    pct_top: float, pct_bottom: float, light_taskbar: bool,
    *, mode_top: str,
    time_pct_top: float | None,
    extra_usage_available: bool,
) -> Image.Image:
    colors = ICON_DARK if light_taskbar else ICON_LIGHT
    fg, fg_half = colors['fg'], colors['fg_half']

    S = 64
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # Compact uses a single bar at the bottom and a tall, thin, regular-weight
    # percentage so the digits stay readable after Windows downscales the
    # icon to ~16-24 px.  Width is the binding constraint: "88" / "99" at
    # Arial Regular 58 fills the 64 px canvas almost exactly.
    bar_h = 9
    bar_y = S - bar_h
    avail_h = bar_y

    text, font, stroke_width = _choose_glyph(pct_top, pct_bottom, extra_usage_available, bold_percent=False, percent_size=58)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Position slightly above center so the digits have more separation
    # from the bar - centered exactly looked low after downscale.
    top_offset = max(0, (avail_h - text_h) // 2 - 4)
    draw.text(
        ((S - tw) / 2 - bbox[0], top_offset - bbox[1]),
        text, fill=fg, font=font, stroke_width=stroke_width, stroke_fill=fg,
    )

    _draw_bar(draw, bar_y, bar_h, S, pct_top, mode_top, time_pct_top, fg, fg_half)

    return img


def _choose_glyph(
    pct_top: float, pct_bottom: float, extra_usage_available: bool,
    *, bold_percent: bool, percent_size: int,
) -> tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, int]:
    """Return (text, font, stroke_width) for the glyph drawn over the icon."""
    any_exhausted = pct_top >= 100 or pct_bottom >= 100
    if any_exhausted and not extra_usage_available:
        return '✕', load_font(36, symbol=True), 2
    if any_exhausted:
        return '$', load_font(42), 2
    if pct_top > 0:
        # Pass bold only when explicitly disabling it - this keeps the classic
        # code path calling load_font(size) exactly the way upstream did,
        # preserving call-site compatibility for tests that check arguments.
        font = load_font(percent_size) if bold_percent else load_font(percent_size, bold=False)
        return f'{pct_top:.0f}', font, 0
    return 'C', load_font(42), 0


def _draw_bar(
    draw: ImageDraw.ImageDraw, y: int, bar_h: int, canvas_w: int,
    pct: float, mode: str, time_pct: float | None,
    fg: tuple, fg_half: tuple,
) -> None:
    """Draw a single progress bar at vertical position *y*."""
    draw.rectangle([0, y, canvas_w - 1, y + bar_h - 1], fill=fg_half)
    if mode == 'overage' and time_pct is not None and time_pct < 100:
        overage = max(0.0, pct - time_pct)
        fill_ratio = min(1.0, overage / (100 - time_pct))
        fill_w = max(0, int(canvas_w * fill_ratio))
    else:
        fill_w = max(0, min(canvas_w, int(canvas_w * pct / 100)))
    if fill_w > 0:
        draw.rectangle([0, y, fill_w - 1, y + bar_h - 1], fill=fg)


def create_status_image(text: str, light_taskbar: bool = False) -> Image.Image:
    """Create monochrome centered-text icon for error/status states."""
    fg_dim = (ICON_DARK if light_taskbar else ICON_LIGHT)['fg_dim']

    S = 64
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    font = load_font(46)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((S - tw) / 2 - bbox[0], (S - th) / 2 - bbox[1]), text, fill=fg_dim, font=font)

    return img
