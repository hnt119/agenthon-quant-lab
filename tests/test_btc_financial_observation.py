from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from unittest import TestCase

from agenthon_financial.analysis import intervals
from agenthon_financial.observe import observation
from agenthon_financial.study import DATA, read_rows


class ObservationTests(TestCase):
    def setUp(self):
        self.raw=(DATA/"sessions.csv").read_bytes()
        self.source=(DATA/"source.json").read_bytes()

    def test_backfilled_observation_has_no_outcome(self):
        o=observation(self.raw,self.source,datetime(2026,11,23,tzinfo=timezone.utc))
        self.assertEqual(o["status"],"retrospective backfill")
        self.assertEqual(o["information_cutoff"],"2025-01-01T00:00:00+00:00")
        self.assertIsNone(o["realized_performance"])

    def test_prospective_window_and_source_binding(self):
        # Artificial append-only history, never a study result.
        row=self.raw.splitlines()[-1].split(b",",1)[1]
        start=date(2025,1,1)
        last=date(2026,11,21)
        extra=b"".join(str(start+timedelta(days=i)).encode()+b","+row+b"\n" for i in range((last-start).days+1))
        snapshot=self.raw+extra
        source=json.loads(self.source)
        source["quality"]["sha256"]=sha256(snapshot).hexdigest()
        source["retrieved_completed_utc"]="2026-11-22T00:02:00+00:00"
        source["quality"]["days"]=len(snapshot.splitlines())-1
        source=json.dumps(source).encode()
        now=datetime(2026,11,22,0,3,tzinfo=timezone.utc)
        self.assertEqual(observation(snapshot,source,now)["status"],"prospective intent")
        self.assertEqual(observation(snapshot,source,now+timedelta(minutes=2))["status"],"retrospective backfill")
        with self.assertRaisesRegex(ValueError,"source manifest"):
            observation(snapshot,self.source,now)
        with self.assertRaisesRegex(ValueError,"acquisition time"):
            observation(snapshot,source,now-timedelta(minutes=3))
        with self.assertRaisesRegex(ValueError,"append-only"):
            observation(snapshot[1:],source,now)

    def test_reject_missing_proxy_or_session(self):
        lines=self.raw.splitlines(keepends=True)
        with self.assertRaisesRegex(ValueError,"noncontiguous"):
            read_rows(b"".join([*lines[:2],lines[3]]))
        fields=lines[1].decode().split(",")
        fields[4]="4"
        with self.assertRaisesRegex(ValueError,"proxies"):
            read_rows(lines[0]+",".join(fields).encode())

    def test_paired_blocks_preserve_identical_arms_and_fixed_state_gap(self):
        path=[dict(date=f"2020-01-{i+1:02d}",daily_return=.01*(-1)**i) for i in range(24)]
        lab=[dict(date=e["date"],positive=i%2==0,forward=.04 if i%2==0 else -.01) for i,e in enumerate(path)]
        ci=intervals((path,path),lab,[2020],dict(draws=40,seed=77,block_sessions=4))
        self.assertEqual(ci["sharpe_delta"],[0,0])
        for end in ci["predictive_difference"]:
            self.assertAlmostEqual(end,.05)
