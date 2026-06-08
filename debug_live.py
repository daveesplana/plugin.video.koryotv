import ssl
import http.client
import binascii
import os
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
    c = SimpleCookie(); c.load(cookie)
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
print('body2', r2.read()[:200])

if r2.status in (301, 302, 303, 307, 308):
    location = r2.getheader('Location')
    print('redirect', location)
    path = location if location.startswith('/') else location
    conn.request('GET', path, headers={
        'User-Agent': UA,
        'Origin': 'https://koryo.tv',
        'Referer': 'https://koryo.tv/',
        'Accept': '*/*',
        'Connection': 'keep-alive',
        'Cookie': cookie_str,
    })
    r3 = conn.getresponse()
    print('playlist', r3.status, r3.reason)
    print('content-type', r3.getheader('Content-Type'))
    print('head', r3.read(200))
conn.close()
