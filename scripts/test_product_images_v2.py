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
assert not m.public_https_url("https://127.0.0.1/a.jpg")
assert not m.public_https_url("http://localhost/x.png")
assert not m.public_https_url("file:///etc/passwd")
print("PASS: bilingual names, form, strength, variants and unsafe URLs")
