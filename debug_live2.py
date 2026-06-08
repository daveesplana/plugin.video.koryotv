import ssl
import http.client
import binascii
import os
import re
from http.cookies import SimpleCookie

EDGE_HOST = 'edge-mcu.koryo.tv'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
ctx = ssl.create_default_context()
conn = http.client.HTTPSConnection(EDGE_HOST, timeout=15, context=ctx)
headers = {
    'User-Agent': UA,
    'Origin': 'https://koryo.tv',
    'Referer': 'https://koryo.tv/',
    'Accept': 'application/json',
    'Connection': 'keep-alive',
}
conn.request('GET', '/session/anon?quality=1080p', headers=headers)
r = conn.getresponse()
print('session', r.status, r.reason)
print('set-cookie', r.getheader('Set-Cookie'))
print('body', r.read()[:200])

cookie_str = ''
cookie = r.getheader('Set-Cookie')
if cookie:
    c = SimpleCookie()
    c.load(cookie)
    cookie_str = '; '.join(f'{m.key}={m.value}' for m in c.values())

rand = binascii.hexlify(os.urandom(12)).decode('ascii')
conn.request('GET', f'/kctv/live/{rand}.m3u8', headers={
    'User-Agent': UA,
    'Origin': 'https://koryo.tv',
    'Referer': 'https://koryo.tv/',
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'Cookie': cookie_str,
})
r2 = conn.getresponse()
print('live', r2.status, r2.reason)
print('location', r2.getheader('Location'))
body2 = r2.read()
print('body2', body2[:200])

location = r2.getheader('Location')
if location.startswith('/'):
    path = location
else:
    path = location
conn.request('GET', path, headers={
    'User-Agent': UA,
    'Origin': 'https://koryo.tv',
    'Referer': 'https://koryo.tv/',
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'Cookie': cookie_str,
})
r3 = conn.getresponse()
data = r3.read().decode('utf-8')
print('playlist', r3.status, r3.reason)
print('content-type', r3.getheader('Content-Type'))
print('firstlines', data.splitlines()[:10])
keyline = [line for line in data.splitlines() if line.startswith('#EXT-X-KEY')][0]
print('keyline', keyline)
m = re.search(r'URI="([^\"]+)"', keyline)
keypath = m.group(1)
print('keypath', keypath)
conn.request('GET', keypath, headers={
    'User-Agent': UA,
    'Origin': 'https://koryo.tv',
    'Referer': 'https://koryo.tv/',
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'Cookie': cookie_str,
})
r4 = conn.getresponse()
print('key', r4.status, r4.reason, r4.getheader('Content-Type'))
print('keylen', len(r4.read()))
conn.close()
