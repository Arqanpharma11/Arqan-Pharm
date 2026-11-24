"""Offline regression tests for Arabic and English image-name matching."""
import importlib.util
import sys
from pathlib import Path
module_path=Path(__file__).with_name("product_images_v2.py")
spec=importlib.util.spec_from_file_location("piv2",module_path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def check(name,title,want):
    result=m.evaluate(name,title)[1]
    assert result==want,(name,title,result,want)
check("بانادول 500مجم اقراص","Panadol 500 mg tablets","ok")
check("اوجمنتين 1جم اقراص","Augmentin 1g tablets","ok")
check("فولتارين 50مجم اقراص","Voltaren 50mg tablets","ok")
check("بانادول اكسترا 500مجم اقراص","Panadol 500mg tablets","reject")
check("فولتارين 50مجم اقراص","Voltaren 75mg tablets","reject")
check("فولتارين 50مجم اقراص","Voltaren 50mg cream","reject")
check("اوجمنتين 1جم اقراص","Augmentin 1g tablets XR","reject")
check("بانادول 500مجم 20قرص","Panadol 500mg 10 tablets","reject")
check("بانادول 500مجم 20قرص","Panadol 500mg tablets","review")
assert m.norm("إِيبـانْتِين ٥٠")=="ايبانتين 50"
assert m.variants_of(m.ordered_tokens("بى فريش احمر")) == {"red"}
assert m.variants_of(m.ordered_tokens("بى فريش اخضر")) == {"green"}
assert m.variants_of(m.ordered_tokens("بيبيلاك 1 لبن")) == set()
assert m.compare_numbers(m.numbers_of("فولتارين 50مجم"),m.numbers_of("Voltaren 75mg")) == "reject"
assert not m.public_https_url("https://127.0.0.1/a.jpg")
assert not m.public_https_url("http://localhost/x.png")
assert not m.public_https_url("file:///etc/passwd")
print("PASS: bilingual names, form, strength, variants and unsafe URLs")

# The existing storefront index skips web search only for an exact product
# and independently readable packaging. Unsafe routes and mismatches never download.
from unittest.mock import patch

name = "بانادول 500مجم 20قرص"
names = ["Panadol 500mg 20 tablets", name]
candidate = {
    "title": "Panadol 500mg 20 tablets",
    "productPage": "https://www.lotusonline.com/products/panadol",
    "imageUrl": "https://cdn.shopify.com/s/files/panadol.webp",
}
product = {"name": name, "candidates": [candidate]}
with patch.object(m, "download", return_value=object()) as download, \
     patch.object(m, "quality_ok", return_value=True), \
     patch.object(m, "ocr_check", return_value=True) as ocr:
    assert m.indexed_pack(product, name, names, "") is not None
    assert ocr.call_args.kwargs == {"strict": True}
    for overrides in (
        {"title": "Panadol 500mg 10 tablets"},
        {"title": "Panadol 250mg 20 tablets"},
        {"imageUrl": "https://unrelated.example/products/panadol.webp"},
        {"productPage": "https://www.lotusonline.com/admin/panadol"},
    ):
        assert m.indexed_pack({"name": name, "candidates": [dict(candidate, **overrides)]}, name, names, "") is None
    assert download.call_count == 1
    ocr.return_value = None
    assert m.indexed_pack(product, name, names, "") is None

print("PASS: public catalog index uses OCR and retains pack quantity, strength and URL checks")
