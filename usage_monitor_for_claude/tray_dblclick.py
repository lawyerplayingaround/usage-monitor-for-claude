"""
Tray Double-Click Handler
==========================

Extends :class:`pystray.Icon` so a left double-click on the tray icon
fires a separate action from a normal single click.  pystray only
delivers ``WM_LBUTTONUP`` and ``WM_RBUTTONUP`` by default; this module
also handles ``WM_LBUTTONDBLCLK`` and resolves the timing ambiguity
between the first ``WM_LBUTTONUP`` of a double-click and a real single
click.

Shell_NotifyIcon delivers a double-click sequence as:

    WM_LBUTTONUP  ->  WM_LBUTTONDBLCLK  ->  WM_LBUTTONUP

Firing the single-click action on the first ``WM_LBUTTONUP`` would race
the popup against the double-click action.  Instead the single click is
deferred briefly: if a ``WM_LBUTTONDBLCLK`` arrives within the deferral
window, the timer is cancelled and the double-click handler runs.  The
trailing ``WM_LBUTTONUP`` (released after the second click) is suppressed
by a short guard window.

This module also provides :func:`launch_claude_desktop`, the default
double-click action.  It opens the installed Claude Desktop app via the
registered ``claude:`` URL handler (which is created by the MSIX
installer of Claude Desktop), falling back to the web app in the
browser when the handler is missing.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import webbrowser
import winreg
from typing import Any, Callable

import pystray  # type: ignore[import-untyped]

__all__ = ['IconWithDoubleClick', 'launch_claude_desktop']

# Win32 message constants. Hard-coded so we do not depend on pystray's
# private _util.win32 module (which could move between versions).
_WM_LBUTTONUP = 0x0202
_WM_LBUTTONDBLCLK = 0x0203

# Time window after WM_LBUTTONDBLCLK during which the trailing
# WM_LBUTTONUP is ignored.  The Windows default double-click time is
# 500 ms; 700 ms covers users who have slowed it down in Mouse Settings.
_DBLCLICK_GUARD_S = 0.7

# How long to defer the single-click popup so a follow-up dblclick can
# cancel it.  Smaller values make the popup snappier on real single
# clicks but miss dblclicks whose two clicks land more than this far
# apart.  120 ms catches dblclicks roughly within the 90th percentile of
# human click intervals; users with slower dblclicks see the popup open,
# can close it, and the next attempt fires the double-click action.
_SINGLE_CLICK_DEFER_S = 0.12

_CLAUDE_URI = 'claude:'
_CLAUDE_URI_REG_KEY = r'claude\shell\open\command'
_CLAUDE_WEB_FALLBACK = 'https://claude.ai/'


class IconWithDoubleClick(pystray.Icon):  # type: ignore[misc]
    """``pystray.Icon`` subclass that distinguishes single from double click.

    Parameters
    ----------
    on_double_click : Callable[[], None] or None
        Invoked from a background thread when the user double-left-clicks
        the tray icon.  ``None`` disables the double-click behavior, in
        which case the icon behaves like a vanilla :class:`pystray.Icon`.

    All other positional and keyword arguments are forwarded to the base
    :class:`pystray.Icon` constructor unchanged.
    """

    def __init__(
        self,
        *args: Any,
        on_double_click: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._on_double_click_cb: Callable[[], None] | None = on_double_click
        self._pending_single_click: threading.Timer | None = None
        self._last_dblclick_at: float = 0.0
        self._click_state_lock = threading.Lock()

    def _on_notify(self, wparam: int, lparam: int) -> None:  # type: ignore[override]
        if lparam == _WM_LBUTTONUP:
            self._handle_lbutton_up()
            return

        if lparam == _WM_LBUTTONDBLCLK and self._on_double_click_cb is not None:
            self._handle_lbutton_dblclk()
            return

        super()._on_notify(wparam, lparam)

    def _handle_lbutton_up(self) -> None:
        with self._click_state_lock:
            if time.time() - self._last_dblclick_at < _DBLCLICK_GUARD_S:
                return

            if self._pending_single_click is not None:
                self._pending_single_click.cancel()

            if self._on_double_click_cb is None:
                self._pending_single_click = None
                fire_now = True
            else:
                timer = threading.Timer(_SINGLE_CLICK_DEFER_S, self._fire_single_click)
                timer.daemon = True
                self._pending_single_click = timer
                timer.start()
                fire_now = False

        if fire_now:
            self._fire_single_click()

    def _handle_lbutton_dblclk(self) -> None:
        with self._click_state_lock:
            if self._pending_single_click is not None:
                self._pending_single_click.cancel()
                self._pending_single_click = None
            self._last_dblclick_at = time.time()
            cb = self._on_double_click_cb

        if cb is None:
            return
        threading.Thread(target=_safe_invoke, args=(cb,), daemon=True).start()

    def _fire_single_click(self) -> None:
        with self._click_state_lock:
            self._pending_single_click = None
        _safe_invoke(self)


def _safe_invoke(target: Callable[[], Any]) -> None:
    try:
        target()
    except Exception:
        pass


def launch_claude_desktop() -> None:
    """Open Claude Desktop, falling back to the web app on failure.

    Tries the registered ``claude:`` URL handler first (the canonical way
    to launch an MSIX-packaged app without hard-coding its versioned
    install path).  If that fails, looks up the EXE path stored under
    ``HKCR\\claude\\shell\\open\\command`` and launches it directly.  As
    a last resort, opens ``claude.ai`` in the default browser so the
    feature degrades gracefully when Claude Desktop is not installed.
    """
    if _try_uri_launch():
        return
    if _try_registry_exe():
        return
    try:
        webbrowser.open(_CLAUDE_WEB_FALLBACK)
    except Exception:
        pass


def _try_uri_launch() -> bool:
    try:
        os.startfile(_CLAUDE_URI)  # type: ignore[attr-defined]
        return True
    except (OSError, AttributeError):
        return False


def _try_registry_exe() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, _CLAUDE_URI_REG_KEY) as key:
            value, _ = winreg.QueryValueEx(key, '')
    except OSError:
        return False

    exe_path = _extract_exe_from_command(value)
    if not exe_path or not os.path.exists(exe_path):
        return False

    try:
        subprocess.Popen(
            [exe_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except OSError:
        return False


def _extract_exe_from_command(command: str) -> str | None:
    """Pull the executable path out of a shell command string.

    Registry entries for URL handlers look like ``"C:\\Path\\App.exe" "%1"``.
    The path is the first token, quoted when it contains spaces (which the
    Claude install path always does because of ``Program Files``).
    """
    text = command.strip()
    if not text:
        return None
    if text.startswith('"'):
        end = text.find('"', 1)
        if end == -1:
            return None
        return text[1:end]
    space = text.find(' ')
    return text if space == -1 else text[:space]
