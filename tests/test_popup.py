"""
Popup Tests
=============

Unit tests for popup data helpers: _usage_entries, _snapshot_to_dict,
and _init_config.
"""
from __future__ import annotations

import ctypes
import unittest
from unittest.mock import MagicMock, patch

from usage_monitor_for_claude.cache import CacheSnapshot
from usage_monitor_for_claude.popup import UsagePopup, _BASELINE_DPI, _MONITORINFO, _PopupApi, _init_config, _snapshot_to_dict, _usage_entries


def _snap(
    usage=None, profile=None, last_success_time=None,
    refreshing=False, last_error=None, version=1,
) -> CacheSnapshot:
    """Build a CacheSnapshot with convenient defaults."""
    return CacheSnapshot(
        usage=usage or {},
        profile=profile,
        last_success_time=last_success_time,
        refreshing=refreshing,
        last_error=last_error,
        version=version,
    )


# ---------------------------------------------------------------------------
# _usage_entries
# ---------------------------------------------------------------------------

class TestUsageEntries(unittest.TestCase):
    """Tests for _usage_entries - extracts labelled tuples from usage dict."""

    def test_returns_entries_for_active_fields(self):
        """Returns entries only for non-null fields with utilization."""
        usage = {
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T00:00:00Z'},
            'seven_day': {'utilization': 10, 'resets_at': '2026-01-07T00:00:00Z'},
            'seven_day_sonnet': None,
        }
        entries = _usage_entries(usage)
        self.assertEqual(len(entries), 2)

    def test_labels_use_popup_label(self):
        """Each entry's label is generated via popup_label."""
        from usage_monitor_for_claude.formatting import popup_label

        usage = {
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T00:00:00Z'},
            'seven_day': {'utilization': 10, 'resets_at': '2026-01-07T00:00:00Z'},
        }
        entries = _usage_entries(usage)
        labels = [e[0] for e in entries]
        self.assertEqual(labels, [popup_label('five_hour'), popup_label('seven_day')])

    def test_periods_derived_from_field_name(self):
        """Period is derived from the field name via field_period."""
        usage = {
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T00:00:00Z'},
            'seven_day': {'utilization': 10, 'resets_at': '2026-01-07T00:00:00Z'},
        }
        entries = _usage_entries(usage)
        periods = [e[2] for e in entries]
        self.assertEqual(periods, [5 * 3600, 7 * 24 * 3600])

    def test_data_extraction(self):
        """Entry data is pulled from the correct usage dict keys."""
        five_hour = {'utilization': 42, 'resets_at': '2026-01-01T00:00:00Z'}
        seven_day = {'utilization': 10, 'resets_at': '2026-01-07T00:00:00Z'}
        usage = {'five_hour': five_hour, 'seven_day': seven_day}

        entries = _usage_entries(usage)
        self.assertEqual(len(entries), 2)
        self.assertIs(entries[0][1], five_hour)
        self.assertIs(entries[1][1], seven_day)

    def test_empty_usage_returns_empty(self):
        """Empty usage dict returns no entries."""
        self.assertEqual(_usage_entries({}), [])

    def test_all_null_fields_returns_empty(self):
        """All-null fields return no entries."""
        usage = {'five_hour': None, 'seven_day': None, 'seven_day_sonnet': None}
        self.assertEqual(_usage_entries(usage), [])

    def test_null_utilization_skipped(self):
        """Fields with utilization None are skipped."""
        usage = {
            'five_hour': {'utilization': None, 'resets_at': '2026-01-01T05:00:00Z'},
            'seven_day': {'utilization': 20, 'resets_at': '2026-01-07T00:00:00Z'},
        }
        entries = _usage_entries(usage)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1]['utilization'], 20)

    @patch('usage_monitor_for_claude.popup.POPUP_FIELDS', ['fve_hour', 'seven_day'])
    def test_misspelled_popup_field_skipped(self):
        """Misspelled popup_fields entry is skipped, valid one shown."""
        usage = {
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T05:00:00Z'},
            'seven_day': {'utilization': 20, 'resets_at': '2026-01-07T00:00:00Z'},
        }
        entries = _usage_entries(usage)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1]['utilization'], 20)

    @patch('usage_monitor_for_claude.popup.POPUP_FIELDS', ['seven_day_sonnet'])
    def test_popup_field_pointing_to_null_skipped(self):
        """popup_fields entry pointing to a null field produces no entries."""
        usage = {'seven_day_sonnet': None, 'five_hour': {'utilization': 42, 'resets_at': ''}}
        entries = _usage_entries(usage)
        self.assertEqual(entries, [])

    def test_non_dict_values_in_usage_ignored(self):
        """Non-dict values (like error strings) in usage are ignored."""
        usage = {
            'error': 'server down',
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T05:00:00Z'},
        }
        entries = _usage_entries(usage)
        self.assertEqual(len(entries), 1)

    def test_extra_usage_not_shown_as_bar(self):
        """extra_usage is excluded from dynamic bars (different structure)."""
        usage = {
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T05:00:00Z'},
            'extra_usage': {'is_enabled': True, 'monthly_limit': 1000, 'used_credits': 500, 'utilization': 50},
        }
        entries = _usage_entries(usage)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1]['utilization'], 42)


# ---------------------------------------------------------------------------
# _snapshot_to_dict
# ---------------------------------------------------------------------------

class TestSnapshotToDict(unittest.TestCase):
    """Tests for _snapshot_to_dict - converts CacheSnapshot to popup JSON."""

    # -- profile --

    def test_no_profile(self):
        """Profile is None when snapshot has no profile."""
        result = _snapshot_to_dict(_snap(), installations=[])
        self.assertIsNone(result['profile'])

    def test_profile_extraction(self):
        """Email and plan are extracted from nested account/organization dicts."""
        profile = {
            'account': {'email': 'test@example.com'},
            'organization': {'organization_type': 'pro_team'},
        }
        result = _snapshot_to_dict(_snap(profile=profile), installations=[])
        self.assertEqual(result['profile']['email'], 'test@example.com')
        self.assertEqual(result['profile']['plan'], 'Pro Team')

    def test_empty_profile_hidden(self):
        """Empty profile dict from API is treated as absent (no broken UI)."""
        result = _snapshot_to_dict(_snap(profile={}), installations=[])
        self.assertIsNone(result['profile'])

    def test_profile_missing_nested_keys(self):
        """Present but incomplete profile defaults missing fields to empty strings."""
        result = _snapshot_to_dict(_snap(profile={'account': {}}), installations=[])
        self.assertEqual(result['profile']['email'], '')
        self.assertEqual(result['profile']['plan'], '')

    # -- usage bars --

    def test_no_usage_data(self):
        """Empty usage dict produces empty usage list."""
        result = _snapshot_to_dict(_snap(), installations=[])
        self.assertEqual(result['usage'], [])

    def test_skips_entries_without_utilization(self):
        """Entries with None utilization are omitted."""
        usage = {'five_hour': {'utilization': None}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(result['usage'], [])

    def test_skips_missing_entries(self):
        """Missing usage keys produce no bar entries."""
        usage = {'five_hour': None}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(result['usage'], [])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='5h 0m')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_usage_bar_fields(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Each usage bar dict has all required fields with correct types."""
        usage = {'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])

        self.assertEqual(len(result['usage']), 1)
        bar = result['usage'][0]
        self.assertEqual(bar['pct_text'], '42%')
        self.assertAlmostEqual(bar['fill_pct'], 0.42)
        self.assertFalse(bar['warn'])
        self.assertIsNone(bar['marker_rel'])
        self.assertEqual(bar['reset_text'], '5h 0m')
        self.assertEqual(bar['midnights'], [])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=30.0)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='3h 30m')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[0.5])
    def test_warn_when_usage_ahead_of_time(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Bar is marked warn when utilization exceeds elapsed percentage."""
        usage = {'five_hour': {'utilization': 60, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])

        bar = result['usage'][0]
        self.assertTrue(bar['warn'])
        self.assertAlmostEqual(bar['marker_rel'], 0.3)

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=80.0)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='1h 0m')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_no_warn_when_usage_behind_time(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Bar is not warn when utilization is below elapsed percentage."""
        usage = {'five_hour': {'utilization': 40, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])

        bar = result['usage'][0]
        self.assertFalse(bar['warn'])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=50.0)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='2h 30m')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_no_warn_when_equal(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Exactly equal usage and elapsed is not a warning (strictly greater)."""
        usage = {'five_hour': {'utilization': 50, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertFalse(result['usage'][0]['warn'])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_warn_at_100_without_time_period(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Bar at 100% is warn even when no time period (time_pct is None)."""
        usage = {'five_hour': {'utilization': 100, 'resets_at': ''}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertTrue(result['usage'][0]['warn'])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=100.0)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_warn_at_100_when_time_also_100(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Bar at 100% is warn even when elapsed time is also 100% (strict > would miss this)."""
        usage = {'five_hour': {'utilization': 100, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertTrue(result['usage'][0]['warn'])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_fill_pct_clamped_to_0_1(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Fill percentage is clamped between 0.0 and 1.0, and over-quota is always warn."""
        usage = {'five_hour': {'utilization': 150, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(result['usage'][0]['fill_pct'], 1.0)
        self.assertTrue(result['usage'][0]['warn'])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_zero_utilization(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Zero utilization produces 0% text and 0.0 fill."""
        usage = {'five_hour': {'utilization': 0, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        # utilization 0 is falsy, so `or 0` kicks in - entry is still shown
        bar = result['usage'][0]
        self.assertEqual(bar['pct_text'], '0%')
        self.assertAlmostEqual(bar['fill_pct'], 0.0)

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_multiple_usage_entries(self, _mock_midnights, _mock_time_until, _mock_elapsed):
        """Multiple usage types each produce a bar entry."""
        usage = {
            'five_hour': {'utilization': 10, 'resets_at': '2026-01-01T05:00:00Z'},
            'seven_day': {'utilization': 20, 'resets_at': '2026-01-07T00:00:00Z'},
            'seven_day_sonnet': {'utilization': 30, 'resets_at': '2026-01-07T00:00:00Z'},
        }
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(len(result['usage']), 3)
        pcts = [b['pct_text'] for b in result['usage']]
        self.assertEqual(pcts, ['10%', '20%', '30%'])

    @patch('usage_monitor_for_claude.popup.POPUP_FIELDS', ['typo_field', 'seven_day'])
    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_misspelled_popup_field_skipped_in_dict(self, _mock_mid, _mock_tu, _mock_ep):
        """Misspelled popup_fields entry produces no bar, valid one shown."""
        usage = {
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T05:00:00Z'},
            'seven_day': {'utilization': 20, 'resets_at': '2026-01-07T00:00:00Z'},
        }
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(len(result['usage']), 1)
        self.assertEqual(result['usage'][0]['pct_text'], '20%')

    def test_all_null_fields_no_bars(self):
        """All-null quota fields produce no usage bars."""
        usage = {'five_hour': None, 'seven_day': None, 'seven_day_sonnet': None}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(result['usage'], [])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_non_dict_values_in_response_ignored(self, _mock_mid, _mock_tu, _mock_ep):
        """Non-dict values in the API response are not shown as bars."""
        usage = {
            'error': 'temporary',
            'rate_limited': True,
            'five_hour': {'utilization': 42, 'resets_at': '2026-01-01T05:00:00Z'},
        }
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(len(result['usage']), 1)
        self.assertEqual(result['usage'][0]['pct_text'], '42%')

    # -- extra usage --

    def test_no_extra_usage(self):
        """Extra is None when no extra_usage key in usage dict."""
        result = _snapshot_to_dict(_snap(), installations=[])
        self.assertIsNone(result['extra'])

    def test_extra_usage_disabled(self):
        """Extra is None when extra usage is not enabled."""
        usage = {'extra_usage': {'is_enabled': False, 'monthly_limit': 1000, 'used_credits': 500}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertIsNone(result['extra'])

    def test_extra_usage_zero_limit(self):
        """Extra is None when monthly limit is zero."""
        usage = {'extra_usage': {'is_enabled': True, 'monthly_limit': 0, 'used_credits': 0}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertIsNone(result['extra'])

    @patch('usage_monitor_for_claude.popup.format_credits', side_effect=lambda c: f'${c / 100:.2f}')
    def test_extra_usage_calculation(self, _mock_credits):
        """Extra usage computes percentage and formatted text correctly."""
        usage = {'extra_usage': {'is_enabled': True, 'monthly_limit': 10000, 'used_credits': 2500}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])

        extra = result['extra']
        self.assertIsNotNone(extra)
        self.assertEqual(extra['pct_text'], '25%')
        self.assertAlmostEqual(extra['fill_pct'], 0.25)
        self.assertIn('$25.00', extra['spent_text'])
        self.assertIn('$100.00', extra['spent_text'])

    @patch('usage_monitor_for_claude.popup.format_credits', side_effect=lambda c: f'${c / 100:.2f}')
    def test_extra_usage_fill_clamped(self, _mock_credits):
        """Extra usage fill is clamped to 1.0 when over limit."""
        usage = {'extra_usage': {'is_enabled': True, 'monthly_limit': 1000, 'used_credits': 2000}}
        result = _snapshot_to_dict(_snap(usage=usage), installations=[])
        self.assertEqual(result['extra']['fill_pct'], 1.0)

    # -- installations --

    def test_installations_passthrough(self):
        """Pre-computed installations list is passed through unchanged."""
        installs = [{'name': 'VS Code', 'version': '1.0.0'}]
        result = _snapshot_to_dict(_snap(), installations=installs)
        self.assertEqual(result['installations'], installs)

    @patch('usage_monitor_for_claude.popup.find_installations')
    def test_installations_auto_detected(self, mock_find):
        """When installations is None, find_installations() is called."""
        inst = MagicMock()
        inst.name = 'Cursor'
        inst.version = '2.0.0'
        mock_find.return_value = [inst]

        result = _snapshot_to_dict(_snap(), installations=None)
        mock_find.assert_called_once()
        self.assertEqual(result['installations'], [{'name': 'Cursor', 'version': '2.0.0'}])

    # -- status --

    def test_status_error_when_no_usage(self):
        """Shows error text when there's no usage data but there's an error."""
        result = _snapshot_to_dict(_snap(usage={}, last_error='Connection failed'), installations=[])
        self.assertEqual(result['status']['text'], 'Connection failed')
        self.assertTrue(result['status']['is_error'])

    def test_status_error_truncated(self):
        """Error messages are truncated to 120 characters."""
        long_error = 'x' * 200
        result = _snapshot_to_dict(_snap(usage={}, last_error=long_error), installations=[])
        self.assertEqual(len(result['status']['text']), 120)

    def test_status_refreshing_when_no_usage_no_error(self):
        """Shows refreshing status when no usage data and no error."""
        from usage_monitor_for_claude.i18n import T

        result = _snapshot_to_dict(_snap(usage={}, last_error=None), installations=[])
        self.assertEqual(result['status']['text'], T['status_refreshing'])
        self.assertFalse(result['status']['is_error'])

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_status_live_mode_keys(self, _mock_mid, _mock_tu, _mock_ep):
        """Live mode status contains all required keys for the JS timer."""
        usage = {'five_hour': {'utilization': 50, 'resets_at': '2026-01-01T05:00:00Z'}}
        result = _snapshot_to_dict(
            _snap(usage=usage, last_success_time=1000.0, refreshing=True, last_error='Server down'),
            installations=[], next_poll_time=1180.0,
        )
        self.assertEqual(set(result['status'].keys()), {'last_success_time', 'next_poll_time', 'refreshing', 'error'})

    @patch('usage_monitor_for_claude.popup.elapsed_pct', return_value=None)
    @patch('usage_monitor_for_claude.popup.time_until', return_value='')
    @patch('usage_monitor_for_claude.popup.midnight_positions', return_value=[])
    def test_status_error_truncated_in_live_mode(self, _mock_mid, _mock_tu, _mock_ep):
        """Error messages are truncated to 120 characters in live mode."""
        usage = {'five_hour': {'utilization': 50, 'resets_at': '2026-01-01T05:00:00Z'}}
        long_error = 'x' * 200
        result = _snapshot_to_dict(
            _snap(usage=usage, last_error=long_error),
            installations=[],
        )
        self.assertEqual(len(result['status']['error']), 120)

    # -- top-level dict structure --

    def test_all_top_level_keys_present(self):
        """Result always has profile, usage, extra, installations, status."""
        result = _snapshot_to_dict(_snap(), installations=[])
        self.assertEqual(set(result.keys()), {'profile', 'usage', 'extra', 'installations', 'status'})


# ---------------------------------------------------------------------------
# _init_config
# ---------------------------------------------------------------------------

class TestInitConfig(unittest.TestCase):
    """Tests for _init_config - builds the JS init() config object."""

    def test_top_level_keys(self):
        """Config has colors, t (translations), app_version, and data."""
        config = _init_config(_snap())
        self.assertEqual(set(config.keys()), {'colors', 't', 'app_version', 'data'})

    def test_colors_from_settings(self):
        """Color values come from settings module constants."""
        from usage_monitor_for_claude.settings import BAR_BG, BAR_DIVIDER, BAR_FG, BAR_FG_WARN, BAR_MARKER, BG, FG, FG_DIM, FG_HEADING, FG_LINK

        config = _init_config(_snap())
        colors = config['colors']
        self.assertEqual(colors['bg'], BG)
        self.assertEqual(colors['fg'], FG)
        self.assertEqual(colors['fg_dim'], FG_DIM)
        self.assertEqual(colors['fg_heading'], FG_HEADING)
        self.assertEqual(colors['fg_link'], FG_LINK)
        self.assertEqual(colors['bar_bg'], BAR_BG)
        self.assertEqual(colors['bar_fg'], BAR_FG)
        self.assertEqual(colors['bar_fg_warn'], BAR_FG_WARN)
        self.assertEqual(colors['bar_divider'], BAR_DIVIDER)
        self.assertEqual(colors['bar_marker'], BAR_MARKER)

    def test_translations_from_i18n(self):
        """Translation values come from the T dict."""
        from usage_monitor_for_claude.i18n import T

        config = _init_config(_snap())
        t = config['t']
        self.assertEqual(t['title'], T['popup_title'])
        self.assertEqual(t['account'], T['account'])
        self.assertEqual(t['email'], T['email'])
        self.assertEqual(t['plan'], T['plan'])
        self.assertEqual(t['usage'], T['usage'])
        self.assertEqual(t['extra_usage'], T['extra_usage'])
        self.assertEqual(t['claude_code'], T['claude_code'])
        self.assertEqual(t['changelog'], T['changelog'])
        self.assertEqual(t['status_updated_s'], T['status_updated_s'])
        self.assertEqual(t['status_updated'], T['status_updated'])
        self.assertEqual(t['status_refreshing'], T['status_refreshing'])
        self.assertEqual(t['status_next_update'], T['status_next_update'])
        self.assertEqual(t['duration_hm'], T['duration_hm'])
        self.assertEqual(t['duration_m'], T['duration_m'])
        self.assertEqual(t['duration_s'], T['duration_s'])
        self.assertEqual(t['refresh'], T['refresh'])

    def test_app_version(self):
        """app_version matches the package version."""
        from usage_monitor_for_claude import __version__

        config = _init_config(_snap())
        self.assertEqual(config['app_version'], __version__)

    def test_data_is_snapshot_to_dict_output(self):
        """The data key contains the output of _snapshot_to_dict."""
        snap = _snap(profile={'account': {'email': 'a@b.com'}, 'organization': {}})
        config = _init_config(snap)
        self.assertEqual(config['data']['profile']['email'], 'a@b.com')
        self.assertEqual(set(config['data'].keys()), {'profile', 'usage', 'extra', 'installations', 'status'})


# ---------------------------------------------------------------------------
# _PopupApi.refresh
# ---------------------------------------------------------------------------

class TestPopupApiRefresh(unittest.TestCase):
    """Tests for _PopupApi.refresh - the JS-callable manual refresh bridge."""

    def test_refresh_delegates_to_request_refresh(self):
        """Calling API.refresh forwards to the popup's _request_refresh."""
        popup = MagicMock()
        api = _PopupApi(popup)
        api.refresh()
        popup._request_refresh.assert_called_once_with()


class TestRequestRefresh(unittest.TestCase):
    """Tests for UsagePopup._request_refresh re-entry and lifecycle guards."""

    def _bind(self, refreshing=False, running=True):
        """Build a stub instance that exposes only the attributes _request_refresh touches."""
        popup = UsagePopup.__new__(UsagePopup)
        popup._refreshing = refreshing
        popup._running = running
        popup.app = MagicMock()
        return popup

    def test_skipped_when_already_refreshing(self):
        """If a refresh is in flight, a second request is a no-op."""
        popup = self._bind(refreshing=True)
        with patch('threading.Thread') as thread_cls:
            UsagePopup._request_refresh(popup)
            thread_cls.assert_not_called()
        self.assertTrue(popup._refreshing)
        popup.app.update.assert_not_called()

    def test_skipped_when_closed(self):
        """If the popup has been closed, the request is dropped."""
        popup = self._bind(running=False)
        with patch('threading.Thread') as thread_cls:
            UsagePopup._request_refresh(popup)
            thread_cls.assert_not_called()
        self.assertFalse(popup._refreshing)
        popup.app.update.assert_not_called()

    def test_spawns_worker_when_idle(self):
        """Idle popup flips _refreshing and spawns a daemon worker thread."""
        popup = self._bind(refreshing=False, running=True)
        with patch('threading.Thread') as thread_cls:
            UsagePopup._request_refresh(popup)
            thread_cls.assert_called_once()
            kwargs = thread_cls.call_args.kwargs
            self.assertTrue(kwargs.get('daemon'))
            self.assertTrue(callable(kwargs.get('target')))
            thread_cls.return_value.start.assert_called_once()
        self.assertTrue(popup._refreshing)

    def _run_worker(self, popup):
        """Capture the worker thread target from _request_refresh and run it inline."""
        popup._push_snapshot = MagicMock()
        with patch('threading.Thread') as thread_cls:
            UsagePopup._request_refresh(popup)
            target = thread_cls.call_args.kwargs['target']
        target()
        return popup

    def test_worker_forces_update_then_clears_flag_and_pushes(self):
        """The worker fetches with force=True (bypass cooldown), clears the flag, pushes."""
        popup = self._bind(refreshing=False, running=True)
        self._run_worker(popup)
        popup.app.update.assert_called_once_with(force=True)
        self.assertFalse(popup._refreshing)
        popup._push_snapshot.assert_called_once_with()

    def test_worker_clears_flag_even_when_update_raises(self):
        """If app.update() raises, _refreshing is still cleared and no exception escapes."""
        popup = self._bind(refreshing=False, running=True)
        popup.app.update.side_effect = RuntimeError('boom')
        self._run_worker(popup)  # must not raise
        self.assertFalse(popup._refreshing)

    def test_worker_swallows_push_snapshot_failure(self):
        """A failure pushing the snapshot (e.g. window torn down) is swallowed."""
        popup = self._bind(refreshing=False, running=True)
        popup._push_snapshot = MagicMock(side_effect=RuntimeError('window gone'))
        with patch('threading.Thread') as thread_cls:
            UsagePopup._request_refresh(popup)
            target = thread_cls.call_args.kwargs['target']
        target()  # must not raise
        self.assertFalse(popup._refreshing)

    def test_request_refresh_allowed_again_after_completion(self):
        """After a worker completes and clears the flag, a new request spawns again."""
        popup = self._bind(refreshing=False, running=True)
        self._run_worker(popup)  # completes, clears _refreshing
        with patch('threading.Thread') as thread_cls:
            UsagePopup._request_refresh(popup)
            thread_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Content-height -> window-height compensation
# ---------------------------------------------------------------------------

class TestHeightCompensation(unittest.TestCase):
    """Tests for _set_content_height / _apply_height / _layout_and_reveal.

    These cover the fix for the footer being clipped on a secondary monitor
    whose DPI scale differs from the primary: the WebView viewport comes out
    shorter than the requested window height, so the window must be grown by
    the measured deficit (``_height_pad``) - all while still transparent, so
    the reveal happens once at the final size with no visible jump.
    """

    def setUp(self):
        self._saved_pad = UsagePopup._learned_pad
        self.addCleanup(lambda: setattr(UsagePopup, '_learned_pad', self._saved_pad))

    def _popup(self, *, shown=False, pad=0, applied=400, reported=True):
        p = UsagePopup.__new__(UsagePopup)
        p._content_height = 400
        p._applied_height = applied
        p._height_pad = pad
        p._shown = shown
        p._running = True
        p._content_reported = reported
        p._window = MagicMock()
        p._resize_and_position = MagicMock()
        p._reveal = MagicMock()
        return p

    def test_set_content_height_records_and_flags(self):
        """Reporting a height stores it and marks content as reported."""
        p = self._popup(shown=False, reported=False)
        p._set_content_height(553)
        self.assertEqual(p._content_height, 553)
        self.assertTrue(p._content_reported)
        # Before reveal, sizing is owned by the coordinator, not this call.
        p._resize_and_position.assert_not_called()

    def test_set_content_height_reapplies_after_reveal(self):
        """After reveal, a content change re-applies the height directly."""
        p = self._popup(shown=True, pad=50, applied=0)
        p._set_content_height(553)
        p._resize_and_position.assert_called_once_with(603)

    def test_set_content_height_ignores_zero(self):
        """A zero height (transient) is ignored."""
        p = self._popup(shown=True)
        p._set_content_height(0)
        p._resize_and_position.assert_not_called()

    def test_apply_height_uses_content_plus_pad(self):
        """Window target is content height plus the pad."""
        p = self._popup(pad=50, applied=0)
        p._content_height = 553
        p._apply_height()
        p._resize_and_position.assert_called_once_with(603)

    def test_apply_height_noop_when_unchanged(self):
        """No resize when the target equals the already-applied height."""
        p = self._popup(pad=0, applied=553)
        p._content_height = 553
        p._apply_height()
        p._resize_and_position.assert_not_called()

    def test_apply_height_deadband_ignores_small_change(self):
        """A sub-dead-band change is ignored (jitter suppression)."""
        p = self._popup(pad=50, applied=600)
        p._content_height = 553  # target 603, only 3 px from applied 600
        p._apply_height()
        p._resize_and_position.assert_not_called()

    def test_apply_height_force_bypasses_deadband(self):
        """force=True applies even a sub-dead-band change."""
        p = self._popup(pad=50, applied=600)
        p._content_height = 553  # target 603
        p._apply_height(force=True)
        p._resize_and_position.assert_called_once_with(603)

    def test_layout_and_reveal_bumps_pad_on_deficit(self):
        """A short viewport grows the pad, then the window is revealed once."""
        p = self._popup(shown=False, pad=0, applied=400)
        p._content_height = 553
        # viewport 503 (deficit 50) on the first probe, then 553 (converged)
        p._window.evaluate_js.side_effect = [503, 553]
        with patch('time.sleep'):
            p._layout_and_reveal()
        self.assertEqual(p._height_pad, 50)
        self.assertEqual(UsagePopup._learned_pad, 50)
        # Grown window was applied (553 + 50) and the reveal happened once.
        p._resize_and_position.assert_any_call(603)
        p._reveal.assert_called_once()

    def test_layout_and_reveal_no_pad_when_viewport_fits(self):
        """When the viewport already fits, the pad stays 0 and it reveals."""
        p = self._popup(shown=False, pad=0, applied=400)
        p._content_height = 553
        p._window.evaluate_js.return_value = 553
        with patch('time.sleep'):
            p._layout_and_reveal()
        self.assertEqual(p._height_pad, 0)
        p._resize_and_position.assert_called_with(553)
        p._reveal.assert_called_once()

    def test_layout_and_reveal_aborts_sizing_if_closed(self):
        """If the popup is closed before content is reported, no sizing happens.

        (The reveal still runs via the finally block, but the real _reveal
        no-ops when not running - see test_reveal_noop_when_closed.)
        """
        p = self._popup(shown=False, reported=False)
        p._running = False
        with patch('time.sleep'):
            p._layout_and_reveal()
        p._resize_and_position.assert_not_called()

    def test_layout_and_reveal_shrinks_stale_pad(self):
        """A pad cached from another monitor (too tall here) self-corrects down."""
        p = self._popup(shown=False, pad=50, applied=0)
        p._content_height = 553
        # Window started at 603 (content+50); viewport reads 603 here (single-DPI),
        # so deficit = 553-603 = -50 -> shrink pad to 0; next probe fits.
        p._window.evaluate_js.side_effect = [603, 553]
        with patch('time.sleep'):
            p._layout_and_reveal()
        self.assertEqual(p._height_pad, 0)
        p._resize_and_position.assert_any_call(553)
        p._reveal.assert_called_once()

    def test_layout_and_reveal_reveals_even_when_evaluate_js_raises(self):
        """An exception while measuring still reveals (finally) and leaves pad unchanged."""
        p = self._popup(shown=False, pad=0, applied=400)
        p._content_height = 553
        p._window.evaluate_js.side_effect = RuntimeError('webview gone')
        with patch('time.sleep'):
            p._layout_and_reveal()
        self.assertEqual(p._height_pad, 0)
        p._reveal.assert_called_once()

    def test_layout_and_reveal_continues_on_zero_inner(self):
        """A falsy innerHeight (0/None) is skipped without changing the pad."""
        p = self._popup(shown=False, pad=0, applied=400)
        p._content_height = 553
        p._window.evaluate_js.side_effect = [0, 553]
        with patch('time.sleep'):
            p._layout_and_reveal()
        self.assertEqual(p._height_pad, 0)
        p._reveal.assert_called_once()

    def test_apply_height_suppresses_change_equal_to_deadband(self):
        """A change of exactly the dead-band is suppressed (<= boundary)."""
        p = self._popup(pad=0, applied=559)
        p._content_height = 553  # |553-559| == 6 == deadband
        p._apply_height()
        p._resize_and_position.assert_not_called()

    def test_apply_height_applies_change_just_over_deadband(self):
        """A change just past the dead-band is applied."""
        p = self._popup(pad=0, applied=560)
        p._content_height = 553  # |553-560| == 7 > deadband
        p._apply_height()
        p._resize_and_position.assert_called_once_with(553)

    def test_reveal_noop_when_closed(self):
        """The real _reveal does nothing (stays hidden, no thread) when not running."""
        p = UsagePopup.__new__(UsagePopup)
        p._shown = False
        p._running = False
        with patch('threading.Thread') as thread_cls:
            UsagePopup._reveal(p)
            thread_cls.assert_not_called()
        self.assertFalse(p._shown)

    def test_reveal_is_best_effort_when_sizing_raises(self):
        """If sizing raises, _reveal still marks shown + starts the update loop.

        Guarantees the popup never ends up invisible-and-undismissable.
        """
        p = UsagePopup.__new__(UsagePopup)
        p._shown = False
        p._running = True
        p._popup_hwnd = 0
        p._apply_height = MagicMock(side_effect=RuntimeError('window torn down'))
        p._update_loop = MagicMock()
        with patch('threading.Thread') as thread_cls:
            UsagePopup._reveal(p)  # must not raise
            thread_cls.assert_called_once()
            thread_cls.return_value.start.assert_called_once()
        self.assertTrue(p._shown)


# ---------------------------------------------------------------------------
# _tray_position
# ---------------------------------------------------------------------------

class TestTrayPosition(unittest.TestCase):
    """Tests for UsagePopup._tray_position - popup placement near the tray.

    _tray_position receives a physical-pixel height (the actual window
    height after DPI scaling) and work-area bounds in physical pixels.
    It returns logical coordinates suitable for pywebview's move().
    """

    def _call(self, work_left, work_top, work_right, work_bottom, dpi, physical_width, physical_height,
              mon_left=0, mon_top=0):
        """Call _tray_position without constructing a full UsagePopup."""
        popup = object.__new__(UsagePopup)
        popup._popup_hwnd = 12345

        def fill_mon_info(_hmon, ptr):
            info = ctypes.cast(ptr, ctypes.POINTER(_MONITORINFO)).contents
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            info.rcMonitor.left = mon_left
            info.rcMonitor.top = mon_top
            info.rcMonitor.right = work_right
            info.rcMonitor.bottom = work_bottom
            info.rcWork.left = work_left
            info.rcWork.top = work_top
            info.rcWork.right = work_right
            info.rcWork.bottom = work_bottom

        with patch('ctypes.windll.user32.FindWindowW', return_value=99999), \
             patch('ctypes.windll.user32.MonitorFromWindow', return_value=11111), \
             patch('ctypes.windll.user32.GetMonitorInfoW', side_effect=fill_mon_info), \
             patch('ctypes.windll.user32.GetDpiForWindow', return_value=dpi):
            return popup._tray_position(physical_width, physical_height)

    def test_bottom_right_at_100_percent_scaling(self):
        """At 100% DPI, popup aligns to bottom-right of work area."""
        x, y = self._call(0, 0, 1920, 1040, _BASELINE_DPI, 340, 400)
        self.assertEqual(x, 1920 - 340 - 12)
        self.assertEqual(y, 1040 - 400 - 12)

    def test_bottom_right_at_125_percent_scaling(self):
        """At 125% DPI, logical coordinates place the popup within the work area."""
        scale = 120 / _BASELINE_DPI  # 1.25
        pw = int(340 * scale)
        ph = int(400 * scale)
        x, y = self._call(0, 0, 2400, 1300, 120, pw, ph)
        expected_x = int((2400 - pw - 12) / scale)
        expected_y = int((1300 - ph - 12) / scale)
        self.assertEqual(x, expected_x)
        self.assertEqual(y, expected_y)

    def test_bottom_right_at_150_percent_scaling(self):
        """At 150% DPI, logical coordinates place the popup within the work area."""
        scale = 144 / _BASELINE_DPI  # 1.5
        pw = int(340 * scale)
        ph = int(400 * scale)
        x, y = self._call(0, 0, 2880, 1560, 144, pw, ph)
        expected_x = int((2880 - pw - 12) / scale)
        expected_y = int((1560 - ph - 12) / scale)
        self.assertEqual(x, expected_x)
        self.assertEqual(y, expected_y)

    def test_taskbar_on_left(self):
        """When taskbar is on the left (work_area.left > 0), popup goes to the left edge."""
        x, y = self._call(60, 0, 1920, 1080, _BASELINE_DPI, 340, 400)
        self.assertEqual(x, 60 + 12)
        self.assertEqual(y, 1080 - 400 - 12)

    def test_taskbar_on_top(self):
        """When taskbar is on top (work_area.top > 0), popup goes to the top edge."""
        x, y = self._call(0, 40, 1920, 1080, _BASELINE_DPI, 340, 400)
        self.assertEqual(x, 1920 - 340 - 12)
        self.assertEqual(y, 40 + 12)

    def test_popup_fits_within_work_area_at_125_percent(self):
        """The popup's physical extent must not exceed the work area at 125% scaling."""
        dpi = 120
        scale = dpi / _BASELINE_DPI
        pw = int(340 * scale)
        ph = int(400 * scale)
        work_right = 2400
        work_bottom = 1300
        x, y = self._call(0, 0, work_right, work_bottom, dpi, pw, ph)
        # move() scales logical coords back to physical
        physical_x = x * scale
        physical_y = y * scale
        self.assertLessEqual(physical_x + pw, work_right)
        self.assertLessEqual(physical_y + ph, work_bottom)

    def test_taskbar_on_bottom_when_monitor_offset_left(self):
        """Popup goes to bottom-right even when the primary monitor is not at virtual x=0.

        Regression: the old code used ``work_area.left > 0`` which fired incorrectly
        whenever secondary monitors were positioned to the left of the primary,
        causing the popup to land at the left edge instead of the bottom-right corner.
        """
        # Primary monitor starts at virtual x=1920 (another monitor sits to its left).
        # Taskbar is at the bottom: work_left == mon_left, so NOT a left-side taskbar.
        x, y = self._call(1920, 0, 3840, 1040, _BASELINE_DPI, 340, 400, mon_left=1920)
        self.assertEqual(x, 3840 - 340 - 12)
        self.assertEqual(y, 1040 - 400 - 12)


# ---------------------------------------------------------------------------
# _resize_and_position
# ---------------------------------------------------------------------------

class TestResizeAndPosition(unittest.TestCase):
    """Tests for UsagePopup._resize_and_position - DPI-aware resize."""

    def _call(self, css_height, dpi):
        """Call _resize_and_position and capture the resize/move arguments."""
        popup = object.__new__(UsagePopup)
        popup.WIDTH = UsagePopup.WIDTH
        popup._popup_hwnd = 12345

        mock_window = MagicMock()
        popup._window = mock_window

        def fill_mon_info(_hmon, ptr):
            info = ctypes.cast(ptr, ctypes.POINTER(_MONITORINFO)).contents
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            info.rcMonitor.left = 0
            info.rcMonitor.top = 0
            info.rcMonitor.right = 1920
            info.rcMonitor.bottom = 1080
            info.rcWork.left = 0
            info.rcWork.top = 0
            info.rcWork.right = 1920
            info.rcWork.bottom = 1040

        with patch('ctypes.windll.user32.GetDpiForWindow', return_value=dpi), \
             patch('ctypes.windll.user32.FindWindowW', return_value=99999), \
             patch('ctypes.windll.user32.MonitorFromWindow', return_value=11111), \
             patch('ctypes.windll.user32.GetMonitorInfoW', side_effect=fill_mon_info):
            popup._resize_and_position(css_height)

        return mock_window

    def test_resize_at_100_percent(self):
        """At 100% DPI, resize uses CSS pixels directly (scale=1)."""
        mock = self._call(500, 96)
        mock.resize.assert_called_once_with(340, 500)

    def test_resize_at_125_percent(self):
        """At 125% DPI, resize receives logical pixels; pywebview scales internally."""
        mock = self._call(500, 120)
        mock.resize.assert_called_once_with(340, 500)

    def test_resize_at_150_percent(self):
        """At 150% DPI, resize receives logical pixels; pywebview scales internally."""
        mock = self._call(500, 144)
        mock.resize.assert_called_once_with(340, 500)

    def test_move_receives_logical_coordinates(self):
        """move() receives logical coordinates regardless of DPI."""
        mock = self._call(500, 120)
        x, y = mock.move.call_args[0]
        # Logical coordinates must be smaller than physical work area
        self.assertLess(x, 1920)
        self.assertLess(y, 1040)

    def test_window_fits_within_work_area_at_125_percent(self):
        """After resize + move at 125% DPI, the window stays within the work area."""
        dpi = 120
        scale = dpi / _BASELINE_DPI
        mock = self._call(500, dpi)
        resize_w, resize_h = mock.resize.call_args[0]
        move_x, move_y = mock.move.call_args[0]
        # pywebview 6.x scales both resize() and move() to physical internally
        self.assertLessEqual((move_x + resize_w) * scale, 1920)
        self.assertLessEqual((move_y + resize_h) * scale, 1040)

    def test_falls_back_to_system_dpi_when_window_dpi_unavailable(self):
        """When GetDpiForWindow returns 0, GetDpiForSystem is used as fallback."""
        popup = object.__new__(UsagePopup)
        popup.WIDTH = UsagePopup.WIDTH
        popup._popup_hwnd = 12345

        mock_window = MagicMock()
        popup._window = mock_window

        def fill_mon_info(_hmon, ptr):
            info = ctypes.cast(ptr, ctypes.POINTER(_MONITORINFO)).contents
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            info.rcMonitor.left = 0
            info.rcMonitor.top = 0
            info.rcMonitor.right = 1920
            info.rcMonitor.bottom = 1080
            info.rcWork.left = 0
            info.rcWork.top = 0
            info.rcWork.right = 1920
            info.rcWork.bottom = 1040

        with patch('ctypes.windll.user32.GetDpiForWindow', return_value=0), \
             patch('ctypes.windll.user32.GetDpiForSystem', return_value=144) as mock_sys_dpi, \
             patch('ctypes.windll.user32.FindWindowW', return_value=99999), \
             patch('ctypes.windll.user32.MonitorFromWindow', return_value=11111), \
             patch('ctypes.windll.user32.GetMonitorInfoW', side_effect=fill_mon_info):
            popup._resize_and_position(500)

        mock_sys_dpi.assert_called()
        mock_window.resize.assert_called_once_with(340, 500)


if __name__ == '__main__':
    unittest.main()
