import json
import os
import binascii
import ssl
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

BASE     = 'https://vod.koryo.tv'
API_BASE = BASE + '/api/v1'
EDGE_HOST = 'edge-mcu.koryo.tv'
EDGE      = 'https://' + EDGE_HOST

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


def _get(url, extra_headers=None):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, headers=headers)
    try:
        response = urlopen(req, timeout=15, context=_ssl_context())
        raw = response.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return json.loads(raw)
    except TypeError:
        response = urlopen(req, timeout=15)
        raw = response.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return json.loads(raw)
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


def get_live_stream_url(channel_id):
    ctx = _ssl_context()
    conn = http_client.HTTPSConnection(EDGE_HOST, timeout=15, context=ctx)

    channel_referer = 'https://koryo.tv/channel/{}'.format(channel_id)
    live_headers = {
        'User-Agent':      UA,
        'Accept':          '*/*',
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
        # Choose session quality: radio channels use a radio-specific quality token
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

        # Radio channels use a different path pattern (observed in HAR): /radio/<id>/b/<token>.m3u8
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
            raise Exception(
                'Live endpoint returned HTTP {}'.format(resp2.status))

        if not location:
            raise Exception('No Location header in redirect response')

        if location.startswith('/'):
            final_url = EDGE + location
        elif location.startswith('http'):
            final_url = location
        else:
            final_url = EDGE + '/' + location

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return final_url, cookie_str


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
