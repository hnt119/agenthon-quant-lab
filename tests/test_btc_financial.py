import copy
from datetime import date, timedelta
import math
import unittest

from agenthon_financial.analysis import analyze, labels
from agenthon_financial.study import books, fit_weights, frozen, rebalance, signals
from agenthon_financial.verify import verify


class FinancialResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=frozen()[0] | dict(evaluation_years=[2020,2021],uncertainty=dict(seed=3,draws=32,block_sessions=20))
        start=date(2019,9,1)
        cls.rows=[]
        for i in range(505):
            p=90+10*math.sin(i*.12)+5*math.cos(i*.073)+i*.02
            cls.rows.append(dict(date=str(start+timedelta(days=i)),open=p,close=p+.2,
                                 price_5=p+.04,minute_5=6,price_30=p-.1,minute_30=31))
        cls.obs,cls.fit=signals(cls.rows,cls.spec)
        w=fit_weights(cls.obs,cls.spec["evaluation_years"])
        cls.weights={str(k):v for k,v in w.items()}
        cls.entries=list(books(cls.rows,cls.obs,w,cls.spec))
        cls.pred={str(d):labels(cls.rows,cls.obs,cls.spec["evaluation_years"],d) for d in (5,30)}
        cls.result=analyze(cls.entries,cls.pred,cls.spec)

    def check_replay(self,entries):
        return verify(self.rows,self.obs,self.fit,self.weights,entries,self.pred,self.result,self.spec)

    def test_fractional_rebalance_both_directions(self):
        for weight in (.6,.15):
            cash,qty,q,fill,charge,drag=rebalance(500,5,weight,100,.005,.001)
            self.assertAlmostEqual(qty*100/(cash+qty*100),weight)
            self.assertAlmostEqual(1000-cash-qty*100,charge+drag)
            self.assertAlmostEqual(cash,500-q*fill-charge)

    def test_future_invariance_and_training_cutoff(self):
        revised=copy.deepcopy(self.rows)
        for r in revised[-10:]:
            r["close"]*=2
        obs,fit=signals(revised,self.spec)
        self.assertEqual(fit,self.fit)
        self.assertEqual(obs[:-10],self.obs[:-10])
        self.assertEqual(fit_weights(obs,[2020,2021]),fit_weights(self.obs,[2020,2021]))

    def test_executable_label_order(self):
        for x in self.pred["5"]:
            self.assertLess(x["signal_date"],x["date"])
            self.assertLess(x["date"],x["exit_date"])
            self.assertEqual(x["date"][:4],x["exit_date"][:4])
        self.assertFalse(any(x["date"]=="2020-12-31" for x in self.pred["5"]))
        self.assertEqual(self.result,analyze(self.entries,self.pred,self.spec))

    def test_independent_replay_and_tamper(self):
        self.assertEqual(self.check_replay(self.entries)["status"],"passed")
        bad=list(self.entries)
        bad[0]=dict(bad[0],execution_proxy_time=bad[0]["decision_time"])
        with self.assertRaisesRegex(ValueError,"execution_proxy_time"):
            self.check_replay(bad)
        bad[0]=dict(self.entries[0],cash=999)
        with self.assertRaisesRegex(ValueError,"cash"):
            self.check_replay(bad)
