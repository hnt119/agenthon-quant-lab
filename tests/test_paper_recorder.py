"""Offline, dated source-receipt and immutable paper-journal integration checks."""
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from observations import prospective_source as public
from observations import recorder as record


DAY = timedelta(days=1)
MIN = timedelta(minutes=1)


class ScheduledRecorderTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.protocol = json.loads(Path(record.__file__).with_name("protocol.json").read_bytes())
        self.start = datetime.fromisoformat(self.protocol["start"]).replace(tzinfo=UTC)
        self.end = datetime.fromisoformat(self.protocol["end"]).replace(tzinfo=UTC)
        self.t = self.start
        self.urls = []
        self.shift = 0
        self.fail = False
        self.clock_lag = timedelta(0)
        reg = {"registered_at": (self.t - 5*DAY).isoformat(), "revision":"1"*40}
        (self.root/"registration.json").write_text(json.dumps(reg))
        self.journal().save_status()
        for p in [patch.object(public, "_now", side_effect=lambda: self.t),
                  patch.object(public, "_get", side_effect=self.provider)]:
            p.start()
            self.addCleanup(p.stop)

    def journal(self):
        return record.Journal(self.root, self.protocol)

    def provider(self, url):
        # Synthetic provider transport only. Exercise the real adapter including
        # its distinct provider DAY labels and minute-fixing timestamps.
        self.urls.append(url)
        if self.fail:
            raise public.SourceError("synthetic public source outage")
        q = parse_qs(urlsplit(url).query)
        begin, end = [datetime.fromisoformat(q[k][0]) for k in ("start_time", "end_time")]
        metric = q["metrics"][0]
        rows = []
        for i in range((end-begin).days + 1):
            label = begin + i*DAY
            event = label + (DAY if metric == "PriceUSD" else timedelta(0))
            usd = 50000 + (event-self.start).days + self.shift
            rows.append({"asset":"btc", "time":label.strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
                         metric:str(usd)})
        return json.dumps({"data":rows}).encode(), self.t - self.clock_lag

    def run_phase(self, when, phase, **kwargs):
        self.t = when
        if "witnessed_at" in kwargs:
            kwargs["witness_revision"] = "1"*40
        return record.run(self.root, self.protocol, phase, now=lambda:self.t,
                          closes=public.capture_closes, quote=public.capture_quote, **kwargs)

    def test_restart_before_quote_duplicate_jobs_and_financial_tamper(self):
        before = self.run_phase(self.start-DAY, "decision")
        self.assertEqual((before["completed"], before["latest_observation_at"], self.urls), (0,None,[]))
        instruction = self.run_phase(self.start+7*MIN, "decision")
        self.assertEqual((instruction["decisions_recorded"],instruction["completed"],len(self.urls)), (1,0,2))
        receipt_path = self.root/"events/00001.json"
        original = receipt_path.read_bytes()
        self.assertEqual(self.run_phase(self.start+8*MIN,"decision"), instruction)
        self.assertEqual(len(self.urls),2)
        witnessed = self.start+41*MIN
        result = self.run_phase(self.start+46*MIN,"fill",witnessed_at=witnessed)
        self.assertEqual(result["completed"],1)
        self.assertEqual(self.run_phase(self.start+47*MIN,"fill",witnessed_at=witnessed),result)
        self.assertEqual(len(self.urls),3)
        self.assertEqual(original,receipt_path.read_bytes())
        self.assertEqual(record.validate(self.root,self.protocol),result)
        fill_path = self.root/"events/00002.json"
        fill = json.loads(fill_path.read_bytes())
        self.assertEqual(fill["data"]["accounts"]["half_funded"]["reserve"],5000)
        fill["data"]["accounts"]["half_funded"]["reserve"] = 4999
        fill_path.write_bytes(record.canonical(fill))
        with self.assertRaises(ValueError):
            record.validate(self.root,self.protocol)

    def test_pre_fill_witness_and_late_jobs_never_backfill(self):
        self.run_phase(self.start+8*MIN,"decision")
        for wake, witness in [(46,45),(51,41),(44,41)]:
            result = self.run_phase(self.start+wake*MIN,"fill",witnessed_at=self.start+witness*MIN)
            self.assertEqual(result["completed"],0)
        self.assertEqual(len(self.urls),2)
        result = self.run_phase(self.start+3*60*MIN, "marks")
        self.assertEqual((result["completed"],result["missed"]),(0,1))
        self.assertEqual(self.journal().accounts["target50"]["cash"], 10000)
        self.assertEqual(self.journal().accounts["half_funded"]["shares"], 0)
        self.assertEqual(len(self.urls), 2)

    def test_fetch_crossing_deadline_is_a_miss(self):
        self.run_phase(self.start+7*MIN,"decision")
        def delayed_quote(event):
            self.t = event + 6*MIN
            return public.capture_quote(event)
        self.t = self.start+46*MIN
        result = record.run(self.root,self.protocol,"fill",now=lambda:self.t,
                            closes=public.capture_closes,quote=delayed_quote,witnessed_at=self.start+41*MIN,witness_revision="1"*40)
        self.assertEqual((result["completed"],result["missed"]),(0,1))

    def test_missed_decision_cannot_trade_even_if_source_recovers(self):
        self.fail = True
        self.run_phase(self.start+7*MIN,"decision")
        self.fail = False
        result = self.run_phase(self.start+46*MIN,"fill",witnessed_at=self.start+41*MIN)
        self.assertEqual((result["completed"],result["decisions_recorded"],len(self.urls)),(0,0,1))
        self.assertEqual(self.run_phase(self.start+51*MIN,"marks")["missed"],1)

    def test_outage_recovery_and_observed_source_revision_are_append_only(self):
        self.fail = True
        result = self.run_phase(self.start+DAY+180*MIN,"marks")
        self.assertEqual((result["failures"],result["financial"]["observed_marks"]),(1,0))
        self.fail = False
        result = self.run_phase(self.start+2*DAY+180*MIN,"marks")
        days = self.journal().events
        restored = next(e for e in days if e["kind"]=="mark" and e["day"]==self.start.date().isoformat())
        self.assertEqual(restored["data"]["status"],"recovered")
        self.assertEqual(restored["data"]["source"]["received_at"], record.stamp(self.t))
        self.assertEqual(result["financial"]["observed_marks"],2)
        files = {p:p.read_bytes() for p in (self.root/"events").iterdir()}
        self.shift = 1
        self.run_phase(self.start+7*DAY+7*MIN,"decision")
        changes = [e for e in self.journal().events if e["kind"]=="revision"]
        self.assertEqual(len(changes),1)
        self.assertEqual([d["observed"]-d["original"] for d in changes[0]["data"]["differences"]],[1.,1.])
        self.assertEqual(files,{p:p.read_bytes() for p in files})

    def test_early_missing_mark_rejected(self):
        # A scheduler interruption can still recover this exact fixing the next day.
        with self.assertRaises(ValueError):
            self.journal().append("mark",self.start.date(),self.start+DAY+MIN,
                                  {"status":"missing","reason":"recovery_window_elapsed"},"valuation")

    def test_actual_decision_must_exist_before_remote_witness(self):
        # Data arrived early but this decision wasn't durably made until minute 15.
        self.clock_lag = 8*MIN
        self.run_phase(self.start+15*MIN,"decision")
        self.clock_lag = timedelta(0)
        try:
            result = self.run_phase(self.start+46*MIN,"fill",witnessed_at=self.start+8*MIN)
        except ValueError:
            pass
        else:
            self.assertEqual(result["completed"],0)
        self.assertEqual(self.journal().accounts["half_funded"]["shares"],0)

    def test_projection_corruption_stops_before_source_access(self):
        status_path = self.root/"status.json"
        displayed = json.loads(status_path.read_bytes())
        displayed["completed"] = 1000
        status_path.write_bytes(record.canonical(displayed))
        with self.assertRaisesRegex(ValueError,"Projection differs"):
            self.run_phase(self.start+7*MIN,"decision")
        self.assertEqual(self.urls,[])

    def test_final_week_transient_failure_can_recover_on_next_job(self):
        self.fail = True
        self.run_phase(self.end+180*MIN, "marks")
        self.fail = False
        result = self.run_phase(self.end+DAY+180*MIN,"marks")
        self.assertEqual(result["financial"]["latest_mark"], self.end.date().isoformat())
        self.assertEqual(result["financial"]["observed_marks"],2)
        self.assertEqual(result["financial"]["accounts"]["target50"]["ending_wealth"],10000)

    def test_terminal_misses_remain_in_denominator_and_closeout_is_idempotent(self):
        closed_at = datetime.fromisoformat(self.protocol["closeout"])
        state = self.run_phase(closed_at,"marks")
        self.assertTrue(state["closed"])
        self.assertEqual((state["scheduled"],state["completed"],state["missed"]), (52,0,52))
        self.assertEqual((state["financial"]["observed_marks"],state["financial"]["missing_marks"],
                          state["financial"]["pending_marks"]),(0,364,0))
        self.assertIsNone(state["financial"]["primary_drawdown_difference_pp"])
        self.assertEqual(self.run_phase(closed_at+DAY,"marks"),state)
        self.assertEqual(self.urls,[])

    def test_interrupted_local_write_cannot_be_resumed_as_a_committed_decision(self):
        # Simulate loss between local event write and recording its projection.
        # Only remote, complete Git snapshots can witness a future quote.
        with patch.object(record.Journal, "save_status", side_effect=OSError("interrupted local write")):
            with self.assertRaises(OSError):
                self.run_phase(self.start+7*MIN,"decision")
        self.assertTrue((self.root/"events/00001.json").is_file())
        with self.assertRaisesRegex(ValueError,"Projection differs"):
            self.run_phase(self.start+46*MIN,"fill",witnessed_at=self.start+41*MIN)
        self.assertEqual(len(self.urls),2)

    def test_complete_synthetic_cash_period_has_all_marks_and_defined_zero_drawdown(self):
        j = self.journal()
        for index in range(364):
            day = self.start + index*DAY
            if day.weekday() == 0:
                for kind in ("decision","fill"):
                    j.append(kind,day.date(),day+51*MIN,
                             {"status":"missed","reason":"no_eligible_durable_record"},"prospective")
            cutoff = day+DAY
            self.t = cutoff+MIN
            fixing = public.capture_closes(cutoff,1)
            j.append("mark",day.date(),self.t,
                     {"status":"observed","source":fixing,"wealth":{"target50":10000,"half_funded":10000}},
                     "valuation")
        j.save_status()
        self.assertIsNone(j.projection()["financial"]["primary_drawdown_difference_pp"])
        state = self.run_phase(datetime.fromisoformat(self.protocol["closeout"]),"marks")
        self.assertTrue(state["closed"])
        self.assertEqual(state["financial"]["observed_marks"],364)
        self.assertEqual(state["financial"]["primary_drawdown_difference_pp"],0)
        self.assertEqual((state["completed"],state["missed"]),(0,52))

    def test_replay_rejects_modified_provider_identity_and_capture_envelope(self):
        self.t = self.start+7*MIN
        dates = [self.start-days*DAY for days in reversed(range(21))]
        sample = public.capture_closes(self.start)
        self.assertEqual(len(record.evidence(sample,dates,self.t)),21)
        for change in ("source","metrics","limit","capture_count","receipt","identical_date","instrument"):
            with self.subTest(change=change):
                altered = json.loads(json.dumps(sample))
                first = altered["captures"][0]
                if change == "source":
                    altered["source"] = "Different provider"
                elif change == "metrics":
                    first["url"] = first["url"].replace("PriceUSD","ReferenceRateUSD")
                elif change == "limit":
                    first["bytes"] = public.BYTE_LIMIT + 1
                elif change == "capture_count":
                    altered["captures"].pop(0)
                elif change == "receipt":
                    altered["captures"][-1]["received_at"] = record.stamp(self.t-MIN)
                elif change == "identical_date":
                    altered["observations"][0]["event_time"] = altered["observations"][1]["event_time"]
                else:
                    first["url"] = first["url"].replace("assets=btc","assets=eth")
                with self.assertRaises(ValueError):
                    record.evidence(altered,dates,self.t)
