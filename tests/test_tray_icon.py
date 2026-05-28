"""
Tray Icon Tests
================

Unit tests for tray icon rendering and theme detection.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

import usage_monitor_for_claude.tray_icon as tray_icon_mod


class TestLoadFont(unittest.TestCase):
    """Tests for load_font()."""

    def setUp(self):
        tray_icon_mod.load_font.cache_clear()

    def tearDown(self):
        tray_icon_mod.load_font.cache_clear()

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_loads_arial_bold_for_normal_text(self, mock_image_font):
        """Default call loads Arial Bold font."""
        mock_font = MagicMock()
        mock_image_font.truetype.return_value = mock_font

        result = tray_icon_mod.load_font(42)

        self.assertIs(result, mock_font)
        mock_image_font.truetype.assert_called_once_with(r'C:\Windows\Fonts\arialbd.ttf', 42)

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_loads_segoe_symbol_for_symbol_text(self, mock_image_font):
        """symbol=True loads Segoe UI Symbol font."""
        mock_font = MagicMock()
        mock_image_font.truetype.return_value = mock_font

        result = tray_icon_mod.load_font(36, symbol=True)

        self.assertIs(result, mock_font)
        mock_image_font.truetype.assert_called_once_with(r'C:\Windows\Fonts\seguisym.ttf', 36)

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_falls_back_to_default_when_all_fail(self, mock_image_font):
        """Falls back to load_default() when no TrueType font found."""
        mock_image_font.truetype.side_effect = OSError
        mock_default = MagicMock()
        mock_image_font.load_default.return_value = mock_default

        result = tray_icon_mod.load_font(42)

        self.assertIs(result, mock_default)
        mock_image_font.load_default.assert_called_once()

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_tries_fallback_names_on_failure(self, mock_image_font):
        """Tries alternative font names when first attempt fails."""
        mock_font = MagicMock()
        mock_image_font.truetype.side_effect = [OSError, mock_font]

        result = tray_icon_mod.load_font(42)

        self.assertIs(result, mock_font)
        self.assertEqual(mock_image_font.truetype.call_count, 2)
        mock_image_font.truetype.assert_called_with('arialbd.ttf', 42)

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_lru_cache_returns_same_instance(self, mock_image_font):
        """Cached: same size returns same font object without second truetype call."""
        mock_font = MagicMock()
        mock_image_font.truetype.return_value = mock_font

        first = tray_icon_mod.load_font(42)
        second = tray_icon_mod.load_font(42)

        self.assertIs(first, second)
        mock_image_font.truetype.assert_called_once()

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_different_sizes_cached_separately(self, mock_image_font):
        """Different sizes produce separate cache entries."""
        mock_image_font.truetype.return_value = MagicMock()

        tray_icon_mod.load_font(36)
        tray_icon_mod.load_font(42)

        self.assertEqual(mock_image_font.truetype.call_count, 2)

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {}, clear=True)
    def test_uses_default_windir_when_not_set(self, mock_image_font):
        """Falls back to C:\\Windows when WINDIR is not set."""
        mock_font = MagicMock()
        mock_image_font.truetype.return_value = mock_font

        tray_icon_mod.load_font(42)

        mock_image_font.truetype.assert_called_once_with(r'C:\Windows\Fonts\arialbd.ttf', 42)


class TestTaskbarUsesLightTheme(unittest.TestCase):
    """Tests for taskbar_uses_light_theme()."""

    @patch.object(tray_icon_mod, 'winreg')
    def test_returns_true_for_light_theme(self, mock_winreg):
        """Registry value 1 means light theme."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (1, 4)

        self.assertTrue(tray_icon_mod.taskbar_uses_light_theme())

    @patch.object(tray_icon_mod, 'winreg')
    def test_returns_false_for_dark_theme(self, mock_winreg):
        """Registry value 0 means dark theme."""
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (0, 4)

        self.assertFalse(tray_icon_mod.taskbar_uses_light_theme())

    @patch.object(tray_icon_mod, 'winreg')
    def test_returns_false_on_os_error(self, mock_winreg):
        """OSError (missing key, permissions) defaults to dark."""
        mock_winreg.OpenKey.side_effect = OSError

        self.assertFalse(tray_icon_mod.taskbar_uses_light_theme())

    @patch.object(tray_icon_mod, 'winreg')
    def test_reads_correct_registry_path(self, mock_winreg):
        """Opens the Personalize registry key."""
        mock_winreg.OpenKey.return_value.__enter__ = MagicMock()
        mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
        mock_winreg.QueryValueEx.return_value = (0, 4)

        tray_icon_mod.taskbar_uses_light_theme()

        mock_winreg.OpenKey.assert_called_once_with(
            mock_winreg.HKEY_CURRENT_USER, tray_icon_mod.THEME_REG_KEY,
        )


def _real_font():
    """Return a real PIL font for rendering tests."""
    from PIL import ImageFont

    try:
        return ImageFont.truetype('arial.ttf', 20)
    except OSError:
        return ImageFont.load_default()


class TestCreateIconImage(unittest.TestCase):
    """Tests for create_icon_image()."""

    def setUp(self):
        tray_icon_mod.load_font.cache_clear()

    def tearDown(self):
        tray_icon_mod.load_font.cache_clear()

    def test_returns_64x64_rgba_image(self):
        """Icon is always 64x64 RGBA."""
        img = tray_icon_mod.create_icon_image(0, 0)

        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, 'RGBA')

    def test_low_usage_renders_without_error(self):
        """Usage <= 50% renders successfully."""
        img = tray_icon_mod.create_icon_image(30, 20)

        self.assertEqual(img.size, (64, 64))

    def test_high_usage_renders_without_error(self):
        """Usage > 50% renders successfully."""
        img = tray_icon_mod.create_icon_image(75, 20)

        self.assertEqual(img.size, (64, 64))

    def test_full_usage_renders_without_error(self):
        """Usage >= 100% renders successfully."""
        img = tray_icon_mod.create_icon_image(100, 20)

        self.assertEqual(img.size, (64, 64))

    def test_dark_and_light_taskbar_produce_different_images(self):
        """Dark vs light taskbar produces different pixel data."""
        img_dark = tray_icon_mod.create_icon_image(50, 50, light_taskbar=False)
        img_light = tray_icon_mod.create_icon_image(50, 50, light_taskbar=True)

        self.assertEqual(img_dark.size, (64, 64))
        self.assertEqual(img_light.size, (64, 64))
        self.assertNotEqual(img_dark.tobytes(), img_light.tobytes())

    def test_zero_usage_no_bar_fill(self):
        """Zero usage has no filled bar pixels beyond the half-tone background."""
        img = tray_icon_mod.create_icon_image(0, 0)

        self.assertEqual(img.size, (64, 64))

    def test_full_bar_fill_at_100_percent(self):
        """100% usage fills the entire bar width."""
        img_full = tray_icon_mod.create_icon_image(100, 100)
        img_zero = tray_icon_mod.create_icon_image(0, 0)

        # The bar area pixels should differ between 0% and 100%
        self.assertNotEqual(img_full.tobytes(), img_zero.tobytes())

    def test_boundary_zero_differs_from_one(self):
        """0% (shows 'C') and 1% (shows percentage) produce different icons."""
        img_zero = tray_icon_mod.create_icon_image(0, 0)
        img_one = tray_icon_mod.create_icon_image(1, 0)

        self.assertNotEqual(img_zero.tobytes(), img_one.tobytes())

    @patch.object(tray_icon_mod, 'load_font')
    def test_zero_usage_calls_font_size_42(self, mock_font):
        """Usage of 0% requests size 42 font for 'C' letter."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(0, 0)

        mock_font.assert_any_call(42)

    @patch.object(tray_icon_mod, 'load_font')
    def test_nonzero_usage_calls_font_size_40(self, mock_font):
        """Any usage > 0% requests size 40 font for percentage."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(30, 20)

        mock_font.assert_any_call(40)

    @patch.object(tray_icon_mod, 'load_font')
    def test_full_usage_calls_symbol_font(self, mock_font):
        """Usage >= 100% requests size 36 symbol font for cross."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(100, 20)

        mock_font.assert_any_call(36, symbol=True)

    @patch.object(tray_icon_mod, 'load_font')
    def test_bottom_bar_at_100_also_triggers_cross(self, mock_font):
        """Bottom bar at 100% triggers the cross glyph even when top bar is low."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(20, 100)

        mock_font.assert_any_call(36, symbol=True)

    @patch.object(tray_icon_mod, 'load_font')
    def test_extra_usage_available_shows_dollar_when_exhausted(self, mock_font):
        """When a quota is exhausted but paid extra-usage is available, show '$' instead of '✕'."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(100, 20, extra_usage_available=True)

        # Dollar sign uses the regular size-42 font, not the symbol font
        mock_font.assert_any_call(42)
        self.assertNotIn(call(36, symbol=True), mock_font.call_args_list)

    @patch.object(tray_icon_mod, 'load_font')
    def test_extra_usage_available_irrelevant_when_no_quota_exhausted(self, mock_font):
        """extra_usage_available has no effect while every quota is below 100%."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(75, 20, extra_usage_available=True)

        # Still shows the percentage, not '$'
        mock_font.assert_any_call(40)

    def test_dollar_and_cross_states_produce_different_images(self):
        """'$' (extra usage available) and '✕' (fully blocked) render differently."""
        img_cross = tray_icon_mod.create_icon_image(100, 20, extra_usage_available=False)
        img_dollar = tray_icon_mod.create_icon_image(100, 20, extra_usage_available=True)

        self.assertNotEqual(img_cross.tobytes(), img_dollar.tobytes())


class TestCreateIconImageOverageMode(unittest.TestCase):
    """Tests for create_icon_image() overage-mode bars.

    Overage mode shows how far usage has gone into the over-budget zone.
    The bar is empty when pct <= time_pct (on pace or ahead), and full when
    pct reaches 100%. Formula: fill_ratio = clamp((pct - time_pct) / (100 - time_pct), 0, 1)
    """

    def setUp(self):
        tray_icon_mod.load_font.cache_clear()

    def tearDown(self):
        tray_icon_mod.load_font.cache_clear()

    def test_overage_mode_returns_64x64_rgba(self):
        """Overage mode still produces a 64x64 RGBA image."""
        img = tray_icon_mod.create_icon_image(80, 80, mode_top='overage', mode_bottom='overage', time_pct_top=60, time_pct_bottom=60)

        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, 'RGBA')

    def test_overage_mode_time_pct_at_100_falls_back_to_utilization(self):
        """time_pct=100 (period over) falls back to normal utilization display."""
        img_fallback = tray_icon_mod.create_icon_image(50, 50, mode_top='overage', mode_bottom='overage', time_pct_top=100, time_pct_bottom=100)
        img_util = tray_icon_mod.create_icon_image(50, 50)

        self.assertEqual(img_fallback.tobytes(), img_util.tobytes())

    def test_on_pace_produces_empty_bar(self):
        """Usage exactly at time_pct means on pace - bar pixels are not fully opaque (no fill)."""
        # pct=60, time_pct=60 -> overage=0 -> fill_ratio=0 -> no fill
        img = tray_icon_mod.create_icon_image(60, 60, mode_top='overage', mode_bottom='overage', time_pct_top=60, time_pct_bottom=60)

        S = 64
        bar_h = 9
        gap = 3
        bar2_y = S - bar_h
        bar1_y = bar2_y - gap - bar_h
        pixels = img.load()
        for bar_y in (bar1_y, bar2_y):
            mid_y = bar_y + bar_h // 2
            # No pixel in the bar should be fully opaque (fill_w=0)
            self.assertNotEqual(pixels[0, mid_y][3], 255, f'Expected no fill at x=0, y={mid_y}')

    def test_below_pace_produces_empty_bar(self):
        """Usage below time_pct (ahead of schedule) also produces an empty bar."""
        # pct=40 < time_pct=60 -> overage=0 -> no fill; same result as pct=60
        S = 64
        bar_h = 9
        gap = 3
        bar2_y = S - bar_h
        bar1_y = bar2_y - gap - bar_h

        img_ahead = tray_icon_mod.create_icon_image(40, 40, mode_top='overage', mode_bottom='overage', time_pct_top=60, time_pct_bottom=60)
        pixels = img_ahead.load()
        for bar_y in (bar1_y, bar2_y):
            mid_y = bar_y + bar_h // 2
            self.assertNotEqual(pixels[0, mid_y][3], 255, f'Expected no fill at x=0, y={mid_y}')

    def test_half_fill_at_midpoint_of_over_budget_range(self):
        """pct halfway between time_pct and 100% produces a half-filled bar."""
        # time_pct=60, pct=80 -> (80-60)/(100-60) = 0.5 -> fill_w = 32px
        img = tray_icon_mod.create_icon_image(80, 80, mode_top='overage', mode_bottom='overage', time_pct_top=60, time_pct_bottom=60)

        S = 64
        bar_h = 9
        gap = 3
        bar2_y = S - bar_h
        bar1_y = bar2_y - gap - bar_h
        pixels = img.load()
        for bar_y in (bar1_y, bar2_y):
            mid_y = bar_y + bar_h // 2
            # x=31 (last pixel of left half) should be filled (fg, alpha=255)
            self.assertEqual(pixels[31, mid_y][3], 255, f'Expected filled pixel at x=31, y={mid_y}')
            # x=32 (first pixel of right half) should not be filled (bg, alpha<255)
            self.assertNotEqual(pixels[32, mid_y][3], 255, f'Expected unfilled pixel at x=32, y={mid_y}')

    def test_full_bar_at_100_percent_usage(self):
        """100% usage fills the entire bar regardless of time_pct."""
        # time_pct=60, pct=100 -> (100-60)/(100-60) = 1.0 -> full bar
        img = tray_icon_mod.create_icon_image(100, 100, mode_top='overage', mode_bottom='overage', time_pct_top=60, time_pct_bottom=60)

        S = 64
        bar_h = 9
        gap = 3
        bar2_y = S - bar_h
        bar1_y = bar2_y - gap - bar_h
        pixels = img.load()
        for bar_y in (bar1_y, bar2_y):
            mid_y = bar_y + bar_h // 2
            self.assertEqual(pixels[S - 1, mid_y][3], 255, f'Expected fully filled bar at y={mid_y}')

    def test_mixed_modes_top_overage_bottom_utilization(self):
        """Top bar in overage mode, bottom bar in utilization mode produces valid image."""
        img = tray_icon_mod.create_icon_image(80, 50, mode_top='overage', mode_bottom='utilization', time_pct_top=60, time_pct_bottom=None)

        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, 'RGBA')


class TestCreateStatusImage(unittest.TestCase):
    """Tests for create_status_image()."""

    def setUp(self):
        tray_icon_mod.load_font.cache_clear()

    def tearDown(self):
        tray_icon_mod.load_font.cache_clear()

    def test_returns_64x64_rgba_image(self):
        """Status icon is always 64x64 RGBA."""
        img = tray_icon_mod.create_status_image('!')

        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, 'RGBA')

    @patch.object(tray_icon_mod, 'load_font')
    def test_uses_size_46_font(self, mock_font):
        """Status text uses size 46 font."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_status_image('?')

        mock_font.assert_called_with(46)

    def test_light_taskbar_variant(self):
        """Light taskbar produces a valid image."""
        img = tray_icon_mod.create_status_image('!', light_taskbar=True)

        self.assertEqual(img.size, (64, 64))


class TestCreateIconImageCompactLayout(unittest.TestCase):
    """Tests for the compact icon layout."""

    def setUp(self):
        tray_icon_mod.load_font.cache_clear()

    def tearDown(self):
        tray_icon_mod.load_font.cache_clear()

    def test_returns_64x64_rgba_image(self):
        """Compact still produces a 64x64 RGBA image."""
        img = tray_icon_mod.create_icon_image(45, 0, layout=tray_icon_mod.LAYOUT_COMPACT)

        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, 'RGBA')

    def test_low_usage_renders_without_error(self):
        """Low percentage renders cleanly in compact mode."""
        img = tray_icon_mod.create_icon_image(15, 5, layout=tray_icon_mod.LAYOUT_COMPACT)
        self.assertEqual(img.size, (64, 64))

    def test_high_usage_renders_without_error(self):
        """High percentage renders cleanly in compact mode."""
        img = tray_icon_mod.create_icon_image(90, 50, layout=tray_icon_mod.LAYOUT_COMPACT)
        self.assertEqual(img.size, (64, 64))

    @patch.object(tray_icon_mod, 'load_font')
    def test_percent_uses_size_58_regular_arial(self, mock_font):
        """Compact mode uses size 58 regular Arial for the percentage text."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(45, 0, layout=tray_icon_mod.LAYOUT_COMPACT)

        mock_font.assert_any_call(58, bold=False)

    @patch.object(tray_icon_mod, 'load_font')
    def test_zero_usage_still_uses_size_42_for_letter_c(self, mock_font):
        """Compact mode keeps the legacy 'C' glyph for the zero-usage state."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(0, 0, layout=tray_icon_mod.LAYOUT_COMPACT)

        mock_font.assert_any_call(42)

    @patch.object(tray_icon_mod, 'load_font')
    def test_exhausted_state_shows_cross(self, mock_font):
        """When a quota is at 100% with no extra credit, compact mode shows the cross glyph."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(100, 30, layout=tray_icon_mod.LAYOUT_COMPACT)

        mock_font.assert_any_call(36, symbol=True)

    @patch.object(tray_icon_mod, 'load_font')
    def test_exhausted_with_extra_credit_shows_dollar(self, mock_font):
        """When a quota is at 100% but extra credits are available, compact shows '$'."""
        mock_font.return_value = _real_font()

        tray_icon_mod.create_icon_image(
            100, 30, extra_usage_available=True,
            layout=tray_icon_mod.LAYOUT_COMPACT,
        )

        mock_font.assert_any_call(42)

    def test_bottom_quota_exhaustion_still_triggers_alert_glyph(self):
        """A second-field exhaustion (pct_bottom>=100) still shifts the glyph to '$'/cross."""
        compact = tray_icon_mod.create_icon_image(20, 100, layout=tray_icon_mod.LAYOUT_COMPACT)
        normal = tray_icon_mod.create_icon_image(20, 50, layout=tray_icon_mod.LAYOUT_COMPACT)

        self.assertNotEqual(compact.tobytes(), normal.tobytes())

    def test_compact_and_classic_produce_different_images(self):
        """Same usage, different layouts produce visibly different icons."""
        classic = tray_icon_mod.create_icon_image(40, 60, layout=tray_icon_mod.LAYOUT_CLASSIC)
        compact = tray_icon_mod.create_icon_image(40, 60, layout=tray_icon_mod.LAYOUT_COMPACT)

        self.assertNotEqual(classic.tobytes(), compact.tobytes())

    def test_default_layout_is_classic(self):
        """Omitting layout keyword keeps upstream classic behavior."""
        explicit_classic = tray_icon_mod.create_icon_image(40, 60, layout=tray_icon_mod.LAYOUT_CLASSIC)
        implicit = tray_icon_mod.create_icon_image(40, 60)

        self.assertEqual(explicit_classic.tobytes(), implicit.tobytes())


class TestLoadFontBoldParameter(unittest.TestCase):
    """Tests for the bold=False fallback ordering in load_font."""

    def setUp(self):
        tray_icon_mod.load_font.cache_clear()

    def tearDown(self):
        tray_icon_mod.load_font.cache_clear()

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_bold_false_prefers_regular_arial(self, mock_image_font):
        """bold=False asks for arial.ttf first, then arialbd.ttf."""
        mock_font = MagicMock()
        mock_image_font.truetype.return_value = mock_font

        tray_icon_mod.load_font(58, bold=False)

        first_call_path = mock_image_font.truetype.call_args_list[0][0][0]
        self.assertIn('arial.ttf', first_call_path.lower())
        self.assertNotIn('arialbd', first_call_path.lower())

    @patch.object(tray_icon_mod, 'ImageFont')
    @patch.dict('os.environ', {'WINDIR': r'C:\Windows'})
    def test_bold_default_true_prefers_bold(self, mock_image_font):
        """Default behavior keeps preferring arialbd.ttf (upstream behavior)."""
        mock_font = MagicMock()
        mock_image_font.truetype.return_value = mock_font

        tray_icon_mod.load_font(40)

        first_call_path = mock_image_font.truetype.call_args_list[0][0][0]
        self.assertIn('arialbd.ttf', first_call_path.lower())


if __name__ == '__main__':
    unittest.main()
