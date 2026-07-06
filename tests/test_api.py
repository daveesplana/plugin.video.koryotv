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


xbmcgui_stub = types.ModuleType('xbmcgui')
xbmcgui_stub.Dialog = _StubDialog
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
    def getAddonInfo(self, key):
        if key == 'path':
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return ''

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

    def test_default_epg_url_uses_the_current_date(self):
        url = api.build_default_epg_url('2026-07-05')
        self.assertIn('date=2026-07-05', url)

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
        self.assertEqual(categories[0]['key'], 'news')
        self.assertEqual(categories[0]['title'], 'News')
        self.assertEqual(categories[1]['title'], "Respected Comrade Kim Jong Un's Revolutionary Activities")
        self.assertEqual(categories[2]['key'], 'societyAndCulture')
        self.assertEqual(categories[2]['title'], 'Society and Culture')
        self.assertEqual(categories[0]['items'][0]['title'], '8pm News [2026/07/04]')
        self.assertEqual(categories[0]['items'][0]['url'], 'https://kctv.koryofront.org/recordings/News/8pm.mp4')


if __name__ == '__main__':
    unittest.main()
