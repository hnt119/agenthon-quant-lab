"""Predeclared endpoints and paired within-year circular block uncertainty."""
from collections import defaultdict
from math import sqrt
from statistics import mean, stdev

import numpy as np

from agenthon_quant.trading import period_metrics


def group(entries):
    books = defaultdict(list)
    for e in entries:
        books[e["scenario"], e["arm"]].append(e)
    return books


def summarize(path, initial):
    m = period_metrics(path, initial)
    daily = [e["daily_return"] for e in path]
    sd = stdev(daily)
    return dict(m, annual_return=(1+m["total_return"])**(365/len(path))-1,
                annual_vol=sd*sqrt(365), sharpe=mean(daily)*sqrt(365)/sd if sd else None)


def labels(rows, obs, years, delay):
    out=[]
    for i in range(1,len(rows)-1):
        a,b=rows[i:i+2]
        if int(a["date"][:4]) not in years or a["date"][:4]!=b["date"][:4]:
            continue
        price=f"price_{delay}"
        out.append(dict(date=a["date"],signal_date=obs[i-1]["date"],exit_date=b["date"],
                        positive=obs[i-1]["momentum20"]>0,entry=a[price],exit=b[price],
                        forward=b[price]/a[price]-1))
    return out


def contrast(observations):
    pos=[e["forward"] for e in observations if e["positive"]]
    neg=[e["forward"] for e in observations if not e["positive"]]
    a=mean(pos) if pos else None
    b=mean(neg) if neg else None
    return dict(positive_n=len(pos),nonpositive_n=len(neg),positive_mean=a,nonpositive_mean=b,
                difference=a-b if a is not None and b is not None else None)


def intervals(pairs, predictive, years, settings):
    rng=np.random.default_rng(settings["seed"])
    draws,block=settings["draws"],settings["block_sessions"]
    def resample(x):
        n=len(x)
        starts=rng.integers(0,n,size=(draws,(n+block-1)//block))
        ids=((starts[:,:,None]+np.arange(block))%n).reshape(draws,-1)[:,:n]
        return x[ids].sum(axis=1)
    perf=np.zeros((draws,4))
    states=np.zeros((draws,4))
    n=0
    for y in years:
        x=np.array([[a["daily_return"],b["daily_return"]] for a,b in zip(*pairs,strict=True)
                    if int(a["date"][:4])==y])
        n+=len(x)
        perf+=resample(np.column_stack((x,x*x)))
        p=np.array([[e["positive"],e["forward"]] for e in predictive if int(e["date"][:4])==y])
        on,ret=p.T
        states+=resample(np.column_stack((on,1-on,on*ret,(1-on)*ret)))
    sums,squares=perf[:,:2],perf[:,2:]
    with np.errstate(divide="ignore",invalid="ignore"):
        sr=sqrt(365)*sums/n / np.sqrt((squares-sums**2/n)/(n-1))
        samples=[sr[:,0]-sr[:,1],states[:,2]/states[:,0]-states[:,3]/states[:,1]]
    return {key:(np.quantile(arr,[.025,.975]).tolist() if np.isfinite(arr).all() else None)
            for key,arr in zip(("sharpe_delta","predictive_difference"),samples,strict=True)}


def analyze(entries, predictions, spec):
    paths=group(entries)
    metrics={}
    years=spec["evaluation_years"]
    for (scenario,arm),path in paths.items():
        initial=spec["initial_cash"]
        values={"pooled":summarize(path,initial)}
        for year in years:
            part=[r for r in path if int(r["date"][:4])==year]
            values[str(year)]=summarize(part,initial)
            initial=part[-1]["equity"]
        metrics.setdefault(scenario,{})[arm]=values
    prediction={key:{"pooled":contrast(lab),**{str(y):contrast([e for e in lab if int(e["date"][:4])==y])
                                               for y in years}} for key,lab in predictions.items()}
    delta={}
    for s,arms in metrics.items():
        delta[s]={}
        for p,m in arms["momentum20"].items():
            other=arms["passive_mix"][p]["sharpe"]
            delta[s][p]=m["sharpe"]-other if None not in (m["sharpe"],other) else None
    ci=intervals((paths["base","momentum20"],paths["base","passive_mix"]),predictions["5"],years,spec["uncertainty"])
    primary=delta["base"]["pooled"]
    pred=prediction["5"]["pooled"]["difference"]
    decision="inconclusive"
    if all(x is not None for x in [primary,pred,*ci.values(),*delta["base"].values(),
                                    delta["double_cost"]["pooled"],delta["later_fill"]["pooled"]]):
        if (all(v[0]>0 for v in ci.values()) and metrics["base"]["momentum20"]["pooled"]["total_return"]>0
                and sum(delta["base"][str(y)]>0 for y in years)>=3
                and all(delta[s]["pooled"]>0 for s in ("double_cost","later_fill"))):
            decision="candidate for prospective paper observation"
        elif (primary<=0 and pred<=0) or any(v[1]<=0 for v in ci.values()):
            decision="unsupported in the tested sample"
    return dict(portfolios=metrics,prediction=prediction,sharpe_delta=delta,interval95=ci,decision=decision)
