import re
import threading
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, parse_qsl, parse_qs, quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from resources.lib import api, utils, iptvmanager

ADDON      = xbmcaddon.Addon()
ADDON_ID   = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
BASE_URL   = sys.argv[0]
HANDLE     = int(sys.argv[1])
PARAMS     = dict(parse_qsl(sys.argv[2][1:]))

REPORT_PREFIX = 'Korean Central Television 8 PM Report'
REPORT_QUERY  = REPORT_PREFIX

_STATUS_BADGE = {
    'fast':    'Fast',
    'ok':      'OK',
    'slow':    'Slow',
    'offline': 'Offline',
}

_PROXY_LOCK   = threading.Lock()
_PROXY_SERVER = None
_STREAM_CACHE = {}

_SESSION_REFRESH_INTERVAL = 25
_STREAM_CACHE_TTL = 60


class _ProxyHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)

        if parsed.path == '/live.m3u8':
            self._serve_playlist()
        elif parsed.path in ('/key', '/seg'):
            self._serve_passthrough(qs)
        else:
            self.send_error(404)

    def _fetch(self, url):
        req = Request(url, headers=self.server.live_headers)
        return urlopen(req, timeout=20, context=api._ssl_context())

    def _serve_playlist(self):
        tried_refresh = False
        while True:
            try:
                resp = self._fetch(self.server.remote_url)
                raw  = resp.read().decode('utf-8', errors='replace')
                base = self.server.remote_url

                lines = []
                for line in raw.splitlines():
                    stripped = line.strip()
                    if stripped.startswith('#EXT-X-KEY'):
                        m = re.search(r'URI="([^"]+)"', stripped)
                        if m:
                            abs_key = urljoin(base, m.group(1))
                            line = stripped.replace(
                                m.group(1),
                                '/key?u=' + quote(abs_key, safe='')
                            )
                    elif stripped and not stripped.startswith('#'):
                        abs_seg = urljoin(base, stripped)
                        line = '/seg?u=' + quote(abs_seg, safe='')
                    lines.append(line)

                body = '\r\n'.join(lines) + '\r\n'
                data = body.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data)
                return
            except HTTPError as he:
                if he.code == 404 and not tried_refresh and getattr(self.server, 'channel_id', None):
                    xbmc.log('[KoryoTV] Playlist 404 from {} — refreshing stream'.format(self.server.remote_url), xbmc.LOGWARNING)
                    tried_refresh = True
                    try:
                        new_url, new_cookie, new_host, new_playlist_id = api.get_live_stream_url(self.server.channel_id)
                        self.server.remote_url   = new_url
                        self.server.edge_host    = new_host
                        self.server.playlist_id  = new_playlist_id
                        if new_cookie:
                            self.server.live_headers['Cookie'] = new_cookie
                        self.server.last_refresh = time.time()
                        _set_cached_stream(self.server.channel_id, new_url, new_cookie, new_host, new_playlist_id)
                        continue
                    except Exception as e2:
                        xbmc.log('[KoryoTV] Playlist refresh failed: {}'.format(e2), xbmc.LOGERROR)
                        _STREAM_CACHE.clear()
                        self.send_error(502, str(e2))
                        return
                xbmc.log('[KoryoTV] Proxy playlist error: {} — clearing stream cache'.format(he), xbmc.LOGERROR)
                _STREAM_CACHE.clear()
                self.send_error(502, str(he))
                return
            except Exception as e:
                xbmc.log('[KoryoTV] Proxy playlist error: {} — clearing stream cache'.format(e), xbmc.LOGERROR)
                _STREAM_CACHE.clear()
                self.send_error(502, str(e))
                return

    def _serve_passthrough(self, qs):
        url = qs.get('u', [None])[0]
        if not url:
            self.send_error(400)
            return
        url = unquote(url)
        try:
            resp = self._fetch(url)
            data = resp.read()
            ct   = resp.getheader('Content-Type', 'application/octet-stream')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            xbmc.log('[KoryoTV] Proxy passthrough error: {}'.format(e), xbmc.LOGERROR)
            self.send_error(502, str(e))

import time as _time_mod
import time  # also expose as 'time' for the proxy handler's last_refresh assignment

def _set_cached_stream(channel_id, stream_url, cookie_str, edge_host, playlist_id, ttl=_STREAM_CACHE_TTL):
    now = time.time()
    _STREAM_CACHE[channel_id] = {
        'stream_url': stream_url,
        'cookie_str': cookie_str,
        'edge_host': edge_host,
        'playlist_id': playlist_id,
        'expires_at': now + ttl,
    }


def _get_cached_stream(channel_id):
    entry = _STREAM_CACHE.get(channel_id)
    if not entry:
        return None
    if time.time() >= entry.get('expires_at', 0):
        _STREAM_CACHE.pop(channel_id, None)
        return None
    return entry['stream_url'], entry['cookie_str'], entry['edge_host'], entry['playlist_id']


def _session_refresh_worker(server):
    while True:
        _time_mod.sleep(_SESSION_REFRESH_INTERVAL)
        try:
            host        = getattr(server, 'edge_host', None)
            playlist_id = getattr(server, 'playlist_id', None)
            channel_id  = getattr(server, 'channel_id', None)
            if not host or not playlist_id or not channel_id:
                continue

            old_cookie  = server.live_headers.get('Cookie', '')
            new_cookie  = api.refresh_session(host, playlist_id, channel_id, old_cookie)
            if new_cookie and new_cookie != old_cookie:
                server.live_headers['Cookie'] = new_cookie
                if channel_id in _STREAM_CACHE:
                    entry = _STREAM_CACHE[channel_id]
                    entry['cookie_str'] = new_cookie

            xbmc.log('[KoryoTV] Session auto-refreshed for {} playlist={}'.format(
                channel_id, playlist_id), xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log('[KoryoTV] Session refresh worker error: {}'.format(e), xbmc.LOGWARNING)


def _ensure_proxy(remote_url, stream_headers, channel_id=None, edge_host=None, playlist_id=None):
    global _PROXY_SERVER
    with _PROXY_LOCK:
        if _PROXY_SERVER is not None:
            _PROXY_SERVER.remote_url   = remote_url
            _PROXY_SERVER.live_headers = stream_headers
            _PROXY_SERVER.channel_id   = channel_id
            _PROXY_SERVER.edge_host    = edge_host
            _PROXY_SERVER.playlist_id  = playlist_id
            return _PROXY_SERVER

        class _Server(ThreadingHTTPServer):
            daemon_threads      = True
            allow_reuse_address = True

        server = _Server(('127.0.0.1', 0), _ProxyHandler)
        server.remote_url   = remote_url
        server.live_headers = stream_headers
        server.channel_id   = channel_id
        server.edge_host    = edge_host
        server.playlist_id  = playlist_id

        t = threading.Thread(target=server.serve_forever)
        t.daemon = True
        t.start()

        r = threading.Thread(target=_session_refresh_worker, args=(server,))
        r.daemon = True
        r.start()

        _PROXY_SERVER = server
        xbmc.log('[KoryoTV] Proxy started on port {}'.format(
            server.server_address[1]), xbmc.LOGINFO)
        return server

def build_url(params):
    return '{0}?{1}'.format(BASE_URL, urlencode(params))


def set_video_info(li, title='', plot='', duration=0, date=''):
    try:
        tag = li.getVideoInfoTag()
        tag.setTitle(title)
        tag.setPlot(plot)
        if duration:
            tag.setDuration(int(duration))
        tag.setMediaType('video')
        if date:
            tag.setFirstAired(date)
    except AttributeError:
        li.setInfo('video', {
            'title':    title,
            'plot':     plot,
            'duration': duration,
            'mediatype':'video',
            'date':     date,
        })


def _channel_icon(ch):
    cid = ch.get('id', '')
    try:
        key = api._normalize_channel_id(cid)
    except Exception:
        key = ''

    if key == 'kctv':
        return getattr(utils, 'kctv_icon', lambda: utils.live_icon())()
    if key == 'kcbs':
        return getattr(utils, 'kcbs_icon', lambda: utils.live_icon())()
    if key == 'vok':
        return getattr(utils, 'vok_icon', lambda: utils.live_icon())()

    try:
        return utils.live_icon()
    except Exception:
        return ''

def main_menu():
    entries = [
        {'label': 'Live Broadcasts',
         'icon':  utils.live_icon(),
         'params': {'action': 'live'},
         'isFolder': True},
        {'label': 'Video Library',
         'icon':  utils.play_icon(),
         'params': {'action': 'listing', 'page': 1, 'ordering': '-add_date'},
         'isFolder': True},
        {'label': 'News',
         'icon':  utils.report_icon(),
         'params': {'action': 'report', 'page': 1},
         'isFolder': True},
        {'label': 'Search',
         'icon':  utils.search_icon(),
         'params': {'action': 'search'},
         'isFolder': True},
        {'label': '[COLOR gold]Support Koryo TV[/COLOR]',
         'icon':  utils.addon2_icon(),
         'params': {'action': 'donate'},
         'isFolder': True},
    ]
    for e in entries:
        li = xbmcgui.ListItem(label=e['label'])
        set_video_info(li, title=e['label'])
        li.setArt({'icon': e['icon'], 'thumb': e['icon']})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(e['params']), li, isFolder=e['isFolder'])
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def live():
    for ch in api.LIVE_CHANNELS:
        li = xbmcgui.ListItem(label=ch['name'])
        set_video_info(li, title=ch['name'], plot='Live stream of {}'.format(ch['name']))
        icon = _channel_icon(ch)
        li.setArt({'icon': icon, 'thumb': icon})
        li.setProperty('IsPlayable', 'true')
        url = build_url({'action': 'play_live', 'channel_id': ch['id'], 'name': ch['name']})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def play_live(channel_id, name):
    channel_key = api._normalize_channel_id(channel_id)
    xbmc.log('[KoryoTV] play_live: channel={} (key={})'.format(channel_id, channel_key), xbmc.LOGINFO)

    cached = _get_cached_stream(channel_key)
    if not cached and channel_id:
        cached = _get_cached_stream(channel_id)
    if cached:
        stream_url, cookie_str, edge_host, playlist_id = cached
        xbmc.log('[KoryoTV] Reusing cached stream: {} (host={}, playlist={})'.format(
            stream_url, edge_host, playlist_id), xbmc.LOGINFO)
    else:
        server_mode = int(ADDON.getSetting('server_mode') or '0')
        forced_host = api.SETTINGS_SERVER_MAP.get(server_mode)

        dialog = xbmcgui.DialogProgress()
        if forced_host:
            label = api.SERVER_LABELS.get(forced_host, forced_host)
            dialog.create(ADDON_NAME, 'Connecting to {}...'.format(label))
        else:
            dialog.create(ADDON_NAME, 'Finding best server...')

        def _progress(percent, message):
            dialog.update(percent, message)

        try:
            stream_url, cookie_str, edge_host, playlist_id = api.get_live_stream_url(
                channel_key, progress_callback=_progress, forced_host=forced_host)
            _set_cached_stream(channel_key, stream_url, cookie_str, edge_host, playlist_id)
            if channel_id != channel_key:
                _set_cached_stream(channel_id, stream_url, cookie_str, edge_host, playlist_id)
            xbmc.log('[KoryoTV] Resolved stream: {} host={} playlist={}'.format(
                stream_url, edge_host, playlist_id), xbmc.LOGINFO)
        except Exception as e:
            dialog.close()
            xbmc.log('[KoryoTV] Live stream error: {}'.format(e), xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON_NAME, 'Live stream error:\n{}'.format(str(e)))
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
        dialog.close()

    stream_headers = {
        'User-Agent':    api.UA,
        'Accept':        '*/*',
        'Origin':        'https://koryo.tv',
        'Referer':       'https://koryo.tv/channel/{}'.format(channel_key),
        'Cache-Control': 'no-cache',
        'Connection':    'keep-alive',
    }
    if cookie_str:
        stream_headers['Cookie'] = cookie_str

    proxy     = _ensure_proxy(stream_url, stream_headers, channel_id, edge_host, playlist_id)
    port      = proxy.server_address[1]
    local_url = 'http://127.0.0.1:{}/live.m3u8'.format(port)
    xbmc.log('[KoryoTV] Proxy URL: {}'.format(local_url), xbmc.LOGINFO)

    li = xbmcgui.ListItem(label=name)
    li.setPath(local_url)
    set_video_info(li, title=name, plot='Live: {}'.format(name))
    li.setMimeType('application/vnd.apple.mpegurl')
    li.setContentLookup(False)
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)


def donate():
    xbmcgui.Dialog().ok(
        'Support Koryo TV',
        'Keep DPRK media accessible to everyone.\n\n'
        'To donate, visit:\n[COLOR cyan]https://koryo.tv/donate[/COLOR]'
    )
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)

def _render_results(data, next_params, prev_params=None):
    if not data or 'results' not in data:
        xbmcgui.Dialog().ok(ADDON_NAME, 'No results found.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    results     = data['results']
    count       = data.get('count', 0)
    has_next    = bool(data.get('next'))
    total_pages = max(1, -(-count // 20))

    for item in results:
        token       = item.get('friendly_token', '')
        title       = item.get('title', 'Untitled')
        thumb       = item.get('thumbnail_url', '')
        if thumb and thumb.startswith('/'):
            thumb = 'https://vod.koryofront.org' + thumb
        duration    = item.get('duration', 0)
        views       = item.get('views', 0)
        add_date    = item.get('add_date', '')[:10]
        description = item.get('description', '')
        plot        = description if description else 'Views: {}  |  Added: {}'.format(views, add_date)

        li = xbmcgui.ListItem(label=title)
        set_video_info(li, title=title, plot=plot, duration=duration, date=add_date)
        li.setArt({'thumb': thumb, 'poster': thumb, 'fanart': thumb})
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(
            HANDLE, build_url({'action': 'play', 'token': token}), li, isFolder=False)

    cur_page = int(next_params.get('page', 2)) - 1

    if prev_params is not None:
        prev_page = int(prev_params.get('page', 1))
        li = xbmcgui.ListItem(
            label='[COLOR yellow]Previous Page ({}/{})[/COLOR]'.format(prev_page, total_pages))
        li.setArt({'icon': utils.play_icon(), 'thumb': utils.play_icon()})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(prev_params), li, isFolder=True)

    if has_next:
        li = xbmcgui.ListItem(
            label='[COLOR yellow]Next Page ({}/{})[/COLOR]'.format(cur_page + 1, total_pages))
        li.setArt({'icon': utils.play_icon(), 'thumb': utils.play_icon()})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(next_params), li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def listing(page=1, ordering='-add_date'):
    page = int(page)
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, 'Loading videos...')
    try:
        data = api.get_media_list(page=page, ordering=ordering)
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().notification(ADDON_NAME, 'Error: {}'.format(str(e)), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    dialog.close()
    prev_params = {'action': 'listing', 'page': page - 1, 'ordering': ordering} if page > 1 else None
    _render_results(data, {'action': 'listing', 'page': page + 1, 'ordering': ordering},
                    prev_params=prev_params)


def report(page=1):
    page = int(page)
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, 'Loading...')
    try:
        data = api.search_media(query=REPORT_QUERY, page=page)
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().notification(ADDON_NAME, 'Error: {}'.format(str(e)), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    dialog.close()
    if data and 'results' in data:
        data['results'] = [i for i in data['results']
                           if i.get('title', '').startswith(REPORT_PREFIX)]
    prev_params = {'action': 'report', 'page': page - 1} if page > 1 else None
    _render_results(data, {'action': 'report', 'page': page + 1}, prev_params=prev_params)


def search():
    kb = xbmc.Keyboard('', 'Search Koryo TV')
    kb.doModal()
    if not kb.isConfirmed():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    query = kb.getText().strip()
    if not query:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    _do_search(query, page=1)


def _do_search(query, page=1):
    page = int(page)
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, 'Searching for "{}"...'.format(query))
    try:
        data = api.search_media(query=query, page=page)
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().notification(ADDON_NAME, 'Search error: {}'.format(str(e)), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    dialog.close()
    count = data.get('count', 0) if data else 0
    xbmcplugin.setPluginCategory(
        HANDLE, 'Search: "{}" - {} result{}'.format(query, count, 's' if count != 1 else ''))
    prev_params = {'action': 'search_results', 'query': query, 'page': page - 1} if page > 1 else None
    _render_results(data, {'action': 'search_results', 'query': query, 'page': page + 1},
                    prev_params=prev_params)


def search_results(query, page=1):
    _do_search(query, page=page)


def play(token):
    try:
        media = api.get_media_detail(token)
    except Exception as e:
        xbmcgui.Dialog().notification(ADDON_NAME, 'Error: {}'.format(str(e)), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    stream_url = api.resolve_stream_url(media)
    if not stream_url:
        xbmcgui.Dialog().ok(ADDON_NAME, 'Could not find a playable stream for this video.')
        return

    title = media.get('title', 'Koryo TV')
    thumb = media.get('thumbnail_url', '')
    if thumb and thumb.startswith('/'):
        thumb = 'https://vod.koryofront.org' + thumb

    li = xbmcgui.ListItem(label=title, path=stream_url)
    set_video_info(li, title=title, plot=media.get('description', ''),
                   duration=media.get('duration', 0))
    li.setArt({'thumb': thumb, 'poster': thumb})
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)


def server_test():
    """Run a speed test against all edge servers, show results, and let the user pick one."""
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, 'Testing servers...')

    results = api.probe_all_servers(
        progress_callback=lambda pct, msg: dialog.update(pct, msg)
    )
    dialog.close()

    STATUS_ICON = {
        'fast':    '[COLOR lime]●[/COLOR]',
        'ok':      '[COLOR yellow]●[/COLOR]',
        'slow':    '[COLOR orange]●[/COLOR]',
        'offline': '[COLOR red]●[/COLOR]',
    }

    select_labels = ['[COLOR cyan]🔄 Automatic (speed test on connect)[/COLOR]']
    index_to_mode = [0]

    host_to_mode = {v: k for k, v in api.SETTINGS_SERVER_MAP.items()}

    for r in results:
        host   = r['host']
        label  = r['label']
        status = r['status']
        icon   = STATUS_ICON.get(status, '●')

        if r['latency_ms'] is None:
            detail = '[COLOR red]Offline[/COLOR]'
        elif r['speed_mbps'] and r['speed_mbps'] > 0:
            detail = '{}ms  •  {:.1f} MB/s'.format(r['latency_ms'], r['speed_mbps'])
        else:
            detail = '{}ms'.format(r['latency_ms'])

        line = '{} {}  [COLOR grey]{}[/COLOR]'.format(icon, label, detail)
        select_labels.append(line)
        index_to_mode.append(host_to_mode.get(host, 0))

    current_mode = int(ADDON.getSetting('server_mode') or '0')
    current_index = 0
    for i, mode in enumerate(index_to_mode):
        if mode == current_mode:
            current_index = i
            break

    chosen = xbmcgui.Dialog().select(
        'Select Server  (current: {})'.format(
            'Automatic' if current_mode == 0
            else api.SERVER_LABELS.get(api.SETTINGS_SERVER_MAP.get(current_mode, ''), 'Unknown')
        ),
        select_labels,
        preselect=current_index
    )

    if chosen >= 0:
        new_mode = index_to_mode[chosen]
        ADDON.setSetting('server_mode', str(new_mode))
        if new_mode == 0:
            msg = 'Server set to Automatic (speed test on connect).'
        else:
            host  = api.SETTINGS_SERVER_MAP.get(new_mode, '')
            msg   = 'Server set to {}.'.format(api.SERVER_LABELS.get(host, host))
        xbmcgui.Dialog().notification(ADDON_NAME, msg, xbmcgui.NOTIFICATION_INFO, 3000)

    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)

def _iptv_stream_url(channel_id, name):
    return 'plugin://{}/?{}'.format(ADDON_ID, urlencode({
        'action': 'play_live', 'channel_id': channel_id, 'name': name}))


def _build_iptv_channels():
    channels = []
    for ch in api.LIVE_CHANNELS:
        cid = ch['id']
        channels.append({
            'id':     api.IPTV_CHANNEL_IDS.get(cid, cid),
            'name':   ch['name'],
            'stream': _iptv_stream_url(cid, ch['name']),
            'logo':   _channel_icon(ch),
            'group':  'Koryo TV',
            'radio':  cid in ('KCBS', 'VOK'),
        })
    return channels


def iptv_channels():
    if (ADDON.getSetting('iptv.enabled') or 'true').lower() != 'true':
        return
    port = PARAMS.get('port')
    if not port:
        return
    mgr = iptvmanager.IPTVManager(port)
    try:
        mgr.connect()
    except Exception as e:
        xbmc.log('[KoryoTV] IPTV Manager channels: socket connect failed: {}'.format(e), xbmc.LOGWARNING)
        return
    try:
        mgr.send({'version': 1, 'streams': _build_iptv_channels()})
    except Exception as e:
        xbmc.log('[KoryoTV] IPTV Manager channels: build failed: {}'.format(e), xbmc.LOGERROR)
        mgr.abort()


def iptv_epg():
    if (ADDON.getSetting('iptv.enabled') or 'true').lower() != 'true':
        return
    port = PARAMS.get('port')
    if not port:
        return
    mgr = iptvmanager.IPTVManager(port)
    try:
        mgr.connect()
    except Exception as e:
        xbmc.log('[KoryoTV] IPTV Manager EPG: socket connect failed: {}'.format(e), xbmc.LOGWARNING)
        return
    try:
        enabled = (ADDON.getSetting('iptv.enabled') or 'true').lower() == 'true'
        if not enabled:
            return
        wanted = set(api.IPTV_CHANNEL_IDS.values())
        epg = api.get_default_iptv_epg(wanted_channel_ids=wanted)
        mgr.send({'version': 1, 'epg': epg})
    except Exception as e:
        xbmc.log('[KoryoTV] IPTV Manager EPG: build failed: {}'.format(e), xbmc.LOGERROR)
        mgr.abort()


action = PARAMS.get('action', 'main')

if   action == 'main':           main_menu()
elif action == 'listing':        listing(page=PARAMS.get('page', 1), ordering=PARAMS.get('ordering', '-add_date'))
elif action == 'live':           live()
elif action == 'play_live':      play_live(channel_id=PARAMS.get('channel_id', 'KCTV'), name=PARAMS.get('name', 'Live TV'))
elif action == 'search':         search()
elif action == 'search_results': search_results(query=PARAMS.get('query', ''), page=PARAMS.get('page', 1))
elif action == 'report':         report(page=PARAMS.get('page', 1))
elif action == 'donate':         donate()
elif action == 'play':           play(PARAMS.get('token', ''))
elif action == 'server_test':    server_test()
elif action == 'iptv_channels':  iptv_channels()
elif action == 'iptv_epg':       iptv_epg()
else:                            main_menu()
