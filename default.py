"""
Koryo TV - Kodi Plugin
Streams video content from vod.koryo.tv
"""

import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from urllib.parse import urlencode, parse_qsl

from resources.lib import api, utils

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
BASE_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
PARAMS = dict(parse_qsl(sys.argv[2][1:]))

REPORT_PREFIX = 'Korean Central Television 8 PM Report'
REPORT_QUERY  = REPORT_PREFIX


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
            'title': title,
            'plot': plot,
            'duration': duration,
            'mediatype': 'video',
            'date': date,
        })


def main_menu():
    entries = [
        {
            'label': 'Latest Videos',
            'icon':  utils.play_icon(),
            'params': {'action': 'listing', 'page': 1, 'ordering': '-add_date'},
        },
        {
            'label': 'Report',
            'icon':  utils.play_icon(),
            'params': {'action': 'report', 'page': 1},
        },
        {
            'label': 'Search',
            'icon':  utils.search_icon(),
            'params': {'action': 'search'},
        },
        {
            'label': '[COLOR gold]Support / Donate to Koryo TV[/COLOR]',
            'icon':  utils.addon_icon(),
            'params': {'action': 'donate'},
        },
    ]

    for e in entries:
        li = xbmcgui.ListItem(label=e['label'])
        set_video_info(li, title=e['label'])
        li.setArt({'icon': e['icon'], 'thumb': e['icon']})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(e['params']), li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def donate():
    xbmcgui.Dialog().ok(
        'Support Koryo TV',
        'Keep DPRK media accessible to everyone.\n\n'
        'To donate, visit:\n[COLOR cyan]https://koryo.tv/donate[/COLOR]'
    )
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def _render_results(data, next_params, prev_params=None):
    """Shared renderer for listing and search results."""
    if not data or 'results' not in data:
        xbmcgui.Dialog().ok(ADDON_NAME, 'No results found.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    results = data['results']
    count = data.get('count', 0)
    has_next = bool(data.get('next'))
    total_pages = max(1, -(-count // 20))

    for item in results:
        token = item.get('friendly_token', '')
        title = item.get('title', 'Untitled')
        thumb = item.get('thumbnail_url', '')
        if thumb and thumb.startswith('/'):
            thumb = 'https://vod.koryo.tv' + thumb
        duration = item.get('duration', 0)
        views = item.get('views', 0)
        add_date = item.get('add_date', '')[:10]
        description = item.get('description', '')

        plot = description if description else 'Views: {}  |  Added: {}'.format(views, add_date)

        li = xbmcgui.ListItem(label=title)
        set_video_info(li, title=title, plot=plot, duration=duration, date=add_date)
        li.setArt({'thumb': thumb, 'poster': thumb, 'fanart': thumb})
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'play', 'token': token}), li, isFolder=False)

    cur_page = int(next_params.get('page', 2)) - 1

    # Previous page button
    if prev_params is not None:
        prev_page = int(prev_params.get('page', 1))
        li = xbmcgui.ListItem(label='[COLOR yellow]Previous Page ({}/{})[/COLOR]'.format(prev_page, total_pages))
        li.setArt({'icon': utils.play_icon(), 'thumb': utils.play_icon()})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(prev_params), li, isFolder=True)

    # Next page button
    if has_next:
        li = xbmcgui.ListItem(label='[COLOR yellow]Next Page ({}/{})[/COLOR]'.format(cur_page + 1, total_pages))
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

    prev_params = None
    if page > 1:
        prev_params = {'action': 'listing', 'page': page - 1, 'ordering': ordering}

    _render_results(
        data,
        {'action': 'listing', 'page': page + 1, 'ordering': ordering},
        prev_params=prev_params,
    )


def report(page=1):
    page = int(page)
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, 'Loading 8 PM News Reports...')
    try:
        data = api.search_media(query=REPORT_QUERY, page=page)
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().notification(ADDON_NAME, 'Error: {}'.format(str(e)), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    dialog.close()

    if data and 'results' in data:
        data['results'] = [i for i in data['results'] if i.get('title', '').startswith(REPORT_PREFIX)]

    prev_params = None
    if page > 1:
        prev_params = {'action': 'report', 'page': page - 1}

    _render_results(
        data,
        {'action': 'report', 'page': page + 1},
        prev_params=prev_params,
    )


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
    xbmcplugin.setPluginCategory(HANDLE, 'Search: "{}" - {} result{}'.format(
        query, count, 's' if count != 1 else ''))

    prev_params = None
    if page > 1:
        prev_params = {'action': 'search_results', 'query': query, 'page': page - 1}

    _render_results(
        data,
        {'action': 'search_results', 'query': query, 'page': page + 1},
        prev_params=prev_params,
    )


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
    set_video_info(li, title=title, plot=media.get('description', ''), duration=media.get('duration', 0))
    li.setArt({'thumb': thumb, 'poster': thumb})
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)


# --- Router ---

action = PARAMS.get('action', 'main')

if action == 'main':
    main_menu()
elif action == 'listing':
    listing(page=PARAMS.get('page', 1), ordering=PARAMS.get('ordering', '-add_date'))
elif action == 'search':
    search()
elif action == 'search_results':
    search_results(query=PARAMS.get('query', ''), page=PARAMS.get('page', 1))
elif action == 'report':
    report(page=PARAMS.get('page', 1))
elif action == 'donate':
    donate()
elif action == 'play':
    play(PARAMS.get('token', ''))
else:
    main_menu()
