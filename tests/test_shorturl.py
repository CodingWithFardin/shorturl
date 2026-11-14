import json
import os
import tempfile
import unittest

from shorturl.server import handle
from shorturl.store import Shortener, encode_id, resolve_path


class Clock:
    def __init__(self):
        self.now = 500.0

    def __call__(self):
        return self.now


class RoutingTest(unittest.TestCase):
    def test_resolve_path(self):
        self.assertEqual(resolve_path("/abc123"), ("redirect", "abc123"))
        self.assertEqual(resolve_path("/api/links?x=1"), ("api", "links"))
        self.assertEqual(resolve_path("/health"), ("health", ""))
        self.assertEqual(resolve_path("/a"), ("not_found", "/a"))

    def test_encode_is_stable_and_fixed_width(self):
        self.assertEqual(len(encode_id(1)), 6)
        self.assertEqual(encode_id(62), "000010")
        self.assertNotEqual(encode_id(61), encode_id(62))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Shortener(os.path.join(self.tmp.name, "l.db"), clock=Clock())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_shorten_is_idempotent(self):
        first = self.store.shorten("https://example.com/a")
        second = self.store.shorten("https://example.com/a")
        self.assertEqual(first, second)

    def test_rejects_relative_urls(self):
        with self.assertRaises(ValueError):
            self.store.shorten("/nope")

    def test_resolve_counts_hits(self):
        code = self.store.shorten("https://example.com/b")
        self.assertEqual(self.store.resolve(code), "https://example.com/b")
        self.store.hit(code)
        self.store.hit(code)
        self.assertEqual(self.store.stats(code)["hits"], 2)

    def test_top_orders_by_hits(self):
        low = self.store.shorten("https://example.com/low")
        high = self.store.shorten("https://example.com/high")
        self.store.hit(high)
        self.store.hit(high)
        self.store.hit(low)
        self.assertEqual(self.store.top(1)[0]["code"], high)


class HandlerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Shortener(os.path.join(self.tmp.name, "h.db"), clock=Clock())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_create_then_redirect(self):
        status, headers, body = handle(self.store, "POST", "/api/links",
                                       b'{"url":"https://example.com/x"}')
        self.assertEqual(status, 201)
        code = json.loads(body)["code"]
        status, headers, _ = handle(self.store, "GET", "/" + code)
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "https://example.com/x")

    def test_bad_payload(self):
        status, _, _ = handle(self.store, "POST", "/api/links", b'{"url":"relative"}')
        self.assertEqual(status, 400)

    def test_unknown_code(self):
        status, _, _ = handle(self.store, "GET", "/zzzzzz")
        self.assertEqual(status, 404)

    def test_health(self):
        status, _, body = handle(self.store, "GET", "/health")
        self.assertEqual(status, 200)
        self.assertIn(b"true", body)


if __name__ == "__main__":
    unittest.main()
