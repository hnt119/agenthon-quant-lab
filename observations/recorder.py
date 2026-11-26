"""Immutable, replayed receipts for the registered paper accounts. No broker interface."""
import hashlib
import json
import math
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from observations.prospective_source import BYTE_LIMIT, ENDPOINT, SOURCE

from observations.paper_accounts import (
    apply_fill, decision, fresh_accounts, mark_accounts, summarize, verify_fill,
)

UTC = timezone.utc
DAY = timedelta(days=1)
MIN = timedelta(minutes=1)
MAX_BYTES = 5_000_000


def require(test, message):
    if not test:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stamp(value):
    require(value.tzinfo is not None and value.utcoffset() == timedelta(0), "Expected UTC clock")
    return value.isoformat().replace("+00:00", "Z")


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    stamp(result)
    return result


def midnight(day):
    return datetime.combine(day, time(), UTC)


def bounds(p):
    first, last = date.fromisoformat(p["start"]), date.fromisoformat(p["end"])
    require(first.weekday() == 0 and last - first == 363 * DAY, "Expected complete 52-week horizon")
    return first, last


def evidence(record, dates, at):
    prices = []
    obs, parts = record["observations"], record["captures"]
    require(record["source"] == SOURCE and len(obs) == len(dates), "Source shape")
    receipt = instant(record["received_at"])
    require(receipt <= at, "Receipt from future")
    groups = []
    if len(dates) == 21:
        groups.append(("PriceUSD", "1d", dates[0]-DAY, dates[-2]-DAY, 20))
    last = dates[-1]
    groups.append(("ReferenceRateUSD", "1d" if last == midnight(last.date()) else "1m", last, last, 1))
    require(len(groups) == len(parts), "Source request count")
    for (metric, frequency, begin, end, size), part in zip(groups, parts, strict=True):
        url = ENDPOINT + "?" + urlencode(dict(assets="btc", metrics=metric, frequency=frequency,
            start_time=stamp(begin), end_time=stamp(end), page_size=size+1))
        require(re.fullmatch(r"[a-f0-9]{64}", part["raw_sha256"]) and part["url"] == url and
                0 < part["bytes"] <= BYTE_LIMIT and
                (end + DAY if metric == "PriceUSD" else end) <= instant(part["received_at"]) <= receipt, "Source identity")
    require(instant(parts[-1]["received_at"]) == receipt, "Last receipt mismatch")
    for item, expected in zip(obs, dates):
        price = item["price"]
        require(instant(item["event_time"]) == expected <= receipt and
                type(price) in (float, int) and math.isfinite(price) and price > 0, "Invalid fixing")
        prices.append(price)
    return prices


class Journal:
    def __init__(self, root, protocol):
        self.root, self.protocol = Path(root), protocol
        self.first, self.last = bounds(protocol)
        self.reg = json.loads((self.root / "registration.json").read_bytes())
        self.registered = instant(self.reg["registered_at"])
        require(self.registered < instant(protocol["registration_deadline"]), "Late registration")
        self.events = []
        self.keys = set()
        self.decisions, self.fills, self.marks, self.mark_prices = {}, {}, {}, {}
        self.decision_times = {}
        self.accounts = fresh_accounts()
        self.errors = self.byte_count = 0
        self.closed = False
        self.last_hash = digest(canonical(self.reg))
        folder = self.root / "events"
        if folder.exists():
            require(folder.is_dir() and not folder.is_symlink(), "Invalid record directory")
            for n, path in enumerate(sorted(folder.iterdir()), 1):
                require(path.name == f"{n:05d}.json" and path.is_file() and not path.is_symlink()
                        and path.stat().st_size <= 65536, "Invalid event file")
                raw = path.read_bytes()
                event = json.loads(raw)
                require(canonical(event) == raw, "Noncanonical event")
                self.consume(event, raw)

    def consume(self, e, raw):
        key, kind = e["key"], e["kind"]
        require(not self.closed and len(self.events) < 2200 and self.byte_count + len(raw) < MAX_BYTES and
                e["previous"] == self.last_hash and key not in self.keys, "Invalid event chain")
        at = instant(e["recorded_at"])
        require(at >= self.registered and (not self.events or at >= instant(self.events[-1]["recorded_at"])),
                "Invalid or reversed recording time")
        day = date.fromisoformat(e["day"])
        t = midnight(day)
        payload = e["data"]
        latest = instant(self.protocol["closeout"]).date() if kind == "error" else self.last
        require(self.first <= day <= latest and key == f"{kind}/{day}", "Invalid event identity")
        if kind in ("decision", "fill"):
            require(day.weekday() == 0 and e["scope"] == "prospective", "Invalid cycle")
            book = self.decisions if kind == "decision" else self.fills
            valid = payload["status"] == "accepted"
            if valid and kind == "decision":
                self.decision_times[day] = at
                require(t <= at < t + 35 * MIN, "Late decision")
                prices = evidence(payload["source"], [t - i*DAY for i in reversed(range(21))], at)
                closes = [dict(date=(day - (21-i)*DAY).isoformat(),close=p) for i,p in enumerate(prices)]
                require(payload["instruction"] == decision(day.isoformat(), closes) and
                        instant(payload["input_cutoff"]) == t and
                        payload["delay_seconds"] == (at-(t+7*MIN)).total_seconds(), "Signal differs")
            elif valid:
                require(day in self.decisions and self.decisions[day]["status"] == "accepted", "No instruction")
                require(re.fullmatch(r"[0-9a-f]{40}", payload["witness_revision"]), "Missing public witness revision")
                witnessed = instant(payload["witnessed_at"])
                fixing = t + 45 * MIN
                require(self.decision_times[day] <= witnessed < fixing <= at <= fixing + 5*MIN,
                        "Quote outside prospective window")
                price, = evidence(payload["source"], [fixing], at)
                require(payload["delay_seconds"] == (instant(payload["source"]["received_at"])-fixing).total_seconds(),
                        "Wrong fill delay")
                verify_fill(self.accounts, self.decisions[day]["instruction"]["positive"], price,
                            payload["accounts"], payload["trades"])
                self.accounts = payload["accounts"]
            else:
                require(payload["status"] == "missed" and bool(payload["reason"]) and at >= t, "Invalid missed cycle")
            book[day] = payload
        elif kind == "mark":
            fixing = t + DAY
            require(at >= fixing and e["scope"] == "valuation", "Premature close")
            if payload["status"] == "missing":
                require(at > fixing + 2*DAY and payload["reason"] == "recovery_window_elapsed", "Premature missing mark")
                self.marks[day.isoformat()] = None
            else:
                require(payload["status"] == ("recovered" if at > fixing + 360*MIN else "observed")
                        and at <= fixing + 2*DAY, "Wrong valuation receipt window")
                price, = evidence(payload["source"], [fixing], at)
                prior_fills = [d for d,v in self.fills.items() if d <= day and v["status"] == "accepted"]
                balance = self.fills[max(prior_fills)]["accounts"] if prior_fills else fresh_accounts()
                values = mark_accounts(balance, price)
                require(values == payload["wealth"], "Closing wealth differs")
                self.marks[day.isoformat()], self.mark_prices[day] = values, price
        elif kind == "error":
            require(e["scope"] == "operations" and at.date() == day and isinstance(payload["failures"], list) and
                    0 < len(payload["failures"]) <= 3, "Invalid failure record")
            self.errors += len(payload["failures"])
        elif kind == "revision":
            require(e["scope"] == "operations" and day in self.decisions and
                    self.decisions[day]["status"] == "accepted" and
                    payload["differences"] == self.revisions(day, self.decisions[day]["source"]) and
                    bool(payload["differences"]), "Invalid source revision")
        elif kind == "closed":
            require(day == self.last and at >= instant(self.protocol["closeout"]) and
                    len(self.marks) == 364 and len(self.decisions) == len(self.fills) == 52, "Premature closeout")
            self.closed = True
        else:
            raise ValueError("Unknown event")
        self.last_hash = digest(raw)
        self.byte_count += len(raw)
        self.events.append(e)
        self.keys.add(key)

    def revisions(self, monday, source):
        changes = []
        for i, item in enumerate(source["observations"]):
            day = monday - (21-i)*DAY
            if day in self.mark_prices and self.mark_prices[day] != item["price"]:
                changes.append({"day": day.isoformat(), "original": self.mark_prices[day], "observed":item["price"]})
        return changes

    def append(self, kind, day, at, data, scope):
        e = dict(key=f"{kind}/{day}", kind=kind, day=day.isoformat(), recorded_at=stamp(at),
                 previous=self.last_hash, data=data, scope=scope)
        raw = canonical(e)
        self.consume(e, raw)
        folder = self.root / "events"
        folder.mkdir(exist_ok=True)
        with (folder / f"{len(self.events):05d}.json").open("xb") as file:
            file.write(raw)

    def projection(self):
        result = summarize(self.accounts, self.marks, self.first.isoformat(), self.last.isoformat())
        if not self.closed and result["status"] == "complete":
            result["status"] = "awaiting_registered_analysis"
            result["primary_drawdown_difference_pp"] = None
        return dict(study=self.protocol["study"], start=self.protocol["start"], end=self.protocol["end"],
                    registered_at=self.reg["registered_at"], revision=self.reg["revision"], closed=self.closed,
                    as_of=self.events[-1]["recorded_at"] if self.events else self.reg["registered_at"],
                    latest_observation_at=next((e["recorded_at"] for e in reversed(self.events)
                          if e["data"].get("status") in ("accepted","observed","recovered")), None),
                    decisions_recorded=sum(d["status"] == "accepted" for d in self.decisions.values()),
                    completed=sum(d["status"] == "accepted" for d in self.fills.values()),
                    missed=sum(d["status"] == "missed" for d in self.fills.values()), scheduled=52,
                    failures=self.errors, last_event_sha256=self.last_hash,
                    status="closed" if self.closed else "collecting" if self.events else "registered",
                    attribution="Coin Metrics Community Data, CC BY-NC 4.0. Aligned fixing dates and hypothetical valuations by Agenthon Quant Lab.",
                    license="https://creativecommons.org/licenses/by-nc/4.0/",
                    inference="Interim figures descriptive; fixed closing endpoint requires 364 valuations.",
                    financial=result)

    def save_status(self):
        target = self.root / "status.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(canonical(self.projection()))
        os.replace(tmp, target)


def validate(state_dir, protocol):
    journal = Journal(state_dir, protocol)
    require((journal.root / "status.json").read_bytes() == canonical(journal.projection()), "Projection differs")
    return journal.projection()


def run(state_dir, protocol, phase, *, now, closes, quote, witnessed_at=None, witness_revision=None):
    """One bounded turn. Caller validates remote revision, registration and persistent branch."""
    validate(state_dir, protocol)
    j = Journal(state_dir, protocol)
    at = now()
    today = at.date()
    if j.closed or today < j.first:
        return j.projection()
    if phase in ("decision", "fill"):
        if today > j.last or today.weekday() != 0:
            return j.projection()
        t = midnight(today)
        book = j.decisions if phase == "decision" else j.fills
        if today in book:
            return j.projection()
        if phase == "decision":
            if not t <= at < t + 35*MIN:
                return j.projection()
            try:
                rec = closes(t, count=21)
                at = now()
                prices = evidence(rec, [t-i*DAY for i in reversed(range(21))], at)
                require(at < t+35*MIN, "decision_deadline")
                rows = [dict(date=(today-(21-i)*DAY).isoformat(), close=p) for i,p in enumerate(prices)]
                data = dict(status="accepted", input_cutoff=stamp(t), source=rec, instruction=decision(str(today),rows),
                            delay_seconds=(at-(t+7*MIN)).total_seconds())
            except (ValueError, OSError, KeyError, TimeoutError, RuntimeError) as err:
                data = dict(status="missed", reason="decision_capture_"+type(err).__name__)
            j.append(phase,today,now() if data["status"]=="missed" else at,data,"prospective")
            if data["status"] == "accepted" and (changes := j.revisions(today, rec)):
                j.append("revision", today, now(), dict(differences=changes), "operations")
        else:
            fixing = t+45*MIN
            eligible = today in j.decisions and j.decisions[today]["status"] == "accepted"
            if not (eligible and witnessed_at and re.fullmatch(r"[a-f0-9]{40}", witness_revision or "")
                    and j.decision_times[today] <= witnessed_at < fixing <= at <= fixing+5*MIN):
                return j.projection()
            try:
                rec = quote(fixing)
                at = now()
                price, = evidence(rec, [fixing], at)
                require(at <= fixing+5*MIN, "quote_deadline")
            except (ValueError, OSError, KeyError, TimeoutError, RuntimeError) as err:
                j.append(phase,today,now(),dict(status="missed",reason="quote_capture_"+type(err).__name__),"prospective")
            else:
                after,trades = apply_fill(j.accounts,j.decisions[today]["instruction"]["positive"],price)
                j.append(phase,today,at,dict(status="accepted",source=rec,witnessed_at=stamp(witnessed_at),
                         witness_revision=witness_revision,verification="independent accounting replay passed",
                         delay_seconds=(instant(rec["received_at"])-fixing).total_seconds(),accounts=after,
                         trades=trades),"prospective")
    elif phase == "marks":
        failures = []
        # Reconcile every elapsed slot. Only recent closes may trigger a network request.
        for i in range(364):
            day = j.first+i*DAY
            t = midnight(day)
            if day.weekday()==0 and at > t+50*MIN:
                for kind,book in (("decision",j.decisions),("fill",j.fills)):
                    if day not in book:
                        j.append(kind,day,now(),dict(status="missed",reason="no_eligible_durable_record"),"prospective")
            fixing = t+DAY
            if at < fixing or str(day) in j.marks:
                continue
            if at > fixing+2*DAY:
                j.append("mark",day,now(),dict(status="missing",reason="recovery_window_elapsed"),"valuation")
                continue
            # A run per UTC date; up to three eligible fixings at the exact endpoint.
            attempt_day = today
            if f"error/{attempt_day}" in j.keys:
                continue
            try:
                rec = closes(fixing,count=1)
                received = now()
                price, = evidence(rec,[fixing],received)
                require(received <= fixing+2*DAY, "valuation_deadline")
            except (ValueError,OSError,KeyError,TimeoutError,RuntimeError) as err:
                failures.append({"day":str(day), "type":type(err).__name__})
                continue
            fills = [d for d,v in j.fills.items() if d<=day and v["status"]=="accepted"]
            balances = j.fills[max(fills)]["accounts"] if fills else fresh_accounts()
            j.append("mark",day,received,dict(status="recovered" if received > fixing+360*MIN else "observed",
                     source=rec,wealth=mark_accounts(balances,price)),"valuation")
        if failures:
            j.append("error",today,now(),dict(failures=failures),"operations")
        if at >= instant(protocol["closeout"]):
            j.append("closed",j.last,now(),{},"operations")
    else:
        raise ValueError("Unknown phase")
    j.save_status()
    return validate(state_dir,protocol)
