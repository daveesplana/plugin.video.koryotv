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

from resources.lib import api, utils

ADDON      = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
BASE_URL   = sys.argv[0]
HANDLE     = int(sys.argv[1])
PARAMS     = dict(parse_qsl(sys.argv[2][1:]))

REPORT_PREFIX = 'Korean Central Television 8 PM Report'
REPORT_QUERY  = REPORT_PREFIX

# ---------------------------------------------------------------------------
# Live proxy
# ---------------------------------------------------------------------------

_PROXY_LOCK   = threading.Lock()
_PROXY_SERVER = None   # survives invoker teardown (module-level)
_STREAM_CACHE = {}     # channel_id -> (stream_url, cookie_str)


class _ProxyHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress access log spam

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
        except Exception as e:
            xbmc.log('[KoryoTV] Proxy playlist error: {} — clearing stream cache'.format(e), xbmc.LOGERROR)
            _STREAM_CACHE.clear()   # force fresh token on next play
            self.send_error(502, str(e))

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


def _ensure_proxy(remote_url, stream_headers):
    """Start proxy server once; subsequent calls just update remote_url/headers."""
    global _PROXY_SERVER
    with _PROXY_LOCK:
        if _PROXY_SERVER is not None:
            _PROXY_SERVER.remote_url   = remote_url
            _PROXY_SERVER.live_headers = stream_headers
            return _PROXY_SERVER

        class _Server(ThreadingHTTPServer):
            daemon_threads      = True
            allow_reuse_address = True

        server = _Server(('127.0.0.1', 0), _ProxyHandler)
        server.remote_url   = remote_url
        server.live_headers = stream_headers

        t = threading.Thread(target=server.serve_forever)
        t.daemon = True
        t.start()

        _PROXY_SERVER = server
        xbmc.log('[KoryoTV] Proxy started on port {}'.format(
            server.server_address[1]), xbmc.LOGINFO)
        return server


# ---------------------------------------------------------------------------
# Kodi helpers
# ---------------------------------------------------------------------------

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
    if cid == 'kctv':  return utils.kctv_icon()
    if cid == 'vok':   return utils.vok_icon()
    return utils.live_icon()


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

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
    xbmc.log('[KoryoTV] play_live: channel={}'.format(channel_id), xbmc.LOGINFO)

    # Reuse cached URL so replaying doesn't fetch a brand-new session/token.
    # Cache is cleared automatically if the playlist fetch fails (see proxy above).
    cached = _STREAM_CACHE.get(channel_id)
    if cached:
        stream_url, cookie_str = cached
        xbmc.log('[KoryoTV] Reusing cached stream: {}'.format(stream_url), xbmc.LOGINFO)
    else:
        dialog = xbmcgui.DialogProgress()
        dialog.create(ADDON_NAME, 'Connecting to live stream...')
        try:
            stream_url, cookie_str = api.get_live_stream_url(channel_id)
            _STREAM_CACHE[channel_id] = (stream_url, cookie_str)
            xbmc.log('[KoryoTV] Resolved stream: {}'.format(stream_url), xbmc.LOGINFO)
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
        'Referer':       'https://koryo.tv/channel/{}'.format(channel_id),
        'Cache-Control': 'no-cache',
        'Connection':    'keep-alive',
    }
    if cookie_str:
        stream_headers['Cookie'] = cookie_str

    proxy     = _ensure_proxy(stream_url, stream_headers)
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


# ---------------------------------------------------------------------------
# VOD helpers
# ---------------------------------------------------------------------------

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
            thumb = 'https://vod.koryo.tv' + thumb
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
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, 'Loading video...')
    try:
        media = api.get_media_detail(token)
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().notification(ADDON_NAME, 'Error: {}'.format(str(e)), xbmcgui.NOTIFICATION_ERROR)
        return
    dialog.close()

    stream_url = api.resolve_stream_url(media)
    if not stream_url:
        xbmcgui.Dialog().ok(ADDON_NAME, 'Could not find a playable stream for this video.')
        return

    title = media.get('title', 'Koryo TV')
    thumb = media.get('thumbnail_url', '')
    if thumb and thumb.startswith('/'):
        thumb = 'https://vod.koryo.tv' + thumb

    li = xbmcgui.ListItem(label=title, path=stream_url)
    set_video_info(li, title=title, plot=media.get('description', ''),
                   duration=media.get('duration', 0))
    li.setArt({'thumb': thumb, 'poster': thumb})
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

action = PARAMS.get('action', 'main')

if   action == 'main':           main_menu()
elif action == 'listing':        listing(page=PARAMS.get('page', 1), ordering=PARAMS.get('ordering', '-add_date'))
elif action == 'live':           live()
elif action == 'play_live':      play_live(channel_id=PARAMS.get('channel_id', 'kctv'), name=PARAMS.get('name', 'Live TV'))
elif action == 'search':         search()
elif action == 'search_results': search_results(query=PARAMS.get('query', ''), page=PARAMS.get('page', 1))
elif action == 'report':         report(page=PARAMS.get('page', 1))
elif action == 'donate':         donate()
elif action == 'play':           play(PARAMS.get('token', ''))
else:                            main_menu()
