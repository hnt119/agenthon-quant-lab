"""Read-only Coin Metrics Community BTC/USD observations for the paper recorder."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCE = "Coin Metrics Community API v4, BTC/USD reference rates"
ENDPOINT = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
BYTE_LIMIT = 24_576
SOCKET_TIMEOUT_SECONDS = 10
DAY = timedelta(days=1)
QUOTE_MAX_AGE = timedelta(minutes=5)
MARK_MAX_AGE = 2 * DAY


class SourceError(ValueError):
    """An exact requested fixing could not be qualified."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _now():
    return datetime.now(UTC)


def _iso(t):
    return t.isoformat().replace("+00:00", "Z")


def _get(url):
    request = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": "Agenthon-Quant-Lab observation/1"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != url:
                raise SourceError("unexpected provider response")
            if response.headers.get_content_type() != "application/json":
                raise SourceError("expected JSON content type")
            body = response.read(BYTE_LIMIT + 1)
            received = _now()
    except HTTPError as exc:
        raise SourceError(f"provider HTTP {exc.code}") from exc
    except (OSError, URLError) as exc:
        raise SourceError("public source unavailable") from exc
    if len(body) > BYTE_LIMIT:
        raise SourceError("response exceeds byte limit")
    return body, received


def _unique_keys(pairs):
    item = {}
    for key, value in pairs:
        if key in item:
            raise SourceError("duplicate JSON field")
        item[key] = value
    return item


def _rows(metric, frequency, labels, offset):
    url = ENDPOINT + "?" + urlencode({
        "assets": "btc", "metrics": metric, "frequency": frequency,
        "start_time": _iso(labels[0]), "end_time": _iso(labels[-1]),
        "page_size": len(labels) + 1,
    })
    body, received = _get(url)
    try:
        payload = json.loads(body, object_pairs_hook=_unique_keys)
    except (ValueError, UnicodeError) as exc:
        raise SourceError("invalid or ambiguous provider JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"data"}:
        raise SourceError("unexpected or paginated provider response")
    rows = payload["data"]
    if not isinstance(rows, list) or len(rows) != len(labels):
        raise SourceError("missing or extra provider observations")
    observations = []
    for label, row in zip(labels, rows, strict=True):
        if not isinstance(row, dict) or set(row) != {"asset", "time", metric} or row["asset"] != "btc":
            raise SourceError("wrong instrument or observation schema")
        # Exact second, or an all-zero fractional second (provider normally emits 9 zeros).
        expected = label.strftime("%Y-%m-%dT%H:%M:%S")
        if not isinstance(row["time"], str) or not re.fullmatch(expected + r"(?:\.0{1,9})?Z", row["time"]):
            raise SourceError("wrong, unordered or duplicate market timestamp")
        event = label + offset
        if received < event:
            raise SourceError("market event is later than local receipt")
        price = row[metric]
        if not isinstance(price, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", price):
            raise SourceError("invalid BTC/USD price representation")
        value = float(price)
        if not math.isfinite(value) or value <= 0:
            raise SourceError("invalid BTC/USD price")
        observations.append({"event_time": _iso(event), "price": value})
    capture = {"url": url, "raw_sha256": sha256(body).hexdigest(), "received_at": _iso(received),
               "bytes": len(body)}
    return observations, capture, received


def _limit(t, now, age):
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        raise SourceError("explicit UTC event required")
    if not timedelta(0) <= now - t <= age:
        raise SourceError("future or stale market event")


def capture_closes(cutoff: datetime, count: int = 21) -> dict:
    """Return 21 completed daily fixings for a signal, or one exact midnight mark.

    The earlier 20 PriceUSD timestamps label sessions; their events occur 24h later.
    The newest ReferenceRateUSD labels the actual midnight fixing. A 48h recovery
    ceiling permits delayed marks; the journal separately classifies their receipt.
    """
    _limit(cutoff, _now(), MARK_MAX_AGE)
    if any((cutoff.hour, cutoff.minute, cutoff.second, cutoff.microsecond)) or type(count) != int or count not in (1, 21):
        raise SourceError("expected UTC midnight and 1 or 21 closes")
    captures, observations = [], []
    if count == 21:
        labels = [cutoff - n * DAY for n in range(21, 1, -1)]
        warmup, receipt, _ = _rows("PriceUSD", "1d", labels, DAY)
        observations.extend(warmup)
        captures.append(receipt)
    mark, receipt, received = _rows("ReferenceRateUSD", "1d", [cutoff], timedelta(0))
    _limit(cutoff, received, MARK_MAX_AGE)
    if captures and received < datetime.fromisoformat(captures[-1]["received_at"]):
        raise SourceError("local receipt clock moved backwards")
    captures.append(receipt)
    return {"source": SOURCE, "received_at": _iso(received), "captures": captures,
            "observations": observations + mark}


def capture_quote(event: datetime) -> dict:
    """Read one preselected minute reference-rate fixing within five minutes."""
    _limit(event, _now(), QUOTE_MAX_AGE)
    if event.second or event.microsecond:
        raise SourceError("expected exact UTC minute")
    rows, receipt, received = _rows("ReferenceRateUSD", "1m", [event], timedelta(0))
    _limit(event, received, QUOTE_MAX_AGE)
    return {"source": SOURCE, "received_at": _iso(received), "captures": [receipt],
            "observations": rows}
