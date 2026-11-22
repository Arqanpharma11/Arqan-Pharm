#!/usr/bin/env python3
"""Static correctness gates for the current Arkan candidate and trial feeds.

Reject malformed IDs, duplicated URLs between SKUs, unsafe schemes and accidental
promotion of unverified trial photos. Does not change or reclassify product images.
"""
import json
from pathlib import Path
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]
def load(name):
    return json.loads((root / 'data' / name).read_text(encoding='utf-8'))
quick = load('arkan-quick-image-candidates.json')
trial = load('arkan-trial-photo-feed.json')
auto = load('arkan-auto-published-images.json')
total = 4218
errors = []

def valid_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return False
    try:
        u = urlparse(value)
        return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password and u.hostname not in ('localhost','127.0.0.1')
    except ValueError:
        return False

def check_id(raw_id):
    return str(raw_id).isdigit() and 1 <= int(raw_id) <= total

def inspect(rows, name):
    seen = {}
    for identifier, url, title in rows:
        if not check_id(identifier):
            errors.append(f'{name}: invalid product ID {identifier}')
        if not valid_url(url):
            errors.append(f'{name}: invalid image URL for {identifier}')
        if not isinstance(title, str) or not title.strip():
            errors.append(f'{name}: empty candidate title for {identifier}')
        if url in seen and seen[url] != str(identifier):
            errors.append(f'{name}: same image URL assigned to {seen[url]} and {identifier}')
        seen[url] = str(identifier)

if quick.get('total') != total:
    errors.append('quick: catalog total mismatch')
rows = quick.get('byId', {})
if not isinstance(rows, dict):
    errors.append('quick: byId must be a dictionary')
    rows = {}
if quick.get('count') != len(rows):
    errors.append('quick: count field inconsistent with map')
inspect(((id, row[0] if isinstance(row, list) and len(row)>0 else '',
          row[1] if isinstance(row, list) and len(row)>1 else '')
         for id, row in rows.items()), 'quick')

if trial.get('mode') != 'trial' or trial.get('approvedForProduction') is not False:
    errors.append('trial: unverified content must never be production-approved')
if trial.get('catalogTotal') != total:
    errors.append('trial: catalog total mismatch')
entries = trial.get('items', [])
if not isinstance(entries, list):
    errors.append('trial: items must be a list')
    entries = []
if trial.get('trialImages') != len(entries):
    errors.append('trial: inconsistent count')
seen_ids = set()
for row in entries:
    pid = str(row.get('id', ''))
    if pid in seen_ids:
        errors.append(f'trial: repeated ID {pid}')
    seen_ids.add(pid)
    if row.get('status') != 'trial_unverified' or row.get('catalogMatch') != 'not_visually_verified':
        errors.append(f'trial: false verification status at {pid}')
inspect(((row.get('id'), row.get('imageUrl'), row.get('title')) for row in entries), 'trial')
if not isinstance(auto.get('byId', {}), dict):
    errors.append('auto: byId must be a dictionary')
else:
    for pid, row in auto.get('byId', {}).items():
        if not check_id(pid) or row.get('status') != 'auto_published_strict_unverified_pack':
            errors.append(f'auto: invalid publication record {pid}')
        if not valid_url(row.get('url')):
            errors.append(f'auto: invalid image URL {pid}')

if errors:
    raise SystemExit('Arkan image data validation FAILED:\n' + '\n'.join(errors[:30]))
print(f'PASS: {len(rows)} unique quick photo candidates, {len(entries)} distinct trial photos, '
      f'{len(auto.get("byId",{}))} correctly flagged auto records; no cross-SKU duplicate image URLs')
