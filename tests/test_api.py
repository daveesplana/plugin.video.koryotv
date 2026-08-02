import os
import sys
import time
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if len(sys.argv) < 2 or not sys.argv[1].lstrip('-').isdigit():
    sys.argv = [sys.argv[0], '-1', '']

xbmc_stub = types.ModuleType('xbmc')
xbmc_stub.log = lambda *args, **kwargs: None
xbmc_stub.LOGDEBUG = 0
xbmc_stub.LOGINFO = 1
xbmc_stub.LOGWARNING = 2
xbmc_stub.LOGERROR = 3
sys.modules.setdefault('xbmc', xbmc_stub)

class _StubListItem(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.label = kwargs.get('label', '')

    def getLabel(self):
        return self.label

    def getVideoInfoTag(self):
        return self

    def setTitle(self, *args, **kwargs):
        return None

    def setPlot(self, *args, **kwargs):
        return None

    def setDuration(self, *args, **kwargs):
        return None

    def setMediaType(self, *args, **kwargs):
        return None

    def setFirstAired(self, *args, **kwargs):
        return None

    def setInfo(self, *args, **kwargs):
        return None

    def setArt(self, *args, **kwargs):
        return None

    def setProperty(self, *args, **kwargs):
        return None

    def setPath(self, *args, **kwargs):
        return None

    def setMimeType(self, *args, **kwargs):
        return None

    def setContentLookup(self, *args, **kwargs):
        return None


class _StubDialog(object):
    def __init__(self, *args, **kwargs):
        pass

    def create(self, *args, **kwargs):
        return None

    def update(self, *args, **kwargs):
        return None

    def close(self):
        return None

    def ok(self, *args, **kwargs):
        return None

    def notification(self, *args, **kwargs):
        return None

    def select(self, *args, **kwargs):
        return -1


class _StubDialogProgress(object):
    def create(self, *args, **kwargs):
        return None

    def update(self, *args, **kwargs):
        return None

    def close(self):
        return None


xbmcgui_stub = types.ModuleType('xbmcgui')
xbmcgui_stub.Dialog = _StubDialog
xbmcgui_stub.DialogProgress = _StubDialogProgress
xbmcgui_stub.ListItem = _StubListItem
xbmcgui_stub.NOTIFICATION_ERROR = 0
xbmcgui_stub.NOTIFICATION_INFO = 1
sys.modules.setdefault('xbmcgui', xbmcgui_stub)

class _StubPlugin(object):
    SORT_METHOD_NONE = 0

    def addDirectoryItem(self, *args, **kwargs):
        return None

    def addSortMethod(self, *args, **kwargs):
        return None

    def endOfDirectory(self, *args, **kwargs):
        return None

    def setResolvedUrl(self, *args, **kwargs):
        return None

    def setPluginCategory(self, *args, **kwargs):
        return None


xbmcplugin_stub = types.ModuleType('xbmcplugin')
xbmcplugin_stub.addDirectoryItem = _StubPlugin().addDirectoryItem
xbmcplugin_stub.addSortMethod = _StubPlugin().addSortMethod
xbmcplugin_stub.endOfDirectory = _StubPlugin().endOfDirectory
xbmcplugin_stub.setResolvedUrl = _StubPlugin().setResolvedUrl
xbmcplugin_stub.setPluginCategory = _StubPlugin().setPluginCategory
xbmcplugin_stub.SORT_METHOD_NONE = _StubPlugin.SORT_METHOD_NONE
sys.modules.setdefault('xbmcplugin', xbmcplugin_stub)

class _StubAddon(object):
    def __init__(self):
        self._strings = {
            30030: 'Translated Live Broadcasts',
            30031: 'Translated Report',
            30032: 'Translated Revolutionary Activities',
            30033: 'Translated Society and Culture',
            30034: 'Translated Search',
            30035: 'Translated Support Koryo TV',
            30040: 'Translated Korean Central Television',
            30041: 'Translated Korean Central Broadcasting Station',
            30042: 'Translated Voice of Korea',
        }

    def getAddonInfo(self, key):
        if key == 'path':
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return ''

    def getLocalizedString(self, string_id):
        return self._strings.get(string_id, str(string_id))

    def getSetting(self, key):
        return ''

    def setSetting(self, key, value):
        return None

xbmcaddon_stub = types.ModuleType('xbmcaddon')
xbmcaddon_stub.Addon = lambda *args, **kwargs: _StubAddon()
sys.modules.setdefault('xbmcaddon', xbmcaddon_stub)

from resources.lib import api


class LiveChannelIdTests(unittest.TestCase):
    def test_cached_live_streams_expire_after_the_ttl(self):
        import default as default_module

        default_module._STREAM_CACHE.clear()
        original_time = default_module.time.time
        current_time = 1000.0
        default_module.time.time = lambda: current_time

        try:
            default_module._set_cached_stream('KCTV', 'http://example.test/stream.m3u8', 'cookie', 'edge', 'playlist', ttl=30)
            cached = default_module._get_cached_stream('KCTV')
            self.assertIsNotNone(cached)
            self.assertEqual(cached[0], 'http://example.test/stream.m3u8')

            current_time = 1031.0
            self.assertIsNone(default_module._get_cached_stream('KCTV'))
        finally:
            default_module.time.time = original_time
            default_module._STREAM_CACHE.clear()
    def test_channel_ids_are_normalized_for_live_paths(self):
        self.assertEqual(api._normalize_channel_id('KCTV'), 'kctv')
        self.assertEqual(api._normalize_channel_id('KCBS'), 'kcbs')
        self.assertEqual(api._normalize_channel_id('VOK'), 'vok')
        self.assertEqual(api._normalize_channel_id('kctv'), 'kctv')

    def test_custom_channel_ids_map_to_known_live_endpoints(self):
        self.assertEqual(api._normalize_channel_id('Channel KCTV'), 'kctv')
        self.assertEqual(api._normalize_channel_id('KCTV-1'), 'kctv')
        self.assertEqual(api._normalize_channel_id('Voice of Korea 2'), 'vok')

    def test_radio_channels_use_the_lowercase_endpoint_key(self):
        channel_key = api._normalize_channel_id('KCBS')
        self.assertIn(channel_key, ('kcbs', 'vok'))

    def test_live_channel_icon_selection_does_not_crash_for_kcbs(self):
        import default as default_module

        icon = default_module._channel_icon({'id': 'KCBS'})
        self.assertTrue(icon)

    def test_main_menu_uses_addon_localized_labels(self):
        import default as default_module

        captured = []
        original_add_directory_item = default_module.xbmcplugin.addDirectoryItem

        def fake_add_directory_item(handle, url, li, isFolder=False):
            captured.append(li.getLabel())

        default_module.xbmcplugin.addDirectoryItem = fake_add_directory_item
        try:
            default_module.main_menu()
        finally:
            default_module.xbmcplugin.addDirectoryItem = original_add_directory_item

        self.assertEqual(captured[0], 'Translated Live Broadcasts')
        self.assertEqual(captured[1], 'Translated Report')
        self.assertEqual(captured[2], 'Translated Revolutionary Activities')
        self.assertEqual(captured[3], 'Translated Society and Culture')
        self.assertEqual(captured[4], 'Translated Search')
        self.assertEqual(captured[5], '[COLOR gold]Translated Support Koryo TV[/COLOR]')

    def test_iptv_channel_ids_match_the_epg_source_channel_ids(self):
        import default as default_module

        channels = default_module._build_iptv_channels()
        ids = {entry['id'] for entry in channels}
        self.assertIn('KCTV', ids)
        self.assertIn('KCBS', ids)
        self.assertIn('VOK', ids)

    def test_json_epg_payload_is_converted_to_iptv_format(self):
        payload = {
            'programs': [{
                'channel': 'KCTV',
                'start': '2026-07-04T19:00:00+09:00',
                'stop': '2026-07-04T20:00:00+09:00',
                'title': 'News',
                'description': 'Evening bulletin',
            }]
        }

        epg = api.parse_json_epg(payload, wanted_channel_ids={'kctv'})
        self.assertIn('kctv', epg)
        self.assertEqual(epg['kctv'][0]['title'], 'News')
        self.assertEqual(epg['kctv'][0]['description'], 'Evening bulletin')

    def test_json_epg_payload_with_language_titles_and_time_only_times_is_converted(self):
        payload = {
            'channel': 'KCTV',
            'date': '2026-07-04',
            'programs': [{
                'start': '09:13',
                'end': '09:40',
                'title': {
                    'en': 'Morning News',
                    'ko': '아침 뉴스',
                },
                'category': 'News',
            }]
        }

        epg = api.parse_json_epg(payload, wanted_channel_ids={'kctv'})
        self.assertIn('kctv', epg)
        self.assertEqual(epg['kctv'][0]['title'], 'Morning News')
        self.assertEqual(epg['kctv'][0]['start'], '2026-07-04T09:13:00+09:00')
        self.assertEqual(epg['kctv'][0]['stop'], '2026-07-04T09:40:00+09:00')
        self.assertEqual(epg['kctv'][0]['genre'], 'News')

    def test_default_epg_url_uses_the_koryofront_epg_endpoint_for_kctv(self):
        url = api.build_default_epg_url()
        self.assertEqual(url, 'https://koryofront.org/api/epg?channel=KCTV')

    def test_default_iptv_epg_is_cached_for_a_day(self):
        original_urlopen = api.urlopen
        original_cache = api._DEFAULT_EPG_CACHE.copy()
        original_cache_key = getattr(api, '_DEFAULT_EPG_CACHE_KEY', None)
        calls = {'count': 0}

        xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="KCTV"><display-name lang="en">Korean Central Television</display-name></channel>
  <programme start="20260801120000 +0900" stop="20260801123000 +0900" channel="KCTV">
    <title>News</title>
  </programme>
</tv>'''

        class _FakeResponse(object):
            def read(self):
                return xml

        def fake_urlopen(req, timeout=20, context=None):
            calls['count'] += 1
            return _FakeResponse()

        api.urlopen = fake_urlopen
        api._DEFAULT_EPG_CACHE = {}
        api._DEFAULT_EPG_CACHE_KEY = ''

        try:
            first = api.get_default_iptv_epg(wanted_channel_ids={'kctv'})
            second = api.get_default_iptv_epg(wanted_channel_ids={'kctv'})
        finally:
            api.urlopen = original_urlopen
            api._DEFAULT_EPG_CACHE = original_cache
            api._DEFAULT_EPG_CACHE_KEY = original_cache_key

        self.assertEqual(calls['count'], 1)
        self.assertIn('kctv', first)
        self.assertIn('kctv', second)
        self.assertEqual(first['kctv'][0]['title'], 'News')
        self.assertEqual(second['kctv'][0]['title'], 'News')

    def test_xmltv_epg_channels_are_normalized_for_iptv_channel_ids(self):
        raw = b'''<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="KCTV"><display-name lang="en">Korean Central Television</display-name></channel>
  <programme start="20260706120000 +0900" stop="20260706123000 +0900" channel="KCTV">
    <title>News</title>
  </programme>
</tv>'''

        epg = api.parse_xmltv_epg(raw, wanted_channel_ids={'kctv'})
        self.assertIn('kctv', epg)
        self.assertEqual(epg['kctv'][0]['title'], 'News')

    def test_thumb_url_uses_the_kctv_thumbnail_endpoint(self):
        thumb = api.build_thumb_url('/recordings/News/8pm%20News%20%5B2026-07-04%5D.mp4', timestamp=5)
        self.assertIn('/api/kctv/thumb?', thumb)
        self.assertIn('path=%2Frecordings%2FNews%2F8pm%2520News%2520%255B2026-07-04%255D.mp4', thumb)
        self.assertIn('t=5', thumb)

    def test_kctv_media_list_payload_is_parsed_into_categories(self):
        payload = {
            'newsTitle': 'News',
            'activitiesTitle': "Respected Comrade Kim Jong Un's Revolutionary Activities",
            'societyAndCultureTitle': 'Society and Culture',
            'news': [{
                'title': '8pm News [2026/07/04]',
                'date': '2026-07-04',
                'url': '/recordings/News/8pm.mp4',
            }],
            'activities': [{
                'title': 'Activity Clip',
                'date': '2026-07-03',
                'url': '/recordings/Activities/clip.mp4',
            }],
            'societyAndCulture': [{
                'title': 'Culture Clip',
                'date': '2026-07-02',
                'url': '/recordings/Society/clip.mp4',
            }],
        }

        categories = api.parse_kctv_media_list(payload)
        self.assertEqual(categories[0]['key'], 'report')
        self.assertEqual(categories[0]['title'], 'Report')
        self.assertEqual(categories[1]['title'], "Respected Comrade Kim Jong Un's Revolutionary Activities")
        self.assertEqual(categories[2]['key'], 'societyAndCulture')
        self.assertEqual(categories[2]['title'], 'Society and Culture')
        self.assertEqual(categories[0]['items'][0]['title'], '8pm News [2026/07/04]')
        self.assertEqual(categories[0]['items'][0]['url'], 'https://kctv.koryofront.org/recordings/News/8pm.mp4')

    def test_server_test_hides_connection_status_when_server_mode_is_manual(self):
        import default as default_module

        captured = {'select_labels': None}

        class _StubSelectDialog(_StubDialog):
            def select(self, *args, **kwargs):
                captured['select_labels'] = args[1]
                return -1

        original_dialog = default_module.xbmcgui.Dialog
        original_addon_setting = default_module.ADDON.getSetting
        original_probe_all_servers = default_module.api.probe_all_servers

        default_module.xbmcgui.Dialog = _StubSelectDialog
        default_module.ADDON.getSetting = lambda key: '2' if key == 'server_mode' else ''
        default_module.api.probe_all_servers = lambda progress_callback=None: [
            {'host': 'edge-mtr.koryo.tv', 'label': 'Canada (MTR)', 'status': 'fast', 'latency_ms': 12, 'speed_mbps': 2.5},
        ]

        try:
            default_module.server_test()
        finally:
            default_module.xbmcgui.Dialog = original_dialog
            default_module.ADDON.getSetting = original_addon_setting
            default_module.api.probe_all_servers = original_probe_all_servers

        self.assertEqual(captured['select_labels'][0], '[COLOR cyan]🔄 Automatic (speed test on connect)[/COLOR]')
        self.assertEqual(captured['select_labels'][1], 'Canada (MTR)')
        self.assertNotIn('●', captured['select_labels'][1])
        self.assertNotIn('ms', captured['select_labels'][1])

    def test_name_mentions_are_bolded_in_all_localized_titles(self):
        import default as default_module

        labels = []
        original_add_directory_item = default_module.xbmcplugin.addDirectoryItem

        def fake_add_directory_item(handle, url, li, isFolder=False):
            labels.append(li.getLabel())

        default_module.xbmcplugin.addDirectoryItem = fake_add_directory_item
        default_module.api.get_media_list = lambda page=1, ordering='-add_date': {
            'categories': [
                {'key': 'activities', 'title': '경애하는 김정은동지의 혁명활동'},
                {'key': 'activities', 'title': '尊敬的同志金正恩革命活动'},
                {'key': 'activities', 'title': "Respected Comrade Kim Jong Un's Revolutionary Activities"},
            ]
        }

        try:
            default_module.media_categories()
        finally:
            default_module.xbmcplugin.addDirectoryItem = original_add_directory_item

        self.assertIn('[B]김정은[/B]', labels[0])
        self.assertIn('[B]金正恩[/B]', labels[1])
        self.assertIn('[B]Kim Jong Un[/B]', labels[2])

    def test_live_channel_labels_use_localized_strings(self):
        import default as default_module

        labels = []
        original_add_directory_item = default_module.xbmcplugin.addDirectoryItem

        def fake_add_directory_item(handle, url, li, isFolder=False):
            labels.append(li.getLabel())

        default_module.xbmcplugin.addDirectoryItem = fake_add_directory_item

        try:
            default_module.live()
        finally:
            default_module.xbmcplugin.addDirectoryItem = original_add_directory_item

        self.assertEqual(labels[0], 'Translated Korean Central Television')
        self.assertEqual(labels[1], 'Translated Korean Central Broadcasting Station')
        self.assertEqual(labels[2], 'Translated Voice of Korea')

    def test_report_results_replace_original_titles_with_localized_report_date_label(self):
        import default as default_module

        labels = []
        original_add_directory_item = default_module.xbmcplugin.addDirectoryItem

        def fake_add_directory_item(handle, url, li, isFolder=False):
            labels.append(li.getLabel())

        default_module.xbmcplugin.addDirectoryItem = fake_add_directory_item
        default_module.api.search_media = lambda query, page=1: {
            'results': [
                {'title': 'Korean Central Television 8 PM Report', 'date': '2026-07-25', 'url': '/recordings/report.mp4'}
            ],
            'count': 1,
            'next': None,
            'page': 1,
        }

        try:
            default_module.report(page=1)
        finally:
            default_module.xbmcplugin.addDirectoryItem = original_add_directory_item

        self.assertEqual(labels[0], 'Translated Report 2026-07-25')

    def test_media_category_report_items_replace_original_titles_with_localized_report_date_label(self):
        import default as default_module

        labels = []
        original_add_directory_item = default_module.xbmcplugin.addDirectoryItem

        def fake_add_directory_item(handle, url, li, isFolder=False):
            labels.append(li.getLabel())

        default_module.xbmcplugin.addDirectoryItem = fake_add_directory_item
        default_module.api.get_media_list = lambda page=1, ordering='-add_date': {
            'categories': [
                {
                    'key': 'report',
                    'title': 'Report',
                    'items': [
                        {'title': '8pm News [2026/07/26]', 'date': '2026-07-26', 'url': '/recordings/report.mp4'}
                    ],
                }
            ]
        }

        try:
            default_module.media_category('report')
        finally:
            default_module.xbmcplugin.addDirectoryItem = original_add_directory_item

        self.assertEqual(labels[0], 'Translated Report 2026-07-26')

    def test_play_media_item_uses_localized_report_title_when_plot_contains_report_date(self):
        import default as default_module

        captured = {}
        original_set_resolved_url = default_module.xbmcplugin.setResolvedUrl

        def fake_set_resolved_url(handle, succeeded, listitem=None):
            captured['label'] = listitem.getLabel()

        default_module.xbmcplugin.setResolvedUrl = fake_set_resolved_url

        try:
            default_module.play_media_item(
                'https://example.test/report.mp4',
                title='8pm News [2026/07/26]',
                plot='2026-07-26',
            )
        finally:
            default_module.xbmcplugin.setResolvedUrl = original_set_resolved_url

        self.assertEqual(captured['label'], 'Translated Report 2026-07-26')

    def test_default_entry_handles_incomplete_argv_safely(self):
        import importlib
        import sys

        original_argv = list(sys.argv)
        try:
            sys.argv = [sys.argv[0]]
            import default as default_module
            reloaded = importlib.reload(default_module)
            self.assertEqual(reloaded.HANDLE, -1)
            self.assertEqual(reloaded.PARAMS, {})
        finally:
            sys.argv = original_argv

    def test_live_channel_plot_shows_only_the_current_program_line(self):
        import datetime
        import default as default_module

        original_datetime = default_module.datetime.datetime

        class _FixedDateTime(original_datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.datetime(2026, 8, 1, 20, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=9)))

        default_module.datetime.datetime = _FixedDateTime
        default_module.api.get_default_iptv_epg = lambda wanted_channel_ids=None, timeout=20: {
            'kctv': [
                {'start': '2026-08-01T19:00:00+09:00', 'stop': '2026-08-01T20:00:00+09:00', 'title': 'News'},
                {'start': '2026-08-01T20:00:00+09:00', 'stop': '2026-08-01T21:00:00+09:00', 'title': 'Sports'},
                {'start': '2026-08-01T21:00:00+09:00', 'stop': '2026-08-01T22:00:00+09:00', 'title': 'Weather'},
                {'start': '2026-08-01T22:00:00+09:00', 'stop': '2026-08-01T23:00:00+09:00', 'title': 'Late Night'},
            ]
        }

        try:
            plot = default_module._build_live_channel_plot('kctv')
        finally:
            default_module.datetime.datetime = original_datetime

        self.assertEqual(plot, '[20:00]: Sports')

    def test_play_live_skips_progress_popup_when_server_mode_is_manual(self):
        import default as default_module

        create_calls = {'count': 0}

        class _StubManualProgress(object):
            def create(self, *args, **kwargs):
                create_calls['count'] += 1

            def update(self, *args, **kwargs):
                return None

            def close(self):
                return None

        original_progress = default_module.xbmcgui.DialogProgress
        original_addon_setting = default_module.ADDON.getSetting
        original_get_live_stream_url = default_module.api.get_live_stream_url

        default_module.xbmcgui.DialogProgress = _StubManualProgress
        default_module.ADDON.getSetting = lambda key: '2' if key == 'server_mode' else ''
        default_module.api.get_live_stream_url = lambda channel_key, progress_callback=None, forced_host=None: (
            'https://example.test/live.m3u8', '', 'edge-mtr.koryo.tv', 'playlist-1'
        )

        try:
            default_module.play_live('KCTV', 'Korean Central Television')
        finally:
            default_module.xbmcgui.DialogProgress = original_progress
            default_module.ADDON.getSetting = original_addon_setting
            default_module.api.get_live_stream_url = original_get_live_stream_url

        self.assertEqual(create_calls['count'], 0)


if __name__ == '__main__':
    unittest.main()
