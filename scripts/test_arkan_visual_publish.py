#!/usr/bin/env python3
"""Offline end-to-end tests of actual Arkan OCR image publishing code.

Runs a private temporary catalogue: never touches production index.html or
commits test images. Network downloads and OCR executable are mocked, while
Pillow image decoding, thumbnail creation, seed insertion and report writes
execute for real.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

SOURCE = Path(__file__).resolve().parent / "arkan-visual-publish.py"
SOURCE_URL = "https://images.openfoodfacts.org/images/products/123/456/7.jpg"
PAGE_URL = "https://world.openfoodfacts.org/product/1234567"


class FakeImageResponse(io.BytesIO):
    @property
    def headers(self):
        return {"Content-Type": "image/png"}


def make_photo():
    pic = Image.new("RGB", (560, 420), "white")
    ImageDraw.Draw(pic).rectangle((25, 25, 535, 395), fill="lightgray", outline="black", width=4)
    raw = io.BytesIO()
    pic.save(raw, format="PNG")
    return raw.getvalue()


def exercise(ocr_text, *, medicine=False, source_page=PAGE_URL):
    with tempfile.TemporaryDirectory(prefix="arkan-visual-test-") as tmp:
        root = Path(tmp)
        (root / "data").mkdir()
        (root / "scripts").mkdir()
        (root / "assets" / "product-images").mkdir(parents=True)
        script = root / "scripts" / SOURCE.name
        shutil.copyfile(SOURCE, script)
        name = "Aptamil 2 400g"
        category = "أدوية" if medicine else "ألبان أطفال"
        html = (
            "const EXACT_MASTER_ITEMS = [\\n"
            f'  {{ name: "{name}", cat: "{category}" }},\\n'
            "];\\n"
            "const IMAGE_SEED_VERSION = 'arkan_verified_image_seed_v63';\\n"
            "const verifiedImageSeeds = {\\n"
            "};\\n"
            "const imageSeedBatches = null;\\n"
        ).replace("\\n", "\n")
        (root / "index.html").write_text(html, encoding="utf-8")
        record = {
            "url": SOURCE_URL, "source": "world.openfoodfacts.org",
            "sourcePage": source_page, "license": "Open Facts contributors CC BY-SA 3.0",
            "title": "Aptamil Stage 2 400g", "catalogName": name,
            "englishName": "Aptamil Stage 2 400g",
            "status": "auto_published_strict_unverified_pack",
        }
        (root / "data" / "arkan-auto-published-images.json").write_text(
            json.dumps({"version": 1, "byId": {"1": record}}), encoding="utf-8"
        )
        image_bytes = make_photo()
        opener = SimpleNamespace(open=lambda request, timeout: FakeImageResponse(image_bytes))
        completed = SimpleNamespace(returncode=0, stdout=ocr_text)
        with patch("urllib.request.build_opener", return_value=opener), \
             patch("subprocess.run", return_value=completed), \
             patch.dict(os.environ, {"VISUAL_PUBLISH_BUDGET": "5"}), \
             contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(script), run_name="__main__")
        report = json.loads(
            (root / "data" / "arkan-visual-publish-report.json").read_text(encoding="utf-8")
        )
        updated = (root / "index.html").read_text(encoding="utf-8")
        photo = root / "assets" / "product-images" / "1.jpg"
        exists = photo.exists()
        if exists:
            with Image.open(photo) as result:
                result.verify()
        return report, updated, exists


class VisualPublisherTest(unittest.TestCase):
    def test_exact_pack_publishes_to_local_jpeg_and_portal_seed(self):
        report, html, exists = exercise("Aptamil Stage 2 400g")
        self.assertEqual(report["scanned"], 1)
        self.assertEqual(report["published"], 1)
        self.assertEqual(report["published_ids"], ["1"])
        self.assertTrue(exists)
        self.assertIn("assets/product-images/1.jpg", html)
        self.assertIn(PAGE_URL, html)
        self.assertIn("arkan_verified_image_seed_v64", html)

    def test_wrong_brand_cannot_be_published(self):
        report, html, exists = exercise("Nutrilon Stage 2 400g")
        self.assertEqual(report["published"], 0)
        self.assertFalse(exists)
        self.assertNotIn("assets/product-images/1.jpg", html)
        self.assertIn("pack_name_not_confirmed", [x["reason"] for x in report["review"]])

    def test_medicine_never_enters_consumer_product_publisher(self):
        report, html, exists = exercise("Aptamil Stage 2 400g", medicine=True)
        self.assertEqual(report["published"], 0)
        self.assertEqual(report["scanned"], 0)
        self.assertFalse(exists)

    def test_untrusted_source_page_cannot_write_any_seed(self):
        report, html, exists = exercise(
            "Aptamil Stage 2 400g",
            source_page="https://world.openfoodfacts.org/product/1234567/extra"
        )
        self.assertEqual(report["published"], 0)
        self.assertFalse(exists)


if __name__ == "__main__":
    unittest.main(verbosity=2)
