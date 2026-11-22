#!/usr/bin/env python3
"""Publish only OCR-confirmed, reusable non-medicine packaging photos.

Missing or ambiguous images are quarantined; existing admin seeds are never overwritten.
"""
import io, json, os, re, subprocess, tempfile, urllib.request, time
from pathlib import Path
from PIL import Image, ImageOps

root=Path(__file__).resolve().parents[1]
html_path=root/'index.html'
manifest=json.loads((root/'data/arkan-auto-published-images.json').read_text(encoding='utf-8'))
attempts_path=root/'data/arkan-visual-publish-state.json'
attempts=json.loads(attempts_path.read_text(encoding='utf-8')) if attempts_path.exists() else {}
now=time.time()
html=html_path.read_text(encoding='utf-8')
begin=html.index('const verifiedImageSeeds = {')
end=html.index('const imageSeedBatches',begin)
block=html[begin:end]
known=set(re.findall(r"(?m)^\s*'([0-9]+)': \{ src:",block))
master=re.search(r'const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];',html)
if not master: raise RuntimeError('master catalog missing')
items=re.findall(r'\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"',master.group(1))
dest=root/'assets/product-images'
dest.mkdir(parents=True,exist_ok=True)
budget=max(0,min(15,int(os.getenv('VISUAL_PUBLISH_BUDGET','5'))))
report={'scanned':0,'published':0,'existing_skipped':0,'review':[],'published_ids':[]}
lines=[]
def tokens(x):return re.findall(r'[a-z]{3,}',str(x or '').lower())
def numbers(x):return re.findall(r'(?<!\d)\d+(?:[.,/]\d+)?(?!\d)',str(x or ''))
def latin_brand(record):
    # A merchant image alone cannot prove which Arabic catalog item it belongs to.
    value=str(record.get('englishName') or '').strip()
    return tokens(value)[0] if tokens(value) else None
for pid,record in sorted(manifest.get('byId',{}).items(),key=lambda p:int(p[0])):
    if report['scanned']>=budget:break
    if pid in known:
        report['existing_skipped']+=1
        continue
    if not pid.isdigit() or not 1<=int(pid)<=len(items):
        report['review'].append({'id':pid,'reason':'needs_catalog_sync'})
        continue
    name,cat=items[int(pid)-1]
    if 'أدوية' in cat or not any(x in cat for x in ('ألبان','غذاء','مكمل','تجميل','عناية')):continue
    if record.get('source') not in ('world.openfoodfacts.org','world.openbeautyfacts.org'):continue
    if 'CC BY-SA 3.0' not in record.get('license',''):continue
    url=record.get('url','')
    if not re.match(r'^https://(?:images|static)\.open(?:food|beauty)facts\.org/',url):continue
    # Retry previously rejected candidates after seven days, not on every run.
    if now-float(attempts.get(pid,0))<7*86400:continue
    attempts[pid]=now
    report['scanned']+=1
    if str(record.get('catalogName','')) != name:
        report['review'].append({'id':pid,'reason':'catalog_identity_changed'})
        continue
    expected_brand=latin_brand(record)
    if not expected_brand:
        report['review'].append({'id':pid,'reason':'independent_english_trade_name_missing'})
        continue
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'ArkanPharm-PackCheck/1.0','Accept':'image/*'})
        with urllib.request.urlopen(req,timeout=12) as response:
            if not response.headers.get('Content-Type','').startswith('image/'):raise ValueError('not_image')
            data=response.read(5000001)
        if not 700<=len(data)<=5000000:raise ValueError('invalid_size')
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if min(im.size)<240 or im.width*im.height>18000000:raise ValueError('invalid_dimensions')
            picture=ImageOps.exif_transpose(im).convert('RGB')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'product.png'
            picture.save(path,'PNG')
            result=subprocess.run(['tesseract',str(path),'stdout','-l','eng','--psm','11'],
                                  capture_output=True,text=True,timeout=20)
        if result.returncode:raise ValueError('ocr_failed')
        title=record.get('title','')
        name_words=tokens(title)
        observed=set(tokens(result.stdout))
        strengths=numbers(title)
        if len(name_words)<2 or expected_brand not in observed or expected_brand not in name_words or len(observed.intersection(name_words))<2:
            raise ValueError('pack_name_not_confirmed')
        ocr_numbers=numbers(result.stdout)
        catalog_numbers=numbers(name)
        if not catalog_numbers or not all(n in ocr_numbers for n in catalog_numbers):
            raise ValueError('catalog_numbers_not_confirmed')
        if not strengths or not all(n in ocr_numbers for n in strengths):
            raise ValueError('pack_numbers_not_confirmed')
        out=dest/(pid+'.jpg')
        if out.exists():raise ValueError('local_photo_exists')
        picture.thumbnail((1000,1000))
        picture.save(out,'JPEG',quality=84,optimize=True)
        lines.append("  '"+pid+"': { src: 'assets/product-images/"+pid+".jpg', source: 'Open Facts OCR checked pack CC BY-SA 3.0' },\n")
        report['published_ids'].append(pid)
    except Exception as exc:
        report['review'].append({'id':pid,'reason':str(exc)[:110]})
if lines:
    # Insert into verifiedImageSeeds, not the later legacy-source map.
    marker=block.find('};',block.index('const verifiedImageSeeds = {'))
    if marker<0:raise RuntimeError('cannot update image seed map')
    block=block[:marker]+''.join(lines)+block[marker:]
    html=html[:begin]+block+html[end:]
    html,count=re.subn(r'arkan_verified_image_seed_v(\d+)',
        lambda m:'arkan_verified_image_seed_v'+str(int(m.group(1))+1),html,count=1)
    if count!=1:raise RuntimeError('seed version missing')
    html_path.write_text(html,encoding='utf-8')
report['published']=len(lines)
attempts_path.write_text(json.dumps(attempts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'data/arkan-visual-publish-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='review'},ensure_ascii=False))
