#!/usr/bin/env python3
"""
أداة صور الأصناف v2 - مطابقة صارمة + نشر آمن + سرعة.

الفكرة: مفيش صورة تتنشر على المنصة غير لو عدّت كل فلاتر الأمان (حالة auto).
اللي فيه أي شك يروح لفولدر review_images ويتراجع بنظرة سريعة من صفحة review.html
ومش بيتنشر. وكده نسبة الخطأ في المنشور تقرب من الصفر.

مراحل القرار لكل صنف:
  0) لو في عمود image_url (رابط مباشر من مصدر موثوق زي الهيئة/الشركة) -> بيتجرب الأول
  1) بحث (باركود ثم الاسم) مع تحكم ذكي في معدل الطلبات
  2) فلتر العنوان: الاسم التجاري لازم يطابق + التركيز (رقم+وحدة) + الشكل الدوائي
     + الكلمات المميزة (forte/plus/junior/extra...) لازم تتطابق تماماً
  3) فلتر الصورة: حجم، نسبة أبعاد، حدّة، مش فاضية
  4) إجماع: نفس الصورة (بصمة بصرية) من مصدرين مستقلين، أو دومين موثوق، أو باركود
  5) (اختياري --ocr) قراءة النص على العلبة للتأكد من الاسم
  6) ضغط WebP بحد أقصى للحجم + manifest.json بنسخة لكل صورة
  7) رفع على دفعات مع فحص الملفات قبل الرفع وإعادة محاولة

التثبيت:
    pip install ddgs requests pillow
    (اختياري للـ OCR:  pip install pytesseract  + تثبيت برنامج Tesseract)

التشغيل:
    python product_images_v2.py --csv products.csv --limit 30            # تجربة
    python product_images_v2.py --csv products.csv --workers 6 --push --repo ../product-images
    python product_images_v2.py --csv products.csv --image-url-col image_url   # لو عندك روابط موثوقة
    python product_images_v2.py --csv products.csv --approve approved.txt --push --repo ../product-images

دعم العربي (القائمة عربي):
  - تطبيع كامل: التشكيل والتطويل وأ/إ/آ، ى/ي، ة/ه، والأرقام الهندية، و"ال" التعريف.
  - مطابقة بالنطق: بانادول = Panadol، اوجمنتين = Augmentin، فولتارين = Voltaren.
  - التركيز والشكل وكلمات التمييز بالعربي (مجم، قرص، فورت، اكسترا، اطفال...) بتتفهم.
  - الأفضل: --dict egyptian-drugs.json (قاموس عربي->إنجليزي) أو --en-col لو عندك عمود إنجليزي،
    وساعتها البحث بالإنجليزي والعربي مع بعض ودقة المطابقة بتزيد كتير.
"""

import argparse
import csv
import hashlib
import html
import io
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote, urlparse
import ipaddress
import socket

import requests
from PIL import Image, ImageFilter, ImageStat
Image.MAX_IMAGE_PIXELS = 18_000_000

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
try:
    import pytesseract
except ImportError:
    pytesseract = None

# ================= إعدادات =================
OUT_DIR = "images"            # الصور المعتمدة (دي اللي بتتنشر)
REVIEW_DIR = "review_images"  # صور تحتاج مراجعة (مش بتتنشر)
REPORT = "results_v2.csv"

MIN_SIDE = 300
MAX_SIDE = 600                # صغيرة = أسرع على المنصة
MAX_KB = 45                   # أقصى حجم للصورة بعد الضغط
MAX_DOWNLOAD = 8 * 1024 * 1024
RESULTS_PER_QUERY = 10
TOP_DOWNLOAD = 6              # كام مرشح ننزّل ونقارن
MIN_SUPPORT = 2               # أقل عدد مصادر مستقلة بنفس الصورة
HASH_DIST = 6                 # أقصى فرق بين بصمتين لاعتبارهم نفس الصورة
SEARCH_INTERVAL = 0.7         # أقل فاصل بين طلبات البحث (بيتظبط تلقائياً)
PUSH_EVERY = 300

# دومينات موثوقة (عدّلها بمعرفتك - مثال فقط، مش متحقق منها):
TRUSTED_DOMAINS = []          # مثال: ["eda.mohp.gov.eg", "pfizer.com"]
# ===========================================

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ProductImageBot/2.0)"}

# ---------------- تطبيع العربي ----------------
AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ی": "ي",
                        "ة": "ه", "ؤ": "و", "ئ": "ي", "ک": "ك"})
AR_DIAC = re.compile(r"[\u064B-\u065F\u0670\u0640]")   # تشكيل + تطويل
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫۰۱۲۳۴۵۶۷۸۹", "0123456789.0123456789")


def norm(t):
    t = AR_DIAC.sub("", (t or "").translate(AR_DIGITS).lower())
    return t.translate(AR_MAP)


STOP = {norm(w) for w in ["the", "and", "for", "with", "box", "pack", "of", "من", "في",
                          "علبة", "شركة", "مصر"]}

# كلمات التمييز (forte/plus/...) بالإنجليزي والعربي - لازم تتطابق بالظبط
_VAR_EN = {"forte", "plus", "junior", "extra", "retard", "xr", "sr", "cr", "er", "mr",
           "cold", "flu", "kids", "baby", "max", "advance", "fast", "rapid", "duo",
           "mini", "pediatric", "adult", "children", "dt", "odt", "lite", "ultra",
           "night", "day", "active", "sensitive", "intense", "complex", "mega",
           "light", "men", "women", "sugar", "free"}
_VAR_AR = {"احمر": "red", "أحمر": "red", "اخضر": "green", "أخضر": "green",
           "ازرق": "blue", "أزرق": "blue", "اصفر": "yellow", "أصفر": "yellow",
           "ابيض": "white", "أبيض": "white", "اسود": "black", "أسود": "black",
           "وردي": "pink", "بمبي": "pink", "برتقالي": "orange",
           "red": "red", "green": "green", "blue": "blue", "yellow": "yellow",
           "white": "white", "black": "black", "pink": "pink", "orange": "orange",
           "فورت": "forte", "فورتي": "forte", "بلس": "plus", "بلاس": "plus",
           "جونيور": "junior", "اكسترا": "extra", "كيدز": "kids", "اطفال": "kids",
           "للاطفال": "kids", "ماكس": "max", "كولد": "cold", "فلو": "flu",
           "ريتارد": "retard", "دوو": "duo", "اولترا": "ultra", "نايت": "night",
           "لايت": "light", "ميني": "mini", "ادفانس": "advance", "فاست": "fast",
           "رابيد": "rapid", "اكتيف": "active", "سنسيتيف": "sensitive",
           "ميجا": "mega", "بيبي": "baby", "للكبار": "adult", "رجال": "men",
           "نساء": "women"}
CANON = {v: v for v in _VAR_EN}
CANON["fort"] = "forte"
CANON.update({norm(k): v for k, v in _VAR_AR.items()})


def variants_of(tokens):
    return {CANON[t] for t in tokens if t in CANON}


FORMS = {
    "capsule": ["capsule", "capsules", "cap", "caps", "كبسول", "كبسولة", "كبسولات"],
    "tablet": ["tablet", "tablets", "tab", "tabs", "قرص", "اقراص", "أقراص"],
    "injectable": ["ampoule", "ampoules", "ampule", "ampules", "amp", "amps", "vial",
                   "vials", "injection", "inj", "امبول", "أمبول", "امبولة", "أمبولة",
                   "امبولات", "أمبولات", "حقن", "حقنة", "فيال"],
    "syrup": ["syrup", "susp", "suspension", "شراب", "معلق"],
    "cream": ["cream", "كريم"],
    "gel": ["gel", "جل"],
    "ointment": ["ointment", "oint", "مرهم"],
    "drops": ["drops", "drop", "نقط", "قطرة", "قطره"],
    "spray": ["spray", "سبراي", "بخاخ"],
    "sachet": ["sachet", "sachets", "كيس", "اكياس", "أكياس"],
    "suppository": ["suppository", "suppositories", "supp", "لبوس", "تحاميل"],
    "lotion": ["lotion", "لوشن"],
    "shampoo": ["shampoo", "شامبو"],
    "solution": ["solution", "محلول"],
    "powder": ["powder", "بودرة", "بودره"],
}
FORM_WORD = {norm(w): c for c, ws in FORMS.items() for w in ws}
_UNITS = ["mg", "mcg", "ug", "gm", "g", "ml", "iu", "مجم", "ملجم", "جم", "مل"]
UNIT_WORDS = {norm(u) for u in _UNITS}
UNIT_CANON = {"gm": "g", "ug": "mcg", "مجم": "mg", "ملجم": "mg", "جم": "g", "مل": "ml"}
_CW = "|".join(re.escape(w) for w in sorted(FORM_WORD, key=len, reverse=True))
COUNT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:x\s*)?(?:" + _CW + r")(?=\W|$)")
_UN = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(" + _UN + r"|%)?(?![a-z\u0600-\u06FF])")


# ---------------- مطابقة عربي <-> إنجليزي (بالنطق) ----------------
_AR_SK = {"ب": "b", "ت": "t", "ث": "s", "ج": "g", "ح": "h", "خ": "k", "د": "d", "ذ": "s",
          "ر": "r", "ز": "s", "س": "s", "ش": "s", "ص": "s", "ض": "d", "ط": "t", "ظ": "s",
          "غ": "g", "ف": "f", "ق": "k", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h"}


def _dedupe(s):
    out = []
    for ch in s:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def is_ar(w):
    return bool(re.search(r"[\u0600-\u06FF]", w))


def sk_ar(w):
    """هيكل الحروف الساكنة للكلمة العربية (بدون حروف المد)."""
    return _dedupe("".join(_AR_SK.get(c, "") for c in norm(w)))


def sk_lat(w):
    """نفس الهيكل للكلمة الإنجليزية: Panadol -> bndl, بانادول -> bndl."""
    w = w.lower()
    for x, y in (("ph", "f"), ("ck", "k"), ("ch", "k"), ("sh", "s"), ("th", "t"),
                 ("kh", "k"), ("gh", "g")):
        w = w.replace(x, y)
    w = re.sub(r"c(?=[eiy])", "s", w).replace("c", "k")
    m = {"q": "k", "x": "ks", "v": "f", "p": "b", "j": "g", "z": "s"}
    return _dedupe("".join(c for c in "".join(m.get(c, c) for c in w) if c in "bdfghklmnrst"))


def tok_match(a, b):
    if a == b:
        return True
    aa, ba = is_ar(a), is_ar(b)
    if aa != ba:   # عربي مقابل إنجليزي
        x, y = (sk_ar(a), sk_lat(b)) if aa else (sk_ar(b), sk_lat(a))
        return len(x) >= 3 and len(y) >= 3 and (x == y or SequenceMatcher(None, x, y).ratio() >= 0.86)
    n = 5 if aa else 6
    return len(a) >= n and len(b) >= n and SequenceMatcher(None, a, b).ratio() >= 0.88


def ordered_tokens(text):
    out = []
    for w in re.findall(r"[^\W\d_]+", norm(text)):
        if w.startswith("ال") and len(w) > 4:
            w = w[2:]
        if len(w) > 1 and w not in FORM_WORD and w not in UNIT_WORDS and w not in STOP:
            out.append(w)
    return out


def forms_of(text):
    return {FORM_WORD[w] for w in re.findall(r"\w+", norm(text)) if w in FORM_WORD}


def numbers_of(text):
    t = COUNT_RE.sub(" ", norm(text))
    d = {}
    for n, u in NUM_RE.findall(t):
        key = "%g" % float(n.replace(",", "."))
        d.setdefault(key, set())
        if u:
            d[key].add(UNIT_CANON.get(u, u))
    return d


# ---------------- قاموس عربي -> إنجليزي ----------------
AR_KEYS = ["arabic", "name_ar", "nameAr", "ar", "arabic_name", "arabicName",
           "trade_name_ar", "tradeNameAr"]
EN_KEYS = ["english", "name_en", "nameEn", "en", "english_name", "englishName",
           "trade_name", "tradeName", "trade_name_en"]


def load_dict(path, ar_key="", en_key=""):
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [])
    else:
        with open(p, encoding="utf-8-sig", newline="") as f:
            data = list(csv.DictReader(f))
    if not data or not isinstance(data[0], dict):
        sys.exit("ملف القاموس فاضي أو شكله غير مدعوم")
    keys = list(data[0].keys())
    ak = ar_key or next((k for k in AR_KEYS if k in keys), None)
    ek = en_key or next((k for k in EN_KEYS if k in keys), None)
    if not ak or not ek:
        sys.exit(f"مفاتيح القاموس: {keys}\nحدد --dict-ar-key و --dict-en-key")
    idx = {}
    for d in data:
        ar, en = str(d.get(ak) or "").strip(), str(d.get(ek) or "").strip()
        toks = ordered_tokens(ar)
        if not toks or not en:
            continue
        k = sk_ar(toks[0])
        if len(k) >= 2:
            idx.setdefault(k, []).append((toks, en))
    print(f"القاموس: {sum(len(v) for v in idx.values())} اسم")
    return idx


def dict_lookup(idx, name):
    """أطول اسم في القاموس كل كلماته موجودة في اسم الصنف وكلمات التمييز متطابقة."""
    toks = ordered_tokens(name)
    if not toks or not idx:
        return ""
    rv, best = variants_of(toks), None
    for t in toks:
        for etoks, en in idx.get(sk_ar(t), []):
            if (all(any(tok_match(e, r) for r in toks) for e in etoks)
                    and variants_of(etoks) == rv):
                if best is None or len(etoks) > len(best[0]):
                    best = (etoks, en)
    return best[1] if best else ""


def spec_en(name):
    """التركيز والشكل الدوائي بالإنجليزي من الاسم العربي: '500mg tablet'."""
    parts = [n + (sorted(u)[0] if u else "") for n, u in numbers_of(name).items()]
    return " ".join(parts + sorted(forms_of(name)))


def resolve_en(row, a, name):
    en = row.get(a.en_col, "").strip() if a.en_col else ""
    if en:
        return en
    idx = getattr(a, "dict_idx", None)
    if idx:
        base = dict_lookup(idx, name)
        if base:
            return base if re.search(r"\d", base) else f"{base} {spec_en(name)}".strip()
    return ""


def compare_numbers(pn, tn):
    if not pn:
        return "confirmed"
    if not tn:
        return "unconfirmed"
    for n, u in pn.items():
        if n not in tn:
            return "reject"
        if u and tn[n] and not (u & tn[n]):
            return "reject"
    return "confirmed" if set(tn) <= set(pn) else "unconfirmed"


def evaluate(name, title, url_text="", barcode=""):
    """(درجة, حكم, باركود) - الحكم: reject / ok / review"""
    blob = f"{title} {url_text}"
    barcode_match = bool(barcode and len(barcode) >= 8 and re.search(r"(?<!\d)" + re.escape(barcode) + r"(?!\d)", blob))
    a = ordered_tokens(name)
    b = ordered_tokens(blob)
    if not a:
        return 0.0, "reject", False
    if not any(tok_match(a[0], w) for w in b):      # الاسم التجاري الأساسي لازم يظهر
        return 0.0, "reject", False
    s = sum(1 for t in a if any(tok_match(t, w) for w in b)) / len(a)
    if s < 0.6:
        return s, "reject", False
    if variants_of(a) != variants_of(b):
        return s, "reject", False                    # forte/plus/junior... لازم تتطابق
    pf, tf = forms_of(name), forms_of(blob)
    if pf and tf and not (pf & tf):
        return s, "reject", False
    cmp = compare_numbers(numbers_of(name), numbers_of(title))
    if cmp == "reject":
        return s, "reject", False
    # Distinguish pack quantity (10 vs 20 tablets) from strength (500 mg).
    pack_expected = sorted(float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", " ".join(COUNT_RE.findall(norm(name)))))
    pack_observed = sorted(float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", " ".join(COUNT_RE.findall(norm(title)))))
    if pack_expected and pack_observed and pack_expected != pack_observed:
        return s, "reject", False
    if pack_expected != pack_observed:
        return s, "review", False
    confirmed = cmp == "confirmed" and (not pf or bool(tf))
    return s, ("ok" if s >= 0.85 and confirmed else "review"), barcode_match


RANK = {"reject": 0, "review": 1, "ok": 2}


def evaluate_any(names, title, url_t="", barcode=""):
    """يقيّم العنوان مقابل كل اسم (عربي/إنجليزي) ويرجّع الأفضل."""
    best = (0.0, "reject", False)
    for n in names:
        r = evaluate(n, title, url_t, barcode)
        if (RANK[r[1]], r[0]) > (RANK[best[1]], best[0]):
            best = r
    return best


def url_text(page):
    try:
        p = urlparse(page or "")
        return re.sub(r"[^A-Za-z0-9\u0600-\u06FF]+", " ", unquote(p.path))
    except Exception:
        return ""


def domain_of(url):
    d = urlparse(url or "").netloc.lower()
    return d[4:] if d.startswith("www.") else d


# ---------------- بحث بمعدل ذكي ----------------
class RateLimiter:
    def __init__(self, base):
        self.base = self.cur = base
        self.next = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            t = max(self.next, now)
            self.next = t + self.cur
        if t > now:
            time.sleep(t - now)

    def fail(self):
        with self.lock:
            self.cur = min(self.cur * 1.6, 6.0)

    def ok(self):
        with self.lock:
            self.cur = max(self.base, self.cur * 0.97)


def search(q, rl):
    for attempt in range(3):
        rl.wait()
        try:
            with DDGS() as d:
                res = list(d.images(q, max_results=RESULTS_PER_QUERY))
            rl.ok()
            return res
        except Exception:
            rl.fail()
            time.sleep(2 * (attempt + 1) + random.random())
    return []


# ---------------- الصور ----------------
def public_https_url(url):
    """Never download local/private network resources or follow redirects."""
    try:
        u = urlparse(url)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443):
            return False
        host = u.hostname.lower().strip(".")
        if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
            return False
        results = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(results) and all(ipaddress.ip_address(x[4][0]).is_global for x in results)
    except Exception:
        return False


def download(url):
    if not public_https_url(url):
        return None
    try:
        with requests.get(url, headers=HEADERS, timeout=12, stream=True, allow_redirects=False) as r:
            if r.status_code in (301, 302, 303, 307, 308):
                return None
            if not r.headers.get("Content-Type", "").lower().startswith("image/"):
                return None
            r.raise_for_status()
            data = b""
            for chunk in r.iter_content(65536):
                data += chunk
                if len(data) > MAX_DOWNLOAD:
                    return None
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:
        return None


def quality_ok(img):
    w, h = img.size
    if min(w, h) < MIN_SIDE or not (0.5 <= w / h <= 2.0):
        return False
    g = img.convert("L")
    g.thumbnail((256, 256))
    if ImageStat.Stat(g).stddev[0] < 12:                       # صورة شبه فاضية
        return False
    if ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0] < 30:   # مش واضحة
        return False
    return True


def dhash(img, size=8):
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return bits


def to_rgb(img):
    if img.mode == "RGBA" or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


def encode_webp(img):
    img = to_rgb(img)
    data = b""
    for side in (MAX_SIDE, 500, 400):
        im = img.copy()
        im.thumbnail((side, side))
        for q in (80, 70, 60, 50):
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=q, method=6)
            data = buf.getvalue()
            if len(data) <= MAX_KB * 1024:
                return data
    if len(data) > MAX_KB * 1024:
        raise ValueError("webp_exceeds_max_kb")
    return data


def ocr_check(img, names):
    """True = الاسم ظاهر على العلبة، False = في نص بس الاسم مش موجود، None = مش متأكد."""
    if pytesseract is None:
        return None
    anchors = [t[0] for t in (ordered_tokens(n) for n in names) if t]
    if not anchors:
        return None
    text = None
    for lang in ("ara+eng", "eng"):
        try:
            text = pytesseract.image_to_string(to_rgb(img), lang=lang)
            break
        except Exception:
            continue
    if text is None:
        return None
    words = [w for w in re.findall(r"[^\W\d_]+", norm(text)) if len(w) >= 3]
    if len(words) < 2:
        return None
    if not any(tok_match(an, w) for an in anchors for w in words):
        return False
    # OCR brand-only hits must not approve a different SKU/color/strength.
    catalog_name = names[-1]
    expected_variants = variants_of(ordered_tokens(catalog_name))
    if expected_variants and not expected_variants.issubset(variants_of(ordered_tokens(text))):
        return None  # Uncertain OCR: never use OCR alone to auto-approve.
    expected_numbers = numbers_of(catalog_name)
    seen_numbers = numbers_of(text)
    if expected_numbers and any(n not in seen_numbers for n in expected_numbers):
        return None
    return True


# ---------------- معالجة صنف واحد ----------------
def safe_name(code):
    return re.sub(r"[^\w.-]", "_", code)


def mk(code, name, status, reason="", s=0.0, support=0, img=None, src="", page=""):
    data = encode_webp(img) if img is not None else None
    return dict(code=code, name=name, status=status, reason=reason, score=round(s, 2),
                support=support, ver=hashlib.md5(data).hexdigest()[:8] if data else "",
                image="", source_url=src, source_page=page, data=data)


def _process_row(row, a, rl, use_ocr):
    code = row[a.code_col].strip()
    name = row.get(a.name_col, "").strip()
    barcode = row.get(a.barcode_col, "").strip() if a.barcode_col else ""
    brand = row.get(a.brand_col, "").strip() if a.brand_col else ""
    en = resolve_en(row, a, name)
    names = [n for n in (en, name) if n]

    # (0) رابط مباشر من مصدر موثوق
    direct = row.get(a.image_url_col, "").strip() if a.image_url_col else ""
    if direct:
        img = download(direct)
        if img is not None and quality_ok(img):
            ocr = ocr_check(img, names) if use_ocr else None
            if ocr is False:
                return mk(code, name, "review", "trusted_url_ocr_mismatch", 1, 1, img, direct)
            return mk(code, name, "review", "direct_url_requires_independent_verification", 1, 1, img, direct)

    queries = []
    for q in [barcode, en, f"{en} box" if en else "", f"{name} {brand}".strip(), f"{name} علبة"]:
        if q and q not in queries:
            queries.append(q)
    queries = queries[:4]
    for d in TRUSTED_DOMAINS[:2]:
        queries.append(f"{en or name} site:{d}")

    cands, seen = [], set()
    for q in queries:
        for res in search(q, rl):
            u = res.get("image")
            if not u or u in seen:
                continue
            seen.add(u)
            page = res.get("url", "") or ""
            s, verdict, bar = evaluate_any(names, res.get("title", ""), url_text(page), barcode)
            # Never let a short English brand match override Arabic SKU variants,
            # strength, pack count, or pharmaceutical form.
            title = res.get("title", "")
            title_tokens = ordered_tokens(title + " " + url_text(page))
            required_variants = variants_of(ordered_tokens(name))
            if required_variants and not required_variants.issubset(variants_of(title_tokens)):
                continue
            expected_strength = numbers_of(name)
            if expected_strength and compare_numbers(expected_strength, numbers_of(title)) != "confirmed":
                continue
            expected_form = forms_of(name)
            if expected_form and not (expected_form & forms_of(title)):
                continue
            if verdict == "reject":
                continue
            try:
                w, h = int(res.get("width") or 0), int(res.get("height") or 0)
            except (TypeError, ValueError):
                w, h = 0, 0
            if w and h and min(w, h) < MIN_SIDE:
                continue
            dom = domain_of(page) or domain_of(u)
            cands.append(dict(rank=2 if verdict == "ok" else 1, s=s, image=u, verdict=verdict,
                              bar=bar, page=page, domain=dom,
                              trusted=any(dom == t or dom.endswith("." + t) for t in TRUSTED_DOMAINS)))
        if sum(c["verdict"] == "ok" for c in cands) >= 4:
            break
    if not cands:
        return mk(code, name, "not_found", "no_title_match")

    cands.sort(key=lambda c: (c["rank"], c["bar"], c["trusted"], c["s"]), reverse=True)
    members = []
    for c in cands[:TOP_DOWNLOAD]:
        img = download(c["image"])
        if img is not None and quality_ok(img):
            c["img"], c["hash"] = img, dhash(img)
            members.append(c)
    if not members:
        return mk(code, name, "not_found", "no_good_image")

    clusters = []
    for m in members:
        for cl in clusters:
            if bin(cl[0]["hash"] ^ m["hash"]).count("1") <= HASH_DIST:
                cl.append(m)
                break
        else:
            clusters.append([m])

    def cscore(cl):
        return (any(m["verdict"] == "ok" for m in cl), len({m["domain"] for m in cl}),
                any(m["trusted"] for m in cl), max(m["s"] for m in cl))

    best = max(clusters, key=cscore)
    rep = max(best, key=lambda m: (m["verdict"] == "ok", m["img"].size[0] * m["img"].size[1]))
    ok, support = cscore(best)[0], cscore(best)[1]
    others = [c for c in clusters if c is not best and cscore(c)[0]]
    conflict = bool(others) and max(cscore(c)[1] for c in others) >= support
    ocr = ocr_check(rep["img"], names) if use_ocr else None

    if not ok:
        status, reason = "review", "title_unconfirmed"
    elif ocr is False:
        status, reason = "review", "ocr_mismatch"
    elif conflict:
        status, reason = "review", "conflicting_images"
    elif any(m["bar"] for m in best):
        status, reason = "auto", "barcode"
    elif any(m["trusted"] for m in best):
        status, reason = "auto", "trusted_domain"
    elif support >= MIN_SUPPORT:
        status, reason = "auto", f"multi_source_{support}"
    elif ocr is True:
        status, reason = "auto", "ocr"
    else:
        status, reason = "review", "single_source"
    return mk(code, name, status, reason, rep["s"], support, rep["img"], rep["image"], rep["page"])


def process_row(row, a, rl, use_ocr):
    res = _process_row(row, a, rl, use_ocr)
    res["name_en"] = resolve_en(row, a, row.get(a.name_col, "").strip())
    return res


# ---------------- ملفات وتقارير ----------------
FIELDS = ["code", "name", "name_en", "status", "reason", "score", "support", "ver", "image",
          "source_url", "source_page"]


def atomic_write(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def load_report(path):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def save_report(path, results):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    w.writerows(results.values())
    atomic_write(path, buf.getvalue().encode("utf-8-sig"))


def write_manifest(out, results):
    m = {}
    for r in results.values():
        if r["status"] == "auto":
            fn = f"{safe_name(r['code'])}.webp"
            if (out / fn).exists():
                m[r["code"]] = {"f": fn, "v": r.get("ver", "")}
    atomic_write(out / "manifest.json",
                 json.dumps(m, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return m


REVIEW_TMPL = """<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>مراجعة الصور</title>
<style>body{font-family:system-ui,Tahoma,sans-serif;margin:0;background:#f5f5f5}
header{position:sticky;top:0;background:#fff;padding:10px 16px;box-shadow:0 1px 4px #0003;display:flex;gap:12px;align-items:center;z-index:5}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;padding:12px}
.c{background:#fff;border:3px solid transparent;border-radius:8px;padding:8px;cursor:pointer;font-size:12px}
.c.on{border-color:#16a34a;background:#f0fdf4}.c img{width:100%;height:150px;object-fit:contain}
.c small{display:block;color:#666}</style>
<header><b>اضغط على الصورة الصح لاعتمادها</b><span id=n>0</span><button onclick="ex()">تصدير approved.txt</button></header>
<div class=g>%CARDS%</div>
<script>
document.querySelectorAll('.c').forEach(c=>c.onclick=e=>{if(e.target.tagName=='A')return;c.classList.toggle('on');n.textContent=document.querySelectorAll('.c.on').length});
function ex(){const t=[...document.querySelectorAll('.c.on')].map(c=>c.dataset.code).join('\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:'text/plain'}));a.download='approved.txt';a.click()}
</script></html>"""


def write_review_page(repo, results):
    cards = []
    for r in results.values():
        if r["status"] != "review":
            continue
        e = html.escape
        cards.append(
            f'<div class="c" data-code="{e(r["code"])}"><img loading="lazy" '
            f'src="{REVIEW_DIR}/{safe_name(r["code"])}.webp"><b>{e(r["name"])}</b>'
            f'<small>{e(r.get("name_en") or "")} · {e(r["code"])} · {e(r["reason"])}</small>'
            f'<a href="{e(r["source_page"] or r["source_url"])}" target="_blank">المصدر</a></div>')
    atomic_write(repo / "review.html", REVIEW_TMPL.replace("%CARDS%", "".join(cards)).encode("utf-8"))


def verify_files(paths):
    bad = []
    for p in paths:
        try:
            with Image.open(p) as im:
                im.verify()
            if p.stat().st_size > MAX_KB * 1024 * 2:
                bad.append(p)
        except Exception:
            bad.append(p)
    return bad


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def git_push(repo, msg):
    git(repo, "add", OUT_DIR, REPORT, str(Path(OUT_DIR) / "manifest.json"))
    r = git(repo, "commit", "-m", msg)
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        print("   تحذير git:", (r.stderr or r.stdout).strip()[:200])
        return False
    for i in range(3):
        git(repo, "pull", "--rebase", "--autostash")
        p = git(repo, "push")
        if p.returncode == 0:
            return True
        time.sleep(3 * (i + 1))
    print("   تحذير: فشل الرفع بعد 3 محاولات - هيتعاد في الدفعة الجاية")
    return False


# ---------------- التشغيل ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ocr", action="store_true", help="تأكيد الاسم بقراءة نص العلبة")
    ap.add_argument("--retry", action="store_true", help="أعد محاولة not_found")
    ap.add_argument("--approve", help="ملف أكواد اعتمدتها من review.html")
    ap.add_argument("--code-col", default="code")
    ap.add_argument("--name-col", default="name")
    ap.add_argument("--barcode-col", default="barcode")
    ap.add_argument("--brand-col", default="")
    ap.add_argument("--image-url-col", default="")
    ap.add_argument("--en-col", default="", help="عمود الاسم الإنجليزي لو موجود في الملف")
    ap.add_argument("--dict", default="", help="قاموس عربي->إنجليزي (json/csv) زي egyptian-drugs.json")
    ap.add_argument("--dict-ar-key", default="")
    ap.add_argument("--dict-en-key", default="")
    a = ap.parse_args()
    a.dict_idx = load_dict(a.dict, a.dict_ar_key, a.dict_en_key) if a.dict else None

    repo = Path(a.repo)
    out, rev = repo / OUT_DIR, repo / REVIEW_DIR
    out.mkdir(parents=True, exist_ok=True)
    rev.mkdir(parents=True, exist_ok=True)
    report = repo / REPORT
    results = load_report(report)
    pending = []   # (code, path) ملفات جديدة لسه مترفعتش

    def checkpoint(push_msg=None):
        if push_msg and pending:
            bad = verify_files([p for _, p in pending])
            for code, p in list(pending):
                if p in bad:
                    p.unlink(missing_ok=True)
                    results[code]["status"], results[code]["reason"] = "not_found", "corrupt_file"
        save_report(report, results)
        write_manifest(out, results)
        write_review_page(repo, results)
        if push_msg and a.push:
            if git_push(str(repo), push_msg):
                pending.clear()

    if a.approve:
        codes = [c.strip() for c in Path(a.approve).read_text(encoding="utf-8").splitlines() if c.strip()]
        n = 0
        for c in codes:
            r = results.get(c)
            src = rev / f"{safe_name(c)}.webp"
            if r and r["status"] == "review" and src.exists():
                dst = out / src.name
                os.replace(src, dst)
                r["status"], r["reason"] = "auto", "manual_approved"
                r["image"] = f"{OUT_DIR}/{src.name}"
                pending.append((c, dst))
                n += 1
        checkpoint("Approve reviewed product images")
        print(f"تم اعتماد {n} صورة")
        return

    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[: a.limit]
    if rows and (a.code_col not in rows[0] or a.name_col not in rows[0]):
        sys.exit(f"أعمدة الملف: {list(rows[0].keys())}\nاستخدم --code-col و --name-col")

    def needs(row):
        code = row[a.code_col].strip()
        r = results.get(code)
        if not r:
            return True
        if r["status"] == "auto":
            return not (out / f"{safe_name(code)}.webp").exists()
        if r["status"] == "review":
            return not (rev / f"{safe_name(code)}.webp").exists()
        return a.retry or r["status"] == "error"

    todo = [r for r in rows if needs(r)]
    print(f"المطلوب معالجته: {len(todo)} من {len(rows)}")
    if a.en_col or a.dict_idx:
        mapped = sum(bool(resolve_en(r, a, r.get(a.name_col, ""))) for r in todo)
        print(f"اتلاقى اسم إنجليزي لـ {mapped} من {len(todo)} (الباقي هيتبحث بالعربي بس)")
    rl = RateLimiter(SEARCH_INTERVAL)
    stats, since_push, done = Counter(), 0, 0
    ex = ThreadPoolExecutor(max_workers=max(1, a.workers))
    futs = {ex.submit(process_row, r, a, rl, a.ocr): r for r in todo}
    try:
        for fut in as_completed(futs):
            row = futs[fut]
            code = row[a.code_col].strip()
            done += 1
            try:
                res = fut.result()
            except Exception as e:
                print(f"DIAGNOSTIC: {code} {type(e).__name__}: {str(e)[:160]}", file=sys.stderr)
                res = mk(code, row.get(a.name_col, ""), "error", e.__class__.__name__)
            data = res.pop("data")
            if data and res["status"] in ("auto", "review"):
                folder = out if res["status"] == "auto" else rev
                other = rev if res["status"] == "auto" else out
                dst = folder / f"{safe_name(code)}.webp"
                atomic_write(dst, data)
                (other / dst.name).unlink(missing_ok=True)
                res["image"] = f"{folder.name}/{dst.name}"
                if res["status"] == "auto":
                    pending.append((code, dst))
                    since_push += 1
            results[code] = res
            stats[res["status"]] += 1
            print(f"[{done}/{len(todo)}] {code} {res['status']:9} {res['reason']}")
            if done % 25 == 0:
                checkpoint()
            if a.push and since_push >= PUSH_EVERY:
                checkpoint(f"Add product images ({len(pending)})")
                since_push = 0
    except KeyboardInterrupt:
        print("\nتم الإيقاف - بحفظ التقدم...")
        ex.shutdown(wait=False, cancel_futures=True)
    finally:
        checkpoint("Add product images (final)" if a.push else None)

    print("\nالنتيجة:", dict(stats))
    print("auto = صورة اجتازت مطابقة البحث وحُفظت محليًا | review = تحتاج مراجعة | not_found = لم تتوفر صورة مؤكدة")
    print("تقرير النشر هو المرجع لعدد الصور التي وصلت إلى المنصة.")


if __name__ == "__main__":
    main()