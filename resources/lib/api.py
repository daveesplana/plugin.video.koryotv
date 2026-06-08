"""
API helpers for vod.koryo.tv (MediaCMS)
"""

import json
try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import urlopen, Request, URLError, HTTPError
    from urllib import urlencode

BASE = 'https://vod.koryo.tv'
API_BASE = BASE + '/api/v1'
PAGE_SIZE = 20

HEADERS = {
    'User-Agent': 'Kodi/Koryo-TV-Addon/1.0',
    'Accept': 'application/json',
}


def _get(url):
    """Perform a GET request and return parsed JSON."""
    req = Request(url, headers=HEADERS)
    try:
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
    """
    Fetch paginated media list.
    ordering options: -add_date, -views, -likes, add_date, title
    """
    params = {
        'page': int(page),
        'ordering': ordering,
    }
    url = '{}/media?{}'.format(API_BASE, urlencode(params))
    return _get(url)


def search_media(query, page=1):
    """
    Search for media using the dedicated /api/v1/search endpoint.
    Returns the same paginated structure as get_media_list.
    """
    params = {
        'q': query,
        'page': int(page),
    }
    url = '{}/search?{}'.format(API_BASE, urlencode(params))
    return _get(url)


def get_media_detail(token):
    """Fetch full detail for a single media item by friendly_token."""
    url = '{}/media/{}'.format(API_BASE, token)
    return _get(url)


def resolve_stream_url(media):
    """
    Pick the best available stream URL from a media detail dict.
    Priority:
      1. Original file (0-original h264)
      2. Highest available encoding resolution
      3. original_media_url field
    """
    base = BASE

    # Try encodings_info first
    encodings = media.get('encodings_info', {})

    # Prefer original
    original = encodings.get('0-original', {})
    if original:
        for codec, info in original.items():
            url = info.get('url', '')
            if url and info.get('status') == 'success':
                if url.startswith('/'):
                    url = base + url
                return url

    # Try resolutions from highest to lowest
    for res in ['1080', '720', '480', '360', '240', '144']:
        res_data = encodings.get(res, {})
        for codec, info in res_data.items():
            url = info.get('url', '')
            if url and info.get('status') == 'success':
                if url.startswith('/'):
                    url = base + url
                return url

    # Fallback to original_media_url
    fallback = media.get('original_media_url', '')
    if fallback:
        if fallback.startswith('/'):
            fallback = base + fallback
        return fallback

    return None
