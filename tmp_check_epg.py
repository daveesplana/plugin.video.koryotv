from resources.lib import api
wanted={'kctv','kcbs','vok'}
epg=api.get_default_iptv_epg(wanted_channel_ids=wanted)
print('URL', api.build_default_epg_url())
print('KEYS', sorted(epg.keys()))
for key in sorted(epg):
    if key in ('kctv','kcbs','vok'):
        print(key, len(epg[key]))
        if epg[key]:
            print(epg[key][0])
