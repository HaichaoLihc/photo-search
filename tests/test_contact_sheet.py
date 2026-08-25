import unittest
from io import BytesIO

from PIL import Image

from contact_sheet import make_manifest, render_contact_sheet


class ContactSheetTests(unittest.TestCase):
    def test_renders_missing_images_as_placeholders(self):
        for count in (10, 50):
            with self.subTest(count=count):
                results = [
                    {
                        "rank": index + 1,
                        "photo_id": f"photo_{index:016x}",
                        "score": 0.9 - index / 100,
                        "path": f"/missing/photo-{index}.jpg",
                        "filename": f"photo-{index}.jpg",
                        "parent_dir": "missing",
                        "exists": False,
                    }
                    for index in range(count)
                ]

                png = render_contact_sheet("test query", results)
                with Image.open(BytesIO(png)) as sheet:
                    self.assertEqual(sheet.format, "PNG")
                    self.assertGreater(sheet.width, 1000)
                    self.assertGreater(sheet.height, 400)

    def test_manifest_preserves_grid_position_to_photo_id_mapping(self):
        search_result = {
            "query": "mountains",
            "total_indexed": 100,
            "execution_time_ms": 12.5,
            "results": [
                {
                    "rank": 1,
                    "photo_id": "photo_0123456789abcdef",
                    "score": 0.81,
                    "path": "/photos/a.jpg",
                    "filename": "a.jpg",
                    "parent_dir": "photos",
                    "exists": True,
                }
            ],
        }

        manifest = make_manifest(search_result)
        self.assertEqual(manifest["items"][0]["position"], 1)
        self.assertEqual(manifest["items"][0]["row"], 1)
        self.assertEqual(manifest["items"][0]["column"], 1)
        self.assertEqual(manifest["items"][0]["photo_id"], "photo_0123456789abcdef")


if __name__ == "__main__":
    unittest.main()
