"""
Utility helpers for Koryo TV addon
"""

import os
import xbmcaddon

ADDON = xbmcaddon.Addon()
_MEDIA = os.path.join(ADDON.getAddonInfo('path'), 'resources', 'media')


def addon_icon():
    return os.path.join(_MEDIA, 'icon.png')

def play_icon():
    return os.path.join(_MEDIA, 'play.png')

def live_icon():
    return os.path.join(_MEDIA, 'live.png')

def kctv_icon():
    return os.path.join(_MEDIA, 'kctv.png')

def report_icon():
    return os.path.join(_MEDIA, 'bodo.png')

def search_icon():
    return os.path.join(_MEDIA, 'search.png')

def format_duration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return '{:d}:{:02d}:{:02d}'.format(hours, minutes, secs)
    return '{:d}:{:02d}'.format(minutes, secs)
