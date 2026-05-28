"""
Preferences Tests
==================

Unit tests for the registry-stored user preferences.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import usage_monitor_for_claude.preferences as preferences


class TestGetIconLayout(unittest.TestCase):
    """Tests for get_icon_layout()."""

    @patch.object(preferences, 'winreg')
    def test_returns_default_when_key_missing(self, mock_winreg):
        """Missing registry key returns DEFAULT_ICON_LAYOUT."""
        mock_winreg.OpenKey.side_effect = FileNotFoundError

        result = preferences.get_icon_layout()

        self.assertEqual(result, preferences.DEFAULT_ICON_LAYOUT)

    @patch.object(preferences, 'winreg')
    def test_returns_stored_classic(self, mock_winreg):
        """Stored 'classic' value is returned verbatim."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (preferences.ICON_LAYOUT_CLASSIC, 1)

        result = preferences.get_icon_layout()

        self.assertEqual(result, preferences.ICON_LAYOUT_CLASSIC)

    @patch.object(preferences, 'winreg')
    def test_returns_stored_compact(self, mock_winreg):
        """Stored 'compact' value is returned verbatim."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (preferences.ICON_LAYOUT_COMPACT, 1)

        result = preferences.get_icon_layout()

        self.assertEqual(result, preferences.ICON_LAYOUT_COMPACT)

    @patch.object(preferences, 'winreg')
    def test_unknown_stored_value_falls_back_to_default(self, mock_winreg):
        """Unrecognized stored value (e.g. legacy or corrupted) falls back."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = ('something-else', 1)

        result = preferences.get_icon_layout()

        self.assertEqual(result, preferences.DEFAULT_ICON_LAYOUT)

    @patch.object(preferences, 'winreg')
    def test_opens_correct_registry_path(self, mock_winreg):
        """Opens HKCU\\Software\\UsageMonitorForClaude."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (preferences.ICON_LAYOUT_CLASSIC, 1)

        preferences.get_icon_layout()

        mock_winreg.OpenKey.assert_called_once_with(
            mock_winreg.HKEY_CURRENT_USER, preferences.PREFERENCES_REG_KEY,
        )


class TestSetIconLayout(unittest.TestCase):
    """Tests for set_icon_layout()."""

    @patch.object(preferences, 'winreg')
    def test_writes_classic(self, mock_winreg):
        """Writing 'classic' issues a REG_SZ SetValueEx with that exact value."""
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.CreateKeyEx.return_value.__exit__ = MagicMock(return_value=False)

        preferences.set_icon_layout(preferences.ICON_LAYOUT_CLASSIC)

        mock_winreg.SetValueEx.assert_called_once_with(
            mock_key, 'IconLayout', 0, mock_winreg.REG_SZ, preferences.ICON_LAYOUT_CLASSIC,
        )

    @patch.object(preferences, 'winreg')
    def test_writes_compact(self, mock_winreg):
        """Writing 'compact' issues the matching SetValueEx call."""
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.CreateKeyEx.return_value.__exit__ = MagicMock(return_value=False)

        preferences.set_icon_layout(preferences.ICON_LAYOUT_COMPACT)

        mock_winreg.SetValueEx.assert_called_once_with(
            mock_key, 'IconLayout', 0, mock_winreg.REG_SZ, preferences.ICON_LAYOUT_COMPACT,
        )

    @patch.object(preferences, 'winreg')
    def test_invalid_value_raises(self, mock_winreg):
        """Any value other than classic/compact raises ValueError."""
        with self.assertRaises(ValueError):
            preferences.set_icon_layout('bogus')
        mock_winreg.SetValueEx.assert_not_called()

    @patch.object(preferences, 'winreg')
    def test_uses_create_key_so_first_write_succeeds(self, mock_winreg):
        """CreateKeyEx is used (not OpenKey) so the parent key is created if missing."""
        mock_winreg.CreateKeyEx.return_value.__enter__ = MagicMock()
        mock_winreg.CreateKeyEx.return_value.__exit__ = MagicMock(return_value=False)

        preferences.set_icon_layout(preferences.ICON_LAYOUT_CLASSIC)

        mock_winreg.CreateKeyEx.assert_called_once()


class TestGetDblclickOpenClaude(unittest.TestCase):
    """Tests for get_dblclick_open_claude()."""

    @patch.object(preferences, 'winreg')
    def test_returns_default_when_key_missing(self, mock_winreg):
        """Missing key returns DEFAULT_DBLCLICK_OPEN_CLAUDE."""
        mock_winreg.OpenKey.side_effect = FileNotFoundError

        result = preferences.get_dblclick_open_claude()

        self.assertEqual(result, preferences.DEFAULT_DBLCLICK_OPEN_CLAUDE)

    @patch.object(preferences, 'winreg')
    def test_returns_true_for_stored_one(self, mock_winreg):
        """Stored DWORD value 1 is returned as True."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (1, 4)

        self.assertTrue(preferences.get_dblclick_open_claude())

    @patch.object(preferences, 'winreg')
    def test_returns_false_for_stored_zero(self, mock_winreg):
        """Stored DWORD value 0 is returned as False."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (0, 4)

        self.assertFalse(preferences.get_dblclick_open_claude())


class TestSetDblclickOpenClaude(unittest.TestCase):
    """Tests for set_dblclick_open_claude()."""

    @patch.object(preferences, 'winreg')
    def test_writes_one_for_true(self, mock_winreg):
        """Enabling writes REG_DWORD 1."""
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.CreateKeyEx.return_value.__exit__ = MagicMock(return_value=False)

        preferences.set_dblclick_open_claude(True)

        mock_winreg.SetValueEx.assert_called_once_with(
            mock_key, 'DblclickOpenClaude', 0, mock_winreg.REG_DWORD, 1,
        )

    @patch.object(preferences, 'winreg')
    def test_writes_zero_for_false(self, mock_winreg):
        """Disabling writes REG_DWORD 0."""
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.CreateKeyEx.return_value.__exit__ = MagicMock(return_value=False)

        preferences.set_dblclick_open_claude(False)

        mock_winreg.SetValueEx.assert_called_once_with(
            mock_key, 'DblclickOpenClaude', 0, mock_winreg.REG_DWORD, 0,
        )


if __name__ == '__main__':
    unittest.main()
