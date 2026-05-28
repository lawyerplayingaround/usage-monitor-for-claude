"""
Tray Double-Click Tests
========================

Unit tests for the standalone helpers in :mod:`tray_dblclick`.  The
``IconWithDoubleClick`` Win32-message dispatch and the
:func:`launch_claude_desktop` integration paths are exercised manually
because they require a live tray icon and an installed Claude Desktop;
the pure helpers are covered here.
"""
from __future__ import annotations

import unittest

import usage_monitor_for_claude.tray_dblclick as tray_dblclick_mod


class TestExtractExeFromCommand(unittest.TestCase):
    """Tests for _extract_exe_from_command()."""

    def test_quoted_path_with_args_returns_path_only(self):
        """The shell command from the registered claude: URL handler."""
        command = r'"C:\Program Files\WindowsApps\Claude_1.0.0\Claude.exe" "%1"'

        result = tray_dblclick_mod._extract_exe_from_command(command)

        self.assertEqual(result, r'C:\Program Files\WindowsApps\Claude_1.0.0\Claude.exe')

    def test_quoted_path_without_args(self):
        """Quoted path with no trailing %1 is also accepted."""
        command = r'"C:\App\my.exe"'

        result = tray_dblclick_mod._extract_exe_from_command(command)

        self.assertEqual(result, r'C:\App\my.exe')

    def test_unquoted_path_returns_first_token(self):
        """Legacy unquoted handlers take the first whitespace-delimited token."""
        command = r'C:\Apps\Plain.exe %1'

        result = tray_dblclick_mod._extract_exe_from_command(command)

        self.assertEqual(result, r'C:\Apps\Plain.exe')

    def test_empty_string_returns_none(self):
        """Whitespace-only registry values are treated as missing."""
        self.assertIsNone(tray_dblclick_mod._extract_exe_from_command(''))
        self.assertIsNone(tray_dblclick_mod._extract_exe_from_command('   '))

    def test_unbalanced_opening_quote_returns_none(self):
        """A malformed handler that opens but never closes a quote is rejected."""
        result = tray_dblclick_mod._extract_exe_from_command(r'"C:\never-closed.exe')

        self.assertIsNone(result)

    def test_unquoted_single_token_with_no_args(self):
        """Bare executable name without arguments is preserved as-is."""
        result = tray_dblclick_mod._extract_exe_from_command('app.exe')

        self.assertEqual(result, 'app.exe')


if __name__ == '__main__':
    unittest.main()
