import json
import os
import binascii
import ssl
import time
import xbmc
import xml.etree.ElementTree as ET
from http.cookies import SimpleCookie

try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
    from urllib.error import URLError, HTTPError
    import http.client as http_client
except ImportError:
    from urllib2 import urlopen, Request, URLError, HTTPError
    from urllib import urlencode
    import httplib as http_client

BASE       = 'https://vod.koryofront.org'
API_BASE   = BASE + '/api/v1'

EDGE_HOSTS = [
    'edge-mcu.koryo.tv',
    'edge-mtr.koryo.tv',
    'koryo.tv',
    'edge-mtr.koryo.tv',
    'edge-osk.koryo.tv',
    'edge-vvo.koryo.tv',
    'edge-jhb.koryo.tv',
]

SETTINGS_SERVER_MAP = {
    1: 'koryo.tv',
    2: 'edge-mtr.koryo.tv',
    3: 'edge-mcu.koryo.tv',
    4: 'edge-osk.koryo.tv',
    5: 'edge-vvo.koryo.tv',
    6: 'edge-jhb.koryo.tv',
}

SERVER_LABELS = {
    'koryo.tv':          'Kosovo (PRS)',
    'edge-mtr.koryo.tv': 'Canada (MTR)',
    'edge-mcu.koryo.tv': 'Macau (MCU)',
    'edge-osk.koryo.tv': 'Japan (OSK)',
    'edge-vvo.koryo.tv': 'Russia (VVO)',
    'edge-jhb.koryo.tv': 'South Africa (JHB)',
}
EDGE_HOST  = EDGE_HOSTS[0]
EDGE       = 'https://' + EDGE_HOST

LIVE_CHANNELS = [
    {
        'id':   'kctv',
        'name': 'Korean Central Television (KCTV)',
    },
    {
        'id':   'kcbs',
        'name': 'Korean Central Broadcasting Station',
        'group': 'Live Broadcasts',
    },
    {
        'id':   'vok',
        'name': 'Voice of Korea',
        'group': 'Live Broadcasts',
    },
]

IPTV_CHANNEL_IDS = {
    'kctv': 'KoreanCentralTelevision.kp',
    'kcbs': 'KoreanCentralBroadcastingStation.kp',
    'vok':  'VoiceOfKorea.kp',
}

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'

HEADERS = {
    'User-Agent': UA,
    'Accept':     'application/json',
    'Origin':     'https://koryo.tv',
    'Referer':    'https://koryo.tv/',
}

def _random_hex_token():
    return binascii.hexlify(os.urandom(12)).decode('ascii')

def _ssl_context():
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        return ssl._create_unverified_context()

def _cookies_from_set_cookie(header):
    if not header:
        return ''
    cookie = SimpleCookie()
    cookie.load(header)
    return '; '.join(['{}={}'.format(m.key, m.value) for m in cookie.values()])

def _parse_json(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        if not raw or not raw.strip():
            raise Exception(
                'VOD API returned no data. The service may be temporarily unavailable. Please try again later.')
        raise Exception(
            'VOD API returned invalid data. The service may be temporarily unavailable. Please try again later.')

def _get(url, extra_headers=None):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, headers=headers)
    try:
        response = urlopen(req, timeout=15, context=_ssl_context())
        raw = response.read()
        return _parse_json(raw)
    except TypeError:
        response = urlopen(req, timeout=15)
        raw = response.read()
        return _parse_json(raw)
    except HTTPError as e:
        raise Exception('HTTP {}: {}'.format(e.code, url))
    except URLError as e:
        raise Exception('Network error: {}'.format(str(e.reason)))

def get_media_list(page=1, ordering='-add_date'):
    params = {'page': int(page), 'ordering': ordering}
    url = '{}/media?{}'.format(API_BASE, urlencode(params))
    return _get(url)

def search_media(query, page=1):
    params = {'q': query, 'page': int(page)}
    url = '{}/search?{}'.format(API_BASE, urlencode(params))
    return _get(url)

def get_media_detail(token):
    url = '{}/media/{}'.format(API_BASE, token)
    return _get(url)

def _build_edge_url(host, location):
    if location.startswith('/'):
        return 'https://' + host + location
    elif location.startswith('http'):
        return location
    return 'https://' + host + '/' + location

def _probe_host_speed(host, timeout=10.0):
    ctx = _ssl_context()
    t = int(time.time() * 1000)
    probe_path = '/speedtest/probe?bytes=8388608&t={}'.format(t)

    conn = None
    try:
        conn = http_client.HTTPSConnection(host, timeout=timeout, context=ctx)
        headers = {
            'User-Agent':    UA,
            'Accept':        '*/*',
            'Cache-Control': 'no-cache',
            'Pragma':        'no-cache',
            'Origin':        'https://koryo.tv',
            'Referer':       'https://koryo.tv/',
        }
        start = time.time()
        conn.request('GET', probe_path, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        elapsed = time.time() - start
        if resp.status == 200 and len(data) > 0 and elapsed > 0:
            speed_mbps = len(data) / elapsed / (1024 * 1024)
            xbmc.log('[KoryoTV] Speedtest {}: {:.2f} MB/s in {:.2f}s'.format(
                host, speed_mbps, elapsed), xbmc.LOGDEBUG)
            return speed_mbps
    except Exception as e:
        xbmc.log('[KoryoTV] Speedtest probe failed for {}: {}'.format(host, e), xbmc.LOGDEBUG)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    conn = None
    try:
        conn = http_client.HTTPSConnection(host, timeout=5, context=ctx)
        headers = {'User-Agent': UA, 'Accept': '*/*'}
        start = time.time()
        conn.request('GET', '/health', headers=headers)
        resp = conn.getresponse()
        resp.read()
        elapsed = time.time() - start
        if resp.status == 200 and elapsed > 0:
            pseudo = 0.001 / elapsed
            xbmc.log('[KoryoTV] Health probe {}: {:.3f}s (pseudo-speed {:.4f})'.format(
                host, elapsed, pseudo), xbmc.LOGDEBUG)
            return pseudo
    except Exception as e:
        xbmc.log('[KoryoTV] Health probe failed for {}: {}'.format(host, e), xbmc.LOGWARNING)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    return None

def _get_live_stream_url_for_host(channel_id, host):
    ctx = _ssl_context()
    conn = http_client.HTTPSConnection(host, timeout=15, context=ctx)

    channel_referer = 'https://koryo.tv/channel/{}'.format(channel_id)
    live_headers = {
        'User-Agent':      UA,
        'Accept':          'application/json',
        'Accept-Language': 'en-US,en;q=0.5',
        'Origin':          'https://koryo.tv',
        'Referer':         channel_referer,
        'Cache-Control':   'no-cache',
        'Pragma':          'no-cache',
        'TE':              'trailers',
        'Sec-Fetch-Dest':  'empty',
        'Sec-Fetch-Mode':  'cors',
        'Sec-Fetch-Site':  'same-origin',
        'Connection':      'keep-alive',
    }

    try:
        if channel_id in ('kcbs', 'vok'):
            quality = 'radio-{}'.format(channel_id)
        else:
            quality = '1080p'

        conn.request('GET', '/session/anon?quality={}'.format(quality), headers=live_headers)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            raise Exception(
                'Session endpoint returned HTTP {} — body: {}'.format(
                    resp.status, body[:200].decode('utf-8', errors='replace')))

        cookie_str = _cookies_from_set_cookie(resp.getheader('Set-Cookie', ''))
        random_token = _random_hex_token()

        live_headers2 = dict(live_headers)
        live_headers2['Accept'] = '*/*'
        if cookie_str:
            live_headers2['Cookie'] = cookie_str

        if quality.startswith('radio-'):
            live_path = '/radio/{}/b/{}.m3u8'.format(channel_id, random_token)
        else:
            live_path = '/{}/live/{}.m3u8'.format(channel_id, random_token)

        conn.request('GET', live_path, headers=live_headers2)
        resp2 = conn.getresponse()
        resp2.read()

        if resp2.status in (301, 302, 303, 307, 308):
            location = resp2.getheader('Location', '')
        elif resp2.status == 200:
            location = live_path
        else:
            raise Exception('Live endpoint returned HTTP {}'.format(resp2.status))

        if not location:
            raise Exception('No Location header in redirect response')

        final_url = _build_edge_url(host, location)

        playlist_id = None
        import re as _re
        m = _re.search(r'/pl/([0-9a-f]+)\.m3u8', final_url)
        if m:
            playlist_id = m.group(1)

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return final_url, cookie_str, playlist_id

def refresh_session(host, playlist_id, channel_id, cookie_str=''):

    ctx = _ssl_context()
    path = '/session/refresh?playlistId={}'.format(playlist_id)
    headers = {
        'User-Agent':    UA,
        'Accept':        'application/json',
        'Origin':        'https://koryo.tv',
        'Referer':       'https://koryo.tv/channel/{}'.format(channel_id),
        'Cache-Control': 'no-cache',
        'Pragma':        'no-cache',
    }
    if cookie_str:
        headers['Cookie'] = cookie_str

    conn = None
    try:
        conn = http_client.HTTPSConnection(host, timeout=10, context=ctx)
        conn.request('GET', path, headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status == 200:
            new_cookie = _cookies_from_set_cookie(resp.getheader('Set-Cookie', ''))
            if new_cookie:
                cookie_str = new_cookie
            xbmc.log('[KoryoTV] Session refreshed for playlist {}'.format(playlist_id), xbmc.LOGDEBUG)
        else:
            raise Exception('session/refresh HTTP {}: {}'.format(
                resp.status, body[:200].decode('utf-8', errors='replace')))
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    return cookie_str

def probe_all_servers(progress_callback=None):

    results = []
    total   = len(EDGE_HOSTS)

    def _cb(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    for i, host in enumerate(EDGE_HOSTS):
        pct   = int(i * 100 / total)
        label = SERVER_LABELS.get(host, host)
        _cb(pct, 'Testing {}...'.format(label))

        ctx = _ssl_context()
        t   = int(time.time() * 1000)
        probe_path = '/speedtest/probe?bytes=8388608&t={}'.format(t)
        conn = None
        latency_ms  = None
        speed_mbps  = None

        try:
            conn  = http_client.HTTPSConnection(host, timeout=10, context=ctx)
            headers = {
                'User-Agent':    UA,
                'Accept':        '*/*',
                'Cache-Control': 'no-cache',
                'Origin':        'https://koryo.tv',
                'Referer':       'https://koryo.tv/',
            }
            start = time.time()
            conn.request('GET', probe_path, headers=headers)
            resp  = conn.getresponse()
            data  = resp.read()
            elapsed = time.time() - start
            if resp.status == 200 and len(data) > 0 and elapsed > 0:
                latency_ms = round(elapsed * 1000)
                speed_mbps = round(len(data) / elapsed / (1024 * 1024), 1)
        except Exception:
            pass
        finally:
            try:
                if conn: conn.close()
            except Exception:
                pass

        if latency_ms is None:
            conn = None
            try:
                conn  = http_client.HTTPSConnection(host, timeout=5, context=ctx)
                start = time.time()
                conn.request('GET', '/health', headers={'User-Agent': UA, 'Accept': '*/*'})
                resp  = conn.getresponse()
                resp.read()
                elapsed = time.time() - start
                if resp.status == 200:
                    latency_ms = round(elapsed * 1000)
                    speed_mbps = 0.0
            except Exception:
                pass
            finally:
                try:
                    if conn: conn.close()
                except Exception:
                    pass

        if latency_ms is None:
            status = 'offline'
        elif speed_mbps and speed_mbps >= 15:
            status = 'fast'
        elif speed_mbps and speed_mbps >= 5:
            status = 'ok'
        else:
            status = 'slow'

        results.append({
            'host':       host,
            'label':      label,
            'latency_ms': latency_ms,
            'speed_mbps': speed_mbps,
            'status':     status,
        })
        _cb(int((i + 1) * 100 / total), '{}: {}'.format(
            label,
            'offline' if latency_ms is None else '{}ms • {} Mbps'.format(
                latency_ms, speed_mbps if speed_mbps is not None else '—')
        ))

    return results

def get_live_stream_url(channel_id, progress_callback=None, forced_host=None):

    def _cb(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    if forced_host:
        label = SERVER_LABELS.get(forced_host, forced_host)
        _cb(50, 'Connecting to {}...'.format(label))
        try:
            final_url, cookie_str, playlist_id = _get_live_stream_url_for_host(channel_id, forced_host)
            _cb(100, 'Connected to {}!'.format(label))
            xbmc.log('[KoryoTV] Forced host {} -> {}'.format(forced_host, final_url), xbmc.LOGINFO)
            return final_url, cookie_str, forced_host, playlist_id
        except Exception as e:
            raise Exception('Server {} failed: {}'.format(label, e))

    total_hosts    = len(EDGE_HOSTS)
    speed_per_host = 70 // total_hosts if total_hosts else 10

    results = []
    for i, host in enumerate(EDGE_HOSTS):
        base_pct = i * speed_per_host
        label    = SERVER_LABELS.get(host, host)
        _cb(base_pct, 'Testing {}...'.format(label))
        try:
            speed = _probe_host_speed(host, timeout=10.0)
            if speed is not None:
                results.append((speed, host))
                _cb(base_pct + speed_per_host, '{}: {:.1f} MB/s'.format(label, speed))
            else:
                _cb(base_pct + speed_per_host, '{}: unreachable'.format(label))
        except Exception:
            _cb(base_pct + speed_per_host, '{}: failed'.format(label))

    if results:
        results.sort(key=lambda x: x[0], reverse=True)
        order      = [h for _, h in results] + [
            h for h in EDGE_HOSTS if h not in [hh for _, hh in results]]
        best_host  = order[0]
        best_speed = next(s for s, h in results if h == best_host)
        best_label = SERVER_LABELS.get(best_host, best_host)
        _cb(72, 'Best server: {} ({:.1f} MB/s)'.format(best_label, best_speed))
    else:
        order = EDGE_HOSTS[:]
        _cb(72, 'No speed data — trying default order')

    xbmc.log('[KoryoTV] Edge host order by speed: {}'.format(order), xbmc.LOGINFO)

    connect_hosts = order
    connect_total = len(connect_hosts)
    connect_range = 28

    errors = []
    for idx, host in enumerate(connect_hosts):
        pct   = 72 + (idx * connect_range // connect_total)
        label = SERVER_LABELS.get(host, host)
        _cb(pct, 'Connecting to {}...'.format(label))
        xbmc.log('[KoryoTV] Trying host: {}'.format(host), xbmc.LOGDEBUG)
        try:
            final_url, cookie_str, playlist_id = _get_live_stream_url_for_host(channel_id, host)
            xbmc.log('[KoryoTV] Chosen host {} -> {} (playlist={})'.format(
                host, final_url, playlist_id), xbmc.LOGINFO)
            _cb(100, 'Connected to {}!'.format(label))
            return final_url, cookie_str, host, playlist_id
        except Exception as e:
            xbmc.log('[KoryoTV] Host {} failed: {}'.format(host, e), xbmc.LOGWARNING)
            errors.append('{}: {}'.format(host, e))

    raise Exception('All live servers failed: {}'.format('; '.join(errors)))

def resolve_stream_url(media):
    base = BASE
    encodings = media.get('encodings_info', {})

    original = encodings.get('0-original', {})
    if original:
        for codec, info in original.items():
            url = info.get('url', '')
            if url and info.get('status') == 'success':
                if url.startswith('/'):
                    url = base + url
                return url

    for res in ['1080', '720', '480', '360', '240', '144']:
        res_data = encodings.get(res, {})
        for codec, info in res_data.items():
            url = info.get('url', '')
            if url and info.get('status') == 'success':
                if url.startswith('/'):
                    url = base + url
                return url

    fallback = media.get('original_media_url', '')
    if fallback:
        if fallback.startswith('/'):
            fallback = base + fallback
        return fallback

    return None


def _xmltv_time_to_iso(value):
    value = (value or '').strip()
    if not value:
        return None
    parts = value.split(' ')
    dt_part = parts[0]
    tz_part = parts[1] if len(parts) > 1 and parts[1] else '+0000'
    if len(dt_part) < 14:
        return None
    y, mo, d  = dt_part[0:4], dt_part[4:6], dt_part[6:8]
    h, mi, s  = dt_part[8:10], dt_part[10:12], dt_part[12:14]
    sign      = tz_part[0] if tz_part[0] in ('+', '-') else '+'
    tz_digits = tz_part.lstrip('+-')
    tz_h      = tz_digits[0:2] or '00'
    tz_m      = tz_digits[2:4] or '00'
    return '{}-{}-{}T{}:{}:{}{}{}:{}'.format(y, mo, d, h, mi, s, sign, tz_h, tz_m)


def fetch_xmltv(url, timeout=20):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/xml, text/xml, */*'})
    try:
        resp = urlopen(req, timeout=timeout, context=_ssl_context())
    except TypeError:
        resp = urlopen(req, timeout=timeout)
    return resp.read()


def parse_xmltv_epg(raw, wanted_channel_ids=None):
    root = ET.fromstring(raw)

    epg = {}
    seen = set()

    for prog in root.findall('programme'):
        channel_id = prog.get('channel')
        if not channel_id:
            continue
        if wanted_channel_ids is not None and channel_id not in wanted_channel_ids:
            continue

        start_iso = _xmltv_time_to_iso(prog.get('start'))
        stop_iso  = _xmltv_time_to_iso(prog.get('stop'))
        if not start_iso or not stop_iso:
            continue

        title_el = prog.find('title')
        title = (title_el.text or '').strip() if title_el is not None else ''
        if not title:
            continue

        dedup_key = (channel_id, start_iso, stop_iso, title)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        entry = {'start': start_iso, 'stop': stop_iso, 'title': title}

        desc_el = prog.find('desc')
        if desc_el is not None and desc_el.text and desc_el.text.strip():
            entry['description'] = desc_el.text.strip()

        category_el = prog.find('category')
        if category_el is not None and category_el.text and category_el.text.strip():
            entry['genre'] = category_el.text.strip()

        epg.setdefault(channel_id, []).append(entry)

    return epg


def get_iptv_epg(url, wanted_channel_ids=None, timeout=20):
    if not url:
        return {}
    try:
        raw = fetch_xmltv(url, timeout=timeout)
        return parse_xmltv_epg(raw, wanted_channel_ids=wanted_channel_ids)
    except Exception as e:
        xbmc.log('[KoryoTV] EPG fetch/parse failed for {}: {}'.format(url, e), xbmc.LOGWARNING)
        return {}
