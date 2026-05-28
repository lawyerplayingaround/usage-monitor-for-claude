"""
Preferences
============

Reads and writes user-toggleable preferences exposed in the tray
right-click menu. Values are stored in the Windows registry under
``HKCU\\Software\\UsageMonitorForClaude`` so they survive across launches
without the app writing files to disk.

Currently tracked:

* ``IconLayout`` (REG_SZ) - either ``'classic'`` or ``'compact'``.
* ``DblclickOpenClaude`` (REG_DWORD) - 1 to launch Claude Desktop on
  double-click, 0 to leave the icon single-click only.

The constants ``DEFAULT_ICON_LAYOUT`` and ``DEFAULT_DBLCLICK_OPEN_CLAUDE``
define what a fresh install sees when no preference has been stored yet.
"""
from __future__ import annotations

import winreg

__all__ = [
    'PREFERENCES_REG_KEY',
    'ICON_LAYOUT_CLASSIC', 'ICON_LAYOUT_COMPACT',
    'DEFAULT_ICON_LAYOUT', 'DEFAULT_DBLCLICK_OPEN_CLAUDE',
    'get_icon_layout', 'set_icon_layout',
    'get_dblclick_open_claude', 'set_dblclick_open_claude',
]

PREFERENCES_REG_KEY = r'Software\UsageMonitorForClaude'

ICON_LAYOUT_CLASSIC = 'classic'
ICON_LAYOUT_COMPACT = 'compact'
_VALID_ICON_LAYOUTS = frozenset({ICON_LAYOUT_CLASSIC, ICON_LAYOUT_COMPACT})

DEFAULT_ICON_LAYOUT = ICON_LAYOUT_COMPACT
DEFAULT_DBLCLICK_OPEN_CLAUDE = True

_ICON_LAYOUT_VALUE_NAME = 'IconLayout'
_DBLCLICK_VALUE_NAME = 'DblclickOpenClaude'


def get_icon_layout() -> str:
    """Return the active icon layout name.

    Returns
    -------
    str
        ``'classic'`` or ``'compact'``. Falls back to
        :data:`DEFAULT_ICON_LAYOUT` if the value has never been written
        or the stored value is unrecognized.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PREFERENCES_REG_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _ICON_LAYOUT_VALUE_NAME)
    except FileNotFoundError:
        return DEFAULT_ICON_LAYOUT
    text = str(value)
    if text not in _VALID_ICON_LAYOUTS:
        return DEFAULT_ICON_LAYOUT
    return text


def set_icon_layout(value: str) -> None:
    """Persist the icon layout choice.

    Parameters
    ----------
    value : str
        Must be ``'classic'`` or ``'compact'``; anything else raises
        :class:`ValueError`.
    """
    if value not in _VALID_ICON_LAYOUTS:
        raise ValueError(f'invalid icon layout: {value!r}')
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, PREFERENCES_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _ICON_LAYOUT_VALUE_NAME, 0, winreg.REG_SZ, value)


def get_dblclick_open_claude() -> bool:
    """Return whether double-clicking the tray icon launches Claude Desktop.

    Returns
    -------
    bool
        Stored value if present; otherwise
        :data:`DEFAULT_DBLCLICK_OPEN_CLAUDE`.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PREFERENCES_REG_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _DBLCLICK_VALUE_NAME)
    except FileNotFoundError:
        return DEFAULT_DBLCLICK_OPEN_CLAUDE
    return bool(value)


def set_dblclick_open_claude(enabled: bool) -> None:
    """Persist whether double-click launches Claude Desktop.

    Parameters
    ----------
    enabled : bool
        ``True`` to enable the double-click action, ``False`` to disable.
    """
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, PREFERENCES_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _DBLCLICK_VALUE_NAME, 0, winreg.REG_DWORD, int(bool(enabled)))
