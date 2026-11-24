#!/usr/bin/env python3
"""Static correctness gates for the current Arkan candidate and trial feeds.

Reject malformed IDs, duplicated URLs between SKUs, unsafe schemes and accidental
promotion of unverified trial photos. Does not change or reclassify product images.
"""
import json
import re
from pathlib import Path
from ipaddress import ip_address
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]
def load(name):
    return json.loads((root / 'data' / name).read_text(encoding='utf-8'))
quick = load('arkan-quick-image-candidates.json')
trial = load('arkan-trial-photo-feed.json')
auto = load('arkan-auto-published-images.json')
legacy_total = 4218
html = (root / 'index.html').read_text(encoding='utf-8')
master = re.search(r'const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];', html)
if master is None:
    raise SystemExit('Arkan image data validation FAILED: missing catalog')
master_count = len(re.findall(r'\{\s*name:\s*"[^"]+"\s*,\s*cat:\s*"[^"]+"', master[1]))
if master_count < legacy_total:
    raise SystemExit('Arkan image data validation FAILED: incomplete catalog')
reserved_start = 230000
reserved_end = reserved_start + master_count - legacy_total
errors = []

def valid_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return False
    try:
        u = urlparse(value)
        host = (u.hostname or '').lower().rstrip('.')
        if u.scheme != 'https' or not host or u.username or u.password or u.port:
            return False
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
            return False
        try:
            ip_address(host)  # Literal IP/metadata/internal targets are not acceptable.
            return False
        except ValueError:
            return '.' in host
    except ValueError:
        return False

def check_id(raw_id, limit=legacy_total):
    identifier = str(raw_id)
    return identifier.isascii() and identifier.isdecimal() and 1 <= int(identifier) <= limit

def production_id(raw_id):
    if check_id(raw_id):
        return True
    identifier = str(raw_id)
    return identifier.isascii() and identifier.isdecimal() and reserved_start <= int(identifier) < reserved_end

def inspect(rows, name, limit=legacy_total):
    seen = {}
    for identifier, url, title in rows:
        if not check_id(identifier, limit):
            errors.append(f'{name}: invalid product ID {identifier}')
        if not valid_url(url):
            errors.append(f'{name}: invalid image URL for {identifier}')
        if not isinstance(title, str) or not title.strip():
            errors.append(f'{name}: empty candidate title for {identifier}')
        if url in seen and seen[url] != str(identifier):
            errors.append(f'{name}: same image URL assigned to {seen[url]} and {identifier}')
        seen[url] = str(identifier)

if quick.get('total') != legacy_total:
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
trial_total = trial.get('catalogTotal')
if trial_total not in (legacy_total, master_count):
    errors.append('trial: catalog total mismatch')
    trial_total = legacy_total
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
inspect(((row.get('id'), row.get('imageUrl'), row.get('title')) for row in entries), 'trial', trial_total)
if not isinstance(auto.get('byId', {}), dict):
    errors.append('auto: byId must be a dictionary')
else:
    seen_urls = {}
    for pid, row in auto.get('byId', {}).items():
        if (not production_id(pid) or not isinstance(row, dict) or
                row.get('status') not in ('auto_published_strict_unverified_pack', 'candidate_preview') or
                row.get('independentlyVerified') not in (None, False)):
            errors.append(f'auto: invalid publication record {pid}')
            continue
        url = row.get('url')
        if not valid_url(url):
            errors.append(f'auto: invalid image URL {pid}')
            continue
        if url in seen_urls:
            errors.append(f'auto: same image URL assigned to {seen_urls[url]} and {pid}')
        seen_urls[url] = pid

if errors:
    raise SystemExit('Arkan image data validation FAILED:\n' + '\n'.join(errors[:30]))
print(f'PASS: {len(rows)} unique quick photo candidates, {len(entries)} distinct trial photos, '
      f'{len(auto.get("byId",{}))} correctly flagged auto records; no cross-SKU duplicate image URLs')
