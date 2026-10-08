"""Syntax-check all inline JS on rendered pages using node --check."""
import os
import re
import subprocess
import tempfile

import requests

BASE = 'http://localhost:5000'

user = requests.Session()
login_resp = user.post(BASE + '/api/login', json={'email': 'redesign_test@example.com', 'password': 'testpass'})
uid = login_resp.json()['user']['id']
admin = requests.Session()
admin.post(BASE + '/api/login', json={'email': 'admin@example.com', 'password': 'admin123'})

bookings = user.get(BASE + f'/api/users/{uid}/bookings').json()
pay_id = bookings[0]['id'] if bookings else 'BKGXXXXXXXX'

pages = {
    '/': requests.get(BASE + '/').text,
    '/login': requests.get(BASE + '/login').text,
    '/register': requests.get(BASE + '/register').text,
    '/dashboard': user.get(BASE + '/dashboard').text,
    '/stations': user.get(BASE + '/stations').text,
    '/stations/1': user.get(BASE + '/stations/1').text,
    '/history': user.get(BASE + '/history').text,
    '/notifications': user.get(BASE + '/notifications').text,
    '/book/1': user.get(BASE + '/book/1').text,
    f'/payment/{pay_id}': user.get(BASE + f'/payment/{pay_id}').text,
    '/admin': admin.get(BASE + '/admin').text,
}

failures = []
checked = 0
tmpdir = tempfile.mkdtemp()

for name, html in pages.items():
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    for idx, js in enumerate(scripts):
        checked += 1
        path = os.path.join(tmpdir, f'page{abs(hash(name))}_{idx}.js')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(js)
        proc = subprocess.run(['node', '--check', path], capture_output=True, text=True)
        if proc.returncode != 0:
            failures.append((name, idx, proc.stderr.strip()[:300]))

# static JS
checked += 1
proc = subprocess.run(['node', '--check', r'd:\EV-Charging-Station\static\js\main.js'],
                      capture_output=True, text=True)
if proc.returncode != 0:
    failures.append(('static/js/main.js', 0, proc.stderr.strip()[:300]))

print(f'Checked {checked} script blocks across {len(pages)} pages')
if failures:
    for name, idx, err in failures:
        print(f'FAIL {name} script#{idx}: {err}')
    raise SystemExit(1)
print('ALL INLINE SCRIPTS SYNTAX OK')
