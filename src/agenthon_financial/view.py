"""Render verified records using the original Edge Lab read-only pilot charts."""
import csv
from html import escape
from itertools import accumulate
import json

from agenthon_btc.view import COLORS, DASHES, chart, standalone
from .analysis import group
from .reader import overview_html

NAMES={"momentum20":"Momentum","passive_mix":"Passive BTC/cash","momentum20_fft":"Momentum + FFT",
       "buy_and_hold":"Buy and hold","cash":"Cash"}
SCENARIOS={"base":"Base","gross":"Zero friction","double_cost":"Double costs","later_fill":"30-minute delay"}
ATTRIBUTION=('Adapted from <a href="https://www.kaggle.com/datasets/mczielinski/bitcoin-historical-data">Bitcoin Historical Data</a>'
             ' by Zielak (mczielinski), normalized by <a href="https://github.com/ff137/bitstamp-btcusd-minute-data">ff137</a>. '
             'UTC session prices, derived records, tables and figures are distributed under '
             '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.')


def table(columns,rows):
    heads="".join(f'<th scope="col">{escape(k)}</th>' for k in columns)
    body=[]
    for label,*values in rows:
        body.append('<tr><th scope="row">'+escape(str(label))+"</th>"+"".join("<td>"+escape(str(x))+"</td>" for x in values)+"</tr>")
    return '<div class="btc-scroll" tabindex="0"><table><thead><tr>'+heads+"</tr></thead><tbody>"+"".join(body)+"</tbody></table></div>"


def graphs(paths,dates,active,fit):
    series=list(NAMES)[:4]
    middle=next(d for d in dates if d.startswith("2022"))
    pct=lambda v:f"{v:.0%}"
    money=lambda v:f"{v:,.0f}"
    for field,title,formatter in (("equity","Marked portfolio equity · USD",money),
                                  ("drawdown","Loss from running peak",pct),
                                  ("exposure","BTC fraction at the close",pct),
                                  ("costs","Cumulative fees and adverse slippage · USD",money)):
        series_values=[]
        for arm in series:
            path=paths["base",arm]
            data=list(accumulate(e["fee"]+e["slippage_cost"] for e in path)) if field=="costs" else [e[field] for e in path]
            series_values.append((NAMES[arm],data))
        yield chart(title,series_values,dates,middle,formatter,field=="drawdown")
    for key,title,threshold,formatter in (("momentum20","Prior close · trailing 20-session return",0,pct),
                                         ("entropy","Prior close · normalized spectral entropy",fit["fft"]["median"],lambda x:f"{x:.3f}")):
        yield chart(title,[("Prior close",[s[key] for s in active]),("Frozen cutoff",[threshold]*len(dates))],dates,middle,formatter)


def panel(verified):
    record,spec,obs,fit,entries,result,receipt=verified
    metrics=result["portfolios"]
    paths=group(entries)
    plain=paths["base","momentum20"]
    dates=[e["date"] for e in plain]
    features={e["date"]:e for e in obs}
    active=[features[e["signal_session"]] for e in plain]
    out=['<section class="btc-pilot"><h1>Does BTC momentum pay for trading?</h1>',
         overview_html(spec,result),
         '<p><a href="#portfolio">Compare the accounts</a> · <a href="#evidence">Inspect assumptions and the run receipt</a>. '
         'Reproduce locally with <code>quant-lab btc-study</code>.</p>',
         '<h2 id="portfolio">Portfolio comparison</h2>']
    def row(a,m):
        sr=m["sharpe"]
        return [a,f'{m["total_return"]:+.2%}',f'{m["annual_return"]:+.2%}',f'{sr:.3f}' if sr is not None else "Undefined",
                f'{m["annual_vol"]:.2%}',f'{m["max_drawdown"]:.2%}',f'{m["mean_close_exposure"]:.2%}',
                f'{m["turnover"]:.2f}×',m["trade_events"],f'{m["transaction_cost"]:,.2f}']
    cols=["Portfolio","Total","Annualized","Sharpe","Volatility","Drawdown","BTC weight","Turnover","Fills","Costs (USD)"]
    out.append(table(cols,[row(name,metrics["base"][a]["pooled"]) for a,name in NAMES.items()]))
    out.extend(graphs(paths,dates,active,fit))
    out.append('<p>The vertical marker is January 1, 2022. Cash stays at $10,000. All accounts carry across January boundaries.</p>')
    out.append('<h2>Annual folds and sensitivities</h2>')
    for s,name in SCENARIOS.items():
        out.append(f'<details><summary>{name}</summary>')
        for p in ["pooled",*map(str,spec["evaluation_years"])]:
            out.append(f'<h3>{p.capitalize()}</h3>'+table(cols,[row(label,metrics[s][arm][p]) for arm,label in NAMES.items()]))
        out.append("</details>")
    out.append('<h2>Daily decisions</h2><p>UTC dates are execution sessions. BTC targets use the preceding completed close. '
               'Dash denotes a session without a fill. The compressed journal includes all five accounts in every scenario.</p>')
    for y in spec["evaluation_years"]:
        out.append(f'<details><summary>{y} · daily base decisions</summary>')
        out.append(table(["Session","Prior close","Momentum","Entropy","Plain target","FFT target","Plain fill UTC",
                          "Plain units traded","Fee USD","Cash USD","BTC units","Equity USD"],
                         [(e["date"],s["date"],f'{s["momentum20"]:+.2%}',f'{s["entropy"]:.5f}',
                           s["targets"]["momentum20"],s["targets"]["momentum20_fft"],e["execution_time"] or "—",
                           f'{e["trade_quantity"]:.6f}',f'{e["fee"]:.2f}',f'{e["cash"]:,.2f}',f'{e["shares"]:.6f}',f'{e["equity"]:,.2f}')
                          for e,s in zip(plain,active,strict=True) if int(e["date"][:4])==y]))
        out.append("</details>")
    meta={"assumptions":spec,"independent_checks":receipt,"runtime":record,"uncertainty":result["interval95"],
          "annual_passive_fit":fit["annual_weights"]}
    out.append('<details id="evidence"><summary>Assumptions, uncertainty and run identity</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'
               +escape(json.dumps(meta,indent=2,sort_keys=True))+"</pre></details><p>"+ATTRIBUTION+"</p></section>")
    return "\n".join(out)


def render(verified,out):
    html=panel(verified)
    with (out/"dashboard.html").open("x") as f:
        f.write(standalone(html).replace("BTC/USD momentum pilot ·","BTC/USD momentum study ·"))
    # Keep the same chart geometry and paths as the interactive evidence view.
    svg=html.split('<svg role="img"',1)[1].split('</svg>',1)[0].replace('0 0 760 192','0 0 760 231',1)
    legend=[]
    for i,arm in enumerate(list(NAMES)[:4]):
        x=70+i*173
        legend.append(f'<path d="M{x} 205h28" fill="none" stroke="{COLORS[i]}" stroke-width="2" '
                      f'stroke-dasharray="{DASHES[i]}"/><text x="{x+33}" y="209" font-size="12">{NAMES[arm]}</text>')
    with (out/"equity.svg").open("x") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" role="img"'+svg+"".join(legend)+
                '<desc>Momentum (brown dashed), passive BTC/cash (gray dotted), momentum + FFT (teal), buy and hold (purple dash-dot). '
                'Zielak / ff137, adapted under CC BY-SA 4.0.</desc></svg>\n')
    with (out/"tables.csv").open("x",newline="") as f:
        writer=None
        for s,arms in verified[-2]["portfolios"].items():
            for a,periods in arms.items():
                for p,metrics in periods.items():
                    row=dict(scenario=s,arm=a,period=p,**metrics)
                    if writer is None:
                        writer=csv.DictWriter(f,fieldnames=list(row),lineterminator="\n")
                        writer.writeheader()
                    writer.writerow(row)
