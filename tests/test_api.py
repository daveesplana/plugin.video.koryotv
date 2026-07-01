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

    def test_radio_channels_use_the_lowercase_endpoint_key(self):
        channel_key = api._normalize_channel_id('KCBS')
        self.assertIn(channel_key, ('kcbs', 'vok'))


if __name__ == '__main__':
    unittest.main()
