"""Independent synthetic checks against the staged hosted-thumbnail client."""

import base64
import json
import unittest

from tests import test_existing_photo_client as support


class ThumbnailReview(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ExistingPhotoClientTests()
        self.fixture.setUp()

    def test_png_requires_both_header_and_end(self):
        valid = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
        )
        lua = self.fixture.lua
        lua.globals().client = self.fixture.client
        lua.globals().hex = valid.hex()
        self.assertTrue(
            lua.execute(
                'local b=hex:gsub("..",function(h) return string.char(tonumber(h,16)) end);'
                ' return client.validImage(b,"image/png")'
            )
        )
        for raw in (valid[:33], valid[:8] + valid[-12:], valid[:-12]):
            lua.globals().hex = raw.hex()
            self.assertFalse(
                lua.execute(
                    'local b=hex:gsub("..",function(h) return string.char(tonumber(h,16)) end);'
                    ' return client.validImage(b,"image/png")'
                )
            )

    def test_discovery_cardinality_is_validated_before_image_requests(self):
        fixture = self.fixture
        page = fixture.page(total=10, pages=2)
        value = fixture.decode(json.dumps(page))
        self.assertFalse(fixture.client.validatePage(value, 1, 5))
        self.assertIsNone(fixture.client.thumbnailPath(value.photos[1], value))

    def test_maximum_safe_revision_survives_exact_path_encoding(self):
        fixture = self.fixture
        page = fixture.page(linkedFlickrRevision=9007199254740991)
        page["photos"][0]["flickrPhotoId"] = "p@owner:001"
        value = fixture.decode(json.dumps(page))
        path = fixture.client.thumbnailPath(value.photos[1], value)
        self.assertEqual(
            path,
            "/api/v001/existing-public-photos/p%40owner%3A001/thumbnail?page=1&page_size=5&linked_flickr_revision=9007199254740991",
        )


if __name__ == "__main__":
    unittest.main()
