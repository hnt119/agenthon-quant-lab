from datetime import UTC, datetime, timedelta
from hashlib import sha256
import io
import json
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from observations import prospective_source as source


class CaptureTests(TestCase):
    def setUp(self):
        self.cutoff = datetime(2030, 1, 7, tzinfo=UTC)
        self.now = self.cutoff + timedelta(minutes=1)
        self.clock = patch.object(source, "_now", side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.data = []

    def fixture(self, url):
        # Independent example provider. PriceUSD's row date names the session
        # that started then; the daily reference fixing uses the following midnight.
        query = parse_qs(urlsplit(url).query)
        metric = query["metrics"][0]
        start, end = [datetime.fromisoformat(query[k][0]) for k in ("start_time", "end_time")]
        day_count = (end - start).days + 1
        raw = json.dumps({"data": [
            {"time": (start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
             "asset": "btc", metric: str(100 + i) if metric == "PriceUSD" else "132.625"}
            for i in range(day_count)]}).encode()
        self.data.append(raw)
        return raw, self.now

    def test_signal_dates_hashes_and_no_keys(self):
        with patch.object(source, "_get", side_effect=self.fixture):
            result = source.capture_closes(self.cutoff)
        self.assertEqual(len(result["observations"]), 21)
        self.assertEqual([row["event_time"] for row in result["observations"]], [
            (self.cutoff - timedelta(days=20 - i)).strftime("%Y-%m-%dT00:00:00Z") for i in range(21)])
        self.assertEqual([row["price"] for row in result["observations"]], [*range(100, 120), 132.625])
        self.assertEqual([x["raw_sha256"] for x in result["captures"]], [sha256(raw).hexdigest() for raw in self.data])
        self.assertTrue(all("api_key" not in c["url"] for c in result["captures"]))
        self.assertEqual(result["received_at"], "2030-01-07T00:01:00Z")

    def test_recovered_mark_preserves_event_and_actual_receipt(self):
        self.now = self.cutoff + timedelta(days=2)
        with patch.object(source, "_get", side_effect=self.fixture) as get:
            mark = source.capture_closes(self.cutoff, 1)
            self.assertEqual(get.call_count, 1)
            self.now += timedelta(microseconds=1)
            with self.assertRaisesRegex(source.SourceError, "stale"):
                source.capture_closes(self.cutoff, 1)
            self.assertEqual(get.call_count, 1)
        self.assertEqual(mark["received_at"], "2030-01-09T00:00:00Z")
        self.assertEqual(mark["observations"][0]["event_time"], "2030-01-07T00:00:00Z")

    def test_exact_quote_staleness_and_receipt_deadline(self):
        with patch.object(source, "_get", side_effect=self.fixture) as get:
            self.now = self.cutoff + timedelta(minutes=5)
            quote = source.capture_quote(self.cutoff)
            self.assertEqual(quote["observations"], [{"event_time":"2030-01-07T00:00:00Z", "price":132.625}])
            for t in (self.cutoff - timedelta(minutes=1), self.now + timedelta(minutes=1),
                      self.now.replace(microsecond=1), self.cutoff.replace(tzinfo=None)):
                with self.assertRaises(source.SourceError):
                    source.capture_quote(t)
            self.assertEqual(get.call_count, 1)
        with patch.object(source, "_get", return_value=(self.data[0], self.now + timedelta(microseconds=1))):
            with self.assertRaisesRegex(source.SourceError, "stale"):
                source.capture_quote(self.cutoff)

    def test_ambiguous_or_missing_provider_records(self):
        row = dict(time="2030-01-07T00:00:00Z", asset="btc", ReferenceRateUSD="99")
        invalid = [
            {"data":[]}, {"data":[row,row]}, {"data":[row], "next_page_token":"unexpected"},
            {"data":[dict(row, time="2030-01-06T00:00:00Z")]},
            {"data":[dict(row, time="2030-01-07T00:00:00.000000001Z")]},
            {"data":[dict(row, asset="eth")]}, {"data":[dict(row, extra=10)]},
            *[{"data":[dict(row, ReferenceRateUSD=v)]} for v in ("0", "NaN", None, "9"*400, -1)],
        ]
        for body in [b'{"data": [], "data":[]}', b"truncated", *map(lambda x:json.dumps(x).encode(), invalid)]:
            with self.subTest(body=body), patch.object(source, "_get", return_value=(body,self.now)):
                with self.assertRaises(source.SourceError):
                    source.capture_quote(self.cutoff)
        with patch.object(source, "_get", side_effect=self.fixture):
            for t, n in [(self.now,1),(self.cutoff, 0),(self.cutoff,True)]:
                with self.assertRaises(source.SourceError):
                    source.capture_closes(t,n)

    def test_provider_boundaries_reject_large_redirect_nonjson_http_errors(self):
        url = source.ENDPOINT + "?assets=btc"
        for size, ctype, resolved in [(source.BYTE_LIMIT+4,"application/json",url), (0,"text/html",url),
                                      (2,"application/json","https://example.edu/")]:
            response = io.BytesIO(b"x"*size)
            response.status = 200
            response.headers = Mock()
            response.headers.get_content_type.return_value = ctype
            response.geturl = lambda: resolved
            with self.subTest(size=size), patch.object(source, "build_opener") as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(source.SourceError):
                    source._get(url)
                self.assertEqual(opener.return_value.open.call_count, 1)
        for err in (HTTPError(url,429,"limited",{},None), TimeoutError()):
            with patch.object(source, "build_opener") as opener:
                opener.return_value.open.side_effect = err
                with self.assertRaises(source.SourceError):
                    source._get(url)
                self.assertEqual(opener.return_value.open.call_count, 1)
