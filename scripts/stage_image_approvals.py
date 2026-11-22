#!/usr/bin/env python3
"""Prepare safe batch approval queues from all Arqan pharmacy photo candidates.

Metadata checks are useful for rejecting mismatches; only visually inspected
actual package photos may be *approved*. This script never changes the PWA,
never writes to verified_image_replacements.json, and never approves a photo.
"""
import collections
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/arkan-image-candidate-review.json"
INVENTORY = ROOT / "data/arkan-all-4218-image-manifest.json"
OUTPUT = ROOT / "data/arkan-image-approval-worklist.json"
FORM_CHECKS = (
    ("لبوس", r"\b(?:supp|suppositor\w*)\b"),
    ("اقماع", r"\b(?:supp|suppositor\w*)\b"),
    ("اقراص", r"\b(?:tab|tabs|tablets?)\b"),
    ("قرص", r"\b(?:tab|tabs|tablets?)\b"),
    ("كبسول", r"\b(?:cap|caps|capsules?)\b"),
    ("امبول", r"\b(?:amp|amps|ampoule|ampoules|injection)\b"),
    ("فيال", r"\b(?:vial|vials|injection)\b"),
    ("لبن", r"\b(?:milk|formula|powder)\b"),
    ("شراب", r"\b(?:syrup|suspension)\b"),
    ("قطرة", r"\b(?:drops?|gtt)\b"),
    ("قطره", r"\b(?:drops?|gtt)\b"),
    ("كريم", r"\b(?:cream)\b"),
    ("مرهم", r"\b(?:ointment)\b"),
    ("جل", r"\b(?:gel)\b"),
    ("غسول", r"\b(?:cleanser|wash)\b"),
    ("اكياس", r"\b(?:sachet|sachets)\b"),
)
FORM_CHECKS = sorted(FORM_CHECKS, key=lambda x: len(x[0]), reverse=True)
VARIANT_TERMS = ("extra", "plus", "forte", "xr", "sr", "retard", "inf", "junior", "co", "max")
VARIANT_AR = {"extra": "اكسترا", "plus": "بلس", "forte": "فورت", "xr": "اكس ار",
              "sr": "اس ار", "retard": "ريتارد", "inf": "اطفال", "junior": "جونيور",
              "co": "كو", "max": "ماكس"}
NUMBER_RE = re.compile(r"(?<!\d)\d+(?:[.,/]\d+)*(?!\d)")
def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    for src, dst in (("أ","ا"),("إ","ا"),("آ","ا"),("ى","ي"),("ة","ه")):
        s = s.replace(src, dst)
    return s
def number_tokens(text):
    return [m.group().replace(",", ".") for m in NUMBER_RE.finditer(norm(text))]
def check(item, candidate, reference):
    english = norm(item.get("englishName")).strip()
    title = norm(candidate.get("title")).strip()
    if not english:
        return "english_trade_name_missing"
    if not re.match(r"^[a-z][a-z -]{2,}$", english):
        return "english_trade_name_ambiguous"
    if not title.startswith(english + " "):
        return "commercial_brand_mismatch"
    name = norm(item["name"])
    required = number_tokens(name)
    found = number_tokens(title)
    if not required:
        return "strength_or_stage_not_present_in_catalog"
    if not all(v in found for v in required):
        return "strength_stage_or_pack_mismatch"
    # Check the first named dose; this prevents 5mg being paired with 0.5mg.
    expected_dose = next((v for v in required if v not in ("30","20","14","10","7","5","3","2","1")), required[0])
    if expected_dose not in found:
        return "primary_strength_mismatch"
    for form, pattern in FORM_CHECKS:
        if norm(form) in name and not re.search(pattern, title):
            return "dosage_form_mismatch"
    # More conservative with an original pharmacy listing that specifies form.
    source_name = norm(reference.get("sourceName", ""))
    original_form = next((p for _, p in FORM_CHECKS
                          if re.search(p, source_name)), None)
    if original_form and not re.search(original_form, title):
        return "previous_verified_listing_form_mismatch"
    for variant in VARIANT_TERMS:
        if re.search(r"(?:^|\W)" + re.escape(variant) + r"(?:$|\W)", title):
            if variant not in name and VARIANT_AR[variant] not in name:
                return "unconfirmed_trade_variant"
    if "اس ار" in name and not re.search(r"\b(sr|sustained|retard|extended)\b", title):
        return "modified_release_not_confirmed"
    url = candidate.get("imageUrl", "")
    if not isinstance(url, str) or not url.startswith("https://"):
        return "invalid_image_link"
    return None
def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert data["totalCatalogItems"] == len(data["items"]) == 4218
    reference = {int(r["id"]): r for r in inventory["items"]}
    counts = collections.Counter()
    rows = []
    for item in data["items"]:
        rid = int(item["id"])
        if item.get("currentLocalImage"):
            continue
        good, rejected = [], []
        for candidate in item.get("candidates") or []:
            reason = check(item, candidate, reference[rid])
            if reason:
                counts[reason] += 1
                rejected.append({"title": candidate.get("title"), "source": candidate.get("sourceName"),
                                 "reason": reason})
            else:
                good.append(candidate)
        if good:
            counts["metadata_pass_needs_visual_review"] += 1
            state = "metadata_pass_needs_visual_review"
        elif rejected:
            state = "needs_corrected_candidate"
        else:
            state = "no_candidate_found"
        if good or rejected:
            rows.append({"id": rid, "name": item["name"], "englishName": item.get("englishName",""),
                         "status": state, "exactMatchConfirmed": False,
                         "reviewCandidates": good, "excluded": rejected})
    result = {
        "format": "arkan-image-approval-worklist",
        "version": 1,
        "totalCatalogItems": 4218,
        "candidateItemsReviewed": len(rows),
        "metadataPassItemCount": counts["metadata_pass_needs_visual_review"],
        "status": "metadata_filtered_NOT_VISUALLY_APPROVED",
        "rejectionCounts": dict(counts),
        "instructions": "Open and inspect each surviving actual pack. Confirm trade name, strength, form, and pack count. Only then approve; the candidate title alone is not sufficient.",
        "items": rows,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Candidate products:", len(rows), "metadata-pass:", result["metadataPassItemCount"],
          "rejected candidates:", sum(v for k,v in counts.items() if k!="metadata_pass_needs_visual_review"))
if __name__ == "__main__":
    main()
