"""Independent replay from admitted quotes, direct DFTs and post-trade accounting identities."""
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from math import fsum, isclose, log, prod, sqrt
from statistics import mean, median, stdev

from agenthon_btc.verify import entropy


def equal(actual, expected, name):
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        ok=isinstance(actual,(int,float)) and isclose(actual,expected,rel_tol=3e-10,abs_tol=2e-8)
    else:
        ok=actual==expected
    if not ok:
        raise ValueError(f"Independent verification failed: {name} ({actual!r} vs {expected!r})")


def verify(rows,obs,fit,weights,entries,predictions,result,spec):
    returns=[log(b["close"]/a["close"]) for a,b in pairwise(rows)]
    signals=[]
    ent=[entropy(returns[i-64:i]) if i>=64 else None for i in range(len(rows))]
    cutoff=spec["development"][1]
    members=[i for i,r in enumerate(rows) if r["date"]<=cutoff and ent[i] is not None]
    threshold=median(ent[i] for i in members)
    equal(fit["median"],threshold,"entropy median")
    equal(fit["train_end"],cutoff,"training end")
    equal([r["date"] for r in fit["members"]],[rows[i]["date"] for i in members],"training membership")
    for m,i in zip(fit["members"],members,strict=True):
        equal(m["entropy"],ent[i],"fit value")
    for i,(r,s) in enumerate(zip(rows,obs,strict=True)):
        mom=r["close"]/rows[i-20]["close"]-1 if i>=20 else None
        for key,val in (("date",r["date"]),("momentum20",mom),("entropy",ent[i]),
                        ("entropy_status","warmup" if i<64 else "no_variation" if ent[i] is None else "ok")):
            equal(s[key],val,key)
        on=i>=20 and r["close"]>rows[i-20]["close"]
        live=r["date"]>=cutoff
        # On a median tie, compare the values produced by the same DFT arithmetic.
        targets=dict(cash=0,buy_and_hold=int(live),momentum20=int(live and on),
                     momentum20_fft=int(live and on and ent[i] is not None and ent[i]<=threshold))
        equal(s["targets"],targets,"completed-close targets")
        signals.append(on)
    years=spec["evaluation_years"]
    for y in years:
        past=[signals[i] for i in range(20,len(rows)) if int(rows[i]["date"][:4])<y]
        w=weights[str(y)]
        for k,v in dict(valid=len(past),positive=sum(past),weight=mean(past),through=f"{y-1}-12-31").items():
            equal(w[k],v,"past-only passive fit")
    dates=[i for i,r in enumerate(rows) if int(r["date"][:4]) in years]
    paths={}
    for e in entries:
        paths.setdefault((e["scenario"],e["arm"]),[]).append(e)
    equal(set(paths),{(s,a) for s in spec["scenarios"] for a in spec["arms"]},"portfolio coverage")
    for (scenario,arm),path in paths.items():
        delay,fee,slip=spec["scenarios"][scenario]
        cash,shares,prior,peak=spec["initial_cash"],0.,spec["initial_cash"],spec["initial_cash"]
        for i,e in zip(dates,path,strict=True):
            r=rows[i]
            day=r["date"]
            boundary=datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
            proxy=boundary+timedelta(minutes=r[f"minute_{delay}"])
            quantity=e["trade_quantity"]
            stamp=lambda dt:dt.isoformat(timespec="seconds").replace("+00:00","Z")
            quoted=r[f"price_{delay}"]
            pre=cash+shares*quoted
            price=quoted*(1+(1 if quantity>0 else -1)*slip/10000) if quantity else None
            charge=abs(quantity)*(price or 0)*fee/10000
            drag=abs(quantity)*quoted*slip/10000
            cash-=quantity*(price or 0)+charge
            shares+=quantity
            end=cash+shares*r["close"]
            peak=max(peak,end)
            if arm=="passive_mix":
                target=weights[day[:4]]["weight"] if day.endswith("-01-01") else None
            else:
                target=obs[i-1]["targets"][arm]
            if target is None:
                equal(quantity,0,"passive drift")
            else:
                equal(shares*quoted/(cash+shares*quoted),target,"post-cost target")
            equal(cash>=-1e-7 and shares>=-1e-10,True,"long-only solvency")
            values=dict(date=day,signal_session=rows[i-1]["date"],feature_cutoff=stamp(boundary),
                        decision_time=stamp(boundary),execution_proxy_time=stamp(proxy),
                        execution_time=stamp(proxy) if quantity else None,quote=quoted,close=r["close"],
                        target_for_open=target,fill_price=price,fee=charge,slippage_cost=drag,cash=cash,
                        shares=shares,equity=end,pnl=end-prior,exposure=shares*r["close"]/end,
                        turnover=abs(quantity)*quoted/pre,quoted_notional=abs(quantity)*quoted,
                        daily_return=end/prior-1,drawdown=1-end/peak)
            for key,v in values.items():
                equal(e[key],v,f"{day} {arm} {key}")
            prior=end
        for p in ["pooled",*map(str,years)]:
            section=[e for e in path if p=="pooled" or e["date"].startswith(p)]
            m=result["portfolios"][scenario][arm][p]
            rets=[e["daily_return"] for e in section]
            start=section[0]["equity"]-section[0]["pnl"]
            eqpeak=start
            dd=0
            for e in section:
                eqpeak=max(eqpeak,e["equity"])
                dd=max(dd,1-e["equity"]/eqpeak)
            growth=prod(1+x for x in rets)
            vol=stdev(rets)*sqrt(365)
            for key,v in dict(total_return=growth-1,ending_equity=start*growth,starting_equity=start,
                              annual_return=growth**(365/len(rets))-1,annual_vol=vol,
                              sharpe=mean(rets)*365/vol if vol else None,max_drawdown=dd,
                              turnover=fsum(e["turnover"] for e in section),
                              trade_events=sum(bool(e["trade_quantity"]) for e in section),
                              fees=fsum(e["fee"] for e in section),slippage_cost=fsum(e["slippage_cost"] for e in section),
                              mean_close_exposure=mean(e["exposure"] for e in section)).items():
                equal(m[key],v,f"{scenario} {arm} {p} {key}")
    for delay in ("5","30"):
        usable=[i for i in dates if i+1<len(rows) and rows[i]["date"][:4]==rows[i+1]["date"][:4]]
        for i,label in zip(usable,predictions[delay],strict=True):
            a,b=rows[i:i+2]
            p,q=a["price_"+delay],b["price_"+delay]
            for key,v in dict(date=a["date"],signal_date=rows[i-1]["date"],exit_date=b["date"],
                              positive=signals[i-1],entry=p,exit=q,forward=(q-p)/p).items():
                equal(label[key],v,"executable label "+key)
        for p in ["pooled",*map(str,years)]:
            by_state=[[e["forward"] for e in predictions[delay] if e["positive"]==state
                       and (p=="pooled" or e["date"].startswith(p))] for state in (True,False)]
            a,b=by_state
            est=result["prediction"][delay][p]
            for key,val in dict(positive_n=len(a),nonpositive_n=len(b),positive_mean=mean(a) if a else None,
                                nonpositive_mean=mean(b) if b else None,difference=mean(a)-mean(b) if a and b else None).items():
                equal(est[key],val,"predictive summary")
    return dict(status="passed",sessions=len(rows),fit_members=len(members),portfolio_sessions=len(entries),
                portfolios=len(paths),verified_period_summaries=len(paths)*(1+len(years)),
                predictive_labels={d:len(v) for d,v in predictions.items()},
                scope="Direct DFT, fit membership, prior-close targets, independent annual weights, delayed quotes, cash and units, net/gross fills, compounding, risk, exposures and paired label membership. Conditional bootstrap reproducibility is checked by offline regeneration.")
