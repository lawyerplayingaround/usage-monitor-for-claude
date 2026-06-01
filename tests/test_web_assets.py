"""
Bundled Web-Asset Tests
=======================

The popup UI ships as bundled data files (``popup/popup.html``,
``popup/popup.css``, ``popup/popup.js``) that PyInstaller embeds in the
EXE.  Those files are not exercised by any other test (there is no JS/DOM
test harness in this project), so a build that silently dropped or
reverted one of them would not be caught by the rest of the suite.

These tests assert that the marker strings introduced by recent fork
changes are still present in the source assets, so an accidental revert
or a dropped data file fails CI instead of shipping a regressed popup.
They are deliberately lightweight string checks - no Node, no DOM.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import usage_monitor_for_claude

_POPUP_DIR = Path(usage_monitor_for_claude.__file__).resolve().parent / 'popup'


class TestWebAssetsExist(unittest.TestCase):
    """The three bundled popup assets must exist and be non-empty."""

    def test_assets_present(self):
        for name in ('popup.html', 'popup.css', 'popup.js'):
            path = _POPUP_DIR / name
            self.assertTrue(path.is_file(), f'missing bundled asset: {name}')
            self.assertGreater(path.stat().st_size, 0, f'empty bundled asset: {name}')


class TestRefreshButtonAssets(unittest.TestCase):
    """Refresh button + its cooldown must remain wired across html/css/js."""

    @classmethod
    def setUpClass(cls):
        cls.html = (_POPUP_DIR / 'popup.html').read_text(encoding='utf-8')
        cls.css = (_POPUP_DIR / 'popup.css').read_text(encoding='utf-8')
        cls.js = (_POPUP_DIR / 'popup.js').read_text(encoding='utf-8')

    def test_refresh_button_in_html(self):
        """A real <button id="refreshBtn"> must exist (so `disabled` blocks input)."""
        self.assertIn('id="refreshBtn"', self.html)
        self.assertRegex(self.html, r'<button[^>]*id="refreshBtn"')

    def test_refresh_wiring_in_js(self):
        self.assertIn('function requestRefresh', self.js)
        self.assertIn("refreshBtn.addEventListener('click', requestRefresh)", self.js)

    def test_refresh_cooldown_present(self):
        """win.5: a positive-millisecond cooldown disables the button after a click."""
        self.assertIn('startRefreshCooldown', self.js)
        match = re.search(r'REFRESH_COOLDOWN_MS\s*=\s*(\d+)', self.js)
        self.assertIsNotNone(match, 'REFRESH_COOLDOWN_MS constant missing from popup.js')
        self.assertGreater(int(match.group(1)), 0, 'REFRESH_COOLDOWN_MS must be a positive duration')

    def test_disabled_button_style_present(self):
        """The cooldown's disabled state must have a visible (greyed) style."""
        self.assertIn(':disabled', self.css)


class TestErrorWrapAssets(unittest.TestCase):
    """win.5: footer error messages wrap (and the version hides) instead of truncating."""

    @classmethod
    def setUpClass(cls):
        cls.css = (_POPUP_DIR / 'popup.css').read_text(encoding='utf-8')
        cls.js = (_POPUP_DIR / 'popup.js').read_text(encoding='utf-8')

    def test_error_state_wraps_status_text(self):
        self.assertIn('&.error', self.css)
        self.assertIn('white-space: normal', self.css)
        self.assertIn('overflow: visible', self.css)

    def test_error_state_hides_version(self):
        self.assertIn('&.error > #appVersion', self.css)
        self.assertIn('display: none', self.css)

    def test_status_tooltip_wired(self):
        """The full status text must be exposed as a hover tooltip in both branches."""
        self.assertEqual(
            self.js.count('els.statusText.title'), 2,
            'expected statusText.title set in both tickStatusText() and the static branch',
        )


if __name__ == '__main__':
    unittest.main()
