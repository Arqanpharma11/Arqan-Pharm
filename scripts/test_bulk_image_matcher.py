#!/usr/bin/env python3
"""Offline regression checks: never confuse strengths, stages, or dosage forms."""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[0]))
from bulk_pharmacy_image_discovery import match_score, image_link

def check(ar, en, title, expected):
    item = {"name": ar, "englishName": en}
    actual = match_score(item, {"title": title})
    if (actual is not None) != expected:
        raise AssertionError((item, title, actual, expected))

check("ابروفال300مجم اقراص", "Aprovel", "Aprovel 300mg 14 tablets", True)
check("ابروفال300مجم اقراص", "Aprovel", "Aprovel 150mg 14 tablets", False)
check("ابروفال300مجم اقراص", "Aprovel", "Aprovel 300mg syrup", False)
check("ابروفال300مجم اقراص", "Aprovel", "Aprovelx 300mg tablets", False)
check("ابتاميل2 لبن", "Aptamil", "Aptamil Advance 2 Milk Formula 400g", True)
check("ابتاميل2 لبن", "Aptamil", "Aptamil Advance 3 Milk Formula 400g", False)
check("اتورستات40مجم اقراص", "Atorstat", "Atorstat 40mg tablets", True)
check("اتورستات40مجم اقراص", "Atorstat", "Atorstat 80mg tablets", False)
assert image_link({"images":[{"src":"https://example.org/real-pack.jpg"}]}) == "https://example.org/real-pack.jpg"
assert image_link({"images":[{"src":"http://example.org/not-https.jpg"}]}) == ""
print("PASS: trade-brand, strength, stage and dosage-form rejection tests")
